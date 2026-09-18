# 🌍 RoamAI: Omnichannel

> A context-aware group companion with a separate conversation listener, scoped planner,
> durable SQLite queues, and allowlisted discovery tools. Telegram groups and a local web
> simulator are supported; the WhatsApp adapter currently supports direct chats only.

---

## 🌟 Key Features

1. **Selective participation**: A read-only observer identifies topics and coordination needs.
   Deterministic rules gate offers, explicit requests, accepted help, and clear follow-ups.
2. **Scoped memory**: Conversation identities include platform, account, and chat. Topics,
   member preferences, task state, and supporting message IDs stay within that conversation.
3. **Consent-based coordination**: Polls collect changeable votes; expense proposals require
   the payer and every participant to confirm. Reminders persist across restarts.
4. **Durable processing and delivery**: Authenticated webhooks persist events before acknowledging
   them. Inbox retries and independently tracked outbox retries do not rerun the planner on delivery failure.
5. **DeepAgent orchestration**: The scoped planner invokes a DeepAgent supervisor with isolated
   travel, vision, expense, concierge and capability specialists. DeepAgent handles task delegation,
   planning and progressive skill loading; tools enforce scope and consent. Discovery uses allowlisted MCP tools.
   Event search reports its source and availability instead of inventing fallback events.
   Provider credentials, quotas, and charges may apply; no booking or payment execution is enabled.
6. **Local simulator**: The web UI supports multiple speakers, passive messages, and task-specific
   buttons. It is development-only, not an authenticated production messaging service.

---

## 📁 Architecture Overview

The active webhook path is:

```text
adapters -> durable inbox -> GroupListener -> participation policy
                         -> GroupPlanner -> create_roamai_companion
                            -> DeepAgent supervisor -> specialist + guarded tools
                         -> durable outbox -> adapters

                   group / topic / preference / task storage
```

The implementation lives in `src/services/roamai.py`, `src/agents/listener.py`,
`src/agents/group_planner.py`, `src/agents/deep_companion.py`, and `src/storage/roamai.py`.
Every planner request supplies the factory with scoped context and guarded tools. Each specialist
receives that same topic snapshot, an isolated conversation and its own tool subset and skill index.
Skills are snapshotted into the request's virtual filesystem; no host files, shell or file-writing
tools are exposed. There is no cross-turn DeepAgent checkpointer; persisted topic facts and tasks
remain the source of truth. Nested tool results feed citation validation, and actual handoffs and
skill reads are included in simulator traces.

`create_roamai_companion` requires an explicit `tools` argument. There is no legacy adapter,
global companion singleton or no-argument fallback. Its callers and tests use the scoped path;
the legacy ledger, image cache, scheduler and dynamic server-install tools remain outside it.

```
roam.ai/
├── skills/                           # Standard LangChain DeepAgents Skills
│   ├── global/                       # Global supervisor skills
│   │   ├── roamai-arbitration/       # Scoped multi-party constraint synthesis
│   │   ├── group-listening/          # Active planner participation and consent rules
│   │   └── channel-formatting/       # Telegram & WhatsApp presentation bounds
│   ├── travel-skills/                # travel_specialist isolated skills
│   │   ├── flight-search/            # Google Flights query & price filtering
│   │   ├── hotel-finder/             # Accommodation discovery with rating filters
│   │   ├── weather-forecasting/      # Open-Meteo & NWS forecasts
│   │   └── itinerary-synthesis/      # Multi-day geographically clustered plans
│   ├── vision-skills/                # vision_specialist isolated skills
│   │   ├── venue-facade-scouting/    # Storefront recognition & rating checks
│   │   └── menu-receipt-ocr/         # Dish & bill itemization
│   ├── expense-skills/               # expense_specialist isolated skills
│   │   ├── debt-simplification/      # Splitwise bipartite net balance algorithm
│   │   └── currency-conversion/      # Multi-currency FX normalization
│   ├── concierge-skills/             # proactive_concierge isolated skills
│   │   ├── departure-state-machine/  # Trip lifecycle & departure mornings
│   │   └── group-polling/            # Consensus tap-to-vote quick actions
│   └── meta-skills/                  # skill_specialist isolated skills
│       └── mcp-acquisition/          # Dynamic MCP handshake & SKILL.md creation
├── src/
│   ├── config.py                     # App settings & LLM provider factory
│   ├── mcp/                          # Model Context Protocol (MCP) Subsystem
│   │   ├── config.json               # Declared MCP servers
│   │   ├── client.py                 # Multi-server MCP client & LangChain tool wrapper
│   │   ├── travelassistant/          # skarlekar/mcp_travelassistant 6-server ecosystem
│   │   └── servers/
│   │       └── travel_mcp_server.py  # Standalone Travel MCP Server (JSON-RPC over stdio)
│   ├── skills/
│   │   ├── loader.py                 # DeepAgents SkillsLoader & Progressive Disclosure
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
│   ├── test_travelassistant_mcp.py   # skarlekar/mcp_travelassistant 6 servers tests
│   ├── test_deepagents_skills.py     # DeepAgents Skills specification & isolation tests
│   └── test_companion_pipeline.py    # End-to-end  pipeline tests
└── requirements.txt
```

---

## 🚀 Quickstart Guide

### Group Listener Runtime

Webhooks now use a durable SQLite inbox, a separate read-only conversation observer,
a group/topic-scoped planner, and an independent delivery outbox. Run **one Uvicorn
application process** for this release. Two async processing loops can work on different
groups; a group lease serializes its requests. This is not yet the PostgreSQL/multi-worker deployment.

- `ROAMAI_LISTENER_MODE=shadow` is the default: observe allowed groups and log decisions,
   but do not send passive offers. `live` enables offers; `off` disables passive platform intake.
- Set `ROAMAI_ALLOWED_GROUPS` to comma-separated `platform:account-id:chat-id` entries after
   obtaining the group's agreement. For Telegram the account ID is the bot's numeric ID.
   `*` enables all groups and should only be used in controlled testing.
- Set `TELEGRAM_BOT_USERNAME` for accurate mentions and `TELEGRAM_WEBHOOK_SECRET` for
   the `X-Telegram-Bot-Api-Secret-Token` registered with Telegram. Passive listening needs
   appropriate bot privacy/admin settings. Webhooks without the configured secret are rejected.
- WhatsApp POST webhooks require `WHATSAPP_APP_SECRET` and a valid Meta signature.
   This adapter supports direct chats, not WhatsApp group semantics. Window/template
   restrictions still apply; permanent provider failures are not retried.
- Passive messages debounce for 10 seconds (maximum 30); group offer cooldown is 300 seconds.
   Both are configurable. Declined topic offers stay suppressed; explicit requests still work.
- The web UI uses a separate mock connection, asynchronous queued replies and an
   "Address RoamAI" checkbox. Uncheck it for passive group messages. Local web APIs are
   disabled outside `ENVIRONMENT=development`; do not expose this unauthenticated simulator publicly.

Accepted assistance can create short polls, pending expense proposals, and timezone-aware
reminders. Buttons identify the exact task. Expenses require the payer and every participant
to confirm; votes do not authorize expenses. Member IDs must have been observed in the group.
Event search uses SerpApi with supported date filters and never fabricates fallback events.
Read-only discovery tools are allowlisted; chat users cannot install MCP servers or run commands.

### Topic Memory And Input Guards

- Trip fields are stored separately with literal message evidence. A budget update merges that
   field instead of erasing dates, travelers or other facts. Initial summaries remain historical;
   newer field evidence takes precedence. SQLite FTS5 retrieves named older topics alongside
   recent topics, with at most 20 topics in an observer request. The planner retains the original
   messages supporting current facts beyond its normal recent-message window. SQLite must include FTS5.
- The planner receives only the selected topic's messages, preferences and tasks. Explicit
   comparisons receive the named topics in read-only mode with no tools. Topic selection and
   fact extraction still depend on the model; ambiguous references must be clarified.
- Preferences default to the topic and use a small supported-key allowlist. Global preferences
   require explicit wording such as "remember ... for all trips". Transaction status and
   confirmation-policy instructions are not preferences. Pre-existing unscoped preferences
   remain in SQLite for inspection but are not used as trusted memory. Previously lost facts
   cannot be reconstructed reliably; ask the user to restate them.
- Offers bind to the author of the cited help/payment message, not the last batch speaker.
   Expense tools require payer-authored currency and numeric payment evidence; `$` alone is
   insufficient. Years, substrings, estimates and another speaker's amount cannot supply the
   tested payment evidence. Conflicting retries cannot change a pending proposal's terms. Proposal
   details are rendered from the stored record. A rejected split cannot be recreated in the
   same topic, and rejection is not added to positive confirmation history.
- Explicit English refusals such as "do not create" and "don't send" remove mutation tools
   for that turn while retaining read-only balances and discovery. This conservative gate is
   not a complete natural-language authorization system or multilingual intent classifier.
- Flight and hotel dates are validated without changing the year or inventing missing dates.
   Departure evidence must be affirmative and topic-scoped. Unclear wording is rejected for
   clarification. Monthly flight search samples up to four windows and never fabricates fares
   when no provider result exists. Legacy flight/hotel fallback wrappers are not active.
- Response links must come from structured tool results; invented and credential-bearing
   links are suppressed. This is URL provenance, not a reachability check or proof that a
   source supports every claim. Dietary suitability, availability and fare units still need
   independent verification. See [the verification report](tests/TRAVEL_UI_SCENARIOS.md).

Processing retries three times; delivery retries up to six times, honoring provider retry delays.
Replies are split into individually tracked chunks. Platform acceptance is not proof of delivery/read,
and an ambiguous network failure after acceptance can still produce a duplicate. Failed rows remain
in the inbox/outbox and failures are logged; automatic external alerts and an operator redrive UI
are still pending. Reminders older than one hour are cancelled after downtime rather than sent stale.
All claimed messages (up to 50) reach the observer even when the normal history window is 40.
Recent questions addressed to a member are tracked in the outbox; an answer from that member
can receive a failure notice even when the observer itself fails. This does not authorize tools,
and different speakers, expired questions and already answered questions do not qualify.

### Readiness And Diagnostics

- `/health` is liveness only. `/ready` returns 503 when the database cannot be queried, a worker
   is missing/stopped, live model configuration is unavailable, or queues are overdue. It does
   not expose conversation data or provider credentials. Provider connectivity is explicitly
   `not_probed`; configuration is not proof that an API key, quota or external service works.
- `/api/runtime` shows aggregate queue states and overdue work in development only; it returns
   404 outside development. Historical failed rows remain visible without blocking readiness
   forever. This is diagnostic information, not an authenticated production admin interface.
- The active observer/planner require a real model. Initialization failures raise an error
   instead of silently selecting the legacy fake chat model. Legacy test callers can still
   use the default model factory behavior.

Current boundaries: memory is group-scoped with message evidence, but retention/deletion controls,
quiet-hour scheduling, cross-platform account linking, full activity lifecycle cancellation and
production database migration remain follow-ups. The legacy trip/checkpointer tables are preserved;
they are not silently imported into the new group's memory or ledger. Only the scoped DeepAgent
factory is supported; the legacy companion adapter has been removed. Departure skills
coordinate explicit reminders, not automatic trip-state transitions. Capability discovery cannot
install MCP servers from chat. Image analysis uses only the current resolved attachment, without
the legacy global-image fallback. Receipt text still needs payer-authored confirmation before a split.

Focused local checks: `pytest tests/test_roamai_listener.py tests/test_normalization.py tests/test_deepagents_skills.py -q`.
Harness tests execute real DeepAgent graphs with scripted models; they verify delegation, all 14
active skill reads, denied tools, nested source provenance and consent guards. They are not proof
that a live model follows every skill correctly or that every external provider is available.

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

## Adding A Specialist

1. Implement and test an honest discovery tool or a group/topic-scoped mutation tool. Add it to
   the active planner's allowlist or scoped tool builder, never to the legacy tool collection alone.
2. Add a specialist entry to the scoped factory's `routing` table with an explicit tool-name subset
   and a skill directory. Keep the shared authorization and evidence instructions.
3. Write skills against the actual tool schemas. Skill files cannot grant permissions; generated
   MCP skills are not automatically exposed to group conversations.
4. Test real `task` delegation, skill reads, tool results, unavailable inputs, cross-topic isolation,
   consent and retries. Then verify the live path through the simulator and inspect its stored traces.
