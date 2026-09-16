---
name: flight-search
description: Discovers and compares flight options with price, duration, and layover filtering via MCP
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: travel_specialist
allowed_tools:
  - search_flights
---

# Flight Search Skill

## Overview
Connects to Google Flights via the Travel MCP Server to query one-way and round-trip flight itineraries.

## When to Use
- When users mention traveling between cities (e.g. "flights from NYC to Tokyo").
- When looking for price comparisons across airlines.

## Instructions
1. Extract departure airport/city, destination, departure date, and optional return date.
2. Call `search_flights(departure_id, arrival_id, outbound_date, return_date)`.
3. Filter out excessive layovers unless budget strictly requires it.
4. Format response highlighting top 3 options with price, carrier, and total travel time.
