from typing import List, Dict, Any, Optional
import re
from src.models.channel import InteractiveButton, PlatformType

def get_channel_presentation_prompt(platform: str) -> str:
    """
    Dynamically generates the channel-specific presentation prompt to inject
    into the LLM context based on the requesting platform.
    """
    p = (platform or "telegram").lower()

    if p == "telegram":
        return """[CHANNEL PRESENTATION DIRECTIVE: TELEGRAM VISUAL CARDS]
You are rendering your response directly inside Telegram chat. Telegram users expect clean, premium, highly readable Visual Cards instead of unformatted walls of text or wide Markdown tables.

Adhere strictly to the following Telegram Visual Card design system:

1. CARD HEADER BANNERS:
   Use rounded Unicode frames for main section headers:
   ╭────────────────────────────────────────╮
   │  ✈️  TRIP PROPOSAL: [DESTINATION]      │
   ╰────────────────────────────────────────╯

2. STRUCTURED KEY-VALUE BLOCKS:
   Use clean tree-connector bullets (`├ `, `└ `) for metadata so it reads like a sleek visual mobile card:
   ### Recommended Flight (SIN ➔ [IATA])
   ├ Airline: [Airline Name] ([Flight Number])
   ├ Schedule: [Depart] ➔ [Arrive] ([Duration], [Stops])
   └ Price: SGD [Amount] ([One-way / Round-trip])

   ### Recommended Stay
   ├ Venue: [Hotel / Homestay Name]
   ├ Rating: ⭐ [Rating]/5 ([Reviews] reviews)
   ├ Highlights: [Key perks / vibe]
   └ Price: SGD [Amount] / night

   💱 CURRENCY & LIVE EXCHANGE RATE
   ├ Destination Currency: [Currency Name] ([Code])
   ├ Live Rate: 1 SGD ≈ [Rate] [Code]
   └ Conversion Tip: [Cash vs card / ATM advice]

   🏷️ ESTIMATED LOCAL EXPENSES (Per Person)
   • 🏍️ Transport / Scooter: ~[Local Amount] (~SGD [SGD Amount]) / day
   • 🍲 Meals & Drinks: ~[Local Amount] (~SGD [SGD Amount]) / day
   • 🏡 Stay / Homestay: ~[Local Amount] (~SGD [SGD Amount]) / night
   • 🎟️ Entry / Permits: ~[Local Amount] (~SGD [SGD Amount])

   🗺️ ITINERARY HIGHLIGHTS
   • Day 1: [Highlights]
   • Day 2: [Highlights]
   • Day 3: [Highlights]

3. CHEAPEST TRAVEL WINDOW CARD (When scanning month or suggesting dates):
   ╭────────────────────────────────────────╮
   │  📅  CHEAPEST TRAVEL WINDOW            │
   ╰────────────────────────────────────────╯
   🏆 Best Window: [Dates] ([Duration])
   └ Lowest Fare: SGD [Amount] ([Trip Type]) via [Airline]

   📊 Month Fare Comparison:
   • [Window 1]: SGD [Amount]
   • [Window 2]: SGD [Amount]
   • [Window 3]: SGD [Amount]

4. GROUP CONSENSUS CARD (For group chats / multi-party recommendations):
   ╭────────────────────────────────────────╮
   │  🤝  GROUP CONSENSUS CARD              │
   ╰────────────────────────────────────────╯
   👥 Member Constraints Analyzed:
   • [User 1]: [Constraint, e.g. vegan 🌱]
   • [User 2]: [Constraint, e.g. budget < SGD 25 💸]
   • [User 3]: [Constraint, e.g. Chinatown / Tanjong Pagar 📍]

   🍽️ WINNING SPOT: [Venue Name]
   ├ ✨ Vibe: [Description]
   ├ 📍 Location: [Area / MRT]
   └ 🍴 Why it fits everyone:
     - For [User 1]: [Vegan options]
     - For [User 2]: [Under budget]
     - For [User 3]: [Convenient location]

5. EXPENSE CARDS (When money / bills / splits are logged):
   a. EXPENSE LOGGED: PENDING CONSENT (When a new expense is reported):
   ╭────────────────────────────────────────╮
   │  🧾  EXPENSE LOGGED: PENDING CONSENT   │
   ╰────────────────────────────────────────╯
   💰 Amount: SGD [Amount] ([Description])
   ├ Paid by: [Payer Name]
   ├ Split Among: [Members] (~SGD [Share] each)
   ├ Confirmed: [Payer Name] ✅
   ├ Pending Consent: [Other Members] ⏳
   └ Status: Held pending consent before debt is finalized.
   👉 Reply "I'm in" or tap [ 👍 I'm In / Confirm ] to confirm your share!

   b. EXPENSE SETTLEMENT SHEET (When checking who owes what / ledger balance):
   ╭────────────────────────────────────────╮
   │  💳  EXPENSE SETTLEMENT SHEET          │
   ╰────────────────────────────────────────╯
   📊 Active Confirmed Debt (Settled):
   • [Member 1] owes [Payer]: SGD [Amount]
   • [Member 2] owes [Payer]: SGD [Amount]

   ⏳ Pending Confirmation (Held until members confirm):
   • SGD [Amount] for [Description] (Paid by [Payer])
     ├ Confirmed: [Payer] ✅
     └ Awaiting: [Pending Members] ⏳

6. SCOUT & VENUE CARD (For photos / place reviews):
   ╭────────────────────────────────────────╮
   │  📸  SCOUT & VENUE ANALYSIS            │
   ╰────────────────────────────────────────╯
   🏛️ Venue: [Venue Name]
   ├ ⭐ Rating: [Rating]/5
   ├ ✨ Vibe: [Atmosphere & crowd]
   ├ 💵 Pricing: [Price range in SGD]
   └ 💡 Scout Highlights: [Insider tip]

CRITICAL TELEGRAM RULES:
- Always quote all prices in SGD (Singapore Dollars).
- Avoid wide markdown tables (columns wrap poorly on Telegram mobile).
- Keep formatting clean, avoiding unescaped or orphan markdown symbols."""

    elif p == "whatsapp":
        return """[CHANNEL PRESENTATION DIRECTIVE: WHATSAPP FORMAT]
You are rendering your response directly inside WhatsApp.
1. Use native WhatsApp markdown: *bold*, _italics_, ~strikethrough~, and ```code```. Do NOT use double asterisks (**).
2. Avoid Unicode box-drawing frames (╭─, ├─) because non-monospace fonts will misalign them. Use clean bullet points: `• `.
3. Keep descriptions concise, punchy, and conversational.
4. All prices must be quoted in SGD with local currency equivalents.
5. Interactive quick-reply buttons have a strict limit of 3 buttons and 20 characters per title."""

    else:
        return """[CHANNEL PRESENTATION DIRECTIVE: WEB & DASHBOARD]
Render responses in rich standard Markdown with headers (#, ##, ###), tables, code blocks, bold text, and bullet lists. All prices quoted in SGD with local currency conversions."""


def build_channel_buttons(
    platform: str,
    output_text: str,
    tools_executed: Optional[List[Dict[str, Any]]] = None
) -> List[List[InteractiveButton]]:
    """
    Generates channel-adaptive interactive buttons tailored specifically
    for Telegram inline keyboards or WhatsApp quick-reply buttons.
    """
    p = (platform or "telegram").lower()
    lower_text = output_text.lower()
    tools = tools_executed or []

    # Detect context
    is_trip_proposal = any(k in lower_text for k in ["trip proposal", "recommended flight", "recommended stay", "itinerary highlights"])
    is_cheapest_dates = any(k in lower_text for k in ["cheapest travel window", "month fare comparison", "cheapest dates"])
    is_group_consensus = any(k in lower_text for k in ["group consensus card", "winning recommendation", "winning spot"])
    is_expense = any(k in lower_text for k in ["expense settlement sheet", "logged expense", "settlement breakdown", "balance sheet", "who owes what"])
    is_venue = any(k in lower_text for k in ["scout & venue analysis", "scout analysis", "vibe", "facade"])
    is_departure = any(k in lower_text for k in ["departure poll", "are you ready", "confirm departure", "wake-up"])

    if p == "telegram":
        buttons: List[List[InteractiveButton]] = []

        if is_trip_proposal or is_cheapest_dates:
            # Check if there are flight destination codes or query in tools
            flight_search_url = "https://www.google.com/travel/flights"
            for t in tools:
                args = t.get("args", {})
                if "destination" in args:
                    flight_search_url = f"https://www.google.com/travel/flights?q=flights+from+SIN+to+{args['destination']}"
                    break

            buttons.append([
                InteractiveButton(id="search_flights_btn", label="✈️ Google Flights ↗", type="url", url=flight_search_url),
                InteractiveButton(id="confirm_proposal", label="✅ Confirm Plan", type="callback")
            ])
            buttons.append([
                InteractiveButton(id="modify_plan", label="🔄 Adjust Dates / Budget", type="callback"),
                InteractiveButton(id="vote_trip", label="🗳️ Create Group Poll", type="callback")
            ])
            return buttons

        if is_group_consensus:
            buttons.append([
                InteractiveButton(id="open_maps_consensus", label="📍 Open in Maps ↗", type="url", url="https://maps.google.com"),
                InteractiveButton(id="vote_venue_yes", label="👍 Count Me In!", type="callback")
            ])
            buttons.append([
                InteractiveButton(id="suggest_alternative", label="🔄 Suggest Another", type="callback")
            ])
            return buttons

        if is_expense:
            buttons.append([
                InteractiveButton(id="confirm_expense_split", label="👍 I'm In / Confirm", type="callback"),
                InteractiveButton(id="opt_out_expense", label="❌ Not Me / Opt Out", type="callback")
            ])
            buttons.append([
                InteractiveButton(id="view_ledger", label="📊 View Ledger", type="callback"),
                InteractiveButton(id="settle_expenses", label="💳 Settle Balances", type="callback")
            ])
            return buttons

        if is_venue:
            buttons.append([
                InteractiveButton(id="open_maps_venue", label="📍 View on Google Maps ↗", type="url", url="https://maps.google.com"),
                InteractiveButton(id="add_to_itinerary", label="➕ Add to Itinerary", type="callback")
            ])
            return buttons

        if is_departure:
            buttons.append([
                InteractiveButton(id="vote_ready", label="👍 Ready & On My Way!", type="callback"),
                InteractiveButton(id="vote_delayed", label="⏰ Running Late", type="callback")
            ])
            return buttons

        # Default contextual buttons for travel queries
        if any(w in lower_text for w in ["flight", "hotel", "travel", "singapore", "vietnam", "bali"]):
            buttons.append([
                InteractiveButton(id="explore_more", label="🧭 Explore More Options", type="callback"),
                InteractiveButton(id="currency_rates", label="💱 Currency Rates", type="callback")
            ])
            return buttons

        return []

    elif p == "whatsapp":
        # WhatsApp limits: Max 3 buttons, labels <= 20 chars
        if is_trip_proposal or is_cheapest_dates:
            return [[
                InteractiveButton(id="confirm", label="Confirm Plan", type="callback"),
                InteractiveButton(id="adjust", label="Adjust Dates", type="callback"),
                InteractiveButton(id="poll", label="Group Poll", type="callback")
            ]]
        if is_expense:
            return [[
                InteractiveButton(id="settle", label="Settle Debt", type="callback"),
                InteractiveButton(id="balance", label="View Balance", type="callback")
            ]]
        if is_venue:
            return [[
                InteractiveButton(id="add_stop", label="Add to Trip", type="callback"),
                InteractiveButton(id="other_venue", label="Next Option", type="callback")
            ]]
        return []

    else:
        # Web / Mock buttons
        if is_trip_proposal or is_cheapest_dates:
            return [
                [InteractiveButton(id="confirm_booking", label="✅ Confirm Proposal", type="callback")],
                [InteractiveButton(id="modify_plan", label="🔄 Adjust Preferences", type="callback")]
            ]
        return []
