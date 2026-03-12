# RigoHR Leave Reporter

Automates daily leave reporting from RigoHR. Authenticates via IAM SSO, fetches pending and approved leave requests, fetches team attendance, writes reports to CSV, and sends a categorized summary to Google Chat.

## Setup

### 1. Install dependencies

```bash
pip install requests python-dotenv
```

### 2. Configure environment

Create a `.env` file in the project root:

```
RigoId=your.email@company.com
password=your_password
TENANT_ID=your-tenant-uuid
GCHAT_WEBHOOK=https://chat.googleapis.com/v1/spaces/...
```

### 3. Run

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

Add one of these lines:

```cron
# Every weekday at 9:30 AM
30 9 * * 1-5 /home/saras/leave-automation/run.sh >> /home/saras/leave-automation/cron.log 2>&1

# Every weekday at 9:30 AM for a specific date (today is default)
30 9 * * 1-5 /home/saras/leave-automation/run.sh >> /home/saras/leave-automation/cron.log 2>&1
```

Verify cron is running:

```bash
crontab -l
```

## Output

- `leave_requests.csv` — all leave requests (name, type, dates, status, reason)
- `attendance-YYYY-MM-DD.csv` — team attendance for the report date
- Google Chat message — categorized by leave type with status
