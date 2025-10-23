"""
Google Ads MCP Server with FastMCP Cloud OAuth Auto-Discovery
Credentials are automatically injected by FastMCP - no manual auth parameter needed!
"""

import os
import logging
from typing import List, Dict, Optional
from dataclasses import is_dataclass, asdict

from fastmcp import FastMCP, Context

try:
    from core.services.google_ads_service import GoogleAdsService
except ImportError:
    class GoogleAdsService:
        def __init__(self, user_credentials: dict):
            raise RuntimeError("Missing core/services/google_ads_service.py")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP server
mcp = FastMCP("Google Ads MCP")

# --------------------------------------------------------------------
# Helper Functions
# --------------------------------------------------------------------
def _get_user_credentials_from_context(ctx: Context) -> dict:
    """
    Extract OAuth credentials from FastMCP's authenticated context.
    FastMCP Cloud automatically injects these after OAuth flow.
    """
    # FastMCP injects user info into context after OAuth
    if not hasattr(ctx, 'user') or not ctx.user:
        raise RuntimeError(
            "Not authenticated. Please connect via Claude Desktop OAuth flow. "
            "Your FastMCP server should be configured with Google OAuth provider."
        )
    
    user = ctx.user
    
    # Extract tokens from user object
    access_token = getattr(user, 'access_token', None) or (user.get('access_token') if isinstance(user, dict) else None)
    refresh_token = getattr(user, 'refresh_token', None) or (user.get('refresh_token') if isinstance(user, dict) else None)
    
    if not access_token and not refresh_token:
        raise RuntimeError(
            "No OAuth tokens found in context. "
            "Ensure FASTMCP_SERVER_AUTH is configured correctly."
        )
    
    # Build credentials dict for GoogleAdsService
    credentials = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "client_id": os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID") or os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
        "client_secret": os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET") or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
        "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
    }
    
    if not credentials["developer_token"]:
        raise ValueError("GOOGLE_ADS_DEVELOPER_TOKEN environment variable is required")
    
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
Google Ads MCP Server - OAuth Auto-Authentication

AUTHENTICATION:
✅ Automatic via Claude Desktop OAuth flow
✅ No manual credentials needed
✅ Each user's data is automatically isolated

HOW IT WORKS:
1. Add this server to Claude Desktop (remote MCP)
2. Claude detects OAuth configuration
3. Click "Connect" button
4. Sign in with Google
5. Tools automatically use your credentials

TOOLS:
• list_accessible_accounts() - List your Google Ads accounts
• get_account_summary(customer_id, days=30) - Get account performance
• get_campaigns(customer_id, days=30, limit=100) - Get campaigns
• get_keywords(customer_id, campaign_id?, days=30, limit=100) - Get keywords

DEPLOYMENT (FastMCP Cloud):
Set these environment variables:
- FASTMCP_SERVER_AUTH=fastmcp.server.auth.providers.google.GoogleProvider
- FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID=<your_oauth_client_id>
- FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET=<your_oauth_client_secret>
- FASTMCP_SERVER_AUTH_GOOGLE_BASE_URL=<your_fastmcp_url>
- GOOGLE_ADS_DEVELOPER_TOKEN=<your_developer_token>

GOOGLE CLOUD SETUP:
- Create OAuth 2.0 Client ID
- Add redirect URI: <base_url>/auth/callback
- Add scope: https://www.googleapis.com/auth/adwords
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
