---
name: group-polling
description: Dispatches quick interactive confirmation polls to group chats to resolve pending decisions
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: proactive_concierge
allowed_tools:
  - schedule_departure_checkin
---

# Group Polling Skill

## Overview
Generates consensus polls and confirmation prompts with tap-to-vote interactive buttons for Telegram and WhatsApp.

## When to Use
- When confirming attendance, departure readiness, or restaurant choices.
- When an immediate binary or multi-choice decision is needed without spamming text.

## Instructions
1. Determine the core decision to resolve (e.g. "Ready for departure?").
2. Formulate 2 to 3 discrete options (e.g. "Packed & Ready", "Running Late").
3. Schedule checkin via `schedule_departure_checkin(trip_id, departure_time)`.
4. Render interactive buttons in the channel adapter so users can tap to respond.
