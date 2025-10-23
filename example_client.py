"""
Example client demonstrating FastMCP's zero-configuration OAuth.

Just run this script and it will automatically:
1. Launch your browser for Google OAuth
2. Store tokens securely
3. Make authenticated API calls
4. Handle token refresh automatically

No manual token management needed!
"""

import asyncio
from fastmcp import Client


async def main():
    """
    Connect to the Google Ads MCP Server with automatic OAuth.
    
    The first time you run this, it will:
    - Open your browser for Google sign-in
    - Request Google Ads API permissions
    - Store tokens locally for future use
    
    Subsequent runs will reuse stored tokens automatically!
    """
    
    # Change this to your deployed server URL
    SERVER_URL = "https://digital-magenta-bee.fastmcp.app/mcp"
    # Or for local testing: "http://localhost:7070/mcp"
    
    print("🚀 Connecting to Google Ads MCP Server...")
    print("📱 Browser will open for OAuth authentication (first time only)")
    
    async with Client(SERVER_URL, auth="oauth") as client:
        print("✅ Connected and authenticated!")
        
        # List all accessible Google Ads accounts
        print("\n📋 Fetching your Google Ads accounts...")
        accounts = await client.call_tool("list_accessible_accounts")
        
        print(f"\n✨ Found {len(accounts)} account(s):\n")
        for account in accounts:
            print(f"  • {account['name']} (ID: {account['id']})")
            print(f"    Currency: {account['currency']}, Timezone: {account['timezone']}")
            print(f"    Manager Account: {'Yes' if account['is_manager'] else 'No'}")
            print()
        
        # Get performance summary for the first account
        if accounts:
            first_account = accounts[0]
            customer_id = first_account['id']
            
            print(f"\n📊 Fetching 30-day performance for '{first_account['name']}'...")
            summary = await client.call_tool(
                "get_account_summary",
                customer_id=customer_id,
                days=30
            )
            
            print("\n💰 Performance Summary:")
            print(f"  Spend: ${summary.get('spend', 0):,.2f}")
            print(f"  Clicks: {summary.get('clicks', 0):,}")
            print(f"  Impressions: {summary.get('impressions', 0):,}")
            print(f"  Conversions: {summary.get('conversions', 0)}")
            print(f"  CTR: {summary.get('ctr', 0):.2f}%")
            print(f"  CPC: ${summary.get('cpc', 0):.2f}")


if __name__ == "__main__":
    asyncio.run(main())
