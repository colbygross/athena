---
name: athena-mind
description: Scan Obsidian Vault Markdown notes to suggest or apply cross-links, detect consolidation opportunities, recommend directory map pages (MOCs), and audit flat storage to prevent orphan files.
platforms: [linux]
---

# Athena Mind Skill

This skill customizes the core philosophies of persistent agent memory (inspired by `obsidian-mind`) for the Athena OS. It provides mechanisms to scan notes, automatically link concept mentions, consolidate redundant records, recommend Map of Content (MOC) index maps, and audit flat storage to ensure every file is linked in the vault.

## Usage

The utility is driven by `backend/athena_mind.py`. Commands should be run from the project root ``.

### 1. Audit Storage Registry

Ensure no information is lost by cross-referencing all files in `storage/` against the Obsidian Vault Markdown notes and the SQLite database:
```bash
python backend/athena_mind.py audit-storage
```

If orphan or unregistered files are discovered, append the `--fix` flag to automatically create companion frontmatter notes in the appropriate category folders and register the assets inside the SQLite database:
```bash
python backend/athena_mind.py audit-storage --fix
```

---

### 2. Optimize Wiki-Linking

Scan the vault for plain text mentions of other note titles. It compares names by decreasing length (to prevent partial matches) and inserts `[[Note Title]]` links automatically:
```bash
python backend/athena_mind.py find-links
```

To automatically write the link improvements back to the Markdown files in the vault:
```bash
python backend/athena_mind.py find-links --fix
```

---

### 3. Analyze Vault Clusters

Inspect the vault directories to group notes, detect redundant notes (consolidation candidates), and identify clusters that warrant Directory Map notes (MOCs):
```bash
python backend/athena_mind.py analyze-vault
```

---

### 4. Run Full System Optimization

Run all checks consecutively:
```bash
python backend/athena_mind.py run-all [--fix]
```

---

## Playbook and Guidelines for Agents

*   **When to run**: Run `athena-mind` at the end of a long research session, after bulk imports, or during a workspace cleanup session.
*   **Preventing link spam**: The script automatically excludes common generic titles (e.g., "tasks", "inbox", "summaries") defined in `STOP_WORDS` to prevent cluttering notes with link definitions.
*   **Broken Link Resolution**: If the storage auditor reports broken references, find where the file was moved or check if it was deleted.
*   **MOC Integration**: If `analyze-vault` recommends a Map of Content directory page (e.g., `Learning_MOC.md`), create a Markdown file in the vault root listing the links in a structured, themed index.

## Related Skills

- `athena-vault-search` — Core search playbook for finding specific note topics.
- `athena-file-retrieve` — Read the original file behind a companion note.
- `athena-db-view` — Introspect database structures.
