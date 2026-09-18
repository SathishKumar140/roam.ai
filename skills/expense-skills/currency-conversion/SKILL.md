---
name: currency-conversion
description: Estimates currency conversions using provider FX rates without changing the expense ledger
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: expense_specialist
allowed_tools:
  - convert_currency
---

# Currency Conversion Skill

## Overview
Shows informational conversions between explicitly identified currencies. Existing ledger balances remain in their original currencies.

## When to Use
- When receipts or transactions are incurred in foreign currencies during international travel.
- When participants want to know how much an item costs in their home currency.

## Instructions
1. Parse the original amount, base currency, and target currency.
2. Call `convert_currency(amount, from_currency, to_currency)`.
3. Provide the converted amount and the applied exchange rate.
4. Report the rate's date and provider when supplied. Rates may differ from card fees and settlement rates. If unavailable, say so instead of inventing a conversion.
5. Never write a converted amount into the ledger or combine balances across currencies. A conversion request does not authorize an expense proposal or payment.
