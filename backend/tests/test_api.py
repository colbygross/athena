import pytest
import os
import sys

# Set up test database path before importing database or main modules
TEST_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "test_api_life_dashboard.db")
import database
database.DB_PATH = TEST_DB_PATH

# Disable LLM in tests
import agent
agent.LLM_ENABLED = False

from fastapi.testclient import TestClient
import main
from main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """
    Ensure the test database is re-initialized for each test.
    """
    monkeypatch.setattr(database, "DB_PATH", TEST_DB_PATH)
    monkeypatch.setattr(agent, "LLM_ENABLED", False)
    database.init_db()
    yield
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

def test_accounts_endpoints():
    # 1. Get accounts (initially seeds standard accounts Checking, Savings, Credit Card)
    response = client.get("/api/accounts")
    assert response.status_code == 200
    data = response.json()
    assert "accounts" in data
    assert len(data["accounts"]) == 3
    names = [acc["name"] for acc in data["accounts"]]
    assert "Capital One Checking" in names
    assert "Capital One Savings" in names
    assert "Cash" in names

    # 2. Add a new account
    new_account = {
        "name": "Investment Account",
        "type": "investment",
        "starting_balance": 10000.0
    }
    response = client.post("/api/accounts", json=new_account)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    account_id = res_data["id"]

    # 3. Verify accounts list again
    response = client.get("/api/accounts")
    data = response.json()
    accounts = data["accounts"]
    assert len(accounts) == 4
    added = [a for a in accounts if a["id"] == account_id][0]
    assert added["name"] == "Investment Account"
    assert added["current_balance"] == 10000.0

    # 4. Delete the added account
    response = client.delete(f"/api/accounts/{account_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # 5. Verify it's deleted
    response = client.get("/api/accounts")
    data = response.json()
    assert len(data["accounts"]) == 3
    names = [acc["name"] for acc in data["accounts"]]
    assert "Investment Account" not in names


def test_student_loans_endpoints():
    # 1. Get finances (student_loans should be empty initially)
    response = client.get("/api/finances")
    assert response.status_code == 200
    data = response.json()
    assert "student_loans" in data
    assert len(data["student_loans"]) == 0

    # 2. Add a new student loan
    loan_data = {
        "name": "Subsidized Loan 01",
        "type": "subsidized",
        "balance": 5500.0,
        "interest_rate": 4.5,
        "interest_accumulated": 120.0
    }
    response = client.post("/api/student-loans", json=loan_data)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    loan_id = res_data["id"]

    # 3. Verify loan exists in finances
    response = client.get("/api/finances")
    data = response.json()
    assert len(data["student_loans"]) == 1
    added = data["student_loans"][0]
    assert added["id"] == loan_id
    assert added["name"] == "Subsidized Loan 01"
    assert added["type"] == "subsidized"
    assert added["balance"] == 5500.0
    assert added["interest_rate"] == 4.5
    assert added["interest_accumulated"] == 120.0

    # 4. Update the loan details
    update_data = {
        "balance": 5000.0,
        "interest_accumulated": 50.0
    }
    response = client.put(f"/api/student-loans/{loan_id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # 5. Verify updates
    response = client.get("/api/finances")
    data = response.json()
    added = data["student_loans"][0]
    assert added["balance"] == 5000.0
    assert added["interest_accumulated"] == 50.0

    # 6. Delete the loan
    response = client.delete(f"/api/student-loans/{loan_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # 7. Verify deletion
    response = client.get("/api/finances")
    data = response.json()
    assert len(data["student_loans"]) == 0


def test_budgets_endpoints():
    # 1. Get budgets (initially empty)
    response = client.get("/api/budgets")
    assert response.status_code == 200
    assert len(response.json()["budgets"]) == 0

    # 2. Set/Add budget
    budget_data = {
        "category": "food",
        "limit_amount": 500.0
    }
    response = client.post("/api/budgets", json=budget_data)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # 3. Get budgets again
    response = client.get("/api/budgets")
    data = response.json()
    assert len(data["budgets"]) == 1
    assert data["budgets"][0]["category"] == "food"
    assert data["budgets"][0]["limit_amount"] == 500.0

def test_recurring_endpoints():
    # Pre-req: Get account checking id
    acc_res = client.get("/api/accounts")
    checking_id = [a for a in acc_res.json()["accounts"] if a["name"] == "Capital One Checking"][0]["id"]

    # 1. Get recurring (empty)
    response = client.get("/api/recurring")
    assert response.status_code == 200
    assert len(response.json()["recurring"]) == 0

    # 2. Create recurring
    recurring_data = {
        "name": "Netflix",
        "amount": 15.49,
        "interval": "monthly",
        "category": "subscription",
        "account_id": checking_id,
        "next_due_date": "2026-06-01"
    }
    response = client.post("/api/recurring", json=recurring_data)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    recurring_id = res_data["id"]

    # 3. Get recurring and verify
    response = client.get("/api/recurring")
    recurring_list = response.json()["recurring"]
    assert len(recurring_list) == 1
    assert recurring_list[0]["name"] == "Netflix"
    assert recurring_list[0]["next_due_date"] == "2026-06-01"

    # 4. Pay recurring
    pay_res = client.post(f"/api/recurring/{recurring_id}/pay")
    assert pay_res.status_code == 200
    assert pay_res.json()["status"] == "success"
    # Should advance to 2026-07-01
    assert pay_res.json()["next_due_date"] == "2026-07-01"

    # Verify a transaction was logged
    finances_res = client.get("/api/finances")
    txs = finances_res.json()["transactions"]
    assert len(txs) == 1
    assert txs[0]["category"] == "subscription"
    assert txs[0]["amount"] == 15.49
    assert txs[0]["merchant"] == "Netflix"

    # 5. Delete recurring
    del_res = client.delete(f"/api/recurring/{recurring_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"

    # Verify deleted
    response = client.get("/api/recurring")
    assert len(response.json()["recurring"]) == 0

def test_finances_dashboard_and_transactions():
    acc_res = client.get("/api/accounts")
    checking_id = [a for a in acc_res.json()["accounts"] if a["name"] == "Capital One Checking"][0]["id"]
    savings_id = [a for a in acc_res.json()["accounts"] if a["name"] == "Capital One Savings"][0]["id"]

    # 1. Add some transactions
    t1 = {
        "date": "2026-05-15",
        "amount": 2500.0,
        "type": "income",
        "category": "salary",
        "merchant": "ACME Corp",
        "description": "Bi-weekly paycheck",
        "account_id": checking_id
    }
    t2 = {
        "date": "2026-05-16",
        "amount": 45.0,
        "type": "expense",
        "category": "food",
        "merchant": "Whole Foods",
        "description": "Groceries",
        "account_id": checking_id
    }
    t3 = {
        "date": "2026-05-17",
        "amount": 500.0,
        "type": "income",
        "category": "interest",
        "merchant": "Savings Bank",
        "description": "Interest payment",
        "account_id": savings_id
    }

    assert client.post("/api/finances", json=t1).status_code == 200
    assert client.post("/api/finances", json=t2).status_code == 200
    assert client.post("/api/finances", json=t3).status_code == 200

    # 2. Fetch finances dashboard
    response = client.get("/api/finances")
    assert response.status_code == 200
    data = response.json()

    assert len(data["transactions"]) == 3
    # Check Net Wealth: Checking balance is 2500 - 45 = 2455, Savings balance is 500. Net wealth = 2955
    assert data["net_wealth"] == 2955.0

    # Check breakdown (expenses)
    assert len(data["breakdown"]) == 1
    assert data["breakdown"][0]["category"] == "food"
    assert data["breakdown"][0]["total"] == 45.0

    # Check filtered by account
    response_checking = client.get(f"/api/finances?account_id={checking_id}")
    assert len(response_checking.json()["transactions"]) == 2

    # Check filtered by date range
    response_month = client.get("/api/finances?date_range=this_month")
    assert response_month.status_code == 200

def test_meals_endpoints():
    # 1. Get meals (empty)
    res = client.get("/api/meals")
    assert res.status_code == 200
    assert len(res.json()["meals"]) == 0

    # 2. Add meal
    meal_data = {
        "date": "2026-05-23",
        "meal_type": "breakfast",
        "description": "Scrambled eggs and avocado toast",
        "calories": 450,
        "protein_g": 20.0,
        "carbs_g": 30.0,
        "fat_g": 25.0
    }
    res = client.post("/api/meals", json=meal_data)
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    meal_id = res.json()["id"]

    # 3. Get meals for date
    res = client.get("/api/meals?date=2026-05-23")
    assert res.status_code == 200
    meals = res.json()["meals"]
    assert len(meals) == 1
    assert meals[0]["description"] == "Scrambled eggs and avocado toast"
    assert meals[0]["calories"] == 450

    # 4. Delete meal
    res = client.delete(f"/api/meals/{meal_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # Verify deleted
    res = client.get("/api/meals")
    assert len(res.json()["meals"]) == 0

def test_mindfulness_endpoints():
    # 1. Get mindfulness (empty)
    res = client.get("/api/mindfulness")
    assert res.status_code == 200
    assert len(res.json()["mindfulness"]) == 0

    # 2. Add session
    session_data = {
        "date": "2026-05-23",
        "activity_type": "Meditation",
        "duration_minutes": 15,
        "notes": "Focused on breathing"
    }
    res = client.post("/api/mindfulness", json=session_data)
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    session_id = res.json()["id"]

    # 3. Get sessions
    res = client.get("/api/mindfulness")
    assert res.status_code == 200
    sessions = res.json()["mindfulness"]
    assert len(sessions) == 1
    assert sessions[0]["activity_type"] == "Meditation"

    # 4. Delete session
    res = client.delete(f"/api/mindfulness/{session_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # Verify deleted
    res = client.get("/api/mindfulness")
    assert len(res.json()["mindfulness"]) == 0

def test_extended_health_and_wellbeing():
    # 1. Log health vitals with extended columns
    health_data = {
        "date": "2026-05-23",
        "weight_lbs": 159.8,
        "sleep_hours": 8.0,
        "mood": "8/10",
        "systolic": 120,
        "diastolic": 80,
        "notes": "Felt good",
        "water_ml": 2000,
        "energy_level": 8,
        "stress_level": 3
    }
    res = client.post("/api/health", json=health_data)
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # 2. Get health logs and verify the calculated wellbeing score
    res = client.get("/api/health")
    assert res.status_code == 200
    logs = res.json()["logs"]
    assert len(logs) == 1
    log = logs[0]
    assert log["water_ml"] == 2000
    assert log["energy_level"] == 8
    assert log["stress_level"] == 3
    assert "wellbeing_score" in log
    # Sleep score: 20
    # Mood score: 16 (8 * 2)
    # Water score: 20 (2000/2000 * 20)
    # Energy score: 16 (8 * 2)
    # Stress score: 16 ((11-3)*2)
    # Workout bonus: 0
    # Mindfulness bonus: 0
    # Total = 20 + 16 + 20 + 16 + 16 = 88
    assert log["wellbeing_score"] == 88

def test_resources_endpoints():
    # 1. Get resources
    response = client.get("/api/resources")
    assert response.status_code == 200
    data = response.json()
    assert "resources" in data
    
    # 2. Add/create a resource note
    res_data = {
        "content": "# Test Resource\nThis is a test resource note."
    }
    response = client.post("/api/resources/test_note.md", json=res_data)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # 3. Get the resource content
    response = client.get("/api/resources/test_note.md")
    assert response.status_code == 200
    assert response.json()["filename"] == "test_note.md"
    assert response.json()["content"] == "# Test Resource\nThis is a test resource note."

def test_finances_log_nlp_endpoint():
    # 1. Test preview mode (no DB insertion)
    prev_res = client.post("/api/finances/log-nlp", json={
        "text": "Spent $22.50 at Trader Joe's with Capital One Checking",
        "preview": True
    })
    assert prev_res.status_code == 200
    prev_data = prev_res.json()
    assert prev_data["status"] == "preview"
    assert prev_data["parsed"]["amount"] == 22.50
    assert prev_data["parsed"]["account_id"] is not None

    # Check that transaction was NOT logged
    finances_res1 = client.get("/api/finances")
    initial_count = len(finances_res1.json()["transactions"])

    # 2. Test commit mode (DB insertion)
    commit_res = client.post("/api/finances/log-nlp", json={
        "text": "Spent $22.50 at Trader Joe's with Capital One Checking",
        "preview": False
    })
    assert commit_res.status_code == 200
    commit_data = commit_res.json()
    assert commit_data["status"] == "success"
    assert "id" in commit_data
    assert commit_data["parsed"]["amount"] == 22.50

    # Check that transaction was logged
    finances_res2 = client.get("/api/finances")
    new_txs = finances_res2.json()["transactions"]
    assert len(new_txs) == initial_count + 1
    assert any(t["id"] == commit_data["id"] for t in new_txs)
