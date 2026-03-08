# Jira Worklog Uploader

A Python script to bulk import work logs from a CSV file into Jira, with automatic timezone conversion and UTC time handling.

## Features

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
python jira_worklog_uploader_improved.py
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
├── jira_worklog_uploader_improved.py  # Main script
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
