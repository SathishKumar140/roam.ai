---
name: weather-forecasting
description: Fetches daily weather forecasts and climate advisories for destinations via MCP
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: travel_specialist
allowed_tools:
  - geocode_location
  - get_weather_forecast
---

# Weather Forecasting Skill

## Overview
Retrieves weather forecasts (temperature, precipitation, conditions) to guide travel packing and daily outdoor activity planning.

## When to Use
- When planning outdoor excursions, beach days, or walking tours.
- When advising travelers on what clothing to pack for upcoming travel dates.

## Instructions
1. Confirm this trip's destination and dates. Use `geocode_location` for coordinates when needed.
2. Call `get_weather_forecast(latitude, longitude, days)`.
3. Highlight extreme weather advisories (rain, snow, high heat).
4. Suggest rescheduling outdoor activities if high chance of rain is forecasted.
5. Match returned forecast dates to the requested dates. For travel beyond the provider's forecast horizon, say the forecast is unavailable; never present today's weather as that future forecast.
6. Do not label generic weather as an official warning or change plans without agreement.
