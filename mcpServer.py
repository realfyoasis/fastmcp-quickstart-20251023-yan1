# mcp_server.py
import sys
import logging
import os
import json
from pathlib import Path
from types import SimpleNamespace

# FastMCP + FastAPI + ASGI tools
from fastmcp import FastMCP
from fastmcp.server.auth.oauth_proxy import OAuthProxy
from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

# Google libs
import google.auth
from google.cloud import firestore
from google.cloud import secretmanager
from google.api_core.exceptions import AlreadyExists, NotFound

# Local imports (project root)
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.services.google_ads_service import GoogleAdsService

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# GCP project detection
try:
    _, GOOGLE_CLOUD_PROJECT = google.auth.default()
except Exception:
    GOOGLE_CLOUD_PROJECT = None
    logger.warning("Could not determine Google Cloud project ID. Some features will be disabled.")

GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
    logger.warning("Missing GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET. OAuth will be disabled.")

# --- GCP lazy init (defensive - works even if GCP isn't configured locally) ---
from typing import Optional
from google.api_core.exceptions import PermissionDenied

db: Optional[firestore.Client] = None
secret_manager_client: Optional[secretmanager.SecretManagerServiceClient] = None

try:
    if GOOGLE_CLOUD_PROJECT:
        db = firestore.Client(project=GOOGLE_CLOUD_PROJECT)
        secret_manager_client = secretmanager.SecretManagerServiceClient()
        logger.info(f"✅ GCP initialized for project: {GOOGLE_CLOUD_PROJECT}")
    else:
        logger.warning("⚠️  GOOGLE_CLOUD_PROJECT not set; credential saving endpoints will be disabled.")
except Exception as e:
    logger.error(f"❌ Failed to initialize GCP clients: {e}")
    db = None
    secret_manager_client = None

# Build OAuthProxy (unchanged logic but no route appending yet)
def build_oauth_proxy():
    auth_url  = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    scopes = [
        "https://www.googleapis.com/auth/adwords",
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ]
    Verifier = SimpleNamespace(
        verify=lambda *_args, **_kw: True,
        required_scopes=scopes
    )
    public_base = os.getenv("RENDER_EXTERNAL_URL", "http://127.0.0.1:7070").rstrip("/")

    attempts = [
        dict(
            upstream_authorization_endpoint=auth_url,
            upstream_token_endpoint=token_url,
            upstream_jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
            client_id=GOOGLE_OAUTH_CLIENT_ID,
            client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
            default_scopes=scopes,
            require_authorization_consent=False,
        ),
        dict(
            upstream_authorization_endpoint=auth_url,
            upstream_token_endpoint=token_url,
            client_id=GOOGLE_OAUTH_CLIENT_ID,
            client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
            default_scopes=scopes,
            require_authorization_consent=False,
        ),
        dict(
            upstream_authorization_endpoint=auth_url,
            upstream_token_endpoint=token_url,
            upstream_client_id=GOOGLE_OAUTH_CLIENT_ID,
            upstream_client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
            base_url=public_base,
            default_scopes=scopes,
        ),
        dict(
            upstream_authorization_endpoint=auth_url,
            upstream_token_endpoint=token_url,
            upstream_client_id=GOOGLE_OAUTH_CLIENT_ID,
            upstream_client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
            base_url=public_base,
            token_verifier=Verifier,
            default_scopes=scopes,
        ),
        dict(
            upstream_authorization_endpoint=auth_url,
            upstream_token_endpoint=token_url,
            upstream_client_id=GOOGLE_OAUTH_CLIENT_ID,
            upstream_client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
            base_url=public_base,
            token_verifier=Verifier,
        ),
    ]

    last_exc = None
    for kwargs in attempts:
        try:
            return OAuthProxy(**kwargs)
        except TypeError as e:
            last_exc = e
            continue

    raise RuntimeError(f"Could not construct OAuthProxy for this fastmcp version: {last_exc}")

oauth = build_oauth_proxy()
logger.info("OAuthProxy initialized.")

# Create the MCP instance (do NOT call http_app() yet)
mcp = FastMCP(name="Google Ads API", version="1.0")

# --- Secret Manager & Firestore helpers ---
def store_token_in_secret_manager(user_id: str, refresh_token: str) -> Optional[str]:
    """Stores the refresh token in Google Secret Manager and returns the version name."""
    if not secret_manager_client or not GOOGLE_CLOUD_PROJECT:
        logger.warning("Secret Manager client not initialized; skipping token storage.")
        return None

    secret_id = f"user-refresh-token-{user_id}"
    parent = f"projects/{GOOGLE_CLOUD_PROJECT}"
    secret_path = f"{parent}/secrets/{secret_id}"

    try:
        secret_manager_client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {"replication": {"automatic": {}}},
            }
        )
        logger.info(f"Created secret: {secret_id}")
    except AlreadyExists:
        logger.info(f"Secret {secret_id} already exists. Adding new version.")
    except Exception as e:
        logger.error(f"Failed to create secret {secret_id}: {e}")
        raise

    payload = refresh_token.encode("UTF-8")
    version = secret_manager_client.add_secret_version(
        request={"parent": secret_path, "payload": {"data": payload}}
    )
    logger.info(f"Added new version for secret {secret_id}: {version.name}")
    return version.name

def write_user_to_firestore(user_id: str, email: str, profile: dict, secret_version_name: Optional[str]) -> None:
    """Upserts the user document in Firestore."""
    if not db:
        logger.warning("Firestore client not initialized; skipping user write.")
        return

    doc = {
        "email": email,
        "profile": profile or {},
        "providers": ["google"],
        "hasAdsAccess": bool(secret_version_name),
        "auth": {"secret_version_name": secret_version_name} if secret_version_name else {},
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }
    
    # Create if missing, then merge
    ref = db.collection("users").document(user_id)
    if not ref.get().exists:
        doc["createdAt"] = firestore.SERVER_TIMESTAMP
    
    ref.set(doc, merge=True)
    logger.info(f"User {user_id} upserted in Firestore (has token: {bool(secret_version_name)})")

def get_ads_service_from_auth(auth: dict) -> GoogleAdsService:
    if not auth:
        raise RuntimeError("No auth provided by client.")
    if "refresh_token" in auth:
        return GoogleAdsService(user_credentials={"refresh_token": auth["refresh_token"]})
    if "access_token" in auth:
        return GoogleAdsService(user_credentials={"access_token": auth["access_token"]})
    if "secret_version_name" in auth:
        try:
            response = secret_manager_client.access_secret_version(request={"name": auth["secret_version_name"]})
            refresh_token = response.payload.data.decode("UTF-8")
            return GoogleAdsService(user_credentials={"refresh_token": refresh_token})
        except NotFound:
            raise FileNotFoundError("Could not find the stored credential in Secret Manager.")
        except Exception as e:
            raise ConnectionError(f"Failed to retrieve user credentials: {e}")
    raise RuntimeError("Unsupported auth payload: expected access_token, refresh_token, or secret_version_name.")

# --- Define raw tool functions (these are the actual callables) ---
async def list_accessible_accounts(auth: dict) -> list[dict]:
    """List all Google Ads accounts the authenticated user can access."""
    try:
        service = get_ads_service_from_auth(auth)
        accounts = service.get_accessible_accounts()
        return [acc.__dict__ for acc in accounts]
    except Exception as e:
        raise RuntimeError(str(e))

async def get_account_summary(auth: dict, customer_id: str, days: int = 30) -> dict:
    """Get performance summary (spend, clicks, conversions) for a Google Ads account over the specified number of days."""
    try:
        service = get_ads_service_from_auth(auth)
        summary = service.get_account_summary(customer_id, days)
        return summary or {"message": f"No data found for account {customer_id}"}
    except Exception as e:
        raise RuntimeError(str(e))

# --- Build registry with raw callables BEFORE decoration ---
TOOL_REGISTRY = {
    "list_accessible_accounts": list_accessible_accounts,
    "get_account_summary": get_account_summary,
}

# --- Now register with MCP (decorators may wrap the functions, but registry has originals) ---
mcp.tool()(list_accessible_accounts)
mcp.tool()(get_account_summary)

# Rich JSON Schemas so clients like Claude can render proper forms
TOOL_SCHEMAS = {
    "list_accessible_accounts": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "List Accessible Accounts",
        "type": "object",
        "properties": {
            "auth": {
                "title": "Authentication",
                "type": "object",
                "oneOf": [
                    {
                        "title": "Refresh token",
                        "type": "object",
                        "properties": {
                            "refresh_token": {"type": "string", "minLength": 10}
                        },
                        "required": ["refresh_token"],
                        "additionalProperties": False
                    },
                    {
                        "title": "Access token",
                        "type": "object",
                        "properties": {
                            "access_token": {"type": "string", "minLength": 10}
                        },
                        "required": ["access_token"],
                        "additionalProperties": False
                    },
                    {
                        "title": "Secret Manager ref",
                        "type": "object",
                        "properties": {
                            "secret_version_name": {
                                "type": "string",
                                "pattern": r"^projects\/[^\/]+\/secrets\/[^\/]+\/versions\/(latest|\d+)$"
                            }
                        },
                        "required": ["secret_version_name"],
                        "additionalProperties": False
                    }
                ]
            }
        },
        "required": ["auth"],
        "additionalProperties": False
    },
    "get_account_summary": {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Get Account Summary",
        "type": "object",
        "properties": {
            "auth": {
                "title": "Authentication",
                "type": "object",
                "oneOf": [
                    {
                        "title": "Refresh token",
                        "type": "object",
                        "properties": {
                            "refresh_token": {"type": "string", "minLength": 10}
                        },
                        "required": ["refresh_token"],
                        "additionalProperties": False
                    },
                    {
                        "title": "Access token",
                        "type": "object",
                        "properties": {
                            "access_token": {"type": "string", "minLength": 10}
                        },
                        "required": ["access_token"],
                        "additionalProperties": False
                    },
                    {
                        "title": "Secret Manager ref",
                        "type": "object",
                        "properties": {
                            "secret_version_name": {
                                "type": "string",
                                "pattern": r"^projects\/[^\/]+\/secrets\/[^\/]+\/versions\/(latest|\d+)$"
                            }
                        },
                        "required": ["secret_version_name"],
                        "additionalProperties": False
                    }
                ]
            },
            "customer_id": {
                "title": "Customer ID",
                "type": "string",
                "pattern": r"^\d{3}-?\d{3}-?\d{4}$",
                "description": "Google Ads customer ID (with or without dashes)"
            },
            "days": {
                "title": "Days",
                "type": "integer",
                "default": 30,
                "minimum": 1,
                "maximum": 365
            }
        },
        "required": ["auth", "customer_id"],
        "additionalProperties": False
    }
}

# Log the initialized tools and schemas
logger.info("🔧 TOOL REGISTRY INITIALIZED: %s", list(TOOL_REGISTRY.keys()))
logger.info("🔧 TOOL SCHEMAS INITIALIZED: %s", list(TOOL_SCHEMAS.keys()))

# --- Main FastAPI app (no FastMCP HTTP wiring needed - we use direct JSON-RPC shim) ---
from typing import Optional, Any, Dict

app = FastAPI()
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Add OAuth routes
for route in oauth.get_routes(mcp_path="/"):
    app.router.routes.append(route)

# --- JSON-RPC Shim (direct tool calling, bypasses FastMCP HTTP transport) ---
from fastapi import HTTPException

def _jsonrpc_ok(id_val: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_val, "result": result}

def _jsonrpc_err(id_val: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": id_val, "error": err}

async def _handle_initialize(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP initialize request"""
    proto = params.get("protocolVersion", "2024-11-05")
    return {
        "protocolVersion": proto,
        "capabilities": {
            # Explicitly declare tools capability and that the list changed
            "tools": {"listChanged": True}
        },
        "serverInfo": {"name": "Google Ads MCP Server", "version": "1.0"},
        # Optional: human-readable instructions
        "instructions": "Google Ads tools: list accounts, get account summary.",
        # Add explicit tools hint to encourage Claude to call tools/list
        "toolsAvailable": True,
        "toolCount": len(TOOL_REGISTRY)
    }

async def _handle_tools_list() -> Dict[str, Any]:
    """Handle tools/list request"""
    logger.info("🔧 TOOLS LIST: Starting tools list generation")
    logger.info("TOOL_REGISTRY keys: %s", list(TOOL_REGISTRY.keys()))
    logger.info("TOOL_SCHEMAS keys: %s", list(TOOL_SCHEMAS.keys()))
    
    tools = []
    for name, fn in TOOL_REGISTRY.items():
        logger.info("Processing tool: %s", name)
        logger.info("Function: %s", fn)
        logger.info("Function doc: %s", fn.__doc__)
        
        schema = TOOL_SCHEMAS.get(name, {"type": "object"})
        logger.info("Schema for %s: %s", name, schema)
        
        tool_def = {
            "name": name,
            "description": (fn.__doc__ or f"Google Ads tool: {name}").strip(),
            "inputSchema": schema
        }
        tools.append(tool_def)
        logger.info("Added tool: %s", tool_def)
    
    logger.info("🔧 TOOLS LIST: serving %d tools: %s", len(tools), [t["name"] for t in tools])
    logger.info("Full tools response: %s", tools)
    return {"tools": tools}

async def _handle_tools_call(params: Dict[str, Any]) -> Any:
    """Handle tools/call request"""
    name = params.get("name")
    arguments = params.get("arguments") or {}
    
    if name not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {name}")
    
    fn = TOOL_REGISTRY[name]
    
    if not callable(fn):
        raise HTTPException(status_code=500, detail=f"Tool not callable: {name}")
    
    if not isinstance(arguments, dict):
        raise HTTPException(status_code=400, detail="Tool arguments must be an object")
    
    # All our tools are async
    logger.info("Calling tool: %s with args: %s", name, list(arguments.keys()))
    result = await fn(**arguments)
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

async def _dispatch_jsonrpc(req: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a single JSON-RPC request"""
    id_val = req.get("id")
    method = req.get("method")
    params = req.get("params") or {}
    
    logger.info("🚀 DISPATCH: method=%s, id=%s, params=%s", method, id_val, params)

    if method == "initialize":
        logger.info("📋 Handling initialize request")
        result = await _handle_initialize(params)
        logger.info("Initialize result: %s", result)
        return _jsonrpc_ok(id_val, result)

    if method in ("tools/list", "tools.list"):
        logger.info("🔧 Handling tools/list request")
        result = await _handle_tools_list()
        logger.info("Tools list result: %s", result)
        return _jsonrpc_ok(id_val, result)

    if method in ("tools/call", "tools.call"):
        logger.info("⚡ Handling tools/call request")
        result = await _handle_tools_call(params)
        logger.info("Tools call result: %s", result)
        return _jsonrpc_ok(id_val, result)

    logger.warning("❌ UNKNOWN METHOD: %s", method)
    error = _jsonrpc_err(id_val, -32601, f"Method not found: {method}")
    logger.info("Error response: %s", error)
    return error

# --- JSON-RPC HTTP endpoints (all paths supported) ---
def _is_notification(msg: dict) -> bool:
    return isinstance(msg, dict) and msg.get("id") is None

@app.post("/")
async def jsonrpc_root(request: Request):
    """Main JSON-RPC endpoint"""
    logger.info("=== JSON-RPC REQUEST START ===")
    logger.info("Request URL: %s", request.url)
    logger.info("Request headers: %s", dict(request.headers))
    
    payload = await request.json()
    logger.info("Raw payload: %s", payload)
    logger.info("Payload type: %s", type(payload))

    # Single request
    if isinstance(payload, dict):
        method = payload.get("method")
        id_val = payload.get("id")
        logger.info("Single request - method: %s, id: %s", method, id_val)
        
        # Special-case: Claude sends a JSON-RPC notification after initialize.
        # Claude web expects HTTP 200 with empty body, not 204
        if _is_notification(payload):
            logger.info("🔔 NOTIFICATION DETECTED: method=%s (no id field)", method)
            logger.info("Returning empty JSON response for Claude web compatibility")
            # Claude web expects HTTP 200 with empty JSON, not 204
            response = JSONResponse({})
            logger.info("Response: %s", response)
            return response

        logger.info("📞 REGULAR REQUEST: method=%s, id=%s", method, id_val)
        result = await _dispatch_jsonrpc(payload)
        logger.info("Dispatch result: %s", result)
        response = JSONResponse(result)
        logger.info("Final response: %s", response)
        return response

    # Batch requests
    if isinstance(payload, list):
        logger.info("📦 BATCH REQUEST with %d items", len(payload))
        responses = []
        only_notifications = True
        for i, req in enumerate(payload):
            logger.info("Batch item %d: %s", i, req)
            if _is_notification(req):
                logger.info("🔔 Notification in batch: method=%s", req.get("method"))
                continue
            only_notifications = False
            logger.info("📞 Regular request in batch: method=%s, id=%s", req.get("method"), req.get("id"))
            responses.append(await _dispatch_jsonrpc(req))
        
        # If the whole batch was notifications, return 200 with empty array (Claude-friendly)
        if only_notifications:
            logger.info("All batch items were notifications, returning empty array")
            return JSONResponse([], status_code=200)
        
        logger.info("Batch responses: %s", responses)
        return JSONResponse(responses)

    # Invalid payload
    logger.warning("❌ INVALID PAYLOAD: type=%s, value=%s", type(payload), payload)
    error_response = _jsonrpc_err(None, -32600, "Invalid Request")
    logger.info("Error response: %s", error_response)
    return JSONResponse(error_response)

@app.post("/rpc")
async def jsonrpc_rpc(request: Request):
    return await jsonrpc_root(request)

@app.post("/rpc/")
async def jsonrpc_rpc_slash(request: Request):
    return await jsonrpc_root(request)

@app.post("/mcp")
async def jsonrpc_mcp(request: Request):
    return await jsonrpc_root(request)

@app.post("/mcp/")
async def jsonrpc_mcp_slash(request: Request):
    return await jsonrpc_root(request)

# --- User Registration Endpoint ---
from pydantic import BaseModel, Field
from fastapi import HTTPException

class RegisterBody(BaseModel):
    user_id: str = Field(..., description="Your app's user id (e.g., Firebase uid)")
    email: str
    profile: dict = Field(default_factory=dict)  # name, picture, etc.
    # either send refresh_token (server will store & return secret_version_name)
    refresh_token: Optional[str] = None
    # or, if you already stored it earlier, send the secret reference directly
    secret_version_name: Optional[str] = None

@app.post("/register")
def register_user(body: RegisterBody):
    """
    Register/update a user in Firestore after OAuth.
    Optionally stores refresh token in Secret Manager.
    """
    logger.info(f"Registration request for user: {body.user_id} ({body.email})")
    
    # Simple validation
    if not (body.refresh_token or body.secret_version_name):
        # Allow creating a bare user doc without token if needed
        logger.info("Register without token: creating bare user doc.")
        write_user_to_firestore(body.user_id, body.email, body.profile, None)
        return {"ok": True, "stored": False, "message": "User created without Ads token."}

    # If a refresh_token is provided, store it and get a secret reference
    svn = body.secret_version_name
    if body.refresh_token:
        try:
            svn = store_token_in_secret_manager(body.user_id, body.refresh_token)
            if not svn:
                raise HTTPException(
                    status_code=503,
                    detail="Secret Manager not available. Check GCP configuration."
                )
        except PermissionDenied as e:
            raise HTTPException(
                status_code=403,
                detail=f"Secret Manager denied: {e.message}"
            )
        except Exception as e:
            logger.exception("Failed to store refresh token")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to store refresh token: {str(e)}"
            )

    # Write the user doc with the secret ref
    try:
        write_user_to_firestore(body.user_id, body.email, body.profile, svn)
    except Exception as e:
        logger.exception("Failed to write Firestore user")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write Firestore user: {str(e)}"
        )

    logger.info(f"✅ User {body.user_id} registered successfully (token stored: {bool(svn)})")
    return {
        "ok": True,
        "stored": bool(svn),
        "secret_version_name": svn,
        "message": "User registered successfully"
    }

# --- Basic GET endpoints ---
@app.get("/")
def root_info():
    return {
        "name": "Google Ads MCP Server",
        "version": "1.0",
        "status": "running",
        "transport": "Direct JSON-RPC (bypasses FastMCP HTTP)",
        "mcp_endpoints": ["POST /", "POST /rpc", "POST /rpc/", "POST /mcp", "POST /mcp/"],
        "tools": list(TOOL_REGISTRY.keys()),
        "endpoints": {
            "health": "GET /health",
            "debug": "GET /debug",
            "tools": "GET /tools",
            "register": "POST /register",
            "oauth": "GET /.well-known/oauth-authorization-server"
        },
        "gcp": {
            "firestore": db is not None,
            "secret_manager": secret_manager_client is not None,
            "project": GOOGLE_CLOUD_PROJECT
        }
    }

@app.get("/health")
def health():
    return {"ok": True, "mcp_active": True, "oauth_proxy": "enabled"}

@app.get("/debug")
def debug_info():
    """Debug endpoint showing registered tools and schemas"""
    tools_list = []
    for name, fn in TOOL_REGISTRY.items():
        tools_list.append({
            "name": name,
            "description": fn.__doc__ or "",
            "schema": TOOL_SCHEMAS.get(name, {})
        })
    
    return {
        "status": "ok",
        "transport": "Direct JSON-RPC shim",
        "available_tools": tools_list,
        "tool_count": len(TOOL_REGISTRY),
        "server_info": {
            "name": "Google Ads MCP Server",
            "version": "1.0"
        }
    }

@app.get("/tools")
def list_tools():
    """Quick debug endpoint to see tool registry status"""
    tools_info = []
    for name, fn in TOOL_REGISTRY.items():
        schema = TOOL_SCHEMAS.get(name, {})
        tools_info.append({
            "name": name,
            "description": fn.__doc__ or "",
            "has_schema": name in TOOL_SCHEMAS,
            "schema_keys": list(schema.keys()) if isinstance(schema, dict) else [],
            "function": str(fn)
        })
    
    return {
        "count": len(TOOL_REGISTRY),
        "tools": tools_info,
        "registry_keys": list(TOOL_REGISTRY.keys()),
        "schema_keys": list(TOOL_SCHEMAS.keys())
    }

# Run server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7070")), reload=True)
