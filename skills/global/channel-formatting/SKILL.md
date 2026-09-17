---
name: channel-formatting
description: Formats conversational outputs for Telegram visual cards, WhatsApp interactive quick-replies, and web dashboards
license: MIT
compatibility: Python 3.10+
metadata:
  domain: omnichannel
allowed_tools: []
---

# Omnichannel Visual Formatting Skill

## Overview
Ensures outbound messages comply with channel-specific presentation limits and leverages native interactive UI elements across Telegram, WhatsApp, and Web dashboards.

---

## 1. Telegram Platform Formatting: Visual Cards

Telegram supports rich Unicode formatting, clean monospace box-drawing characters, emoji badges, and native inline keyboard buttons. For Telegram, the AI should present information as structured **Visual Cards** instead of dense walls of text or wide Markdown tables (which wrap awkwardly on mobile screens).

### A. Trip Proposal Card
```text
╭────────────────────────────────────────╮
│  ✈️  TRIP PROPOSAL: [DESTINATION]      │
╰────────────────────────────────────────╯

🛫 RECOMMENDED FLIGHT (SIN ➔ [IATA])
├ Airline: [Airline Name] ([Flight Number])
├ Schedule: [Departure] ➔ [Arrival] ([Duration], [Stops])
└ Price: SGD [Price] ([Trip Type: One-way / Round-trip])

🏨 RECOMMENDED STAY
├ Venue: [Hotel / Homestay Name]
├ Rating: ⭐ [Rating]/5 ([Reviews] reviews)
├ Highlights: [Key perks / location]
└ Price: SGD [Price] / night

💱 CURRENCY & LIVE EXCHANGE RATE
├ Destination Currency: [Currency Name] ([Code])
├ Live Rate: 1 SGD ≈ [Rate] [Code]
└ Conversion Tip: [Cash vs card recommendation]

🏷️ ESTIMATED LOCAL EXPENSES (Per Person)
• 🏍️ Transport / Scooter: ~[Local Amount] (~SGD [SGD Amount]) / day
• 🍲 Daily Meals & Drinks: ~[Local Amount] (~SGD [SGD Amount]) / day
• 🏡 Homestay / Hotel: ~[Local Amount] (~SGD [SGD Amount]) / night
• 🎟️ Local Permits / Tickets: ~[Local Amount] (~SGD [SGD Amount])

🗺️ ITINERARY HIGHLIGHTS
• Day 1: [Key Highlights]
• Day 2: [Key Highlights]
• Day 3: [Key Highlights]
```

### B. Group Consensus & Arbitration Card
```text
╭────────────────────────────────────────╮
│  🤝 GROUP CONSENSUS CARD               │
╰────────────────────────────────────────╯

👥 Group Preferences Analyzed:
• [Member 1]: [Stated constraint, e.g. strictly vegan 🌱]
• [Member 2]: [Budget constraint, e.g. < SGD 25 💸]
• [Member 3]: [Location preference, e.g. Tanjong Pagar 📍]

🍽️ WINNING RECOMMENDATION: [Venue Name]
├ ✨ Vibe: [Casual / Group-friendly]
├ 📍 Location: [Address / Landmark]
└ 🍴 Why it works for everyone:
  - For [Member 1]: [How it satisfies preference]
  - For [Member 2]: [Affordable dishes available]
  - For [Member 3]: [Walkable from MRT]
```

### C. Expense Settlement Card
```text
╭────────────────────────────────────────╮
│  💳 EXPENSE SETTLEMENT SHEET           │
╰────────────────────────────────────────╯

🧾 Total Bill: SGD [Amount] ([Description])
├ Paid by: [Payer Name] (SGD [Amount])
├ Split Among: [List of Members]
└ Settlement Breakdown:
  • [Member 1] owes [Payer]: SGD [Amount]
  • [Member 2] owes [Payer]: SGD [Amount]
```

### D. Scout & Venue Card
```text
╭────────────────────────────────────────╮
│  📸 SCOUT & VENUE ANALYSIS             │
╰────────────────────────────────────────╯

🏛️ Venue: [Venue Name]
├ ⭐ Rating: [Rating]/5
├ ✨ Vibe: [Atmosphere, decor, crowd]
├ 💵 Pricing: [Budget range in SGD]
└ 💡 Scout Highlights: [Key recommendations]
```

---

## 2. WhatsApp Platform Formatting
- Limit buttons to **maximum 3 interactive buttons** with titles $\le 20$ characters.
- Use native WhatsApp markup: `*bold*`, `_italics_`, `~strike~`, and ````code````.
- Use clean bullet points `• ` without complex box-drawing characters that may distort on default non-monospace fonts.

---

## 3. Web Dashboard Platform Formatting
- Full Markdown support including tables, collapsible accordions, code fences, and SVG badges.
