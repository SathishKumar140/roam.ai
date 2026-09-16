# 🌍 RoamAI: Omnichannel Ambient Group Concierge

> A privacy-conscious, multi-channel ambient group companion built with **LangChain DeepAgent**, **Model Context Protocol (MCP)**, **LangGraph**, and a **100% free-tier / local stack** (SQLite, DuckDuckGo, APScheduler).

---

## 🌟 Key Features

1. **Ambient "Silent Sentry" Listening**: Sits quietly in Telegram and WhatsApp group chats. Passively logs messages to a local SQLite sliding-window buffer (`group_messages`) in $< 15$ ms without spamming the chat.
2. **Model Context Protocol (MCP) Architecture**:
   - Instead of hard-coded proprietary tools, domain capabilities run on standard **MCP Servers**.
   - Includes a standalone **Travel MCP Server** (`src/mcp/servers/travel_mcp_server.py`) serving flight discovery, hotel booking, and itinerary synthesis via JSON-RPC 2.0.
   - Powered by a unified **`MCPClientManager`** (`src/mcp/client.py`) that auto-discovers MCP tools and maps them directly into LangChain tools.
3. **Dynamic MCP Skill-Learning Subsystem**:
   - The companion can **learn new skills dynamically on demand** by connecting to external MCP servers at runtime (e.g., `connect_external_mcp_server(name, command, args)`).
   - Hot-reloads learned tools without restarting the server!
4. **LangChain DeepAgent Multi-Agent Orchestration**:
   - **Deep Thinking**: Decomposes complex group discussions and conflicting constraints into structured actions.
   - **Isolated Context Subagents**:
     - ✈️ **`travel_specialist`**: Powered by Travel MCP Server for flights, hotels, and itineraries.
     - 📸 **`vision_specialist`**: Multimodal photo recognition for venue facades, menus, flyers, and landmarks with real-time rating lookups.
     - 💸 **`expense_specialist`**: Expense logging and Splitwise-style bipartite graph debt simplification (minimizing transactions).
     - ⏰ **`proactive_concierge`**: APScheduler-powered temporal state machine that wakes up on departure day, sends confirmation polls, and tracks trip status.
     - 🔌 **`skill_specialist`**: Connects to new MCP servers and lists active learned skills.
5. **Omnichannel Decoupling**: Seamlessly operates across **Telegram** (rich media cards + inline buttons) and **WhatsApp Cloud API** (interactive quick-reply buttons).
6. **Zero-Cost & Free-Tier First**:
   - Database: SQLite (WAL mode, zero cloud costs).
   - Search: DuckDuckGo (`duckduckgo-search`, zero API keys required).
   - LLM: Google Gemini 1.5 Flash (free tier on Google AI Studio) or Groq Llama 3.3.
   - Reminders: APScheduler (local async scheduling).

---

## 📁 Architecture Overview

```
ambient-agent/
├── src/
│   ├── config.py                     # App settings & LLM provider factory
│   ├── mcp/                          # Model Context Protocol (MCP) Subsystem
│   │   ├── config.json               # Declared MCP servers
│   │   ├── client.py                 # Multi-server MCP client & LangChain tool wrapper
│   │   └── servers/
│   │       └── travel_mcp_server.py  # Standalone Travel MCP Server (JSON-RPC over stdio)
│   ├── skills/
│   │   └── mcp_skill_learner.py      # Dynamic runtime MCP skill acquisition engine
│   ├── models/
│   │   ├── channel.py                # ChannelEvent & OutboundMessage schemas
│   │   └── session.py                # ActiveTripSession & ExpenseLedger schemas
│   ├── storage/
│   │   ├── database.py               # SQLite buffer, trip sessions & ledger store
│   │   └── checkpointer.py           # LangGraph SqliteSaver checkpointer
│   ├── adapters/
│   │   ├── base.py                   # ChannelAdapter interface
│   │   ├── telegram.py               # Telegram Bot API adapter
│   │   └── whatsapp.py               # WhatsApp Cloud API adapter
│   ├── agents/
│   │   ├── tools/
│   │   │   ├── travel_tools.py       # Fallback travel tools
│   │   │   ├── vision_tools.py       # Multimodal photo inspection tools
│   │   │   ├── expense_tools.py      # Expense ledger & debt simplification
│   │   │   └── proactive_tools.py    # Trip wakeup & confirmation tools
│   │   └── deep_companion.py         # LangChain DeepAgent supervisor & subagents
│   ├── scheduler/
│   │   └── temporal.py               # APScheduler proactive job runner
│   └── main.py                       # FastAPI webhook gateway
├── tests/
│   ├── test_normalization.py         # Message normalization tests
│   ├── test_debt_simplification.py   # Splitwise algorithm tests
│   ├── test_subagents.py             # Domain tool tests
│   ├── test_mcp_travel_server.py     # Standalone MCP server JSON-RPC tests
│   ├── test_mcp_client.py            # MCP Client tool discovery & execution tests
│   ├── test_mcp_dynamic_learning.py  # Dynamic MCP skill learning tests
│   └── test_companion_pipeline.py    # End-to-end ambient pipeline tests
└── requirements.txt
```

---

## 🚀 Quickstart Guide

### 1. Configure Environment
Copy the example environment file:
```bash
cp .env.example .env
```
Fill in your keys:
- For Google Gemini (recommended free tier): set `GEMINI_API_KEY`.
- For Telegram: set `TELEGRAM_BOT_TOKEN` (from [@BotFather](https://t.me/BotFather)).

### 2. Run Automated Tests
```bash
pytest tests/ -v
```

### 3. Start the Webhook Server
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🧩 Adding a New Subagent in < 50 Lines

To add any new use case (e.g. Movie Night Planner, Event Ticketing, Restaurant Reservation), simply define your tools and register the subagent in `src/agents/deep_companion.py`:

```python
from langchain_core.tools import tool

@tool
def find_movie_showtimes(city: str, date: str) -> str:
    """Finds current movie showtimes in nearby cinemas."""
    return f"Showtimes in {city} for {date}: Dune 2 (7:00 PM), Interstellar (8:30 PM)."

# Add to subagents_config in create_ambient_companion():
{
    "name": "movie_specialist",
    "description": "Finds movie showtimes and coordinates cinema outings.",
    "system_prompt": "You are a cinema specialist. Help groups vote on movies and pick showtimes.",
    "tools": [find_movie_showtimes, search_web]
}
```
