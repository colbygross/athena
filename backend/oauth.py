"""
OAuth 2.1 for Athena's MCP server, so MCP clients (claude.ai connectors, Claude Code, ...)
connect by URL and an approval click instead of copying tokens around.

Athena is both the authorization server and the protected resource:
  /.well-known/oauth-protected-resource[/mcp]  RFC 9728 metadata for /mcp
  /.well-known/oauth-authorization-server      RFC 8414 metadata
  /register  /authorize  /token  /revoke       handled by the MCP SDK (PKCE S256, DCR)
  /oauth/consent                               Athena's approval page (admin password + scope picker)

Each approval is a grant (oauth_grants) with a label, scopes and rotating tokens; revoking the
grant revokes all of its tokens. Authorization codes and tokens are stored only as SHA-256 hashes.

Config: ATHENA_PUBLIC_URL (the public origin, e.g. https://host.tailnet.ts.net) and an admin
password set with `python backend/mcp_tokens.py set-admin-password`.
"""
import hashlib
import hmac
import html
import json
import os
import secrets
import threading
import time
from urllib.parse import urlparse

from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Route

from mcp.server.auth.handlers.metadata import ProtectedResourceMetadataHandler
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.server.auth.routes import cors_middleware, create_auth_routes
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken, ProtectedResourceMetadata

from database import create_new_connection
from mcp_server import ALL_SCOPES, DOMAINS

PUBLIC_URL = os.getenv("ATHENA_PUBLIC_URL", "http://localhost:8000").rstrip("/")
RESOURCE_URL = f"{PUBLIC_URL}/mcp"
PROTECTED_RESOURCE_METADATA_URL = f"{PUBLIC_URL}/.well-known/oauth-protected-resource"

ACCESS_TOKEN_TTL = 60 * 60            # 1 hour
REFRESH_TOKEN_TTL = 60 * 60 * 24 * 30  # 30 days, rotated on every use
CODE_TTL = 5 * 60
PENDING_TTL = 10 * 60

# Scopes pre-checked on the approval page when the client doesn't ask for specific ones.
DEFAULT_SCOPES = list(ALL_SCOPES)

SCOPE_LABELS = {
    "career": "Read job applications and leads",
    "calendar": "Read calendar events",
    "tasks": "Read tasks",
    "finances": "Read transactions, balances and budgets",
    "health": "Read health, fitness, meals and mindfulness logs",
    "learning": "Read the learning log",
    "habits": "Read habit check-ins",
    "notes": "Read daily briefs and vault notes",
    "career:write": "Log applications, timeline events and leads",
    "calendar:write": "Create, change and delete calendar events (incl. Google Calendar)",
    "tasks:write": "Create, change, complete and delete tasks",
    "finances:write": "Record and edit transactions, accounts, recurring payments and loans",
    "health:write": "Log and delete vitals, workouts, meals and mindfulness",
    "learning:write": "Log and delete study time",
    "habits:write": "Check off habits",
    "notes:write": "Write, append to, delete and mark notes private",
}


def _hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now():
    return int(time.time())


def _db():
    return create_new_connection()


# --- Admin password -----------------------------------------------------------

def set_admin_password(password):
    if len(password) < 10:
        raise ValueError("Use at least 10 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    value = f"scrypt${salt.hex()}${digest.hex()}"
    conn = _db()
    try:
        conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('admin_password', ?)", (value,))
        conn.commit()
    finally:
        conn.close()


def admin_password_is_set():
    conn = _db()
    try:
        return conn.execute("SELECT 1 FROM app_settings WHERE key = 'admin_password'").fetchone() is not None
    finally:
        conn.close()


def check_admin_password(password):
    conn = _db()
    try:
        row = conn.execute("SELECT value FROM app_settings WHERE key = 'admin_password'").fetchone()
    finally:
        conn.close()
    if not row or not password:
        return False
    _, salt_hex, digest_hex = row["value"].split("$")
    digest = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
    return hmac.compare_digest(digest.hex(), digest_hex)


class _FailedLogins:
    """Global lockout for the single-user approval page: 10 bad passwords per 15 minutes."""

    def __init__(self, limit=10, window=15 * 60):
        self.limit, self.window, self._times, self._lock = limit, window, [], threading.Lock()

    def locked(self):
        with self._lock:
            cutoff = time.monotonic() - self.window
            self._times = [t for t in self._times if t > cutoff]
            return len(self._times) >= self.limit

    def record(self):
        with self._lock:
            self._times.append(time.monotonic())


failed_logins = _FailedLogins()


# --- Grants -------------------------------------------------------------------

def list_grants():
    conn = _db()
    try:
        rows = conn.execute("""
            SELECT g.id, g.label, g.scopes, g.created_at, g.last_used_at, g.revoked_at, c.client_info
            FROM oauth_grants g LEFT JOIN oauth_clients c ON c.client_id = g.client_id ORDER BY g.id
        """).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        client = json.loads(r["client_info"]) if r["client_info"] else {}
        out.append({**{k: r[k] for k in ("id", "label", "created_at", "last_used_at", "revoked_at")},
                    "scopes": json.loads(r["scopes"]), "client": client.get("client_name") or "unknown client"})
    return out


def revoke_grant(grant_id):
    conn = _db()
    try:
        cur = conn.execute(
            "UPDATE oauth_grants SET revoked_at = CURRENT_TIMESTAMP WHERE id = ? AND revoked_at IS NULL", (grant_id,)
        )
        conn.execute(
            "UPDATE oauth_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE grant_id = ? AND revoked_at IS NULL", (grant_id,)
        )
        conn.execute("DELETE FROM oauth_codes WHERE grant_id = ?", (grant_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def verify_access_token(token):
    """Return {"name", "scopes"} for a live OAuth access token, or None. Used by the /mcp endpoint."""
    if not token:
        return None
    conn = _db()
    try:
        row = conn.execute("""
            SELECT t.scopes, g.id AS grant_id, g.label FROM oauth_tokens t JOIN oauth_grants g ON g.id = t.grant_id
            WHERE t.token_hash = ? AND t.kind = 'access' AND t.revoked_at IS NULL AND g.revoked_at IS NULL
              AND t.expires_at > ?
        """, (_hash(token), _now())).fetchone()
        if not row:
            return None
        conn.execute("UPDATE oauth_grants SET last_used_at = CURRENT_TIMESTAMP WHERE id = ?", (row["grant_id"],))
        conn.commit()
        return {"name": row["label"], "scopes": set(json.loads(row["scopes"]))}
    finally:
        conn.close()


def _issue_tokens(conn, grant_id, scopes, resource):
    access, refresh = "atk_" + secrets.token_urlsafe(32), "rtk_" + secrets.token_urlsafe(32)
    for kind, token, ttl in (("access", access, ACCESS_TOKEN_TTL), ("refresh", refresh, REFRESH_TOKEN_TTL)):
        conn.execute(
            "INSERT INTO oauth_tokens (grant_id, kind, token_hash, scopes, resource, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
            (grant_id, kind, _hash(token), json.dumps(scopes), resource, _now() + ttl)
        )
    return OAuthToken(access_token=access, token_type="Bearer", expires_in=ACCESS_TOKEN_TTL,
                      refresh_token=refresh, scope=" ".join(scopes))


# --- Provider (called by the MCP SDK's OAuth handlers) -------------------------

class AthenaAuthorizationCode(AuthorizationCode):
    grant_id: int


class AthenaRefreshToken(RefreshToken):
    grant_id: int
    resource: str | None = None


class AthenaAccessToken(AccessToken):
    grant_id: int


class AthenaOAuthProvider:
    async def get_client(self, client_id):
        conn = _db()
        try:
            row = conn.execute("SELECT client_info FROM oauth_clients WHERE client_id = ?", (client_id,)).fetchone()
        finally:
            conn.close()
        return OAuthClientInformationFull.model_validate_json(row["client_info"]) if row else None

    async def register_client(self, client_info):
        conn = _db()
        try:
            conn.execute("INSERT INTO oauth_clients (client_id, client_info) VALUES (?, ?)",
                         (client_info.client_id, client_info.model_dump_json()))
            conn.commit()
        finally:
            conn.close()

    async def authorize(self, client, params: AuthorizationParams):
        """Park the request and send the browser to Athena's approval page."""
        request_id = secrets.token_urlsafe(24)
        conn = _db()
        try:
            conn.execute("DELETE FROM oauth_pending WHERE created_at < ?", (time.time() - PENDING_TTL,))
            conn.execute("INSERT INTO oauth_pending (request_id, client_id, params, created_at) VALUES (?, ?, ?, ?)",
                         (request_id, client.client_id, params.model_dump_json(), time.time()))
            conn.commit()
        finally:
            conn.close()
        return f"{PUBLIC_URL}/oauth/consent?request={request_id}"

    async def load_authorization_code(self, client, authorization_code):
        conn = _db()
        try:
            row = conn.execute("SELECT grant_id, data, expires_at FROM oauth_codes WHERE code_hash = ?",
                               (_hash(authorization_code),)).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        data = json.loads(row["data"])
        if data["client_id"] != client.client_id:
            return None
        return AthenaAuthorizationCode(code=authorization_code, expires_at=row["expires_at"], grant_id=row["grant_id"], **data)

    async def exchange_authorization_code(self, client, authorization_code: AthenaAuthorizationCode):
        conn = _db()
        try:
            # Codes are single use: delete first, and fail if someone else already did.
            if conn.execute("DELETE FROM oauth_codes WHERE code_hash = ?", (_hash(authorization_code.code),)).rowcount != 1:
                raise TokenError(error="invalid_grant", error_description="authorization code already used")
            tokens = _issue_tokens(conn, authorization_code.grant_id, authorization_code.scopes, authorization_code.resource)
            conn.commit()
            return tokens
        finally:
            conn.close()

    async def load_refresh_token(self, client, refresh_token):
        conn = _db()
        try:
            row = conn.execute("""
                SELECT t.grant_id, t.scopes, t.resource, t.expires_at FROM oauth_tokens t
                JOIN oauth_grants g ON g.id = t.grant_id
                WHERE t.token_hash = ? AND t.kind = 'refresh' AND t.revoked_at IS NULL
                  AND g.revoked_at IS NULL AND g.client_id = ?
            """, (_hash(refresh_token), client.client_id)).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return AthenaRefreshToken(token=refresh_token, client_id=client.client_id, scopes=json.loads(row["scopes"]),
                                  expires_at=row["expires_at"], grant_id=row["grant_id"], resource=row["resource"])

    async def exchange_refresh_token(self, client, refresh_token: AthenaRefreshToken, scopes):
        conn = _db()
        try:
            # Rotate: the used refresh token and the grant's older access tokens stop working.
            if conn.execute("UPDATE oauth_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE token_hash = ? AND revoked_at IS NULL",
                            (_hash(refresh_token.token),)).rowcount != 1:
                raise TokenError(error="invalid_grant", error_description="refresh token already used")
            conn.execute("UPDATE oauth_tokens SET revoked_at = CURRENT_TIMESTAMP WHERE grant_id = ? AND kind = 'access' AND revoked_at IS NULL",
                         (refresh_token.grant_id,))
            tokens = _issue_tokens(conn, refresh_token.grant_id, scopes, refresh_token.resource)
            conn.commit()
            return tokens
        finally:
            conn.close()

    async def load_access_token(self, token):
        conn = _db()
        try:
            row = conn.execute("""
                SELECT t.grant_id, t.scopes, t.resource, t.expires_at, g.client_id FROM oauth_tokens t
                JOIN oauth_grants g ON g.id = t.grant_id
                WHERE t.token_hash = ? AND t.kind = 'access' AND t.revoked_at IS NULL AND g.revoked_at IS NULL
            """, (_hash(token),)).fetchone()
        finally:
            conn.close()
        if not row or row["expires_at"] <= _now():
            return None
        return AthenaAccessToken(token=token, client_id=row["client_id"], scopes=json.loads(row["scopes"]),
                                 expires_at=row["expires_at"], resource=row["resource"], grant_id=row["grant_id"])

    async def revoke_token(self, token):
        revoke_grant(token.grant_id)


provider = AthenaOAuthProvider()


# --- Approval page ------------------------------------------------------------

_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Connect to Athena</title>
<style>
:root {{ --bg:#0b0b0c; --panel:#141416; --line:#2a2a2e; --text:#ededed; --muted:#9a9aa0; --accent:#f2f2f2; --danger:#ff6b6b; }}
@media (prefers-color-scheme: light) {{ :root {{ --bg:#f6f6f4; --panel:#fff; --line:#dcdcd6; --text:#151515; --muted:#5f5f5a; --accent:#111; --danger:#b42318; }} }}
* {{ box-sizing:border-box }} body {{ margin:0; background:var(--bg); color:var(--text);
  font:15px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; display:flex; justify-content:center; padding:32px 16px; }}
main {{ width:100%; max-width:460px; background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:24px; }}
h1 {{ font-size:20px; letter-spacing:.08em; text-transform:uppercase; margin:0 0 4px }}
p {{ color:var(--muted); margin:0 0 16px }} .err {{ color:var(--danger) }}
fieldset {{ border:1px solid var(--line); border-radius:8px; margin:0 0 16px; padding:8px 12px }}
legend {{ color:var(--muted); padding:0 4px }}
label.scope {{ display:flex; gap:10px; align-items:flex-start; padding:6px 0 }}
label.scope small {{ display:block; color:var(--muted) }}
input[type=text], input[type=password] {{ width:100%; padding:10px; margin:4px 0 14px; border-radius:8px;
  border:1px solid var(--line); background:var(--bg); color:var(--text); font:inherit }}
.row {{ display:flex; gap:10px }} button {{ flex:1; padding:12px; border-radius:8px; font:inherit; cursor:pointer;
  border:1px solid var(--line); background:transparent; color:var(--text) }}
button.primary {{ background:var(--accent); color:var(--bg); border-color:var(--accent) }}
</style></head><body><main>{body}</main></body></html>"""


def _page(body, status=200):
    return HTMLResponse(_PAGE.format(body=body), status_code=status, headers={
        "Cache-Control": "no-store", "X-Frame-Options": "DENY", "Content-Security-Policy": "frame-ancestors 'none'"})


def _load_pending(request_id):
    conn = _db()
    try:
        row = conn.execute("SELECT client_id, params, created_at FROM oauth_pending WHERE request_id = ?",
                           (request_id or "",)).fetchone()
        if not row or row["created_at"] < time.time() - PENDING_TTL:
            return None, None
        client = conn.execute("SELECT client_info FROM oauth_clients WHERE client_id = ?", (row["client_id"],)).fetchone()
    finally:
        conn.close()
    if not client:
        return None, None
    return (OAuthClientInformationFull.model_validate_json(client["client_info"]),
            AuthorizationParams.model_validate_json(row["params"]))


def _consent_form(request_id, client, params, error=None):
    requested = params.scopes or DEFAULT_SCOPES
    name = html.escape(client.client_name or "An MCP client")
    host = html.escape(urlparse(str(params.redirect_uri)).netloc)
    boxes = "".join(
        f'<label class="scope"><input type="checkbox" name="scope" value="{html.escape(s)}"'
        f'{" checked" if s in requested else ""}><span>{html.escape(s)}<small>{html.escape(SCOPE_LABELS[s])}</small></span></label>'
        for s in ALL_SCOPES
    )
    err = f'<p class="err">{html.escape(error)}</p>' if error else ""
    return f"""<h1>Connect to Athena</h1>
<p><strong>{name}</strong> wants access to your Athena data. You'll return to <strong>{host}</strong> afterwards.</p>{err}
<form method="post" action="/oauth/consent">
<input type="hidden" name="request" value="{html.escape(request_id)}">
<fieldset><legend>Allow</legend>{boxes}</fieldset>
<label for="label">Name this connection</label>
<input type="text" id="label" name="label" maxlength="60" value="{name}">
<label for="password">Athena admin password</label>
<input type="password" id="password" name="password" autocomplete="current-password" required autofocus>
<div class="row"><button type="submit" name="action" value="deny" formnovalidate>Deny</button>
<button type="submit" name="action" value="approve" class="primary">Approve</button></div>
</form>"""


async def consent_page(request: Request) -> Response:
    request_id = request.query_params.get("request") if request.method == "GET" else (await request.form()).get("request")
    client, params = _load_pending(request_id)
    if not client:
        return _page("<h1>Link expired</h1><p>Start connecting again from your MCP client.</p>", 400)
    if not admin_password_is_set():
        return _page("<h1>Not set up</h1><p>Set an admin password on the Athena host first:<br>"
                     "<code>python backend/mcp_tokens.py set-admin-password</code></p>", 503)
    if request.method == "GET":
        return _page(_consent_form(request_id, client, params))

    form = await request.form()

    def finish(**query):
        conn = _db()
        try:
            conn.execute("DELETE FROM oauth_pending WHERE request_id = ?", (request_id,))
            conn.commit()
        finally:
            conn.close()
        return RedirectResponse(construct_redirect_uri(str(params.redirect_uri), state=params.state, **query), status_code=302)

    if form.get("action") != "approve":
        return finish(error="access_denied", error_description="The user denied the request")
    if failed_logins.locked():
        return _page(_consent_form(request_id, client, params, "Too many wrong passwords. Try again in 15 minutes."), 429)
    if not check_admin_password(form.get("password", "")):
        failed_logins.record()
        return _page(_consent_form(request_id, client, params, "Wrong password."), 401)

    scopes = [s for s in ALL_SCOPES if s in form.getlist("scope")]
    if not scopes:
        return _page(_consent_form(request_id, client, params, "Pick at least one permission."), 400)
    label = (form.get("label") or client.client_name or "mcp-client").strip()[:60]

    code = secrets.token_urlsafe(32)
    conn = _db()
    try:
        grant_id = conn.execute("INSERT INTO oauth_grants (client_id, label, scopes) VALUES (?, ?, ?)",
                                (client.client_id, label, json.dumps(scopes))).lastrowid
        conn.execute("INSERT INTO oauth_codes (code_hash, grant_id, data, expires_at) VALUES (?, ?, ?, ?)", (
            _hash(code), grant_id,
            json.dumps({"client_id": client.client_id, "code_challenge": params.code_challenge, "scopes": scopes,
                        "redirect_uri": str(params.redirect_uri),
                        "redirect_uri_provided_explicitly": params.redirect_uri_provided_explicitly,
                        "resource": params.resource}),
            time.time() + CODE_TTL))
        conn.commit()
    finally:
        conn.close()
    return finish(code=code)


# --- Routes -------------------------------------------------------------------

def routes():
    """OAuth discovery, SDK endpoints and the approval page, all at the app root."""
    resource_metadata = ProtectedResourceMetadataHandler(ProtectedResourceMetadata(
        resource=AnyHttpUrl(RESOURCE_URL), authorization_servers=[AnyHttpUrl(PUBLIC_URL)], scopes_supported=list(ALL_SCOPES),
    ))
    prm = cors_middleware(resource_metadata.handle, ["GET", "OPTIONS"])
    return [
        *create_auth_routes(
            provider, issuer_url=AnyHttpUrl(PUBLIC_URL),
            client_registration_options=ClientRegistrationOptions(
                enabled=True, valid_scopes=list(ALL_SCOPES), default_scopes=list(ALL_SCOPES)),
            revocation_options=RevocationOptions(enabled=True),
        ),
        # RFC 9728: clients look at the root and at the path-suffixed form for the /mcp resource.
        Route("/.well-known/oauth-protected-resource", endpoint=prm, methods=["GET", "OPTIONS"]),
        Route("/.well-known/oauth-protected-resource/mcp", endpoint=prm, methods=["GET", "OPTIONS"]),
        Route("/oauth/consent", endpoint=consent_page, methods=["GET", "POST"]),
    ]


# Paths the dashboard's own CORS/API-key middleware must leave alone (they set their own CORS).
OAUTH_PATH_PREFIXES = ("/.well-known/oauth-", "/authorize", "/token", "/register", "/revoke", "/oauth/", "/mcp")
