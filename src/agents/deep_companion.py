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
1. **WHEN ASKED TO FIND CHEAPEST / SUGGEST DATES** (e.g. "find the cheapest and suggest the dates", "cheapest 5 days next month", "when is it cheapest to fly?"):
   - **DO NOT REFUSE!** NEVER say "As an AI, I cannot choose dates for you".
   - Consult 'travel_specialist' to scan the month across Google Flights using `search_cheapest_flights_in_month`.
   - Proactively recommend the cheapest travel window found, show price comparisons across the month, and present the best flight options!
2. **WHEN DATES & ROUTE ARE SPECIFIC** (e.g. "Fly Oct 15 to Oct 22"):
   - Consult 'travel_specialist' to search live flights for those exact dates.
3. **WHEN DETAILS ARE MISSING & NO BEST-DATE SEARCH REQUESTED**:
   - If the user asks for flights but gave neither specific dates nor asked to find the cheapest dates across a timeframe, politely ask for clarification (dates and departure city).

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

    # Discover live travel tools from MCP server (fallback to internal if server offline)
    mcp_travel_tools = mcp_manager.get_tools_for_server("travel")
    active_travel_tools = mcp_travel_tools if mcp_travel_tools else travel_tools

    now_sgt = datetime.now(timezone(timedelta(hours=8)))
    today_str = now_sgt.strftime("%A, %d %B %Y")
    next_month_str = (now_sgt.replace(day=1) + timedelta(days=32)).strftime("%B %Y")

    # Subagent definitions conforming to DeepAgents custom subagent specification
    subagents_config = [
        {
            "name": "travel_specialist",
            "description": "Searches flights and accommodations, scans entire months to find the cheapest travel dates, and generates day-by-day itineraries using the Travel MCP server.",
            "system_prompt": (
                f"You are an expert travel planner powered by MCP tools.\n"
                f"## CALENDAR CONTEXT (DO NOT HALLUCINATE):\n"
                f"- Today's date is: {today_str} (Year {now_sgt.year}).\n"
                f"- 'Next month' is: {next_month_str}.\n"
                f"- NEVER use 2025 or any past dates.\n\n"
                f"## TOOLS AND USAGE RULES:\n"
                f"1. **`search_cheapest_flights_in_month`**: Use this whenever the user asks to find the cheapest dates, asks to suggest dates, or wants the cheapest N-day trip in a month (e.g., 'cheapest 5-day trip in {next_month_str}'). DO NOT refuse or ask them to pick dates—scan the month, find the lowest fares, and recommend the best dates!\n"
                f"2. **`search_flights`**: Use this when the user has provided specific travel dates (e.g., '2026-10-15 to 2026-10-20').\n"
                f"3. **Origin & Destination**: If departure city (e.g. Singapore vs Bangalore) is ambiguous in context, confirm the city or default to the primary mentioned origin."
            ),
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
            "system_prompt": f"You are a proactive trip coordinator. Today is {today_str}. Check in on trip morning and track journey progress.",
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
            f"- If the user asks to find the cheapest dates, suggest dates, or find the best 5-day trip in a month: "
            f"DO NOT REFUSE! Consult 'travel_specialist' to scan the month across Google Flights, discover the cheapest dates, and recommend them.\n"
            f"- If the user specifies travel plans without dates and did NOT ask to find the cheapest, ask for clarification."
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

        logger.info(f"✅ [DeepAgent] Graph executed successfully. Response preview: {output_text[:80]}...")
        return {"output": output_text}


ambient_companion = create_ambient_companion()
