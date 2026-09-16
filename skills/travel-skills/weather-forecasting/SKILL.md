---
name: weather-forecasting
description: Fetches daily weather forecasts and climate advisories for destinations via MCP
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: travel_specialist
allowed_tools:
  - get_weather_forecast
---

# Weather Forecasting Skill

## Overview
Retrieves weather forecasts (temperature, precipitation, conditions) to guide travel packing and daily outdoor activity planning.

## When to Use
- When planning outdoor excursions, beach days, or walking tours.
- When advising travelers on what clothing to pack for upcoming travel dates.

## Instructions
1. Determine destination latitude and longitude (or city name).
2. Call `get_weather_forecast(latitude, longitude, days)`.
3. Highlight extreme weather advisories (rain, snow, high heat).
4. Suggest rescheduling outdoor activities if high chance of rain is forecasted.
