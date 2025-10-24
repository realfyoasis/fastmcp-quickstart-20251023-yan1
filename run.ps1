# Run Google Ads MCP Server Locally
# This script activates the virtual environment and runs the server

Write-Host "🚀 Starting Google Ads MCP Server..." -ForegroundColor Green
Write-Host ""

# Activate virtual environment
if (Test-Path .venv\Scripts\Activate.ps1) {
    .venv\Scripts\Activate.ps1
    Write-Host "✅ Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "❌ Virtual environment not found at .venv" -ForegroundColor Red
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    .venv\Scripts\Activate.ps1
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

Write-Host ""

# Check if .env file exists
if (-not (Test-Path .env)) {
    Write-Host "⚠️  .env file not found!" -ForegroundColor Yellow
    Write-Host "Please create a .env file with your credentials:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "GOOGLE_OAUTH_CLIENT_ID=your_client_id_here"
    Write-Host "GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret_here"
    Write-Host "GOOGLE_ADS_DEVELOPER_TOKEN=your_developer_token_here"
    Write-Host ""
    exit 1
}

Write-Host "📋 Configuration Check:" -ForegroundColor Cyan
Write-Host "  • .env file: ✅ Found" -ForegroundColor Green
Write-Host ""

# Run the server
Write-Host "🌐 Starting server on http://localhost:7070" -ForegroundColor Green
Write-Host "🔐 OAuth login: http://localhost:7070/oauth/login" -ForegroundColor Green
Write-Host "📡 MCP endpoint: http://localhost:7070/mcp" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python googleads_final.py
