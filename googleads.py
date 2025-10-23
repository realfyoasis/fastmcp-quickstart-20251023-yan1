"""
Google Ads MCP Server (echo-style, no FastAPI)
"""

from fastmcp import FastMCP
from typing import List, Dict

# --- Optional GCP Secret Manager (only if you want to resolve secret_version_name) ---
from google.cloud import secretmanager
from google.api_core.exceptions import NotFound

# --- Your Google Ads service (you must provide this file/class) ---
# Expecting: core/services/google_ads_service.py with class GoogleAdsService(user_credentials: dict)
# and methods: get_accessible_accounts() -> Iterable[object], get_account_summary(customer_id: str, days: int) -> dict
try:
    from core.services.google_ads_service import GoogleAdsService
except Exception as e:  # pragma: no cover
    # Lightweight guard so the module imports even if the service isn't present yet
    class GoogleAdsService:  # type: ignore
        def __init__(self, user_credentials: dict):
            raise RuntimeError(
                "Missing core/services/google_ads_service.py. "
                "Provide GoogleAdsService(user_credentials) with "
                "get_accessible_accounts() and get_account_summary(customer_id, days)."
            )

# --------------------------------------------------------------------
# Create server (same shape as your echo.py)
# --------------------------------------------------------------------
mcp = FastMCP("Google Ads MCP")


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def _resolve_creds(auth: dict) -> dict:
    """
    Accepts one of:
      {"refresh_token": "..."} |
      {"access_token": "..."} |
      {"secret_version_name": "projects/<id>/secrets/<name>/versions/<n|latest>"}
    Returns a dict suitable for GoogleAdsService(user_credentials=...).
    """
    if not isinstance(auth, dict):
        raise ValueError("auth must be an object")

    if "refresh_token" in auth:
        return {"refresh_token": auth["refresh_token"]}

    if "access_token" in auth:
        return {"access_token": auth["access_token"]}

    if "secret_version_name" in auth:
        name = auth["secret_version_name"]
        client = secretmanager.SecretManagerServiceClient()
        try:
            resp = client.access_secret_version(request={"name": name})
        except NotFound as e:
            raise FileNotFoundError(f"Secret version not found: {name}") from e
        token = resp.payload.data.decode("utf-8")
        return {"refresh_token": token}

    raise ValueError(
        "auth must include one of: refresh_token | access_token | secret_version_name"
    )


# --------------------------------------------------------------------
# Tools (decorator style exactly like echo.py)
# --------------------------------------------------------------------
@mcp.tool
def list_accessible_accounts(auth: dict) -> List[Dict]:
    """List all Google Ads accounts the authenticated user can access.

    auth can be:
      {"refresh_token": "..."} |
      {"access_token": "..."} |
      {"secret_version_name": "projects/<id>/secrets/<name>/versions/<n|latest>"}
    """
    svc = GoogleAdsService(user_credentials=_resolve_creds(auth))
    accounts = svc.get_accessible_accounts()
    # normalize to plain dicts
    return [getattr(a, "__dict__", dict(a)) for a in accounts]


@mcp.tool
def get_account_summary(auth: dict, customer_id: str, days: int = 30) -> Dict:
    """Get performance summary (spend/clicks/conversions) for a Google Ads account.

    Args:
      auth: same formats as list_accessible_accounts
      customer_id: Google Ads customer ID (with or without dashes)
      days: lookback window (default 30)
    """
    svc = GoogleAdsService(user_credentials=_resolve_creds(auth))
    data = svc.get_account_summary(customer_id, days)
    return data or {"message": f"No data found for account {customer_id}"}


# --------------------------------------------------------------------
# Resources (optional, like your echo resources)
# --------------------------------------------------------------------
@mcp.resource("google-ads://help")
def help_resource() -> str:
    return (
        "Google Ads MCP\n"
        "Tools:\n"
        " • list_accessible_accounts(auth)\n"
        " • get_account_summary(auth, customer_id, days=30)\n"
        "\n"
        "auth may be one of:\n"
        "  {\"refresh_token\":\"...\"} | {\"access_token\":\"...\"} | "
        "{\"secret_version_name\":\"projects/<id>/secrets/<name>/versions/<n|latest>\"}\n"
    )


@mcp.resource("google-ads://summary/{customer_id}")
def summary_template(customer_id: str) -> str:
    """Template resource that documents how to get a summary for a specific customer."""
    return (
        f"To fetch a summary for {customer_id}, call tool "
        f"`get_account_summary` with {{auth: <see help>, customer_id: \"{customer_id}\", days: 30}}"
    )


# --------------------------------------------------------------------
# Prompt (optional, same style as echo prompt)
# --------------------------------------------------------------------
@mcp.prompt("ads_instructions")
def ads_instructions(text: str = "Provide Google Ads auth and optional customer_id/days.") -> str:
    return text


# --------------------------------------------------------------------
# Run (HTTP for Claude custom HTTP connector; mirrors tiny style)
# --------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio, os
    # Serve pure FastMCP HTTP (root path) so you can point Claude at http://host:7070/
    asyncio.run(mcp.run_http_async(host="0.0.0.0", port=int(os.getenv("PORT", "7070"))))
