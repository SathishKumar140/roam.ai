---
name: hotel-finder
description: Finds accommodations with ratings, amenities, and price per night filtering via MCP
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: travel_specialist
allowed_tools:
  - search_hotels
---

# Hotel Finder Skill

## Overview
Queries hotels, resorts, and vacation stays matching group preferences and location constraints.

## When to Use
- When group members request lodging recommendations in a destination city.
- When filtering for specific amenities (pool, free Wi-Fi, central location).

## Instructions
1. Check destination, explicit future check-in/check-out dates, occupancy, budget units and requested currency. Use only this trip's current facts.
2. If travel dates are missing or unspecified, clarify with the user first (e.g. "What dates will you need accommodation for?").
3. Call `search_hotels` using its actual schema, including adults and currency. Never silently change a year or assume two travelers.
4. Compare returned properties with the group's constraints. Missing ratings, accessibility or dietary information are unknown, not verified matches.
5. Present returned prices with nightly/total units when known and exact public source URLs. Search results do not establish a booking or guaranteed availability.
