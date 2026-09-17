from src.models.session import ExpenseItem
from src.agents.tools.expense_tools import simplify_debts

def test_simple_three_way_split():
    # Alice pays $90 for Alice, Bob, and Charlie
    expenses = [
        ExpenseItem(
            expense_id="e1",
            paid_by_user_id="alice",
            paid_by_name="Alice",
            amount=90.0,
            split_between_user_ids=["alice", "bob", "charlie"],
            description="Seafood Dinner"
        )
    ]

    transfers = simplify_debts(expenses)
    assert len(transfers) == 2
    
    # Sort by amount or recipient to assert
    transfers_dict = {t["from_name"]: t["amount"] for t in transfers}
    assert transfers_dict["Bob"] == 30.0
    assert transfers_dict["Charlie"] == 30.0
    for t in transfers:
        assert t["to_name"] == "Alice"

def test_transitive_debt_simplification():
    # 1. Alice pays $90 for Alice, Bob, Charlie (each owes $30)
    # 2. Bob pays $30 for Alice and Bob (each owes $15)
    # Net:
    # Alice: +90 - 30 - 15 = +$45
    # Bob:   -30 + 30 - 15 = -$15
    # Charlie: -30 = -$30
    # Simplified transfers: Bob pays Alice $15, Charlie pays Alice $30
    expenses = [
        ExpenseItem(
            expense_id="e1",
            paid_by_user_id="alice",
            paid_by_name="Alice",
            amount=90.0,
            split_between_user_ids=["alice", "bob", "charlie"],
            description="Dinner"
        ),
        ExpenseItem(
            expense_id="e2",
            paid_by_user_id="bob",
            paid_by_name="Bob",
            amount=30.0,
            split_between_user_ids=["alice", "bob"],
            description="Taxi"
        )
    ]

    transfers = simplify_debts(expenses)
    assert len(transfers) == 2

    transfers_dict = {t["from_name"]: t["amount"] for t in transfers}
    assert transfers_dict["Bob"] == 15.0
    assert transfers_dict["Charlie"] == 30.0
    for t in transfers:
        assert t["to_name"] == "Alice"

def test_consent_based_expense_confirmation():
    from src.storage.database import db
    from src.agents.tools.expense_tools import record_expense, confirm_expense_split, get_balance_sheet

    channel = "consent_test_channel_1"
    # 1. Alice logs expense of $90 split with Bob
    res = record_expense.invoke({
        "channel_id": channel,
        "payer_name": "Alice",
        "amount": 90.0,
        "description": "Seafood Dinner",
        "split_members": "Alice, Bob"
    })
    assert "PENDING CONSENT" in res or "Pending Consent" in res
    assert "Bob" in res

    # 2. Before Bob confirms, balance sheet should show no active debt
    sheet_before = get_balance_sheet.invoke({"channel_id": channel})
    assert "PENDING CONFIRMATION" in sheet_before
    assert "ACTIVE CONFIRMED DEBTS" not in sheet_before or "No expenses have been finalized yet" in sheet_before

    # 3. Bob confirms ("I'm in")
    conf_res = confirm_expense_split.invoke({
        "channel_id": channel,
        "participant_name": "Bob"
    })
    assert "Bob" in conf_res
    assert "FULLY CONFIRMED" in conf_res or "confirmed" in conf_res.lower()

    # 4. Now balance sheet should show active debt: Bob owes Alice SGD 45.00
    sheet_after = get_balance_sheet.invoke({"channel_id": channel})
    assert "Bob owes Alice" in sheet_after
    assert "45.00" in sheet_after
