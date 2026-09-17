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
1. **WHEN ASKED TO PLAN A TRIP (e.g. "let's plan a trip to Bali!")**:
   - Immediately consult 'travel_specialist' to synthesize a comprehensive 'Trip Proposal' with 'Recommended Flight' and 'Recommended Stay' tailored to constraints in chat history.
2. **WHEN ASKED TO FIND CHEAPEST / SUGGEST DATES** (e.g. "find the cheapest and suggest the dates", "cheapest 5 days next month", "when is it cheapest to fly?"):
   - **DO NOT REFUSE!** NEVER say "As an AI, I cannot choose dates for you".
   - Consult 'travel_specialist' to scan the month across Google Flights using `search_cheapest_flights_in_month`.
   - Proactively recommend the cheapest travel window found, show price comparisons across the month, and present the best flight options!
3. **WHEN DATES & ROUTE ARE SPECIFIC** (e.g. "Fly Oct 15 to Oct 22"):
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
                f"## MANDATORY TOOL CALLING RULES (NO MOCK DATA, NO PLACEHOLDERS):\n"
                f"1. YOU MUST ACTUALLY CALL YOUR TOOLS before giving recommendations.\n"
                f"2. NEVER output placeholders like '[Insert Departure City]' or estimated costs without calling tools.\n"
                f"3. When asked to plan a trip to a destination (e.g. Vietnam Ha Giang loop, Bali, Tokyo):\n"
                f"   - Call `search_web` to research the destination's geography, best stops, and route details.\n"
                f"   - Call `search_flights` or `search_cheapest_flights_in_month` to find real live flights (default origin: 'SIN' if unspecified).\n"
                f"   - Call `search_hotels` to look up real accommodation in the destination.\n"
                f"   - Call `generate_itinerary` or compile real route recommendations from live search results.\n"
                f"4. Format the final response clearly titled '# Trip Proposal' with sections '### Recommended Flight' and '### Recommended Stay'."
            ),
            "tools": active_travel_tools,
            "skills": ["./skills/travel-skills/"],
        },
        {
            "name": "vision_specialist",
            "description": "Analyzes photos sent to the group (venues, menus, flyers, receipts) using multimodal vision.",
            "system_prompt": "You are a multimodal venue and scout expert. When analyzing photos or places, always structure your response with exact headers '### Scout Analysis', '### Vibe', and '### Pricing'.",
            "tools": vision_tools,
            "skills": ["./skills/vision-skills/"],
        },
        {
            "name": "expense_specialist",
            "description": "Manages the group expense ledger and calculates simplified debt settlement (who owes what).",
            "system_prompt": (
                "You are an accurate group accountant. "
                "When a user reports paying an expense (e.g. 'I paid $120 for dinner'), IMMEDIATELY call 'record_expense'. "
                "If specific split members are not mentioned, split among all group members or use 'Alice, Bob'. "
                "Always include 'Logged expense' in your response. "
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
            f"[TRAVEL RULES]:\n"
            f"- If the user asks about planning a trip, vacation, or mentions a destination (e.g. 'I am planning to vietnam giang loop' or 'plan trip to Bali'): "
            f"You MUST delegate to 'travel_specialist'. The travel specialist must execute live tools (search_web, search_flights, search_hotels) to research actual options and generate a verified 'Trip Proposal' with real flights and stays.\n"
            f"- NEVER output placeholders like '[Insert Departure City]'. If departure city is not stated, assume default origin is Singapore (SIN).\n"
            f"- If the user asks to find the cheapest dates or suggest dates in a month: "
            f"Consult 'travel_specialist' to scan Google Flights via search_cheapest_flights_in_month and recommend the cheapest dates.\n"
            f"- If asked about skills, capabilities, or MCP servers: consult 'skill_specialist' using list_connected_mcp_skills.\n"
            f"- If a photo is attached: consult 'vision_specialist' and format response with 'Scout Analysis', 'Vibe', and 'Pricing'.\n"
            f"- If money, bills, dinner payments, balance, or 'Who owes what' is asked: You MUST delegate to 'expense_specialist' to call 'record_expense' or 'get_balance_sheet' and output the 'Group Expense Settlement Sheet' or 'Logged expense'!"
        )

        if history:
            history_lines = "\n".join(
                f"  {m.get('sender_name', 'User')}: {m.get('text', '')}"
                for m in history[-20:]
            )
            parts.append(f"[Recent group chat history]\n{history_lines}")

        parts.append(f"[{platform.upper()} | sender={sender}]")

        if media:
            parts.append(f"[Media attached: type={media.get('type')}, id={media.get('file_id', '')}]")

        parts.append(text)
        return HumanMessage(content="\n".join(parts))

    async def ainvoke(self, data: Dict[str, Any], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Invoke the deepagents graph and return a normalised output dict."""
        channel_id = data.get("channel_id", "default")
        text = data.get("text", "")
        logger.info(f"🧠 [DeepAgent] Processing input for channel '{channel_id}': \"{text}\"")

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

        # Generate action buttons based on interaction type
        buttons = []
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

        logger.info(f"✅ [DeepAgent] Graph executed successfully ({len(executed_tool_calls)} tool calls recorded). Response preview: {output_text[:80]}...")
        return {"output": output_text, "buttons": buttons, "tool_calls": executed_tool_calls}


ambient_companion = create_ambient_companion()
