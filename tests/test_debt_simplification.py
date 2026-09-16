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
