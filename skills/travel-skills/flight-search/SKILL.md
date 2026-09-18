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
Queries specific flights or a bounded sample of travel windows via MCP. A sampled minimum is not the cheapest fare across the entire month.

## When to Use
- When users mention specific travel dates between cities (use `search_flights`).
- When users ask to "find the cheapest", "suggest dates", or look for the best price for a trip duration (e.g. 5 days) across a month (use `search_cheapest_flights_in_month`).

## Instructions
1. **Specific Dates**: If the user provides specific departure/return dates, call `search_flights(departure_id, arrival_id, outbound_date, return_date)`.
2. **Find Cheapest / Suggest Dates across Month**: If the user asks for the cheapest dates, asks to suggest dates, or gives a month (e.g. "cheapest for 5 days next month"):
  - Establish the route, explicit year/month, duration, traveler count and requested currency first.
   - Call `search_cheapest_flights_in_month(departure_id, arrival_id, month, duration_days)`.
   - Present the recommended cheapest dates, price comparisons across the tested windows, and top flight options!
3. **Completely Missing Route/City**: If departure or destination is completely unknown, clarify the missing city.
4. Format response highlighting the best travel dates, prices, carrier, departure times, and total travel time.
5. The actual tool schema is authoritative. Supply departure_evidence_id and departure_text from this topic's user messages. Never default to SIN, a currency, or another trip's origin.
6. Use future dates exactly as requested; ask about ambiguous years. Forward adults and currency. State whether fares are per person or total only if the provider establishes it.
7. Report unavailable searches honestly. Cite only returned public URLs; distinguish sampled dates and search leads from confirmed fares or bookings.
