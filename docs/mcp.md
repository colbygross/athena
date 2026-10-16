# Athena MCP Server

Athena exposes an [MCP](https://modelcontextprotocol.io) server so your agents (Claude Code on your laptop or in the cloud, scheduled routines, etc.) can read your data and log your job hunt. Athena itself no longer searches for jobs. Agents feed it applications and leads, and the local LLM only runs inbox analysis (nightly, or when you press **Run agent**).

* **Endpoint:** `POST /mcp` on the Athena app (Streamable HTTP, stateless, JSON responses). Code: [backend/mcp_server.py](../backend/mcp_server.py).
* **Auth:** every request needs `Authorization: Bearer <token>`. Each agent has its own token, and only a SHA-256 hash of it is stored.
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

3. **Expose only `/mcp` to the internet with Tailscale Funnel.** Funnel is turned on per port, not per path, so it gets its own port. That keeps the dashboard on 443 tailnet-only:

   ```bash
   sudo tailscale funnel --bg --https=8443 --set-path /mcp http://127.0.0.1:8000/mcp
   tailscale funnel status
   ```

   The public endpoint is `https://<machine>.<tailnet>.ts.net:8443/mcp`. Check that `https://<machine>.<tailnet>.ts.net:8443/` (the dashboard) does **not** load from outside your tailnet. Agents on your tailnet can skip Funnel and use `http://<tailscale-ip>:8000/mcp`.

## Connecting agents

**Claude Code (CLI):**

```bash
claude mcp add --transport http athena https://<machine>.<tailnet>.ts.net:8443/mcp --header "Authorization: Bearer $ATHENA_MCP_TOKEN"
```

**Project `.mcp.json`** (for example, for cloud sessions; set `ATHENA_MCP_TOKEN` as a secret in the environment):

```json
{
  "mcpServers": {
    "athena": {
      "type": "http",
      "url": "https://<machine>.<tailnet>.ts.net:8443/mcp",
      "headers": { "Authorization": "Bearer ${ATHENA_MCP_TOKEN}" }
    }
  }
}
```

**Smoke test:**

```bash
curl -s https://<machine>.<tailnet>.ts.net:8443/mcp \
  -H "Authorization: Bearer $ATHENA_MCP_TOKEN" \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_overview","arguments":{}}}'
```

Responses: `401` means the token is missing or revoked, and `429` means the rate limit was hit. A tool result with `isError: true` means the token lacks the scope or the input was invalid. The message says which.
