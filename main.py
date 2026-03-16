import argparse
import csv
import os
from collections import defaultdict
from datetime import date
from pathlib import Path

import requests

from attendance_api import fetch_team_attendance
from auth import authenticate
from leave_api import fetch_leave_requests

LEAVE_CSV_FIELDS = ["name", "leave_type", "from_date", "to_date", "status", "reason", "sent"]


def _get_tenant_id() -> str:
    tid = os.getenv("TENANT_ID", "")
    if not tid:
        raise SystemExit("Set TENANT_ID in .env")
    return tid
def _get_webhook_url() -> str:
    url = os.getenv("GCHAT_WEBHOOK", "")
    if not url:
        raise SystemExit("Set GCHAT_WEBHOOK in .env")
    return url


# --- Step 1: Authenticate ---


def login(rigo_id: str, password: str) -> requests.Session:
    return authenticate(rigo_id, password)


# --- Step 2: Fetch latest data ---


def _format_date(date_str: str) -> str:
    if not date_str:
        return ""
    return date_str.split("T")[0]


def _get_status(item: dict) -> str:
    status = item.get("Status", "")
    if status == "Request":
        return "Pending"
    if status in ("Approved", "Completed"):
        return "Approved"
    return status


def fetch_reports(session: requests.Session, tenant_id: str, report_date: str) -> dict:
    raw_leaves = fetch_leave_requests(
        session, tenant_id, start_date=report_date, end_date=report_date
    )
    leave_records = [
        {
            "name": item["Requester"],
            "leave_type": item["LeaveName"],
            "from_date": _format_date(item.get("FromDateEng", "")),
            "to_date": _format_date(item.get("ToDateEng", "")),
            "status": _get_status(item),
            "reason": item["Reason"],
        }
        for item in raw_leaves
    ]

    raw_attendance = fetch_team_attendance(session, tenant_id, report_date)
    attendance_records = [
        {
            "name": item["Name"],
            "department": item.get("Department", ""),
            "is_present": item.get("IsPresent", False),
        }
        for item in raw_attendance
    ]

    return {"leaves": leave_records, "attendance": attendance_records}


# --- Step 3: State-aware CSV management ---


def _leave_key(record: dict) -> str:
    """Unique key for a leave record to detect duplicates."""
    return f"{record['name']}|{record['leave_type']}|{record['from_date']}|{record['to_date']}"


def _leave_csv_path(report_date: str) -> Path:
    return Path(f"leave-{report_date}.csv")


def _read_existing_leaves(csv_path: Path) -> dict[str, dict]:
    """Read existing leave CSV and return dict keyed by leave_key."""
    if not csv_path.exists():
        return {}
    existing = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = _leave_key(row)
            existing[key] = row
    return existing


def _write_leave_csv(csv_path: Path, records: list[dict]) -> None:
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LEAVE_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(records)


def process_leaves(reports: dict, report_date: str, mode: str) -> list[dict]:
    """Process leaves with state tracking. Returns the list of leaves to send."""
    csv_path = _leave_csv_path(report_date)
    todays_leaves = [
        r for r in reports["leaves"]
        if r["leave_type"] and r["from_date"] <= report_date <= r["to_date"]
    ]

    if mode == "morning":
        # First run of the day: write all leaves as sent
        all_records = [{**r, "sent": "true"} for r in todays_leaves]
        _write_leave_csv(csv_path, all_records)
        print(f"Wrote {len(all_records)} leave records to {csv_path}")
        return todays_leaves

    # afternoon mode: compare with existing state
    existing = _read_existing_leaves(csv_path)
    new_leaves = []
    all_records = list(existing.values())

    for leave in todays_leaves:
        key = _leave_key(leave)
        if key not in existing:
            new_leaves.append(leave)
            all_records.append({**leave, "sent": "true"})

    _write_leave_csv(csv_path, all_records)
    print(f"Updated {csv_path}: {len(existing)} existing + {len(new_leaves)} new = {len(all_records)} total")
    return new_leaves


# --- Step 4: Write attendance CSV ---


def write_attendance_csv(reports: dict, report_date: str) -> None:
    attendance_file = f"attendance-{report_date}.csv"
    fieldnames = ["name", "department", "is_present"]
    with open(attendance_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(reports["attendance"])
    print(f"Wrote {len(reports['attendance'])} attendance records to {attendance_file}")


# --- Step 5: Send webhook ---


def send_webhook(leaves_to_send: list[dict], sender: str, report_date: str, mode: str) -> None:
    if not leaves_to_send:
        print(f"No {'new ' if mode == 'afternoon' else ''}leave requests for {report_date}")
        return

    grouped = defaultdict(list)
    for r in leaves_to_send:
        grouped[r["leave_type"]].append(r)

    title = f"*Leave Report for {report_date}*"
    if mode == "afternoon":
        title = f"*New Leave Requests since morning — {report_date}*"

    lines = [f"{title}\n_From: {sender}_\n"]
    for leave_type, entries in grouped.items():
        lines.append(f"*{leave_type}* ({len(entries)})")
        for entry in entries:
            reason = f" — {entry['reason']}" if entry["reason"] else ""
            lines.append(f"  • {entry['name']}{reason}")
        lines.append("")

    message = "\n".join(lines)
    print(f"\n{message}")

    response = requests.post(_get_webhook_url(), json={"text": message})
    response.raise_for_status()
    print("Sent to Google Chat")


# --- Entrypoint ---


def main():
    parser = argparse.ArgumentParser(description="RigoHR Leave Report")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Report date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--mode", type=str, choices=["morning", "afternoon"], default="morning",
        help="Run mode: morning (full report) or afternoon (new leaves only)",
    )
    args = parser.parse_args()
    report_date = args.date or date.today().isoformat()

    rigo_id = os.getenv("RigoId")
    password = os.getenv("password")
    if not rigo_id or not password:
        raise SystemExit("Set RigoId and password in .env")

    tenant_id = _get_tenant_id()

    session = login(rigo_id, password)
    reports = fetch_reports(session, tenant_id, report_date)

    leaves_to_send = process_leaves(reports, report_date, args.mode)
    write_attendance_csv(reports, report_date)
    send_webhook(leaves_to_send, sender=rigo_id, report_date=report_date, mode=args.mode)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    main()
