# Athena MCP Server

Athena exposes an [MCP](https://modelcontextprotocol.io) server so your agents (Claude Code on your laptop or in the cloud, scheduled routines, etc.) can read your data and log your job hunt. Athena itself no longer searches for jobs. Agents feed it applications and leads, and the local LLM only runs inbox analysis (nightly, or when you press **Run agent**).

* **Endpoint:** `POST /mcp` on the Athena app (Streamable HTTP, stateless, JSON responses). Code: [backend/mcp_server.py](../backend/mcp_server.py).
* **Auth:** OAuth 2.1 for MCP clients that support it (claude.ai connectors, Claude Code), or a static per-agent bearer token for scripts. Either way the request carries `Authorization: Bearer <token>`, scopes apply, and only SHA-256 hashes are stored. Code: [backend/oauth.py](../backend/oauth.py).
* **Limits:** 60 requests per minute per token (`MCP_RATE_LIMIT_PER_MINUTE`). Every tool call is recorded in the `mcp_call_log` table.

## Scopes and tools

Each domain has a read scope and a matching `:write` scope. The approval page lets you pick exactly which ones a connection gets.

| Domain | Read tools | Write tools (`<domain>:write`) |
| --- | --- | --- |
| *(any)* | `get_overview`: today's snapshot, limited to the connection's scopes | |
| `calendar` | `list_events`, `find_free_time(date)` | `create_event`, `update_event`, `delete_event` (Google-synced like dashboard events) |
| `tasks` | `list_tasks` | `create_task`, `update_task`, `delete_task`, `add_subtask`, `update_subtask`, `delete_subtask` |
| `finances` | `list_transactions`, `get_finance_summary` | `add_transaction`, `update_transaction`, `delete_transaction`, `add_account`, `update_account`, `add_recurring`, `update_recurring`, `pay_recurring`, `delete_recurring`, `save_student_loan` (accounts and loans can't be deleted) |
| `health` | `list_health_logs(kind = vitals \| fitness \| meals \| mindfulness)` | `log_vitals` (merges into the day), `log_workout`, `log_meal`, `log_mindfulness`, `delete_health_entry` |
| `learning` | `list_learning` | `log_learning`, `delete_learning_entry` |
| `habits` | `list_habits` | `log_habit`, `delete_habit_log` |
| `notes` | `list_notes`, `read_note` | `write_note`, `append_to_note`, `delete_note`, `mark_note_private` |
| `career` | `list_applications`, `get_application`, `list_leads` | `log_application`, `update_application`, `update_application_status`, `add_application_event`, `delete_application`, `add_lead`, `dismiss_lead`, `promote_lead` |

Write behavior:

* Writes go through the same code as the dashboard. Events push to Google Calendar, and tasks show up in `tasks.md` and their source notes.
* `log_application` and `add_lead` are safe to repeat: duplicates are updated, and a repeat never moves an application's status backwards.
* Static-token presets: `job-agent`, `full-read`, `full-access`.

## Private data

Mark things private and **no cloud model sees them**. They stay readable on the Athena machine: in Obsidian, in the dashboard, and by the local LLM.

* **A note** is private if its frontmatter has `private: true`, or it lives inside a `Private/` folder.
* **An ingested file** (receipt, PDF, …) is private if it's flagged in the dashboard or its companion note is private.
* **Derived data inherits privacy:**
  * transactions, workouts, vitals and learning entries created from a private file;
  * tasks written inside a private note;
  * lines of daily briefs, summaries and archives built from those. The generators tag these lines with `%%private%%`, an Obsidian comment hidden in reading view; MCP drops the lines and the dashboard hides the tag.
* **To agents, private data looks like it doesn't exist:** it isn't listed, and reading, editing or deleting it returns "not found".
* **Agents may mark a note private (`mark_note_private`) but can never unmark it.** Only the dashboard can, with `GET/POST /api/privacy`. Notes in `Private/` are always private.
* **Account balances and net wealth are totals** and include every transaction. Only per-transaction detail is hidden.

**Limit:** this is enforced in the MCP server. Anything with shell access to the Athena machine (SSH, Claude Code running there) can still read files directly, so don't give cloud agents shell access to the Athena machine.

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
