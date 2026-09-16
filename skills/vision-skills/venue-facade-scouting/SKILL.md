---
name: venue-facade-scouting
description: Recognizes restaurants, storefronts, and landmarks from photos and checks public ratings and vibe
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: vision_specialist
allowed_tools:
  - inspect_venue_photo
---

# Venue Facade Scouting Skill

## Overview
Identifies storefronts, restaurants, and landmark facades from user photos shared in group chats and cross-references them with live rating databases.

## When to Use
- When a user takes a photo of an entrance, cafe sign, or building and asks "Should we go here?" or "Is this place good?".

## Instructions
1. Extract visual features from the image using `inspect_venue_photo`.
2. Determine name, cuisine/venue type, and confidence score.
3. Fetch public ratings, price tier, and notable specialties.
4. Compare venue characteristics with active group dietary and budget constraints.
5. Provide a quick thumbs-up/down recommendation with rationale.
