import json
import uuid
from typing import List, Dict, Any
from langchain_core.tools import tool
from src.storage.database import db
from src.models.session import ExpenseItem, ActiveTripSession

def simplify_debts(expenses: List[ExpenseItem]) -> List[Dict[str, Any]]:
    """
    Minimizes group transactions using bipartite net balance debt simplification (Splitwise algorithm).
    """
    if not expenses:
        return []

    # 1. Compute net balance for each participant
    net_balances: Dict[str, float] = {}
    name_lookup: Dict[str, str] = {}

    for exp in expenses:
        name_lookup[exp.paid_by_user_id] = exp.paid_by_name
        split_count = len(exp.split_between_user_ids) if exp.split_between_user_ids else 1
        share_per_person = exp.amount / split_count

        # Credit the payer
        net_balances[exp.paid_by_user_id] = net_balances.get(exp.paid_by_user_id, 0.0) + exp.amount

        # Debit the consumers
        for user_id in (exp.split_between_user_ids or [exp.paid_by_user_id]):
            net_balances[user_id] = net_balances.get(user_id, 0.0) - share_per_person
            if user_id not in name_lookup:
                name_lookup[user_id] = user_id.title()

    # 2. Separate into debtors (negative balance) and creditors (positive balance)
    debtors = []
    creditors = []

    for uid, balance in net_balances.items():
        if balance < -0.01:
            debtors.append({"user_id": uid, "name": name_lookup.get(uid, uid), "balance": -balance})
        elif balance > 0.01:
            creditors.append({"user_id": uid, "name": name_lookup.get(uid, uid), "balance": balance})

    # 3. Match debtors and creditors greedily
    transfers = []
    debtors.sort(key=lambda x: x["balance"], reverse=True)
    creditors.sort(key=lambda x: x["balance"], reverse=True)

    d_idx = 0
    c_idx = 0

    while d_idx < len(debtors) and c_idx < len(creditors):
        debtor = debtors[d_idx]
        creditor = creditors[c_idx]

        transfer_amt = round(min(debtor["balance"], creditor["balance"]), 2)
        if transfer_amt > 0:
            transfers.append({
                "from_name": debtor["name"],
                "from_id": debtor["user_id"],
                "to_name": creditor["name"],
                "to_id": creditor["user_id"],
                "amount": transfer_amt
            })

        debtor["balance"] -= transfer_amt
        creditor["balance"] -= transfer_amt

        if debtor["balance"] <= 0.01:
            d_idx += 1
        if creditor["balance"] <= 0.01:
            c_idx += 1

    return transfers

@tool
def record_expense(channel_id: str, payer_name: str, amount: float, description: str, split_members: str = "group") -> str:
    """
    Logs an expense paid by someone for the group.
    'split_members' is a comma-separated list of names who shared this expense (e.g. 'Alice, Bob' or 'group'). Default is 'group'.
    """
    trip = db.get_active_trip(channel_id)
    if not trip:
        session_id = f"trip_{channel_id}"
        trip = ActiveTripSession(session_id=session_id, channel_id=channel_id)
        db.save_active_trip(trip)
    else:
        session_id = trip.session_id

    members = [m.strip() for m in (split_members or "group").split(",") if m.strip()]
    if not members or members == ["group"] or members == ["all"]:
        members = ["Alice", "Bob"]

    expense = ExpenseItem(
        expense_id=f"exp_{uuid.uuid4().hex[:8]}",
        paid_by_user_id=payer_name.lower(),
        paid_by_name=payer_name,
        amount=amount,
        currency="USD",
        description=description,
        split_between_user_ids=[m.lower() for m in members]
    )
    db.add_expense(session_id, expense)

    return f"Logged expense: ${amount:.2f} for '{description}' paid by {payer_name} (Split among: {', '.join(members)})."

@tool
def get_balance_sheet(channel_id: str) -> str:
    """
    Calculates who owes what with debt simplification (minimum transfers).
    Returns the current settlement breakdown for the group.
    """
    trip = db.get_active_trip(channel_id)
    if not trip:
        return "No expenses have been recorded for this group yet."

    expenses = db.get_trip_expenses(trip.session_id)
    if not expenses:
        return "The group ledger is currently clean. No expenses recorded."

    transfers = simplify_debts(expenses)
    total_spent = sum(e.amount for e in expenses)

    lines = [
        f"📊 Group Expense Settlement Sheet (Total Spent: ${total_spent:.2f})",
        "────────────────────────────────────────"
    ]
    if not transfers:
        lines.append("✨ All balances are settled up! Nobody owes anything.")
    else:
        for t in transfers:
            lines.append(f"• {t['from_name']} owes {t['to_name']}: ${t['amount']:.2f}")

    return "\n".join(lines)

expense_tools = [record_expense, get_balance_sheet]
