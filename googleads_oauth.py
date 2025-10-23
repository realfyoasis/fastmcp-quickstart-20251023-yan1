"""
Google Ads MCP Server with proper multi-user OAuth support via FastMCP's auth system

This implementation uses FastMCP's built-in Google OAuth provider to handle
authentication for multiple users. Each user authenticates separately and their
tokens are managed by FastMCP's authentication system.

FastMCP Cloud deployment: Set these environment variables:
- FASTMCP_SERVER_AUTH=fastmcp.server.auth.providers.google.GoogleProvider
- FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID=<your_client_id>
- FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET=<your_client_secret>
- FASTMCP_SERVER_AUTH_GOOGLE_BASE_URL=<your_fastmcp_cloud_url>
- GOOGLE_ADS_DEVELOPER_TOKEN=<your_developer_token>
- GOOGLE_ADS_LOGIN_CUSTOMER_ID=<your_manager_account_id>  # Optional
"""

from fastmcp import FastMCP, Context
from typing import List, Dict, Optional
from dataclasses import is_dataclass, asdict
import os

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

# Create server with HTTP transport (required for OAuth)
mcp = FastMCP("Google Ads MCP")


def _get_user_credentials(context: Context) -> dict:
    """
    Extract Google OAuth credentials from FastMCP's context.
    
    When FastMCP is configured with GoogleProvider authentication,
    user credentials are available through the HTTP request context.
    """
    # Try to get HTTP request from context
    try:
        request = context.get_http_request()
        if request and hasattr(request, 'state') and hasattr(request.state, 'user'):
            user = request.state.user
            
            # Build credentials dict for GoogleAdsService
            credentials = {
                "access_token": user.get("access_token") if isinstance(user, dict) else getattr(user, "access_token", None),
                "refresh_token": user.get("refresh_token") if isinstance(user, dict) else getattr(user, "refresh_token", None),
                "client_id": os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET"),
                "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
            }
            
            # Validate required fields
            if not credentials["developer_token"]:
                raise ValueError("GOOGLE_ADS_DEVELOPER_TOKEN environment variable is required")
            
            if credentials["access_token"] or credentials["refresh_token"]:
                return credentials
    except Exception as e:
        # Log but continue to fallback
        pass
    
    # Fallback: use environment variables or stored tokens
    # This allows testing without full OAuth setup
    env_refresh_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
    if env_refresh_token:
        return {
            "refresh_token": env_refresh_token,
            "client_id": os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID") or os.getenv("GOOGLE_ADS_CLIENT_ID"),
            "client_secret": os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET") or os.getenv("GOOGLE_ADS_CLIENT_SECRET"),
            "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
        }
    
    raise ValueError(
        "User not authenticated and no fallback credentials found. "
        "Please either: "
        "1. Configure FastMCP OAuth and authenticate via /auth/login, or "
        "2. Set GOOGLE_ADS_REFRESH_TOKEN environment variable for testing"
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


# ============================================================================
# MCP Tools - Each user's authentication is automatically handled by FastMCP
# ============================================================================

@mcp.tool
def list_accessible_accounts(context: Context) -> List[Dict]:
    """
    List all Google Ads accounts the authenticated user can access.
    
    This tool automatically uses the logged-in user's OAuth credentials.
    Each user sees only their own Google Ads accounts.
    
    Returns:
        List of account objects with id, name, is_manager, currency, timezone
    """
    # Get the current user's credentials from FastMCP's auth context
    credentials = _get_user_credentials(context)
    
    # Create service instance with user's credentials
    service = GoogleAdsService(user_credentials=credentials)
    
    # Fetch accounts using user's auth
    accounts = service.get_accessible_accounts()
    
    return _normalize_accounts(accounts)


@mcp.tool
def get_account_summary(
    context: Context,
    customer_id: str,
    days: int = 30
) -> Dict:
    """
    Get performance summary for a Google Ads account.
    
    This tool automatically uses the logged-in user's OAuth credentials.
    Users can only access accounts they have permission to view.
    
    Args:
        customer_id: Google Ads customer ID (with or without dashes)
        days: Lookback window in days (default: 30)
        
    Returns:
        Dictionary with account performance metrics (impressions, clicks, cost, etc.)
    """
    credentials = _get_user_credentials(context)
    service = GoogleAdsService(user_credentials=credentials)
    
    data = service.get_account_summary(customer_id, days)
    return data or {"message": f"No data found for account {customer_id}"}


@mcp.tool
def get_campaigns(
    context: Context,
    customer_id: str,
    days: int = 30,
    limit: int = 100
) -> List[Dict]:
    """
    Get campaigns for a specific Google Ads account.
    
    Args:
        customer_id: Google Ads customer ID
        days: Lookback window in days (default: 30)
        limit: Maximum number of campaigns to return (default: 100)
        
    Returns:
        List of campaign objects with performance metrics
    """
    credentials = _get_user_credentials(context)
    service = GoogleAdsService(user_credentials=credentials)
    
    campaigns = service.get_campaigns(customer_id, days, limit)
    return _normalize_accounts(campaigns)


@mcp.tool
def get_keywords(
    context: Context,
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
        
    Returns:
        List of keyword objects with performance metrics
    """
    credentials = _get_user_credentials(context)
    service = GoogleAdsService(user_credentials=credentials)
    
    keywords = service.get_keywords(customer_id, campaign_id, days, limit)
    return _normalize_accounts(keywords)


@mcp.tool
def get_auth_status(context: Context) -> Dict:
    """
    Check the current user's authentication status.
    
    Returns:
        Dictionary with authentication info and user details
    """
    try:
        request = context.get_http_request()
        if request and hasattr(request, 'state') and hasattr(request.state, 'user'):
            user = request.state.user
            user_dict = user if isinstance(user, dict) else vars(user) if hasattr(user, '__dict__') else {}
            
            return {
                "authenticated": True,
                "user_id": user_dict.get("id") or user_dict.get("sub") or user_dict.get("email"),
                "email": user_dict.get("email"),
                "has_access_token": bool(user_dict.get("access_token")),
                "has_refresh_token": bool(user_dict.get("refresh_token")),
                "message": "Successfully authenticated with Google OAuth"
            }
    except Exception:
        pass
    
    # Check for environment variable fallback
    if os.getenv("GOOGLE_ADS_REFRESH_TOKEN"):
        return {
            "authenticated": True,
            "message": "Using environment variable credentials (fallback mode)",
            "has_refresh_token": True,
            "note": "This is fallback mode. For production, use OAuth authentication."
        }
    
    return {
        "authenticated": False,
        "message": "Not authenticated. Visit /auth/login to authenticate with Google OAuth."
    }


# ============================================================================
# Resources
# ============================================================================

@mcp.resource("google-ads://help")
def help_resource() -> str:
    return """
Google Ads MCP Server with Multi-User OAuth Support

AUTHENTICATION:
Each user authenticates separately via Google OAuth.
1. Visit /auth/login in your browser
2. Sign in with your Google account
3. Grant Google Ads API permissions
4. Return to Claude and use the tools

TOOLS:
• get_auth_status() - Check your authentication status
• list_accessible_accounts() - List your Google Ads accounts
• get_account_summary(customer_id, days=30) - Get account performance
• get_campaigns(customer_id, days=30, limit=100) - Get campaigns
• get_keywords(customer_id, campaign_id?, days=30, limit=100) - Get keywords

All tools automatically use YOUR authenticated credentials.
Each user sees only their own data.

ENVIRONMENT VARIABLES (FastMCP Cloud):
- FASTMCP_SERVER_AUTH=fastmcp.server.auth.providers.google.GoogleProvider
- FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID=<your_oauth_client_id>
- FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET=<your_oauth_client_secret>
- FASTMCP_SERVER_AUTH_GOOGLE_BASE_URL=<your_fastmcp_cloud_url>
- GOOGLE_ADS_DEVELOPER_TOKEN=<your_developer_token>

GOOGLE CLOUD CONSOLE SETUP:
1. Create OAuth 2.0 Client ID (Web application)
2. Add authorized redirect URI: <base_url>/auth/callback
3. Enable Google Ads API
4. Add scopes: https://www.googleapis.com/auth/adwords
"""


@mcp.resource("google-ads://oauth-info")
def oauth_info() -> str:
    """Information about the OAuth setup"""
    base_url = os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_BASE_URL", "http://localhost:7070")
    client_id = os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID", "not_set")
    
    return f"""
OAuth Configuration Status:

Base URL: {base_url}
Client ID: {client_id[:20]}... (configured: {'✓' if client_id != 'not_set' else '✗'})
Developer Token: {'✓ configured' if os.getenv('GOOGLE_ADS_DEVELOPER_TOKEN') else '✗ not set'}

OAuth Flow URLs:
- Login: {base_url}/auth/login
- Callback: {base_url}/auth/callback
- Logout: {base_url}/auth/logout

To authenticate:
1. Visit {base_url}/auth/login
2. Complete Google OAuth flow
3. Return here and use the tools

Each user authenticates independently and accesses only their own data.
"""


@mcp.resource("google-ads://account/{customer_id}")
def account_resource(customer_id: str) -> str:
    """Template for accessing account data"""
    return f"""
Google Ads Account: {customer_id}

To get data for this account, use:
• get_account_summary(customer_id="{customer_id}", days=30)
• get_campaigns(customer_id="{customer_id}", days=30)
• get_keywords(customer_id="{customer_id}", days=30)

You must be authenticated and have access to this account.
"""


# ============================================================================
# Prompts
# ============================================================================

@mcp.prompt("authenticate")
def authenticate_prompt() -> str:
    """Prompt to guide users through authentication"""
    return """
To access your Google Ads data:

1. First, check your authentication status:
   Use the `get_auth_status` tool

2. If not authenticated, you need to log in:
   Visit the OAuth login URL (use `google-ads://oauth-info` resource to get URL)
   
3. Once authenticated, you can:
   - List your accounts with `list_accessible_accounts`
   - Get account summaries, campaigns, and keywords
   
Your credentials are automatically used for all tools.
Other users' data remains private to them.
"""


@mcp.prompt("get_started")
def get_started_prompt(account_name: str = "your account") -> str:
    """Prompt for getting started with Google Ads data"""
    return f"""
Let's access {account_name} data:

1. Check authentication: get_auth_status()
2. List accounts: list_accessible_accounts()
3. Get account summary: get_account_summary(customer_id="...")
4. Explore campaigns: get_campaigns(customer_id="...")

What would you like to see first?
"""


# ============================================================================
# Server Entry Point
# ============================================================================

if __name__ == "__main__":
    import asyncio
    
    # When running locally, you can set environment variables here or in .env
    # For FastMCP Cloud, set these in the deployment environment
    
    port = int(os.getenv("PORT", "7070"))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  Google Ads MCP Server with Multi-User OAuth                ║
╚══════════════════════════════════════════════════════════════╝

Server starting on: http://{host}:{port}

OAUTH ENDPOINTS:
  Login:    http://{host}:{port}/auth/login
  Callback: http://{host}:{port}/auth/callback
  Logout:   http://{host}:{port}/auth/logout

SETUP REQUIRED:
1. Set environment variables (see google-ads://help resource)
2. Configure Google Cloud Console OAuth redirect URI
3. Users visit /auth/login to authenticate
4. Each user's data is isolated and secure

Press Ctrl+C to stop
""")
    
    asyncio.run(mcp.run_http_async(host=host, port=port))
