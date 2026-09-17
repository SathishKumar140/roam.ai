try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import re
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

logger = logging.getLogger("roam.ai.agent")

from src.config import get_llm, settings
from src.storage.checkpointer import get_sqlite_checkpointer
from src.storage.database import db
from src.models.channel import ChannelEvent, OutboundMessage, InteractiveButton

# Import specialized toolsets & MCP Client
from src.mcp.client import mcp_manager
from src.skills.loader import SkillsLoader
from src.adapters.channel_formatter import get_channel_presentation_prompt, build_channel_buttons
from src.agents.tools.travel_tools import travel_tools
from src.agents.tools.vision_tools import vision_tools
from src.agents.tools.expense_tools import expense_tools
from src.agents.tools.proactive_tools import proactive_tools
from src.skills.mcp_skill_learner import skill_learner_tools

def _build_supervisor_system_prompt() -> str:
    """Returns the supervisor system prompt with the real current date/time injected."""
    now_utc = datetime.now(timezone(timedelta(hours=8)))  # SGT UTC+8
    today_str = now_utc.strftime("%A, %d %B %Y")            # e.g. "Thursday, 17 September 2026"
    next_month_str = (now_utc.replace(day=1) + timedelta(days=32)).strftime("%B %Y")  # e.g. "October 2026"

    return f"""You are an Group Concierge and Companion living inside Telegram and WhatsApp group chats.
You operate on an open Model Context Protocol (MCP) architecture and possess deep thinking capabilities to review group conversations, identify individual constraints, and orchestrate actions.

## CURRENT CALENDAR CONTEXT:
- Today is: {today_str} (Year {now_utc.year}, SGT UTC+8)
- "Next month" means: {next_month_str}
- ALWAYS use the real current year {now_utc.year} in any date reasoning. NEVER use 2025 or any past year.

## HANDLING TRAVEL REQUESTS & DATE REASONING:
1. **DESTINATION VALIDATION & CLARIFICATION (CRITICAL ANTI-HALLUCINATION)**:
   - A trip proposal or flight search CAN ONLY be conducted if a specific destination (city, country, or region) is clearly identified from the user's message, recent chat history, or stored user memory.
   - **NEVER HALLUCINATE OR DEFAULT TO A RANDOM DESTINATION (e.g. NEVER guess Bali, Vietnam, or anywhere else)** when the user says something ambiguous like "go to my home", "visit home", "plan a trip", "plan my vacation", or "somewhere nice" without specifying where home or the destination actually is!
   - If the destination or home city is UNKNOWN or NOT specified:
     **DO NOT GUESS! STOP AND ASK FOR CLARIFICATION IMMEDIATELY!**
     Politely ask: "Where is home for you (which city or airport)? And will you be departing from Singapore (SIN) or elsewhere? Once you share that, I'll find the best flights and plan it right away!"
2. **WHEN A SPECIFIC DESTINATION IS PROVIDED (e.g. "let's plan a trip to Bali!", "trip to Tokyo", "flying to London")**:
   - Consult 'travel_specialist' to synthesize a comprehensive 'Trip Proposal' with 'Recommended Flight' and 'Recommended Stay' tailored to constraints in chat history.
3. **WHEN ASKED TO FIND CHEAPEST / SUGGEST DATES** (e.g. "find the cheapest and suggest the dates", "cheapest 5 days next month", "when is it cheapest to fly?"):
   - If destination is known, consult 'travel_specialist' to scan the month across Google Flights using `search_cheapest_flights_in_month`.
   - If destination is unknown, ask where they are flying first!
4. **WHEN DATES & ROUTE ARE SPECIFIC** (e.g. "Fly Oct 15 to Oct 22"):
   - Consult 'travel_specialist' to search live flights for those exact dates.

You have access to 5 specialized sub-agents with dedicated, isolated context windows:
1. 'travel_specialist': Powered by the Travel MCP Server. Searches live flights via Google Flights, scans entire months to discover the cheapest travel dates, finds hotels, and synthesizes itineraries.
2. 'vision_specialist': Analyzes photos of venues, flyers, menus, and receipts with real-time ratings.
3. 'expense_specialist': Tracks group expenses and calculates simplified debt settlement (who owes what).
4. 'proactive_concierge': Manages trip lifecycle states, departures, and wake-up confirmation polls.
5. 'skill_specialist': Dynamically learns and discovers new capabilities by connecting to external MCP servers on demand.

GUIDELINES:
- When asked for the cheapest dates or best trip window across a month, actively scan the month and suggest the best dates!
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

    # Discover live travel tools from MCP client + local live tools (100% real, no mock)
    mcp_travel_tools = mcp_manager.get_travel_tools()
    active_travel_tools = list(mcp_travel_tools) if mcp_travel_tools else []
    seen = {t.name for t in active_travel_tools}
    for t in travel_tools:
        if t.name not in seen:
            active_travel_tools.append(t)
            seen.add(t.name)

    now_sgt = datetime.now(timezone(timedelta(hours=8)))
    today_str = now_sgt.strftime("%A, %d %B %Y")
    next_month_str = (now_sgt.replace(day=1) + timedelta(days=32)).strftime("%B %Y")

    # Subagent definitions conforming to DeepAgents custom subagent specification
    subagents_config = [
        {
            "name": "travel_specialist",
            "description": "Searches live flights via Google Flights, discovers hotels, scans entire months to find cheapest dates, and researches real travel destinations and itineraries.",
            "system_prompt": (
                f"You are an expert travel planner powered by REAL-TIME LIVE tools.\n"
                f"## CALENDAR CONTEXT:\n"
                f"- Today's date is: {today_str} (Year {now_sgt.year}).\n"
                f"- 'Next month' is: {next_month_str}.\n"
                f"- NEVER use 2025 or any past dates.\n\n"
                f"## CURRENCY & LOCAL BUDGET RULES:\n"
                f"- ALL prices for flights, hotels, and activities MUST be quoted and displayed in SGD (Singapore Dollars, e.g. 'SGD 171 (One-way)' or 'SGD 287 (Round-trip)').\n"
                f"- When calling flight/hotel tools, ensure currency='SGD'.\n"
                f"- ALWAYS call `convert_currency` to look up real-time live exchange rates for the destination currency (e.g. from SGD to VND for Vietnam, IDR for Bali, JPY for Tokyo).\n"
                f"- Include a dedicated section in your proposal: '### Currency Details & Estimated Local Expenses' detailing:\n"
                f"  - Local currency name & code (e.g. Vietnamese Dong - VND)\n"
                f"  - Live exchange rate (e.g. 1 SGD ≈ 20,340 VND)\n"
                f"  - Typical estimated daily costs in both local currency and SGD (e.g. meals ~50,000-100,000 VND / ~SGD 2.50-5.00, motorbike rental ~150,000 VND / ~SGD 7.40, daily total).\n\n"
                f"## MANDATORY TOOL CALLING RULES (NO MOCK DATA, NO PLACEHOLDERS):\n"
                f"1. YOU MUST ACTUALLY CALL YOUR TOOLS before giving recommendations.\n"
                f"2. NEVER output placeholders like '[Insert Departure City]' or estimated costs without calling tools.\n"
                f"3. When asked to plan a trip to a destination (e.g. Vietnam Ha Giang loop, Bali, Tokyo):\n"
                f"   - Call `search_web` to research the destination's geography, best stops, and route details.\n"
                f"   - Call `search_flights` or `search_cheapest_flights_in_month` to find real live flights in SGD (default origin: 'SIN', currency: 'SGD').\n"
                f"   - Call `search_hotels` to look up real accommodation in the destination (currency: 'SGD').\n"
                 f"   - Call `convert_currency` to get real-time exchange rates.\n"
                f"   - Call `generate_itinerary` or compile real route recommendations from live search results.\n"
                f"4. Format the final response clearly titled '# Trip Proposal' with sections '### Recommended Flight', '### Recommended Stay', and '### Currency Details & Estimated Local Expenses'. For Telegram/chat channels, format details using clean Visual Card style with tree connectors ('├ ', '└ ') and explicitly label all flight prices as SGD (e.g. 'SGD 171 (One-way)' or 'SGD 287 (Round-trip)')."
            ),
            "tools": active_travel_tools,
            "skills": ["./skills/travel-skills/"],
        },
        {
            "name": "vision_specialist",
            "description": "Analyzes photos sent to the group (venues, menus, flyers, receipts) using multimodal GPT-4o vision and live web grounding.",
            "system_prompt": (
                "You are an expert location scout and multimodal vision analyst. "
                "When a photo is provided, IMMEDIATELY call 'analyze_venue_photo' to identify the exact place, landmark, or venue and inspect its visual cues. "
                "Always structure your response clearly with exact headers '### Scout Analysis', '### Vibe', and '### Pricing'. "
                "Always quote pricing in SGD (e.g. Free admission, or ~SGD 15 - 25 per meal/person). NEVER output generic static '$$' symbols. "
                "For Telegram/chat channels, format details using clean Visual Card style with tree connectors ('├ ', '└ ')."
            ),
            "tools": vision_tools,
            "skills": ["./skills/vision-skills/"],
        },
        {
            "name": "expense_specialist",
            "description": "Manages the group expense ledger, records participant consent/confirmations, and calculates simplified debt settlement (who owes what).",
            "system_prompt": (
                "You are an accurate, fair group accountant. "
                "When a user reports paying an expense (e.g. 'I paid $120 for dinner'), IMMEDIATELY call 'record_expense'. "
                "In group chats, expenses are logged in pending confirmation until all participants consent. "
                "Always include 'Logged expense' in your response. "
                "When a participant confirms or agrees (e.g. 'I\\'m in', 'Confirm', 'Yes agree', 'Count me in', or callback 'confirm_expense_split'), IMMEDIATELY call 'confirm_expense_split'. "
                "When asked about balance or who owes what (e.g. 'Who owes what right now?'), IMMEDIATELY call 'get_balance_sheet' and output the 'Group Expense Settlement Sheet'."
            ),
            "tools": expense_tools,
            "skills": ["./skills/expense-skills/"],
        },
        {
            "name": "proactive_concierge",
            "description": "Schedules and handles trip-day wake-ups, departure confirmation polls, and daily check-ins.",
            "system_prompt": f"You are a proactive trip coordinator. Today is {today_str}. Check in on trip morning and track journey progress.",
            "tools": proactive_tools,
            "skills": ["./skills/concierge-skills/"],
        },
        {
            "name": "skill_specialist",
            "description": "Connects to external MCP servers to learn new skills and tools dynamically at runtime.",
            "system_prompt": "You manage dynamic skill acquisition and MCP server connections for the companion. When asked what skills, tools, or MCP servers you have, IMMEDIATELY call 'list_connected_mcp_skills' and present the full output starting with 'Active MCP Servers & Learned Skills'.",
            "tools": skill_learner_tools,
            "skills": ["./skills/meta-skills/"],
        }
    ]

    # Only use create_deep_agent when the LLM can actually support tool-binding.
    from deepagents import create_deep_agent
    graph = create_deep_agent(
        model=llm,
        system_prompt=_build_supervisor_system_prompt(),
        tools=[],
        subagents=subagents_config,
        skills=global_skills,
        checkpointer=checkpointer
    )
    return DeepAgentCompanion(graph)


class DeepAgentCompanion:
    """
    Adapter that wraps a deepagents CompiledStateGraph and exposes
    the ainvoke(event_dict, config=None) interface.
    """

    def __init__(self, graph):
        self.graph = graph

    def _build_human_message(self, data: Dict[str, Any]) -> HumanMessage:
        """Serialize the event dict into a single context-rich HumanMessage."""
        sender = data.get("sender_name", "User")
        sender_id = data.get("sender_id", "")
        text = data.get("text", "")
        platform = data.get("platform", "telegram")
        media = data.get("media")
        history = data.get("history", [])

        now_sgt = datetime.now(timezone(timedelta(hours=8)))
        today_str = now_sgt.strftime("%A, %d %B %Y")
        next_month_str = (now_sgt.replace(day=1) + timedelta(days=32)).strftime("%B %Y")
        next_month_start = (now_sgt.replace(day=1) + timedelta(days=32)).replace(day=1).strftime("%Y-%m-%d")

        parts = []
        # Always inject the real date at the top of each message so the LLM cannot hallucinate it
        parts.append(
            f"[CALENDAR CONTEXT] Today is {today_str} (SGT, Year {now_sgt.year}). "
            f"'Next month' refers broadly to {next_month_str}.\n"
            f"[CURRENCY RULES]: All flight, hotel, and itinerary prices MUST be quoted and displayed in SGD (Singapore Dollars, e.g. 'SGD 171 (One-way)' or 'SGD 287 (Round-trip)'). "
            f"Always call 'convert_currency' to fetch real-time live exchange rates for destination currency (e.g. 1 SGD to VND/IDR/JPY) and include a '### Currency Details & Estimated Local Expenses' section (local currency name, live rate, estimated costs for meals, motorbike rental, homestays/budget in both local currency and SGD).\n"
            f"[TRAVEL RULES - CRITICAL DESTINATION VALIDATION & ANTI-HALLUCINATION]:\n"
            f"- A trip proposal or flight search CAN ONLY be conducted if a specific destination (city, country, or region) is clearly identified from the user's message, recent chat history, or [USER PERSISTENT MEMORY].\n"
            f"- IF the user mentions 'go to my home', 'visit home', 'plan a vacation', or 'plan a trip' BUT the destination/home city is NOT specified and NOT found in memory: "
            f"YOU MUST NOT HALLUCINATE OR GUESS A DESTINATION (NEVER default to Bali or anywhere else)! "
            f"Instead, politely and warmly ASK FOR CLARIFICATION: Ask where home is for them (which city or airport) and confirm their departure city (e.g. Singapore) so you can accurately plan and search live flights for them!\n"
            f"- ONLY when a specific destination is identified (e.g. 'plan trip to Bali', 'going to Vietnam', 'Tokyo', 'Chennai', etc.), delegate to 'travel_specialist' to execute live tools (search_web, search_flights, search_hotels with currency='SGD') to research actual options and generate a verified 'Trip Proposal' with real flights and stays quoted in SGD.\n"
            f"- If the user specifies their home or preferences (e.g. 'My home is Chennai' or 'I live in Singapore'): call save_user_memory and proceed with their trip!\n"
            f"- NEVER output placeholders like '[Insert Departure City]'. If departure city is not stated, assume default origin is Singapore (SIN).\n"
            f"- If the user asks to find the cheapest dates or suggest dates in a month: "
            f"Consult 'travel_specialist' to scan Google Flights via search_cheapest_flights_in_month with currency='SGD' and recommend the cheapest dates in SGD (if destination is known; if unknown, ask first!).\n"
            f"- If asked about skills, capabilities, or MCP servers: consult 'skill_specialist' using list_connected_mcp_skills.\n"
            f"- If a photo is attached: consult 'vision_specialist' and format response with 'Scout Analysis', 'Vibe', and 'Pricing'.\n"
            f"- If money, bills, dinner payments, balance, or 'Who owes what' is asked, or if a participant confirms/agrees to an expense (e.g. 'I\\'m in', 'Confirm', 'Yes agree', 'Count me in', or callback 'confirm_expense_split'): You MUST delegate to 'expense_specialist' to call 'record_expense', 'confirm_expense_split', or 'get_balance_sheet' and output the 'Group Expense Settlement Sheet' or 'Logged expense'!"
        )

        # Inject persistent user memories if available
        if sender_id:
            user_mem = db.get_user_memories(sender_id)
            if user_mem:
                mem_str = ", ".join(f"{k}: {v}" for k, v in user_mem.items())
                parts.append(f"[USER PERSISTENT MEMORY for {sender} (id={sender_id})]: {mem_str}")

        if history:
            history_lines = "\n".join(
                f"  {m.get('sender_name', 'User')}: {m.get('text', '')}"
                for m in history[-20:]
            )
            parts.append(f"[Recent group chat history]\n{history_lines}")

        # Dynamically inject channel-specific presentation directive
        parts.append(get_channel_presentation_prompt(platform))
        parts.append(f"[{platform.upper()} | sender={sender}]")

        if media:
            file_id = media.get("file_id") or ""
            file_url = media.get("url") or ""
            photo_ref = file_url or file_id
            parts.append(f"[Media attached: type={media.get('type')}, id={file_id}, url={file_url}, photo_ref={photo_ref}]")

        parts.append(text)
        return HumanMessage(content="\n".join(parts))

    async def ainvoke(self, data: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Invoke the deepagents graph and return a normalised output dict."""
        channel_id = data.get("channel_id", "default")
        platform = data.get("platform", "telegram")
        text = data.get("text", "")
        logger.info(f"🧠 [DeepAgent] Processing input for channel '{channel_id}': \"{text}\"")

        # Cache media if present so vision tools can access the direct Telegram photo
        if data.get("media"):
            from src.agents.tools.vision_tools import set_channel_media
            set_channel_media(channel_id, data.get("media"))

        # Progressive disclosure skill inspection & listing intercept
        text_lower = text.lower()
        if "inspect skill" in text_lower:
            from src.skills.loader import SkillsLoader
            skill_name = text_lower.split("inspect skill")[-1].replace("instructions", "").strip().split()[0].strip()
            all_skills = SkillsLoader.load_skills_from_sources([
                "./skills/travel-skills/",
                "./skills/vision-skills/",
                "./skills/expense-skills/",
                "./skills/concierge-skills/",
                "./skills/meta-skills/",
                "./skills/global/"
            ])
            if skill_name in all_skills:
                content = SkillsLoader.read_skill_full_markdown(all_skills[skill_name]["path"])
                return {"output": content, "buttons": [], "tool_calls": []}

        if any(p in text_lower for p in ["what skills do you have", "what skills and mcp servers do you have", "skills library", "list skills"]):
            from src.skills.loader import SkillsLoader
            lines = ["🧠 **DeepAgents Skills Library (Progressive Disclosure)**:\n"]
            for sub_name, s_dir in [
                ("travel_specialist", "./skills/travel-skills/"),
                ("vision_specialist", "./skills/vision-skills/"),
                ("expense_specialist", "./skills/expense-skills/"),
                ("proactive_concierge", "./skills/concierge-skills/"),
                ("skill_specialist", "./skills/meta-skills/"),
            ]:
                skills_dict = SkillsLoader.load_skills_from_sources([s_dir])
                lines.append(f"• **`{sub_name}`** (`{s_dir}`):")
                for s_name, meta in skills_dict.items():
                    lines.append(f"  - `{s_name}`: {meta['description']}")
            
            try:
                from src.skills.mcp_skill_learner import list_connected_mcp_skills
                mcp_listing = list_connected_mcp_skills.invoke({})
                lines.append(f"\n{mcp_listing}")
            except Exception:
                pass
            return {"output": "\n".join(lines), "buttons": [], "tool_calls": []}

        # Build LangGraph config — always inject thread_id so the checkpointer works
        lg_config: Dict[str, Any] = {"configurable": {"thread_id": channel_id}}
        if config:
            if "configurable" in config:
                lg_config["configurable"].update(config["configurable"])
            else:
                lg_config.update(config)

        # Attach Langfuse tracing callback if credentials configured
        callbacks = list(config.get("callbacks", [])) if config and "callbacks" in config else []
        if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
            try:
                from langfuse.langchain import CallbackHandler
                callbacks.append(CallbackHandler())
                logger.info(f"📊 [Langfuse] Full trace enabled for session '{channel_id}' at {settings.LANGFUSE_HOST}")
            except Exception as e:
                logger.warning(f"⚠️ [Langfuse] Could not attach callback handler: {e}")

        if callbacks:
            lg_config["callbacks"] = callbacks

        message = self._build_human_message(data)
        result = await self.graph.ainvoke({"messages": [message]}, config=lg_config)

        if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
            try:
                from langfuse import get_client
                get_client().flush()
            except Exception:
                pass

        messages = result.get("messages", [])
        output_text = "I'm on it! 🚀"
        for msg in reversed(messages):
            content = getattr(msg, "content", None)
            if content and not getattr(msg, "tool_calls", None):
                if isinstance(content, str):
                    output_text = content
                elif isinstance(content, list):
                    texts = []
                    for part in content:
                        if isinstance(part, dict) and "text" in part:
                            texts.append(part["text"])
                        elif isinstance(part, str):
                            texts.append(part)
                    output_text = "\n".join(texts) if texts else str(content)
                else:
                    output_text = str(content)
                break

        # Extract and log tool executions
        executed_tool_calls = []
        for m in messages:
            tcs = getattr(m, "tool_calls", None)
            if tcs:
                for tc in tcs:
                    t_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", str(tc))
                    t_args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
                    logger.info(f"⚡ [Agent Tool Call] -> {t_name}({t_args})")
                    if t_name == "task" and isinstance(t_args, dict) and "subagent_type" in t_args:
                        display_name = f"subagent:{t_args['subagent_type']}"
                    else:
                        display_name = t_name
                    if not any(x.get("name") == display_name for x in executed_tool_calls):
                        executed_tool_calls.append({"name": display_name, "args": t_args})
            msg_type = getattr(m, "type", "")
            if msg_type == "tool" or hasattr(m, "tool_call_id"):
                t_name = getattr(m, "name", "tool")
                content_sample = str(getattr(m, "content", ""))[:140].replace("\n", " ")
                logger.info(f"📥 [Agent Tool Result] <- {t_name} returned: {content_sample}...")
                if t_name and t_name != "tool" and not any(x.get("name") == t_name for x in executed_tool_calls):
                    executed_tool_calls.append({"name": t_name, "args": {}})

        # Generate channel-adaptive action buttons based on interaction type and tools executed
        buttons = build_channel_buttons(platform, output_text, executed_tool_calls)
        if not buttons:
            lower_output = output_text.lower()
            if any(w in lower_output for w in ["trip proposal", "recommended flight", "recommended stay", "itinerary"]):
                buttons = [
                    [InteractiveButton(id="confirm_booking", label="✅ Confirm Proposal", type="callback")],
                    [InteractiveButton(id="modify_plan", label="🔄 Adjust Preferences", type="callback")]
                ]
            elif any(w in lower_output for w in ["scout analysis", "venue analysis", "facade", "vibe"]):
                buttons = [
                    [InteractiveButton(id="maps_view", label="📍 View on Maps", type="callback")]
                ]
            elif any(w in lower_output for w in ["wake-up", "departure poll", "are you ready", "confirm departure"]):
                buttons = [
                    [InteractiveButton(id="vote_yes", label="👍 Ready & On My Way!", type="callback")],
                    [InteractiveButton(id="vote_delayed", label="⏰ Running Late", type="callback")]
                ]

        logger.info(f"✅ [DeepAgent] Graph executed successfully ({len(executed_tool_calls)} tool calls recorded, {len(buttons)} button rows). Response preview: {output_text[:80]}...")
        return {"output": output_text, "buttons": buttons, "tool_calls": executed_tool_calls}


ambient_companion = create_ambient_companion()
