# Quick Setup Guide for Local Development

## Prerequisites
- Python 3.11+ installed ✅ (You have Python 3.11.9)
- Virtual environment set up ✅ (You have .venv)
- Dependencies installed ✅ (All packages installed)

## Step 1: Configure Your Credentials

Edit the `.env` file with your actual credentials:

```env
GOOGLE_OAUTH_CLIENT_ID=YOUR_ACTUAL_CLIENT_ID.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=YOUR_ACTUAL_CLIENT_SECRET
GOOGLE_ADS_DEVELOPER_TOKEN=YOUR_ACTUAL_DEVELOPER_TOKEN
```

### Where to get these credentials:

1. **Google OAuth Client ID & Secret**:
   - Go to: https://console.cloud.google.com/apis/credentials
   - Create a new OAuth 2.0 Client ID (Web application)
   - Add authorized redirect URI: `http://localhost:7070/oauth/callback`
   - Save your Client ID and Client Secret

2. **Google Ads Developer Token**:
   - Go to: https://ads.google.com/aw/apicenter
   - Request access to the Google Ads API
   - Copy your developer token

## Step 2: Run the Server

### Option A: Using the PowerShell script (Recommended)
```powershell
.\run.ps1
```

### Option B: Manual activation
```powershell
.venv\Scripts\Activate.ps1
python googleads_final.py
```

## Step 3: Access the Application

Once running, open your browser to:
- **Home Page**: http://localhost:7070
- **OAuth Login**: http://localhost:7070/oauth/login
- **Test Auth**: http://localhost:7070/test-auth
- **Health Check**: http://localhost:7070/healthz

## Step 4: Authenticate

1. Click "Login with Google" on the home page
2. Grant permissions to your Google Ads account
3. Save the access_token and refresh_token displayed
4. Use these tokens to call the MCP tools

## Troubleshooting

### Port already in use?
Change the PORT in `.env`:
```env
PORT=8080
```

### Missing dependencies?
```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### OAuth redirect URI mismatch?
Make sure your Google Cloud Console OAuth configuration includes:
- Authorized redirect URI: `http://localhost:7070/oauth/callback`
- Match the PORT in your `.env` file

## Next Steps

Once authenticated, you can:
- Test the MCP tools from Claude Desktop
- Use the API endpoints programmatically
- Integrate with other MCP clients

Happy coding! 🚀
