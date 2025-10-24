# 🔗 Connecting to Claude Desktop via ngrok

## Your Current Setup

✅ **MCP Server URL**: `https://306a9ed164a3.ngrok-free.app/mcp`

This is **CORRECT**! ✅

## How to Configure Claude Desktop

### Step 1: Find Your Claude Desktop Config File

**Windows Location:**
```
C:\Users\YourUsername\AppData\Roaming\Claude\claude_desktop_config.json
```

**Mac Location:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

### Step 2: Add Your MCP Server Configuration

Edit `claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "google-ads": {
      "url": "https://306a9ed164a3.ngrok-free.app/mcp",
      "transport": "http"
    }
  }
}
```

Or if you already have other servers:

```json
{
  "mcpServers": {
    "existing-server": {
      "command": "some-command"
    },
    "google-ads": {
      "url": "https://306a9ed164a3.ngrok-free.app/mcp",
      "transport": "http"
    }
  }
}
```

### Step 3: Restart Claude Desktop

1. Close Claude Desktop completely (check system tray)
2. Reopen Claude Desktop
3. Claude will now connect to your MCP server!

## Testing the Connection

### Method 1: Check Server Logs

Watch your terminal where the server is running. When Claude connects, you'll see:

```
INFO: POST /mcp HTTP/1.1 200 OK
```

### Method 2: Ask Claude to List Tools

In Claude Desktop, type:

```
What MCP tools do you have access to?
```

Claude should respond with your Google Ads tools:
- `list_accessible_accounts`
- `get_account_summary`
- `get_campaigns`
- `get_keywords`

### Method 3: Test a Tool

Ask Claude:

```
Can you list my Google Ads accounts?
```

Claude will prompt you for authentication or use your saved `google_user_id`.

## Important Notes

### 🔒 ngrok Configuration

Make sure your ngrok tunnel is running:

```bash
ngrok http 7070
```

Your ngrok URL will look like:
```
https://306a9ed164a3.ngrok-free.app
```

**Add `/mcp` to the end** when configuring Claude Desktop!

### 🔄 URL Changes

⚠️ **ngrok free tier URLs change every time you restart ngrok!**

When you restart ngrok:
1. Get the new URL from ngrok terminal
2. Update `claude_desktop_config.json`
3. Restart Claude Desktop

**Solution**: Use ngrok's static domain (paid feature) or configure a custom domain.

### 📱 Multiple Devices

You can use the same ngrok URL from:
- Your laptop
- Your desktop
- Any device that can access the internet

All will connect to your local server!

## Troubleshooting

### ❌ Error: "Cannot connect to MCP server"

**Check:**
1. Is your server running? (`python googleads_final.py`)
2. Is ngrok running? (`ngrok http 7070`)
3. Is the URL in `claude_desktop_config.json` correct?
4. Did you add `/mcp` to the end?
5. Did you restart Claude Desktop?

### ❌ Error: "404 Not Found"

**Fix:**
- Make sure the URL ends with `/mcp`
- Correct: `https://YOUR-URL.ngrok-free.app/mcp` ✅
- Wrong: `https://YOUR-URL.ngrok-free.app` ❌

### ❌ Error: "MCP tools not showing up"

**Fix:**
1. Check Claude Desktop logs:
   - Windows: `%APPDATA%\Claude\logs\`
   - Mac: `~/Library/Logs/Claude/`

2. Verify JSON syntax in config file (use JSONLint.com)

3. Restart Claude Desktop completely

### ✅ Success Indicators

You'll know it's working when you see in your server logs:

```
INFO: POST /mcp HTTP/1.1 200 OK
```

And Claude can see your tools!

## Using the Tools in Claude

### Example 1: List Accounts (Automatic Mode)

```
Claude, can you list my Google Ads accounts?
Use my google_user_id: 118328020788738579058
```

### Example 2: Get Campaigns

```
Claude, show me campaigns for customer ID 1234567890
Use my google_user_id: 118328020788738579058
```

### Example 3: Get Keywords

```
Claude, what are the top keywords for campaign 9876543210?
Customer ID: 1234567890
Use my google_user_id: 118328020788738579058
```

## Advanced: Production Setup

For production, instead of ngrok:

1. **Deploy to Render/Railway/Fly.io**
   - Get a permanent HTTPS URL
   - No need to restart ngrok

2. **Use ngrok Static Domain** (paid)
   ```bash
   ngrok http 7070 --domain=your-static-domain.ngrok-free.app
   ```

3. **Custom Domain with Cloudflare Tunnel** (free!)
   ```bash
   cloudflare tunnel --url localhost:7070
   ```

## Summary

✅ **Your Configuration is Correct:**

```json
{
  "mcpServers": {
    "google-ads": {
      "url": "https://306a9ed164a3.ngrok-free.app/mcp",
      "transport": "http"
    }
  }
}
```

Just make sure:
1. ✅ Server is running
2. ✅ ngrok is running
3. ✅ Claude Desktop config has the `/mcp` endpoint
4. ✅ Claude Desktop is restarted

**You should be good to go!** 🚀
