"""
Google Ads MCP Server with FastMCP Built-in OAuth Authentication
Uses FastMCP's GoogleProvider for zero-configuration OAuth setup.
"""

import os
import logging
from typing import List, Dict, Optional
from dataclasses import is_dataclass, asdict

from fastmcp import FastMCP, Context
from fastmcp.server.auth import GoogleProvider

try:
    from core.services.google_ads_service import GoogleAdsService
except ImportError:
    class GoogleAdsService:
        def __init__(self, user_credentials: dict):
            raise RuntimeError("Missing core/services/google_ads_service.py")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------
# FastMCP Authentication Setup (Enterprise-Grade OAuth)
# --------------------------------------------------------------------
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID") or os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET")
BASE_URL = os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:7070"

# Initialize GoogleProvider with required scopes for Google Ads API
auth = None
if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    auth = GoogleProvider(
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        base_url=BASE_URL.rstrip("/"),
        scopes=[
            "https://www.googleapis.com/auth/adwords",
            "openid",
            "email",
            "profile"
        ]
    )
    logger.info("✅ FastMCP GoogleProvider initialized - OAuth enabled")
else:
    logger.warning("⚠️ Missing OAuth credentials - server will run without authentication")

# Create FastMCP server with authentication
mcp = FastMCP("Google Ads MCP", auth=auth)

# --------------------------------------------------------------------
# Helper Functions
# --------------------------------------------------------------------
def _get_user_credentials_from_context(ctx: Context) -> dict:
    """
    Extract OAuth credentials from FastMCP's authenticated context.
    FastMCP GoogleProvider automatically injects user credentials after OAuth flow.
    """
    # FastMCP auth providers inject authenticated user into context
    if not ctx or not hasattr(ctx, 'user') or not ctx.user:
        raise RuntimeError(
            "Not authenticated. Please authenticate via OAuth flow. "
            "Client usage: Client('https://your-server.com/mcp', auth='oauth')"
        )
    
    user = ctx.user
    
    # FastMCP GoogleProvider stores tokens in user object
    access_token = None
    refresh_token = None
    
    # Try different attribute access patterns
    if isinstance(user, dict):
        access_token = user.get('access_token')
        refresh_token = user.get('refresh_token')
    else:
        access_token = getattr(user, 'access_token', None)
        refresh_token = getattr(user, 'refresh_token', None)
    
    if not access_token and not refresh_token:
        raise RuntimeError(
            "No OAuth tokens found in authenticated context. "
            "Ensure GoogleProvider is configured with correct scopes."
        )
    
    # Build credentials dict for GoogleAdsService
    credentials = {
        "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
    }
    
    if access_token:
        credentials["access_token"] = access_token
    if refresh_token:
        credentials["refresh_token"] = refresh_token
    
    # Add OAuth client credentials for token refresh
    if GOOGLE_CLIENT_ID:
        credentials["client_id"] = GOOGLE_CLIENT_ID
    if GOOGLE_CLIENT_SECRET:
        credentials["client_secret"] = GOOGLE_CLIENT_SECRET
    
    if not credentials["developer_token"]:
        raise ValueError(
            "GOOGLE_ADS_DEVELOPER_TOKEN environment variable is required. "
            "Get it from: https://ads.google.com/aw/apicenter"
        )
    
    return credentials


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
        except Exception:
            out.append({"raw": str(a)})

    return out


# --------------------------------------------------------------------
# MCP Tools - Credentials automatically from OAuth context
# --------------------------------------------------------------------
@mcp.tool
def list_accessible_accounts(ctx: Context) -> List[Dict]:
    """
    List all Google Ads accounts you can access.
    
    Authentication is handled automatically via OAuth.
    No manual credentials needed!
    
    Returns:
        List of account objects with id, name, is_manager, currency, timezone
    """
    try:
        # Get credentials from authenticated context (injected by FastMCP OAuth)
        credentials = _get_user_credentials_from_context(ctx)
        
        # Create service with user's OAuth credentials
        service = GoogleAdsService(user_credentials=credentials)
        
        # Fetch accounts
        accounts = service.get_accessible_accounts()
        
        return _normalize_accounts(accounts)
    except Exception as e:
        raise RuntimeError(f"Failed to list accounts: {str(e)}")


@mcp.tool
def get_account_summary(ctx: Context, customer_id: str, days: int = 30) -> Dict:
    """
    Get performance summary for a Google Ads account.
    
    Authentication is handled automatically via OAuth.
    
    Args:
        customer_id: Google Ads customer ID (with or without dashes)
        days: Lookback window in days (default: 30)
    
    Returns:
        Dictionary with account performance metrics
    """
    try:
        credentials = _get_user_credentials_from_context(ctx)
        service = GoogleAdsService(user_credentials=credentials)
        
        summary = service.get_account_summary(customer_id, days)
        return summary or {"message": f"No data found for account {customer_id}"}
    except Exception as e:
        raise RuntimeError(f"Failed to get account summary: {str(e)}")


@mcp.tool
def get_campaigns(ctx: Context, customer_id: str, days: int = 30, limit: int = 100) -> List[Dict]:
    """
    Get campaigns for a specific Google Ads account.
    
    Args:
        customer_id: Google Ads customer ID
        days: Lookback window in days (default: 30)
        limit: Maximum number of campaigns to return (default: 100)
    """
    try:
        credentials = _get_user_credentials_from_context(ctx)
        service = GoogleAdsService(user_credentials=credentials)
        
        campaigns = service.get_campaigns(customer_id, days, limit)
        return _normalize_accounts(campaigns)
    except Exception as e:
        raise RuntimeError(f"Failed to get campaigns: {str(e)}")


@mcp.tool
def get_keywords(
    ctx: Context,
    customer_id: str,
    campaign_id: Optional[str] = None,
    days: int = 30,
    limit: int = 100
) -> List[Dict]:
    """
    Get keywords for a specific Google Ads account.
    
    Args:
        customer_id: Google Ads customer ID
        campaign_id: Optional campaign ID to filter by
        days: Lookback window in days (default: 30)
        limit: Maximum number of keywords to return (default: 100)
    """
    try:
        credentials = _get_user_credentials_from_context(ctx)
        service = GoogleAdsService(user_credentials=credentials)
        
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
Google Ads MCP Server - FastMCP Built-in OAuth Authentication

AUTHENTICATION - Enterprise-Grade, Zero Configuration:
✅ FastMCP GoogleProvider with automatic browser-based OAuth
✅ Token refresh and persistent storage handled automatically
✅ Production-ready security with comprehensive error handling

CONNECTING FROM CLAUDE DESKTOP:
Add to your Claude Desktop configuration:

{
  "mcpServers": {
    "google-ads": {
      "url": "https://your-server.fastmcp.app/mcp",
      "auth": "oauth"
    }
  }
}

That's it! Claude will automatically:
1. Launch browser for Google OAuth
2. Store tokens securely
3. Refresh tokens when needed
4. Handle all authentication flows

CONNECTING FROM PYTHON CLIENT:
```python
from fastmcp import Client

async with Client("https://your-server.fastmcp.app/mcp", auth="oauth") as client:
    # Automatic browser-based OAuth flow on first connection
    accounts = await client.call_tool("list_accessible_accounts")
    print(accounts)
```

TOOLS AVAILABLE:
• list_accessible_accounts() - List your Google Ads accounts
• get_account_summary(customer_id, days=30) - Get account performance
• get_campaigns(customer_id, days=30, limit=100) - Get campaigns
• get_keywords(customer_id, campaign_id?, days=30, limit=100) - Get keywords

DEPLOYMENT ENVIRONMENT VARIABLES:
Required:
- GOOGLE_OAUTH_CLIENT_ID=<your_oauth_client_id>
- GOOGLE_OAUTH_CLIENT_SECRET=<your_oauth_client_secret>
- GOOGLE_ADS_DEVELOPER_TOKEN=<your_developer_token>
- RENDER_EXTERNAL_URL=https://your-server.fastmcp.app

GOOGLE CLOUD CONSOLE SETUP:
1. Create OAuth 2.0 Client ID (Web application)
2. Add authorized redirect URI:
   https://your-server.fastmcp.app/auth/callback
3. Enable Google Ads API
4. Add required scopes:
   - https://www.googleapis.com/auth/adwords
   - openid
   - email
   - profile

WHY FASTMCP AUTH IS BETTER:
✓ Zero-config OAuth - just pass auth="oauth"
✓ Automatic token refresh
✓ Persistent credential storage
✓ Browser-based flow with local callback server
✓ Enterprise-ready security
✓ Full OIDC support
✓ Works with any OAuth provider

Get your Developer Token: https://ads.google.com/aw/apicenter
"""


# ============================================================================
# Run
# ============================================================================
if __name__ == "__main__":
    import asyncio
    
    port = int(os.getenv("PORT", "7070"))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info("Starting Google Ads MCP Server with FastMCP Cloud OAuth")
    logger.info(f"Server URL: http://{host}:{port}")
    
    asyncio.run(mcp.run_http_async(host=host, port=port))
