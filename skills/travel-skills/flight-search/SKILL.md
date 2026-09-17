---
name: flight-search
description: Discovers and compares flight options with price, duration, and layover filtering via MCP
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: travel_specialist
allowed_tools:
  - search_flights
  - search_cheapest_flights_in_month
---

# Flight Search Skill

## Overview
Connects to Google Flights via the Travel MCP Server to query specific flights or scan an entire month to discover the cheapest travel dates and lowest airfares.

## When to Use
- When users mention specific travel dates between cities (use `search_flights`).
- When users ask to "find the cheapest", "suggest dates", or look for the best price for a trip duration (e.g. 5 days) across a month (use `search_cheapest_flights_in_month`).

## Instructions
1. **Specific Dates**: If the user provides specific departure/return dates, call `search_flights(departure_id, arrival_id, outbound_date, return_date)`.
2. **Find Cheapest / Suggest Dates across Month**: If the user asks for the cheapest dates, asks to suggest dates, or gives a month (e.g. "cheapest for 5 days next month"):
   - DO NOT refuse or ask them to pick dates.
   - Call `search_cheapest_flights_in_month(departure_id, arrival_id, month, duration_days)`.
   - Present the recommended cheapest dates, price comparisons across the tested windows, and top flight options!
3. **Completely Missing Route/City**: If departure or destination is completely unknown, clarify the missing city.
4. Format response highlighting the best travel dates, prices, carrier, departure times, and total travel time.
