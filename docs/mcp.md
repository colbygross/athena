# Athena MCP Server

Athena exposes an [MCP](https://modelcontextprotocol.io) server so your agents (Claude Code on your laptop or in the cloud, scheduled routines, etc.) can read your data and log your job hunt. Athena itself no longer searches for jobs. Agents feed it applications and leads, and the local LLM only runs inbox analysis (nightly, or when you press **Run agent**).

* **Endpoint:** `POST /mcp` on the Athena app (Streamable HTTP, stateless, JSON responses). Code: [backend/mcp_server.py](../backend/mcp_server.py).
* **Auth:** OAuth 2.1 for MCP clients that support it (claude.ai connectors, Claude Code), or a static per-agent bearer token for scripts. Either way the request carries `Authorization: Bearer <token>`, scopes apply, and only SHA-256 hashes are stored. Code: [backend/oauth.py](../backend/oauth.py).
* **Limits:** 60 requests per minute per token (`MCP_RATE_LIMIT_PER_MINUTE`). Every tool call is recorded in the `mcp_call_log` table.

## Scopes and tools

A token can read only the domains in its scopes. Career is the only domain agents can write to.

| Scope | Tools |
| --- | --- |
| *(any)* | `get_overview`: today's snapshot, limited to the token's scopes |
| `calendar` | `list_events(start_date, end_date)` |
| `tasks` | `list_tasks(status, due_before, category)` |
| `finances` | `list_transactions(start_date, end_date, account_id, category)`, `get_finance_summary()` |
| `health` | `list_health_logs(kind = vitals \| fitness \| meals \| mindfulness, start_date, end_date)` |
| `learning` | `list_learning(start_date, end_date)` |
| `habits` | `list_habits(start_date, end_date)` |
| `notes` | `list_notes(folder)`, `read_note(path)`: daily briefs, summaries, projects, areas, resources, archives |
| `career` | `list_applications(status)`, `get_application(id)`, `list_leads(status)` |
| `career:write` | `log_application`, `update_application_status`, `add_application_event`, `add_lead`, `dismiss_lead`, `promote_lead` |

Presets:

* `job-agent`: `career`, `calendar`, `tasks`, `career:write`
* `full-read`: every read scope, no writes

Write behavior:

* `log_application` is safe to repeat. It updates an existing application with the same job URL, or with the same company and role (case-insensitive) within 90 days. Blank fields never overwrite data, and a repeat never moves the status backwards.
* `add_lead` updates a lead that has the same URL.
* Status changes and events go on the application's timeline (`application_events`) along with the token name that made them.

## Host setup (run on the Athena machine)

1. **Deploy this version.** `requirements.txt` changed (`mcp` was added and `playwright` removed), so rebuild the image:

   ```bash
   docker compose up -d --build
   ```

   On first start, the database migration backs up the retired job-hunt data (search profiles, outreach logs, tailored bullets, cover letters, cold emails) to `storage/career_backup_<timestamp>.json`, then drops it.

2. **Create a token for each agent:**

   ```bash
   docker compose exec athena python backend/mcp_tokens.py create claude-code-cloud --preset job-agent
   docker compose exec athena python backend/mcp_tokens.py list
   docker compose exec athena python backend/mcp_tokens.py revoke claude-code-cloud
   docker compose exec athena python backend/mcp_tokens.py log --limit 20
   ```

   The token is printed once. Store it in the agent's secret store.

3. **Set the public URL and the admin password** (the password unlocks the approval page):

   ```bash
   echo 'ATHENA_PUBLIC_URL=https://<machine>.<tailnet>.ts.net' >> .env
   docker compose up -d
   docker compose exec athena python backend/mcp_tokens.py set-admin-password
   ```

4. **Expose only the MCP and OAuth paths with Tailscale Funnel**, on the standard HTTPS port (443). claude.ai's connector service won't dial non-standard ports like 8443. Only these paths are proxied, so `/` (the dashboard) and `/api` stay tailnet-only:

   ```bash
   for p in /mcp /.well-known/oauth-protected-resource /.well-known/oauth-authorization-server \
            /authorize /token /register /revoke /oauth; do
     sudo tailscale funnel --bg --https=443 --set-path "$p" "http://127.0.0.1:8000$p"
   done
   tailscale funnel status
   ```

   Check that `https://<machine>.<tailnet>.ts.net/` (the dashboard) returns 404 from outside your tailnet. Don't add a handler for `/` on port 443.

## Connecting agents

**claude.ai (and cloud routines):** go to Settings → Connectors → *Add custom connector* and enter `https://<machine>.<tailnet>.ts.net/mcp`. Leave the OAuth fields empty. claude.ai registers itself and opens Athena's approval page. Pick the permissions, name the connection, enter the admin password, and approve. Routines can then use the connector.

Manage connections:

```bash
docker compose exec athena python backend/mcp_tokens.py grants
docker compose exec athena python backend/mcp_tokens.py revoke-grant <id>
```

**Claude Code (CLI):**

```bash
claude mcp add --transport http athena https://<machine>.<tailnet>.ts.net/mcp --header "Authorization: Bearer $ATHENA_MCP_TOKEN"
```

**Project `.mcp.json`** (for example, for cloud sessions; set `ATHENA_MCP_TOKEN` as a secret in the environment):

```json
{
  "mcpServers": {
    "athena": {
      "type": "http",
      "url": "https://<machine>.<tailnet>.ts.net/mcp",
      "headers": { "Authorization": "Bearer ${ATHENA_MCP_TOKEN}" }
    }
  }
}
```

**Smoke test:**

```bash
curl -s https://<machine>.<tailnet>.ts.net/mcp \
  -H "Authorization: Bearer $ATHENA_MCP_TOKEN" \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_overview","arguments":{}}}'
```

Responses: `401` means the token is missing or revoked, and `429` means the rate limit was hit. A tool result with `isError: true` means the token lacks the scope or the input was invalid. The message says which.
