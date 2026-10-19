import base64
import hashlib
import json
import os
import secrets
import sys
from urllib.parse import parse_qs, urlparse

import pytest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import database
import main
import mcp_server
import oauth
from fastapi.testclient import TestClient

REDIRECT = "https://claude.ai/api/mcp/auth_callback"
PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "oauth.db"))
    monkeypatch.setattr(mcp_server, "rate_limiter", mcp_server.RateLimiter(1000))
    monkeypatch.setattr(oauth, "failed_logins", oauth._FailedLogins())
    database.init_db()
    yield


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


def _pkce():
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def _register(client):
    res = client.post("/register", json={
        "client_name": "Claude", "redirect_uris": [REDIRECT],
        "grant_types": ["authorization_code", "refresh_token"], "token_endpoint_auth_method": "none",
    })
    assert res.status_code == 201, res.text
    return res.json()["client_id"]


def _authorize(client, client_id, challenge, scope=None):
    params = {"response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT,
              "code_challenge": challenge, "code_challenge_method": "S256", "state": "xyz",
              "resource": oauth.RESOURCE_URL}
    if scope:
        params["scope"] = scope
    res = client.get("/authorize", params=params, follow_redirects=False)
    assert res.status_code == 302, res.text
    consent = urlparse(res.headers["location"])
    assert consent.path == "/oauth/consent"
    return parse_qs(consent.query)["request"][0]


def _approve(client, request_id, scopes, password=PASSWORD, label="job-agent"):
    return client.post("/oauth/consent", data={
        "request": request_id, "action": "approve", "password": password, "label": label, "scope": scopes,
    }, follow_redirects=False)


def _connect(client, scopes=("career", "career:write"), label="job-agent"):
    """Run the whole flow and return the token response."""
    oauth.set_admin_password(PASSWORD)
    client_id = _register(client)
    verifier, challenge = _pkce()
    res = _approve(client, _authorize(client, client_id, challenge), list(scopes), label=label)
    assert res.status_code == 302
    query = parse_qs(urlparse(res.headers["location"]).query)
    assert query["state"] == ["xyz"]
    tokens = client.post("/token", data={
        "grant_type": "authorization_code", "code": query["code"][0], "redirect_uri": REDIRECT,
        "client_id": client_id, "code_verifier": verifier,
    })
    assert tokens.status_code == 200, tokens.text
    return client_id, query["code"][0], verifier, tokens.json()


def _mcp(client, token, tool, **arguments):
    return client.post("/mcp", headers={
        "Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }, json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": arguments}})


def test_discovery_metadata(client):
    prm = client.get("/.well-known/oauth-protected-resource").json()
    assert prm["resource"] == oauth.RESOURCE_URL
    assert prm["authorization_servers"] == [oauth.PUBLIC_URL + "/"]
    assert client.get("/.well-known/oauth-protected-resource/mcp").json() == prm

    asm = client.get("/.well-known/oauth-authorization-server").json()
    assert asm["authorization_endpoint"] == oauth.PUBLIC_URL + "/authorize"
    assert asm["registration_endpoint"] == oauth.PUBLIC_URL + "/register"
    assert asm["code_challenge_methods_supported"] == ["S256"]

    res = client.post("/mcp", json={})
    assert res.status_code == 401
    assert f'resource_metadata="{oauth.PROTECTED_RESOURCE_METADATA_URL}"' in res.headers["www-authenticate"]


def test_full_flow_scopes_and_attribution(client):
    _, _, _, tokens = _connect(client)
    assert tokens["scope"] == "career career:write" and tokens["refresh_token"]
    access = tokens["access_token"]

    res = _mcp(client, access, "log_application", company="Acme", role="SWE").json()["result"]
    assert not res["isError"]
    app_id = json.loads(res["content"][0]["text"])["id"]
    app = json.loads(_mcp(client, access, "get_application", application_id=app_id).json()["result"]["content"][0]["text"])
    assert app["created_by"] == "job-agent"

    denied = _mcp(client, access, "list_transactions").json()["result"]
    assert denied["isError"] and "finances" in denied["content"][0]["text"]
    assert oauth.list_grants()[0]["last_used_at"] is not None


def test_code_is_single_use_and_pkce_checked(client):
    client_id, code, verifier, _ = _connect(client)
    again = client.post("/token", data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
                                        "client_id": client_id, "code_verifier": verifier})
    assert again.status_code == 400 and again.json()["error"] == "invalid_grant"

    verifier2, challenge2 = _pkce()
    res = _approve(client, _authorize(client, client_id, challenge2), ["career"])
    code2 = parse_qs(urlparse(res.headers["location"]).query)["code"][0]
    wrong = client.post("/token", data={"grant_type": "authorization_code", "code": code2, "redirect_uri": REDIRECT,
                                        "client_id": client_id, "code_verifier": "not-the-verifier"})
    assert wrong.status_code == 400


def test_refresh_rotates_tokens(client):
    client_id, _, _, tokens = _connect(client)
    new = client.post("/token", data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"],
                                      "client_id": client_id})
    assert new.status_code == 200, new.text
    new = new.json()
    assert new["access_token"] != tokens["access_token"]
    assert _mcp(client, tokens["access_token"], "list_leads").status_code == 401  # old access token retired
    assert _mcp(client, new["access_token"], "list_leads").status_code == 200
    reuse = client.post("/token", data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"],
                                        "client_id": client_id})
    assert reuse.status_code == 400


def test_revoking_grant_cuts_access(client):
    _, _, _, tokens = _connect(client)
    grant_id = oauth.list_grants()[0]["id"]
    assert oauth.revoke_grant(grant_id)
    assert _mcp(client, tokens["access_token"], "list_leads").status_code == 401


def test_consent_page_password_deny_and_lockout(client):
    client_id = _register(client)
    _, challenge = _pkce()
    request_id = _authorize(client, client_id, challenge)
    assert client.get(f"/oauth/consent?request={request_id}").status_code == 503  # no admin password yet

    oauth.set_admin_password(PASSWORD)
    page = client.get(f"/oauth/consent?request={request_id}")
    assert page.status_code == 200 and 'value="career:write"' in page.text
    assert page.headers["x-frame-options"] == "DENY"
    assert _approve(client, request_id, ["career"], password="wrong").status_code == 401
    assert _approve(client, request_id, [], password=PASSWORD).status_code == 400

    deny = client.post("/oauth/consent", data={"request": request_id, "action": "deny"}, follow_redirects=False)
    query = parse_qs(urlparse(deny.headers["location"]).query)
    assert query["error"] == ["access_denied"] and query["state"] == ["xyz"]
    assert client.get(f"/oauth/consent?request={request_id}").status_code == 400  # consumed

    request_id = _authorize(client, client_id, challenge)
    for _ in range(10):
        _approve(client, request_id, ["career"], password="wrong")
    assert _approve(client, request_id, ["career"]).status_code == 429


def test_static_tokens_still_work(client):
    token = mcp_server.create_token("script", ["career"])
    assert _mcp(client, token, "list_leads").status_code == 200


def test_admin_password_rules():
    with pytest.raises(ValueError):
        oauth.set_admin_password("short")
    oauth.set_admin_password(PASSWORD)
    assert oauth.check_admin_password(PASSWORD) and not oauth.check_admin_password("nope")


def test_clients_registered_before_new_scopes_can_request_them(client):
    oauth.set_admin_password(PASSWORD)
    res = client.post("/register", json={"client_name": "Old", "redirect_uris": [REDIRECT], "scope": "career",
                                         "grant_types": ["authorization_code", "refresh_token"],
                                         "token_endpoint_auth_method": "none"})
    client_id = res.json()["client_id"]
    _, challenge = _pkce()
    request_id = _authorize(client, client_id, challenge, scope="career tasks:write")
    page = client.get(f"/oauth/consent?request={request_id}").text
    assert 'value="tasks:write" checked' in page
