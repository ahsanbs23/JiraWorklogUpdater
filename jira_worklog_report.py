import argparse
import csv
import os
import sys
from datetime import datetime, time, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

# ================= CONFIG =================
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
EMAIL = os.getenv("EMAIL")
API_TOKEN = os.getenv("API_TOKEN")
LOCAL_TIMEZONE_OFFSET = int(os.getenv("LOCAL_TIMEZONE_OFFSET", 6))
# Custom field holding the client reference; looked up by name if not set
CLIENT_REF_FIELD_NAME = os.getenv("CLIENT_REF_FIELD_NAME", "Client Reference")
CLIENT_REF_FIELD_ID = os.getenv("CLIENT_REF_FIELD_ID")
# Report settings
REPORT_EMAILS = os.getenv("REPORT_EMAILS", "")        # comma-separated emails
REPORT_START_DATE = os.getenv("REPORT_START_DATE")    # YYYY-MM-DD (inclusive)
REPORT_END_DATE = os.getenv("REPORT_END_DATE")        # YYYY-MM-DD (inclusive)
REPORT_OUTPUT_PATH = os.getenv("REPORT_OUTPUT_PATH")  # optional
# ==========================================

auth = (EMAIL, API_TOKEN)
headers = {"Accept": "application/json", "Content-Type": "application/json"}
local_tz = timezone(timedelta(hours=LOCAL_TIMEZONE_OFFSET))


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def resolve_account_id(person):
    """Accept an accountId directly, or look one up by email / display name."""
    if len(person) >= 20 and not any(c in person for c in " @"):
        return person, person

    r = requests.get(f"{JIRA_BASE_URL}/rest/api/3/user/search",
                     params={"query": person}, headers=headers, auth=auth)
    r.raise_for_status()
    users = r.json()
    if not users:
        sys.exit(f"❌ No Jira user found for '{person}'")
    if len(users) > 1:
        print(f"⚠️ Multiple users match '{person}', using the first:")
        for u in users:
            print(f"   - {u.get('displayName')} ({u.get('emailAddress', 'email hidden')}) {u['accountId']}")
    return users[0]["accountId"], users[0].get("displayName", person)


def get_client_ref_field_id():
    if CLIENT_REF_FIELD_ID:
        return CLIENT_REF_FIELD_ID
    r = requests.get(f"{JIRA_BASE_URL}/rest/api/3/field", headers=headers, auth=auth)
    r.raise_for_status()
    for f in r.json():
        if f["name"].lower() == CLIENT_REF_FIELD_NAME.lower():
            return f["id"]
    print(f"⚠️ Field '{CLIENT_REF_FIELD_NAME}' not found; client reference will be blank")
    return None


def adf_to_text(node):
    """Flatten a Jira rich-text (ADF) comment to plain text."""
    if not node:
        return ""
    if isinstance(node, str):
        return node
    if node.get("type") == "text":
        return node.get("text", "")
    parts = [adf_to_text(c) for c in node.get("content", [])]
    sep = " | " if node.get("type") == "doc" else " "
    return sep.join(p for p in parts if p).strip()


def find_issues(account_id, start_date, end_date, ref_field):
    """Issues with worklogs by this user near the range (padded a day for timezone slack)."""
    jql = (f'worklogAuthor = "{account_id}" '
           f'AND worklogDate >= "{start_date - timedelta(days=1)}" '
           f'AND worklogDate <= "{end_date + timedelta(days=1)}"')
    keys, token = [], None
    while True:
        body = {"jql": jql, "fields": ["components"] + ([ref_field] if ref_field else []), "maxResults": 100}
        if token:
            body["nextPageToken"] = token
        r = requests.post(f"{JIRA_BASE_URL}/rest/api/3/search/jql", json=body, headers=headers, auth=auth)
        r.raise_for_status()
        data = r.json()
        keys += [(i["key"],
                  (i["fields"].get(ref_field) or "") if ref_field else "",
                  ", ".join(c["name"] for c in i["fields"].get("components") or []))
                 for i in data["issues"]]
        token = data.get("nextPageToken")
        if not token:
            return keys


def get_worklogs(issue_key):
    start_at = 0
    while True:
        r = requests.get(f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/worklog",
                         params={"startAt": start_at, "maxResults": 1000}, headers=headers, auth=auth)
        r.raise_for_status()
        data = r.json()
        yield from data["worklogs"]
        start_at += len(data["worklogs"])
        if not data["worklogs"] or start_at >= data["total"]:
            return


def parse_started(value):
    # Jira returns e.g. 2026-01-15T09:00:00.000+0600
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")


def main():
    p = argparse.ArgumentParser(description="Generate a worklog CSV for people in a date range. "
                                            "Settings come from .env; flags override them.")
    p.add_argument("--emails", default=REPORT_EMAILS, help="Comma-separated emails (REPORT_EMAILS)")
    p.add_argument("--start", default=REPORT_START_DATE, help="Start date YYYY-MM-DD (REPORT_START_DATE)")
    p.add_argument("--end", default=REPORT_END_DATE, help="End date YYYY-MM-DD (REPORT_END_DATE)")
    p.add_argument("-o", "--output", default=REPORT_OUTPUT_PATH,
                   help="Output CSV path (REPORT_OUTPUT_PATH; default: worklog_report_<start>_<end>.csv)")
    args = p.parse_args()

    people = [e.strip() for e in args.emails.split(",") if e.strip()]
    if not people:
        sys.exit("❌ No people given: set REPORT_EMAILS in .env (or pass --emails)")
    if not args.start or not args.end:
        sys.exit("❌ Set REPORT_START_DATE and REPORT_END_DATE in .env (or pass --start/--end)")
    try:
        start, end = parse_date(args.start), parse_date(args.end)
    except ValueError:
        sys.exit("❌ Dates must be in YYYY-MM-DD format")
    if end < start:
        sys.exit("❌ End date is before start date")

    range_start = datetime.combine(start, time.min, tzinfo=local_tz)
    range_end = datetime.combine(end + timedelta(days=1), time.min, tzinfo=local_tz)
    ref_field = get_client_ref_field_id()

    rows = []  # (date, started, name, issue key, description, hours, client ref, components)
    for person in people:
        account_id, name = resolve_account_id(person)
        count = 0
        for key, client_ref, components in find_issues(account_id, start, end, ref_field):
            for wl in get_worklogs(key):
                if wl["author"]["accountId"] != account_id:
                    continue
                started = parse_started(wl["started"])
                if not (range_start <= started < range_end):
                    continue
                rows.append((started.astimezone(local_tz).date(), started, name, key,
                             adf_to_text(wl.get("comment")), wl["timeSpentSeconds"] / 3600,
                             client_ref, components))
                count += 1
        print(f"👤 {name}: {count} worklogs")

    rows.sort(key=lambda r: (r[2], r[0], r[1], r[3]))

    # Same columns/date format as the uploader's input CSV, plus extra columns
    output = args.output or f"worklog_report_{start}_{end}.csv"
    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Task Key", "What did you do?", "Duration (hours)",
                         "Client Reference", "Components", "Logged By"])
        for day, _, name, key, desc, hours, client_ref, components in rows:
            writer.writerow([f"{day.month}/{day.day}/{day.year}", key, desc, f"{hours:g}",
                             client_ref, components, name])

    print(f"✅ {len(rows)} worklogs written to {output} (total {sum(r[5] for r in rows):.2f}h)")


if __name__ == "__main__":
    main()
