#!/usr/bin/env python3
"""
Athena Mind: Link Optimizer, Storage Auditor, and Consolidation Analyzer.
Scans Obsidian Vault notes to optimize inter-note linking, ensure flat storage
integrity, and suggest directory maps (MOCs) and tag consolidation.
"""
import sys
import os
import re
import argparse
from pathlib import Path
import sqlite3
import json

# Add backend directory to system path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from database import get_db_connection
    from agent import VAULT_DIR, STORAGE_DIR, CATEGORIES, save_data_to_db, create_obsidian_note
except ImportError as e:
    print(f"Error importing Athena backend modules: {e}")
    sys.exit(1)

# Text coloring for HUD style
CYAN = "\033[1;36m"
GREEN = "\033[1;32m"
PINK = "\033[1;35m"
YELLOW = "\033[1;33m"
RESET = "\033[0m"

# Common words to exclude from autolinking to avoid spamming links
STOP_WORDS = {
    "tasks", "inbox", "summaries", "briefs", "archives", "notes", "file", 
    "home", "data", "date", "link", "system", "general", "work", "week"
}

def log_info(msg):
    print(f"{CYAN}[ATHENA_MIND]{RESET} {msg}")

def log_success(msg):
    print(f"{GREEN}[SUCCESS]{RESET} {msg}")

def log_warning(msg):
    print(f"{YELLOW}[WARNING]{RESET} {msg}")

def log_error(msg):
    print(f"{PINK}[ERROR]{RESET} {msg}", file=sys.stderr)

def create_custom_obsidian_note(analysis, dest_dir, note_name, final_filename):
    from datetime import datetime
    note_path = os.path.join(dest_dir, note_name)
    
    category = analysis.get("category", "general")
    desc = analysis.get("description", "")
    struct = analysis.get("structured_data", {})
    
    # Generate YAML frontmatter
    yaml_lines = [
        "---",
        "type: document-context",
        f"category: {category}",
        f"original_name: {analysis['original_name']}",
        f"processed_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"meta_storage_relative_path: {json.dumps(final_filename)}"
    ]
    
    for k, v in struct.items():
        if v is not None:
            yaml_lines.append(f"meta_{k}: {json.dumps(v)}")
            
    yaml_lines.append("---")
    
    # Generate content
    abs_storage_path = os.path.join(STORAGE_DIR, final_filename)
    content_lines = [
        "\n".join(yaml_lines),
        f"\n# {desc}",
        "\n## File Attachment",
        f"[Original Document](file://{abs_storage_path})",
        "\n## Extracted Metadata",
    ]
    
    for k, v in struct.items():
        if v is not None:
            content_lines.append(f"- **{k.replace('_', ' ').title()}**: {v}")
            
    content_lines.append("\n## Notes")
    content_lines.append(f"Processed and synchronized by your Hermes Agent on {datetime.now().strftime('%Y-%m-%d')}.")
    
    with open(note_path, "w", encoding="utf-8") as f:
        f.write("\n".join(content_lines))
        
    print(f"Created Obsidian note: {note_name}")

# --- 1. STORAGE AUDIT MODULE ---

def guess_category_from_filename(filename):
    name = filename.lower()
    if any(k in name for k in ["receipt", "invoice", "finances", "stripe", "spending", "payment", "tax", "bill"]):
        return "finances"
    if any(k in name for k in ["workout", "run", "lift", "cycle", "swim", "fitness", "cardio", "gym"]):
        return "fitness"
    if any(k in name for k in ["medical", "health", "sleep", "mood", "bp", "vitals", "weight", "doctor", "blood"]):
        return "health"
    if any(k in name for k in ["study", "learn", "cs", "algorithm", "tree", "class", "lecture", "book", "paper", "concept"]):
        return "learning"
    if any(k in name for k in ["career", "resume", "job", "application", "interview", "recruiting", "nuwc", "company", "offer"]):
        return "career"
    return "general"

def audit_storage(fix=False):
    log_info("Commencing storage reference audit...")
    
    # Get all files in storage
    if not os.path.exists(STORAGE_DIR):
        log_warning(f"Storage directory {STORAGE_DIR} does not exist. Creating it.")
        os.makedirs(STORAGE_DIR)
        return
        
    storage_files = {f for f in os.listdir(STORAGE_DIR) if os.path.isfile(os.path.join(STORAGE_DIR, f))}
    log_info(f"Found {len(storage_files)} files in flat storage: {STORAGE_DIR}")
    
    # Scan all markdown files in vault to extract storage references
    referenced_files = set()
    vault_notes = []
    
    for root, dirs, files in os.walk(VAULT_DIR):
        # Exclude hidden, config, and archive folders
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['.obsidian', '04_Archives', '04_Archive', 'Daily_Briefs', 'Summaries']]
        for file in files:
            if file.endswith('.md'):
                note_path = os.path.join(root, file)
                vault_notes.append(note_path)
                try:
                    with open(note_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    log_error(f"Error reading {file}: {e}")
                    continue
                
                # Check frontmatter meta_storage_relative_path
                fm_match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
                if fm_match:
                    fm_text = fm_match.group(1)
                    path_match = re.search(r'meta_storage_relative_path:\s*"(.*?)"|meta_storage_relative_path:\s*([^\s\n]+)', fm_text)
                    if path_match:
                        ref_path = path_match.group(1) or path_match.group(2)
                        referenced_files.add(os.path.basename(ref_path))
                
                # Check markdown links pointing to storage
                links = re.findall(r'\[.*?\]\(file://.*?/storage/(.*?)\)', content)
                for link in links:
                    referenced_files.add(os.path.basename(link))
                    
    log_info(f"Scanned {len(vault_notes)} notes. Found {len(referenced_files)} unique storage references.")
    
    # Query database to see what is tracked
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT new_path FROM processed_files;")
    db_paths = {os.path.basename(row['new_path']) for row in cursor.fetchall()}
    conn.close()
    
    unreferenced_vault = storage_files - referenced_files
    unreferenced_db = storage_files - db_paths
    
    # Output Findings
    if not unreferenced_vault and not unreferenced_db:
        log_success("Vault and database references are fully synchronized! No orphan storage files.")
        return
        
    if unreferenced_vault:
        log_warning(f"Found {len(unreferenced_vault)} files in storage UNREFERENCED in Vault:")
        for f in sorted(unreferenced_vault):
            print(f"  - {f}")
            
    if unreferenced_db:
        log_warning(f"Found {len(unreferenced_db)} files in storage UNREGISTERED in SQLite Database:")
        for f in sorted(unreferenced_db):
            print(f"  - {f}")
            
    # Fix operations (auto-generate companion notes and insert to DB)
    if fix:
        log_info("Fix flag active. Repairing missing references...")
        fixed_count = 0
        
        for filename in sorted(unreferenced_vault | unreferenced_db):
            file_path = os.path.join(STORAGE_DIR, filename)
            category = guess_category_from_filename(filename)
            sub_folder = CATEGORIES.get(category, "03_Resources")
            vault_dest_dir = os.path.join(VAULT_DIR, sub_folder)
            os.makedirs(vault_dest_dir, exist_ok=True)
            
            relative_moved_path = os.path.join("storage", filename)
            
            analysis = {
                "category": category,
                "description": f"Recovered storage record: {filename.replace('_', ' ')}",
                "original_name": filename,
                "recommended_filename": filename,
                "structured_data": {
                    "date": filename[:10] if re.match(r'^\d{4}-\d{2}-\d{2}', filename) else None
                }
            }
            
            # 1. Create note if missing
            note_name = os.path.splitext(filename)[0] + ".md"
            note_path = os.path.join(vault_dest_dir, note_name)
            if os.path.exists(note_path):
                # If note exists but doesn't mention our file, append extension to make unique
                try:
                    with open(note_path, 'r', encoding='utf-8') as f:
                        note_content = f.read()
                    if filename not in note_content:
                        ext = os.path.splitext(filename)[1].replace('.', '').lower()
                        note_name = os.path.splitext(filename)[0] + f"_{ext}.md"
                        note_path = os.path.join(vault_dest_dir, note_name)
                except Exception:
                    pass

            if not os.path.exists(note_path):
                create_custom_obsidian_note(analysis, vault_dest_dir, note_name, filename)
                log_success(f"Generated missing companion note: {note_name} in {sub_folder}/")
            
            # 2. Add to database if missing
            if filename in unreferenced_db:
                save_data_to_db(analysis, relative_moved_path)
                log_success(f"Registered file in SQLite database: {filename}")
                
            fixed_count += 1
            
        log_success(f"Storage reference repair complete. Fixed {fixed_count} missing references.")

# --- 2. LINK OPTIMIZER MODULE ---

def optimize_links(fix=False):
    log_info("Commencing cross-linking scan...")
    
    # 1. Build note index (filenames and pathways)
    note_catalog = [] # list of dicts: {'path', 'title', 'title_lower'}
    
    for root, dirs, files in os.walk(VAULT_DIR):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['.obsidian', '04_Archives', '04_Archive', 'Daily_Briefs', 'Summaries']]
        for file in files:
            if file.endswith('.md'):
                note_path = os.path.join(root, file)
                title = os.path.splitext(file)[0]
                # Filter out stop words and short names to prevent false matching
                if title.lower() in STOP_WORDS or len(title) < 4:
                    continue
                note_catalog.append({
                    'path': note_path,
                    'title': title,
                    'title_lower': title.lower()
                })
                
    # Sort by title length descending to match longer titles first (e.g. "Stripe API" before "Stripe")
    note_catalog.sort(key=lambda x: len(x['title']), reverse=True)
    log_info(f"Indexed {len(note_catalog)} notes for cross-linking candidates.")
    
    links_suggested = 0
    files_modified = 0
    
    # 2. Scan note contents
    for note in note_catalog:
        note_path = note['path']
        current_title_lower = note['title_lower']
        
        try:
            with open(note_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            log_error(f"Error reading {note['title']}: {e}")
            continue
            
        # Separate frontmatter
        fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if fm_match:
            frontmatter = fm_match.group(0)
            body = content[fm_match.end():]
        else:
            frontmatter = ""
            body = content
            
        modified_body = body
        links_in_file = []
        
        # Temporary replacement of existing wikilinks and file links to prevent matching nested content
        placeholders = []
        def repl_placeholder(match):
            placeholders.append(match.group(0))
            return f"__ATHENA_LINK_PLACEHOLDER_{len(placeholders)-1}__"
            
        # Replace wikilinks [[link]] and standard markdown links [text](url)
        modified_body = re.sub(r'\[\[[^\]]+\]\]', repl_placeholder, modified_body)
        modified_body = re.sub(r'\[[^\]]+\]\([^)]+\)', repl_placeholder, modified_body)
        
        # Scan for plain text occurrences of other note titles
        for target_note in note_catalog:
            # Don't link to itself
            if target_note['title_lower'] == current_title_lower:
                continue
                
            target_title = target_note['title']
            # Search case-insensitively with word boundaries
            pattern = re.compile(rf'\b({re.escape(target_title)})\b', re.IGNORECASE)
            
            matches = pattern.findall(modified_body)
            if matches:
                # Replace with wiki-link representation containing the exact text matched
                # Since we process longer titles first, this is safe
                def repl_match(m):
                    matched_text = m.group(1)
                    links_in_file.append(target_title)
                    return f"[[{target_title}|{matched_text}]]"
                modified_body = pattern.sub(repl_match, modified_body)
                
        # Restore placeholders
        for idx, pl in enumerate(placeholders):
            modified_body = modified_body.replace(f"__ATHENA_LINK_PLACEHOLDER_{idx}__", pl)
            
        if links_in_file:
            links_suggested += len(links_in_file)
            log_info(f"Note '{note['title']}' has link opportunities: {', '.join(set(links_in_file))}")
            
            if fix:
                try:
                    with open(note_path, 'w', encoding='utf-8') as f:
                        f.write(frontmatter + modified_body)
                    files_modified += 1
                except Exception as e:
                    log_error(f"Failed to write updates to {note['title']}: {e}")
                    
    log_success(f"Link optimization scan complete. Found {links_suggested} link opportunities.")
    if fix:
        log_success(f"Auto-linking applied: Updated {files_modified} notes in the vault.")

# --- 3. CONSOLIDATION & MOC ENGINE ---

def analyze_vault():
    log_info("Analyzing vault directories, tags, and structure...")
    
    note_catalog = []
    
    for root, dirs, files in os.walk(VAULT_DIR):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['.obsidian', '04_Archives', '04_Archive', 'Daily_Briefs', 'Summaries']]
        for file in files:
            if file.endswith('.md'):
                note_path = os.path.join(root, file)
                title = os.path.splitext(file)[0]
                category = guess_category_from_filename(file)
                note_catalog.append({
                    'path': note_path,
                    'title': title,
                    'category': category
                })
                
    # 1. Look for duplicates or highly overlapping titles (consolidation candidates)
    log_info("Checking for consolidation opportunities...")
    consolidation_found = False
    
    # Basic consolidation: notes in different locations with similar names
    for i in range(len(note_catalog)):
        for j in range(i+1, len(note_catalog)):
            n1 = note_catalog[i]
            n2 = note_catalog[j]
            
            # Check if name stems match
            stem1 = n1['title'].lower().replace('_', ' ').replace('-', ' ')
            stem2 = n2['title'].lower().replace('_', ' ').replace('-', ' ')
            
            if stem1 == stem2:
                consolidation_found = True
                log_warning(f"Consolidation candidate: '{n1['title']}' is duplicate in different locations:")
                print(f"  1. {os.path.relpath(n1['path'], VAULT_DIR)}")
                print(f"  2. {os.path.relpath(n2['path'], VAULT_DIR)}")
                
    if not consolidation_found:
        log_success("No duplicate or highly overlapping notes identified.")
        
    # 2. Suggest Maps of Content (MOCs) / Directory pages based on category sizes
    log_info("Analyzing cluster hubs and Directory Pages (MOCs)...")
    clusters = {}
    for note in note_catalog:
        cat = note['category']
        if cat not in clusters:
            clusters[cat] = []
        clusters[cat].append(note['title'])
        
    for cat, notes in clusters.items():
        if len(notes) >= 5:
            moc_name = f"{cat.capitalize()}_MOC.md"
            moc_path = os.path.join(VAULT_DIR, moc_name)
            
            log_info(f"Category '{cat}' contains {len(notes)} notes. Primary candidate for Directory Map.")
            if not os.path.exists(moc_path):
                log_warning(f"Suggested action: Create Directory Map page '{moc_name}' at vault root to link these references.")
            else:
                log_success(f"Directory Map '{moc_name}' exists.")
                
    # 3. Tag analysis
    log_info("Analyzing tags distribution...")
    all_tags = {}
    for note in note_catalog:
        try:
            with open(note['path'], 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            continue
        # Find tags (words starting with #, ignoring header formatting and comments)
        tags = re.findall(r'(?<!\w)#([a-zA-Z0-9_-]+)\b', content)
        for t in tags:
            # Exclude hex color definitions
            if re.match(r'^[0-9a-fA-F]{3}$|^[0-9a-fA-F]{6}$', t):
                continue
            all_tags[t] = all_tags.get(t, 0) + 1
            
    if all_tags:
        log_info("Top tracked tags in Vault:")
        for t, count in sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  #{t} ({count} occurrences)")
    else:
        log_warning("No tags detected in vault notes.")

# --- 4. EXTENDED SYSTEM TASKS ---

def tag_existing_daily_summaries(fix=False):
    log_info("Scanning for existing daily summaries to add the daily-summary tags...")
    archives_dir = os.path.join(VAULT_DIR, "04_Archives")
    if not os.path.exists(archives_dir):
        return
        
    summary_pattern = re.compile(r"^Daily_Summary_(\d{4}-\d{2}-\d{2})\.md$")
    files_processed = 0
    
    for filename in os.listdir(archives_dir):
        m = summary_pattern.match(filename)
        if m:
            date_str = m.group(1)
            file_path = os.path.join(archives_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                log_error(f"Error reading summary {filename}: {e}")
                continue
                
            has_fm = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
            
            # Check if tag is already there
            if "daily-summary" in content:
                continue
                
            log_warning(f"Orphan summary found (needs tag): {filename}")
            files_processed += 1
            
            if fix:
                fm_header = (
                    "---\n"
                    "type: daily-summary\n"
                    "tags:\n"
                    "  - daily-summary\n"
                    f"date: {date_str}\n"
                    "---\n\n"
                )
                
                if not has_fm:
                    new_content = fm_header + content
                    try:
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        log_success(f"Added daily-summary tag to: {filename}")
                    except Exception as e:
                        log_error(f"Error writing to {filename}: {e}")
                        
    log_success(f"Daily summary tagging scan complete. Processed {files_processed} summaries.")

def link_similar_notes(fix=False):
    log_info("Scanning for similar notes to establish related versions links...")
    
    note_catalog = []
    for root, dirs, files in os.walk(VAULT_DIR):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['.obsidian', '04_Archives', '04_Archive', 'Daily_Briefs', 'Summaries']]
        for file in files:
            if file.endswith('.md'):
                note_path = os.path.join(root, file)
                title = os.path.splitext(file)[0]
                note_catalog.append({
                    'path': note_path,
                    'title': title
                })
                
    groups = {}
    for note in note_catalog:
        title = note['title']
        stem = title.lower().replace('-', '_')
        for suffix in ['_pdf', '_html', '_txt', '_jpg', '_png', '_jpeg', ' pdf', ' html', ' txt', ' doc', ' docx']:
            if stem.endswith(suffix):
                stem = stem[:-len(suffix)]
                break
        stem = stem.strip()
        
        if len(stem) < 4:
            continue
            
        if stem not in groups:
            groups[stem] = []
        groups[stem].append(note)
        
    links_added = 0
    
    for stem, notes in groups.items():
        if len(notes) > 1:
            log_info(f"Group found for stem '{stem}': {[n['title'] for n in notes]}")
            
            for note in notes:
                try:
                    with open(note['path'], 'r', encoding='utf-8') as f:
                        content = f.read()
                except Exception as e:
                    log_error(f"Error reading {note['title']}: {e}")
                    continue
                    
                other_notes = [n for n in notes if n['title'] != note['title']]
                missing_links = []
                
                for other in other_notes:
                    if f"[[{other['title']}" not in content:
                        missing_links.append(other['title'])
                        
                if missing_links:
                    links_added += len(missing_links)
                    log_warning(f"Note '{note['title']}' is missing links to related versions: {missing_links}")
                    
                    if fix:
                        related_section = "\n\n## Related Versions\n"
                        for l in missing_links:
                            desc = l.split('_')[-1].upper() if '_' in l else "Version"
                            if desc not in ["PDF", "HTML", "TXT"]:
                                desc = "Alternate Version"
                            related_section += f"- [[{l}|{desc} version]]\n"
                            
                        try:
                            with open(note['path'], 'a', encoding='utf-8') as f:
                                f.write(related_section)
                            log_success(f"Appended related links to: {note['title']}")
                        except Exception as e:
                            log_error(f"Error appending to {note['title']}: {e}")
                            
    log_success(f"Related version linking scan complete. Identified {links_added} missing links.")

# --- MAIN EXECUTION COMMANDER ---

def main():
    parser = argparse.ArgumentParser(description="Athena Mind Link and Consolidation Utility")
    parser.add_argument("command", choices=["audit-storage", "find-links", "analyze-vault", "run-all"], help="Command to run")
    parser.add_argument("--fix", action="store_true", help="Automatically write changes, create stubs, or link files")
    
    args = parser.parse_args()
    
    if args.command == "audit-storage":
        audit_storage(args.fix)
    elif args.command == "find-links":
        optimize_links(args.fix)
    elif args.command == "analyze-vault":
        analyze_vault()
    elif args.command == "run-all":
        print(f"{CYAN}=== STARTING ATHENA MIND SYSTEM OPTIMIZATION ==={RESET}")
        audit_storage(args.fix)
        print()
        optimize_links(args.fix)
        print()
        analyze_vault()
        print()
        tag_existing_daily_summaries(args.fix)
        print()
        link_similar_notes(args.fix)
        print(f"{CYAN}=== ATHENA MIND SYSTEM OPTIMIZATION COMPLETE ==={RESET}")

if __name__ == "__main__":
    main()
