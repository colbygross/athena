#!/usr/bin/env python3
import os
import sys
import time
import argparse
import sqlite3
from datetime import datetime
from playwright.sync_api import sync_playwright

DB_PATH = os.path.join(os.path.dirname(__file__), "life_dashboard.db")
CONTEXT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "playwright_context")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def setup_login():
    """Launches headful browser for the user to log in and save cookies."""
    print("==================================================================")
    print(" Athena OS: Career Breach Playwright Login Setup                  ")
    print("==================================================================")
    print(f"Using persistent browser context in: {CONTEXT_DIR}")
    print("We will open LinkedIn, Indeed, and Handshake in a headful browser.")
    print("Please log into each site in the browser window.")
    print("Once you are logged in, return to this terminal and press ENTER.")
    print("==================================================================")

    os.makedirs(os.path.dirname(CONTEXT_DIR), exist_ok=True)
    
    with sync_playwright() as p:
        # Launch headful browser with large window
        context = p.chromium.launch_persistent_context(
            user_data_dir=CONTEXT_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        
        # Open LinkedIn
        page = context.new_page()
        try:
            page.goto("https://www.linkedin.com/login", timeout=30000)
            print("Opened LinkedIn login page.")
        except Exception as e:
            print(f"Could not load LinkedIn: {e}")
            
        # Open Indeed
        page2 = context.new_page()
        try:
            page2.goto("https://www.indeed.com", timeout=30000)
            print("Opened Indeed home page.")
        except Exception as e:
            print(f"Could not load Indeed: {e}")

        # Open Handshake
        page3 = context.new_page()
        try:
            page3.goto("https://app.joinhandshake.com/login", timeout=30000)
            print("Opened Handshake login page.")
        except Exception as e:
            print(f"Could not load Handshake: {e}")

        input("\nPress ENTER when you have successfully logged in and are ready to save the session... ")
        context.close()
        print("Session saved successfully!")

def scrape_linkedin(page, keyword, location):
    """Scrapes jobs from LinkedIn using search keywords."""
    print(f"Searching LinkedIn for '{keyword}' in '{location}'...")
    url = f"https://www.linkedin.com/jobs/search/?keywords={keyword}&location={location}"
    try:
        page.goto(url, timeout=45000)
        page.wait_for_timeout(3000) # Give it time to load
    except Exception as e:
        print(f"Failed to load LinkedIn search: {e}")
        return []

    jobs = []
    try:
        # Scroll job list to load more items
        for _ in range(3):
            page.evaluate("document.querySelector('.jobs-search-results-list')?.scrollBy(0, 500)")
            page.wait_for_timeout(1000)
            
        # Select job cards
        cards = page.query_selector_all(".jobs-search-results__list-item, .job-card-container")
        print(f"Found {len(cards)} LinkedIn job cards on page.")
        
        for i, card in enumerate(cards[:15]): # Limit to first 15 jobs to be polite and save time
            try:
                # Find title and link
                link_elem = card.query_selector("a.job-card-list__title, a.job-card-container__link, .disabled.artdeco-entity-lockup__title a")
                if not link_elem:
                    continue
                
                title = link_elem.inner_text().strip()
                job_url = link_elem.get_attribute("href")
                if not job_url:
                    continue
                    
                # Standardize link to clean out tracker params
                if "?" in job_url:
                    job_url = job_url.split("?")[0]
                if not job_url.startswith("http"):
                    job_url = "https://www.linkedin.com" + job_url

                # Company
                comp_elem = card.query_selector("span.job-card-container__primary-description, .artdeco-entity-lockup__subtitle")
                company = comp_elem.inner_text().strip() if comp_elem else "Unknown Company"

                # Location
                loc_elem = card.query_selector(".job-card-container__metadata-item, .artdeco-entity-lockup__caption")
                loc = loc_elem.inner_text().strip() if loc_elem else location

                # Click to fetch description if possible, or navigate directly in a new page later
                # We'll fetch the description by loading the clean URL in a new page to keep scraping simple and robust
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": loc,
                    "url": job_url,
                    "source": "linkedin"
                })
            except Exception as card_err:
                print(f"Error parsing LinkedIn job card: {card_err}")
    except Exception as e:
        print(f"Error scraping LinkedIn search: {e}")
        
    return jobs

def scrape_indeed(page, keyword, location):
    """Scrapes jobs from Indeed using search keywords."""
    print(f"Searching Indeed for '{keyword}' in '{location}'...")
    url = f"https://www.indeed.com/jobs?q={keyword}&l={location}"
    try:
        page.goto(url, timeout=45000)
        page.wait_for_timeout(3000)
    except Exception as e:
        print(f"Failed to load Indeed search: {e}")
        return []

    jobs = []
    try:
        # Check for Cloudflare / captcha
        if "hcaptcha" in page.content().lower() or "cloudflare" in page.content().lower():
            print("WARNING: Indeed page triggered Cloudflare / Captcha. Please run with --login to resolve or solve captcha manually.")
            
        cards = page.query_selector_all(".job_seen_beacon")
        print(f"Found {len(cards)} Indeed job cards.")
        
        for card in cards[:15]:
            try:
                title_elem = card.query_selector("h2.jobTitle span, a.jcs-JobDetails span")
                link_elem = card.query_selector("a.jcs-JobDetails, h2.jobTitle a")
                if not title_elem or not link_elem:
                    continue
                    
                title = title_elem.inner_text().strip()
                job_url = link_elem.get_attribute("href")
                if not job_url:
                    continue
                    
                if "?" in job_url:
                    job_url = job_url.split("?")[0]
                if not job_url.startswith("http"):
                    job_url = "https://www.indeed.com" + job_url

                # Company
                comp_elem = card.query_selector("[data-testid='company-name']")
                company = comp_elem.inner_text().strip() if comp_elem else "Unknown Company"

                # Location
                loc_elem = card.query_selector("[data-testid='text-location']")
                loc = loc_elem.inner_text().strip() if loc_elem else location

                jobs.append({
                    "title": title,
                    "company": company,
                    "location": loc,
                    "url": job_url,
                    "source": "indeed"
                })
            except Exception as card_err:
                print(f"Error parsing Indeed job card: {card_err}")
    except Exception as e:
        print(f"Error scraping Indeed: {e}")
        
    return jobs

def scrape_handshake(page, keyword):
    """Scrapes jobs from Handshake Student dashboard."""
    print(f"Searching Handshake for '{keyword}'...")
    url = f"https://app.joinhandshake.com/stu/jobs?query={keyword}"
    try:
        page.goto(url, timeout=45000)
        page.wait_for_timeout(3000)
    except Exception as e:
        print(f"Failed to load Handshake jobs: {e}")
        return []

    jobs = []
    try:
        # Check login state
        if "login" in page.url:
            print("WARNING: Handshake is logged out. Please run with --login to log in first.")
            return []

        # Find anchors containing "/jobs/"
        links = page.query_selector_all("a")
        seen_urls = set()
        
        for link in links:
            try:
                href = link.get_attribute("href")
                if href and ("/jobs/" in href or "/stu/jobs/" in href):
                    # Extract job id
                    job_id = None
                    parts = href.split("/")
                    for idx, part in enumerate(parts):
                        if part in ["jobs", "stu"]:
                            # Next or next-next might be id
                            for offset in [1, 2]:
                                if idx + offset < len(parts) and parts[idx+offset].isdigit():
                                    job_id = parts[idx+offset]
                                    break
                        if job_id:
                            break
                    
                    if not job_id:
                        continue
                        
                    clean_url = f"https://app.joinhandshake.com/jobs/{job_id}"
                    if clean_url in seen_urls:
                        continue
                    seen_urls.add(clean_url)
                    
                    # Read link text as a starting point
                    text = link.inner_text().strip()
                    if len(text) < 3 or "\n" in text:
                        # Try to find text structure inside the link
                        title_elem = link.query_selector("span, h3, div")
                        title = title_elem.inner_text().strip() if title_elem else "Handshake Listing"
                    else:
                        title = text
                        
                    jobs.append({
                        "title": title,
                        "company": "Handshake Recruiter",
                        "location": "Remote / Onsite",
                        "url": clean_url,
                        "source": "handshake"
                    })
            except Exception:
                continue
    except Exception as e:
        print(f"Error scraping Handshake: {e}")
        
    return jobs

def fetch_job_description(page, url, source):
    """Loads a specific job page and extracts its full description text."""
    try:
        page.goto(url, timeout=30000)
        page.wait_for_timeout(2000)
        
        # Source-specific selectors for full text
        description = ""
        if source == "linkedin":
            selectors = [
                "article.jobs-description__content",
                ".jobs-box__html-content",
                "#job-details"
            ]
        elif source == "indeed":
            selectors = [
                "#jobDescriptionText",
                ".jobsearch-jobDescriptionText"
            ]
        elif source == "handshake":
            selectors = [
                "[data-hook='job-description']",
                ".job-description-class", # backup
                ".description"
            ]
        else:
            selectors = ["body"]

        for sel in selectors:
            elem = page.query_selector(sel)
            if elem:
                description = elem.inner_text().strip()
                break
                
        if not description:
            # Fallback: get raw body text
            description = page.locator("body").inner_text().strip()[:2000] # Limit size
            
        return description
    except Exception as e:
        print(f"Failed to fetch description for {url}: {e}")
        return ""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--login", action="store_true", help="Open headful browser to log in")
    parser.add_argument("--profile-id", type=int, help="Limit scrape to a specific search profile ID")
    args = parser.parse_args()

    if args.login:
        setup_login()
        return

    # Load active profiles from DB
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM career_search_profiles WHERE active = 1"
    params = []
    if args.profile_id:
        query += " AND id = ?"
        params.append(args.profile_id)
        
    cursor.execute(query, params)
    profiles = cursor.fetchall()
    
    if not profiles:
        print("No active career search profiles found in database. Please configure them in the dashboard.")
        conn.close()
        return

    print(f"Loaded {len(profiles)} active search profiles.")
    
    # Initialize Playwright in headless mode
    with sync_playwright() as p:
        if not os.path.exists(CONTEXT_DIR):
            print(f"Persistent browser context not found at: {CONTEXT_DIR}")
            print("Please run this script with --login first to log in and save cookies.")
            conn.close()
            return
            
        print("Launching background browser context...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=CONTEXT_DIR,
            headless=True,
            viewport={"width": 1280, "height": 800},
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = context.new_page()

        for prof in profiles:
            print(f"\nProcessing search profile: {prof['name']}")
            keywords = [kw.strip() for kw in prof['keywords'].split(",") if kw.strip()]
            locations = [loc.strip() for loc in prof['locations'].split(",") if loc.strip()]
            
            all_leads = []
            for kw in keywords:
                for loc in locations:
                    # Scrape LinkedIn
                    try:
                        li_jobs = scrape_linkedin(page, kw, loc)
                        for j in li_jobs:
                            j["profile_id"] = prof["id"]
                            all_leads.append(j)
                    except Exception as e:
                        print(f"LinkedIn scraping failed: {e}")
                        
                    # Scrape Indeed
                    try:
                        ind_jobs = scrape_indeed(page, kw, loc)
                        for j in ind_jobs:
                            j["profile_id"] = prof["id"]
                            all_leads.append(j)
                    except Exception as e:
                        print(f"Indeed scraping failed: {e}")

                # Scrape Handshake (usually locations are handled inside keywords/filters in portal)
                try:
                    hs_jobs = scrape_handshake(page, kw)
                    for j in hs_jobs:
                        j["profile_id"] = prof["id"]
                        all_leads.append(j)
                except Exception as e:
                    print(f"Handshake scraping failed: {e}")

            # Now process the gathered leads and fetch descriptions for new ones
            print(f"\nGathered {len(all_leads)} total lead opportunities for profile. Filtering duplicates...")
            
            new_leads_added = 0
            for lead in all_leads:
                # Check if URL exists in DB
                cursor.execute("SELECT id FROM job_leads WHERE job_url = ?", (lead["url"],))
                exist_lead = cursor.fetchone()
                
                cursor.execute("SELECT id FROM job_applications WHERE job_description_url = ?", (lead["url"],))
                exist_app = cursor.fetchone()
                
                if exist_lead or exist_app:
                    continue
                
                # Fetch full description
                print(f"Fetching description for new lead: {lead['title']} at {lead['company']} ({lead['source']})")
                desc = fetch_job_description(page, lead["url"], lead["source"])
                lead["job_description"] = desc or "No description details fetched."
                
                # Insert into DB
                today = datetime.now().strftime("%Y-%m-%d")
                try:
                    cursor.execute("""
                        INSERT INTO job_leads (date_found, company, role, location, salary_range, job_description, job_url, source, status, profile_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'lead', ?)
                    """, (
                        today,
                        lead["company"],
                        lead["title"],
                        lead["location"],
                        "", # Salary unknown on search list
                        lead["job_description"],
                        lead["url"],
                        lead["source"],
                        lead["profile_id"]
                    ))
                    conn.commit()
                    new_leads_added += 1
                except Exception as db_err:
                    print(f"Database insert error: {db_err}")
                    conn.rollback()
                    
            print(f"Completed profile. Added {new_leads_added} new job leads to the database.")

        context.close()
    conn.close()
    print("\nAthena OS job scraping run completed.")

if __name__ == "__main__":
    main()
