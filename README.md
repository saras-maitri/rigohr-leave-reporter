# RigoHR Leave Reporter

Automates daily leave reporting from RigoHR. Authenticates via IAM SSO, fetches pending and approved leave requests, fetches team attendance, writes reports to CSV, and sends a categorized summary to Google Chat.

## How It Works

1. **Authenticate** — Logs into RigoHR via IAM SSO (OpenIddict OAuth flow)
2. **Fetch data** — Retrieves pending + approved leave requests and team attendance
3. **Write CSV** — Saves `leave_requests.csv` and `attendance-YYYY-MM-DD.csv`
4. **Send webhook** — Posts a categorized leave report to Google Chat

## Setup

### 1. Clone the repo

```bash
git clone git@github.com:saras-maitri/rigohr-leave-reporter.git
cd rigohr-leave-reporter
```

### 2. Install dependencies

```bash
pip install requests python-dotenv
```

### 3. Configure environment

Create a `.env` file in the project root:

```env
RigoId=your.email@company.com
password=your_password
TENANT_ID=your-tenant-uuid
GCHAT_WEBHOOK=https://chat.googleapis.com/v1/spaces/...
```

### 4. Run

```bash
# Today's report
python3 main.py

# Specific date
python3 main.py --date 2026-03-10
```

## Cron Setup

The `run.sh` script handles `cd` into the project directory so it works from cron.

```bash
chmod +x run.sh
```

Edit your crontab:

```bash
crontab -e
```

Add:

```cron
# Every weekday at 11:35 AM
35 11 * * 1-5 /path/to/rigohr-leave-reporter/run.sh >> /path/to/rigohr-leave-reporter/cron.log 2>&1
```

Verify:

```bash
crontab -l
```

## Output

| File | Description |
|------|-------------|
| `leave_requests.csv` | All leave requests — name, type, dates, status, reason |
| `attendance-YYYY-MM-DD.csv` | Team attendance for the report date |
| Google Chat message | Categorized by leave type with pending/approved status |

## Project Structure

```
├── main.py             # Entrypoint — orchestrates the 4-step workflow
├── auth.py             # IAM SSO authentication (login → SSO → session activation)
├── leave_api.py        # Fetches pending + approved leave requests (paginated)
├── attendance_api.py   # Fetches team attendance (paginated)
├── run.sh              # Shell wrapper for cron
├── .env                # Credentials and config (gitignored)
└── .gitignore
```
