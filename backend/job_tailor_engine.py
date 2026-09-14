#!/usr/bin/env python3
"""
Athena OS: Dual-Anchor LLM Job Tailoring & Recruiter Enrichment Engine
Generates tailored application packets (bullets, cover letters, recruiter cold emails with calendar slots).
"""
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

BASE_DIR = os.getenv("WORKSPACE_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VAULT_DIR = os.getenv("VAULT_DIR", os.path.join(BASE_DIR, "obsidian_vault"))

# LLM Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi4-mini:latest")

def get_db():
    return database.create_new_connection()

def get_open_calendar_slots():
    """Finds 3 non-overlapping 30-min interview slots in the next 7 business days."""
    now = datetime.now()
    end_date = now + timedelta(days=7)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT start_time, end_time FROM calendar_events 
        WHERE start_time >= ? AND start_time <= ?
        ORDER BY start_time ASC
    """, (now.strftime("%Y-%m-%d %H:%M:%S"), end_date.strftime("%Y-%m-%d %H:%M:%S")))
    events = cursor.fetchall()
    conn.close()
    
    busy_slots = []
    for ev in events:
        try:
            st = datetime.strptime(ev['start_time'], "%Y-%m-%d %H:%M:%S")
            et = datetime.strptime(ev['end_time'], "%Y-%m-%d %H:%M:%S")
            busy_slots.append((st, et))
        except Exception:
            continue
            
    suggested = []
    current_day = now + timedelta(days=1)
    
    while current_day <= end_date and len(suggested) < 3:
        if current_day.weekday() < 5: # Mon-Fri
            for hour, minute in [(10, 0), (13, 30), (15, 0)]:
                st = current_day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                et = st + timedelta(minutes=30)
                
                overlap = any(not (et <= b_st or st >= b_et) for b_st, b_et in busy_slots)
                if not overlap:
                    day_str = st.strftime("%A, %B %d")
                    time_str = st.strftime("%I:%M %p")
                    suggested.append(f"{day_str} at {time_str}")
                    if len(suggested) == 3:
                        break
        current_day += timedelta(days=1)
        
    while len(suggested) < 3:
        d = now + timedelta(days=len(suggested) + 1)
        suggested.append(f"{d.strftime('%A, %B %d')} at 10:00 AM")
        
    return suggested

def get_candidate_baseline_profile():
    """Returns candidate credentials emphasizing Dual-Anchor framing."""
    return """
CANDIDATE BACKGROUND & DUAL-ANCHOR PROFILE:
Candidate Name: Colby Gross
Education: BS in Computer Science, UMass Amherst (Concentration: Cybersecurity & Networking, Graduation: May 2026).
Core Technical Skills: Agentic AI Systems, Python, C++, Java, Bash, Linux Systems, Networking Protocols, Security Tools (Wireshark, Metasploit), REST APIs, SQLite, Git.
Professional Career Maturity: 7 years of full-time professional work experience outside of tech.
Key Transferable Strengths: Executive communication, project leadership, self-directed work ethic, operational reliability, cross-functional collaboration, crisis management.
"""

def guess_company_domain(company):
    clean = re.sub(r"[^a-zA-Z0-9]", "", company).lower()
    if not clean:
        return "company.com"
    known = {
        "google": "google.com", "meta": "meta.com", "amazon": "amazon.com",
        "apple": "apple.com", "microsoft": "microsoft.com", "anthropic": "anthropic.com",
        "scaleai": "scale.com", "cloudflare": "cloudflare.com", "datadog": "datadoghq.com",
        "toast": "toasttab.com", "hubspot": "hubspot.com", "akamai": "akamai.com"
    }
    for k, v in known.items():
        if k in clean:
            return v
    return f"{clean}.com"

def call_llm(prompt):
    """Executes call to local Ollama model or Gemini API."""
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
            with urllib.request.urlopen(req, timeout=25) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            print(f"Gemini API call error: {e}. Falling back to local Ollama...")

    # Local Ollama fallback
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
        with urllib.request.urlopen(req, timeout=45) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return (res.get("thinking", "") + res.get("response", "")).strip()
    except Exception as e:
        print(f"Ollama API call error: {e}")
        raise RuntimeError("LLM calls failed.")

def tailor_job_lead(lead_id):
    """Generates tailored bullet points, cover letter, recruiter info, and email draft."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM job_leads WHERE id = ?", (lead_id,))
    lead = cursor.fetchone()
    if not lead:
        conn.close()
        raise ValueError(f"Job lead ID {lead_id} not found.")
        
    slots = get_open_calendar_slots()
    slots_formatted = "\n".join([f"- {s}" for s in slots])
    domain = guess_company_domain(lead['company'])
    
    prompt = f"""
You are an expert career placement agent. Analyze the job description and generate a tailored application packet using DUAL-ANCHOR FRAMING (blending 7 years non-tech professional maturity with a UMass Amherst CS degree & Agentic AI / Networking skills).

{get_candidate_baseline_profile()}

TARGET JOB POSITION:
Company: {lead['company']}
Role: {lead['role']}
Location: {lead['location']} (Remote: {'Yes' if lead['is_remote'] else 'No'})
Description: {lead['job_description'][:2000]}

SUGGESTED INTERVIEW AVAILABILITY SLOTS:
{slots_formatted}

INSTRUCTIONS:
Return ONLY a valid JSON object matching this schema without markdown wrappers:
{{
  "match_score": integer (0 to 100 representing job match alignment),
  "recruiter_name": "Name of recruiter/hiring manager or 'Hiring Team'",
  "recruiter_email": "Estimated email address (e.g. recruiter@{domain} or careers@{domain})",
  "tailored_bullets": "3 markdown bullet points blending candidate's technical skills (AI, Python, C++, Security) with 7 years proven professional maturity",
  "cover_letter": "Short 200-word cover letter matching candidate's dual-anchor strengths to this role",
  "cold_email_draft": "Professional 150-word cold outreach email to recruiter incorporating candidate's CS degree, enthusiasm, and proposing the 3 exact interview slots: {slots[0]}, {slots[1]}, and {slots[2]}."
}}
"""
    print(f"Tailoring application for '{lead['role']}' at '{lead['company']}'...")
    raw_response = call_llm(prompt)
    
    raw_clean = raw_response.strip()
    if raw_clean.startswith("```"):
        raw_clean = raw_clean.split("```", 2)[1]
        if raw_clean.startswith("json"):
            raw_clean = raw_clean[4:].strip()
            
    try:
        data = json.loads(raw_clean)
    except Exception as e:
        print(f"JSON parse fallback for lead {lead_id}: {e}")
        data = {
            "match_score": lead['match_score'] or 75,
            "recruiter_name": "Hiring Team",
            "recruiter_email": f"careers@{domain}",
            "tailored_bullets": f"- Built Agentic AI systems & networking scripts aligned with {lead['role']}\n- Leveraged 7 years of professional career experience for reliable project execution\n- Applied UMass Amherst CS core concepts to production software pipelines",
            "cover_letter": f"Dear Hiring Team,\n\nI am writing to express my strong interest in the {lead['role']} position at {lead['company']}. With a BS in Computer Science from UMass Amherst specializing in Agentic AI and Networking, alongside 7 years of proven professional experience, I bring both technical capability and operational reliability to your team.",
            "cold_email_draft": f"Dear Hiring Team,\n\nI recently applied for the {lead['role']} role at {lead['company']} and would love to connect. As a UMass Amherst CS graduate with experience in Agentic AI and backend systems, I am excited about your work.\n\nAre you free for a brief chat at any of these times?\n- {slots[0]}\n- {slots[1]}\n- {slots[2]}\n\nBest regards,\nColby Gross"
        }
        
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Insert or replace into job_applications
    cursor.execute("""
        INSERT INTO job_applications (
            date_applied, company, role, salary_range, status, 
            job_description_url, notes, lead_id, recruiter_name, 
            recruiter_email, cold_email_draft, outreach_status, 
            tailored_bullets, cover_letter
        ) VALUES (?, ?, ?, ?, 'applied', ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
    """, (
        today, lead['company'], lead['role'], lead['salary_range'] or "",
        lead['job_url'], "Tailored via Dual-Anchor Engine", lead['id'],
        data.get("recruiter_name", "Hiring Team"),
        data.get("recruiter_email", f"careers@{domain}"),
        data.get("cold_email_draft", ""),
        data.get("tailored_bullets", ""),
        data.get("cover_letter", "")
    ))
    app_id = cursor.lastrowid
    
    # Update lead status and match_score
    cursor.execute("""
        UPDATE job_leads 
        SET status = 'applied', match_score = ? 
        WHERE id = ?
    """, (data.get("match_score", 75), lead_id))
    
    conn.commit()
    conn.close()
    
    print(f"Successfully tailored lead {lead_id}. Created Application ID: {app_id}")
    return app_id

def batch_tailor_top_leads(limit=10):
    """Processes top un-applied job leads into ready-to-apply application packets."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM job_leads 
        WHERE status = 'lead' 
        ORDER BY match_score DESC, tier ASC 
        LIMIT ?
    """, (limit,))
    leads = cursor.fetchall()
    conn.close()
    
    processed = []
    for row in leads:
        try:
            app_id = tailor_job_lead(row['id'])
            processed.append(app_id)
        except Exception as e:
            print(f"Error tailoring lead {row['id']}: {e}")
            
    return processed

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        tailor_job_lead(int(sys.argv[1]))
    else:
        batch_tailor_top_leads(5)
