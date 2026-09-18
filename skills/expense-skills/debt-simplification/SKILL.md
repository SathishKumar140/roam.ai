---
name: debt-simplification
description: Proposes consent-required expense splits and reads confirmed group balances by currency
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: expense_specialist
allowed_tools:
  - propose_group_expense
  - get_group_balances
---

# Debt Simplification Skill

## Overview
Reads confirmed net balances by currency. Pending and rejected proposals create no debt. The active tools do not execute payments or compute a guaranteed minimum-transaction settlement.

## When to Use
- When participants log shared bills ("Alice paid $90 for dinner with Bob and Charlie").
- When the group asks "Who owes what?" or "Settle up".

## Instructions
1. A payment mention is not consent to split. Offer help, then confirm the amount, currency,
  description, payer and actual participant IDs. Do not invent participants or infer currency from '$'.
2. Use `propose_group_expense` in the scoped planner; all affected members confirm through
  authenticated expense-specific buttons. Use `get_group_balances()` to read confirmed balances.
3. Supply the payer's exact amount and currency quotes with their scoped message IDs. Use the latest evidence, not a year, budget or another member's estimate.
4. Read balances with `get_group_balances`; keep currencies separate. Positive means owed, negative means owes. Do not manufacture ledger entries, approvals, repayments or a computed minimum settlement.
5. Reuse existing tasks. A rejected split cannot be reopened and conflicting retries cannot change its terms. Chat text such as 'yes' is never an authenticated expense confirmation.
