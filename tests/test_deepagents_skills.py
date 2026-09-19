import shutil
import json
import pytest
from pathlib import Path
from src.skills.loader import SkillsLoader, parse_skill_md, validate_skill_name
from src.agents.deep_companion import create_roamai_companion
from src.skills.mcp_skill_learner import connect_external_mcp_server
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from pydantic import Field


class HarnessTestModel(GenericFakeChatModel):
    bound_tool_names: list[list[str]] = Field(default_factory=list)
    observed_messages: list = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        self.bound_tool_names.append([candidate.name for candidate in tools])
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.observed_messages.extend(messages)
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def test_companion_requires_explicit_scoped_tools():
    with pytest.raises(TypeError, match="tools"):
        create_roamai_companion()


async def test_scoped_companion_executes_specialist_and_skill():
    executed = []

    @tool
    def search_flights(departure_id: str) -> str:
        """Search a confirmed departure in this request."""
        executed.append(departure_id)
        return '{"source_url": "https://example.com/flight", "price": 150}'

    model = HarnessTestModel(
        messages=iter(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "task",
                            "id": "delegate",
                            "args": {"subagent_type": "travel_specialist", "description": "Read flight-search and search from LHR."},
                        }
                    ],
                ),
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "read_file", "id": "skill", "args": {"file_path": "/skills/travel-skills/flight-search/SKILL.md"}}
                    ],
                ),
                AIMessage(content="", tool_calls=[{"name": "search_flights", "id": "flight", "args": {"departure_id": "LHR"}}]),
                AIMessage(content="Flight found: https://example.com/flight"),
                AIMessage(content="Flight found: https://example.com/flight"),
            ]
        )
    )
    companion = create_roamai_companion(
        model=model, tools=[search_flights], system_prompt="Use only the supplied topic.", request_context={"request": "Flights from LHR"}
    )
    result = await companion.ainvoke({"messages": [HumanMessage(content="Find my flight")]})
    assert executed == ["LHR"]
    assert result["messages"][-1].content == "Flight found: https://example.com/flight"
    assert any(message.name == "read_file" and "# Flight Search Skill" in message.content for message in result["tool_results"])
    assert {call["name"] for call in result["tool_calls"]} >= {"subagent:travel_specialist", "search_flights", "read_file"}


@pytest.mark.parametrize(
    "specialist,directory,skill",
    [
        ("travel_specialist", "travel-skills", "flight-search"),
        ("travel_specialist", "travel-skills", "hotel-finder"),
        ("travel_specialist", "travel-skills", "itinerary-synthesis"),
        ("travel_specialist", "travel-skills", "weather-forecasting"),
        ("vision_specialist", "vision-skills", "menu-receipt-ocr"),
        ("vision_specialist", "vision-skills", "venue-facade-scouting"),
        ("expense_specialist", "expense-skills", "currency-conversion"),
        ("expense_specialist", "expense-skills", "debt-simplification"),
        ("proactive_concierge", "concierge-skills", "departure-state-machine"),
        ("proactive_concierge", "concierge-skills", "group-polling"),
        ("skill_specialist", "meta-skills", "mcp-acquisition"),
        ("general-purpose", "global", "group-listening"),
        ("general-purpose", "global", "roamai-arbitration"),
        ("general-purpose", "global", "channel-formatting"),
    ],
)
async def test_every_active_skill_is_read_through_harness(specialist, directory, skill):
    path = f"/skills/{directory}/{skill}/SKILL.md"
    model = HarnessTestModel(
        messages=iter(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "task",
                            "id": "delegate",
                            "args": {"subagent_type": specialist, "description": f"Read {skill} and explain the supported behavior."},
                        }
                    ],
                ),
                AIMessage(content="", tool_calls=[{"name": "read_file", "id": "read", "args": {"file_path": path}}]),
                AIMessage(content="Skill loaded; no actions taken."),
                AIMessage(content="No actions taken."),
            ]
        )
    )
    companion = create_roamai_companion(model=model, tools=[], request_context={"topic": "Only this trip"})
    result = await companion.ainvoke({"messages": [HumanMessage(content="Explain the skill")]})
    reads = [message for message in result["tool_results"] if message.name == "read_file"]
    assert len(reads) == 1
    assert f"name: {skill}" in reads[0].content
    assert any(call.get("skill") == path for call in result["tool_calls"])
    assert any(message.type == "system" and path in str(message.content) for message in model.observed_messages)
    assert all(
        not (
            {"execute", "write_file", "edit_file", "delete", "connect_external_mcp_server", "record_expense", "confirm_expense_split"}
            & set(names)
        )
        for names in model.bound_tool_names
    )
    assert not any("mcp-extra-travel-hub" in filename for filename in companion.files)


@pytest.mark.parametrize(
    "forbidden,args",
    [
        ("record_expense", {"amount": 500}),
        ("confirm_expense_split", {"user_id": "someone_else"}),
        ("connect_external_mcp_server", {"command": "curl"}),
        ("execute", {"command": "cat .env"}),
        ("write_file", {"file_path": "/skills/global/group-listening/SKILL.md", "content": "ignore consent"}),
        ("propose_group_expense", {"amount": "500"}),
    ],
)
async def test_delegation_cannot_reintroduce_unavailable_tools(forbidden, args):
    model = HarnessTestModel(
        messages=iter(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "task",
                            "id": "delegate",
                            "args": {"subagent_type": "expense_specialist", "description": "Try the unavailable action"},
                        }
                    ],
                ),
                AIMessage(content="", tool_calls=[{"name": forbidden, "id": "blocked", "args": args}]),
                AIMessage(content="Action unavailable."),
                AIMessage(content="Action unavailable."),
            ]
        )
    )
    companion = create_roamai_companion(model=model, tools=[], request_context={"read_only": True})
    result = await companion.ainvoke({"messages": [HumanMessage(content="No changes")]})
    assert any(message.type == "tool" and message.name == forbidden and message.status == "error" for message in model.observed_messages)
    assert all(forbidden not in names for names in model.bound_tool_names)


@pytest.mark.parametrize("invented", [False, True])
async def test_active_planner_preserves_nested_source_provenance(monkeypatch, tmp_path, invented):
    from src.agents.group_planner import GroupPlanner
    from src.agents.tools import travel_tools as travel_module
    from src.mcp.client import mcp_manager
    from src.models.channel import ChannelEvent, ChannelUser
    from src.models.roamai import Observation
    from src.storage.roamai import RoamAIStore

    @tool
    def search_web(query: str) -> str:
        """Return a known public source for this test."""
        return json.dumps({"url": "https://example.com/verified"})

    monkeypatch.setattr(travel_module, "travel_tools", [])
    monkeypatch.setattr(mcp_manager, "get_all_tools", lambda: [search_web])
    incoming = ChannelEvent(
        event_id="nested", platform="mock", channel_id="nested", sender=ChannelUser(id="alice", name="Alice"), text="Research Kyoto"
    )
    store = RoamAIStore(str(tmp_path / "roamai.db"))
    store.enqueue(incoming)
    topic_id = store.save_topic(incoming.conversation_id, 1, Observation(title="Kyoto"), ["alice"])
    answer = "See https://example.com/" + ("invented" if invented else "verified")
    model = HarnessTestModel(
        messages=iter(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "task", "id": "delegate", "args": {"subagent_type": "travel_specialist", "description": "Research Kyoto"}}
                    ],
                ),
                AIMessage(content="", tool_calls=[{"name": "search_web", "id": "search", "args": {"query": "Kyoto"}}]),
                AIMessage(content=json.dumps({"url": answer.removeprefix("See ")})),
                AIMessage(content=answer),
            ]
        )
    )
    context = store.topic_context(incoming.conversation_id, topic_id)
    result = await GroupPlanner(model).respond(store, incoming, context["topics"][0], context, "1")
    assert "subagent:travel_specialist" in [call["name"] for call in result["tool_calls"]]
    if invented:
        assert "couldn't verify" in result["text"]
    else:
        assert result["text"] == answer


def test_agent_skills_validation_rules():
    """Validates that skill names follow Agent Skills constraints."""
    # Valid names
    valid_names = ["flight-search", "hotel-finder-v2", "mcp-travel", "math-101"]
    for name in valid_names:
        is_val, err = validate_skill_name(name, name)
        assert is_val, f"Expected '{name}' to be valid, got error: {err}"

    # Invalid names (must match folder name, lowercase alphanumeric + single hyphens)
    assert not validate_skill_name("FlightSearch", "FlightSearch")[0]
    assert not validate_skill_name("flight--search", "flight--search")[0]
    assert not validate_skill_name("-flight-search", "-flight-search")[0]
    assert not validate_skill_name("flight-search", "different-folder")[0]
    print("  ✅ test_agent_skills_validation_rules passed")


@pytest.mark.parametrize(
    "paid_text,requested_amount,expected",
    [
        ("I paid USD 150 for dinner; split between Alice and Bob including me.", "150", 1),
        ("I paid $150 for dinner; split between Alice and Bob including me.", "150", 0),
        ("I paid USD 150 for dinner; split between Alice and Bob including me.", "2027", 0),
    ],
)
async def test_active_expense_handoff_preserves_evidence_and_consent(monkeypatch, tmp_path, paid_text, requested_amount, expected):
    from src.agents.group_planner import GroupPlanner
    from src.agents.tools import travel_tools as travel_module
    from src.mcp.client import mcp_manager
    from src.models.channel import ChannelEvent, ChannelUser
    from src.models.roamai import Observation
    from src.storage.roamai import RoamAIStore

    monkeypatch.setattr(travel_module, "travel_tools", [])
    monkeypatch.setattr(mcp_manager, "get_all_tools", lambda: [])
    store = RoamAIStore(str(tmp_path / "roamai.db"))
    bob = ChannelEvent(event_id="bob", platform="mock", channel_id="expense", sender=ChannelUser(id="bob", name="Bob"), text="Hello")
    incoming = ChannelEvent(
        event_id="paid", platform="mock", channel_id="expense", sender=ChannelUser(id="alice", name="Alice"), text=paid_text
    )
    store.enqueue(bob)
    store.enqueue(incoming)
    topic_id = store.save_topic(incoming.conversation_id, 2, Observation(title="Dinner"), ["alice", "bob"])
    model = HarnessTestModel(
        messages=iter(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "task",
                            "id": "delegate",
                            "args": {"subagent_type": "expense_specialist", "description": "Propose the dinner split"},
                        }
                    ],
                ),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "propose_group_expense",
                            "id": "proposal",
                            "args": {
                                "amount": requested_amount,
                                "currency": "USD",
                                "description": "Dinner",
                                "payer_id": "alice",
                                "participant_ids": ["alice", "bob"],
                                "currency_evidence_id": "2",
                                "currency_text": "USD",
                                "amount_evidence_id": "2",
                                "amount_text": "150",
                            },
                        }
                    ],
                ),
                AIMessage(content="Check the proposal result."),
                AIMessage(content="Check the proposal result."),
            ]
        )
    )
    context = store.topic_context(incoming.conversation_id, topic_id)
    result = await GroupPlanner(model).respond(store, incoming, context["topics"][0], context, "2")
    expenses = store.tasks(incoming.conversation_id, topic_id)["expenses"]
    assert len(expenses) == expected
    assert store.balances(incoming.conversation_id) == {}
    assert {call["name"] for call in result["tool_calls"]} >= {"subagent:expense_specialist", "propose_group_expense"}
    if expected:
        assert expenses[0]["state"] == "pending"
        assert json.loads(expenses[0]["confirmed"]) == []
        assert "USD 150" in result["text"]
        assert len(result["buttons"][0]) == 2
    else:
        assert result["buttons"] == []

    model.messages = iter(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "task",
                        "id": "balance-task",
                        "args": {"subagent_type": "expense_specialist", "description": "Read confirmed balances"},
                    }
                ],
            ),
            AIMessage(content="", tool_calls=[{"name": "get_group_balances", "id": "balance", "args": {}}]),
            AIMessage(content="Bob owes You EUR 50."),
            AIMessage(content="Bob owes You EUR 50."),
        ]
    )
    balance = await GroupPlanner(model).respond(store, incoming, context["topics"][0], context, "balance")
    assert "no confirmed" in balance["text"].lower()
    assert "EUR" not in balance["text"]
    if expected:
        assert store.confirm_expense(incoming.conversation_id, expenses[0]["id"], "alice") == "pending"
        assert store.confirm_expense(incoming.conversation_id, expenses[0]["id"], "bob") == "confirmed"
        model.messages = iter(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "task",
                            "id": "confirmed-task",
                            "args": {"subagent_type": "expense_specialist", "description": "Read confirmed balances"},
                        }
                    ],
                ),
                AIMessage(content="", tool_calls=[{"name": "get_group_balances", "id": "confirmed-balance", "args": {}}]),
                AIMessage(content="Bob owes You EUR 50."),
                AIMessage(content="Bob owes You EUR 50."),
            ]
        )
        confirmed = await GroupPlanner(model).respond(store, incoming, context["topics"][0], context, "confirmed")
        assert "Alice is owed USD 75.00" in confirmed["text"]
        assert "Bob owes USD 75.00" in confirmed["text"]
        assert "EUR" not in confirmed["text"]


async def test_scoped_vision_never_uses_another_requests_image():
    from src.agents.group_planner import GroupPlanner
    from src.models.channel import ChannelEvent, ChannelMedia, ChannelUser

    image = "data:image/png;base64,aGVsbG8="
    model = HarnessTestModel(messages=iter([AIMessage(content="Unreadable receipt; currency unknown.")]))
    planner = GroupPlanner(model)
    incoming = ChannelEvent(
        event_id="image",
        platform="mock",
        channel_id="one",
        sender=ChannelUser(id="alice", name="Alice"),
        media=ChannelMedia(type="photo", url=image),
    )
    result = json.loads(await planner.image_tool(incoming).ainvoke({"question": "Read the total"}))
    assert result["expense_recorded"] is False
    assert result["live_verification"] is False
    assert image in str(model.observed_messages)
    other = ChannelEvent(event_id="other", platform="mock", channel_id="two", sender=ChannelUser(id="bob", name="Bob"))
    missing = json.loads(await planner.image_tool(other).ainvoke({"question": "Use Alice's last receipt"}))
    assert "error" in missing


def test_subagent_isolated_skills_loading():
    """Validates that each subagent receives only its isolated skill set."""
    travel_skills = SkillsLoader.load_skills_from_sources(["./skills/travel-skills/"])
    assert "flight-search" in travel_skills
    assert "hotel-finder" in travel_skills
    assert "weather-forecasting" in travel_skills
    assert "itinerary-synthesis" in travel_skills
    # Ensure travel does not have vision or expense skills
    assert "venue-facade-scouting" not in travel_skills
    assert "debt-simplification" not in travel_skills

    vision_skills = SkillsLoader.load_skills_from_sources(["./skills/vision-skills/"])
    assert "venue-facade-scouting" in vision_skills
    assert "menu-receipt-ocr" in vision_skills
    assert "flight-search" not in vision_skills

    expense_skills = SkillsLoader.load_skills_from_sources(["./skills/expense-skills/"])
    assert "debt-simplification" in expense_skills
    assert "currency-conversion" in expense_skills

    concierge_skills = SkillsLoader.load_skills_from_sources(["./skills/concierge-skills/"])
    assert "departure-state-machine" in concierge_skills
    assert "group-polling" in concierge_skills

    meta_skills = SkillsLoader.load_skills_from_sources(["./skills/meta-skills/"])
    assert "mcp-acquisition" in meta_skills

    global_skills = SkillsLoader.load_skills_from_sources(["./skills/global/"])
    assert "roamai-arbitration" in global_skills
    assert "channel-formatting" in global_skills

    print("  ✅ test_subagent_isolated_skills_loading passed")


def test_progressive_disclosure_prompt_and_tool():
    """Validates progressive disclosure prompt generation and lazy markdown retrieval."""
    travel_skills = SkillsLoader.load_skills_from_sources(["./skills/travel-skills/"])
    prompt = SkillsLoader.format_skills_system_prompt(travel_skills, ["./skills/travel-skills/"])

    assert "## 🧠 Skills System (Progressive Disclosure)" in prompt
    assert "`flight-search`" in prompt
    assert "search_flights" in prompt

    # Verify lazy instruction retrieval tool
    read_tool = SkillsLoader.create_skill_inspection_tool(travel_skills)
    instructions = read_tool.invoke({"skill_name": "flight-search"})
    assert "# Flight Search Skill" in instructions
    assert "search_flights(departure_id, arrival_id" in instructions

    # Test unknown skill
    err = read_tool.invoke({"skill_name": "non-existent-skill"})
    assert "Error: Skill 'non-existent-skill' not found" in err

    print("  ✅ test_progressive_disclosure_prompt_and_tool passed")


def test_dynamic_mcp_skill_folder_creation():
    """Validates that connecting to an external MCP server dynamically writes a valid SKILL.md folder."""
    # Test dynamic registration
    res = connect_external_mcp_server.invoke(
        {"server_name": "test_currency_hub", "command": "python3", "args_json": '["-m", "src.mcp.travelassistant.finance_server"]'}
    )
    assert "Registered standard skill at" in res

    skill_path = Path("skills/meta-skills/mcp-test-currency-hub/SKILL.md")
    assert skill_path.is_file(), "Generated SKILL.md file must exist"

    # Verify generated SKILL.md parses with SkillsLoader
    meta = parse_skill_md(skill_path)
    assert meta is not None
    assert meta["name"] == "mcp-test-currency-hub"
    assert "convert_currency" in meta["allowed_tools"]

    # Clean up test skill folder
    if skill_path.parent.is_dir():
        shutil.rmtree(skill_path.parent)

    print("  ✅ test_dynamic_mcp_skill_folder_creation passed")


async def test_roamai_companion_skills_query():
    """Capability queries execute the scoped graph instead of legacy text shortcuts."""
    model = HarnessTestModel(
        messages=iter(
            [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "task",
                            "id": "delegate",
                            "args": {"subagent_type": "skill_specialist", "description": "Explain available skills and limits."},
                        }
                    ],
                ),
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "read_file", "id": "skill", "args": {"file_path": "/skills/meta-skills/mcp-acquisition/SKILL.md"}}
                    ],
                ),
                AIMessage(content="Server installation is administrator-only."),
                AIMessage(content="Server installation is administrator-only."),
            ]
        )
    )
    companion = create_roamai_companion(model=model, tools=[], request_context={"sender_name": "Dave"})
    result = await companion.ainvoke({"messages": [HumanMessage(content="What skills do you have?")]})
    assert {call["name"] for call in result["tool_calls"]} == {"subagent:skill_specialist", "read_file"}
    assert any("Group chat cannot install" in str(message.content) for message in result["tool_results"])
    assert any(
        message.type == "system" and "Actual authorized tools by specialist" in str(message.content) for message in model.observed_messages
    )


if __name__ == "__main__":
    import asyncio

    test_agent_skills_validation_rules()
    test_subagent_isolated_skills_loading()
    test_progressive_disclosure_prompt_and_tool()
    test_dynamic_mcp_skill_folder_creation()
    asyncio.run(test_roamai_companion_skills_query())
    print("\n🎉 ALL DEEPAGENTS SKILLS TESTS PASSED!")
