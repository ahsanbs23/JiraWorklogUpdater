import argparse
import csv
import os
import re
import sys
from datetime import datetime, time, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

# ================= CONFIG =================
JIRA_BASE_URL = (os.getenv("JIRA_BASE_URL") or "").rstrip("/")
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


class JiraError(Exception):
    """A Jira/network problem with a message that is safe to show the user as-is."""


def _jira_detail(r):
    """Jira's own explanation of what went wrong, if the response has one."""
    try:
        data = r.json()
    except ValueError:
        return r.text.strip()[:300]
    if not isinstance(data, dict):
        return ""
    parts = list(data.get("errorMessages") or [])
    parts += [f"{k}: {v}" for k, v in (data.get("errors") or {}).items()]
    return "; ".join(parts) or data.get("message", "")


def jira(method, path, **kwargs):
    """Call the Jira REST API. Returns the response, or raises JiraError with the real reason."""
    try:
        r = requests.request(method, f"{JIRA_BASE_URL}{path}", headers=headers, auth=auth, timeout=60, **kwargs)
    except requests.exceptions.InvalidURL:
        raise JiraError(f"JIRA_BASE_URL is not a valid URL: '{JIRA_BASE_URL}'")
    except requests.exceptions.MissingSchema:
        raise JiraError(f"JIRA_BASE_URL must start with https:// (currently '{JIRA_BASE_URL}')")
    except requests.exceptions.ConnectionError as e:
        raise JiraError(f"Cannot connect to {JIRA_BASE_URL}. Check JIRA_BASE_URL and your internet connection. ({e})")
    except requests.exceptions.Timeout:
        raise JiraError(f"Jira did not respond in time for {path}. Try again, or use a smaller date range.")

    if r.ok:
        return r

    detail = _jira_detail(r)
    suffix = f" Jira said: {detail}" if detail else ""
    if r.status_code == 401:
        raise JiraError("Authentication failed (401): EMAIL or API_TOKEN in .env is wrong, expired or revoked." + suffix)
    if r.status_code == 403:
        raise JiraError(f"Permission denied (403) for {method} {path}: this account is not allowed to do that." + suffix)
    if r.status_code == 404:
        raise JiraError(f"Not found (404) for {method} {path}. Check JIRA_BASE_URL, and that the issue/user exists "
                        f"and you can see it." + suffix)
    if r.status_code == 429:
        raise JiraError(f"Jira rate limit hit (429). Wait {r.headers.get('Retry-After', 'a minute')}s and try again, "
                        f"or use fewer people / a smaller date range." + suffix)
    if r.status_code >= 500:
        raise JiraError(f"Jira server error ({r.status_code}) for {method} {path}. Try again later." + suffix)
    raise JiraError(f"Jira rejected the request ({r.status_code}) for {method} {path}." + suffix)


def check_credentials():
    """Fail early, with a clear message, if the .env settings can't log in. Returns the account's display name."""
    missing = [n for n, v in (("JIRA_BASE_URL", JIRA_BASE_URL), ("EMAIL", EMAIL), ("API_TOKEN", API_TOKEN)) if not v]
    if missing:
        raise JiraError(f"Missing {', '.join(missing)} in .env")
    me = jira("GET", "/rest/api/3/myself").json()
    if not me.get("accountId"):
        raise JiraError("Jira did not recognise this login (EMAIL / API_TOKEN in .env).")
    return me.get("displayName", EMAIL)


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def resolve_account_id(person):
    """Accept an accountId directly, or look one up by email / display name."""
    if len(person) >= 20 and not any(c in person for c in " @"):
        return person, person

    users = jira("GET", "/rest/api/3/user/search", params={"query": person}).json()
    if not users:
        raise JiraError(f"No Jira user found for '{person}'. If you used an email, the user may hide it in their "
                        f"Jira privacy settings: try their display name or accountId instead.")
    exact = [u for u in users if (u.get("emailAddress") or "").lower() == person.lower()]
    if exact:
        users = exact
    elif len(users) > 1:
        print(f"⚠️ Multiple users match '{person}', using the first:")
        for u in users:
            print(f"   - {u.get('displayName')} ({u.get('emailAddress', 'email hidden')}) {u['accountId']}")
    return users[0]["accountId"], users[0].get("displayName", person)


def get_client_ref_field_id():
    if CLIENT_REF_FIELD_ID:
        return CLIENT_REF_FIELD_ID
    for f in jira("GET", "/rest/api/3/field").json():
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
        data = jira("POST", "/rest/api/3/search/jql", json=body).json()
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
        data = jira("GET", f"/rest/api/3/issue/{issue_key}/worklog",
                    params={"startAt": start_at, "maxResults": 1000}).json()
        yield from data["worklogs"]
        start_at += len(data["worklogs"])
        if not data["worklogs"] or start_at >= data["total"]:
            return


def parse_started(value):
    # Jira returns e.g. 2026-01-15T09:00:00.000+0600
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "user"


def default_output_path(names, start, end):
    """worklog_report_<people>_<start>_<end>.csv, never overwriting an earlier report."""
    if len(names) <= 3:
        who = "-".join(slug(n) for n in names)
    else:
        who = f"{slug(names[0])}-and-{len(names) - 1}-others"
    base = f"worklog_report_{who}_{start}_{end}"
    path, n = f"{base}.csv", 2
    while os.path.exists(path):
        path, n = f"{base}_{n}.csv", n + 1
    return path


def main():
    p = argparse.ArgumentParser(description="Generate a worklog CSV for people in a date range. "
                                            "Settings come from .env; flags override them.")
    p.add_argument("--emails", default=REPORT_EMAILS, help="Comma-separated emails (REPORT_EMAILS)")
    p.add_argument("--start", default=REPORT_START_DATE, help="Start date YYYY-MM-DD (REPORT_START_DATE)")
    p.add_argument("--end", default=REPORT_END_DATE, help="End date YYYY-MM-DD (REPORT_END_DATE)")
    p.add_argument("-o", "--output", default=REPORT_OUTPUT_PATH,
                   help="Output CSV path (REPORT_OUTPUT_PATH; default: "
                        "worklog_report_<people>_<start>_<end>.csv)")
    args = p.parse_args()

    people = [e.strip() for e in args.emails.split(",") if e.strip()]
    if not people:
        sys.exit("❌ No people given: set REPORT_EMAILS in .env (or pass --emails)")
    if not args.start or not args.end:
        sys.exit("❌ Set REPORT_START_DATE and REPORT_END_DATE in .env (or pass --start/--end)")
    try:
        start, end = parse_date(args.start), parse_date(args.end)
    except ValueError:
        sys.exit(f"❌ Dates must be in YYYY-MM-DD format (got start '{args.start}', end '{args.end}')")
    if end < start:
        sys.exit("❌ End date is before start date")

    range_start = datetime.combine(start, time.min, tzinfo=local_tz)
    range_end = datetime.combine(end + timedelta(days=1), time.min, tzinfo=local_tz)

    rows = []  # (date, started, name, issue key, description, hours, client ref, components)
    names = []
    try:
        print(f"🔑 Logged in as {check_credentials()}")
        ref_field = get_client_ref_field_id()
        for person in people:
            account_id, name = resolve_account_id(person)
            names.append(name)
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
    except JiraError as e:
        sys.exit(f"❌ {e}")

    rows.sort(key=lambda r: (r[2], r[0], r[1], r[3]))

    # Same columns/date format as the uploader's input CSV, plus extra columns
    output = args.output or default_output_path(names, start, end)
    if args.output and os.path.exists(output):
        print(f"⚠️ {output} already exists and will be overwritten")
    try:
        with open(output, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Task Key", "What did you do?", "Duration (hours)",
                             "Client Reference", "Components", "Logged By"])
            for day, _, name, key, desc, hours, client_ref, components in rows:
                writer.writerow([f"{day.month}/{day.day}/{day.year}", key, desc, f"{hours:g}",
                                 client_ref, components, name])
    except OSError as e:
        sys.exit(f"❌ Could not write {output}: {e.strerror or e}. "
                 f"If the file is open in Excel, close it and run again.")

    print(f"✅ {len(rows)} worklogs written to {output} (total {sum(r[5] for r in rows):.2f}h)")


if __name__ == "__main__":
    main()
