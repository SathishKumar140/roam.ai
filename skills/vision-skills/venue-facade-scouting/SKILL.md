---
name: venue-facade-scouting
description: Recognizes restaurants, storefronts, and landmarks from photos and checks public ratings and vibe
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: vision_specialist
allowed_tools:
  - analyze_attached_image
  - search_web
---

# Venue Facade Scouting Skill

## Overview
Identifies storefronts, restaurants, and landmark facades from user photos shared in group chats and cross-references them with live rating databases.

## When to Use
- When a user takes a photo of an entrance, cafe sign, or building and asks "Should we go here?" or "Is this place good?".

## Instructions
1. Extract visual features only from this request's image using `analyze_attached_image`.
2. Describe visible signage and uncertainty. Ask for location if identity is ambiguous; never invent an exact venue from appearance alone.
3. Use `search_web` to check an identified venue. Cite returned public URLs and distinguish search snippets from verified ratings, prices and opening hours.
4. Compare venue characteristics with active group dietary and budget constraints.
5. Give a concise, qualified recommendation. Never invent ratings or default to Singapore, SGD, or a previous group's image.
