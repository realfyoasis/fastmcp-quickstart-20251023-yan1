# 🚀 Quick Deployment Fix

## ✅ The Problem

Error: `cannot import name 'GoogleProvider' from 'fastmcp.server.auth'`

## ✅ The Solution

The code has been fixed! `GoogleProvider` doesn't exist in FastMCP Cloud. Instead, OAuth is configured via environment variables.

---

## 📋 Deployment Checklist

### Step 1: Set Environment Variables in FastMCP Cloud

Go to your FastMCP Cloud dashboard and add these environment variables:

```bash
FASTMCP_SERVER_AUTH=google
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-your-secret
GOOGLE_ADS_DEVELOPER_TOKEN=your-developer-token
RENDER_EXTERNAL_URL=https://digital-magenta-bee.fastmcp.app
```

**Important:** Replace with your actual values!

### Step 2: Update Google Cloud Console

Add this redirect URI to your OAuth client:
```
https://digital-magenta-bee.fastmcp.app/auth/callback
```

### Step 3: Deploy the Fixed Code

```bash
git add googleads_final.py
git commit -m "Fix: Use environment-based OAuth"
git push
```

---

## 🧪 Test After Deployment

### 1. Check the server starts without errors

Look for this in logs:
```
INFO - Starting Google Ads MCP Server with FastMCP Cloud OAuth
```

**NOT this:**
```
ERROR - Failed to run: cannot import name 'GoogleProvider'
```

### 2. Test OAuth endpoint

Visit in browser:
```
https://digital-magenta-bee.fastmcp.app/auth/login
```

Should redirect to Google sign-in.

### 3. Connect from Claude Desktop

```json
{
  "mcpServers": {
    "google-ads": {
      "url": "https://digital-magenta-bee.fastmcp.app/mcp",
      "auth": "oauth"
    }
  }
}
```

---

## 🔍 What Was Changed

### Before (Broken)
```python
from fastmcp.server.auth import GoogleProvider  # ❌ Doesn't exist!

auth = GoogleProvider(client_id="...", ...)
mcp = FastMCP("Server", auth=auth)
```

### After (Fixed)
```python
from fastmcp import FastMCP, Context

# ✅ OAuth configured via environment variables
mcp = FastMCP("Google Ads MCP")
```

---

## ✅ Success Indicators

After deployment, you should see:

**Server Logs:**
```
INFO - Starting Google Ads MCP Server
INFO - Server running on port 7070
```

**OAuth Test:**
- Visit `/auth/login` → Redirects to Google
- Sign in → Redirects back to `/auth/callback`
- No errors in logs

**Claude Desktop:**
- Shows "Connect" button
- Clicking opens browser for OAuth
- After auth, tools work

---

## 🐛 If Still Not Working

### Check Environment Variables
```bash
# In FastMCP Cloud dashboard, verify all are set:
FASTMCP_SERVER_AUTH=google ✓
GOOGLE_OAUTH_CLIENT_ID=... ✓
GOOGLE_OAUTH_CLIENT_SECRET=... ✓
GOOGLE_ADS_DEVELOPER_TOKEN=... ✓
RENDER_EXTERNAL_URL=https://... ✓
```

### Check Google Cloud Console
- OAuth redirect URI matches exactly (no trailing slashes!)
- Google Ads API is enabled
- Scopes include `https://www.googleapis.com/auth/adwords`

### Check Logs
```bash
# Look for authentication-related messages
# Should NOT see "GoogleProvider" errors
# Should see OAuth endpoint registration
```

---

## 🎉 Ready!

Once deployed with the fixed code and correct environment variables, your Google Ads MCP server will work with OAuth authentication!

The key insight: **FastMCP Cloud doesn't use `GoogleProvider` class - it uses environment variables.**
