---
name: group-polling
description: Dispatches quick interactive confirmation polls to group chats to resolve pending decisions
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: proactive_concierge
allowed_tools:
  - create_group_poll
---

# Group Polling Skill

## Overview
Generates consensus polls and confirmation prompts with tap-to-vote interactive buttons for Telegram and WhatsApp.

## When to Use
- When confirming attendance, departure readiness, or restaurant choices.
- When an immediate binary or multi-choice decision is needed without spamming text.

## Instructions
1. Determine the core decision to resolve (e.g. "Ready for departure?").
2. Obtain 2 to 3 agreed discrete options, each at most 20 characters. Never invent choices to fill missing configuration.
3. Obtain agreement to create the poll and establish its closing deadline. Call
  `create_group_poll(question, options, closes_in_minutes)` only in the scoped group planner.
4. Use the application's poll-specific buttons. Each authenticated member has one changeable vote.
5. The durable worker closes the poll and reports totals. No votes or a tie is not a consensus.
6. Votes do not authorize expenses, bookings or attendance commitments. Do not promise native platform polls.
7. Reuse an existing active poll. Poll editing is unavailable; do not claim an update or create a duplicate when a follow-up is ambiguous.
