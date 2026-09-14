---
name: athena-file-retrieve
description: Resolve a note's storage path and read the original source file (PDF, TXT, HTML) referenced by an Obsidian vault companion note.
platforms: [linux]
---

# Athena File Retrieve Skill

Use this skill when the agent has found an Obsidian companion note (via `athena-vault-search`) and needs to read the **original source file** it references — for example, the actual PDF, text document, or HTML report stored in `storage/`.

This skill answers follow-up questions like:
- "What does the full NUWC flyer say?"
- "Can you read the actual research document, not the summary?"
- "Show me the full text of that receipt."

---

## Storage Directory Map

All original (non-markdown) files processed through the inbox land in:

```
/home/archer/ATHENA/storage/
```

Markdown files processed from the inbox are filed directly inside the vault under their area:
```
/home/archer/ATHENA/obsidian_vault/02_Areas/<Category>/
/home/archer/ATHENA/obsidian_vault/03_Resources/
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
grep "meta_storage_relative_path" /home/archer/ATHENA/obsidian_vault/02_Areas/Career/2026-05-23_nuwc_recruiting_event_flyer_may_30.md
```

This will return something like:
```
meta_storage_relative_path: "2026-05-23_nuwc_recruiting_event_flyer_may_30.pdf"
```

The absolute path to the original file is then:
```
/home/archer/ATHENA/storage/<meta_storage_relative_path_value>
```

Or, if the value starts with `obsidian_vault/` or `storage/`, build it as:
```
/home/archer/ATHENA/<meta_storage_relative_path_value>
```

---

## Step 2: Read the Original File

### Text Files (.txt, .md, .html)

```bash
cat /home/archer/ATHENA/storage/<filename>
```

*Example:*
```bash
cat /home/archer/ATHENA/storage/2026-05-25_CS_NUWK_Newport_Research_and_Undersea_Technology.txt
```

### PDF Files (.pdf) — Extract Text

```bash
pdftotext /home/archer/ATHENA/storage/<filename.pdf> -
```

*Example:*
```bash
pdftotext /home/archer/ATHENA/storage/2026-05-23_nuwc_recruiting_event_flyer_may_30.pdf -
```

### HTML Files (.html) — Strip Tags for Readable Text

```bash
cat /home/archer/ATHENA/storage/<filename.html> | sed 's/<[^>]*>//g' | sed '/^[[:space:]]*$/d'
```

*Example:*
```bash
cat /home/archer/ATHENA/storage/2026-05-25_study_nuwc_company_research.html | sed 's/<[^>]*>//g' | sed '/^[[:space:]]*$/d'
```

---

## Step 3: List All Files in Storage

To see every original file archived in storage:
```bash
ls -1t /home/archer/ATHENA/storage/
```

To search storage filenames by keyword:
```bash
ls /home/archer/ATHENA/storage/ | grep -i "<keyword>"
```

*Example — find all NUWC-related source files:*
```bash
ls /home/archer/ATHENA/storage/ | grep -i "nuwc"
```

---

## Common Patterns

### "Read the full document behind this note"
1. `grep "meta_storage_relative_path"` the companion note → get the filename
2. Determine the file type from the extension
3. Use `cat`, `pdftotext`, or `sed` strip accordingly

### "Find and read the resume"
```bash
ls /home/archer/ATHENA/storage/ | grep -i "resume"
# Then:
pdftotext /home/archer/ATHENA/storage/<resume_filename>.pdf -
```

### "What notes reference this file?"
Search the vault for the filename:
```bash
grep -ri "<filename_stem>" /home/archer/ATHENA/obsidian_vault --include="*.md" -l
```

---

## File Type Reference

| Extension | How to Read |
|---|---|
| `.txt` | `cat <path>` |
| `.md` | `cat <path>` |
| `.pdf` (digital) | `pdftotext <path> -` |
| `.html` | `cat <path> \| sed 's/<[^>]*>//g'` |
| `.ics` | `cat /home/archer/ATHENA/obsidian_vault/calendar.ics` |

---

## Related Skills

- `athena-vault-search` — Find the companion note first (get the path, then use this skill).
- `athena-db-view` — Query structured DB records linked to the same file via `file_id`.
