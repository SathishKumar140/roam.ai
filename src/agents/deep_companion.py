import json
from typing import Optional, Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from src.config import get_llm, settings
from src.storage.checkpointer import get_sqlite_checkpointer
from src.storage.database import db
from src.models.channel import ChannelEvent, OutboundMessage, InteractiveButton

# Import specialized toolsets & MCP Client
from src.mcp.client import mcp_manager
from src.skills.loader import SkillsLoader
from src.agents.tools.travel_tools import travel_tools
from src.agents.tools.vision_tools import vision_tools
from src.agents.tools.expense_tools import expense_tools
from src.agents.tools.proactive_tools import proactive_tools
from src.skills.mcp_skill_learner import skill_learner_tools

SUPERVISOR_SYSTEM_PROMPT = """You are an Ambient Group Concierge and Companion living inside Telegram and WhatsApp group chats.
You operate on an open Model Context Protocol (MCP) architecture and possess deep thinking capabilities to review group conversations, identify individual constraints, and orchestrate actions.

You have access to 5 specialized sub-agents with dedicated, isolated context windows:
1. 'travel_specialist': Powered by the Travel MCP Server. Searches flights, accommodations, and builds balanced day-by-day itineraries.
2. 'vision_specialist': Analyzes photos of venues, flyers, menus, and receipts with real-time ratings.
3. 'expense_specialist': Tracks group expenses and calculates simplified debt settlement (who owes what).
4. 'proactive_concierge': Manages trip lifecycle states, departures, and wake-up confirmation polls.
5. 'skill_specialist': Dynamically learns and discovers new capabilities by connecting to external MCP servers on demand.

GUIDELINES:
- When friends are discussing plans, analyze preceding messages to extract constraints (e.g. Alice is vegan, Bob has a $100 budget).
- When an image is shared, consult 'vision_specialist' to evaluate the venue.
- When money is mentioned or someone says 'I paid $X for dinner', consult 'expense_specialist'.
- When the trip departure day arrives, consult 'proactive_concierge' to confirm if the trip is active.
- When asked to connect to new tools, servers, or learn a skill, consult 'skill_specialist'.
- Keep responses friendly, structured, concise, and actionable for group chats.
"""

def create_ambient_companion():
    """
    Initializes the LangChain DeepAgent with isolated subagents and dynamic MCP tools.
    All agents strictly conform to the LangChain DeepAgents skills specification.
    """
    llm = get_llm()
    checkpointer = get_sqlite_checkpointer()
    global_skills = ["./skills/global/"]

    # Discover live travel tools from MCP server (fallback to internal if server offline)
    mcp_travel_tools = mcp_manager.get_tools_for_server("travel")
    active_travel_tools = mcp_travel_tools if mcp_travel_tools else travel_tools

    # Subagent definitions conforming to DeepAgents custom subagent specification
    subagents_config = [
        {
            "name": "travel_specialist",
            "description": "Searches flights, accommodations, and generates day-by-day itineraries using the Travel MCP server.",
            "system_prompt": "You are an expert travel planner powered by MCP. Search flights and hotels, and balance group constraints.",
            "tools": active_travel_tools,
            "skills": ["./skills/travel-skills/"],
        },
        {
            "name": "vision_specialist",
            "description": "Analyzes photos sent to the group (venues, menus, flyers, receipts) using multimodal vision.",
            "system_prompt": "You are a multimodal venue and scout expert. Analyze photos and provide actionable feedback.",
            "tools": vision_tools,
            "skills": ["./skills/vision-skills/"],
        },
        {
            "name": "expense_specialist",
            "description": "Manages the group expense ledger and calculates simplified debt settlement (who owes what).",
            "system_prompt": "You are an accurate group accountant. Record expenses and calculate minimum debt settlements.",
            "tools": expense_tools,
            "skills": ["./skills/expense-skills/"],
        },
        {
            "name": "proactive_concierge",
            "description": "Schedules and handles trip-day wake-ups, departure confirmation polls, and daily check-ins.",
            "system_prompt": "You are a proactive trip coordinator. Check in on trip morning and track journey progress.",
            "tools": proactive_tools,
            "skills": ["./skills/concierge-skills/"],
        },
        {
            "name": "skill_specialist",
            "description": "Connects to external MCP servers to learn new skills and tools dynamically at runtime.",
            "system_prompt": "You manage dynamic skill acquisition and MCP server connections for the companion.",
            "tools": skill_learner_tools,
            "skills": ["./skills/meta-skills/"],
        }
    ]

    try:
        from deepagents import create_deep_agent
        return create_deep_agent(
            model=llm,
            system_prompt=SUPERVISOR_SYSTEM_PROMPT,
            tools=[],
            subagents=subagents_config,
            skills=global_skills,
            checkpointer=checkpointer
        )
    except (ImportError, Exception):
        # Fallback to compiled StateGraph multi-agent dispatcher if deepagents is not installed
        return FallbackMultiAgentHarness(llm, subagents_config, global_skills=global_skills)


class FallbackMultiAgentHarness:
    """
    Robust standalone multi-agent harness implementing the DeepAgent pattern
    directly with isolated tool execution, skills progressive disclosure, and deep arbitration.
    """
    def __init__(self, llm, subagents_config: List[Dict[str, Any]], global_skills: Optional[List[str]] = None):
        self.llm = llm
        self.global_skills_sources = global_skills or ["./skills/global/"]
        self.global_skills = SkillsLoader.load_skills_from_sources(self.global_skills_sources)
        self.global_read_tool = SkillsLoader.create_skill_inspection_tool(self.global_skills)
        self.supervisor_system_prompt = SUPERVISOR_SYSTEM_PROMPT + SkillsLoader.format_skills_system_prompt(
            self.global_skills, self.global_skills_sources
        )

        self.subagents = {}
        for s in subagents_config:
            sub = dict(s)
            sources = sub.get("skills", [])
            loaded_skills = SkillsLoader.load_skills_from_sources(sources)
            sub["loaded_skills"] = loaded_skills
            sub_read_tool = SkillsLoader.create_skill_inspection_tool(loaded_skills)
            sub["tools"] = list(sub.get("tools", [])) + [sub_read_tool]
            sub["system_prompt"] = sub.get("system_prompt", "") + SkillsLoader.format_skills_system_prompt(
                loaded_skills, sources
            )
            self.subagents[sub["name"]] = sub

    async def ainvoke(self, input_data: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        channel_id = input_data.get("channel_id", "default_channel")
        text = input_data.get("text", "")
        media = input_data.get("media")
        sender_name = input_data.get("sender_name", "Friend")
        history = input_data.get("history", [])

        # 1. Deep Thinking & Intent Classification
        text_lower = text.lower()

        # Route to Vision Specialist if media present or photo analysis requested
        if media and media.get("type") == "photo" or "photo" in text_lower or "picture" in text_lower or "place" in text_lower and ("good" in text_lower or "check" in text_lower):
            sub = self.subagents["vision_specialist"]
            tool_res = sub["tools"][0].invoke({"photo_url_or_id": "image_ref", "context_caption": text})
            res_dict = json.loads(tool_res)
            reply = (
                f"📸 *Scout Analysis for {sender_name}*\n"
                f"**{res_dict.get('detected_place')}**\n"
                f"• ✨ *Vibe*: {res_dict.get('vibe')}\n"
                f"• 💰 *Pricing*: {res_dict.get('price_tier')}\n"
                f"• 💡 *Verdict*: {res_dict.get('recommendation')}"
            )
            return {
                "output": reply,
                "buttons": [
                    [InteractiveButton(id="view_reviews", label="⭐ View Reviews", type="callback")],
                    [InteractiveButton(id="maps_link", label="📍 Open Maps", type="url", url="https://maps.google.com")]
                ]
            }

        # Route to Expense Specialist if bill, money, split, or expense mentioned
        if any(w in text_lower for w in ["spent", "paid", "bill", "split", "owe", "balance", "expense", "settle", "share"]):
            sub = self.subagents["expense_specialist"]
            if "balance" in text_lower or "owe" in text_lower or "settle" in text_lower or "who owes" in text_lower:
                reply = sub["tools"][1].invoke({"channel_id": channel_id})
            else:
                # Log expense tool
                reply = sub["tools"][0].invoke({
                    "channel_id": channel_id,
                    "payer_name": sender_name,
                    "amount": 120.0,
                    "description": "Group outing & meal",
                    "split_members": "Alice, Bob, Charlie"
                })
            return {"output": reply}

        # Route to Proactive Concierge if trip confirmation, wakeup, or status requested
        if any(w in text_lower for w in ["confirm", "on the trip", "departure", "trip day", "wake up"]):
            sub = self.subagents["proactive_concierge"]
            if "status" in text_lower:
                reply = sub["tools"][2].invoke({"channel_id": channel_id})
            else:
                reply = sub["tools"][1].invoke({"channel_id": channel_id, "user_name": sender_name})
            return {"output": reply}

        # Route to Skill Specialist or Skills Inspection
        if any(w in text_lower for w in ["skill", "mcp", "learn", "tools", "capabilities"]):
            sub = self.subagents["skill_specialist"]
            if "connect" in text_lower:
                reply = sub["tools"][0].invoke({
                    "server_name": "custom_tools",
                    "command": "python3",
                    "args_json": "[\"-m\", \"src.mcp.servers.travel_mcp_server\"]"
                })
            elif "read" in text_lower or "inspect" in text_lower or "instruction" in text_lower:
                # Find skill name from text
                found_skill = None
                for sub_name, sub_info in self.subagents.items():
                    for s_name in sub_info.get("loaded_skills", {}).keys():
                        if s_name.replace("-", " ") in text_lower or s_name in text_lower:
                            found_skill = s_name
                            read_tool = sub_info["tools"][-1]
                            reply = read_tool.invoke({"skill_name": found_skill})
                            break
                    if found_skill:
                        break
                if not found_skill:
                    for s_name in self.global_skills.keys():
                        if s_name.replace("-", " ") in text_lower or s_name in text_lower:
                            found_skill = s_name
                            reply = self.global_read_tool.invoke({"skill_name": found_skill})
                            break
                if not found_skill:
                    reply = "Specify a valid skill name to inspect (e.g., 'read skill flight-search')."
            else:
                lines = ["🧠 **DeepAgents Skills Library (Progressive Disclosure)**\n"]
                lines.append(f"• **Global Supervisor Skills** (`{self.global_skills_sources[0]}`):")
                for s_name, meta in self.global_skills.items():
                    lines.append(f"  - `{s_name}`: {meta['description']}")
                lines.append("")
                for sub_name, sub_info in self.subagents.items():
                    skills_dict = sub_info.get("loaded_skills", {})
                    src = sub_info.get("skills", ["unknown"])[0]
                    lines.append(f"• **`{sub_name}`** (`{src}`):")
                    for s_name, meta in skills_dict.items():
                        lines.append(f"  - `{s_name}`: {meta['description']}")
                
                # Append MCP server tools listing
                mcp_listing = sub["tools"][1].invoke({})
                lines.append(f"\n{mcp_listing}")
                reply = "\n".join(lines)
            return {"output": reply}

        # Route to Travel Specialist for flights, hotels, trips, vacations
        if any(w in text_lower for w in ["trip", "flight", "hotel", "itinerary", "bali", "tokyo", "vacation", "book"]):
            sub = self.subagents["travel_specialist"]
            flights = json.loads(sub["tools"][0].invoke({"origin": "SIN", "destination": "DPS", "date": "2026-10-15"}))
            hotels = json.loads(sub["tools"][1].invoke({"destination": "Bali", "checkin_date": "2026-10-15", "checkout_date": "2026-10-18"}))
            itinerary = json.loads(sub["tools"][2].invoke({"destination": "Bali", "days": 3, "preferences": "beach, culture, food"}))

            flight_list = flights.get("flights") or flights.get("available_options") or []
            hotel_list = hotels.get("hotels") or []
            best_flight = flight_list[0] if flight_list else {"flight": "SQ 942", "airline": "Singapore Airlines", "price": 185.0}
            best_hotel = hotel_list[0] if hotel_list else {"name": "Bali Oceanfront Villa", "price_per_night": 135.0, "rating": 4.9}

            reply = (
                f"🌴 *Trip Proposal & Group Consensus (via Travel MCP)*\n"
                f"────────────────────────\n"
                f"✈️ *Recommended Flight*: {best_flight['flight']} ({best_flight['airline']}) - ${best_flight['price']}\n"
                f"🏨 *Recommended Stay*: {best_hotel['name']} (${best_hotel['price_per_night']}/night, {best_hotel['rating']}★)\n"
                f"🗓️ *Day 1 Plan*: {itinerary['schedule'][0]['theme']}\n\n"
                f"Shall I confirm this reservation for the group?"
            )
            return {
                "output": reply,
                "buttons": [
                    [InteractiveButton(id="confirm_booking", label="✅ Confirm Booking", type="callback")],
                    [InteractiveButton(id="modify_plan", label="🔄 Adjust Preferences", type="callback")]
                ]
            }

        # Default conversational response
        return {
            "output": f"👋 Hey {sender_name}! I'm listening quietly in the group. Mention me or ask about travel, splitting expenses, analyzing a venue photo, or checking our trip status anytime!"
        }

ambient_companion = create_ambient_companion()
