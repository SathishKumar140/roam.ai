---
name: roamai-arbitration
description: Arbitrates multi-party constraints (diets, budgets, conflicting schedules) from group chat histories
license: MIT
compatibility: Python 3.10+
metadata:
  domain: group-arbitration
allowed_tools: []
---

# RoamAI Arbitration Skill

## Overview
Compares explicitly supplied participant constraints in the selected topic. Unstated preferences remain unknown.

## When to Use
- When multiple friends propose differing dates, budgets, dietary preferences, or activity types.
- When an impasse or conflict arises in the group chat.

## Instructions
1. **Scoped Evidence**: Use current topic facts, scoped preferences and their source messages. New field values override historical summaries; never borrow facts from another trip.
2. **Conflict Detection**:
   - Compare budget caps (e.g. Alice: $100/night vs Bob: luxury only).
   - Compare dietary requirements (vegan, halal, gluten-free).
3. **Compromise Synthesis**: Propose optimal Pareto-efficient compromises that satisfy hard constraints first.
4. **Interactive Actionables**: Suggest compromises without declaring consensus. Delegate an agreed, fully configured poll to the concierge; only the application creates real buttons.
