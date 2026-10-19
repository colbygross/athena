"""
Private data: things only the local machine (dashboard, Obsidian, the local LLM) may read.
Cloud models reaching Athena through the MCP server never see private data.

What is private:
  - a vault note with `private: true` in its frontmatter, or any note inside a `Private/` folder;
  - an ingested file flagged private (processed_files.private) or whose companion note is private;
  - data derived from those: rows created from a private file (file_id) and tasks written
    inside a private note (tasks.source_file);
  - lines of generated notes (daily briefs, summaries) built from private data. Generators tag
    those lines with PRIVATE_MARKER, an Obsidian comment that is hidden in reading view; the MCP
    server drops tagged lines and the dashboard just hides the tag.

Cloud agents may mark notes private but never unmark them; only the local dashboard can.
"""
import os
import re

PRIVATE_FOLDER = "Private"
PRIVATE_MARKER = "%%private%%"

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(\n|\Z)", re.DOTALL)
_PRIVATE_LINE_RE = re.compile(r"^private\s*:\s*(true|yes|1)\s*$", re.IGNORECASE | re.MULTILINE)

# abs path -> (mtime, is_private); avoids re-reading unchanged notes
_note_cache = {}


def _vault_dir():
    import agent  # lazy: agent imports this module
    return os.path.realpath(agent.VAULT_DIR)


def _normalize(rel_path):
    return (rel_path or "").replace("\\", "/").lstrip("/")


def in_private_folder(rel_path):
    return PRIVATE_FOLDER in _normalize(rel_path).split("/")


def frontmatter_is_private(text):
    match = _FRONTMATTER_RE.match(text or "")
    return bool(match and _PRIVATE_LINE_RE.search(match.group(1)))


def is_private_note(rel_path):
    """True if the vault note at rel_path is private (folder or frontmatter)."""
    rel_path = _normalize(rel_path)
    if in_private_folder(rel_path):
        return True
    full = os.path.join(_vault_dir(), rel_path)
    try:
        mtime = os.path.getmtime(full)
    except OSError:
        return False
    cached = _note_cache.get(full)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            head = f.read(8192)
    except OSError:
        return False
    private = frontmatter_is_private(head)
    _note_cache[full] = (mtime, private)
    return private


def private_note_paths():
    """Vault-relative paths ('a/b.md') of every private note."""
    vault = _vault_dir()
    paths = set()
    for dirpath, dirnames, filenames in os.walk(vault):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if name.endswith(".md"):
                rel = os.path.relpath(os.path.join(dirpath, name), vault).replace(os.sep, "/")
                if is_private_note(rel):
                    paths.add(rel)
    return paths


def companion_note_path(new_path, category):
    """Vault-relative note for an ingested file (the file itself for markdown, else its companion note)."""
    import agent
    new_path = _normalize(new_path)
    if new_path.startswith("obsidian_vault/"):
        return new_path[len("obsidian_vault/"):]
    stem = os.path.splitext(os.path.basename(new_path))[0]
    return f"{agent.CATEGORIES.get(category, '03_Resources')}/{stem}.md"


def private_file_ids(conn):
    """ids of processed_files that are private (flagged, or their note is private)."""
    rows = conn.execute("SELECT id, new_path, category, private FROM processed_files").fetchall()
    return {r["id"] for r in rows if r["private"] or is_private_note(companion_note_path(r["new_path"], r["category"]))}


def task_is_private(source_file, private_notes):
    source_file = _normalize(source_file)
    return bool(source_file) and (source_file in private_notes or in_private_folder(source_file))


def marker(private):
    """Suffix for a generated-note line built from private data."""
    return f" {PRIVATE_MARKER}" if private else ""


def strip_private_lines(text):
    """Cloud view of a generated note: drop every line tagged private."""
    return "\n".join(line for line in text.split("\n") if PRIVATE_MARKER not in line)


def hide_markers(text):
    """Local view of a generated note: keep the lines, drop the tag."""
    return text.replace(f" {PRIVATE_MARKER}", "").replace(PRIVATE_MARKER, "")


def set_note_private(rel_path, private=True):
    """
    Add or remove `private: true` in a note's frontmatter. Notes inside a Private/ folder stay
    private regardless. Returns the note's privacy afterwards.
    """
    import agent
    rel_path = _normalize(rel_path)
    full = os.path.join(_vault_dir(), rel_path)
    with open(full, "r", encoding="utf-8") as f:
        text = f.read()
    match = _FRONTMATTER_RE.match(text)
    if match:
        body = _PRIVATE_LINE_RE.sub("", match.group(1)).strip("\n")
        lines = [l for l in body.split("\n") if l.strip()]
        if private:
            lines.append("private: true")
        rest = text[match.end():]
        text = (f"---\n" + "\n".join(lines) + "\n---\n" + rest) if lines else rest.lstrip("\n")
    elif private:
        text = "---\nprivate: true\n---\n" + text
    agent.write_file_atomically(full, text)
    _note_cache.pop(full, None)
    return is_private_note(rel_path)


def set_file_private(conn, file_id, private=True):
    """Flag an ingested file (and its companion note) private or not. Local use only."""
    row = conn.execute("SELECT new_path, category FROM processed_files WHERE id = ?", (file_id,)).fetchone()
    if not row:
        raise ValueError(f"File {file_id} not found")
    conn.execute("UPDATE processed_files SET private = ? WHERE id = ?", (int(bool(private)), file_id))
    note = companion_note_path(row["new_path"], row["category"])
    if os.path.exists(os.path.join(_vault_dir(), note)):
        set_note_private(note, private)
