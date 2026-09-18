---
name: menu-receipt-ocr
description: Parses items, prices, and tax from photos of printed menus or paper receipts
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: vision_specialist
allowed_tools:
  - analyze_attached_image
---

# Menu & Receipt OCR Skill

## Overview
Extracts itemized dish lists, prices, currency signs, and bill totals from photos of physical paper receipts or dining menus.

## When to Use
- When someone uploads a photo of a restaurant menu to ask about options.
- When someone snaps a photo of the dinner bill to split costs.

## Instructions
1. Inspect only this request's image using `analyze_attached_image`. Missing or unreadable attachments require clarification, not a cached image from another conversation.
2. Extract line items, quantities, and subtotal amounts.
3. Identify visible dietary labels; ingredients and allergen safety not printed on the menu remain unverified.
4. For receipts, distinguish subtotal, tax, tip and final total; mark unreadable digits unknown. '$' does not establish a currency.
5. Return the transcription to the supervisor. The payer must confirm amount, currency and participants in chat before the expense specialist can propose a split. The image itself is not consent or payer-authored amount evidence.
