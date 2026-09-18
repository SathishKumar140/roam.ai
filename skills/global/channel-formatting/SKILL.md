---
name: channel-formatting
description: Formats concise group-chat replies and preserves application-owned action buttons
license: MIT
compatibility: Python 3.10+
metadata:
  domain: omnichannel
allowed_tools: []
---

# Channel Formatting Skill

## Instructions
1. Reply in short conversational paragraphs or simple lists. Avoid decorative frames, wide tables, HTML and unsupported dashboard widgets.
2. Use the requested currency and confirmed route. No currency, airport, year or participant defaults.
3. For discoveries, show actual returned details and exact public source URLs. Clearly mark unknown units, availability and suitability.
4. The application creates buttons only from successful scoped tools. Never invent booking, payment, confirmation or map buttons in text.
5. Poll option labels are at most 20 characters with two or three options. Expense buttons belong to a specific proposal and authenticate each participant.
6. Platform adapters own delivery formatting and message splitting. Do not claim native polls, bookings or interactive features the application did not create.
