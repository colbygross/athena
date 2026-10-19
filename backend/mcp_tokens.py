#!/usr/bin/env python3
"""
Manage access to Athena's MCP server.

OAuth (how claude.ai connectors and most MCP clients connect):
  python backend/mcp_tokens.py set-admin-password      # password for the approval page
  python backend/mcp_tokens.py grants                  # approved connections
  python backend/mcp_tokens.py revoke-grant <id>

Static bearer tokens (scripts and clients that can send headers):

  python backend/mcp_tokens.py create <name> --preset job-agent
  python backend/mcp_tokens.py create <name> --scopes career,calendar,career:write
  python backend/mcp_tokens.py list
  python backend/mcp_tokens.py revoke <name>
  python backend/mcp_tokens.py log [--limit 50]

The plaintext token is printed once by `create`; only its hash is stored.
"""
import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, create_new_connection
import mcp_server
import oauth


def main():
    parser = argparse.ArgumentParser(description="Manage Athena MCP agent tokens.")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create a token for an agent")
    create.add_argument("name", help="Agent name, e.g. claude-code-cloud (shown in timelines and the call log)")
    group = create.add_mutually_exclusive_group(required=True)
    group.add_argument("--preset", choices=sorted(mcp_server.SCOPE_PRESETS))
    group.add_argument("--scopes", help=f"Comma-separated: {', '.join(mcp_server.ALL_SCOPES)}")

    sub.add_parser("list", help="List tokens")
    revoke = sub.add_parser("revoke", help="Revoke an agent's token")
    revoke.add_argument("name")
    log = sub.add_parser("log", help="Show recent MCP tool calls")
    log.add_argument("--limit", type=int, default=50)
    pw = sub.add_parser("set-admin-password", help="Set the password for the OAuth approval page")
    pw.add_argument("--stdin", action="store_true", help="Read the password from stdin instead of prompting")
    sub.add_parser("grants", help="List OAuth connections")
    revoke_grant = sub.add_parser("revoke-grant", help="Revoke an OAuth connection and all its tokens")
    revoke_grant.add_argument("id", type=int)

    args = parser.parse_args()
    init_db()

    if args.command == "create":
        scopes = mcp_server.SCOPE_PRESETS[args.preset] if args.preset else [s.strip() for s in args.scopes.split(",") if s.strip()]
        try:
            token = mcp_server.create_token(args.name, scopes)
        except Exception as e:
            sys.exit(f"Error: {e}")
        print(f"Created token for '{args.name}' with scopes: {', '.join(sorted(scopes))}")
        print("Store it now; it cannot be shown again:\n")
        print(token)
    elif args.command == "list":
        for t in mcp_server.list_tokens():
            state = f"revoked {t['revoked_at']}" if t["revoked_at"] else f"last used {t['last_used_at'] or 'never'}"
            print(f"{t['name']:<24} {','.join(t['scopes']):<50} created {t['created_at']}  {state}")
    elif args.command == "revoke":
        if not mcp_server.revoke_token(args.name):
            sys.exit(f"No active token named '{args.name}'")
        print(f"Revoked '{args.name}'.")
    elif args.command == "set-admin-password":
        if args.stdin:
            password = sys.stdin.readline().rstrip("\n")
        else:
            password = getpass.getpass("New admin password: ")
            if getpass.getpass("Repeat: ") != password:
                sys.exit("Passwords don't match.")
        try:
            oauth.set_admin_password(password)
        except ValueError as e:
            sys.exit(f"Error: {e}")
        print("Admin password set.")
    elif args.command == "grants":
        for g in oauth.list_grants():
            state = f"revoked {g['revoked_at']}" if g["revoked_at"] else f"last used {g['last_used_at'] or 'never'}"
            print(f"{g['id']:<4} {g['label']:<28} {g['client']:<20} {','.join(g['scopes']):<50} {state}")
    elif args.command == "revoke-grant":
        if not oauth.revoke_grant(args.id):
            sys.exit(f"No active grant {args.id}")
        print(f"Revoked grant {args.id}.")
    elif args.command == "log":
        conn = create_new_connection()
        try:
            rows = conn.execute(
                "SELECT called_at, token_name, tool, ok, error FROM mcp_call_log ORDER BY id DESC LIMIT ?", (args.limit,)
            ).fetchall()
        finally:
            conn.close()
        for r in reversed(rows):
            status = "ok" if r["ok"] else f"FAILED: {r['error']}"
            print(f"{r['called_at']}  {r['token_name']:<20} {r['tool']:<28} {status}")


if __name__ == "__main__":
    main()
