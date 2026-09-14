---
name: athena-vault-search
description: Search the Athena Obsidian vault by filename, tag, or full-text content to locate notes, projects, and companion documents.
platforms: [linux]
---

# Athena Vault Search Skill

Use this skill whenever the user asks about a topic, event, person, company, project, or concept that may exist as a note in the vault. The vault lives at `/home/archer/ATHENA/obsidian_vault/`.

This skill answers questions like:
- "Do I have any notes about NUWC?"
- "What projects am I currently working on?"
- "Show me everything tagged #high."
- "What did I write about red-black trees?"

---

## Vault Directory Map

| Directory | What Lives Here |
|---|---|
| `01_Projects/` | Active project notes (human-authored, long-form) |
| `02_Areas/Career/` | Career companion notes (job applications, resume docs) |
| `02_Areas/Finances/` | Financial companion notes (receipts, invoices) |
| `02_Areas/Fitness/` | Workout companion notes |
| `02_Areas/Health/` | Health document companion notes |
| `02_Areas/Learning/` | Study session companion notes |
| `02_Areas/Habits/` | Habit tracking notes |
| `03_Resources/` | General reference documents |
| `04_Archives/` | Archived notes |
| `Daily_Briefs/` | Auto-generated daily briefings |
| `Summaries/` | Auto-generated aggregate summaries (finances, health, learning/career) |
| `Inbox/` | Staging area for unprocessed files |
| `tasks.md` | Synced task checklist |

---

## Search Methods

### 1. Search by Filename (Name / Topic)

Find notes whose filename matches a keyword:
```bash
find /home/archer/ATHENA/obsidian_vault -type f -name "*.md" | grep -i "<keyword>"
```

*Example — find all NUWC-related notes:*
```bash
find /home/archer/ATHENA/obsidian_vault -type f -name "*.md" | grep -i "nuwc"
```

*Example — find all notes from a specific date:*
```bash
find /home/archer/ATHENA/obsidian_vault -type f -name "2026-05-23*.md"
```

---

### 2. Search by Tag

Tags in `tasks.md` and companion notes follow the format `#tagname`. Common tags:
- Priority: `#high`, `#medium`, `#low`
- Importance: `#major`, `#minor`
- Category tags embedded in frontmatter: `category: career`, `category: fitness`, etc.

Find all notes or tasks carrying a specific tag:
```bash
grep -r "#<tag>" /home/archer/ATHENA/obsidian_vault --include="*.md" -l
```

*Example — find all high-priority tasks:*
```bash
grep -r "#high" /home/archer/ATHENA/obsidian_vault --include="*.md" -l
```

*Example — list all lines tagged #major across the whole vault:*
```bash
grep -rn "#major" /home/archer/ATHENA/obsidian_vault --include="*.md"
```

---

### 3. Full-Text / Keyword Search

Search inside note content for any keyword, phrase, or concept:
```bash
grep -ri "<keyword>" /home/archer/ATHENA/obsidian_vault --include="*.md" -l
```

*Example — find all notes mentioning "NUWC":*
```bash
grep -ri "nuwc" /home/archer/ATHENA/obsidian_vault --include="*.md" -l
```

*Example — find notes mentioning a company name with context lines:*
```bash
grep -ri "naval undersea" /home/archer/ATHENA/obsidian_vault --include="*.md" -B2 -A5
```

*Example — find notes with a specific frontmatter field value:*
```bash
grep -ri "meta_status: \"applied\"" /home/archer/ATHENA/obsidian_vault --include="*.md" -l
```

---

### 4. Read a Specific Note

Once a note path is found, read its full content:
```bash
cat "<absolute_path_to_note>"
```

*Example:*
```bash
cat /home/archer/ATHENA/obsidian_vault/02_Areas/Career/2026-05-23_nuwc_recruiting_event_flyer_may_30.md
```

---

### 5. Read Obsidian Wikilinks / Backlinks

Companion notes embed `[[WikiLink]]` references. To find all notes that link to a given topic:
```bash
grep -ri "\[\[<topic>\]\]" /home/archer/ATHENA/obsidian_vault --include="*.md" -l
```

---

### 6. Read Pre-Built Summaries

For broad overview questions, read the auto-generated summaries directly. These are always up to date:
```bash
cat /home/archer/ATHENA/obsidian_vault/Summaries/Financial_Summary.md
cat /home/archer/ATHENA/obsidian_vault/Summaries/Health_Fitness_Summary.md
cat /home/archer/ATHENA/obsidian_vault/Summaries/Learning_Career_Summary.md
```

For today's full daily brief:
```bash
cat /home/archer/ATHENA/obsidian_vault/Daily_Briefs/Daily_Brief_$(date +%Y-%m-%d).md
```

---

### 7. List All Notes in a Category Directory

```bash
ls -1t /home/archer/ATHENA/obsidian_vault/02_Areas/<Category>/
ls -1t /home/archer/ATHENA/obsidian_vault/01_Projects/
```

*Example — list all career-related notes, newest first:*
```bash
ls -1t /home/archer/ATHENA/obsidian_vault/02_Areas/Career/
```

---

## Frontmatter Reference

Every companion note (auto-generated) has YAML frontmatter with these searchable fields:

| Field | Description |
|---|---|
| `type` | Always `document-context` for companion notes |
| `category` | `finances`, `health`, `fitness`, `learning`, `career`, `general` |
| `original_name` | The original filename dropped into the inbox |
| `processed_at` | Timestamp when the agent processed it |
| `meta_storage_relative_path` | Relative path to the original file in `storage/` or vault |
| `meta_*` | Category-specific fields (e.g., `meta_company`, `meta_status`, `meta_topic`) |

---

## Related Skills

- `athena-file-retrieve` — Resolve a note's `meta_storage_relative_path` to an absolute path and read the original file.
- `athena-db-view` — Query the SQLite database for structured data corresponding to a vault note.
- `athena-db-edit` — Insert or update database records.
