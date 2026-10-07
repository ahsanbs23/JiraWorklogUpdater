# Jira Worklog Uploader

Python scripts to bulk import work logs from a CSV file into Jira (`jira_worklog_uploader.py`), and to export logged hours for selected people over a date range back to CSV (`jira_worklog_report.py`).

## Features

- 📤 **Worklog Report**: Export logged hours per person for a date range to CSV, including client reference and components

- 📋 **CSV Import**: Read worklogs from a structured CSV file
- 🕐 **Timezone Conversion**: Automatically converts local time (GMT+6) to UTC for Jira
- 📊 **Summary Reporting**: Displays total hours logged after processing
- ✅ **Date Sorting**: Processes entries in chronological order
- 📝 **Error Handling**: Skips invalid rows with informative warnings
- 🔑 **Secure Config**: Uses environment variables for sensitive credentials

## Requirements

- Python 3.8+
- pip (Python package manager)

## Installation

### 1. Create a Virtual Environment
```powershell
cd d:\source\jira-worklog-cleanup
py -m venv venv
```

### 2. Activate Virtual Environment

**PowerShell (Windows):**
```powershell
.\venv\Scripts\Activate.ps1
```

**Git Bash (Windows):**
```bash
source venv/Scripts/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## Configuration

### Setup Environment Variables

1. **Copy the example file:**
   ```bash
   copy .env.example .env
   ```

2. **Edit `.env` with your Jira credentials:**
   ```env
   JIRA_BASE_URL=https://pm23.atlassian.net
   EMAIL=your-email@example.com
   API_TOKEN=your-api-token-from-jira
   CSV_FILE_PATH=C:\Users\username\Downloads\February_Logs.csv
   LOCAL_TIMEZONE_OFFSET=6
   ```

### Getting Your Jira API Token

1. Go to https://id.atlassian.com/manage/api-tokens
2. Click "Create API token"
3. Copy the token and paste it in `.env`

### CSV File Format

Your CSV must have these columns:
- **Date**: Format `M/D/YYYY` (e.g., `1/15/2026`)
- **Task Key**: Jira issue key (e.g., `PROJ-123`)
- **What did you do?**: Work description
- **Duration (hours)**: Hours logged (e.g., `8`, `2.5`)

**Example:**
```
Date,Task Key,What did you do?,Duration (hours)
1/15/2026,PROJ-123,Implemented feature X,8
1/15/2026,PROJ-124,Bug fixes and testing,2.5
1/16/2026,PROJ-123,Code review and documentation,4
```

## Usage

### Run the Script

```bash
python jira_worklog_uploader.py
```

### Output Example

```
✅ PROJ-123 - 8.0h logged
✅ PROJ-124 - 2.5h logged
✅ PROJ-123 - 4.0h logged

📊 Total hours logged: 14.5h
```

### Error Handling

The script provides helpful feedback:
- ✅ Success: Shows issue key and hours logged
- ❌ Failed: Shows issue key and error details
- ⚠️ Skipped: Warns about rows that couldn't be processed

## Worklog Report

`jira_worklog_report.py` is read-only. It fetches the worklogs of one or more people within a date range and writes them to a CSV.

### Configuration

Add to `.env`:

```env
REPORT_EMAILS=person1@example.com,person2@example.com
REPORT_START_DATE=2026-09-01
REPORT_END_DATE=2026-09-30
```

| Variable | Required | Description |
|---|---|---|
| `REPORT_EMAILS` | Yes | Comma-separated emails (display names or Jira accountIds also work) |
| `REPORT_START_DATE` | Yes | Start date, `YYYY-MM-DD`, inclusive |
| `REPORT_END_DATE` | Yes | End date, `YYYY-MM-DD`, inclusive |
| `REPORT_OUTPUT_PATH` | No | Output file (default: `worklog_report_<people>_<start>_<end>.csv`, e.g. `worklog_report_ana_doe_2026-09-01_2026-09-30.csv`; never overwrites an earlier report, a `_2`, `_3` suffix is added instead) |
| `CLIENT_REF_FIELD_NAME` | No | Name of the client reference custom field (default: `Client Reference`) |
| `CLIENT_REF_FIELD_ID` | No | Field ID, e.g. `customfield_10820`; skips the name lookup |

Day boundaries use `LOCAL_TIMEZONE_OFFSET`, same as the uploader.

### Run

```bash
python jira_worklog_report.py
```

Flags override `.env` for a single run:

```bash
python jira_worklog_report.py --emails a@x.com,b@x.com --start 2026-09-01 --end 2026-09-30 -o september.csv
```

### Output

One row per worklog, sorted by person then date. The first four columns match the uploader's input CSV (dates as `M/D/YYYY`):

```
Date,Task Key,What did you do?,Duration (hours),Client Reference,Components,Logged By
9/15/2026,PROJ-123,Implemented feature X,8,ACME-42,Checkout,Jane Doe
```

- **Client Reference**: custom field on the issue
- **Components**: issue components, joined with `, `
- **Logged By**: Jira display name of the person who logged the work

### Notes

- Looking up by email can fail if the user's Jira privacy settings hide it; use their accountId instead.
- Issues the API token's user cannot browse are not included in the totals.

## How It Works

1. **Load Configuration**: Reads environment variables from `.env`
2. **Read CSV**: Parses the CSV file with UTF-8 encoding support
3. **Sort Entries**: Arranges worklogs chronologically
4. **Process Rows**: For each valid row:
   - Parses the date
   - Creates a 9 AM start time in GMT+6 timezone
   - Converts to UTC for Jira
   - Uploads to Jira via REST API
5. **Report Summary**: Displays total hours logged

## Timezone Handling

- **Default Timezone**: GMT+6 (Bangladesh Standard Time)
- **Start Time**: All worklogs logged at 9:00 AM local time
- **Conversion**: Automatically converts to UTC for Jira API

To change timezone, update `LOCAL_TIMEZONE_OFFSET` in `.env`.

## Troubleshooting

### Date Parsing Errors
- Ensure CSV dates are in `M/D/YYYY` format
- Check for extra spaces around date values

### Authentication Failures
- Verify email and API token in `.env`
- Ensure API token hasn't expired
- Check Jira Base URL is correct

### CSV Not Found
- Verify `CSV_FILE_PATH` in `.env` is correct
- Check file exists and is readable
- Use absolute paths for better reliability

### Missing Dependencies
- Run `pip install -r requirements.txt` again
- Ensure virtual environment is activated

## Project Structure

```
jira-worklog-cleanup/
├── jira_worklog_uploader.py             # Upload worklogs from CSV to Jira
├── jira_worklog_report.py               # Export worklogs for a date range to CSV
├── requirements.txt                     # Python dependencies
├── .env.example                         # Example configuration template
├── .env                                 # Actual configuration (git ignored)
├── .gitignore                           # Git ignore rules
├── README.md                            # This file
└── RUN_INSTRUCTIONS.md                  # Legacy instructions
```

## Security Notes

- **Never commit `.env`**: This file is in `.gitignore` for your protection
- **Share `.env.example` instead**: Use this template for documentation
- **Use app passwords**: Consider using Jira app passwords instead of main account API tokens
- **Rotate tokens**: Regularly rotate your API tokens for security

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review Jira API documentation: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
3. Verify your CSV format matches the required schema

## License

Internal tool for worklog management.
