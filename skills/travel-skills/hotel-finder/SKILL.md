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
1. Check for required details: destination, check-in date, and check-out date.
2. If travel dates are missing or unspecified, clarify with the user first (e.g. "What dates will you need accommodation for?").
3. Call `search_hotels(destination, checkin_date, checkout_date)`.
4. Filter properties that match group safety and rating thresholds (minimum 4.0/5.0).
5. Present top curated stays with pricing, neighborhood location, and highlighted amenities.
