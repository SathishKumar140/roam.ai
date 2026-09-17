import json
import uuid
from typing import List, Dict, Any, Optional
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
    In group chats, expenses are logged in 'pending_confirmation' status until all participants confirm/consent.
    'split_members' is a comma-separated list of names who shared this expense (e.g. 'Alice, Bob' or 'group').
    """
    trip = db.get_active_trip(channel_id)
    if not trip:
        session_id = f"trip_{channel_id}"
        trip = ActiveTripSession(session_id=session_id, channel_id=channel_id)
        db.save_active_trip(trip)
    else:
        session_id = trip.session_id

    raw_members = [m.strip() for m in (split_members or "group").split(",") if m.strip()]
    if not raw_members or raw_members == ["group"] or raw_members == ["all"]:
        members = ["Alice", "Bob"]
    else:
        members = raw_members

    clean_payer = payer_name.strip()
    split_user_ids = [m.strip() for m in members]

    # Payer is automatically confirmed
    confirmed = [clean_payer]

    # Check if all participants are already confirmed (e.g., solo expense)
    pending_members = [m for m in split_user_ids if m.lower() != clean_payer.lower()]
    status = "confirmed" if not pending_members else "pending_confirmation"

    expense_id = f"exp_{uuid.uuid4().hex[:8]}"
    expense = ExpenseItem(
        expense_id=expense_id,
        paid_by_user_id=clean_payer.lower(),
        paid_by_name=clean_payer,
        amount=amount,
        currency="SGD",
        description=description,
        split_between_user_ids=split_user_ids,
        confirmed_by_user_ids=confirmed,
        status=status
    )
    db.add_expense(session_id, expense)

    share_per_person = amount / len(split_user_ids) if split_user_ids else amount

    if status == "confirmed":
        return (
            f"✅ Logged expense: SGD {amount:.2f} for '{description}' paid by {clean_payer}.\n"
            f"All participants confirmed. Added to active ledger!"
        )

    return (
        f"🧾 EXPENSE LOGGED: PENDING CONSENT\n"
        f"────────────────────────────────────────\n"
        f"• Bill: SGD {amount:.2f} for '{description}'\n"
        f"• Paid by: {clean_payer}\n"
        f"• Split Among: {', '.join(split_user_ids)} (~SGD {share_per_person:.2f} each)\n"
        f"• Confirmed: {clean_payer} ✅\n"
        f"• Pending Consent: {', '.join(pending_members)} ⏳\n"
        f"• Status: Held in pending confirmation. Debt will NOT be added to balances until members confirm.\n"
        f"👉 Group members: Reply \"I'm in\" or tap [ 👍 I'm In / Confirm ] to confirm your split!"
    )

@tool
def confirm_expense_split(channel_id: str, participant_name: str, expense_id: Optional[str] = None) -> str:
    """
    Registers a group member's consent/confirmation to an expense split.
    Call this whenever a user says "I'm in", "Confirm", "Yes agree", "Count me in", or taps the confirm button.
    """
    trip = db.get_active_trip(channel_id)
    if not trip:
        return f"No active trip found for channel {channel_id}."

    updated = db.confirm_expense_participant(trip.session_id, participant_name, expense_id)
    if not updated:
        return f"No pending expenses found awaiting confirmation for {participant_name}."

    lines = [f"👍 Consent recorded for {participant_name}:"]
    for u in updated:
        if u["status"] == "confirmed":
            lines.append(f"• ✅ '{u['description']}' (SGD {u['amount']:.2f}) is now FULLY CONFIRMED by all participants and active in the ledger!")
        else:
            lines.append(f"• ⏳ '{u['description']}' (SGD {u['amount']:.2f}) confirmed by {participant_name}. Still awaiting: {', '.join(u['pending_for'])}.")
    return "\n".join(lines)

@tool
def get_balance_sheet(channel_id: str) -> str:
    """
    Calculates who owes what with debt simplification (minimum transfers).
    Returns the current settlement breakdown for the group.
    Only confirmed expenses are included in active debt settlement.
    Pending expenses are listed separately awaiting member consent.
    """
    trip = db.get_active_trip(channel_id)
    if not trip:
        return "No expenses have been recorded for this group yet."

    expenses = db.get_trip_expenses(trip.session_id)
    if not expenses:
        return "The group ledger is currently clean. No expenses recorded."

    confirmed = [e for e in expenses if e.status == "confirmed"]
    pending = [e for e in expenses if e.status == "pending_confirmation"]

    total_confirmed = sum(e.amount for e in confirmed)
    transfers = simplify_debts(confirmed)

    lines = [
        f"📊 Group Expense Settlement Sheet (Active Confirmed: SGD {total_confirmed:.2f})",
        "────────────────────────────────────────"
    ]

    if not confirmed:
        lines.append("ℹ️ No expenses have been finalized yet (awaiting participant consent).")
    elif not transfers:
        lines.append("✨ All confirmed balances are settled up! Nobody owes anything.")
    else:
        lines.append("💳 ACTIVE CONFIRMED DEBTS:")
        for t in transfers:
            lines.append(f"• {t['from_name']} owes {t['to_name']}: SGD {t['amount']:.2f}")

    if pending:
        lines.append("")
        lines.append("⏳ PENDING CONFIRMATION (Not in active balance until confirmed):")
        for p in pending:
            pending_users = [u for u in p.split_between_user_ids if not any(c.lower() == u.lower() or u.lower() in c.lower() for c in p.confirmed_by_user_ids)]
            lines.append(f"• SGD {p.amount:.2f} for '{p.description}' (Paid by {p.paid_by_name})")
            lines.append(f"  ├ Confirmed: {', '.join(p.confirmed_by_user_ids)} ✅")
            lines.append(f"  └ Awaiting: {', '.join(pending_users)} ⏳ (Reply 'I\\'m in' to confirm)")

    return "\n".join(lines)

expense_tools = [record_expense, confirm_expense_split, get_balance_sheet]
