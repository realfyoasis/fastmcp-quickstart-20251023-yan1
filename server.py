import os
import logging
from typing import List, Dict, Optional, Tuple

from fastmcp import FastMCP, Context
from fastmcp.server.auth.providers.google import GoogleProvider
import fastmcp, logging
logging.info(f"FastMCP version: {fastmcp.__version__}")
# --- Read from environment ---
PUBLIC_BASE_URL = os.environ["PUBLIC_BASE_URL"]  # e.g. https://<your-ngrok>.ngrok-free.app
GOOGLE_OAUTH_CLIENT_ID = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
GOOGLE_OAUTH_CLIENT_SECRET = os.environ["GOOGLE_OAUTH_CLIENT_SECRET"]
GOOGLE_ADS_DEVELOPER_TOKEN = os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"]
JWT_SIGNING_KEY = os.environ["JWT_SIGNING_KEY"]            # long random string
TOKEN_ENCRYPTION_KEY = os.environ["TOKEN_ENCRYPTION_KEY"] 


print(f"JWT Signing Key: {JWT_SIGNING_KEY}")
print(f"Token Encryption Key: {TOKEN_ENCRYPTION_KEY}")

logger = logging.getLogger("google_ads_mcp")
logging.basicConfig(level=logging.INFO)

auth_provider = GoogleProvider(
    client_id=GOOGLE_OAUTH_CLIENT_ID,
    client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
    base_url=PUBLIC_BASE_URL,  # e.g. https://a2d0037ef801.ngrok-free.app

    # Scopes you need from Google
    required_scopes=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/adwords",
    ],

    # These two make /token return a FastMCP JWT (eyJ...) and store upstream tokens encrypted
    # jwt_signing_key=os.environ["JWT_SIGNING_KEY"],           # Secret for signing JWT tokens
    # token_encryption_key=os.environ["TOKEN_ENCRYPTION_KEY"], 

    # Let Claude and localhost complete the OAuth dance
    allowed_client_redirect_uris=[
        "http://localhost:*",
        "http://127.0.0.1:*",
        "https://claude.ai/api/mcp/auth_callback",
    ],

    # redirect_path="/auth/callback",  # default; make sure this exact URI is in Google console
)



# Build your MCP server with auth attached
mcp = FastMCP(name="Google Ads Connector", auth=auth_provider)

# ─────────────────────────────────────────────────────────────────────────────
# Token & Pref Stores (fallbacks only; prefer provider-managed tokens)
# ─────────────────────────────────────────────────────────────────────────────
_user_prefs: dict[str, dict] = {}  # {user_sub: {"default_customer_id": "1234567890"}}

def _get_user_key(ctx: Context) -> str:
    if not ctx or not getattr(ctx, "user", None):
        raise RuntimeError("Not authenticated. In Claude, click Connect for this connector.")
    claims = ctx.user  # {'sub': '...', 'email': '...'}
    return claims.get("sub") or claims.get("email") or "unknown"

def _set_default_customer_id(ctx: Context, customer_id: str) -> None:
    user_key = _get_user_key(ctx)
    _user_prefs.setdefault(user_key, {})["default_customer_id"] = customer_id.replace("-", "")

def _get_default_customer_id(ctx: Context) -> Optional[str]:
    user_key = _get_user_key(ctx)
    return _user_prefs.get(user_key, {}).get("default_customer_id")

# ─────────────────────────────────────────────────────────────────────────────
# Provider-managed token retrieval (preferred)
# Tries several common access points depending on FastMCP minor version.
# If not available, raises a single, clear message.
# ─────────────────────────────────────────────────────────────────────────────
def _get_tokens(ctx: Context) -> Tuple[str, Optional[str]]:
    sub = _get_user_key(ctx)

    # Try common places for the auth provider instance
    provider = None
    # FastMCP sometimes exposes the provider here:
    if hasattr(mcp, "auth"):
        provider = getattr(mcp, "auth")
    # Or current() if the framework exposes it (safe to try)
    if not provider and hasattr(FastMCP, "current"):
        cur = FastMCP.current()
        if cur and hasattr(cur, "auth"):
            provider = cur.auth

    # Known helper name in many 2.x builds
    if provider and hasattr(provider, "get_tokens_for_subject"):
        toks = provider.get_tokens_for_subject(sub)
        # Expect attributes access_token / refresh_token
        access = getattr(toks, "access_token", None)
        refresh = getattr(toks, "refresh_token", None)
        if not access:
            raise RuntimeError("Authenticated, but no Google access token found. Reconnect this connector.")
        return access, refresh

    # If your build exposes a different helper, add it here:
    if provider and hasattr(provider, "get_user_tokens"):
        access, refresh = provider.get_user_tokens(sub)  # hypothetical
        if not access:
            raise RuntimeError("Authenticated, but no Google access token found. Reconnect this connector.")
        return access, refresh

    # No helper → ask user to add tiny persistence bridge (I can provide snippet)
    raise RuntimeError(
        "Auth connected, but this FastMCP build does not expose a token helper.\n"
        "Option A (recommended): update FastMCP / provider to enable provider-managed tokens.\n"
        "Option B: add a 10-line auth-success persistence bridge to store (access, refresh) "
        "per ctx.user['sub'] — I can paste a ready snippet."
    )

# ─────────────────────────────────────────────────────────────────────────────
# Google Ads client wrapper
# ─────────────────────────────────────────────────────────────────────────────
from google.oauth2.credentials import Credentials
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

class GoogleAdsService:
    def __init__(self, access_token: str, refresh_token: Optional[str]):
        if not GOOGLE_ADS_DEVELOPER_TOKEN:
            raise RuntimeError("GOOGLE_ADS_DEVELOPER_TOKEN is not set.")
        if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
            raise RuntimeError("Google OAuth client env vars are not set.")
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
        out: List[Dict] = []
        try:
            customer_service = self.client.get_service("CustomerService")
            rns = customer_service.list_accessible_customers().resource_names
            for rn in rns:
                cid = rn.split("/")[-1]
                ga_service = self.client.get_service("GoogleAdsService")
                rows = ga_service.search(
                    customer_id=cid,
                    query="SELECT customer.descriptive_name FROM customer LIMIT 1",
                )
                name = None
                for row in rows:
                    name = row.customer.descriptive_name
                    break
                out.append({"id": cid, "name": name or cid})
        except GoogleAdsException as ex:
            raise RuntimeError(_fmt_err("get_accessible_accounts", ex))
        return out

    def list_campaigns(self, customer_id: str) -> List[Dict]:
        customer_id = customer_id.replace("-", "")
        ga_service = self.client.get_service("GoogleAdsService")
        q = """
            SELECT
              campaign.id,
              campaign.name,
              campaign.status
            FROM campaign
            ORDER BY campaign.id
        """
        try:
            rows = ga_service.search(customer_id=customer_id, query=q)
            return [
                {
                    "id": str(row.campaign.id),
                    "name": row.campaign.name,
                    "status": row.campaign.status.name,
                }
                for row in rows
            ]
        except GoogleAdsException as ex:
            raise RuntimeError(_fmt_err("list_campaigns", ex))

    def get_account_summary(self, customer_id: str, days: int = 30) -> Dict:
        customer_id = customer_id.replace("-", "")
        ga_service = self.client.get_service("GoogleAdsService")
        date_window = f"LAST_{days}_DAYS" if days in (7, 14, 30, 90) else "LAST_30_DAYS"
        q = f"""
            SELECT
              metrics.impressions,
              metrics.clicks,
              metrics.cost_micros,
              metrics.conversions
            FROM customer
            WHERE segments.date DURING {date_window}
        """
        try:
            rows = ga_service.search(customer_id=customer_id, query=q)
            summary = {"impressions": 0, "clicks": 0, "cost_micros": 0, "conversions": 0.0}
            for row in rows:
                m = row.metrics
                summary["impressions"] += int(getattr(m, "impressions", 0) or 0)
                summary["clicks"] += int(getattr(m, "clicks", 0) or 0)
                summary["cost_micros"] += int(getattr(m, "cost_micros", 0) or 0)
                cv = getattr(m, "conversions", 0.0) or 0.0
                try:
                    summary["conversions"] += float(cv)
                except Exception:
                    pass
            return summary
        except GoogleAdsException as ex:
            raise RuntimeError(_fmt_err("get_account_summary", ex))

def _fmt_err(where: str, ex: GoogleAdsException) -> str:
    parts = [f"Google Ads API error in {where}: {ex.error.code().name}"]
    for err in ex.failure.errors:
        parts.append(f"- {err.error_code}: {err.message}")
    return "\n".join(parts)

def _normalize(items: List[Dict]) -> List[Dict]:
    return items

def _resolve_customer_id(customer_id: Optional[str], ctx: Context, svc: GoogleAdsService) -> str:
    if customer_id:
        return customer_id.replace("-", "")
    default_cid = _get_default_customer_id(ctx)
    if default_cid:
        return default_cid
    accts = svc.get_accessible_accounts()
    if len(accts) == 1:
        return str(accts[0]["id"]).replace("-", "")
    raise RuntimeError(
        "Multiple accounts found and no default set. "
        "Run resolve_account(name_or_partial) then set_default_account(customer_id), "
        "or pass customer_id directly."
    )

# ─────────────────────────────────────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def whoami(ctx: Context) -> dict:
    """Return auth claims to confirm user context."""
    if not getattr(ctx, "user", None):
        raise RuntimeError("No user in context (not authenticated).")
    return {"user": ctx.user}

@mcp.tool()
def debug_auth_status(ctx: Context) -> dict:
    """Check whether the server can fetch Google tokens for you."""
    try:
        a, r = _get_tokens(ctx)
        return {"has_access_token": bool(a), "has_refresh_token": bool(r)}
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def list_accessible_accounts(ctx: Context) -> List[Dict]:
    access_token, refresh_token = _get_tokens(ctx)
    svc = GoogleAdsService(access_token, refresh_token)
    return _normalize(svc.get_accessible_accounts())

@mcp.tool()
def list_campaigns(ctx: Context, customer_id: Optional[str] = None) -> List[Dict]:
    access_token, refresh_token = _get_tokens(ctx)
    svc = GoogleAdsService(access_token, refresh_token)
    cid = _resolve_customer_id(customer_id, ctx, svc)
    return _normalize(svc.list_campaigns(cid))

@mcp.tool()
def get_account_summary(ctx: Context, customer_id: Optional[str] = None, days: int = 30) -> Dict:
    access_token, refresh_token = _get_tokens(ctx)
    svc = GoogleAdsService(access_token, refresh_token)
    cid = _resolve_customer_id(customer_id, ctx, svc)
    return svc.get_account_summary(cid, days)

@mcp.tool()
def resolve_account(ctx: Context, query: str) -> Dict:
    access_token, refresh_token = _get_tokens(ctx)
    svc = GoogleAdsService(access_token, refresh_token)
    accts = svc.get_accessible_accounts()
    q = query.replace("-", "").strip().lower()
    matches = []
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
    access_token, refresh_token = _get_tokens(ctx)
    svc = GoogleAdsService(access_token, refresh_token)
    ids = {str(a["id"]).replace("-", "") for a in svc.get_accessible_accounts()}
    cid = customer_id.replace("-", "")
    if cid not in ids:
        raise RuntimeError(f"Account {customer_id} is not in your accessible list.")
    _set_default_customer_id(ctx, cid)
    return {"ok": True, "default_customer_id": cid}

# ─────────────────────────────────────────────────────────────────────────────
# Run (SSE for Claude)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
