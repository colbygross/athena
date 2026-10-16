"""Finance queries shared by the REST API (main.py) and the MCP server (mcp_server.py)."""
import json
import os

# Static monthly budget, edited by hand in backend/config/budget.json
BUDGET_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "budget.json")

ACCOUNT_BALANCES_SQL = """
    SELECT a.id, a.name, a.type, a.starting_balance,
           a.starting_balance +
           COALESCE((SELECT SUM(amount) FROM transactions WHERE account_id = a.id AND type='income'), 0) -
           COALESCE((SELECT SUM(amount) FROM transactions WHERE account_id = a.id AND type='expense'), 0) -
           COALESCE((SELECT SUM(amount) FROM transactions WHERE account_id = a.id AND type='transfer'), 0) +
           COALESCE((SELECT SUM(amount) FROM transactions WHERE transfer_account_id = a.id AND type='transfer'), 0) as current_balance
    FROM accounts a
"""


def account_balances(cursor):
    cursor.execute(ACCOUNT_BALANCES_SQL)
    return [dict(row) for row in cursor.fetchall()]


def net_wealth(accounts):
    # Credit card balances are negative when money is owed (expenses lower them,
    # payments raise them), so every account simply adds its balance.
    return sum(acc['current_balance'] for acc in accounts)


def load_budgets(path=BUDGET_CONFIG_PATH):
    try:
        with open(path) as f:
            data = json.load(f)
        return [
            {"category": b["category"], "limit_amount": float(b["limit_amount"])}
            for b in data.get("budgets", [])
        ]
    except FileNotFoundError:
        return []
