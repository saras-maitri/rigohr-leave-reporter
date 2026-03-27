import math
from datetime import date, timedelta

import requests

API_BASE = "https://api.app.rigohr.com"

LEAVE_REQUESTS_PATH = "/v1/ltoa/ltOa/requests"
PAGE_SIZE = 10
COMMON_PARAMS = {
    "EmployeeName": "",
    "RequestId": "null",
    "RequestType": "",
    "RequestEndDate": "",
}


def _fetch_all_pages(session: requests.Session, params: dict) -> list[dict]:
    query = {**params, "PageIndex": "0", "PageSize": str(PAGE_SIZE)}
    response = session.get(f"{API_BASE}{LEAVE_REQUESTS_PATH}", params=query)
    response.raise_for_status()
    first_page = response.json().get("Data", [])
    if not first_page or not isinstance(first_page, list):
        return []

    total_rows = first_page[0].get("TotalRow", len(first_page))
    total_pages = math.ceil(total_rows / PAGE_SIZE)
    all_records = list(first_page)

    for page in range(1, total_pages):
        query["PageIndex"] = str(page)
        r = session.get(f"{API_BASE}{LEAVE_REQUESTS_PATH}", params=query)
        r.raise_for_status()
        data = r.json().get("Data", [])
        if isinstance(data, list):
            all_records.extend(data)

    return all_records


def fetch_pending_requests(session: requests.Session, tenant_id: str) -> list[dict]:
    """Fetch all pending leave requests."""
    session.headers["tenantid"] = tenant_id
    params = {
        **COMMON_PARAMS,
        "IsHistory": "false",
        "Status": "null",
        "EventStartDate": "",
        "EventEndDate": "",
    }
    return _fetch_all_pages(session, params)


def fetch_approved_requests(
    session: requests.Session, tenant_id: str, start_date: str, end_date: str
) -> list[dict]:
    """Fetch approved leave requests for a date range."""
    session.headers["tenantid"] = tenant_id
    params = {
        **COMMON_PARAMS,
        "IsHistory": "true",
        "Status": "7",
        "EventStartDate": start_date,
        "EventEndDate": end_date,
    }
    return _fetch_all_pages(session, params)


def fetch_leave_requests(
    session: requests.Session, tenant_id: str, start_date: str, end_date: str
) -> list[dict]:
    """Fetch both pending and approved leave requests, deduplicated by RequestId."""
    pending = fetch_pending_requests(session, tenant_id)
    # Use a 30-day lookback so multi-day leaves starting before the
    # report date are not missed by the API's EventStartDate filter.
    lookback = (date.fromisoformat(start_date) - timedelta(days=30)).isoformat()
    approved = fetch_approved_requests(session, tenant_id, lookback, end_date)

    seen = set()
    combined = []
    for record in pending + approved:
        rid = record.get("RequestId")
        if rid not in seen:
            seen.add(rid)
            combined.append(record)

    return combined
