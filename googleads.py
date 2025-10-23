"""
Google Ads MCP Server with OAuthProxy for Claude Desktop
Uses FastMCP's OAuthProxy for automatic OAuth discovery and token handling.
"""

import os
import logging
from typing import List, Dict
from dataclasses import is_dataclass, asdict
from types import SimpleNamespace

from fastmcp import FastMCP
from fastmcp.server.auth.oauth_proxy import OAuthProxy
from google.cloud import secretmanager
from google.api_core.exceptions import NotFound

try:
    from core.services.google_ads_service import GoogleAdsService
except Exception as e:
    class GoogleAdsService:
        def __init__(self, user_credentials: dict):
            raise RuntimeError(
                "Missing core/services/google_ads_service.py. "
                "Provide GoogleAdsService(user_credentials) with "
                "get_accessible_accounts() and get_account_summary(customer_id, days)."
            )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# OAuth Proxy Setup (for Claude's automatic OAuth discovery)
# --------------------------------------------------------------------
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID") or os.getenv("GOOGLE_ADS_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or os.getenv("GOOGLE_ADS_CLIENT_SECRET")

if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
    logger.warning("⚠️  Missing GOOGLE_OAUTH_CLIENT_ID/SECRET - OAuth will be disabled")
    oauth = None
else:
    def build_oauth_proxy():
        """Build OAuthProxy for Google OAuth with Google Ads scope"""
        from fastmcp.server.auth import StaticTokenVerifier
        
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        token_url = "https://oauth2.googleapis.com/token"
        scopes = [
            "https://www.googleapis.com/auth/adwords",
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
        ]
        
        # Token verifier (FastMCP requires this)
        verifier = StaticTokenVerifier(secret="dummy", required_scopes=scopes)
        
        public_base = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("PUBLIC_URL") or "https://digital-magenta-bee.fastmcp.app"
        public_base = public_base.rstrip("/")
        
        return OAuthProxy(
            upstream_authorization_endpoint=auth_url,
            upstream_token_endpoint=token_url,
            upstream_client_id=GOOGLE_OAUTH_CLIENT_ID,
            upstream_client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
            token_verifier=verifier,
            base_url=public_base,
        )
    
    try:
        oauth = build_oauth_proxy()
        logger.info("✅ OAuthProxy initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize OAuthProxy: {e}")
        oauth = None

# --------------------------------------------------------------------
# Create FastMCP server
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

    out = []
    for a in accounts:
        # dataclass -> asdict
        try:
            if is_dataclass(a):
                out.append(asdict(a))
                continue
        except Exception:
            pass

        # plain object with __dict__
        if hasattr(a, "__dict__"):
            try:
                out.append(vars(a))
                continue
            except Exception:
                pass

        # already a mapping
        if isinstance(a, dict):
            out.append(a)
            continue

        # try to coerce to dict (may raise TypeError)
        try:
            out.append(dict(a))
            continue
        except Exception:
            out.append({"raw": str(a)})

    return out


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
def ads_instructions(text: str = "Provide Google Ads auth and optional customer_id/days.optionally where applicable make graphs.") -> str:
    return text


# ============================================================================
# Run (HTTP with OAuth discovery)
# ============================================================================
if __name__ == "__main__":
    import asyncio
    
    port = int(os.getenv("PORT", "7070"))
    host = os.getenv("HOST", "0.0.0.0")
    
    # Get the HTTP app and add OAuth routes
    app = mcp.http_app()
    
    if oauth:
        # Add OAuth routes for discovery
        for route in oauth.get_routes(mcp_path="/"):
            app.router.routes.append(route)
        logger.info("✅ OAuth routes added - Claude will auto-discover OAuth config")
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  Google Ads MCP Server with OAuth Discovery                 ║
╚══════════════════════════════════════════════════════════════╝

Server URL: http://{host}:{port}
MCP Endpoint: http://{host}:{port}/mcp

OAuth Discovery: {'✅ Enabled' if oauth else '❌ Disabled (missing credentials)'}
  - Claude will find OAuth config at /.well-known/oauth-authorization-server
  - User clicks "Connect" → OAuth flow starts automatically
  - No manual configuration needed!

Environment Variables:
  GOOGLE_OAUTH_CLIENT_ID: {'✅ Set' if GOOGLE_OAUTH_CLIENT_ID else '❌ Missing'}
  GOOGLE_OAUTH_CLIENT_SECRET: {'✅ Set' if GOOGLE_OAUTH_CLIENT_SECRET else '❌ Missing'}
  GOOGLE_ADS_DEVELOPER_TOKEN: {'✅ Set' if os.getenv('GOOGLE_ADS_DEVELOPER_TOKEN') else '❌ Missing'}

Press Ctrl+C to stop
""")
    
    asyncio.run(mcp.run_http_async(host=host, port=port))
