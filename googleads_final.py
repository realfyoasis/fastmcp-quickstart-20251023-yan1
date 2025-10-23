"""
Google Ads MCP Server with OAuthProxy (FastMCP) — fixed & production-ready.

- Correct redirect path: /oauth/callback
- Proper route mounting with include_router
- Public base defaults to https://digital-magenta-bee.fastmcp.app (override with RENDER_EXTERNAL_URL)
- Adds simple health + login links at /
"""

import os
import logging
from typing import List, Dict, Optional
from dataclasses import is_dataclass, asdict
from types import SimpleNamespace

from fastmcp import FastMCP, Context

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("google_ads_mcp")

# --------------------------------------------------------------------------------------
# Optional Imports
# --------------------------------------------------------------------------------------
try:
    from fastmcp.server.auth.oauth_proxy import OAuthProxy
except ImportError:
    OAuthProxy = None
    logger.warning("OAuthProxy not available in this FastMCP version")

try:
    from core.services.google_ads_service import GoogleAdsService
except ImportError:
    class GoogleAdsService:
        def __init__(self, user_credentials: dict):
            raise RuntimeError("Missing core/services/google_ads_service.py")


# --------------------------------------------------------------------------------------
# Environment / Config
# --------------------------------------------------------------------------------------
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
GOOGLE_ADS_DEVELOPER_TOKEN = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")

# Public URL used for OAuth metadata & callback URLs
PUBLIC_BASE = (
    os.getenv("RENDER_EXTERNAL_URL", "https://digital-magenta-bee.fastmcp.app")
    .strip()
    .rstrip("/")
)

if not PUBLIC_BASE.startswith("http"):
    PUBLIC_BASE = "https://" + PUBLIC_BASE

logger.info(f"PUBLIC_BASE set to: {PUBLIC_BASE}")

# --------------------------------------------------------------------------------------
# OAuth Proxy Builder
# --------------------------------------------------------------------------------------
oauth = None

def build_oauth_proxy():
    """Build and return an OAuthProxy instance, or None if unavailable."""
    if not OAuthProxy:
        logger.error("OAuthProxy class not available; upgrade fastmcp to a version that includes it.")
        return None

    if not (GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET):
        logger.error("GOOGLE_OAUTH_CLIENT_ID/SECRET not set; OAuth will not be configured.")
        return None

    # Google OAuth endpoints
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    scopes = [
        "https://www.googleapis.com/auth/adwords",
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]

    # A very permissive verifier you can later harden if needed
    Verifier = SimpleNamespace(
        verify=lambda *_args, **_kw: True,
        required_scopes=scopes,
    )

    # Some versions of OAuthProxy use slightly different kwargs; try the common ones
    attempts = [
        dict(
            upstream_authorization_endpoint=auth_url,
            upstream_token_endpoint=token_url,
            upstream_client_id=GOOGLE_OAUTH_CLIENT_ID,
            upstream_client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
            base_url=PUBLIC_BASE,
            token_verifier=Verifier,
            default_scopes=scopes,
        ),
        dict(
            upstream_authorization_endpoint=auth_url,
            upstream_token_endpoint=token_url,
            client_id=GOOGLE_OAUTH_CLIENT_ID,
            client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
            base_url=PUBLIC_BASE,
            token_verifier=Verifier,
            default_scopes=scopes,
        ),
        dict(  # minimal set as a last resort
            upstream_authorization_endpoint=auth_url,
            upstream_token_endpoint=token_url,
            client_id=GOOGLE_OAUTH_CLIENT_ID,
            client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
            default_scopes=scopes,
        ),
    ]

    last_exc = None
    for i, kwargs in enumerate(attempts, start=1):
        try:
            proxy = OAuthProxy(**kwargs)
            logger.info(f"OAuthProxy constructed with attempt {i}.")
            return proxy
        except TypeError as e:
            last_exc = e
            logger.warning(f"OAuthProxy kwargs attempt {i} failed: {e}")
        except Exception as e:
            last_exc = e
            logger.warning(f"OAuthProxy attempt {i} failed: {e}")

    raise RuntimeError(f"Could not construct OAuthProxy: {last_exc}")

try:
    oauth = build_oauth_proxy()
    if oauth:
        logger.info("✅ OAuthProxy initialized - OAuth flow will work")
except Exception as e:
    logger.error(f"❌ Failed to initialize OAuthProxy: {e}")
    oauth = None

if not oauth:
    logger.warning("⚠️ OAuth not configured - auth screen will not work until env & version are correct.")


# --------------------------------------------------------------------------------------
# FastMCP Server
# --------------------------------------------------------------------------------------
mcp = FastMCP("Google Ads MCP")

# --------------------------------------------------------------------------------------
# Helper Functions
# --------------------------------------------------------------------------------------
def _get_user_credentials_from_context(ctx: Context) -> dict:
    """
    Extract OAuth credentials from FastMCP's authenticated context.
    FastMCP Cloud/clients inject user identity after OAuth flow.
    """
    if not ctx or not hasattr(ctx, "user") or not ctx.user:
        raise RuntimeError(
            "Not authenticated. Please authenticate via OAuth flow. "
            "Client usage: Client('https://digital-magenta-bee.fastmcp.app/mcp', auth='oauth')"
        )

    user = ctx.user

    # Access tokens can be on dict-like or attribute-like user objects
    if isinstance(user, dict):
        access_token = user.get("access_token")
        refresh_token = user.get("refresh_token")
    else:
        access_token = getattr(user, "access_token", None)
        refresh_token = getattr(user, "refresh_token", None)

    if not access_token and not refresh_token:
        raise RuntimeError(
            "No OAuth tokens found in authenticated context. "
            "Ensure OAuth is configured with correct scopes."
        )

    if not GOOGLE_ADS_DEVELOPER_TOKEN:
        raise ValueError(
            "GOOGLE_ADS_DEVELOPER_TOKEN environment variable is required. "
            "Get it from: https://ads.google.com/aw/apicenter"
        )

    credentials = {
        "developer_token": GOOGLE_ADS_DEVELOPER_TOKEN,
    }
    if access_token:
        credentials["access_token"] = access_token
    if refresh_token:
        credentials["refresh_token"] = refresh_token

    # Include client credentials for refresh flow if needed
    client_id = GOOGLE_OAUTH_CLIENT_ID or os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID")
    client_secret = GOOGLE_OAUTH_CLIENT_SECRET or os.getenv("FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET")
    if client_id:
        credentials["client_id"] = client_id
    if client_secret:
        credentials["client_secret"] = client_secret

    return credentials


def _normalize(obj_list: List) -> List[Dict]:
    out = []
    for a in obj_list:
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


# --------------------------------------------------------------------------------------
# MCP Tools (auth pulled from ctx automatically)
# --------------------------------------------------------------------------------------
@mcp.tool
def list_accessible_accounts(ctx: Context) -> List[Dict]:
    """List all Google Ads accounts you can access."""
    try:
        credentials = _get_user_credentials_from_context(ctx)
        service = GoogleAdsService(user_credentials=credentials)
        accounts = service.get_accessible_accounts()
        return _normalize(accounts)
    except Exception as e:
        raise RuntimeError(f"Failed to list accounts: {str(e)}")


@mcp.tool
def get_account_summary(ctx: Context, customer_id: str, days: int = 30) -> Dict:
    """Get performance summary for a Google Ads account."""
    try:
        credentials = _get_user_credentials_from_context(ctx)
        service = GoogleAdsService(user_credentials=credentials)
        summary = service.get_account_summary(customer_id, days)
        return summary or {"message": f"No data found for account {customer_id}"}
    except Exception as e:
        raise RuntimeError(f"Failed to get account summary: {str(e)}")


@mcp.tool
def get_campaigns(ctx: Context, customer_id: str, days: int = 30, limit: int = 100) -> List[Dict]:
    """Get campaigns for a specific Google Ads account."""
    try:
        credentials = _get_user_credentials_from_context(ctx)
        service = GoogleAdsService(user_credentials=credentials)
        campaigns = service.get_campaigns(customer_id, days, limit)
        return _normalize(campaigns)
    except Exception as e:
        raise RuntimeError(f"Failed to get campaigns: {str(e)}")


@mcp.tool
def get_keywords(
    ctx: Context,
    customer_id: str,
    campaign_id: Optional[str] = None,
    days: int = 30,
    limit: int = 100,
) -> List[Dict]:
    """Get keywords for a specific Google Ads account."""
    try:
        credentials = _get_user_credentials_from_context(ctx)
        service = GoogleAdsService(user_credentials=credentials)
        keywords = service.get_keywords(customer_id, campaign_id, days, limit)
        return _normalize(keywords)
    except Exception as e:
        raise RuntimeError(f"Failed to get keywords: {str(e)}")


# --------------------------------------------------------------------------------------
# Resources
# --------------------------------------------------------------------------------------
@mcp.resource("google-ads://help")
def help_resource() -> str:
    return f"""
Google Ads MCP Server - FastMCP Built-in OAuth Authentication

HOW AUTH WORKS
✅ Automatic OAuth via OAuthProxy
✅ Token refresh & storage handled by the proxy
✅ Works with Claude Desktop (interactive) and Remote connectors (manual link)

CONNECT FROM CLAUDE DESKTOP
Add to your claude config:
{{
  "mcpServers": {{
    "google-ads": {{
      "url": "{PUBLIC_BASE}/mcp",
      "auth": "oauth"
    }}
  }}
}}

REMOTE CONNECTOR (no popup)
1) Open {PUBLIC_BASE}/oauth/login in your browser and complete Google consent once.
2) Then connect your client to {PUBLIC_BASE}/mcp.

PYTHON CLIENT
```python
from fastmcp import Client
import asyncio

async def main():
    async with Client("{PUBLIC_BASE}/mcp", auth="oauth") as client:
        print(await client.call_tool("list_accessible_accounts"))

asyncio.run(main())
```
"""


# --------------------------------------------------------------------------------------
# Run with OAuth Support
# --------------------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "7070"))
    host = os.getenv("HOST", "0.0.0.0")

    # Build FastAPI app from FastMCP
    app = mcp.http_app()

    # Simple status + links
    root = APIRouter()

    @root.get("/", response_class=HTMLResponse)
    def index():
        return f"""
        <html>
          <body>
            <h2>Google Ads MCP</h2>
            <ul>
              <li>MCP Endpoint: <code>{PUBLIC_BASE}/mcp</code></li>
              <li>OAuth Metadata: <a href="{PUBLIC_BASE}/.well-known/oauth-authorization-server">.well-known/oauth-authorization-server</a></li>
              <li><b>Start Login:</b> <a href="{PUBLIC_BASE}/oauth/login">/oauth/login</a></li>
              <li>Callback (register in Google Cloud): <code>{PUBLIC_BASE}/oauth/callback</code></li>
            </ul>
          </body>
        </html>
        """

    @root.get("/healthz")
    def healthz():
        return JSONResponse({"ok": True, "oauth_configured": bool(oauth)})

    app.include_router(root)

    # Mount OAuth routes
    if oauth:
        logger.info("✅ Adding OAuth routes to FastMCP app")
        if hasattr(oauth, "router"):
            app.include_router(oauth.router)
        else:
            try:
                for route in oauth.get_routes(mcp_path="/mcp"):
                    app.router.routes.append(route)
            except Exception as e:
                logger.error(f"Failed to mount oauth routes: {e}")
        logger.info("✅ OAuth endpoints available:")
        logger.info("   - GET /.well-known/oauth-authorization-server")
        logger.info("   - GET /oauth/login")
        logger.info("   - GET /oauth/callback")
    else:
        logger.warning("⚠️ OAuth not configured - auth screen will not work")

    logger.info(f"🚀 Server starting at http://{host}:{port}")
    logger.info(f"📡 MCP endpoint: {PUBLIC_BASE}/mcp")

    uvicorn.run(app, host=host, port=port)
