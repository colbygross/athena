#!/usr/bin/env python3
import sys
import os
import argparse
import json

# Add backend directory to sys.path to ensure database import works regardless of CWD
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from database import get_db_connection

# Helper to format rows as Markdown table
def to_markdown_table(rows, headers):
    if not rows:
        return "No results."
    widths = {h: len(h) for h in headers}
    formatted_rows = []
    for r in rows:
        formatted_row = {}
        for h in headers:
            val = str(r[h]) if r[h] is not None else ""
            formatted_row[h] = val
            widths[h] = max(widths[h], len(val))
        formatted_rows.append(formatted_row)
        
    border_line = "|" + "|".join("-" * (widths[h] + 2) for h in headers) + "|"
    header_line = "|" + "|".join(f" {h:<{widths[h]}} " for h in headers) + "|"
    lines = [header_line, border_line]
    for r in formatted_rows:
        row_line = "|" + "|".join(f" {r[h]:<{widths[h]}} " for h in headers) + "|"
        lines.append(row_line)
    return "\n".join(lines)

def run_query(sql, params=None, raw_json=False):
    params = params or []
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        if sql.strip().upper().startswith("SELECT") or "RETURNING" in sql.strip().upper():
            rows = cursor.fetchall()
            headers = [d[0] for d in cursor.description]
            if raw_json:
                result = [dict(r) for r in rows]
                print(json.dumps(result, indent=2))
            else:
                print(to_markdown_table(rows, headers))
        else:
            conn.commit()
            print(f"Success. Rows affected: {cursor.rowcount}")
    except Exception as e:
        print(f"Error executing query: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

def list_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [r['name'] for r in cursor.fetchall()]
    conn.close()
    return tables

def show_table(table_name, limit=20, raw_json=False):
    tables = list_tables()
    if table_name not in tables:
        print(f"Error: Table '{table_name}' does not exist. Available tables: {', '.join(tables)}", file=sys.stderr)
        sys.exit(1)
    
    # Select default order column if exists
    order_col = "id DESC"
    if table_name == "health_logs":
        order_col = "date DESC"
    elif table_name == "transactions":
        order_col = "date DESC, id DESC"
    elif table_name == "meal_logs":
        order_col = "date DESC, id DESC"
    elif table_name == "mindfulness_logs":
        order_col = "date DESC, id DESC"
    elif table_name == "fitness_logs":
        order_col = "date DESC, id DESC"
    
    sql = f"SELECT * FROM {table_name} ORDER BY {order_col} LIMIT ?;"
    run_query(sql, [limit], raw_json)

def serialize_calendar_if_needed(table_name):
    if table_name == "calendar_events":
        try:
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            import agent
            agent.serialize_local_events_to_ics_helper()
            print("Successfully updated calendar.ics after modifying calendar_events table.")
        except Exception as e:
            print(f"Warning: could not update calendar.ics: {e}")

def insert_row(table_name, data_json):
    try:
        data = json.loads(data_json)
    except Exception as e:
        print(f"Error parsing data JSON: {e}", file=sys.stderr)
        sys.exit(1)
        
    tables = list_tables()
    if table_name not in tables:
        print(f"Error: Table '{table_name}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    if table_name == "calendar_events" and "event_uid" not in data:
        import uuid
        data["event_uid"] = f"{uuid.uuid4()}@local"
        
    columns = list(data.keys())
    placeholders = ", ".join(["?"] * len(columns))
    sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders});"
    run_query(sql, list(data.values()))
    serialize_calendar_if_needed(table_name)

def update_row(table_name, row_id, data_json):
    try:
        data = json.loads(data_json)
    except Exception as e:
        print(f"Error parsing data JSON: {e}", file=sys.stderr)
        sys.exit(1)
        
    tables = list_tables()
    if table_name not in tables:
        print(f"Error: Table '{table_name}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    set_clause = ", ".join([f"{col} = ?" for col in data.keys()])
    
    sql = f"UPDATE {table_name} SET {set_clause} WHERE id = ?;"
    run_query(sql, list(data.values()) + [row_id])
    serialize_calendar_if_needed(table_name)

def delete_row(table_name, row_id):
    tables = list_tables()
    if table_name not in tables:
        print(f"Error: Table '{table_name}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    sql = f"DELETE FROM {table_name} WHERE id = ?;"
    run_query(sql, [row_id])
    serialize_calendar_if_needed(table_name)

def log_nlp_transaction(text, preview=False):
    from agent import parse_natural_language_transaction
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        parsed = parse_natural_language_transaction(text, cursor=cursor)
        
        acc_name = "None"
        if parsed.get("account_id"):
            cursor.execute("SELECT name FROM accounts WHERE id = ?", (parsed["account_id"],))
            row = cursor.fetchone()
            if row:
                acc_name = row["name"]
                
        transfer_acc_name = "None"
        if parsed.get("transfer_account_id"):
            cursor.execute("SELECT name FROM accounts WHERE id = ?", (parsed["transfer_account_id"],))
            row = cursor.fetchone()
            if row:
                transfer_acc_name = row["name"]
                
        print("\n=== Parsed Transaction ===")
        print(f"Date:         {parsed['date']}")
        print(f"Amount:       ${parsed['amount']:.2f}")
        print(f"Type:         {parsed['type'].upper()}")
        print(f"Category:     {parsed['category']}")
        print(f"Merchant:     {parsed['merchant']}")
        print(f"Description:  {parsed['description']}")
        print(f"Account:      {acc_name} (id={parsed['account_id']})")
        if parsed['type'] == 'transfer':
            print(f"Destination:  {transfer_acc_name} (id={parsed['transfer_account_id']})")
            
        if preview:
            print("\n[Preview mode: transaction not saved]")
            return
            
        cursor.execute(
            "INSERT INTO transactions (date, amount, type, category, merchant, description, account_id, transfer_account_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                parsed["date"],
                parsed["amount"],
                parsed["type"],
                parsed["category"],
                parsed["merchant"],
                parsed["description"],
                parsed["account_id"],
                parsed["transfer_account_id"]
            )
        )
        conn.commit()
        tx_id = cursor.lastrowid
        print(f"\n✓ Successfully logged transaction #{tx_id} into ledger.")
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Athena SQLite Database CLI Tool")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")
    
    # list-tables
    subparsers.add_parser("list-tables", help="List all tables in the database")
    
    # show
    show_parser = subparsers.add_parser("show", help="Show entries from a specific table")
    show_parser.add_argument("table", help="Table name")
    show_parser.add_argument("--limit", type=int, default=20, help="Number of rows to return")
    show_parser.add_argument("--json", action="store_true", help="Output raw JSON instead of Markdown table")
    
    # query
    query_parser = subparsers.add_parser("query", help="Run a custom SQL query")
    query_parser.add_argument("sql", help="SQL statement")
    query_parser.add_argument("--json", action="store_true", help="Output raw JSON instead of Markdown table")
    
    # add
    add_parser = subparsers.add_parser("add", help="Add a row to a table")
    add_parser.add_argument("table", help="Table name")
    add_parser.add_argument("data", help="JSON string representing column-value mappings")
    
    # update
    update_parser = subparsers.add_parser("update", help="Update an existing row")
    update_parser.add_argument("table", help="Table name")
    update_parser.add_argument("id", type=int, help="Row ID")
    update_parser.add_argument("data", help="JSON string representing column-value mappings to update")
    
    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete a row from a table")
    delete_parser.add_argument("table", help="Table name")
    delete_parser.add_argument("id", type=int, help="Row ID to delete")

    # log-nlp
    nlp_parser = subparsers.add_parser("log-nlp", help="Log a transaction using natural language via qwen2.5-coder:3b")
    nlp_parser.add_argument("text", help="Natural language description of transaction")
    nlp_parser.add_argument("--preview", action="store_true", help="Preview parsed transaction without committing")
    
    args = parser.parse_args()
    
    if args.command == "list-tables":
        print("\n".join(list_tables()))
    elif args.command == "show":
        show_table(args.table, args.limit, args.json)
    elif args.command == "query":
        run_query(args.sql, raw_json=args.json)
    elif args.command == "add":
        insert_row(args.table, args.data)
    elif args.command == "update":
        update_row(args.table, args.id, args.data)
    elif args.command == "delete":
        delete_row(args.table, args.id)
    elif args.command == "log-nlp":
        log_nlp_transaction(args.text, args.preview)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
