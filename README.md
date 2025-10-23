# Google Ads MCP Server

**Enterprise-grade Google Ads API access via FastMCP with zero-configuration OAuth.**

## 🚀 Quick Start (3 Steps)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
```bash
export GOOGLE_OAUTH_CLIENT_ID="your-id.apps.googleusercontent.com"
export GOOGLE_OAUTH_CLIENT_SECRET="GOCSPX-your-secret"
export GOOGLE_ADS_DEVELOPER_TOKEN="your-developer-token"
export RENDER_EXTERNAL_URL="http://localhost:7070"
```

### 3. Run Server
```bash
python googleads_final.py
```

**Test it:**
```bash
python example_client.py
```

Browser will open for Google sign-in. After authentication, your Google Ads accounts will be displayed!

---

## ✨ Features

- ✅ **Zero-Config OAuth** - Just pass `auth="oauth"` to connect
- ✅ **Automatic Token Refresh** - Never worry about expired tokens
- ✅ **Enterprise Security** - FastMCP's battle-tested authentication
- ✅ **Claude Desktop Ready** - One-line configuration
- ✅ **Python Client** - Simple async API access

---

## 🔌 Usage

### Python Client

```python
from fastmcp import Client

async with Client("http://localhost:7070/mcp", auth="oauth") as client:
    accounts = await client.call_tool("list_accessible_accounts")
    print(accounts)
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "google-ads": {
      "url": "http://localhost:7070/mcp",
      "auth": "oauth"
    }
  }
}
```

---

## 🛠️ Available Tools

- **`list_accessible_accounts()`** - List all accessible Google Ads accounts
- **`get_account_summary(customer_id, days=30)`** - Get performance metrics
- **`get_campaigns(customer_id, days=30, limit=100)`** - Get campaigns
- **`get_keywords(customer_id, campaign_id?, days=30, limit=100)`** - Get keywords

---

## 📚 Documentation

- **[Deployment Guide](DEPLOYMENT_GUIDE.md)** - Complete deployment instructions
- **[Authentication Guide](AUTHENTICATION_GUIDE.md)** - FastMCP auth explained
- **[Implementation Summary](IMPLEMENTATION_SUMMARY.md)** - Architecture overview

---

## 🔒 Security

This server uses **FastMCP's enterprise-grade authentication**:

- ✅ Persistent token storage with encryption
- ✅ Automatic token refresh
- ✅ Full OIDC compliance
- ✅ Comprehensive error handling
- ✅ Production-ready security

Same system used by major corporations for OAuth authentication.

---

## 🎯 Why FastMCP?

| Feature | Manual OAuth | **FastMCP** |
|---------|--------------|-------------|
| Setup | 100+ lines | **2 lines** |
| Token Refresh | Manual | **Automatic** |
| Client Config | Complex JSON | **`auth="oauth"`** |
| Security Audit | Required | **Pre-audited** |
| Production Ready | Testing needed | **Battle-tested** |

---

## 🐛 Troubleshooting

**"redirect_uri_mismatch"**
→ Add `http://localhost:7070/auth/callback` to Google Cloud Console

**"Not authenticated"**
→ Delete `~/.fastmcp/tokens/` and re-run

**"Invalid developer token"**
→ Check token is approved in [Google Ads API Center](https://ads.google.com/aw/apicenter)

---

## 📖 Learn More

- **FastMCP**: https://gofastmcp.com/
- **Google Ads API**: https://developers.google.com/google-ads/api
- **MCP Protocol**: https://modelcontextprotocol.io/

---

## 🎉 Ready to Deploy?

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for production deployment instructions.

**Questions?** Open an issue or check the [FastMCP documentation](https://gofastmcp.com/).

