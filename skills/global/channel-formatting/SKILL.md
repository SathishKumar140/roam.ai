---
name: channel-formatting
description: Formats conversational outputs for Telegram inline keyboards and WhatsApp interactive quick-replies
license: MIT
compatibility: Python 3.10+
metadata:
  domain: omnichannel
allowed_tools: []
---

# Channel Formatting Skill

## Overview
Ensures outbound messages comply with channel-specific presentation limits and interactive UI elements across Telegram and WhatsApp.

## When to Use
- When generating responses intended for Telegram groups (inline keyboards, HTML/Markdown formatting).
- When generating responses for WhatsApp groups (interactive buttons, list messages).

## Instructions
1. **Telegram**:
   - Limit messages to 4096 characters.
   - Attach inline keyboard buttons using `InteractiveButton(id, title, payload)`.
2. **WhatsApp**:
   - Limit interactive button titles to 20 characters and max 3 buttons per reply.
   - Use clean plain text formatting with bold asterisks `*bold*`.
