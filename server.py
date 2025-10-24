import os
import logging
from typing import List, Dict, Optional, Tuple

from fastmcp import FastMCP, Context
from fastmcp.server.auth import GoogleProvider

# ----------------------------------
# Config / Environment
# ----------------------------------
GOOGLE_ADS_DEVELOPER_TOKEN = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", "")
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "")  # your public domain, e.g. https://xyz.fastmcp.cloud

# Scopes we need
GOOGLE_OAUTH_SCOPES = [
    "openid", "email", "profile",
    "https://www.googleapis.com/auth/adwords",
]

# ----------------------------------
# FastMCP + OAuth
# ----------------------------------
auth = GoogleProvider(
    client_id=GOOGLE_OAUTH_CLIENT_ID,
    client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
    base_url=PUBLIC_BASE_URL,
    scopes=GOOGLE_OAUTH_SCOPES,
)

mcp = FastMCP("Google Ads Connector", auth=auth)

logger = logging.getLogger("google_ads_mcp")
logging.basicConfig(level=logging.INFO)


# ----------------------------------
# Token / Pref Stores (replace with DB in prod)
# ----------------------------------
# In production, replace both with persistent storage (Redis/DB/etc).
_user_tokens: dict[str, Tuple[str, Optional[str]]] = {}  # {user_sub: (access_token, refresh_token?)}
_user_prefs: dict[str, dict] = {}  # {user_sub: {"default_customer_id": "1234567890"}}


def _get_user_key(ctx: Context) -> str:
    """
    Unique per-user key from OAuth claims. Prefer stable 'sub'; fallback to email.
    """
    if not ctx or not getattr(ctx, "user", None):
        raise RuntimeError("Not authenticated. In Claude, click Connect for this connector.")
    claims = ctx.user  # e.g. {"sub": "...", "email": "..."}
    sub = claims.get("sub")
    email = claims.get("email")
    return sub or email or "unknown"


def _get_tokens(ctx: Context) -> Tuple[str, Optional[str]]:
    """
    Retrieve Google access/refresh tokens for the current user.
    This demo uses an in-memory dict. In production, wire this to your persistent store
    OR (if your FastMCP auth exposes a helper) fetch directly from the auth provider.
    """
    user_key = _get_user_key(ctx)

    # TODO: Replace this with your persistence (e.g., DB) or FastMCP auth provider helper.
    # For example, if your OAuth layer saves tokens on login:
    # tokens = db.get_user_tokens(user_key) -> (access_token, refresh_token)
    tokens = _user_tokens.get(user_key)

    if not tokens or not tokens[0]:
        # This message is what Claude will surface to the user
        raise RuntimeError("You’re not authenticated yet. In Claude, open ‘Search and Tools’ → "
                           "find this connector → click **Connect** and sign in with Google.")
    return tokens


def _set_tokens_for_user(user_key: str, access_token: str, refresh_token: Optional[str]) -> None:
    """
    Programmatic setter for tokens (if you have a login callback that captures tokens).
    Not used directly by tools; provided for completeness.
    """
    _user_tokens[user_key] = (access_token, refresh_token)


def _get_default_customer_id(ctx: Context) -> Optional[str]:
    user_key = _get_user_key(ctx)
    return _user_prefs.get(user_key, {}).get("default_customer_id")


def _set_default_customer_id(ctx: Context, customer_id: str) -> None:
    user_key = _get_user_key(ctx)
    prefs = _user_prefs.setdefault(user_key, {})
    prefs["default_customer_id"] = customer_id.replace("-", "")


# ----------------------------------
# Google Ads Client (thin wrapper)
# ----------------------------------
# Uses google-ads & google.oauth2.credentials under the hood
from google.oauth2.credentials import Credentials
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException


class GoogleAdsService:
    def __init__(self, access_token: str, refresh_token: Optional[str]):
        # Build OAuth2 creds from tokens
        self.credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            client_id=GOOGLE_OAUTH_CLIENT_ID,
            client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
        )
        self.client = GoogleAdsClient(
            credentials=self.credentials,
            developer_token=GOOGLE_ADS_DEVELOPER_TOKEN,
        )

    def get_accessible_accounts(self) -> List[Dict]:
        """
        Returns a list of accessible accounts.
        We use the GoogleAdsService to query customer_client links from the manager/root.
        Alternatively, you can use the OAuth2 identity to call the CustomerService.ListAccessibleCustomers.
        """
        output: List[Dict] = []

        try:
            # Preferred: CustomerService.ListAccessibleCustomers
            customer_service = self.client.get_service("CustomerService")
            resource_names = customer_service.list_accessible_customers().resource_names
            # resource_names are like "customers/1234567890"
            for rn in resource_names:
                cid = rn.split("/")[-1]
                # Try to fetch display name (optional)
                ga_service = self.client.get_service("GoogleAdsService")
                query = """
                    SELECT customer.descriptive_name
                    FROM customer
                    LIMIT 1
                """
                rows = ga_service.search(customer_id=cid, query=query)
                name = None
                for row in rows:
                    name = row.customer.descriptive_name
                    break
                output.append({"id": cid, "name": name or cid})
        except GoogleAdsException as ex:
            raise RuntimeError(_format_gads_error("get_accessible_accounts", ex))
        return output

    def list_campaigns(self, customer_id: str) -> List[Dict]:
        """
        Returns campaigns for a given customer_id.
        """
        customer_id = customer_id.replace("-", "")
        ga_service = self.client.get_service("GoogleAdsService")
        query = """
            SELECT
              campaign.id,
              campaign.name,
              campaign.status
            FROM campaign
            ORDER BY campaign.id
        """
        try:
            results = ga_service.search(customer_id=customer_id, query=query)
            campaigns: List[Dict] = []
            for row in results:
                campaigns.append({
                    "id": str(row.campaign.id),
                    "name": row.campaign.name,
                    "status": row.campaign.status.name,
                })
            return campaigns
        except GoogleAdsException as ex:
            raise RuntimeError(_format_gads_error("list_campaigns", ex))

    def get_account_summary(self, customer_id: str, days: int = 30) -> Dict:
        """
        Simple aggregate metrics at account level for 'days' lookback.
        """
        customer_id = customer_id.replace("-", "")
        ga_service = self.client.get_service("GoogleAdsService")
        # LAST_N_DAYS is supported; use LAST_30_DAYS / LAST_7_DAYS style for clarity
        # For arbitrary N, use BETWEEN with segments.date.
        date_window = f"LAST_{days}_DAYS" if days in (7, 14, 30, 90) else "LAST_30_DAYS"

        query = f"""
            SELECT
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros,
              metrics.conversions
            FROM customer
            WHERE segments.date DURING {date_window}
        """
        try:
            results = ga_service.search(customer_id=customer_id, query=query)
            # Sum across rows if multiple (some APIs return one row)
            summary = {"impressions": 0, "clicks": 0, "cost_micros": 0, "conversions": 0.0}
            for row in results:
                m = row.metrics
                summary["impressions"] += int(getattr(m, "impressions", 0) or 0)
                summary["clicks"] += int(getattr(m, "clicks", 0) or 0)
                summary["cost_micros"] += int(getattr(m, "cost_micros", 0) or 0)
                # conversions may be float
                cv = getattr(m, "conversions", 0.0) or 0.0
                try:
                    summary["conversions"] += float(cv)
                except Exception:
                    pass
            return summary
        except GoogleAdsException as ex:
            raise RuntimeError(_format_gads_error("get_account_summary", ex))


def _format_gads_error(where: str, ex: GoogleAdsException) -> str:
    parts = [f"Google Ads API error in {where}: {ex.error.code().name}"]
    for err in ex.failure.errors:
        parts.append(f"- {err.error_code}: {err.message}")
    return "\n".join(parts)


# ----------------------------------
# Helpers for UX
# ----------------------------------
def _normalize(items: List[Dict]) -> List[Dict]:
    # Basic normalization hook if needed
    return items


def _resolve_customer_id(customer_id: Optional[str], ctx: Context, svc: GoogleAdsService) -> str:
    """
    Resolve which customer_id to use:
    - if provided: use it
    - else if user default exists: use it
    - else if only one account accessible: use it
    - else: ask user to set a default or resolve
    """
    if customer_id:
        return customer_id.replace("-", "")

    default_cid = _get_default_customer_id(ctx)
    if default_cid:
        return default_cid

    accounts = svc.get_accessible_accounts()
    if len(accounts) == 1:
        return str(accounts[0]["id"]).replace("-", "")

    raise RuntimeError(
        "Multiple accounts found and no default set. "
        "Use resolve_account(name_or_partial) and then set_default_account(customer_id), "
        "or pass customer_id directly."
    )


# ----------------------------------
# Tools
# ----------------------------------
@mcp.tool()
def list_accessible_accounts(ctx: Context) -> List[Dict]:
    """
    List all Google Ads accounts accessible to the authenticated user.
    """
    access_token, refresh_token = _get_tokens(ctx)
    svc = GoogleAdsService(access_token, refresh_token)
    accounts = svc.get_accessible_accounts()
    return _normalize(accounts)


@mcp.tool()
def list_campaigns(
    ctx: Context,
    customer_id: Optional[str] = None,
) -> List[Dict]:
    """
    List all campaigns in the chosen account.
    If customer_id is omitted, uses your default account; if none, auto-selects if only one account exists.
    """
    access_token, refresh_token = _get_tokens(ctx)
    svc = GoogleAdsService(access_token, refresh_token)
    cid = _resolve_customer_id(customer_id, ctx, svc)
    return _normalize(svc.list_campaigns(cid))


@mcp.tool()
def get_account_summary(
    ctx: Context,
    customer_id: Optional[str] = None,
    days: int = 30,
) -> Dict:
    """
    Get a performance summary (impressions, clicks, cost_micros, conversions) for the chosen account.
    If customer_id is omitted, uses your default or auto-selects when only one account exists.
    """
    access_token, refresh_token = _get_tokens(ctx)
    svc = GoogleAdsService(access_token, refresh_token)
    cid = _resolve_customer_id(customer_id, ctx, svc)
    return svc.get_account_summary(cid, days)


@mcp.tool()
def resolve_account(ctx: Context, query: str) -> Dict:
    """
    Resolve a partial name or ID-like string to a customer_id.
    Returns either {"customer_id", "name"} or {"ambiguous": True, "candidates": [...] }.
    """
    access_token, refresh_token = _get_tokens(ctx)
    svc = GoogleAdsService(access_token, refresh_token)
    accts = svc.get_accessible_accounts()
    q = query.replace("-", "").strip().lower()

    matches: List[Dict] = []
    for a in accts:
        aid = str(a.get("id", "")).replace("-", "")
        name = (a.get("name") or "").lower()
        if q in aid or q in name:
            matches.append(a)

    if not matches:
        raise RuntimeError(f"No account matched '{query}'.")
    if len(matches) > 1:
        return {"ambiguous": True, "candidates": matches[:6]}
    m = matches[0]
    return {"customer_id": str(m["id"]), "name": m.get("name")}


@mcp.tool()
def set_default_account(ctx: Context, customer_id: str) -> Dict:
    """
    Set the default Google Ads account for your future calls.
    """
    access_token, refresh_token = _get_tokens(ctx)
    svc = GoogleAdsService(access_token, refresh_token)

    # Validate the account is accessible
    ids = {str(a["id"]).replace("-", "") for a in svc.get_accessible_accounts()}
    cid = customer_id.replace("-", "")
    if cid not in ids:
        raise RuntimeError(f"Account {customer_id} is not in your accessible list.")
    _set_default_customer_id(ctx, cid)
    return {"ok": True, "default_customer_id": cid}


# ----------------------------------
# Run (FastMCP Cloud will handle ports)
# ----------------------------------
if __name__ == "__main__":
    mcp.run()
