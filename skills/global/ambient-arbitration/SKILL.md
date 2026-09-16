---
name: ambient-arbitration
description: Arbitrates multi-party constraints (diets, budgets, conflicting schedules) from group chat histories
license: MIT
compatibility: Python 3.10+
metadata:
  domain: group-arbitration
allowed_tools: []
---

# Ambient Arbitration Skill

## Overview
Analyzes group chat discussions to identify unstated, implicit, and conflicting constraints across multiple participants.

## When to Use
- When multiple friends propose differing dates, budgets, dietary preferences, or activity types.
- When an impasse or conflict arises in the group chat.

## Instructions
1. **Sliding Buffer Extraction**: Read recent messages to build a participant constraint map.
2. **Conflict Detection**:
   - Compare budget caps (e.g. Alice: $100/night vs Bob: luxury only).
   - Compare dietary requirements (vegan, halal, gluten-free).
3. **Compromise Synthesis**: Propose optimal Pareto-efficient compromises that satisfy hard constraints first.
4. **Interactive Actionables**: Present choices as quick inline action buttons.
