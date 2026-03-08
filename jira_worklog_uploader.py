import csv
import os
import requests
from datetime import datetime, timedelta, time, timezone, timedelta
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ================= CONFIG =================
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
EMAIL = os.getenv("EMAIL")
API_TOKEN = os.getenv("API_TOKEN")
CSV_FILE_PATH = os.getenv("CSV_FILE_PATH")
LOCAL_TIMEZONE_OFFSET = int(os.getenv("LOCAL_TIMEZONE_OFFSET", 6))
# ==========================================

auth = (EMAIL, API_TOKEN)
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def to_seconds(hours):
    return int(float(hours) * 3600)

def to_jira_timestamp(dt):
    """Convert datetime to ISO 8601 format string that Jira expects: yyyy-MM-dd'T'HH:mm:ss.SSSZ"""
    # Format: 2021-01-17T12:34:00.000+0000
    return dt.strftime('%Y-%m-%dT%H:%M:%S.000%z')

def get_start_time_local_to_utc(date_obj):
    """
    Create a 9 AM start time in local timezone (GMT+6), then convert to UTC
    date_obj: a date object in local timezone
    """
    local_tz = timezone(timedelta(hours=LOCAL_TIMEZONE_OFFSET))
    # Create 9 AM in local timezone
    local_dt = datetime.combine(date_obj, time(9, 0), tzinfo=local_tz)
    return local_dt

def add_worklog(issue_key, started_dt, seconds, comment):
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/worklog"

    payload = {
        "started": to_jira_timestamp(started_dt),
        "timeSpentSeconds": seconds,
        "comment": {
            "type": "doc",
            "version": 1,
            "content": [{
                "type": "paragraph",
                "content": [{"type": "text", "text": comment}]
            }]
        }
    }

    r = requests.post(url, json=payload, headers=headers, auth=auth)

    if r.status_code == 201:
        print(f"✅ {issue_key} - {seconds/3600:.1f}h logged")
    else:
        print(f"❌ {issue_key} failed: {r.text}")

with open(CSV_FILE_PATH, newline='', encoding='utf-8-sig') as csvfile:
    reader = csv.DictReader(csvfile)
    rows = list(reader)
    
    # Sort by date with error handling
    try:
        rows = sorted(rows, key=lambda r: datetime.strptime(r["Date"].strip(), "%m/%d/%Y"))
    except ValueError as e:
        print(f"⚠️ Date parsing failed. Checking date format...")
        # Print first few date values to help debug
        for i, row in enumerate(rows[:3]):
            print(f"   Row {i+1} Date: '{row['Date']}'")
        print(f"Expected format: MM-DD-YYYY (e.g., 01-15-2026)")
        raise

    total_hours = 0
    for row in rows:
        try:
            date_obj = datetime.strptime(row["Date"].strip(), "%m/%d/%Y").date()
            issue_key = row["Task Key"].strip()
            description = row["What did you do?"].strip()
            duration = row["Duration (hours)"]

            if not issue_key or not duration:
                continue

            total_hours += float(duration)
            seconds = to_seconds(duration)
            start_time = get_start_time_local_to_utc(date_obj)

            add_worklog(issue_key, start_time, seconds, description)

        except Exception as e:
            print(f"⚠️ Skipped row: {e}")
    
    print(f"\n📊 Total hours logged: {total_hours:.1f}h")
