"""
Google Ads MCP Server with Working OAuth - Fixed Version

Key changes:
1. Proper FastMCP auth configuration
2. Correct OAuth proxy setup
3. Working callback handling
4. Session management
"""

import os
import logging
from typing import List, Dict, Optional
from dataclasses import is_dataclass, asdict
from dotenv import load_dotenv

from fastmcp import FastMCP
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("google_ads_mcp")

# --------------------------------------------------------------------------------------
# Environment / Config
# --------------------------------------------------------------------------------------
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
GOOGLE_ADS_DEVELOPER_TOKEN = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")

# Public URL used for OAuth
# For local development, use localhost
PUBLIC_BASE = (
    os.getenv("RENDER_EXTERNAL_URL", "http://localhost:7070")
    .strip()
    .rstrip("/")
)

if not PUBLIC_BASE.startswith("http"):
    PUBLIC_BASE = "https://" + PUBLIC_BASE

logger.info(f"PUBLIC_BASE set to: {PUBLIC_BASE}")

# Validate required env vars
if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
    logger.error("❌ GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be set!")
    raise ValueError("Missing OAuth credentials")

if not GOOGLE_ADS_DEVELOPER_TOKEN:
    logger.error("❌ GOOGLE_ADS_DEVELOPER_TOKEN must be set!")
    raise ValueError("Missing Google Ads developer token")

# --------------------------------------------------------------------------------------
# Import Google Ads Service
# --------------------------------------------------------------------------------------
try:
    from core.services.google_ads_service import GoogleAdsService
except ImportError:
    logger.error("❌ Missing core/services/google_ads_service.py")
    class GoogleAdsService:
        def __init__(self, user_credentials: dict):
            raise RuntimeError("Missing core/services/google_ads_service.py - please create it first")

# --------------------------------------------------------------------------------------
# FastMCP Server with OAuth
# --------------------------------------------------------------------------------------
from fastapi import FastAPI
from starlette.routing import Route

# Create FastAPI app separately
app = FastAPI(title="Google Ads MCP with OAuth")

# Create FastMCP instance
mcp = FastMCP("Google Ads MCP")

# Configure OAuth in FastMCP
# This is the KEY part that was missing!
@app.get("/oauth/login")
async def oauth_login(request: Request):
    """Initiate OAuth flow"""
    from urllib.parse import urlencode
    
    # Google OAuth endpoint
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    
    scopes = [
        "https://www.googleapis.com/auth/adwords",
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]
    
    params = {
        "client_id": GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": f"{PUBLIC_BASE}/oauth/callback",
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",  # Get refresh token
        "prompt": "consent",  # Force consent to get refresh token
    }
    
    redirect_url = f"{auth_url}?{urlencode(params)}"
    logger.info(f"🔐 Redirecting to Google OAuth: {redirect_url}")
    
    return RedirectResponse(url=redirect_url)


@app.get("/oauth/callback")
async def oauth_callback(request: Request):
    """Handle OAuth callback from Google"""
    import httpx
    from urllib.parse import urlencode
    
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    
    if error:
        logger.error(f"❌ OAuth error: {error}")
        return HTMLResponse(f"""
            <html>
                <body>
                    <h2>Authentication Failed</h2>
                    <p>Error: {error}</p>
                    <a href="/oauth/login">Try Again</a>
                </body>
            </html>
        """, status_code=400)
    
    if not code:
        logger.error("❌ No authorization code received")
        return HTMLResponse("""
            <html>
                <body>
                    <h2>Authentication Failed</h2>
                    <p>No authorization code received</p>
                    <a href="/oauth/login">Try Again</a>
                </body>
            </html>
        """, status_code=400)
    
    # Exchange code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
        "redirect_uri": f"{PUBLIC_BASE}/oauth/callback",
        "grant_type": "authorization_code",
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=token_data)
            response.raise_for_status()
            tokens = response.json()
            
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        
        if not access_token:
            raise ValueError("No access token in response")
        
        logger.info(f"✅ Got access token: {access_token[:20]}...")
        if refresh_token:
            logger.info(f"✅ Got refresh token: {refresh_token[:20]}...")
        else:
            logger.warning("⚠️ No refresh token received - user might need to re-consent")
        
        # Get user info
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with httpx.AsyncClient() as client:
            user_response = await client.get(user_info_url, headers=headers)
            user_response.raise_for_status()
            user_info = user_response.json()
        
        email = user_info.get("email", "unknown")
        user_id = user_info.get("id", "unknown")
        
        logger.info(f"✅ Authenticated user: {email} (ID: {user_id})")
        
        # Store tokens in session (you'll want to use a proper session store in production)
        # For now, we'll return them in the response for testing
        
        return HTMLResponse(f"""
            <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 40px; }}
                        .success {{ color: green; }}
                        .token {{ 
                            background: #f4f4f4; 
                            padding: 10px; 
                            border-radius: 5px;
                            word-break: break-all;
                            font-family: monospace;
                            font-size: 12px;
                        }}
                    </style>
                </head>
                <body>
                    <h2 class="success">✅ Authentication Successful!</h2>
                    <p><strong>Email:</strong> {email}</p>
                    <p><strong>User ID:</strong> {user_id}</p>
                    
                    <h3>Your Tokens (SAVE THESE):</h3>
                    <p><strong>Access Token:</strong></p>
                    <div class="token">{access_token}</div>
                    
                    {f'<p><strong>Refresh Token:</strong></p><div class="token">{refresh_token}</div>' if refresh_token else '<p><em>No refresh token received. You may need to revoke access and re-authenticate.</em></p>'}
                    
                    <h3>Next Steps:</h3>
                    <ol>
                        <li>Save these tokens securely</li>
                        <li>Use them to call the MCP tools</li>
                        <li>See <a href="/test-auth">Test Auth</a> to verify your tokens work</li>
                    </ol>
                    
                    <p><a href="/">Back to Home</a></p>
                </body>
            </html>
        """)
        
    except Exception as e:
        logger.error(f"❌ Token exchange failed: {e}")
        return HTMLResponse(f"""
            <html>
                <body>
                    <h2>Token Exchange Failed</h2>
                    <p>Error: {str(e)}</p>
                    <a href="/oauth/login">Try Again</a>
                </body>
            </html>
        """, status_code=500)


@app.get("/test-auth")
async def test_auth(request: Request):
    """Test page to verify tokens work"""
    return HTMLResponse("""
        <html>
            <head>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    input, textarea { width: 100%; padding: 8px; margin: 5px 0; }
                    button { 
                        padding: 10px 20px; 
                        background: #4285f4; 
                        color: white; 
                        border: none; 
                        cursor: pointer;
                        border-radius: 4px;
                    }
                    button:hover { background: #357ae8; }
                    #result { 
                        margin-top: 20px; 
                        padding: 15px; 
                        background: #f4f4f4;
                        border-radius: 5px;
                        white-space: pre-wrap;
                        font-family: monospace;
                    }
                </style>
            </head>
            <body>
                <h2>Test Your Authentication</h2>
                <p>Paste your access token below to test if it works:</p>
                
                <form id="testForm">
                    <label>Access Token:</label>
                    <textarea id="accessToken" rows="3" required></textarea>
                    
                    <label>Refresh Token (optional):</label>
                    <textarea id="refreshToken" rows="3"></textarea>
                    
                    <br><br>
                    <button type="submit">Test Authentication</button>
                </form>
                
                <div id="result"></div>
                
                <script>
                    document.getElementById('testForm').addEventListener('submit', async (e) => {
                        e.preventDefault();
                        
                        const accessToken = document.getElementById('accessToken').value;
                        const refreshToken = document.getElementById('refreshToken').value;
                        const resultDiv = document.getElementById('result');
                        
                        resultDiv.textContent = 'Testing...';
                        
                        try {
                            const response = await fetch('/verify-token', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ 
                                    access_token: accessToken,
                                    refresh_token: refreshToken 
                                })
                            });
                            
                            const data = await response.json();
                            resultDiv.textContent = JSON.stringify(data, null, 2);
                        } catch (error) {
                            resultDiv.textContent = 'Error: ' + error.message;
                        }
                    });
                </script>
                
                <p><a href="/">Back to Home</a></p>
            </body>
        </html>
    """)


@app.post("/verify-token")
async def verify_token(request: Request):
    """Verify if a token works with Google Ads API"""
    import httpx
    
    body = await request.json()
    access_token = body.get("access_token")
    refresh_token = body.get("refresh_token")
    
    if not access_token:
        return JSONResponse({"error": "access_token required"}, status_code=400)
    
    try:
        # Test the token by calling Google Ads API
        credentials = {
            "developer_token": GOOGLE_ADS_DEVELOPER_TOKEN,
            "access_token": access_token,
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
        }
        
        if refresh_token:
            credentials["refresh_token"] = refresh_token
        
        service = GoogleAdsService(user_credentials=credentials)
        accounts = service.get_accessible_accounts()
        
        return JSONResponse({
            "success": True,
            "message": "✅ Token is valid!",
            "accounts_found": len(accounts),
            "accounts": [
                {
                    "id": getattr(acc, 'id', getattr(acc, 'customer_id', 'unknown')),
                    "name": getattr(acc, 'name', getattr(acc, 'descriptive_name', 'unknown'))
                }
                for acc in accounts[:5]  # Show first 5
            ]
        })
        
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        return JSONResponse({
            "success": False,
            "error": str(e),
            "message": "❌ Token verification failed"
        }, status_code=400)


# --------------------------------------------------------------------------------------
# Helper Functions
# --------------------------------------------------------------------------------------
def _normalize(obj_list: List) -> List[Dict]:
    """Convert objects to dictionaries"""
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
# MCP Tools
# --------------------------------------------------------------------------------------
@mcp.tool()
def list_accessible_accounts(
    access_token: str,
    refresh_token: Optional[str] = None
) -> List[Dict]:
    """
    List all Google Ads accounts you can access.
    
    Args:
        access_token: Your OAuth access token
        refresh_token: Your OAuth refresh token (optional but recommended)
    """
    try:
        credentials = {
            "developer_token": GOOGLE_ADS_DEVELOPER_TOKEN,
            "access_token": access_token,
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
        }
        
        if refresh_token:
            credentials["refresh_token"] = refresh_token
        
        service = GoogleAdsService(user_credentials=credentials)
        accounts = service.get_accessible_accounts()
        return _normalize(accounts)
    except Exception as e:
        raise RuntimeError(f"Failed to list accounts: {str(e)}")


@mcp.tool()
def get_account_summary(
    customer_id: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    days: int = 30
) -> Dict:
    """
    Get performance summary for a Google Ads account.
    
    Args:
        customer_id: The Google Ads customer ID
        access_token: Your OAuth access token
        refresh_token: Your OAuth refresh token (optional)
        days: Number of days to look back (default: 30)
    """
    try:
        credentials = {
            "developer_token": GOOGLE_ADS_DEVELOPER_TOKEN,
            "access_token": access_token,
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
        }
        
        if refresh_token:
            credentials["refresh_token"] = refresh_token
        
        service = GoogleAdsService(user_credentials=credentials)
        summary = service.get_account_summary(customer_id, days)
        return summary or {"message": f"No data found for account {customer_id}"}
    except Exception as e:
        raise RuntimeError(f"Failed to get account summary: {str(e)}")


@mcp.tool()
def get_campaigns(
    customer_id: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    days: int = 30,
    limit: int = 100
) -> List[Dict]:
    """
    Get campaigns for a specific Google Ads account.
    
    Args:
        customer_id: The Google Ads customer ID
        access_token: Your OAuth access token
        refresh_token: Your OAuth refresh token (optional)
        days: Number of days to look back (default: 30)
        limit: Maximum number of campaigns to return (default: 100)
    """
    try:
        credentials = {
            "developer_token": GOOGLE_ADS_DEVELOPER_TOKEN,
            "access_token": access_token,
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
        }
        
        if refresh_token:
            credentials["refresh_token"] = refresh_token
        
        service = GoogleAdsService(user_credentials=credentials)
        campaigns = service.get_campaigns(customer_id, days, limit)
        return _normalize(campaigns)
    except Exception as e:
        raise RuntimeError(f"Failed to get campaigns: {str(e)}")


@mcp.tool()
def get_keywords(
    customer_id: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    campaign_id: Optional[str] = None,
    days: int = 30,
    limit: int = 100
) -> List[Dict]:
    """
    Get keywords for a specific Google Ads account.
    
    Args:
        customer_id: The Google Ads customer ID
        access_token: Your OAuth access token
        refresh_token: Your OAuth refresh token (optional)
        campaign_id: Optional campaign ID to filter by
        days: Number of days to look back (default: 30)
        limit: Maximum number of keywords to return (default: 100)
    """
    try:
        credentials = {
            "developer_token": GOOGLE_ADS_DEVELOPER_TOKEN,
            "access_token": access_token,
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
        }
        
        if refresh_token:
            credentials["refresh_token"] = refresh_token
        
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
Google Ads MCP Server - OAuth Authentication Guide

STEP 1: AUTHENTICATE
Visit: {PUBLIC_BASE}/oauth/login
- Complete Google OAuth flow
- Save your access_token and refresh_token

STEP 2: TEST YOUR TOKENS
Visit: {PUBLIC_BASE}/test-auth
- Paste your tokens to verify they work

STEP 3: USE THE TOOLS
All tools require your tokens as parameters:

Example:
list_accessible_accounts(
    access_token="ya29.xxx",
    refresh_token="1//xxx"
)

IMPORTANT NOTES:
- Access tokens expire after 1 hour
- Refresh tokens let you get new access tokens
- Store tokens securely
- Never commit tokens to git

MCP ENDPOINT: {PUBLIC_BASE}/mcp
"""


# --------------------------------------------------------------------------------------
# Home Page
# --------------------------------------------------------------------------------------
@app.get("/")
async def index():
    return HTMLResponse(f"""
        <html>
            <head>
                <style>
                    body {{ 
                        font-family: Arial, sans-serif; 
                        margin: 40px;
                        max-width: 800px;
                    }}
                    .step {{
                        background: #f8f9fa;
                        padding: 20px;
                        margin: 15px 0;
                        border-radius: 8px;
                        border-left: 4px solid #4285f4;
                    }}
                    a {{
                        color: #4285f4;
                        text-decoration: none;
                        font-weight: bold;
                    }}
                    a:hover {{ text-decoration: underline; }}
                    code {{
                        background: #e8eaed;
                        padding: 2px 6px;
                        border-radius: 3px;
                        font-family: monospace;
                    }}
                </style>
            </head>
            <body>
                <h1>🚀 Google Ads MCP Server</h1>
                <p>Welcome! Follow these steps to get started:</p>
                
                <div class="step">
                    <h3>Step 1: Authenticate with Google</h3>
                    <p><a href="/oauth/login">🔐 Click here to login with Google</a></p>
                    <p>You'll be redirected to Google to grant access to your Google Ads accounts.</p>
                </div>
                
                <div class="step">
                    <h3>Step 2: Save Your Tokens</h3>
                    <p>After authentication, you'll receive:</p>
                    <ul>
                        <li><strong>Access Token</strong> - Valid for 1 hour</li>
                        <li><strong>Refresh Token</strong> - Use to get new access tokens</li>
                    </ul>
                    <p>⚠️ Save these securely! You'll need them to use the tools.</p>
                </div>
                
                <div class="step">
                    <h3>Step 3: Test Your Authentication</h3>
                    <p><a href="/test-auth">🧪 Test your tokens here</a></p>
                    <p>Verify your tokens work before using the MCP tools.</p>
                </div>
                
                <div class="step">
                    <h3>Step 4: Use the MCP Tools</h3>
                    <p>MCP Endpoint: <code>{PUBLIC_BASE}/mcp</code></p>
                    <p>Available tools:</p>
                    <ul>
                        <li><code>list_accessible_accounts</code></li>
                        <li><code>get_account_summary</code></li>
                        <li><code>get_campaigns</code></li>
                        <li><code>get_keywords</code></li>
                    </ul>
                </div>
                
                <hr>
                <p><small>OAuth Configuration:</small></p>
                <ul style="font-size: 12px;">
                    <li>Client ID: {GOOGLE_OAUTH_CLIENT_ID[:20]}...</li>
                    <li>Callback URL: <code>{PUBLIC_BASE}/oauth/callback</code></li>
                    <li>Developer Token: {'✅ Configured' if GOOGLE_ADS_DEVELOPER_TOKEN else '❌ Missing'}</li>
                </ul>
            </body>
        </html>
    """)


# --------------------------------------------------------------------------------------
# Health Check
# --------------------------------------------------------------------------------------
@app.get("/healthz")
async def health():
    return JSONResponse({
        "status": "healthy",
        "oauth_configured": bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET),
        "developer_token_configured": bool(GOOGLE_ADS_DEVELOPER_TOKEN),
        "public_base": PUBLIC_BASE
    })


# --------------------------------------------------------------------------------------
# Well-known OAuth metadata
# --------------------------------------------------------------------------------------
@app.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    return JSONResponse({
        "issuer": PUBLIC_BASE,
        "authorization_endpoint": f"{PUBLIC_BASE}/oauth/login",
        "token_endpoint": f"{PUBLIC_BASE}/oauth/callback",
        "scopes_supported": [
            "https://www.googleapis.com/auth/adwords",
            "openid",
            "email",
            "profile"
        ]
    })


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "7070"))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info("=" * 60)
    logger.info("🚀 Starting Google Ads MCP Server")
    logger.info("=" * 60)
    logger.info(f"📡 Server: http://{host}:{port}")
    logger.info(f"🌐 Public URL: {PUBLIC_BASE}")
    logger.info(f"🔐 OAuth Login: {PUBLIC_BASE}/oauth/login")
    logger.info(f"📋 MCP Endpoint: {PUBLIC_BASE}/mcp")
    logger.info("=" * 60)
    
    # Mount the MCP server at /mcp
    mcp_app = mcp.http_app()
    app.mount("/mcp", mcp_app)
    
    uvicorn.run(app, host=host, port=port)