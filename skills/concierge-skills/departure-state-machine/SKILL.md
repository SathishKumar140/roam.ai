---
name: departure-state-machine
description: Tracks trip progression from planning to departed and handles departure day wake-up triggers
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: proactive_concierge
allowed_tools:
  - get_trip_status
  - set_trip_departed
---

# Departure State Machine Skill

## Overview
Manages the lifecycle state of group trips (`PLANNING`, `ACTIVE`, `DEPARTED`, `COMPLETED`) and triggers timely proactive alerts.

## When to Use
- When scheduled departure days approach.
- When querying whether a trip is confirmed or active.

## Instructions
1. Query current trip state with `get_trip_status()`.
2. On departure morning, verify departure status with participants.
3. Once departure is acknowledged, transition trip state using `set_trip_departed()`.
4. Provide daily check-ins and emergency contact details for the active trip.
