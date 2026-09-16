---
name: debt-simplification
description: Calculates minimal cash transaction settlements for group expenses using bipartite graph net balances
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: expense_specialist
allowed_tools:
  - record_expense
  - get_debt_settlement
---

# Debt Simplification Skill

## Overview
Computes net balances across all group participants and executes greedy bipartite graph reduction to minimize the number of repayment transactions (Splitwise-style).

## When to Use
- When participants log shared bills ("Alice paid $90 for dinner with Bob and Charlie").
- When the group asks "Who owes what?" or "Settle up".

## Instructions
1. When an expense is mentioned, log it with `record_expense(payer, amount, description, participants)`.
2. To compute settlements, call `get_debt_settlement()`.
3. Verify that net balances sum to zero across all users.
4. Output concise settlement statements: "Alice pays Bob $30.00".
