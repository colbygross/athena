import os
import json
import shutil
import sqlite3
import mimetypes
import re
import uuid
import base64
import urllib.request
import urllib.error
import tempfile
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database import get_db_connection, init_db

# Calendar imports
from icalendar import Calendar, Event as ICalEvent
# Google Calendar API imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

# Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", BASE_DIR)
VAULT_DIR = os.getenv("VAULT_DIR", os.path.join(WORKSPACE_DIR, "obsidian_vault"))
INBOX_DIR = os.getenv("INBOX_DIR", os.path.join(VAULT_DIR, "Inbox"))
STORAGE_DIR = os.getenv("STORAGE_DIR", os.path.join(WORKSPACE_DIR, "storage"))

def write_file_atomically(file_path, content, mode='w', encoding='utf-8'):
    """
    Write content to a temporary file in the same directory as file_path,
    then atomically replace file_path.
    """
    parent_dir = os.path.dirname(os.path.abspath(file_path))
    os.makedirs(parent_dir, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode=mode, dir=parent_dir, delete=False, suffix=".tmp", encoding=encoding if 'b' not in mode else None) as temp_file:
        temp_file.write(content)
        temp_path = temp_file.name
    try:
        os.replace(temp_path, file_path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


# LLM Config — Ollama (local)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi4-mini:latest")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "qwen3-vl:2b")
OLLAMA_FINANCE_MODEL = os.getenv("OLLAMA_FINANCE_MODEL", "qwen2.5-coder:3b")
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() in ("1", "true", "yes")

def normalize_model_name(model_name):
    if not model_name:
        return "qwen2.5-coder:3b"
    m = model_name.strip().lower()
    if m in ("qwen2.5coder:3b", "qwen2.5coder", "qwen2.5-coder", "qwen2.5-coder:3b"):
        return "qwen2.5-coder:3b"
    return model_name

CATEGORIES = {
    "finances": "02_Areas/Finances",
    "health": "02_Areas/Health",
    "fitness": "02_Areas/Fitness",
    "learning": "02_Areas/Learning",
    "career": "02_Areas/Career",
    "general": "03_Resources"
}

PROMPT_TEMPLATE = """
You are an expert personal data organizer assistant. Analyze the provided file (which might be a receipt, medical record, workout log, study paper, or career document).
Extract the following information and output it in strict JSON format. Do not write any markdown code block formatting or explanation. Just return raw JSON.

JSON Schema:
{
  "category": "finances" | "health" | "fitness" | "learning" | "career" | "general",
  "description": "Short, clear summary of what this document is",
  "recommended_filename": "YYYY-MM-DD_short_descriptive_name.ext" (keep the original extension, replace spaces with underscores, and use lowercase),
  "structured_data": {
    // IF category is finances:
    "date": "YYYY-MM-DD",
    "amount": number (absolute value),
    "type": "expense" | "income",
    "category": "food" | "utilities" | "subscription" | "academic" | "rent" | "salary" | "other",
    "merchant": "name of merchant or source",
    "description": "details",
    "account": "payment method or card name/type if mentioned on the receipt (e.g. 'Capital One', 'Checking', 'Savings', 'Cash', 'Visa') or null"
    
    // IF category is fitness:
    "date": "YYYY-MM-DD",
    "activity_type": "run" | "lift" | "cycle" | "swim" | "yoga" | "other",
    "duration_minutes": number,
    "distance_km": number or null,
    "calories_burned": number or null,
    "intensity": "low" | "medium" | "high",
    "notes": "workout details"
    
    // IF category is health:
    "date": "YYYY-MM-DD",
    "weight_lbs": number or null,
    "sleep_hours": number or null,
    "mood": "scale 1-10",
    "systolic": number or null,
    "diastolic": number or null,
    "notes": "symptoms, doctor visit notes, sleep details"
    
    // IF category is learning:
    "date": "YYYY-MM-DD",
    "topic": "CS concept or tool learned",
    "category": "Computer Science" | "General" | "Math" | "Career",
    "hours_spent": number,
    "notes": "takeaways, brief study notes",
    "source_link": "link or book/paper name",
    "status": "completed" | "in-progress"

    // IF category is career:
    "date_applied": "YYYY-MM-DD",
    "company": "company name",
    "role": "job title",
    "salary_range": "salary info if available",
    "status": "applied" | "interviewing" | "offered",
    "job_description_url": "link",
    "notes": "notes about the job"
    
    // IF category is general:
    // empty object {}
  }
}

Important Rules:
1. Ensure the JSON is well-formed.
2. If you cannot extract a specific value, return null for that field.
3. For dates, default to today's date if not found in the document (use current local date: {current_date}).
4. Ensure category is exactly one of the six options: finances, health, fitness, learning, career, general.
"""

def extract_file_content(file_path):
    """
    Read text files directly. Extract text from PDF files using pdftotext.
    Return None for other binary files or PDFs with no text (which will be processed via vision model).
    """
    import subprocess
    mime_type, _ = mimetypes.guess_type(file_path)
    
    if file_path.lower().endswith('.pdf'):
        try:
            result = subprocess.run(["pdftotext", file_path, "-"], capture_output=True, text=True, check=True)
            text = result.stdout.strip()
            if text:
                return text, mime_type
            else:
                print(f"PDF {file_path} contains no digital text. Falling back to page-to-image conversion for vision model.")
                return None, mime_type
        except Exception as e:
            print(f"Error extracting text from PDF {file_path}: {e}")
            return None, mime_type
            
    if mime_type and (mime_type.startswith("text/") or mime_type in ["application/json", "application/xml"]):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read(), mime_type
        except Exception:
            pass
    return None, mime_type

def get_mock_analysis(filename, file_path):
    """
    Fallback method to generate mock data if GEMINI_API_KEY is not set.
    """
    ext = os.path.splitext(filename)[1].lower()
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    if "receipt" in filename.lower() or "invoice" in filename.lower() or ext in [".png", ".jpg"] and "receipt" in filename.lower():
        return {
            "category": "finances",
            "description": f"Processed Receipt: {filename}",
            "recommended_filename": f"{date_str}_receipt_{filename.replace(' ', '_').lower()}",
            "structured_data": {
                "date": date_str,
                "amount": 15.50,
                "type": "expense",
                "category": "food",
                "merchant": "Local Cafe",
                "description": "Coffee and pastry",
                "account": "Capital One Checking"
            }
        }
    elif "workout" in filename.lower() or "run" in filename.lower():
        return {
            "category": "fitness",
            "description": f"Fitness session: {filename}",
            "recommended_filename": f"{date_str}_workout_{filename.replace(' ', '_').lower()}",
            "structured_data": {
                "date": date_str,
                "activity_type": "run",
                "duration_minutes": 45,
                "distance_km": 5.2,
                "calories_burned": 400,
                "intensity": "medium",
                "notes": "Felt good, steady pace"
            }
        }
    elif "medical" in filename.lower() or "health" in filename.lower() or "report" in filename.lower():
        return {
            "category": "health",
            "description": f"Medical document: {filename}",
            "recommended_filename": f"{date_str}_health_{filename.replace(' ', '_').lower()}",
            "structured_data": {
                "date": date_str,
                "weight_lbs": 165.3,
                "sleep_hours": 7.5,
                "mood": "8",
                "systolic": 120,
                "diastolic": 80,
                "notes": "Standard checkup log"
            }
        }
    elif "study" in filename.lower() or "learn" in filename.lower() or ext == ".pdf":
        return {
            "category": "learning",
            "description": f"Academic reference: {filename}",
            "recommended_filename": f"{date_str}_study_{filename.replace(' ', '_').lower()}",
            "structured_data": {
                "date": date_str,
                "topic": "CS Core Concepts",
                "category": "Computer Science",
                "hours_spent": 2.0,
                "notes": "Reviewed algorithms and data structures.",
                "source_link": "N/A",
                "status": "completed"
            }
        }
    elif "career" in filename.lower() or "resume" in filename.lower() or "job" in filename.lower():
        return {
            "category": "career",
            "description": f"Career related document: {filename}",
            "recommended_filename": f"{date_str}_career_{filename.replace(' ', '_').lower()}",
            "structured_data": {
                "date_applied": date_str,
                "company": "Tech Corp",
                "role": "Software Engineer",
                "salary_range": "$90,000 - $110,000",
                "status": "applied",
                "job_description_url": "https://techcorp.jobs",
                "notes": "Found on LinkedIn"
            }
        }
    else:
        return {
            "category": "general",
            "description": f"General reference file: {filename}",
            "recommended_filename": f"{date_str}_{filename.replace(' ', '_').lower()}",
            "structured_data": {}
        }

def _ollama_generate(prompt, image_data=None, model=None):
    """Call Ollama API to generate structured JSON analysis."""
    import time
    payload = {
        "model": model or OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 2048, "num_ctx": 8192},
    }
    if image_data:
        payload["images"] = [base64.b64encode(image_data).decode("utf-8")]

    url = f"{OLLAMA_BASE_URL}/api/generate"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    max_retries = 3
    base_timeout = 60  # seconds per attempt
    backoff = 2

    for attempt in range(max_retries):
        try:
            # Gradually increase timeout on subsequent attempts if needed
            attempt_timeout = base_timeout + (attempt * 30)
            with urllib.request.urlopen(req, timeout=attempt_timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                # Combine thinking + response for models that separate them (e.g., qwen3)
                raw = (result.get("thinking", "") + result.get("response", "")).strip()
                return raw
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Ollama API query failed after {max_retries} attempts. Last error: {e}")
                raise RuntimeError(f"Ollama API error: {e}")
            sleep_time = backoff ** attempt
            print(f"Ollama API query failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {sleep_time}s...")
            time.sleep(sleep_time)


def analyze_file(file_path):
    """
    Call local Ollama LLM to analyze file content, or fall back to mock data.
    """
    filename = os.path.basename(file_path)
    if not LLM_ENABLED:
        print(f"LLM disabled (LLM_ENABLED=false). Using mock analyzer for {filename}")
        return get_mock_analysis(filename, file_path)

    text_content, mime_type = extract_file_content(file_path)
    current_date = datetime.now().strftime("%Y-%m-%d")
    prompt = PROMPT_TEMPLATE.replace("{current_date}", current_date)

    try:
        if text_content:
            full_prompt = f"{prompt}\n\nFile content:\n{text_content}"
            resp_text = _ollama_generate(full_prompt)
        else:
            # For binary files (PDFs, Images), use vision model
            if file_path.lower().endswith('.pdf'):
                import tempfile
                import subprocess
                with tempfile.TemporaryDirectory() as temp_dir:
                    output_prefix = os.path.join(temp_dir, "page")
                    try:
                        subprocess.run(
                            ["pdftoppm", "-png", "-f", "1", "-l", "1", "-r", "150", file_path, output_prefix],
                            check=True, capture_output=True
                        )
                        png_path = f"{output_prefix}-1.png"
                        if os.path.exists(png_path):
                            with open(png_path, "rb") as f:
                                file_bytes = f.read()
                            print(f"Successfully converted scanned PDF {filename} to PNG for vision processing.")
                        else:
                            raise FileNotFoundError("pdftoppm did not generate page-1.png")
                    except Exception as e:
                        print(f"Failed to convert scanned PDF {filename} to image: {e}. Falling back to raw bytes.")
                        with open(file_path, "rb") as f:
                            file_bytes = f.read()
            else:
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
            resp_text = _ollama_generate(prompt, image_data=file_bytes, model=OLLAMA_VISION_MODEL)

        # Clean response text (remove ```json wrappers if the model generated them)
        resp_text = resp_text.strip()
        if resp_text.startswith("```"):
            resp_text = resp_text.split("```", 2)[1]
            if resp_text.startswith("json"):
                resp_text = resp_text[4:].strip()

        return json.loads(resp_text)
    except Exception as e:
        print(f"Error during LLM analysis of {filename}: {e}. Falling back to mock data.")
        return get_mock_analysis(filename, file_path)

def resolve_account_id(cursor, struct=None, merchant=None, desc=None):
    """
    Resolves the appropriate account_id for a transaction.
    Prefers explicit match, then keywords against account names/types,
    falling back to 'Capital One Checking' or first available account.
    """
    cursor.execute("SELECT id, name, type FROM accounts")
    accounts = [dict(row) for row in cursor.fetchall()]
    if not accounts:
        return None
        
    name_map = {a["name"].lower(): a["id"] for a in accounts}
    
    # 1. Check if struct has explicit account_id
    if struct and struct.get("account_id"):
        for a in accounts:
            if a["id"] == struct["account_id"]:
                return a["id"]
                
    # 2. Check if struct has extracted account string
    extracted_acc = (struct.get("account") or "").strip().lower() if struct else ""
    combined_text = f"{extracted_acc} {merchant or ''} {desc or ''}".lower()
    
    if extracted_acc:
        for a in accounts:
            if a["name"].lower() == extracted_acc or a["name"].lower() in extracted_acc:
                return a["id"]
                
    # Keyword matching against types/names
    if "saving" in combined_text:
        for a in accounts:
            if a["type"] == "savings" or "saving" in a["name"].lower():
                return a["id"]
    if "cash" in combined_text:
        for a in accounts:
            if a["type"] == "cash" or "cash" in a["name"].lower():
                return a["id"]
    if any(k in combined_text for k in ["checking", "capital one", "debit", "visa", "mastercard", "credit"]):
        if "capital one checking" in name_map:
            return name_map["capital one checking"]
        for a in accounts:
            if a["type"] == "checking":
                return a["id"]
                
    # Default fallback to 'Capital One Checking'
    if "capital one checking" in name_map:
        return name_map["capital one checking"]
        
    # Fallback to any checking account
    for a in accounts:
        if a["type"] == "checking":
            return a["id"]
            
    return accounts[0]["id"]

NLP_TRANSACTION_PROMPT = """You are an expert financial assistant. Extract transaction details from the user sentence into strict JSON.

User input: "{text}"
Current Date: {current_date}

JSON Schema:
{{
  "date": "YYYY-MM-DD",
  "amount": number (exact positive float, e.g. 14.50),
  "type": "expense" | "income" | "transfer",
  "category": "food" | "utilities" | "subscription" | "academic" | "rent" | "salary" | "transfer" | "other",
  "merchant": "name of merchant, store, employer, or transfer destination",
  "description": "brief description of the item or reason",
  "account": "payment account mentioned (e.g. 'Capital One Checking', 'Capital One Savings', 'Cash', 'Visa') or null",
  "transfer_account": "destination account if this is a transfer (or null)"
}}

Rules:
1. Ensure the amount matches the full number stated in the input (e.g., if input says $14.50, amount is 14.50; if $125, amount is 125).
2. Infer relative dates relative to {current_date} ("today" = {current_date}, "yesterday" = 1 day before, etc.).
3. If type is "transfer", set type to "transfer", category to "transfer", and identify both source account and destination transfer_account.
4. Return ONLY raw JSON without markdown formatting or commentary.
"""

def fallback_parse_transaction(text, today_str):
    """
    Deterministic rule/regex fallback parser for natural language transactions
    when Ollama is offline or in test environments.
    """
    t_lower = text.lower()
    
    # Extract amount
    amount = 0.0
    amt_match = re.search(r'\$?\s*([0-9]+(?:\.[0-9]{1,2})?)', text)
    if amt_match:
        try:
            amount = float(amt_match.group(1))
        except ValueError:
            amount = 0.0
            
    # Extract type
    tx_type = "expense"
    if any(w in t_lower for w in ["transfer", "moved", "move", "transferred"]):
        tx_type = "transfer"
    elif any(w in t_lower for w in ["income", "paycheck", "salary", "earned", "received", "deposit"]):
        tx_type = "income"
        
    # Extract date
    date = today_str
    try:
        today_dt = datetime.strptime(today_str, "%Y-%m-%d")
        if "yesterday" in t_lower:
            date = (today_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        elif "tomorrow" in t_lower:
            date = (today_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    except Exception:
        pass
        
    # Extract merchant
    merchant = "General"
    at_match = re.search(r'\b(?:at|from|to)\s+([A-Z0-9][a-zA-Z0-9\'\s]+?)(?:\s+(?:on|for|using|with|via|yesterday|today|\$)|$)', text, re.IGNORECASE)
    if at_match:
        candidate = at_match.group(1).strip()
        if candidate.lower() not in ("capital one", "checking", "savings", "cash", "lunch", "dinner", "breakfast"):
            merchant = candidate
            
    # Extract category
    category = "other"
    if tx_type == "transfer":
        category = "transfer"
    elif any(w in t_lower for w in ["chipotle", "starbucks", "food", "lunch", "dinner", "breakfast", "groceries", "restaurant", "cafe"]):
        category = "food"
    elif any(w in t_lower for w in ["electric", "water", "internet", "utility", "bills", "phone"]):
        category = "utilities"
    elif any(w in t_lower for w in ["netflix", "spotify", "subscription", "hulu"]):
        category = "subscription"
    elif any(w in t_lower for w in ["tuition", "course", "book", "academic"]):
        category = "academic"
    elif any(w in t_lower for w in ["rent"]):
        category = "rent"
    elif tx_type == "income":
        category = "salary"

    # Extract accounts
    account = None
    transfer_account = None
    if "cash" in t_lower:
        account = "Cash"
    elif "saving" in t_lower:
        account = "Capital One Savings"
    elif "checking" in t_lower or "capital one" in t_lower:
        account = "Capital One Checking"
        
    if tx_type == "transfer":
        if "to capital one savings" in t_lower or "to savings" in t_lower:
            transfer_account = "Capital One Savings"
        elif "to capital one checking" in t_lower or "to checking" in t_lower:
            transfer_account = "Capital One Checking"

    return {
        "date": date,
        "amount": amount,
        "type": tx_type,
        "category": category,
        "merchant": merchant,
        "description": text,
        "account": account,
        "transfer_account": transfer_account
    }

def parse_natural_language_transaction(text, model=None, current_date=None, cursor=None):
    """
    Parses a natural language sentence into structured transaction data using qwen2.5-coder:3b (Ollama)
    or fallback heuristic if Ollama is disabled/unavailable.
    Resolves account_id and transfer_account_id against database accounts.
    """
    today_str = current_date or datetime.now().strftime("%Y-%m-%d")
    target_model = normalize_model_name(model or OLLAMA_FINANCE_MODEL)
    
    parsed = None
    if LLM_ENABLED:
        prompt = NLP_TRANSACTION_PROMPT.format(text=text, current_date=today_str)
        try:
            raw_response = _ollama_generate(prompt, model=target_model)
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            parsed = json.loads(cleaned)
        except Exception as e:
            print(f"Ollama NLP transaction parsing failed with {target_model}: {e}. Using fallback parser.")

    if not parsed:
        parsed = fallback_parse_transaction(text, today_str)

    # Sanitize and ensure required fields
    tx_type = parsed.get("type", "expense")
    if tx_type not in ("expense", "income", "transfer"):
        tx_type = "expense"
    
    amount = float(parsed.get("amount") or 0.0)
    # Cross-check amount with explicit dollar figure in input text
    amt_match = re.search(r'\$\s*([0-9]+(?:\.[0-9]{1,2})?)', text)
    if amt_match:
        try:
            regex_amt = float(amt_match.group(1))
            if amount <= 0.0 or abs(amount - regex_amt) > 0.01:
                amount = regex_amt
        except ValueError:
            pass

    category = parsed.get("category") or ("transfer" if tx_type == "transfer" else "other")
    merchant = parsed.get("merchant") or "General"
    description = parsed.get("description") or text
    date = parsed.get("date") or today_str
    
    account_id = None
    transfer_account_id = None
    
    close_conn = False
    if cursor is None:
        conn = get_db_connection()
        cursor = conn.cursor()
        close_conn = True
        
    try:
        account_id = resolve_account_id(cursor, parsed, merchant=merchant, desc=f"{description} {text}")
        if tx_type == "transfer":
            transfer_dest = parsed.get("transfer_account")
            if transfer_dest:
                transfer_account_id = resolve_account_id(cursor, {"account": transfer_dest}, merchant=transfer_dest)
            if transfer_account_id == account_id or not transfer_account_id:
                # If destination is same as source, pick an alternate account
                cursor.execute("SELECT id FROM accounts WHERE id != ? ORDER BY id ASC LIMIT 1", (account_id,))
                other_acc = cursor.fetchone()
                if other_acc:
                    transfer_account_id = other_acc["id"]
    finally:
        if close_conn:
            conn.close()
            
    return {
        "date": date,
        "amount": amount,
        "type": tx_type,
        "category": category,
        "merchant": merchant,
        "description": description,
        "account_id": account_id,
        "transfer_account_id": transfer_account_id,
        "extracted_account": parsed.get("account"),
        "extracted_transfer_account": parsed.get("transfer_account")
    }

def save_data_to_db(analysis_results, relative_moved_path):
    """
    Insert records into SQLite database.
    """
    category = analysis_results.get("category", "general")
    desc = analysis_results.get("description", "")
    struct = analysis_results.get("structured_data", {})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. Insert into processed_files
        cursor.execute(
            "INSERT INTO processed_files (original_name, new_path, category, description) VALUES (?, ?, ?, ?)",
            (analysis_results["original_name"], relative_moved_path, category, desc)
        )
        file_id = cursor.lastrowid
        
        # 2. Insert into respective tables
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        if category == "finances" and struct:
            account_id = resolve_account_id(cursor, struct, struct.get("merchant"), desc)
            cursor.execute(
                "INSERT INTO transactions (date, amount, type, category, merchant, description, account_id, file_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    struct.get("date") or current_date_str,
                    struct.get("amount", 0.0),
                    struct.get("type", "expense"),
                    struct.get("category", "other"),
                    struct.get("merchant"),
                    struct.get("description", desc),
                    account_id,
                    file_id
                )
            )
        elif category == "fitness" and struct:
            cursor.execute(
                "INSERT INTO fitness_logs (date, activity_type, duration_minutes, distance_km, calories_burned, intensity, notes, file_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    struct.get("date") or current_date_str,
                    struct.get("activity_type", "other"),
                    struct.get("duration_minutes"),
                    struct.get("distance_km"),
                    struct.get("calories_burned"),
                    struct.get("intensity", "medium"),
                    struct.get("notes", desc),
                    file_id
                )
            )
        elif category == "health" and struct:
            cursor.execute(
                "INSERT OR REPLACE INTO health_logs (date, weight_lbs, sleep_hours, mood, systolic, diastolic, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    struct.get("date") or current_date_str,
                    struct.get("weight_lbs"),
                    struct.get("sleep_hours"),
                    struct.get("mood"),
                    struct.get("systolic"),
                    struct.get("diastolic"),
                    struct.get("notes", desc)
                )
            )
        elif category == "learning" and struct:
            cursor.execute(
                "INSERT INTO learning_progress (date, topic, category, hours_spent, notes, source_link, status, file_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    struct.get("date") or current_date_str,
                    struct.get("topic", "CS study"),
                    struct.get("category", "Computer Science"),
                    struct.get("hours_spent", 0),
                    struct.get("notes", desc),
                    struct.get("source_link"),
                    struct.get("status", "completed"),
                    file_id
                )
            )
        elif category == "career" and struct:
            cursor.execute(
                "INSERT INTO job_applications (date_applied, company, role, salary_range, status, job_description_url, notes, resume_file_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    struct.get("date_applied") or current_date_str,
                    struct.get("company", "Unknown"),
                    struct.get("role", "Software Engineer"),
                    struct.get("salary_range"),
                    struct.get("status", "applied"),
                    struct.get("job_description_url"),
                    struct.get("notes", desc),
                    file_id
                )
            )
            
        conn.commit()
        print(f"Successfully saved {category} record to database.")
    except Exception as e:
        conn.rollback()
        print(f"Database insertion error: {e}")
    finally:
        conn.close()

def create_obsidian_note(analysis, dest_dir, final_filename):
    """
    Create a companion markdown file in the Obsidian vault with links
    and YAML frontmatter metadata.
    """
    note_name = os.path.splitext(final_filename)[0] + ".md"
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
            # Safe representation of strings/objects in YAML
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
    
    write_file_atomically(note_path, "\n".join(content_lines))
        
    print(f"Created Obsidian note: {note_name}")

def update_markdown_file_frontmatter(file_path, analysis):
    """
    Parse an existing markdown file, add or update YAML frontmatter metadata,
    and save it back.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading markdown file {file_path}: {e}")
        return
        
    # Check if there is existing frontmatter
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    
    category = analysis.get("category", "general")
    struct = analysis.get("structured_data", {})
    
    new_fields = {
        "type": "document-context",
        "category": category,
        "original_name": analysis.get("original_name", os.path.basename(file_path)),
        "processed_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    for k, v in struct.items():
        if v is not None:
            new_fields[f"meta_{k}"] = v
            
    yaml_lines = []
    
    if frontmatter_match:
        existing_yaml = frontmatter_match.group(1)
        remaining_content = content[frontmatter_match.end():]
        
        existing_fields = {}
        for line in existing_yaml.split("\n"):
            line = line.strip()
            if not line or ":" not in line:
                continue
            k, v = line.split(":", 1)
            existing_fields[k.strip()] = v.strip()
            
        # Update existing fields with new fields
        existing_fields.update({k: json.dumps(v) if not isinstance(v, str) or v.startswith("[") or v.startswith("{") else v for k, v in new_fields.items()})
        
        for k, v in existing_fields.items():
            yaml_lines.append(f"{k}: {v}")
    else:
        remaining_content = content
        for k, v in new_fields.items():
            yaml_lines.append(f"{k}: {json.dumps(v) if not isinstance(v, str) or v.startswith('[') or v.startswith('{') else v}")
            
    new_frontmatter = "---\n" + "\n".join(yaml_lines) + "\n---\n"
    
    try:
        write_file_atomically(file_path, new_frontmatter + remaining_content.lstrip())
        print(f"Updated YAML frontmatter for: {os.path.basename(file_path)}")
    except Exception as e:
        print(f"Error writing markdown file {file_path}: {e}")


def generate_obsidian_summaries():
    """
    Read SQLite logs and generate visual summaries in the Obsidian vault under /Summaries
    """
    os.makedirs(os.path.join(VAULT_DIR, "Summaries"), exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Weekly Finance Summary
    cursor.execute("""
        SELECT date, amount, type, category, merchant, description 
        FROM transactions 
        ORDER BY date DESC LIMIT 20
    """)
    txs = cursor.fetchall()
    
    finance_md = ["# Weekly Financial Summary\n", "## Recent Transactions\n"]
    finance_md.append("| Date | Merchant | Category | Type | Amount |")
    finance_md.append("| --- | --- | --- | --- | --- |")
    for tx in txs:
        sign = "+" if tx['type'] == 'income' else "-"
        finance_md.append(f"| {tx['date']} | {tx['merchant']} | {tx['category']} | {tx['type'].upper()} | {sign}${tx['amount']:.2f} |")
        
    # Write to Summaries
    write_file_atomically(os.path.join(VAULT_DIR, "Summaries", "Financial_Summary.md"), "\n".join(finance_md))
        
    # 2. Fitness & Health Summary
    cursor.execute("""
        SELECT date, activity_type, duration_minutes, distance_km, calories_burned, notes 
        FROM fitness_logs 
        ORDER BY date DESC LIMIT 10
    """)
    workouts = cursor.fetchall()
    
    fitness_md = ["# Fitness & Health Summary\n", "## Recent Workouts\n"]
    fitness_md.append("| Date | Activity | Duration | Distance | Calories | Notes |")
    fitness_md.append("| --- | --- | --- | --- | --- | --- |")
    for w in workouts:
        dist = f"{w['distance_km']} km" if w['distance_km'] else "N/A"
        cals = w['calories_burned'] if w['calories_burned'] else "N/A"
        fitness_md.append(f"| {w['date']} | {w['activity_type'].capitalize()} | {w['duration_minutes']} mins | {dist} | {cals} | {w['notes']} |")
        
    cursor.execute("SELECT date, weight_lbs, sleep_hours, mood FROM health_logs ORDER BY date DESC LIMIT 7")
    health = cursor.fetchall()
    fitness_md.append("\n## Health Metrics (Last 7 Logs)\n")
    fitness_md.append("| Date | Weight (lbs) | Sleep (hours) | Mood (1-10) |")
    fitness_md.append("| --- | --- | --- | --- |")
    for h in health:
        fitness_md.append(f"| {h['date']} | {h['weight_lbs'] or 'N/A'} | {h['sleep_hours'] or 'N/A'} | {h['mood'] or 'N/A'} |")
        
    write_file_atomically(os.path.join(VAULT_DIR, "Summaries", "Health_Fitness_Summary.md"), "\n".join(fitness_md))
        
    # 3. Learning & Career Summary
    cursor.execute("SELECT date, topic, category, hours_spent, status FROM learning_progress ORDER BY date DESC LIMIT 10")
    learns = cursor.fetchall()
    
    learning_md = ["# Learning & Career Tracker\n", "## Recent Study Topics\n"]
    learning_md.append("| Date | Topic | Category | Hours | Status |")
    learning_md.append("| --- | --- | --- | --- | --- |")
    for l in learns:
        learning_md.append(f"| {l['date']} | {l['topic']} | {l['category']} | {l['hours_spent']} hrs | {l['status'].upper()} |")
        
    cursor.execute("SELECT company, role, status, date_applied FROM job_applications ORDER BY date_applied DESC")
    jobs = cursor.fetchall()
    learning_md.append("\n## Job Applications\n")
    learning_md.append("| Company | Role | Date Applied | Status |")
    learning_md.append("| --- | --- | --- | --- |")
    for j in jobs:
        learning_md.append(f"| {j['company']} | {j['role']} | {j['date_applied']} | {j['status'].upper()} |")
        
    write_file_atomically(os.path.join(VAULT_DIR, "Summaries", "Learning_Career_Summary.md"), "\n".join(learning_md))
        
    conn.close()
    print("Regenerated Obsidian Vault index summaries.")

def process_inbox():
    """
    Main loop to scan and process the inbox folder.
    """
    init_db()
    if not os.path.exists(INBOX_DIR):
        print(f"Inbox directory {INBOX_DIR} does not exist. Creating it.")
        os.makedirs(INBOX_DIR)
        return []
        
    files = [f for f in os.listdir(INBOX_DIR) if os.path.isfile(os.path.join(INBOX_DIR, f))]
    processed = []
    
    if not files:
        print("Inbox is empty. No files to process.")
        # Regenerate summaries anyway to keep files in sync
        generate_obsidian_summaries()
        return []
        
    print(f"Found {len(files)} files in inbox. Commencing processing...")
    
    for filename in files:
        file_path = os.path.join(INBOX_DIR, filename)
        print(f"\nProcessing: {filename}")
        
        # 1. Ask LLM to analyze the file
        analysis = analyze_file(file_path)
        analysis["original_name"] = filename
        
        category = analysis.get("category", "general")
        sub_folder = CATEGORIES.get(category, "03_Resources")
        recommended_name = analysis.get("recommended_filename") or filename
        
        is_md = filename.lower().endswith('.md')
        
        if is_md:
            dest_dir = os.path.join(VAULT_DIR, sub_folder)
            os.makedirs(dest_dir, exist_ok=True)
            
            final_filename = recommended_name
            dest_file_path = os.path.join(dest_dir, final_filename)
            if os.path.exists(dest_file_path):
                base, ext = os.path.splitext(recommended_name)
                final_filename = f"{base}_{int(datetime.now().timestamp())}{ext}"
                dest_file_path = os.path.join(dest_dir, final_filename)
                
            try:
                shutil.move(file_path, dest_file_path)
                print(f"Moved markdown file to: {dest_file_path}")
            except Exception as e:
                print(f"Failed to move file: {e}")
                continue
                
            # Update companion frontmatter in-place
            update_markdown_file_frontmatter(dest_file_path, analysis)
            relative_moved_path = os.path.join("obsidian_vault", sub_folder, final_filename)
        else:
            dest_dir = STORAGE_DIR
            os.makedirs(dest_dir, exist_ok=True)
            
            final_filename = recommended_name
            dest_file_path = os.path.join(dest_dir, final_filename)
            if os.path.exists(dest_file_path):
                base, ext = os.path.splitext(recommended_name)
                final_filename = f"{base}_{int(datetime.now().timestamp())}{ext}"
                dest_file_path = os.path.join(dest_dir, final_filename)
                
            try:
                shutil.move(file_path, dest_file_path)
                print(f"Moved original file to flat storage: {dest_file_path}")
            except Exception as e:
                print(f"Failed to move file: {e}")
                continue
                
            # Create companion Obsidian note under the relevant vault directory
            vault_dest_dir = os.path.join(VAULT_DIR, sub_folder)
            os.makedirs(vault_dest_dir, exist_ok=True)
            create_obsidian_note(analysis, vault_dest_dir, final_filename)
            relative_moved_path = os.path.join("storage", final_filename)
            
        # 4. Save metadata to DB
        save_data_to_db(analysis, relative_moved_path)
        
        processed.append({
            "original_name": filename,
            "new_name": final_filename,
            "category": category,
            "description": analysis.get("description", "")
        })
        
        # 5. Cooling sleep to enforce sequential separation and prevent Ollama overload
        import time
        time.sleep(2)
        
    # 5. Regenerate Vault markdown summary sheets
    generate_obsidian_summaries()
    return processed

# --- TASK AND CALENDAR SYNCHRONIZATION HELPERS ---

def toggle_task_in_file(vault_dir, relative_file_path, task_title, mark_completed):
    if not relative_file_path:
        relative_file_path = "tasks.md"
    file_path = os.path.join(vault_dir, relative_file_path)
    if not os.path.exists(file_path):
        if relative_file_path == "tasks.md":
            try:
                write_file_atomically(file_path, "# Athena Tasks\n\n")
            except Exception as e:
                print(f"Error initializing tasks.md: {e}")
                return False
        else:
            return False
            
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading task source file {file_path}: {e}")
        return False
        
    old_state = "- [ ]" if mark_completed else "- [x]"
    new_state = "- [x]" if mark_completed else "- [ ]"
    
    updated = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("- [ ]") or stripped.startswith("- [x]") or stripped.startswith("- [X]"):
            # Normalize title from line
            raw_title = stripped[5:].strip()
            # Strip due date
            raw_title = re.sub(r'📅\s*\d{4}-\d{2}-\d{2}', '', raw_title).strip()
            # Strip tags
            raw_title = re.sub(r'#(high|medium|low|major|minor|p1|p2|p3)\b', '', raw_title, flags=re.IGNORECASE).strip()
            # Normalize spaces
            normalized_line_title = re.sub(r'\s+', ' ', raw_title).strip()
            normalized_target = re.sub(r'\s+', ' ', task_title.strip()).strip()
            
            if normalized_line_title == normalized_target:
                if stripped.startswith(old_state):
                    idx = line.find(old_state)
                    if idx != -1:
                        lines[i] = line[:idx] + new_state + line[idx + len(old_state):]
                        updated = True
                        break
                elif stripped.startswith(new_state):
                    updated = True # already in correct state
                    break
                
    if not updated and relative_file_path == "tasks.md":
        lines.append(f"{new_state} {task_title}\n")
        updated = True
        
    if updated:
        try:
            write_file_atomically(file_path, "".join(lines))
            return True
        except Exception as e:
            print(f"Error writing to task source file {file_path}: {e}")
            return False
    return False

def sync_db_to_tasks_md_helper():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Fetch pending tasks and tasks completed in the last 24 hours
    one_day_ago = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        SELECT * FROM tasks 
        WHERE status = 'pending' OR (status = 'completed' AND completed_at >= ?)
        ORDER BY category ASC, due_date ASC, created_at DESC
    """, (one_day_ago,))
    rows = cursor.fetchall()
    conn.close()
    
    categories_tasks = {}
    for row in rows:
        cat = row['category'] or 'general'
        if cat not in categories_tasks:
            categories_tasks[cat] = []
        categories_tasks[cat].append(row)
        
    content = [
        "# Athena Tasks\n",
        "This file is synced automatically with your Athena OS Dashboard.\n"
    ]
    
    for cat in ["finances", "health", "fitness", "learning", "career", "general"]:
        tasks_in_cat = categories_tasks.get(cat, [])
        if not tasks_in_cat:
            continue
            
        content.append(f"\n## {cat.capitalize()}")
        for t in tasks_in_cat:
            checkbox = "- [ ]" if t['status'] == 'pending' else "- [x]"
            tags = []
            importance = t['importance'] or 'minor'
            priority = t['priority'] or 'medium'
            if importance == 'major':
                tags.append('#major')
            elif importance == 'minor':
                tags.append('#minor')
            if priority == 'high':
                tags.append('#high')
            elif priority == 'medium':
                tags.append('#medium')
            elif priority == 'low':
                tags.append('#low')
            tag_str = " " + " ".join(tags) if tags else ""
            due_str = f" 📅 {t['due_date']}" if t['due_date'] else ""
            content.append(f"{checkbox} {t['title']}{tag_str}{due_str}")
            
    # Remaining categories
    for cat, tasks_in_cat in categories_tasks.items():
        if cat in ["finances", "health", "fitness", "learning", "career", "general"]:
            continue
        content.append(f"\n## {cat.capitalize()}")
        for t in tasks_in_cat:
            checkbox = "- [ ]" if t['status'] == 'pending' else "- [x]"
            tags = []
            importance = t['importance'] or 'minor'
            priority = t['priority'] or 'medium'
            if importance == 'major':
                tags.append('#major')
            elif importance == 'minor':
                tags.append('#minor')
            if priority == 'high':
                tags.append('#high')
            elif priority == 'medium':
                tags.append('#medium')
            elif priority == 'low':
                tags.append('#low')
            tag_str = " " + " ".join(tags) if tags else ""
            due_str = f" 📅 {t['due_date']}" if t['due_date'] else ""
            content.append(f"{checkbox} {t['title']}{tag_str}{due_str}")
            
    tasks_md_path = os.path.join(VAULT_DIR, "tasks.md")
    try:
        write_file_atomically(tasks_md_path, "\n".join(content) + "\n")
    except Exception as e:
        print(f"Error writing to tasks.md: {e}")

def serialize_local_events_to_ics_helper():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM calendar_events WHERE source = 'local_ics'")
    rows = cursor.fetchall()
    conn.close()
    
    cal = Calendar()
    cal.add('prodid', '-//Athena OS Calendar//mxm.dk//')
    cal.add('version', '2.0')
    
    for row in rows:
        event = ICalEvent()
        event.add('summary', row['title'])
        if row['description']:
            event.add('description', row['description'])
            
        def parse_dt(dt_str):
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M"):
                try:
                    return datetime.strptime(dt_str, fmt)
                except ValueError:
                    continue
            try:
                return datetime.strptime(dt_str, "%Y-%m-%d")
            except ValueError:
                pass
            return datetime.now()

        start_dt = parse_dt(row['start_time'])
        end_dt = parse_dt(row['end_time'])
        
        event.add('dtstart', start_dt)
        event.add('dtend', end_dt)
        event.add('uid', row['event_uid'])
        event.add('dtstamp', datetime.now())
        
        cal.add_component(event)
        
    ics_path = os.path.join(VAULT_DIR, "calendar.ics")
    try:
        write_file_atomically(ics_path, cal.to_ical(), mode='wb')
        print(f"Serialized local events to {ics_path}")
    except Exception as e:
        print(f"Error writing to calendar.ics: {e}")

def parse_local_ics():
    ics_path = os.path.join(VAULT_DIR, "calendar.ics")
    if not os.path.exists(ics_path):
        return []
        
    events = []
    try:
        with open(ics_path, 'rb') as f:
            cal = Calendar.from_ical(f.read())
            
        for component in cal.walk():
            if component.name == "VEVENT":
                title = str(component.get('summary'))
                description = str(component.get('description')) if component.get('description') else None
                
                dtstart = component.get('dtstart').dt
                dtend = component.get('dtend').dt if component.get('dtend') else dtstart
                
                if isinstance(dtstart, datetime):
                    start_str = dtstart.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    start_str = f"{dtstart.strftime('%Y-%m-%d')} 00:00:00"
                    
                if isinstance(dtend, datetime):
                    end_str = dtend.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    end_str = f"{dtend.strftime('%Y-%m-%d')} 23:59:59"
                    
                uid = str(component.get('uid'))
                
                events.append({
                    'title': title,
                    'description': description,
                    'start_time': start_str,
                    'end_time': end_str,
                    'event_uid': uid
                })
    except Exception as e:
        print(f"Error parsing local ICS: {e}")
        
    return events

def sync_local_ics_to_db():
    local_events = parse_local_ics()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT event_uid FROM calendar_events WHERE source = 'local_ics'")
        existing_uids = set([row['event_uid'] for row in cursor.fetchall()])
        
        parsed_uids = set([ev['event_uid'] for ev in local_events])
        
        uids_to_delete = existing_uids - parsed_uids
        for uid in uids_to_delete:
            cursor.execute("DELETE FROM calendar_events WHERE event_uid = ?", (uid,))
            
        for ev in local_events:
            cursor.execute(
                """INSERT INTO calendar_events 
                   (title, description, start_time, end_time, source, event_uid) 
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(event_uid) DO UPDATE SET
                   title=excluded.title,
                   description=excluded.description,
                   start_time=excluded.start_time,
                   end_time=excluded.end_time""",
                (ev['title'], ev['description'], ev['start_time'], ev['end_time'], "local_ics", ev['event_uid'])
            )
        conn.commit()
        print(f"Synced {len(local_events)} local calendar events to database.")
    except Exception as e:
        conn.rollback()
        print(f"Error syncing local ICS to database: {e}")
    finally:
        conn.close()

def sync_google_calendar():
    creds = None
    token_path = os.path.join(BASE_DIR, 'token.json')
    creds_path = os.path.join(BASE_DIR, 'credentials.json')
    
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            print(f"Error loading token.json: {e}")
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing Google Calendar credentials: {e}")
                creds = None
        else:
            if os.path.exists(creds_path):
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                    creds = flow.run_local_server(port=0)
                    with open(token_path, 'w') as token:
                        token.write(creds.to_json())
                except Exception as e:
                    print(f"Google Calendar OAuth flow failed: {e}. Skipping Google Calendar sync.")
                    return []
            else:
                print("credentials.json not found. Skipping Google Calendar sync.")
                return []
                
    if not creds:
        return []
        
    try:
        service = build('calendar', 'v3', credentials=creds)
        time_min = (datetime.utcnow() - timedelta(days=30)).isoformat() + 'Z'
        time_max = (datetime.utcnow() + timedelta(days=60)).isoformat() + 'Z'
        
        print('Fetching events from Google Calendar...')
        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        return events_result.get('items', [])
    except Exception as e:
        print(f"Error fetching Google Calendar events: {e}")
        return []

def sync_google_calendar_to_db():
    google_events = sync_google_calendar()
    if not google_events:
        return
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Clear upcoming/recent Google events
        time_min = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        time_max = (datetime.utcnow() + timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "DELETE FROM calendar_events WHERE source = 'google' AND start_time >= ? AND start_time <= ?",
            (time_min, time_max)
        )
        
        count = 0
        for ev in google_events:
            title = ev.get('summary', 'No Title')
            description = ev.get('description', '')
            
            start = ev.get('start', {})
            end = ev.get('end', {})
            
            start_time = start.get('dateTime') or start.get('date')
            end_time = end.get('dateTime') or end.get('date')
            
            if not start_time:
                continue
                
            def clean_iso(iso_str):
                if 'T' in iso_str:
                    parts = iso_str.split('T')
                    date_part = parts[0]
                    time_part = parts[1].split('-')[0].split('+')[0].split('Z')[0]
                    return f"{date_part} {time_part}"
                else:
                    return f"{iso_str} 00:00:00"
                    
            start_str = clean_iso(start_time)
            end_str = clean_iso(end_time) if end_time else start_str
            
            cursor.execute(
                """INSERT OR REPLACE INTO calendar_events 
                   (title, description, start_time, end_time, source, event_uid) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (title, description, start_str, end_str, "google", ev['id'])
            )
            count += 1
            
        conn.commit()
        print(f"Synced {count} Google Calendar events to database.")
    except Exception as e:
        conn.rollback()
        print(f"Error syncing Google Calendar to database: {e}")
    finally:
        conn.close()

def scan_vault_for_tasks():
    task_pattern = re.compile(r'^\s*-\s*\[([ xX])\]\s*(.+)$')
    due_date_pattern = re.compile(r'📅\s*(\d{4}-\d{2}-\d{2})')
    
    last_sync_path = os.path.join(STORAGE_DIR, "last_task_sync.txt")
    last_sync_time = 0.0
    if os.path.exists(last_sync_path):
        try:
            with open(last_sync_path, "r") as sf:
                last_sync_time = float(sf.read().strip())
        except Exception:
            pass
            
    tasks = []
    
    for root, dirs, files in os.walk(VAULT_DIR):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['Summaries', '04_Archive', '04_Archives', 'Daily_Briefs', '.obsidian']]
        
        for file in files:
            if not file.endswith('.md'):
                continue
            if file == "tasks.md":
                continue
                
            file_path = os.path.join(root, file)
            relative_file = os.path.relpath(file_path, VAULT_DIR).replace('\\', '/')
            
            loaded_from_db = False
            if last_sync_time > 0:
                try:
                    file_mtime = os.path.getmtime(file_path)
                    if file_mtime <= last_sync_time:
                        db_tasks = []
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT title, category, status, due_date, line_number, priority, importance FROM tasks WHERE source_file = ?",
                            (relative_file,)
                        )
                        rows = cursor.fetchall()
                        conn.close()
                        
                        if rows:
                            for row in rows:
                                db_tasks.append({
                                    'title': row['title'],
                                    'category': row['category'],
                                    'status': row['status'],
                                    'due_date': row['due_date'],
                                    'source_file': relative_file,
                                    'line_number': row['line_number'],
                                    'priority': row['priority'],
                                    'importance': row['importance']
                                })
                            tasks.extend(db_tasks)
                            loaded_from_db = True
                except Exception as e:
                    print(f"Error loading tasks from DB for {relative_file}: {e}")
            
            if loaded_from_db:
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"Error reading task list from {file_path}: {e}")
                continue
                
            for idx, line in enumerate(lines):
                match = task_pattern.match(line)
                if match:
                    status_char = match.group(1)
                    task_text = match.group(2).strip()
                    
                    status = 'completed' if status_char.lower() == 'x' else 'pending'
                    
                    due_match = due_date_pattern.search(task_text)
                    due_date = None
                    if due_match:
                        due_date = due_match.group(1)
                        task_text = due_date_pattern.sub('', task_text).strip()
                        
                    # Defaults
                    priority = 'medium'
                    importance = 'minor'
                    
                    importance_pattern = re.compile(r'#major\b|#minor\b', re.IGNORECASE)
                    priority_pattern = re.compile(r'#high\b|#p1\b|#medium\b|#p2\b|#low\b|#p3\b', re.IGNORECASE)
                    
                    # Extract importance
                    imp_match = importance_pattern.search(task_text)
                    if imp_match:
                        imp_str = imp_match.group(0).lower()
                        if imp_str == '#major':
                            importance = 'major'
                        elif imp_str == '#minor':
                            importance = 'minor'
                        task_text = importance_pattern.sub('', task_text).strip()
                    
                    # Extract priority
                    pri_match = priority_pattern.search(task_text)
                    if pri_match:
                        pri_str = pri_match.group(0).lower()
                        if pri_str in ('#high', '#p1'):
                            priority = 'high'
                        elif pri_str in ('#medium', '#p2'):
                            priority = 'medium'
                        elif pri_str in ('#low', '#p3'):
                            priority = 'low'
                        task_text = priority_pattern.sub('', task_text).strip()
                        
                    task_text = re.sub(r'\s+', ' ', task_text).strip()
                        
                    category = 'general'
                    for cat_name, cat_path in CATEGORIES.items():
                        if relative_file.replace('\\', '/').startswith(cat_path):
                            category = cat_name
                            break
                            
                    tasks.append({
                        'title': task_text,
                        'category': category,
                        'status': status,
                        'due_date': due_date,
                        'source_file': relative_file.replace('\\', '/'),
                        'line_number': idx + 1,
                        'priority': priority,
                        'importance': importance
                    })
                    
    # Save the last sync time
    try:
        os.makedirs(STORAGE_DIR, exist_ok=True)
        with open(last_sync_path, "w") as sf:
            sf.write(str(datetime.now().timestamp()))
    except Exception as e:
        print(f"Error saving last task sync timestamp: {e}")

    return tasks

def reconcile_tasks_in_db(scanned_tasks):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, title, status, source_file, priority, importance FROM tasks")
        db_tasks = cursor.fetchall()
        
        db_task_map = {}
        for row in db_tasks:
            key = (row['source_file'], row['title'])
            db_task_map[key] = row
            
        scanned_keys = set()
        
        for task in scanned_tasks:
            key = (task['source_file'], task['title'])
            scanned_keys.add(key)
            
            if key in db_task_map:
                db_row = db_task_map[key]
                if (db_row['status'] != task['status'] or 
                    db_row['priority'] != task['priority'] or 
                    db_row['importance'] != task['importance']):
                    completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if task['status'] == 'completed' else None
                    cursor.execute(
                        "UPDATE tasks SET status = ?, completed_at = ?, due_date = ?, line_number = ?, category = ?, priority = ?, importance = ? WHERE id = ?",
                        (task['status'], completed_at, task['due_date'], task['line_number'], task['category'], task['priority'], task['importance'], db_row['id'])
                    )
                else:
                    cursor.execute(
                        "UPDATE tasks SET due_date = ?, line_number = ?, category = ? WHERE id = ?",
                        (task['due_date'], task['line_number'], task['category'], db_row['id'])
                    )
            else:
                completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if task['status'] == 'completed' else None
                cursor.execute(
                    "INSERT INTO tasks (title, category, status, due_date, completed_at, source_file, line_number, priority, importance) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (task['title'], task['category'], task['status'], task['due_date'], completed_at, task['source_file'], task['line_number'], task['priority'], task['importance'])
                )
                
        # Clean up tasks in DB that are missing from vault notes (only if source_file is not tasks.md or null)
        for key, db_row in db_task_map.items():
            src_file = db_row['source_file']
            if src_file and src_file != "tasks.md" and key not in scanned_keys:
                cursor.execute("DELETE FROM tasks WHERE id = ?", (db_row['id'],))
                
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error reconciling tasks in database: {e}")
    finally:
        conn.close()

def parse_workout_regimen(vault_dir, day_name):
    """
    Parses Workout_Routine.md in vault_dir/02_Areas/Fitness/.
    Finds the routine for the given day of the week (e.g. 'Monday').
    """
    regimen_path = os.path.join(vault_dir, "02_Areas", "Fitness", "Workout_Routine.md")
    if not os.path.exists(regimen_path):
        return None
        
    try:
        with open(regimen_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        header_pattern = re.compile(
            rf"^###\s*{day_name}\b.*$", 
            re.MULTILINE | re.IGNORECASE
        )
        header_match = header_pattern.search(content)
        if not header_match:
            return None
            
        start_idx = header_match.end()
        
        next_section_pattern = re.compile(
            r"^(#+|---|[*]{3})\s+", 
            re.MULTILINE
        )
        next_match = next_section_pattern.search(content, start_idx)
        end_idx = next_match.start() if next_match else len(content)
        
        routine_text = content[start_idx:end_idx].strip()
        
        exercises = []
        for line in routine_text.splitlines():
            line = line.strip()
            if line.startswith("-") or line.startswith("*"):
                ex = re.sub(r"^[-*]\s*", "", line)
                exercises.append(ex)
                
        if not exercises:
            return None
            
        return {
            "name": f"{day_name}'s Split",
            "exercises": exercises
        }
    except Exception as e:
        print(f"Error parsing Workout_Routine.md: {e}")
        return None


def generate_daily_brief():
    os.makedirs(os.path.join(VAULT_DIR, "Daily_Briefs"), exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    today_start = f"{today} 04:00:00"
    today_end = f"{tomorrow} 03:59:59"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Today's events
        cursor.execute("""
            SELECT * FROM calendar_events 
            WHERE (start_time >= ? AND start_time <= ?) OR (start_time <= ? AND end_time >= ?)
            ORDER BY start_time ASC
        """, (today_start, today_end, today_start, today_start))
        events = cursor.fetchall()
        
        # Tasks due today (still pending)
        cursor.execute("""
            SELECT * FROM tasks 
            WHERE status = 'pending' AND due_date = ?
        """, (today,))
        due_tasks = cursor.fetchall()
        
        # Tasks completed today
        cursor.execute("""
            SELECT * FROM tasks 
            WHERE status = 'completed' AND completed_at >= ? AND completed_at <= ?
        """, (today_start, today_end))
        completed_today = cursor.fetchall()
        
        # Overdue / pushed-off tasks (pending with a due_date before today)
        cursor.execute("""
            SELECT * FROM tasks 
            WHERE status = 'pending' AND due_date IS NOT NULL AND due_date != '' AND due_date < ?
            ORDER BY due_date ASC
        """, (today,))
        overdue_tasks = cursor.fetchall()
        
        # Other pending tasks (no due date or future due date)
        cursor.execute("""
            SELECT * FROM tasks 
            WHERE status = 'pending' AND (due_date IS NULL OR due_date = '' OR due_date > ?)
            ORDER BY due_date ASC, category ASC LIMIT 10
        """, (today,))
        upcoming_tasks = cursor.fetchall()
        
        # Today's habits
        cursor.execute("""
            SELECT * FROM habit_logs 
            WHERE date = ?
            ORDER BY habit_name ASC
        """, (today,))
        todays_habits = cursor.fetchall()
        
        # Yesterday's accomplishments
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday_start = f"{yesterday} 04:00:00"
        yesterday_end = f"{today} 03:59:59"
        
        cursor.execute("""
            SELECT * FROM tasks 
            WHERE status = 'completed' AND completed_at >= ? AND completed_at <= ?
        """, (yesterday_start, yesterday_end))
        completed_yesterday = cursor.fetchall()
        
        cursor.execute("""
            SELECT * FROM fitness_logs 
            WHERE date = ?
        """, (yesterday,))
        fitness_yesterday = cursor.fetchall()
        
        cursor.execute("""
            SELECT * FROM health_logs 
            WHERE date = ?
        """, (yesterday,))
        health_yesterday = cursor.fetchone()
        
        # --- Build the brief ---
        brief = []
        brief.append(f"# Daily Brief — {today}\n")
        brief.append(f"> Generated by Athena at {datetime.now().strftime('%H:%M:%S')}\n")
        
        # Today's Schedule
        brief.append("## 📅 Today's Schedule")
        if events:
            for ev in events:
                time_str = ev['start_time'].split(' ')[1][:5] if ' ' in ev['start_time'] else "All Day"
                src = "Google" if ev['source'] == 'google' else "Local"
                brief.append(f"- **{time_str}** ({src}): {ev['title']} — *{ev['description'] or 'No description'}*")
        else:
            brief.append("- No events scheduled for today.")
            
        # Tasks Completed Today
        brief.append(f"\n## ✅ Completed Today ({len(completed_today)})")
        if completed_today:
            for t in completed_today:
                completed_time = ""
                if t['completed_at']:
                    try:
                        completed_time = f" at {t['completed_at'].split(' ')[1][:5]}"
                    except (IndexError, AttributeError):
                        pass
                brief.append(f"- [x] {t['title']} ({t['category']}){completed_time}")
        else:
            brief.append("- Nothing checked off yet today.")
            
        # Tasks Still Due Today
        brief.append(f"\n## 🎯 Still Due Today ({len(due_tasks)})")
        if due_tasks:
            for t in due_tasks:
                brief.append(f"- [ ] {t['title']} ({t['category']})")
        else:
            brief.append("- All clear — no outstanding tasks due today.")
            
        # Overdue / Pushed Off
        brief.append(f"\n## ⚠️ Overdue / Pushed Off ({len(overdue_tasks)})")
        if overdue_tasks:
            for t in overdue_tasks:
                try:
                    due_dt = datetime.strptime(t['due_date'], "%Y-%m-%d")
                    days_late = (datetime.strptime(today, "%Y-%m-%d") - due_dt).days
                    brief.append(f"- [ ] {t['title']} ({t['category']}) — was due {t['due_date']} ({days_late}d overdue)")
                except (ValueError, TypeError):
                    brief.append(f"- [ ] {t['title']} ({t['category']}) — was due {t['due_date'] or 'N/A'}")
        else:
            brief.append("- No overdue tasks. You're on track.")
            
        # Today's Habits
        brief.append(f"\n## 🔄 Habit Checklist")
        default_habits = ['Code 1 Hour', 'Read 10 pages', 'Workout', 'Drink 3L Water', 'Sleep 8 hours']
        logged_habits = {h['habit_name']: h['completed'] for h in todays_habits}
        habits_done = sum(1 for v in logged_habits.values() if v == 1)
        habits_total = max(len(default_habits), len(logged_habits))
        brief.append(f"**{habits_done}/{habits_total}** habits completed today.\n")
        
        for habit_name in default_habits:
            if habit_name in logged_habits:
                check = "x" if logged_habits[habit_name] == 1 else " "
                brief.append(f"- [{check}] {habit_name}")
            else:
                brief.append(f"- [ ] {habit_name} *(not logged)*")
        # Include any extra tracked habits not in the default list
        for habit_name, completed in logged_habits.items():
            if habit_name not in default_habits:
                check = "x" if completed == 1 else " "
                brief.append(f"- [{check}] {habit_name}")
        
        # Today's Workout Routine
        try:
            today_dt = datetime.strptime(today, "%Y-%m-%d")
        except Exception:
            today_dt = datetime.now()
            
        day_name = today_dt.strftime("%A")  # e.g., 'Monday'
        
        # Parse from Workout_Routine.md based on day of week
        current_routine = parse_workout_regimen(VAULT_DIR, day_name)
        
        if not current_routine:
            print(f"Falling back to default for {day_name}.")
            current_routine = {
                "name": f"{day_name} (Fallback)",
                "exercises": ["Refer to Workout_Routine.md for today's session."]
            }
        
        brief.append(f"\n## 🏋️ Today's Workout Routine")
        brief.append(f"**Routine**: {current_routine['name']}")
        brief.append("Reference: [[02_Areas/Fitness/Workout_Routine|Workout Routine]]\n")
        for exercise in current_routine['exercises']:
            brief.append(f"- [ ] {exercise}")
        
        # Upcoming Tasks
        brief.append(f"\n## 📋 Coming Up Next")
        if upcoming_tasks:
            for t in upcoming_tasks:
                due = f" 📅 {t['due_date']}" if t['due_date'] else ""
                brief.append(f"- [ ] {t['title']} ({t['category']}){due}")
        else:
            brief.append("- No upcoming tasks in the queue.")
            
        # Yesterday's Review
        brief.append(f"\n## ↩️ Yesterday's Review ({yesterday})")
        has_yesterday = False
        if completed_yesterday:
            has_yesterday = True
            brief.append(f"### Completed ({len(completed_yesterday)} tasks)")
            for t in completed_yesterday:
                brief.append(f"- [x] {t['title']} ({t['category']})")
        if fitness_yesterday:
            has_yesterday = True
            brief.append("\n### Fitness")
            for f_log in fitness_yesterday:
                dist = f" ({f_log['distance_km']} km)" if f_log['distance_km'] else ""
                brief.append(f"- {f_log['activity_type'].capitalize()} for {f_log['duration_minutes']} mins{dist}")
        if health_yesterday:
            has_yesterday = True
            brief.append("\n### Health")
            sleep = f"Sleep: {health_yesterday['sleep_hours']}h" if health_yesterday['sleep_hours'] else "Sleep: —"
            mood = f"Mood: {health_yesterday['mood']}/10" if health_yesterday['mood'] else "Mood: —"
            brief.append(f"- {sleep} · {mood}")
            
        if not has_yesterday:
            brief.append("- No tracked activity recorded yesterday.")
            
        brief_path = os.path.join(VAULT_DIR, "Daily_Briefs", f"Daily_Brief_{today}.md")
        write_file_atomically(brief_path, "\n".join(brief) + "\n")
            
        print(f"Generated Daily Brief at {brief_path}")
    except Exception as e:
        print(f"Error generating Daily Brief: {e}")
        raise e
    finally:
        conn.close()

def generate_daily_summary(target_date=None):
    """
    Generate a comprehensive daily summary for a specific date (defaults to YESTERDAY).
    Archive it to 04_Archives/, then delete the daily brief for that date.
    Pulls tasks, events, habits, inbox, fitness, health, finances, learning, and career data.
    """
    if target_date is None:
        logical_now = datetime.now() - timedelta(hours=4)
        target_date = (logical_now - timedelta(days=1)).strftime("%Y-%m-%d")
        
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    target_start = f"{target_date} 04:00:00"
    target_end = f"{(target_dt + timedelta(days=1)).strftime('%Y-%m-%d')} 03:59:59"

    os.makedirs(os.path.join(VAULT_DIR, "04_Archives"), exist_ok=True)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # ---- TASKS: all tasks active on target_date ----
        cursor.execute("""
            SELECT * FROM tasks
            WHERE (completed_at >= ? AND completed_at <= ?)
               OR (due_date = ?)
               OR (created_at >= ? AND created_at <= ?)
            ORDER BY status DESC, category ASC
        """, (target_start, target_end, target_date, target_start, target_end))
        yesterday_tasks = cursor.fetchall()
        
        # ---- EVENTS ----
        cursor.execute("""
            SELECT * FROM calendar_events 
            WHERE (start_time >= ? AND start_time <= ?) OR (start_time <= ? AND end_time >= ?)
            ORDER BY start_time ASC
        """, (target_start, target_end, target_start, target_start))
        events = cursor.fetchall()

        # ---- HABITS ----
        cursor.execute("SELECT * FROM habit_logs WHERE date = ? ORDER BY habit_name ASC", (target_date,))
        yesterday_habits = cursor.fetchall()

        # ---- INBOX processed files ----
        cursor.execute("""
            SELECT * FROM processed_files
            WHERE processed_at >= ? AND processed_at <= ?
            ORDER BY processed_at ASC
        """, (target_start, target_end))
        inbox_processed = cursor.fetchall()

        # ---- FITNESS ----
        cursor.execute("SELECT * FROM fitness_logs WHERE date = ?", (target_date,))
        fitness_yesterday = cursor.fetchall()

        # ---- HEALTH ----
        cursor.execute("SELECT * FROM health_logs WHERE date = ?", (target_date,))
        health_yesterday = cursor.fetchone()

        # ---- FINANCES ----
        cursor.execute("SELECT * FROM transactions WHERE date = ?", (target_date,))
        transactions_yesterday = cursor.fetchall()

        # ---- LEARNING ----
        cursor.execute("SELECT * FROM learning_progress WHERE date = ?", (target_date,))
        learning_yesterday = cursor.fetchall()

        # ---- CAREER ----
        cursor.execute("SELECT * FROM job_applications WHERE date_applied = ?", (target_date,))
        career_yesterday = cursor.fetchall()

        # ---- BUILD THE SUMMARY ----
        lines = []
        lines.append("---")
        lines.append("type: daily-summary")
        lines.append("tags:")
        lines.append("  - daily-summary")
        lines.append(f"date: {target_date}")
        lines.append("---")
        lines.append("")
        lines.append(f"# Daily Summary — {target_date}")
        lines.append(f"> Archived by Athena at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # --- Tasks ---
        completed = [t for t in yesterday_tasks if t['status'] == 'completed' and t['completed_at'] and target_start <= t['completed_at'] <= target_end]
        pending = [t for t in yesterday_tasks if t['status'] == 'pending' and t['due_date'] == target_date]
        total_tasks = len(completed) + len(pending)

        lines.append(f"## 📋 Tasks ({total_tasks} total — {len(completed)} done, {len(pending)} left)")
        lines.append("")

        if completed:
            lines.append("### ✅ Completed")
            for t in completed:
                cat = t['category'] or 'general'
                lines.append(f"- [x] {t['title']} ({cat})")
            lines.append("")

        if pending:
            lines.append("### ❌ Not Completed")
            for t in pending:
                cat = t['category'] or 'general'
                due = f" 📅 {t['due_date']}" if t['due_date'] else ""
                lines.append(f"- [ ] {t['title']} ({cat}){due}")
            lines.append("")

        if not completed and not pending:
            lines.append("- No task activity recorded.")
            lines.append("")

        # --- Events ---
        lines.append("## 📅 Events")
        lines.append("")
        if events:
            for ev in events:
                time_str = ev['start_time'].split(' ')[1][:5] if ' ' in ev['start_time'] else "All Day"
                src = "Google" if ev['source'] == 'google' else "Local"
                lines.append(f"- **{time_str}** ({src}): {ev['title']} — *{ev['description'] or 'No description'}*")
        else:
            lines.append("- No events scheduled or recorded.")
        lines.append("")

        # --- Habits ---
        habits_done = sum(1 for h in yesterday_habits if h['completed'] == 1)
        habits_total = len(yesterday_habits)
        lines.append(f"## 🔄 Habits ({habits_done}/{habits_total} completed)")
        lines.append("")

        if yesterday_habits:
            default_habits = ['Code 1 Hour', 'Read 10 pages', 'Workout', 'Drink 3L Water', 'Sleep 8 hours']
            logged_names = {h['habit_name']: h['completed'] for h in yesterday_habits}
            for habit_name in default_habits:
                comp = logged_names.get(habit_name)
                if comp is not None:
                    check = "x" if comp == 1 else " "
                    lines.append(f"- [{check}] {habit_name}")
                else:
                    lines.append(f"- [ ] {habit_name} *(not logged)*")
            for h in yesterday_habits:
                if h['habit_name'] not in default_habits:
                    check = "x" if h['completed'] == 1 else " "
                    lines.append(f"- [{check}] {h['habit_name']}")
        else:
            lines.append("- No habits logged.")
        lines.append("")

        # --- Inbox Activity ---
        lines.append(f"## 📥 Inbox Processing ({len(inbox_processed)} files)")
        lines.append("")
        if inbox_processed:
            for f in inbox_processed:
                lines.append(f"- **{f['original_name']}** → {f['category']} ({f['description'] or 'no description'})")
        else:
            lines.append("- No files processed from inbox.")
        lines.append("")

        # --- Fitness ---
        lines.append("## 🏃 Fitness")
        lines.append("")
        if fitness_yesterday:
            for w in fitness_yesterday:
                dist = f" — {w['distance_km']} km" if w['distance_km'] else ""
                cals = f" — {w['calories_burned']} cal" if w['calories_burned'] else ""
                lines.append(f"- **{w['activity_type'].capitalize()}**: {w['duration_minutes']} mins{dist}{cals}")
                if w['notes']:
                    lines.append(f"  - {w['notes']}")
        else:
            lines.append("- No workout logged.")
        lines.append("")

        # --- Health ---
        lines.append("## ❤️ Health")
        lines.append("")
        if health_yesterday:
            w = f"- Weight: {health_yesterday['weight_lbs']} lbs" if health_yesterday['weight_lbs'] else ""
            s = f"- Sleep: {health_yesterday['sleep_hours']} hours" if health_yesterday['sleep_hours'] else ""
            m = f"- Mood: {health_yesterday['mood']}" if health_yesterday['mood'] else ""
            bp = ""
            if health_yesterday['systolic'] and health_yesterday['diastolic']:
                bp = f"- Blood Pressure: {health_yesterday['systolic']}/{health_yesterday['diastolic']}"
            lines.append(w) if w else None
            lines.append(s) if s else None
            lines.append(m) if m else None
            lines.append(bp) if bp else None
            if not any([w, s, m, bp]):
                lines.append("- No health metrics logged.")
        else:
            lines.append("- No health metrics logged.")
        lines.append("")

        # --- Finances ---
        lines.append("## 💰 Finances")
        lines.append("")
        if transactions_yesterday:
            lines.append("| Merchant | Category | Type | Amount |")
            lines.append("| --- | --- | --- | --- |")
            for tx in transactions_yesterday:
                sign = "+" if tx['type'] == 'income' else "-"
                lines.append(f"| {tx['merchant'] or 'N/A'} | {tx['category']} | {tx['type']} | {sign}${tx['amount']:.2f} |")
            total_spent = sum(tx['amount'] for tx in transactions_yesterday if tx['type'] == 'expense')
            total_income = sum(tx['amount'] for tx in transactions_yesterday if tx['type'] == 'income')
            lines.append("")
            lines.append(f"**Total spent:** ${total_spent:.2f}  |  **Total income:** ${total_income:.2f}")
        else:
            lines.append("- No transactions logged.")
        lines.append("")

        # --- Learning ---
        lines.append("## 📚 Learning")
        lines.append("")
        if learning_yesterday:
            for l in learning_yesterday:
                status = "✓" if l['status'] == 'completed' else "⏳"
                lines.append(f"- {status} **{l['topic']}** ({l['category']}) — {l['hours_spent']} hrs")
                if l['notes']:
                    lines.append(f"  - {l['notes']}")
        else:
            lines.append("- No study sessions logged.")
        lines.append("")

        # --- Career ---
        lines.append("## 💼 Career")
        lines.append("")
        if career_yesterday:
            for j in career_yesterday:
                lines.append(f"- **{j['company']}** — {j['role']} ({j['status']})")
                if j['notes']:
                    lines.append(f"  - {j['notes']}")
        else:
            lines.append("- No job applications logged.")
        lines.append("")

        # --- Write the summary ---
        summary_path = os.path.join(VAULT_DIR, "04_Archives", f"Daily_Summary_{target_date}.md")
        write_file_atomically(summary_path, "\n".join(lines) + "\n")
        print(f"Archived daily summary to {summary_path}")

    except Exception as e:
        print(f"Error generating daily summary: {e}")
        raise e
    finally:
        conn.close()

    # ---- Delete the Daily Brief for this date ----
    brief_path = os.path.join(VAULT_DIR, "Daily_Briefs", f"Daily_Brief_{target_date}.md")
    if os.path.exists(brief_path):
        try:
            os.remove(brief_path)
            print(f"Deleted old daily brief: {brief_path}")
        except OSError as e:
            print(f"Could not delete old brief {brief_path}: {e}")


def cleanup_old_completed_tasks(days=3):
    """
    Remove completed tasks older than `days` days from both the database and their source files.
    """
    print(f"\nCleaning up completed tasks older than {days} days...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        threshold = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("SELECT id, title, source_file FROM tasks WHERE status = 'completed' AND completed_at < ?", (threshold,))
        old_tasks = cursor.fetchall()
        
        if not old_tasks:
            print("No old completed tasks to clean up.")
            return
            
        print(f"Found {len(old_tasks)} old completed tasks to remove.")
        
        # Group tasks by source file to minimize file operations
        tasks_by_file = {}
        for task in old_tasks:
            src_file = task['source_file']
            if src_file:
                if src_file not in tasks_by_file:
                    tasks_by_file[src_file] = []
                tasks_by_file[src_file].append(task['title'])
            else:
                # Task has no source file (created in DB directly), just delete from DB
                cursor.execute("DELETE FROM tasks WHERE id = ?", (task['id'],))
                
        # Regex and patterns for task matching
        task_pattern = re.compile(r'^\s*-\s*\[([xX])\]\s*(.+)$')
        due_date_pattern = re.compile(r'📅\s*(\d{4}-\d{2}-\d{2})')
        importance_pattern = re.compile(r'#major\b|#minor\b', re.IGNORECASE)
        priority_pattern = re.compile(r'#high\b|#p1\b|#medium\b|#p2\b|#low\b|#p3\b', re.IGNORECASE)

        for src_file, titles in tasks_by_file.items():
            if not src_file or src_file == "tasks.md":
                # Clean up from DB (since they don't reside in human-authored files)
                for title in titles:
                    cursor.execute("DELETE FROM tasks WHERE (source_file IS NULL OR source_file = '' OR source_file = 'tasks.md') AND title = ?", (title,))
            else:
                # For human-authored files, we preserve completed tasks to keep history
                # of both note content and database telemetry records.
                print(f"Preserving completed task in human-authored file: {src_file}")
                
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error in cleanup_old_completed_tasks: {e}")
    finally:
        conn.close()


def run_agent_sync():
    """
    Run full synchronization routine.
    """
    print("=== STARTING FULL ATHENA AGENT SYNC ===")

    # 1. Process inbox files
    process_inbox()

    # 1.2. Run career job discovery & tailoring engine
    try:
        import job_discovery_engine
        import job_tailor_engine
        print("\nRunning Automated Career Job Discovery & Tailoring Engine...")
        job_discovery_engine.run_discovery_pipeline()
        job_tailor_engine.batch_tailor_top_leads(5)
    except Exception as e:
        print(f"Error running job discovery in agent sync: {e}")

    # 1.5. Clean up completed tasks older than 3 days
    cleanup_old_completed_tasks(days=3)

    # 2. Sync tasks from notes
    print("\nScanning vault notes for tasks...")
    scanned_tasks = scan_vault_for_tasks()
    print(f"Found {len(scanned_tasks)} tasks in vault notes. Reconciling with database...")
    reconcile_tasks_in_db(scanned_tasks)

    # 3. Sync local calendar events

    print("\nParsing local calendar.ics...")
    sync_local_ics_to_db()

    # 4. Sync Google Calendar
    print("\nSyncing Google Calendar...")
    sync_google_calendar_to_db()

    # 5. Write back active tasks to tasks.md
    print("\nWriting back active tasks to tasks.md...")
    sync_db_to_tasks_md_helper()

    # 6. Generate Daily Brief (for today)
    print("\nGenerating Daily Brief...")
    generate_daily_brief()

    # 7. Generate Daily Summary (archive yesterday, delete old brief)
    print("\nGenerating Daily Summary for yesterday...")
    generate_daily_summary()

    # 8. Generate Summaries
    print("\nRegenerating summaries...")
    generate_obsidian_summaries()

    print("\n=== ATHENA AGENT SYNC COMPLETED ===")

if __name__ == "__main__":
    run_agent_sync()
