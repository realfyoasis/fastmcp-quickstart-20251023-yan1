# FastMCP Cloud OAuth Setup - FIXED!

## ✅ Issue Fixed!

The error **"cannot import name 'GoogleProvider'"** was caused by trying to import a class that doesn't exist in the current FastMCP version.

**FastMCP Cloud uses environment-based OAuth configuration instead.**

---

## 🔧 Environment Variables for OAuth

FastMCP Cloud automatically configures OAuth when you set these environment variables:

```bash
# Required for OAuth
FASTMCP_SERVER_AUTH=google
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-your-secret
RENDER_EXTERNAL_URL=https://your-app.fastmcp.app

# Required for Google Ads API
GOOGLE_ADS_DEVELOPER_TOKEN=your-developer-token
```

---

## 📋 Setup Steps

### 1. Set Environment Variables in FastMCP Cloud

When deploying, add these environment variables:

```bash
FASTMCP_SERVER_AUTH=google
GOOGLE_OAUTH_CLIENT_ID=123456789-abc.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-your_secret_here
GOOGLE_ADS_DEVELOPER_TOKEN=your_developer_token
RENDER_EXTERNAL_URL=https://digital-magenta-bee.fastmcp.app
```

### 2. Configure Google Cloud OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **APIs & Services > Credentials**
3. Edit your OAuth 2.0 Client ID
4. Add authorized redirect URI:
   ```
   https://digital-magenta-bee.fastmcp.app/auth/callback
   ```
5. Add required scopes:
   - `https://www.googleapis.com/auth/adwords`
   - `openid`
   - `email`
   - `profile`

### 3. Deploy

```bash
# Push to git
git add .
git commit -m "Fix OAuth configuration"
git push

# Or use FastMCP CLI
fastmcp deploy
```

### 1. Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create or select a project
3. Enable **Google Ads API**
4. Go to **APIs & Services → Credentials**
5. Create **OAuth 2.0 Client ID** (Web application)
6. Add authorized redirect URI:
   ```
   https://your-fastmcp-cloud-url.com/auth/callback
   ```
   For local testing:
   ```
   http://localhost:7070/auth/callback
   ```
7. Note your **Client ID** and **Client Secret**
8. Get a **Developer Token** from your Google Ads account

### 2. FastMCP Cloud Environment Variables

Set these in your FastMCP Cloud deployment:

```bash
# Enable Google OAuth provider
FASTMCP_SERVER_AUTH=fastmcp.server.auth.providers.google.GoogleProvider

# OAuth credentials
FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID=123456789.apps.googleusercontent.com
FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET=GOCSPX-abc123...
FASTMCP_SERVER_AUTH_GOOGLE_BASE_URL=https://your-fastmcp-cloud-url.com

# Google Ads API credentials
GOOGLE_ADS_DEVELOPER_TOKEN=your_developer_token_here

# Optional: Manager account ID
GOOGLE_ADS_LOGIN_CUSTOMER_ID=1234567890
```

### 3. Deploy to FastMCP Cloud

```bash
# Use the new OAuth-enabled server
fastmcp deploy googleads_oauth.py
```

Or update your `fastmcp.json`:
```json
{
  "$schema": "https://gofastmcp.com/public/schemas/fastmcp.json/v1.json",
  "source": {
    "path": "googleads_oauth.py",
    "entrypoint": "mcp"
  },
  "environment": {
    "type": "uv"
  }
}
```

## 📝 Usage Flow for Users

### First Time Setup (Per User):

1. **User opens Claude Desktop**
2. **User connects to your MCP server**
3. **Claude shows available tools**
4. **User tries to use a tool** (e.g., `list_accessible_accounts`)
5. **Server responds: "Not authenticated. Visit /auth/login"**
6. **User visits** `https://your-server.com/auth/login` **in browser**
7. **User logs in with Google**
8. **User grants permissions**
9. **User returns to Claude**
10. **User can now use all tools** (their tokens are automatically used)

### Subsequent Use:

- User's session is maintained (via cookies or JWT)
- Tools automatically use their stored tokens
- No need to authenticate again until session expires
- FastMCP automatically refreshes access tokens

## 🔧 Available Tools

All tools automatically use the authenticated user's credentials:

```python
# Check your authentication status
get_auth_status()

# List YOUR Google Ads accounts
list_accessible_accounts()

# Get performance summary for YOUR account
get_account_summary(customer_id="123-456-7890", days=30)

# Get YOUR campaigns
get_campaigns(customer_id="123-456-7890", days=30, limit=100)

# Get YOUR keywords
get_keywords(customer_id="123-456-7890", days=30, limit=100)
```

## 🔒 Security Features

1. **Per-User Isolation**: Each user's session is separate
2. **No Shared Credentials**: No single refresh token shared across users
3. **Automatic Token Refresh**: FastMCP refreshes expired access tokens
4. **Secure Storage**: Tokens stored in encrypted sessions (managed by FastMCP)
5. **OAuth 2.0**: Industry-standard authentication
6. **Scoped Access**: Users only grant specific permissions

## 🧪 Local Testing

```powershell
# Set environment variables
$env:FASTMCP_SERVER_AUTH="fastmcp.server.auth.providers.google.GoogleProvider"
$env:FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_ID="your_client_id"
$env:FASTMCP_SERVER_AUTH_GOOGLE_CLIENT_SECRET="your_client_secret"
$env:FASTMCP_SERVER_AUTH_GOOGLE_BASE_URL="http://localhost:7070"
$env:GOOGLE_ADS_DEVELOPER_TOKEN="your_dev_token"

# Run the server
python googleads_oauth.py
```

Visit `http://localhost:7070/auth/login` to test OAuth flow.

## 📊 How It Works Internally

```
User A Request → FastMCP → Extracts User A's session
                         → Gets User A's tokens from session
                         → Passes to GoogleAdsService
                         → Returns User A's data

User B Request → FastMCP → Extracts User B's session
                         → Gets User B's tokens from session
                         → Passes to GoogleAdsService
                         → Returns User B's data
```

FastMCP's `AuthenticatedContext` object contains:
```python
context.user = {
    "id": "user_unique_id",
    "email": "user@example.com",
    "access_token": "ya29.a0...",
    "refresh_token": "1//0gS...",
    # other user-specific data
}
```

## 🆚 Old vs New Approach

### ❌ Old (Single User):
- One `.oauth_tokens.json` file
- All users share the same token
- User B could see User A's data
- Manual token passing in every request

### ✅ New (Multi-User):
- FastMCP manages sessions
- Each user has their own token
- Automatic token isolation
- Automatic token refresh
- Context-based authentication

## 🔍 Troubleshooting

### "User not authenticated" error:
→ User needs to visit `/auth/login`

### "No access or refresh token available":
→ Session expired, user needs to re-authenticate

### "GOOGLE_ADS_DEVELOPER_TOKEN not set":
→ Set environment variable in FastMCP Cloud

### Redirect URI mismatch:
→ Ensure Google Cloud Console redirect URI exactly matches `<BASE_URL>/auth/callback`

## 📚 References

- [FastMCP Authentication Docs](https://gofastmcp.com/servers/auth/authentication)
- [FastMCP Google Provider](https://gofastmcp.com/integrations/google)
- [Google Ads API OAuth](https://developers.google.com/google-ads/api/docs/oauth/overview)
