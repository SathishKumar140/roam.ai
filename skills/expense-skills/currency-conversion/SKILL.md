---
name: currency-conversion
description: Normalizes international currencies into a single group base currency using real-time FX rates
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: expense_specialist
allowed_tools:
  - convert_currency
---

# Currency Conversion Skill

## Overview
Converts multi-currency transactions into the group's agreed base currency (e.g. USD, EUR, JPY) for consistent expense tracking.

## When to Use
- When receipts or transactions are incurred in foreign currencies during international travel.
- When participants want to know how much an item costs in their home currency.

## Instructions
1. Parse the original amount, base currency, and target currency.
2. Call `convert_currency(amount, from_currency, to_currency)`.
3. Provide the converted amount and the applied exchange rate.
4. Record the normalized amount into the expense ledger with note of original currency.
