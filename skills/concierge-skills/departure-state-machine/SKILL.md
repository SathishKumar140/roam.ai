---
name: departure-state-machine
description: Coordinates explicitly requested departure reminders and explains trip-status limitations
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: proactive_concierge
allowed_tools:
  - schedule_group_reminder
  - cancel_group_reminder
---

# Departure State Machine Skill

## Overview
The active runtime supports durable topic-scoped reminders, not an automatic departure state machine. It cannot mark a trip departed or completed.

## When to Use
- When scheduled departure days approach.
- When querying whether a trip is confirmed or active.

## Instructions
1. Read the supplied topic facts and existing reminders. Do not claim a departure status that participants have not stated.
2. Schedule only a requested or explicitly agreed check-in. Confirm the date, timezone and purpose, then use `schedule_group_reminder` with a timezone-aware ISO timestamp.
3. Cancel only a supplied current-topic reminder ID on request. Report the actual tool result; do not silently recreate or reschedule it.
4. Automatic lifecycle transitions and recurring daily check-ins are unavailable. A reminder or poll vote does not establish that everyone departed.
