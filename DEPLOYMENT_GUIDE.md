# Google Ads MCP Server - Deployment Guide

## ✨ FastMCP Built-in OAuth Authentication

This server uses **FastMCP's enterprise-grade OAuth authentication** - the same system used by major corporations for production deployments.

### 🎯 Key Features

- ✅ **Zero-Configuration OAuth** - Just pass `auth="oauth"` to connect
- ✅ **Automatic Token Refresh** - Never worry about expired tokens
- ✅ **Persistent Storage** - Tokens stored securely for reuse
- ✅ **Browser-Based Flow** - Automatic browser launch with local callback
- ✅ **Enterprise Security** - Full OIDC support, comprehensive error handling
- ✅ **Production Ready** - Used in production by companies worldwide

---

## 🚀 Quick Start (3 Steps)

### 1. Set Environment Variables

```bash
# Google OAuth Credentials
export GOOGLE_OAUTH_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export GOOGLE_OAUTH_CLIENT_SECRET="GOCSPX-your-secret"

# Google Ads API Developer Token
export GOOGLE_ADS_DEVELOPER_TOKEN="your-developer-token"

# Your server's public URL (for OAuth redirect)
export RENDER_EXTERNAL_URL="https://your-server.fastmcp.app"
```

### 2. Deploy to FastMCP Cloud

```bash
# Install FastMCP CLI
pip install fastmcp

# Deploy (automatically detects googleads_final.py)
fastmcp deploy
```

### 3. Connect from Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "google-ads": {
      "url": "https://your-server.fastmcp.app/mcp",
      "auth": "oauth"
    }
  }
}
```

**That's it!** Claude will automatically handle OAuth when you first use the server.

---

## 📋 Detailed Setup

### Step 1: Google Cloud Console Setup

#### Create OAuth 2.0 Client

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services** → **Credentials**
3. Click **+ CREATE CREDENTIALS** → **OAuth client ID**
4. Choose **Web application**
5. Add **Authorized redirect URIs**:
   ```
   https://your-server.fastmcp.app/auth/callback
   http://localhost:7070/auth/callback  (for local testing)
   ```
6. Save and copy your **Client ID** and **Client Secret**

#### Enable Google Ads API

1. In Google Cloud Console, go to **APIs & Services** → **Library**
2. Search for "Google Ads API"
3. Click **ENABLE**

#### Get Developer Token

1. Go to [Google Ads API Center](https://ads.google.com/aw/apicenter)
2. Apply for API access (may take 24-48 hours for approval)
3. Copy your **Developer Token**

### Step 2: Environment Variables

Create a `.env` file or set in your deployment platform:

```bash
# Required
GOOGLE_OAUTH_CLIENT_ID=123456789-abcdefg.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-your_secret_here
GOOGLE_ADS_DEVELOPER_TOKEN=your_developer_token_here

# Deployment URL (change for production)
RENDER_EXTERNAL_URL=https://your-server.fastmcp.app

# Optional: Override defaults
PORT=7070
HOST=0.0.0.0
```

### Step 3: Deploy

#### Option A: FastMCP Cloud (Recommended)

```bash
pip install fastmcp
fastmcp deploy
```

FastMCP CLI will:
- Package your server automatically
- Deploy to cloud infrastructure
- Configure OAuth endpoints
- Provide your server URL

#### Option B: Render.com

1. Connect your GitHub repo
2. Set environment variables in Render dashboard
3. Deploy as Web Service
4. Use the Render URL as your `RENDER_EXTERNAL_URL`

#### Option C: Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
python googleads_final.py
```

Server will start at `http://localhost:7070`

---

## 🔌 Client Usage

### Python Client (FastMCP)

```python
from fastmcp import Client
import asyncio

async def main():
    # Zero-config OAuth - automatic browser launch
    async with Client("https://your-server.fastmcp.app/mcp", auth="oauth") as client:
        # First time: browser opens for Google sign-in
        # Subsequent times: uses stored tokens automatically
        
        accounts = await client.call_tool("list_accessible_accounts")
        print(f"Found {len(accounts)} accounts")
        
        for account in accounts:
            summary = await client.call_tool(
                "get_account_summary",
                customer_id=account['id'],
                days=30
            )
            print(f"{account['name']}: ${summary['spend']}")

asyncio.run(main())
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "google-ads": {
      "url": "https://your-server.fastmcp.app/mcp",
      "auth": "oauth"
    }
  }
}
```

Restart Claude Desktop. When you first use Google Ads tools, Claude will:
1. Show an "Authenticate" button
2. Open browser for Google sign-in
3. Request Google Ads API permissions
4. Store tokens for future use

### Direct HTTP Calls

```bash
# Not recommended - use FastMCP Client for automatic OAuth
curl -X POST https://your-server.fastmcp.app/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "list_accessible_accounts"
    }
  }'
```

---

## 🛠️ Available Tools

### `list_accessible_accounts()`
List all Google Ads accounts you can access.

**Returns:**
```json
[
  {
    "id": "1234567890",
    "name": "My Business",
    "is_manager": false,
    "currency": "USD",
    "timezone": "America/New_York"
  }
]
```

### `get_account_summary(customer_id, days=30)`
Get performance metrics for an account.

**Parameters:**
- `customer_id` (string): Google Ads customer ID
- `days` (integer): Lookback period (default: 30)

**Returns:**
```json
{
  "spend": 1250.50,
  "clicks": 1234,
  "impressions": 45678,
  "conversions": 23,
  "ctr": 2.7,
  "cpc": 1.01
}
```

### `get_campaigns(customer_id, days=30, limit=100)`
Get campaigns for an account.

**Parameters:**
- `customer_id` (string): Google Ads customer ID
- `days` (integer): Lookback period (default: 30)
- `limit` (integer): Max campaigns to return (default: 100)

### `get_keywords(customer_id, campaign_id?, days=30, limit=100)`
Get keywords for an account or campaign.

**Parameters:**
- `customer_id` (string): Google Ads customer ID
- `campaign_id` (string, optional): Filter by campaign
- `days` (integer): Lookback period (default: 30)
- `limit` (integer): Max keywords to return (default: 100)

---

## 🔒 Security Best Practices

### Production Deployment

1. **Never commit credentials** - Use environment variables
2. **Use HTTPS** - Always use `https://` for production URLs
3. **Restrict OAuth scopes** - Only request necessary permissions
4. **Monitor token usage** - FastMCP logs all authentication events
5. **Regular token rotation** - FastMCP handles this automatically

### OAuth Redirect URIs

Add all URLs where your server runs:

```
Production:  https://your-server.fastmcp.app/auth/callback
Staging:     https://staging.fastmcp.app/auth/callback
Local Dev:   http://localhost:7070/auth/callback
```

### Environment Variable Storage

**Never hardcode credentials!** Use:

- **Local Development**: `.env` file (add to `.gitignore`)
- **Render.com**: Environment variables in dashboard
- **FastMCP Cloud**: Set via CLI or dashboard
- **Docker**: Pass via `-e` flags or env file

---

## 🐛 Troubleshooting

### "Not authenticated" error

**Problem:** Tools fail with authentication error

**Solutions:**
1. Check environment variables are set correctly
2. Verify OAuth redirect URI matches exactly (trailing slashes matter!)
3. Ensure `RENDER_EXTERNAL_URL` matches your actual server URL
4. Try removing stored tokens: `rm -rf ~/.fastmcp/tokens/`

### "redirect_uri_mismatch" error

**Problem:** OAuth fails with redirect URI mismatch

**Solution:** Add the exact redirect URI to Google Cloud Console:
```
https://your-actual-server-url.com/auth/callback
```

### "Invalid developer token" error

**Problem:** Google Ads API rejects requests

**Solutions:**
1. Verify `GOOGLE_ADS_DEVELOPER_TOKEN` is set correctly
2. Check token is approved (not in test mode)
3. Ensure billing is enabled in Google Ads account
4. Wait 24-48 hours if token was just created

### Browser doesn't open for OAuth

**Problem:** No browser window appears for authentication

**Solutions:**
1. Check you're using `auth="oauth"` in Client
2. Ensure server's `/auth/callback` endpoint is accessible
3. Try manually opening: `https://your-server.com/auth/login`

### Tokens expire quickly

**Problem:** Need to re-authenticate frequently

**FastMCP handles this automatically!** If you're seeing this:
1. Check FastMCP version: `pip install --upgrade fastmcp`
2. Verify token storage permissions: `~/.fastmcp/tokens/`
3. Enable logging to see refresh attempts: `FASTMCP_LOG_LEVEL=DEBUG`

---

## 📚 Additional Resources

- **FastMCP Documentation**: https://gofastmcp.com/
- **Google Ads API**: https://developers.google.com/google-ads/api
- **OAuth 2.0 Guide**: https://developers.google.com/identity/protocols/oauth2
- **MCP Protocol**: https://modelcontextprotocol.io/

---

## 🎉 You're Ready!

Your Google Ads MCP server is now deployed with enterprise-grade authentication!

**Next Steps:**
1. Test with the example client: `python example_client.py`
2. Add to Claude Desktop for AI-powered ad management
3. Build custom integrations using FastMCP Client
4. Monitor usage in server logs

**Questions?** Check the [FastMCP Documentation](https://gofastmcp.com/) or open an issue on GitHub.
