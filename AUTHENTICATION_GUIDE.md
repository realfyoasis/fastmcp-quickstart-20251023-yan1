# FastMCP Authentication - Quick Reference

## 🎯 What Changed

**BEFORE (Your Old Code):**
```python
# Complex manual OAuth setup
oauth = OAuthProxy(...)
app = FastAPI()
# Manual token handling
# Manual route registration
# No automatic refresh
```

**NOW (FastMCP Built-in):**
```python
# Two lines of code!
auth = GoogleProvider(client_id="...", client_secret="...", base_url="...")
mcp = FastMCP("Google Ads MCP", auth=auth)

# That's it! Everything else is automatic.
```

---

## 🔑 Key Benefits

| Feature | Manual OAuth | FastMCP GoogleProvider |
|---------|--------------|------------------------|
| **Setup** | 100+ lines | 2 lines |
| **Token Storage** | Manual | Automatic |
| **Token Refresh** | Manual | Automatic |
| **Error Handling** | Custom | Built-in |
| **Browser Flow** | Manual | Automatic |
| **Client Connection** | Complex JSON | `auth="oauth"` |
| **Production Ready** | Requires testing | Battle-tested |

---

## 📝 Environment Variables

```bash
# Required for FastMCP GoogleProvider
GOOGLE_OAUTH_CLIENT_ID="your-id.apps.googleusercontent.com"
GOOGLE_OAUTH_CLIENT_SECRET="GOCSPX-your-secret"
RENDER_EXTERNAL_URL="https://your-server.fastmcp.app"
GOOGLE_ADS_DEVELOPER_TOKEN="your-developer-token"
```

---

## 🔌 Connection Examples

### Claude Desktop
```json
{
  "mcpServers": {
    "google-ads": {
      "url": "https://your-server.fastmcp.app/mcp",
      "auth": "oauth"  ← This triggers automatic OAuth!
    }
  }
}
```

### Python Client
```python
from fastmcp import Client

# Automatic browser-based OAuth - zero configuration!
async with Client("https://your-server.fastmcp.app/mcp", auth="oauth") as client:
    result = await client.call_tool("list_accessible_accounts")
```

---

## 🎭 How It Works

1. **Server Side** (Your Code):
   ```python
   auth = GoogleProvider(client_id="...", client_secret="...", base_url="...")
   mcp = FastMCP("Google Ads MCP", auth=auth)
   ```
   - FastMCP automatically adds `/auth/login`, `/auth/callback` endpoints
   - Handles token storage, refresh, and validation
   - Injects authenticated user into tool context

2. **Client Side** (Claude/Python):
   ```python
   Client("https://server.com/mcp", auth="oauth")
   ```
   - Detects OAuth endpoints automatically
   - Launches browser for user authentication
   - Stores tokens locally in `~/.fastmcp/tokens/`
   - Refreshes tokens automatically when needed

3. **Tool Execution**:
   ```python
   @mcp.tool
   def list_accessible_accounts(ctx: Context):
       credentials = _get_user_credentials_from_context(ctx)
       # ctx.user automatically populated by FastMCP!
   ```

---

## 🚨 Common Mistakes (Avoid These!)

### ❌ DON'T: Mix authentication patterns
```python
# DON'T do this - pick one!
from fastmcp.server.auth.oauth_proxy import OAuthProxy
auth = OAuthProxy(...)  # Old pattern
mcp = FastMCP("Server", auth=GoogleProvider(...))  # New pattern
```

### ✅ DO: Use GoogleProvider
```python
# Clean and simple!
from fastmcp.server.auth import GoogleProvider
auth = GoogleProvider(client_id="...", client_secret="...", base_url="...")
mcp = FastMCP("Server", auth=auth)
```

### ❌ DON'T: Add manual auth parameters
```python
@mcp.tool
def my_tool(ctx: Context, auth: dict):  # DON'T!
    pass
```

### ✅ DO: Extract from context
```python
@mcp.tool
def my_tool(ctx: Context):  # Clean signature
    credentials = _get_user_credentials_from_context(ctx)
    # ctx.user populated automatically by FastMCP
```

---

## 🔍 Debugging

### Check Authentication Status

```python
@mcp.tool
def debug_auth(ctx: Context):
    """Debug endpoint to check authentication"""
    return {
        "authenticated": bool(ctx and ctx.user),
        "user": str(ctx.user) if ctx and ctx.user else None,
        "has_access_token": bool(getattr(ctx.user, 'access_token', None)) if ctx and ctx.user else False,
        "has_refresh_token": bool(getattr(ctx.user, 'refresh_token', None)) if ctx and ctx.user else False
    }
```

### Enable Debug Logging

```bash
export FASTMCP_LOG_LEVEL=DEBUG
python googleads_final.py
```

### Test OAuth Flow Manually

```bash
# Open in browser
https://your-server.fastmcp.app/auth/login

# Should redirect to Google sign-in
# Then redirect back to /auth/callback
# Check server logs for token storage
```

---

## 📊 Architecture Comparison

### Old Architecture (Manual)
```
Client → Manual OAuth Setup
  ↓
  Token Exchange
  ↓
  Manual Storage
  ↓
  Pass tokens manually
  ↓
  Server validates manually
  ↓
  Tool extracts from auth param
```

### New Architecture (FastMCP)
```
Client (auth="oauth")
  ↓
  FastMCP auto-detects endpoints
  ↓
  Browser flow (automatic)
  ↓
  FastMCP stores tokens
  ↓
  FastMCP validates & injects ctx.user
  ↓
  Tool extracts from context
  
Everything automatic! 🎉
```

---

## 🎓 Why This Matters

**Production Readiness:**
- ✅ Battle-tested by companies in production
- ✅ Comprehensive error handling
- ✅ Automatic token refresh (prevents downtime)
- ✅ Secure credential storage
- ✅ Full OIDC compliance

**Developer Experience:**
- ✅ 2 lines of code vs 100+
- ✅ Zero-config client connection
- ✅ Automatic browser launch
- ✅ Clear error messages
- ✅ Works with all major OAuth providers

**Enterprise Features:**
- ✅ WorkOS SSO integration
- ✅ Azure Active Directory support
- ✅ Auth0 tenant support
- ✅ Dynamic Client Registration (DCR)
- ✅ Custom JWT validation

---

## 🚀 Next Steps

1. **Test locally:**
   ```bash
   python googleads_final.py
   python example_client.py
   ```

2. **Deploy to production:**
   ```bash
   fastmcp deploy
   ```

3. **Add to Claude Desktop:**
   ```json
   {"url": "https://your-server.com/mcp", "auth": "oauth"}
   ```

4. **Build amazing things!** 🎉

---

## 📚 Learn More

- **FastMCP Docs**: https://gofastmcp.com/
- **Auth Guide**: https://gofastmcp.com/authentication
- **Examples**: https://github.com/jlowin/fastmcp/tree/main/examples
