---
name: menu-receipt-ocr
description: Parses items, prices, and tax from photos of printed menus or paper receipts
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: vision_specialist
allowed_tools:
  - inspect_venue_photo
---

# Menu & Receipt OCR Skill

## Overview
Extracts itemized dish lists, prices, currency signs, and bill totals from photos of physical paper receipts or dining menus.

## When to Use
- When someone uploads a photo of a restaurant menu to ask about options.
- When someone snaps a photo of the dinner bill to split costs.

## Instructions
1. Inspect image content using `inspect_venue_photo`.
2. Extract line items, quantities, and subtotal amounts.
3. Identify dish names for dietary filtering (highlight vegan, nut, gluten items).
4. For receipts: summarize the final total and forward item totals to `expense_specialist`.
