try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import re
import json
import logging
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

    # Only use create_deep_agent when the LLM can actually support tool-binding.
    from deepagents import create_deep_agent
    graph = create_deep_agent(
        model=llm,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
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

        parts = []
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
