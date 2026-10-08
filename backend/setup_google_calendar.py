#!/usr/bin/env python3
"""
ATHENA - Google Calendar Integration Setup Assistant
This script guides you through authenticating Google Calendar with ATHENA.
"""

import os
import sys
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

STORAGE_DIR = os.path.join(BASE_DIR, "storage")
os.makedirs(STORAGE_DIR, exist_ok=True)

GOOGLE_CALENDAR_SCOPES = ['https://www.googleapis.com/auth/calendar']

def find_credentials_file():
    candidates = [
        os.path.join(STORAGE_DIR, "credentials.json"),
        os.path.join(BASE_DIR, "credentials.json"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def main():
    print("=" * 65)
    print("        ATHENA - Google Calendar Setup Assistant")
    print("=" * 65)
    print()

    creds_path = find_credentials_file()
    token_path = os.path.join(STORAGE_DIR, "token.json")

    if not creds_path:
        print("❌ 'credentials.json' was not found.")
        print()
        print("Please place your downloaded client secrets JSON in:")
        print(f"   📁 {os.path.join(STORAGE_DIR, 'credentials.json')}")
        print("or:")
        print(f"   📁 {os.path.join(BASE_DIR, 'credentials.json')}")
        print("=" * 65)
        sys.exit(1)

    print(f"✅ Found credentials file at:")
    print(f"   {creds_path}")
    print()

    creds = None
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, GOOGLE_CALENDAR_SCOPES)
            if creds.valid:
                print(f"✅ Valid existing token found at: {token_path}")
            elif creds.expired and creds.refresh_token:
                print("🔄 Refreshing existing token...")
                creds.refresh(Request())
                print("✅ Token refreshed successfully!")
            else:
                creds = None
        except Exception as e:
            print(f"Existing token could not be used: {e}")
            creds = None

    if not creds or not creds.valid:
        print("Initiating Google OAuth authentication...")
        flow = InstalledAppFlow.from_client_secrets_file(creds_path, GOOGLE_CALENDAR_SCOPES)

        try:
            # Try running local server with dynamic available port
            print("Starting local authorization server...")
            creds = flow.run_local_server(
                port=0,
                open_browser=True,
                authorization_prompt_message=(
                    "\n👉 Open this URL in your browser to authorize ATHENA:\n\n{url}\n\n"
                    "Note: If Google displays 'Google hasn't verified this app',\n"
                    "click 'Advanced' -> 'Go to ATHENA (unsafe)' -> 'Continue'.\n"
                ),
                timeout_seconds=120
            )
        except Exception as e:
            print(f"\n⚠️  Local browser listener timed out or encountered an issue: {e}")
            print("Switching to manual redirect URL input...")
            
            # Manual fallback
            auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
            print("\n" + "=" * 65)
            print("1. Open this URL in ANY browser (on your phone, laptop, or desktop):")
            print(f"\n{auth_url}\n")
            print("2. Log in and approve calendar access.")
            print("3. Your browser will try to redirect to an address like:")
            print("   http://localhost:XXXXX/?code=4/0A...&scope=...")
            print("   (Even if the page says 'Unable to connect', that's fine!)")
            print("4. Copy that full redirect URL from your browser's address bar and paste it below:")
            print("=" * 65)
            
            user_input = input("\nPaste the full redirect URL or the 'code' parameter here: ").strip()
            if not user_input:
                print("❌ No input received. Aborting.")
                sys.exit(1)
            
            # Extract code if full URL was pasted
            if "code=" in user_input:
                parsed = parse_qs(urlparse(user_input).query)
                auth_code = parsed.get("code", [user_input])[0]
            else:
                auth_code = user_input
            
            flow.fetch_token(code=auth_code)
            creds = flow.credentials

        # Save tokens
        with open(token_path, "w") as token_file:
            token_file.write(creds.to_json())
        print(f"\n✅ Authorization token saved to: {token_path}")
        
        # Also mirror to root token.json
        root_token = os.path.join(BASE_DIR, "token.json")
        try:
            with open(root_token, "w") as rf:
                rf.write(creds.to_json())
        except Exception:
            pass

    print()
    print("Testing connection to Google Calendar API...")
    try:
        service = build('calendar', 'v3', credentials=creds)
        cal = service.calendars().get(calendarId='primary').execute()
        cal_name = cal.get('summary', 'Primary Calendar')
        cal_id = cal.get('id', 'primary')
        print(f"✅ Successfully connected to: {cal_name} ({cal_id})")

        # Fetch upcoming events
        now = datetime.utcnow().isoformat() + 'Z'
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=5,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        print(f"\nFound {len(events)} upcoming events on Google Calendar:")
        for ev in events:
            start = ev.get('start', {}).get('dateTime', ev.get('start', {}).get('date'))
            title = ev.get('summary', 'Untitled Event')
            print(f"  📅 {start[:16]} | {title}")

        print("\nSyncing events into ATHENA local database...")
        try:
            from backend import agent
            agent.sync_google_calendar_to_db()
            print("✅ Initial sync complete! Events imported into ATHENA.")
        except Exception as e:
            print(f"Local sync note: {e}")

        print()
        print("=" * 65)
        print("🎉 SUCCESS! Google Calendar is fully connected to ATHENA.")
        print("You can now click 'Google Sync' in the ATHENA Web UI anytime,")
        print("and events created with 'Sync to Google' will push automatically.")
        print("=" * 65)

    except Exception as e:
        print(f"❌ Error communicating with Google Calendar API: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
