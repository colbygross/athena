#!/usr/bin/env python3
import os
import re
import json
import sqlite3
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

import database

VAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "obsidian_vault")

# LLM Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi4-mini:latest")

def get_free_calendar_slots():
    """Finds 3 non-overlapping 30-min slots in the next 7 working days."""
    now = datetime.now()
    end_date = now + timedelta(days=7)
    
    # Query calendar events from SQLite DB
    conn = sqlite3.connect(database.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT start_time, end_time FROM calendar_events 
        WHERE start_time >= ? AND start_time <= ?
        ORDER BY start_time ASC
    """, (now.strftime("%Y-%m-%d %H:%M:%S"), end_date.strftime("%Y-%m-%d %H:%M:%S")))
    events = cursor.fetchall()
    conn.close()
    
    # Parse event times
    busy_slots = []
    for event in events:
        try:
            start = datetime.strptime(event['start_time'], "%Y-%m-%d %H:%M:%S")
            end = datetime.strptime(event['end_time'], "%Y-%m-%d %H:%M:%S")
            busy_slots.append((start, end))
        except Exception:
            try:
                start = datetime.fromisoformat(event['start_time'].replace("Z", "+00:00")).replace(tzinfo=None)
                end = datetime.fromisoformat(event['end_time'].replace("Z", "+00:00")).replace(tzinfo=None)
                busy_slots.append((start, end))
            except Exception:
                continue
                
    suggested_slots = []
    current_day = now + timedelta(days=1) # Propose from tomorrow onwards
    
    while current_day <= end_date and len(suggested_slots) < 3:
        if current_day.weekday() < 5: # Monday - Friday only
            for hour, minute in [(10, 0), (13, 30), (15, 0)]:
                slot_start = current_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                slot_end = slot_start + timedelta(minutes=30)
                
                # Check overlap
                overlap = False
                for busy_start, busy_end in busy_slots:
                    if not (slot_end <= busy_start or slot_start >= busy_end):
                        overlap = True
                        break
                        
                if not overlap:
                    day_str = slot_start.strftime("%A, %B %d")
                    time_str = slot_start.strftime("%I:%M %p")
                    suggested_slots.append(f"{day_str} at {time_str}")
                    if len(suggested_slots) == 3:
                        break
        current_day += timedelta(days=1)
        
    while len(suggested_slots) < 3:
        day = now + timedelta(days=len(suggested_slots)+1)
        suggested_slots.append(f"{day.strftime('%A, %B %d')} at 10:00 AM")
        
    return suggested_slots

def get_default_resume_text():
    """Loads fallback resume text if no profile-specific resume is set."""
    # Look in obsidian Career folder first
    career_dir = os.path.join(VAULT_DIR, "02_Areas", "Career")
    if os.path.exists(career_dir):
        files = [os.path.join(career_dir, f) for f in os.listdir(career_dir) if "resume" in f.lower() and f.endswith(".md")]
        if files:
            # Sort by name/date to get latest
            files.sort()
            with open(files[-1], "r", encoding="utf-8") as f:
                content = f.read()
                # Clean frontmatter
                content = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL)
                return content.strip()
                
    # Fallback to the HTML resume in storage
    html_resume = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "2026-05-23_colby_gross_resume.html")
    if os.path.exists(html_resume):
        with open(html_resume, "r", encoding="utf-8") as f:
            html = f.read()
            # Strip styles and tags for LLM text context
            text = re.sub(r"<style>.*?</style>", "", html, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text
            
    return "Colby Gross. UMass Amherst BS CS (Cybersecurity and Networking concentration, May 2026). Skills: Agentic AI, Networking, Security Tools (Wireshark, Metasploit), Python, C++, Java, Bash."

def search_web_recruiter(company):
    """Queries DuckDuckGo HTML page to find recruiter names at company."""
    query = f"recruiter '{company}' site:linkedin.com/in/"
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    
    results = []
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            html = response.read().decode('utf-8', errors='ignore')
            # Extract result snippets and text
            snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
            for snippet in snippets:
                clean_text = re.sub(r'<[^>]+>', '', snippet).strip()
                results.append(clean_text)
                
            links = re.findall(r'<a class="result__url"[^>]*>(.*?)</a>', html, re.DOTALL)
            for link in links:
                clean_text = re.sub(r'<[^>]+>', '', link).strip()
                if "linkedin.com/in/" not in clean_text:
                    results.append(clean_text)
    except Exception as e:
        print(f"DuckDuckGo search failed for recruiter: {e}")
        
    return results[:8]

def guess_company_domain(company):
    """Guesses the domain suffix for a company name."""
    clean = re.sub(r"[^a-zA-Z0-9]", "", company).lower()
    if not clean:
        return "company.com"
        
    # Some common mappings
    mappings = {
        "google": "google.com",
        "meta": "meta.com",
        "facebook": "meta.com",
        "amazon": "amazon.com",
        "apple": "apple.com",
        "microsoft": "microsoft.com",
        "netflix": "netflix.com",
    }
    for k, v in mappings.items():
        if k in clean:
            return v
            
    return f"{clean}.com"

def call_llm(prompt):
    """Executes call to Gemini API if set, else local Ollama model."""
    if GEMINI_API_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"}
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                return text.strip()
        except Exception as e:
            print(f"Gemini API call failed: {e}. Falling back to Ollama...")

    # Ollama local mode
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_ctx": 8192}
    }
    url = f"{OLLAMA_BASE_URL}/api/generate"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            text = (res.get("thinking", "") + res.get("response", "")).strip()
            return text
    except Exception as e:
        print(f"Ollama API call failed: {e}")
        raise RuntimeError("Both Gemini and Ollama LLM requests failed.")

def process_job_lead(lead_id):
    """Performs tailoring, recruiter discovery, and email drafting for a job lead."""
    conn = sqlite3.connect(database.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Fetch Lead details
    cursor.execute("SELECT * FROM job_leads WHERE id = ?", (lead_id,))
    lead = cursor.fetchone()
    if not lead:
        conn.close()
        raise ValueError(f"Lead with ID {lead_id} not found.")
        
    # 2. Get profile details
    resume_text = ""
    if lead['profile_id']:
        cursor.execute("SELECT * FROM career_search_profiles WHERE id = ?", (lead['profile_id'],))
        profile = cursor.fetchone()
        if profile and profile['resume_path'] and os.path.exists(profile['resume_path']):
            try:
                with open(profile['resume_path'], "r", encoding="utf-8") as f:
                    resume_text = f.read()
            except Exception:
                pass
                
    if not resume_text:
        resume_text = get_default_resume_text()
        
    # 3. Search web for recruiter names
    web_results = search_web_recruiter(lead['company'])
    web_results_str = "\n".join([f"- {r}" for r in web_results]) if web_results else "No online recruiter results found."
    
    # 4. Get calendar slots
    slots = get_free_calendar_slots()
    slots_str = "\n".join([f"- {s}" for s in slots])
    
    # 5. Formulate prompt
    prompt = f"""
You are an expert career assistant and agent. Based on the candidate's resume, target job details, potential recruiter search results, and calendar free slots, tailor the resume bullet points, cover letter, find the recruiter name, and draft a cold outreach email.

Candidate Resume:
{resume_text}

Target Job Details:
Company: {lead['company']}
Role: {lead['role']}
Location: {lead['location']}
Description: {lead['job_description']}

Recruiter Web Search Snippets (Use to extract/guess a name):
{web_results_str}

Suggested Interview Times (Incorporate these exact times in the email):
{slots_str}

Please generate the materials. You MUST return ONLY a valid JSON object. Do not wrap in markdown ```json or include extra explanation.

JSON Schema:
{{
  "recruiter_name": "Name of recruiter/hiring manager extracted from search snippets or best guess. If none found, write 'Hiring Team'.",
  "recruiter_email": "Guessed email address for the recruiter. (Use domain {guess_company_domain(lead['company'])} and standard formats like john.doe@{guess_company_domain(lead['company'])} or recruiter@{guess_company_domain(lead['company'])}).",
  "tailored_bullets": "3 tailored bullet points highlighting candidate's matching networking, cybersecurity, or AI agent project experiences, formatted as markdown bullet list.",
  "cover_letter": "A tailored, short cover letter (max 200 words) matching the candidate's skills to this role.",
  "cold_email_draft": "A professional cold email (max 150 words) to the recruiter. State your UMass Amherst CS degree, enthusiasm for the role, and ask for a 15-minute chat. You MUST explicitly propose the 3 suggested interview times: {slots[0]}, {slots[1]}, and {slots[2]}."
}}
"""
    
    # 6. Call LLM
    print(f"Calling LLM to process job lead '{lead['role']}' at '{lead['company']}'...")
    response_text = call_llm(prompt)
    
    # Clean output
    response_text = response_text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("```", 2)[1]
        if response_text.startswith("json"):
            response_text = response_text[4:].strip()
            
    try:
        data = json.loads(response_text)
    except Exception as e:
        print(f"Failed to parse LLM response: {e}. Raw response: {response_text}")
        # Build a safe fallback
        data = {
            "recruiter_name": "Hiring Team",
            "recruiter_email": f"recruiter@{guess_company_domain(lead['company'])}",
            "tailored_bullets": "- Custom project experience matching " + lead['role'],
            "cover_letter": f"Dear Hiring Team,\n\nI am writing to express my strong interest in the {lead['role']} position at {lead['company']}.",
            "cold_email_draft": f"Dear Hiring Team,\n\nI recently applied for the {lead['role']} role and would love to connect. Are you free at either:\n- {slots[0]}\n- {slots[1]}\n- {slots[2]}\n\nBest,\nColby Gross"
        }
        
    # 7. Add to job_applications, moving from lead status
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        INSERT INTO job_applications (
            date_applied, company, role, salary_range, status, job_description_url, notes,
            lead_id, recruiter_name, recruiter_email, cold_email_draft, outreach_status,
            tailored_bullets, cover_letter
        ) VALUES (?, ?, ?, ?, 'applied', ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
    """, (
        today,
        lead['company'],
        lead['role'],
        lead['salary_range'] or "",
        lead['job_url'],
        "Processed via automated hub.",
        lead['id'],
        data.get("recruiter_name", "Hiring Team"),
        data.get("recruiter_email", ""),
        data.get("cold_email_draft", ""),
        data.get("tailored_bullets", ""),
        data.get("cover_letter", "")
    ))
    app_id = cursor.lastrowid
    
    # 8. Mark lead as 'applied'
    cursor.execute("UPDATE job_leads SET status = 'applied' WHERE id = ?", (lead_id,))
    
    conn.commit()
    conn.close()
    
    print(f"Processed lead successfully. Created Job Application ID: {app_id}")
    return app_id

if __name__ == "__main__":
    # Test script if argument provided
    import sys
    if len(sys.argv) > 1:
        try:
            process_job_lead(int(sys.argv[1]))
        except Exception as err:
            print(f"Execution error: {err}")
    else:
        print("Please provide a job lead ID to process.")
