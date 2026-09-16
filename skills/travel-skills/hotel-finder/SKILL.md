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
1. Identify destination query, check-in date, check-out date, and budget limit.
2. Call `search_hotels(query, check_in_date, check_out_date)`.
3. Filter properties that match group safety and rating thresholds (minimum 4.0/5.0).
4. Present top 3 curated stays with pricing, neighborhood location, and highlighted amenities.
