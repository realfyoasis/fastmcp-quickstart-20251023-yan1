# Google Ads MCP Server - Multi-User OAuth Setup

This MCP server implements **proper multi-user OAuth authentication** for Google Ads API access. Each user authenticates separately with their own Google account and can only access their own data.

## 🔐 How Multi-User Authentication Works

### The Flow for Each User:

1. **User A connects to your FastMCP server in Claude**
2. **User A clicks "authenticate" or uses a tool**
3. **FastMCP redirects User A to Google OAuth** (`/auth/login`)
4. **User A signs in with their Google account**
5. **Google redirects back with User A's tokens**
6. **FastMCP stores User A's session** (cookies/JWT)
7. **User A's tools use ONLY their tokens**

8. **User B connects separately**
9. **User B goes through their own OAuth flow**
10. **User B gets their own session with their own tokens**
11. **User B sees ONLY their Google Ads accounts**

### Key Points:
- ✅ Each user has a **separate authenticated session**
- ✅ FastMCP's `AuthenticatedContext` contains the **current user's tokens**
- ✅ Tools receive `context` parameter with the **calling user's credentials**
- ✅ No shared token file - each user's tokens are **session-isolated**
- ✅ User A cannot see User B's data

## 🚀 Setup Instructions

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
