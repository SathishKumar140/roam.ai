---
name: mcp-extra-travel-hub
description: Dynamically learned capabilities from MCP server 'extra_travel_hub'
license: MIT
compatibility: Python 3.10+
metadata:
  server_name: extra_travel_hub
allowed_tools:
  - search_flights
  - search_hotels
  - generate_itinerary
---

# Extra_Travel_Hub MCP Skill

## Overview
Dynamic capabilities provided by the external Model Context Protocol (MCP) server `extra_travel_hub`.

## Tools Available
- **`search_flights`**: [MCP:extra_travel_hub] Searches real-time flight options between origin and destination for a given date via MCP.
- **`search_hotels`**: [MCP:extra_travel_hub] Discovers lodging, private pool villas, and boutique hotels matching group budget via MCP.
- **`generate_itinerary`**: [MCP:extra_travel_hub] Synthesizes an optimal day-by-day travel itinerary balancing group preferences via MCP.

## Usage
Invoke the respective tools above when a user request matches this server's domain.
