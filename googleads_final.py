"""
Google Ads MCP Server with OAuthProxy for Claude Desktop Auto-Discovery
Based on working mcp_server.py pattern with OAuth discovery enabled.

When deployed to FastMCP Cloud:
- Claude Desktop will auto-discover OAuth configuration
- User clicks "Connect" → OAuth flow starts automatically
- No manual JSON configuration needed!
"""

import os
import logging
from typing import List, Dict, Optional
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
                "Missing core/services/google_ads_service.py"
            )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# OAuth Configuration
# --------------------------------------------------------------------
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID") or os.getenv("GOOGLE_ADS_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or os.getenv("GOOGLE_ADS_CLIENT_SECRET")
secret_manager_client = None

try:
    secret_manager_client = secretmanager.SecretManagerServiceClient()
except Exception:
    logger.warning("Secret Manager not available - secret_version_name auth will not work")

if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
    logger.warning("⚠️  Missing GOOGLE_OAUTH_CLIENT_ID/SECRET - OAuth will be disabled")
    oauth = None
else:
    def build_oauth_proxy():
        """Build OAuthProxy with Google OAuth configuration"""
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        token_url = "https://oauth2.googleapis.com/token"
        scopes = [
            "https://www.googleapis.com/auth/adwords",
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
        ]
        
        # Simple token verifier (using SimpleNamespace like your working code)
        Verifier = SimpleNamespace(
            verify=lambda *_args, **_kw: True,
            required_scopes=scopes
        )
        
        public_base = os.getenv("RENDER_EXTERNAL_URL") or "https://digital-magenta-bee.fastmcp.app"
        public_base = public_base.rstrip("/")
        
        return OAuthProxy(
            upstream_authorization_endpoint=auth_url,
            upstream_token_endpoint=token_url,
            upstream_client_id=GOOGLE_OAUTH_CLIENT_ID,
            upstream_client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
            token_verifier=Verifier,
            base_url=public_base,
        )
    
    try:
        oauth = build_oauth_proxy()
        logger.info("✅ OAuthProxy initialized - Claude will auto-discover OAuth config")
    except Exception as e:
        logger.error(f"❌ Failed to initialize OAuthProxy: {e}")
        oauth = None

# --------------------------------------------------------------------
# Create FastMCP Server
# --------------------------------------------------------------------
mcp = FastMCP("Google Ads MCP")

# --------------------------------------------------------------------
# Helper Functions
# --------------------------------------------------------------------
def _resolve_creds(auth: dict) -> dict:
    """
    Resolve credentials from various auth formats.
    Supports: refresh_token, access_token, secret_version_name
    """
    if not isinstance(auth, dict):
        raise ValueError("auth must be an object")

    if "refresh_token" in auth:
        return {"refresh_token": auth["refresh_token"]}

    if "access_token" in auth:
        return {"access_token": auth["access_token"]}

    if "secret_version_name" in auth:
        if not secret_manager_client:
            raise RuntimeError("Secret Manager not available")
        try:
            name = auth["secret_version_name"]
            response = secret_manager_client.access_secret_version(request={"name": name})
            token = response.payload.data.decode("utf-8")
            return {"refresh_token": token}
        except NotFound:
            raise FileNotFoundError(f"Secret version not found: {auth['secret_version_name']}")

    raise ValueError(
        "auth must include one of: refresh_token | access_token | secret_version_name"
    )

def _normalize_accounts(accounts: List) -> List[Dict]:
    """Convert Account objects to plain dicts for JSON serialization."""
    out = []
    for a in accounts:
        try:
            if is_dataclass(a):
                out.append(asdict(a))
                continue
        except Exception:
            pass

        if hasattr(a, "__dict__"):
            try:
                out.append(vars(a))
                continue
            except Exception:
                pass

        if isinstance(a, dict):
            out.append(a)
            continue

        try:
            out.append(dict(a))
            continue
        except Exception:
            out.append({"raw": str(a)})

    return out

# --------------------------------------------------------------------
# MCP Tools
# --------------------------------------------------------------------
@mcp.tool
def list_accessible_accounts(auth: dict) -> List[Dict]:
    """
    List all Google Ads accounts the authenticated user can access.

    Args:
        auth: Authentication credentials. Can be one of:
            - {"refresh_token": "..."} 
            - {"access_token": "..."}
            - {"secret_version_name": "projects/<id>/secrets/<name>/versions/<n|latest>"}
    
    Returns:
        List of account objects with id, name, is_manager, currency, timezone
    """
    try:
        creds = _resolve_creds(auth)
        service = GoogleAdsService(user_credentials=creds)
        accounts = service.get_accessible_accounts()
        return _normalize_accounts(accounts)
    except Exception as e:
        raise RuntimeError(f"Failed to list accounts: {str(e)}")


@mcp.tool
def get_account_summary(auth: dict, customer_id: str, days: int = 30) -> Dict:
    """
    Get performance summary (spend, clicks, conversions) for a Google Ads account.

    Args:
        auth: Authentication credentials (same format as list_accessible_accounts)
        customer_id: Google Ads customer ID (with or without dashes)
        days: Lookback window in days (default: 30)
    
    Returns:
        Dictionary with account performance metrics
    """
    try:
        creds = _resolve_creds(auth)
        service = GoogleAdsService(user_credentials=creds)
        summary = service.get_account_summary(customer_id, days)
        return summary or {"message": f"No data found for account {customer_id}"}
    except Exception as e:
        raise RuntimeError(f"Failed to get account summary: {str(e)}")


@mcp.tool
def get_campaigns(auth: dict, customer_id: str, days: int = 30, limit: int = 100) -> List[Dict]:
    """
    Get campaigns for a specific Google Ads account.

    Args:
        auth: Authentication credentials
        customer_id: Google Ads customer ID
        days: Lookback window in days (default: 30)
        limit: Maximum number of campaigns to return (default: 100)
    """
    try:
        creds = _resolve_creds(auth)
        service = GoogleAdsService(user_credentials=creds)
        campaigns = service.get_campaigns(customer_id, days, limit)
        return _normalize_accounts(campaigns)
    except Exception as e:
        raise RuntimeError(f"Failed to get campaigns: {str(e)}")


@mcp.tool
def get_keywords(
    auth: dict,
    customer_id: str,
    campaign_id: Optional[str] = None,
    days: int = 30,
    limit: int = 100
) -> List[Dict]:
    """
    Get keywords for a specific Google Ads account.

    Args:
        auth: Authentication credentials
        customer_id: Google Ads customer ID
        campaign_id: Optional campaign ID to filter by
        days: Lookback window in days (default: 30)
        limit: Maximum number of keywords to return (default: 100)
    """
    try:
        creds = _resolve_creds(auth)
        service = GoogleAdsService(user_credentials=creds)
        keywords = service.get_keywords(customer_id, campaign_id, days, limit)
        return _normalize_accounts(keywords)
    except Exception as e:
        raise RuntimeError(f"Failed to get keywords: {str(e)}")


# --------------------------------------------------------------------
# Resources
# --------------------------------------------------------------------
@mcp.resource("google-ads://help")
def help_resource() -> str:
    return """
Google Ads MCP Server with OAuth Auto-Discovery

AUTHENTICATION - TWO WAYS:

Method 1: Claude Desktop Auto-OAuth (Recommended)
  - Deploy to FastMCP Cloud
  - Add server URL to Claude Desktop: https://digital-magenta-bee.fastmcp.app/mcp
  - Claude automatically discovers OAuth config at /.well-known/oauth-authorization-server
  - Click "Connect" button → OAuth flow starts automatically
  - No manual JSON configuration needed!

Method 2: Manual auth parameter (Testing)
  - Pass auth in each tool call:
    {"refresh_token": "..."} or
    {"access_token": "..."} or
    {"secret_version_name": "projects/<id>/secrets/<name>/versions/<version>"}

TOOLS:
• list_accessible_accounts(auth) - List your Google Ads accounts
• get_account_summary(auth, customer_id, days=30) - Get account performance
• get_campaigns(auth, customer_id, days=30, limit=100) - Get campaigns
• get_keywords(auth, customer_id, campaign_id?, days=30, limit=100) - Get keywords

DEPLOYMENT:
Set these environment variables in FastMCP Cloud:
- GOOGLE_OAUTH_CLIENT_ID=<your_oauth_client_id>
- GOOGLE_OAUTH_CLIENT_SECRET=<your_oauth_client_secret>
- GOOGLE_ADS_DEVELOPER_TOKEN=<your_developer_token>
- RENDER_EXTERNAL_URL=https://digital-magenta-bee.fastmcp.app

Google Cloud Console Setup:
- Add redirect URI: https://digital-magenta-bee.fastmcp.app/oauth/callback
- Enable Google Ads API
- Add scope: https://www.googleapis.com/auth/adwords
"""


# ============================================================================
# Run Server with OAuth Discovery
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "7070"))
    host = os.getenv("HOST", "0.0.0.0")
    
    # Get HTTP app from FastMCP
    app = mcp.http_app()
    
    if oauth:
        # Add OAuth routes for Claude's auto-discovery
        # This adds /.well-known/oauth-authorization-server endpoint
        for route in oauth.get_routes(mcp_path="/mcp"):
            app.router.routes.append(route)
        logger.info("✅ OAuth discovery routes added to FastMCP app")
    else:
        logger.warning("⚠️  OAuth not configured - Claude connect button will not work")
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  Google Ads MCP with OAuth Auto-Discovery for Claude        ║
╚══════════════════════════════════════════════════════════════╝

Server URL: http://{host}:{port}
MCP Endpoint: http://{host}:{port}/mcp
OAuth Discovery: http://{host}:{port}/.well-known/oauth-authorization-server

OAuth Status: {'✅ ENABLED' if oauth else '❌ Disabled'}
  
How it works:
  1. Deploy to FastMCP Cloud
  2. Claude Desktop reads /.well-known/oauth-authorization-server
  3. Claude shows "Connect" button automatically
  4. User clicks "Connect" → OAuth flow starts
  5. No manual JSON configuration needed!

Environment Variables:
  GOOGLE_OAUTH_CLIENT_ID: {'✅ Set' if GOOGLE_OAUTH_CLIENT_ID else '❌ Missing'}
  GOOGLE_OAUTH_CLIENT_SECRET: {'✅ Set' if GOOGLE_OAUTH_CLIENT_SECRET else '❌ Missing'}
  GOOGLE_ADS_DEVELOPER_TOKEN: {'✅ Set' if os.getenv('GOOGLE_ADS_DEVELOPER_TOKEN') else '❌ Missing'}

Press Ctrl+C to stop
""")
    
    # Run with uvicorn directly (like your original mcp_server.py)
    uvicorn.run(app, host=host, port=port)
