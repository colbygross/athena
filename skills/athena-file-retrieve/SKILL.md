---
name: athena-file-retrieve
description: Resolve a note's storage path and read the original source file (PDF, TXT, HTML) referenced by an Obsidian vault companion note.
platforms: [linux]
---

# Athena File Retrieve Skill

Use this skill when the agent has found an Obsidian companion note (via `athena-vault-search`) and needs to read the **original source file** it references — for example, the actual PDF, text document, or HTML report stored in `storage/`.

This skill answers follow-up questions like:
- "What does the full conference flyer say?"
- "Can you read the actual research document, not the summary?"
- "Show me the full text of that receipt."

---

## Storage Directory Map

All original (non-markdown) files processed through the inbox land in:

```
storage/
```

Markdown files processed from the inbox are filed directly inside the vault under their area:
```
obsidian_vault/02_Areas/<Category>/
obsidian_vault/03_Resources/
```

---

## Step 1: Extract the Storage Path from a Companion Note

Every companion note has a `meta_storage_relative_path` field in its YAML frontmatter. This is the relative path to the original file from the project root.

Read the companion note and extract this field:
```bash
grep "meta_storage_relative_path" "<path_to_companion_note.md>"
```

*Example:*
```bash
grep "meta_storage_relative_path" obsidian_vault/02_Areas/Career/2026-06-01_sample_flyer.md
```

This will return something like:
```
meta_storage_relative_path: "2026-06-01_sample_flyer.pdf"
```

The absolute path to the original file is then:
```
storage/<meta_storage_relative_path_value>
```

Or, if the value starts with `obsidian_vault/` or `storage/`, build it as:
```
/<meta_storage_relative_path_value>
```

---

## Step 2: Read the Original File

### Text Files (.txt, .md, .html)

```bash
cat storage/<filename>
```

*Example:*
```bash
cat storage/2026-06-01_tech_research_paper.txt
```

### PDF Files (.pdf) — Extract Text

```bash
pdftotext storage/<filename.pdf> -
```

*Example:*
```bash
pdftotext storage/2026-06-01_sample_flyer.pdf -
```

### HTML Files (.html) — Strip Tags for Readable Text

```bash
cat storage/<filename.html> | sed 's/<[^>]*>//g' | sed '/^[[:space:]]*$/d'
```

*Example:*
```bash
cat storage/2026-06-01_company_research.html | sed 's/<[^>]*>//g' | sed '/^[[:space:]]*$/d'
```

---

## Step 3: List All Files in Storage

To see every original file archived in storage:
```bash
ls -1t storage/
```

To search storage filenames by keyword:
```bash
ls storage/ | grep -i "<keyword>"
```

*Example — find all receipt files:*
```bash
ls storage/ | grep -i "receipt"
```

---

## Common Patterns

### "Read the full document behind this note"
1. `grep "meta_storage_relative_path"` the companion note → get the filename
2. Determine the file type from the extension
3. Use `cat`, `pdftotext`, or `sed` strip accordingly

### "Find and read the resume"
```bash
ls storage/ | grep -i "resume"
# Then:
pdftotext storage/<resume_filename>.pdf -
```

### "What notes reference this file?"
Search the vault for the filename:
```bash
grep -ri "<filename_stem>" obsidian_vault --include="*.md" -l
```

---

## File Type Reference

| Extension | How to Read |
|---|---|
| `.txt` | `cat <path>` |
| `.md` | `cat <path>` |
| `.pdf` (digital) | `pdftotext <path> -` |
| `.html` | `cat <path> \| sed 's/<[^>]*>//g'` |
| `.ics` | `cat obsidian_vault/calendar.ics` |

---

## Related Skills

- `athena-vault-search` — Find the companion note first (get the path, then use this skill).
- `athena-db-view` — Query structured DB records linked to the same file via `file_id`.
