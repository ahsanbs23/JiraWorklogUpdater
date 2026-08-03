# Jira Worklog Uploader Script - Setup & Run Instructions

## Overview
This script imports worklogs from a CSV file into Jira with the following features:
- **Source**: CSV file with columns: Date, Task Key, What did you do?, Duration (hours)
- **Timezone**: Automatically converts GMT+6 local time to UTC for Jira
- **Start Time**: All worklogs logged at 9 AM (GMT+6)
- **Format Supported**: Date format `M/D/YYYY` (e.g., 1/5/2026)

## Prerequisites
- Python 3.8+ installed
- Git Bash or PowerShell with access to the workspace

## Setup Instructions

### Step 1: Create Virtual Environment
```bash
cd d:\source\jira-worklog-cleanup
py -m venv venv
```

### Step 2: Activate Virtual Environment

**On PowerShell (Windows):**
```powershell
.\venv\Scripts\Activate.ps1
```

**On Git Bash (Windows):**
```bash
source venv/Scripts/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

You should see output confirming the installation of `requests` and `python-dateutil`.

## Running the Script

### Basic Run
```bash
python jira_worklog_uploader.py
```

This will:
- ✅ Read the CSV file from the configured path
- ✅ Parse dates in `M/D/YYYY` format
- ✅ Convert all times from GMT+6 to UTC
- ✅ Log each worklog at 9 AM (GMT+6)
- ✅ Upload to Jira and display status

**Expected Output Example:**
```
✅ IOIA-4736 - 4.0h logged
✅ IOIA-1122 - 2.5h logged
❌ IOIA-9999 failed: {"errorMessages":["Issue not found"]}
⚠️ Skipped row: Invalid data
```

### Handling Errors
- ✅ **Green checkmark (✅)**: Worklog successfully uploaded
- ❌ **Red X (❌)**: API error (see error message for details)
- ⚠️ **Warning (⚠️)**: Row skipped due to missing data or parsing error

## Configuration

To modify the script for different settings, edit these values in `jira_worklog_uploader_improved.py`:

| Variable | Current Value | Purpose |
|----------|---------------|---------|
| `JIRA_BASE_URL` | `https://pm23.atlassian.net` | Your Jira instance URL |
| `EMAIL` | `nazmul.ahsan@brainstation-23.com` | Jira API email |
| `API_TOKEN` | `ATATT3xFfGF0...` | Jira API token |
| `CSV_FILE_PATH` | `C:\Users\BS01673\Downloads\January_Logs.csv` | Path to your CSV file |
| `LOCAL_TIMEZONE_OFFSET` | `6` | Your timezone offset from UTC (GMT+6) |

## Deactivating Virtual Environment

When done, exit the virtual environment:
```bash
deactivate
```

## Troubleshooting

### ❌ `ModuleNotFoundError: No module named 'requests'`
- Ensure you've run `pip install -r requirements.txt`
- Ensure the virtual environment is activated (you should see `(venv)` in your terminal prompt)

### ❌ `KeyError: 'Date'` or `KeyError: 'Task Key'`
- Check that your CSV column names match exactly:
  - `Date` (format: M/D/YYYY)
  - `Task Key` (e.g., IOIA-4736)
  - `What did you do?` (description)
  - `Duration (hours)` (numeric value)

### ❌ Worklog upload fails with "Invalid date format"
- Verify the date format in your CSV is `M/D/YYYY` (e.g., `1/5/2026` not `01-05-2026`)
- Check that `LOCAL_TIMEZONE_OFFSET` is set correctly for your timezone

### ❌ Permission Denied (403)
- Verify your `API_TOKEN` is valid and hasn't expired
- Ensure your email address has permission to log time on those issues

### ❌ Issue Key Not Found
- Verify the issue key (e.g., `IOIA-4736`) exists in your Jira instance
- Check that you have permission to access that issue

### ❌ Python not found
- Install Python from https://www.python.org/downloads/
- Ensure Python is in your PATH

## Safety Notes
✅ **CSV validation** - Script checks for required columns and data  
✅ **Error handling** - Skips invalid rows and continues processing  
✅ **Timezone support** - Correctly handles GMT+6 to UTC conversion  
✅ **Flexible timing** - All worklogs assigned to 9 AM (easily customizable)
