import math

import requests

API_BASE = "https://api.app.rigohr.com"

ATTENDANCE_PATH = "/v1/leave-time/attendance/team"
PAGE_SIZE = 10


def _fetch_page(
    session: requests.Session, page_index: int, report_date: str
) -> list[dict]:
    params = {"PageIndex": str(page_index), "PageSize": str(PAGE_SIZE), "Date": report_date}
    response = session.get(f"{API_BASE}{ATTENDANCE_PATH}", params=params)
    response.raise_for_status()
    data = response.json().get("Data", [])
    return data if isinstance(data, list) else []


def fetch_team_attendance(
    session: requests.Session, tenant_id: str, report_date: str
) -> list[dict]:
    """Fetch all team attendance records for a given date."""
    session.headers["tenantid"] = tenant_id

    first_page = _fetch_page(session, 0, report_date)
    if not first_page:
        return []

    total_rows = first_page[0].get("TotalRows", len(first_page))
    total_pages = math.ceil(total_rows / PAGE_SIZE)
    all_records = list(first_page)

    for page in range(1, total_pages):
        all_records.extend(_fetch_page(session, page, report_date))

    return all_records
