from urllib.parse import urlencode, urlparse, parse_qs

import requests

IAM_BASE = "https://login.app.rigohr.com"
API_BASE = "https://api.app.rigohr.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)


def _create_session() -> requests.Session:
    session = requests.Session()
    session.headers["user-agent"] = USER_AGENT
    return session


def _iam_login(session: requests.Session, rigo_id: str, password: str) -> None:
    """Login to IAM and capture the shared cookie."""
    session.get(f"{IAM_BASE}/login")

    session.headers.update({
        "content-type": "application/json",
        "origin": IAM_BASE,
        "referer": f"{IAM_BASE}/login",
    })
    session.post(f"{IAM_BASE}/signin", json={"RigoId": rigo_id})

    session.headers["content-type"] = "application/x-www-form-urlencoded"
    response = session.post(
        f"{IAM_BASE}/login",
        data=urlencode({"Username": rigo_id, "Password": password, "returnUrl": ""}),
        allow_redirects=False,
    )

    if response.status_code != 302:
        raise RuntimeError(f"IAM login failed with status {response.status_code}")

    # Manually extract .IAM.SharedCookie (requests doesn't parse empty domain=)
    for key, value in response.raw.headers.items():
        if key.lower() == "set-cookie" and ".IAM.SharedCookie" in value:
            cookie_val = value.split(";")[0].split("=", 1)[1]
            session.cookies.set(
                ".IAM.SharedCookie", cookie_val, domain="login.app.rigohr.com"
            )
            return

    raise RuntimeError("IAM login did not return .IAM.SharedCookie")


def _sso_exchange(session: requests.Session) -> tuple[str, str]:
    """Run the SSO OAuth flow and return (code, tenant_id)."""
    session.headers.clear()
    session.headers["user-agent"] = USER_AGENT

    response = session.get(f"{API_BASE}/sso/iam/login", allow_redirects=True)
    parsed = urlparse(response.url)
    params = parse_qs(parsed.query)

    code = params.get("code", [None])[0]
    identifier = params.get("identifier", [None])[0]
    if not code or not identifier:
        raise RuntimeError(f"SSO flow failed, ended at {response.url}")

    return code, identifier


def _activate_session(
    session: requests.Session, code: str, tenant_id: str
) -> None:
    """Exchange the SSO code to activate the API session."""
    session.headers.update({
        "accept": "application/json, text/plain, */*",
        "origin": "https://app.rigohr.com",
        "referer": "https://app.rigohr.com/",
        "tenantid": tenant_id,
    })

    response = session.get(f"{API_BASE}/v1/iam/sso-callback?code={code}")
    data = response.json()
    if not data.get("Status"):
        raise RuntimeError(f"SSO callback failed: {data}")


def authenticate(rigo_id: str, password: str) -> tuple[requests.Session, str]:
    """Full authentication flow. Returns (session, tenant_id)."""
    session = _create_session()
    _iam_login(session, rigo_id, password)
    code, tenant_id = _sso_exchange(session)
    _activate_session(session, code, tenant_id)
    return session, tenant_id
