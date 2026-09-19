---
name: itinerary-synthesis
description: Generates balanced multi-day travel schedules respecting all group members preferences and geographic proximity
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: travel_specialist
allowed_tools:
  - search_web
  - generate_itinerary
  - calculate_distance
  - search_events
---

# Itinerary Synthesis Skill

## Overview
Synthesizes comprehensive day-by-day itineraries by clustering venues geographically to minimize commute times and balancing activity pacing.

## When to Use
- When the group asks for a "3-day plan for Kyoto" or "weekend trip schedule".
- When combining sightseeing, dining, and free time into a coherent plan.

## Instructions
1. When destination and trip duration or dates are known, immediately synthesize and deliver a balanced day-by-day itinerary right away. Do not delay or ask the user to choose between sights, food, or shopping before presenting the plan.
2. Group attractions by neighborhood/geographic clusters using `calculate_distance` or `generate_itinerary`.
3. Check for local festivals or seasonal events using `search_events`.
4. Structure each day: Morning (attraction), Midday (meal matching diet), Afternoon (culture/leisure), Evening (dinner/nightlife).
5. Ensure pacing allows buffer time between activities.
6. Research actual places with `search_web` when needed. Use this topic's current dates, budget and preferences; never import constraints from another trip.
7. Cite returned sources and mark unverified opening hours, suitability and travel times. Generic attractions are not confirmed scheduled events. A proposed itinerary creates no poll, reminder, booking or expense.
