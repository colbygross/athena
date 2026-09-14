#!/usr/bin/env python3
"""
Athena OS: Job Discovery Engine (API-First & Direct ATS Aggregation)
Zero-CAPTCHA 24/7 ingestion engine for remote and New England tech opportunities.
"""
import os
import re
import json
import html
import sqlite3
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import database

BASE_DIR = os.getenv("WORKSPACE_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def clean_html_to_plaintext(raw_text):
    """Converts HTML & double-encoded entities (&lt;p&gt;, &#39;) into clean human-readable plain text."""
    if not raw_text:
        return ""
    # 1. Unescape HTML entities
    text = html.unescape(raw_text)
    text = html.unescape(text)
    
    # 2. Convert structural tags to newlines
    text = re.sub(r"<(br|p|div|h[1-6]|li|tr)[^>]*>", "\n", text, flags=re.IGNORECASE)
    
    # 3. Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    
    # 4. Clean up spacing and empty lines
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    clean_lines = [line for line in lines if line]
    
    return "\n\n".join(clean_lines)

# API Keys (Optional - gracefully fallback to RSS/ATS direct feeds if unconfigured)
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")
JSEARCH_API_KEY = os.getenv("RAPIDAPI_KEY", "") or os.getenv("JSEARCH_API_KEY", "")

# Geographic & Remote Classifier Definitions
NEW_ENGLAND_STATES = {"ma", "ct", "ri", "nh", "vt", "me", "massachusetts", "connecticut", "rhode island", "new hampshire", "vermont", "maine"}
NEW_ENGLAND_CITIES = {
    "boston", "cambridge", "amherst", "worcester", "providence", "hartford", 
    "burlington", "portland", "manchester", "northampton", "waltham", "somerville",
    "quincy", "newton", "framingham", "lowell", "springfield", "new haven", "stamford"
}

NEW_ENGLAND_PATTERNS = [
    r"\b(ma|ct|ri|nh|vt|me)\b",
    r"\b(massachusetts|connecticut|rhode island|new hampshire|vermont|maine)\b",
    r"\b(boston|cambridge|amherst|worcester|providence|hartford|burlington|portland|manchester)\b",
    r"\bnew england\b"
]

REMOTE_PATTERNS = [
    r"\bremote\b", r"\bwork from home\b", r"\bwfh\b", r"\btelecommute\b", 
    r"\banywhere\b", r"\bvirtual\b", r"\bus remote\b", r"\bremote\s*-\s*us\b"
]

def get_db():
    return database.create_new_connection()

def classify_location(location_str, title_str, description_str="", source=""):
    """
    Classifies job into Remote (Tier 1) vs New England Regional (Tier 2) vs Non-NE Onsite (Reject).
    Returns (is_remote, tier, is_accepted, score_bonus)
    """
    combined = f"{location_str} {title_str} {description_str}".lower()
    
    # 1. Check if Remote
    is_remote = 0
    if source in ("remoteok", "weworkremotely") or any(k in combined for k in ["remote", "wfh", "telecommute", "anywhere", "virtual", "work from home"]):
        is_remote = 1
            
    # 2. Check if New England
    is_new_england = False
    for pat in NEW_ENGLAND_PATTERNS:
        if re.search(pat, combined):
            is_new_england = True
            break
            
    if is_remote:
        # Tier 1: Remote US (Highest Priority)
        return (1, 1, True, 40)
    elif is_new_england:
        # Tier 2: New England Regional (Onsite / Hybrid)
        return (0, 2, True, 25)
    else:
        # Onsite or Hybrid outside New England -> Hard Rejection
        return (0, 0, False, 0)

TECH_TITLE_PATTERNS = [
    r"\b(software|developer|engineer|programmer|coder|ai|machine learning|ml|backend|frontend|fullstack|full-stack|full\s+stack|security|cybersecurity|network|systems|solutions|data|devops|infrastructure|cloud|technical|qa|test)\b"
]

SENIOR_TITLE_PATTERNS = [
    r"\b(senior|sr|sr\.|principal|staff|lead|director|vp|manager|head\s+of|architect|chief|exec|vice president)\b"
]

ENTRY_MARKERS = [
    r"\b(junior|jr|jr\.|entry|entry-level|entry\s+level|associate|software engineer i\b|swe i\b|engineer i\b|level 1\b|engineer 1\b|new grad|graduate|early career|university|apprentice|0-2 years|1-3 years|0-3 years)\b"
]

SENIOR_EXP_PATTERNS = [
    r"\b([5-9]|\d{2})\s*\+?\s*(years|yrs)\b",
    r"\b(minimum|at least|requires?)\s*([5-9]|\d{2})\s*(years|yrs)\b"
]

def classify_entry_level(title_str, description_str=""):
    """
    Ensures position is entry-to-mid career CS/AI role.
    Returns (is_acceptable, entry_bonus, reason)
    """
    title_lower = title_str.lower()
    desc_lower = description_str.lower()
    
    # 1. Reject Non-Tech Titles
    has_tech_title = any(re.search(pat, title_lower) for pat in TECH_TITLE_PATTERNS)
    if not has_tech_title:
        return (False, 0, "Non-Tech Title")
        
    # 2. Reject Senior/Lead Titles unless explicit junior marker exists
    is_senior_title = any(re.search(pat, title_lower) for pat in SENIOR_TITLE_PATTERNS)
    has_entry_marker = any(re.search(pat, title_lower) for pat in ENTRY_MARKERS) or any(re.search(pat, desc_lower) for pat in ENTRY_MARKERS)
    
    if is_senior_title and not has_entry_marker:
        return (False, 0, "Senior/Lead Role Excluded")
        
    # 3. Check for high experience requirements in description (5+ years)
    is_high_exp = any(re.search(pat, desc_lower) for pat in SENIOR_EXP_PATTERNS)
    if is_high_exp and not has_entry_marker:
        return (False, 0, "5+ Years Experience Requirement Excluded")
        
    # 4. Calculate Entry Suitability Bonus
    entry_bonus = 35 if has_entry_marker else 15
    return (True, entry_bonus, "Accepted Entry-to-Mid Role")

def calculate_baseline_match_score(title, description, is_remote, tier):
    """Calculates 0-100 initial baseline match score tailored for Entry-Level CS/AI background."""
    text = f"{title} {description}".lower()
    score = 40 if tier == 1 else 25 # Start with tier bonus
    
    is_entry, entry_bonus, reason = classify_entry_level(title, description)
    if not is_entry:
        return 0
        
    score += entry_bonus
    
    # Key skill bonuses for Entry-Level Candidate (UMass Amherst CS, AI, Security)
    high_value_skills = [
        ("agent", 15), ("ai", 12), ("machine learning", 10), ("python", 8),
        ("backend", 8), ("systems", 8), ("security", 7), ("network", 7),
        ("c++", 7), ("java", 5), ("bash", 5), ("api", 5)
    ]
    for skill, bonus in high_value_skills:
        if re.search(rf"\b{re.escape(skill)}\b", text):
            score += bonus
            
    return max(20, min(99, score))

def fetch_url(url, headers=None, timeout=4):
    """Helper to fetch URL with proper User-Agent and redirect handling."""
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.8"
    }
    if headers:
        req_headers.update(headers)
        
    try:
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
        req = urllib.request.Request(url, headers=req_headers)
        with opener.open(req, timeout=timeout) as resp:
            content = resp.read()
            return content.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"Fetch error for {url}: {e}")
        return None

# --- SOURCE 1: RemoteOK RSS / JSON ---
def ingest_remoteok():
    """Fetch RemoteOK public feed."""
    print("Ingesting RemoteOK Feed...")
    raw = fetch_url("https://remoteok.com/api?tag=dev")
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
            
        jobs = []
        for item in data:
            if not isinstance(item, dict) or "position" not in item:
                continue
                
            title = item.get("position", "")
            company = item.get("company", "Unknown")
            location = item.get("location", "Remote")
            url = item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id', '')}"
            desc = item.get("description", "")
            desc_clean = clean_html_to_plaintext(desc)
            
            jobs.append({
                "title": title,
                "company": company,
                "location": location if location else "Remote",
                "job_url": url,
                "job_description": desc_clean or f"{title} at {company}",
                "source": "remoteok"
            })
        return jobs
    except Exception as e:
        print(f"Error parsing RemoteOK data: {e}")
        return []

# --- SOURCE 2: WeWorkRemotely RSS Feeds ---
def ingest_weworkremotely():
    """Fetch WeWorkRemotely RSS feeds."""
    print("Ingesting WeWorkRemotely Feeds...")
    categories = [
        "https://weworkremotely.com/categories/remote-full-stack-programming.rss",
        "https://weworkremotely.com/categories/remote-back-end-programming.rss",
        "https://weworkremotely.com/categories/remote-ai-machine-learning-data-science.rss"
    ]
    
    jobs = []
    for feed_url in categories:
        xml_text = fetch_url(feed_url)
        if not xml_text:
            continue
            
        try:
            root = ET.fromstring(xml_text)
            for item in root.findall("./channel/item"):
                title_elem = item.find("title")
                link_elem = item.find("link")
                desc_elem = item.find("description")
                
                title_text = title_elem.text if title_elem is not None else ""
                link_text = link_elem.text if link_elem is not None else ""
                desc_text = desc_elem.text if desc_elem is not None else ""
                
                company = "WeWorkRemotely Partner"
                role_title = title_text
                if ":" in title_text:
                    parts = title_text.split(":", 1)
                    company = parts[0].strip()
                    role_title = parts[1].strip()
                    
                clean_desc = clean_html_to_plaintext(desc_text)
                
                if link_text:
                    jobs.append({
                        "title": role_title,
                        "company": company,
                        "location": "Remote",
                        "job_url": link_text.strip(),
                        "job_description": clean_desc[:2500],
                        "source": "weworkremotely"
                    })
        except Exception as e:
            print(f"Error parsing WWR XML feed {feed_url}: {e}")
            
    return jobs

# --- SOURCE 3: Direct Public ATS Boards (Greenhouse & Lever) ---
def ingest_direct_ats_boards():
    """Fetch postings from active Greenhouse/Lever public APIs."""
    print("Ingesting Direct ATS Company Boards (Greenhouse & Lever)...")
    target_companies_greenhouse = [
        "anthropic", "scaleai", "cloudflare", "datadog", "toast", 
        "hubspot", "draftkings", "akamai", "stripe", "vercel"
    ]
    
    jobs = []
    for comp in target_companies_greenhouse:
        url = f"https://boards-api.greenhouse.io/v1/boards/{comp}/jobs?content=true"
        raw = fetch_url(url)
        if not raw:
            continue
        try:
            data = json.loads(raw)
            for item in data.get("jobs", []):
                title = item.get("title", "")
                loc_data = item.get("location", {})
                location = loc_data.get("name", "Remote") if isinstance(loc_data, dict) else "Remote"
                job_url = item.get("absolute_url", "")
                desc = item.get("content", "")
                clean_desc = clean_html_to_plaintext(desc)
                
                if job_url:
                    jobs.append({
                        "title": title,
                        "company": comp.capitalize(),
                        "location": location,
                        "job_url": job_url,
                        "job_description": clean_desc[:2500] if clean_desc else f"{title} at {comp.capitalize()}",
                        "source": "greenhouse"
                    })
        except Exception:
            continue
                
    return jobs

# --- SOURCE 4: Hacker News "Who is Hiring?" API ---
def ingest_hn_who_is_hiring():
    """Fetch latest Hacker News Who is Hiring thread posts."""
    print("Ingesting Hacker News 'Who is Hiring?' Feed...")
    search_url = "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&query=Who+is+hiring"
    raw_search = fetch_url(search_url)
    if not raw_search:
        return []
        
    jobs = []
    try:
        search_data = json.loads(raw_search)
        hits = search_data.get("hits", [])
        if not hits:
            return []
            
        latest_story_id = hits[0].get("objectID")
        story_url = f"https://hacker-news.firebaseio.com/v0/item/{latest_story_id}.json"
        raw_story = fetch_url(story_url)
        if not raw_story:
            return []
            
        story_data = json.loads(raw_story)
        kids = story_data.get("kids", [])[:30] # Check first 30 top comment postings
        
        for kid_id in kids:
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json"
            raw_item = fetch_url(item_url)
            if not raw_item:
                continue
            comment = json.loads(raw_item)
            text = comment.get("text", "")
            if not text:
                continue
                
            clean_text = clean_html_to_plaintext(text)
            first_line = clean_text.split("\n")[0]
            
            # Format usually: "Company | Title | Location | Remote/Onsite"
            parts = [p.strip() for p in first_line.split("|")]
            company = parts[0] if len(parts) > 0 else "HN Hiring Startup"
            title = parts[1] if len(parts) > 1 else "Software / AI Engineer"
            location = parts[2] if len(parts) > 2 else "Remote"
            
            hn_url = f"https://news.ycombinator.com/item?id={kid_id}"
            
            jobs.append({
                "title": title[:100],
                "company": company[:80],
                "location": location[:80],
                "job_url": hn_url,
                "job_description": clean_text[:2000],
                "source": "hn_hiring"
            })
    except Exception as e:
        print(f"HN Hiring parse error: {e}")
        
    return jobs

# --- MAIN INGESTION ORCHESTRATOR ---
def run_discovery_pipeline(profile_id=None):
    """Executes multi-source job discovery, location classification, and DB staging."""
    print("=== STARTING ATHENA API-FIRST JOB DISCOVERY PIPELINE ===")
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Fetch active profiles
    cursor.execute("SELECT * FROM career_search_profiles WHERE active = 1")
    profiles = cursor.fetchall()
    
    if not profiles:
        print("No active profiles found. Seeding default profile for AI & Software Engineer...")
        cursor.execute("""
            INSERT INTO career_search_profiles (name, keywords, locations, active)
            VALUES ('AI & Core CS Software Roles', 'AI Agent, Machine Learning, Python, Backend, Software Engineer', 'Remote, Massachusetts, Connecticut, Rhode Island', 1)
        """)
        conn.commit()
        cursor.execute("SELECT * FROM career_search_profiles WHERE active = 1")
        profiles = cursor.fetchall()
        
    all_raw_jobs = []
    
    # Collect jobs from zero-CAPTCHA public feeds
    all_raw_jobs.extend(ingest_remoteok())
    all_raw_jobs.extend(ingest_weworkremotely())
    all_raw_jobs.extend(ingest_direct_ats_boards())
    all_raw_jobs.extend(ingest_hn_who_is_hiring())
    
    print(f"\nGathered {len(all_raw_jobs)} total job candidates from API feeds. Commencing location & relevance classification...")
    
    today = datetime.now().strftime("%Y-%m-%d")
    new_added = 0
    rejected_location = 0
    duplicates = 0
    
    for job in all_raw_jobs:
        title = job.get("title", "").strip()
        company = job.get("company", "").strip()
        location = job.get("location", "").strip()
        job_url = job.get("job_url", "").strip()
        description = job.get("job_description", "").strip()
        source = job.get("source", "api")
        
        if not title or not job_url:
            continue
            
        # Deduplication check
        cursor.execute("SELECT id FROM job_leads WHERE job_url = ?", (job_url,))
        if cursor.fetchone():
            duplicates += 1
            continue
            
        cursor.execute("SELECT id FROM job_applications WHERE job_description_url = ?", (job_url,))
        if cursor.fetchone():
            duplicates += 1
            continue
            
        # Classify Location & Remote Priority
        is_remote, tier, is_accepted, loc_bonus = classify_location(location, title, description, source)
        
        if not is_accepted:
            rejected_location += 1
            continue
            
        # Calculate baseline match score
        match_score = calculate_baseline_match_score(title, description, is_remote, tier)
        if match_score <= 0:
            continue
        
        prof_id = profiles[0]['id'] if profiles else 1
        
        try:
            cursor.execute("""
                INSERT INTO job_leads (
                    date_found, company, role, location, salary_range, 
                    job_description, job_url, source, status, profile_id,
                    is_remote, tier, match_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'lead', ?, ?, ?, ?)
            """, (
                today, company, title, location, "",
                description, job_url, source, prof_id,
                is_remote, tier, match_score
            ))
            new_added += 1
        except sqlite3.IntegrityError:
            duplicates += 1
        except Exception as e:
            print(f"Error inserting job lead {title}: {e}")
            
    conn.commit()
    conn.close()
    
    print(f"\n=== DISCOVERY PIPELINE COMPLETE ===")
    print(f"• New Job Leads Added: {new_added}")
    print(f"• Duplicates Filtered: {duplicates}")
    print(f"• Non-New England Onsite Rejected: {rejected_location}")
    return new_added

if __name__ == "__main__":
    run_discovery_pipeline()
