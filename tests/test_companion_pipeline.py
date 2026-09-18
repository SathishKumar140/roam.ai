import json

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from src.agents.deep_companion import create_roamai_companion
from tests.test_deepagents_skills import HarnessTestModel


async def invoke_specialist(specialist, candidate, arguments, context):
    model = HarnessTestModel(messages=iter([
        AIMessage(content="", tool_calls=[{"name": "task", "id": "delegate", "args": {
            "subagent_type": specialist, "description": "Handle the scoped request with your supplied tool."}}]),
        AIMessage(content="", tool_calls=[{"name": candidate.name, "id": "execute", "args": arguments}]),
        AIMessage(content="Task handled."),
        AIMessage(content="Task handled."),
    ]))
    companion = create_roamai_companion(model=model, tools=[candidate], request_context=context)
    result = await companion.ainvoke({"messages": [HumanMessage(content=json.dumps(context))]})
    assert {call["name"] for call in result["tool_calls"]} >= {"subagent:" + specialist, candidate.name}
    return result, model


async def test_roamai_companion_travel_proposal():
    @tool
    def search_hotels(destination: str, adults: int, currency: str) -> str:
        """Return the scoped hotel search parameters for this test."""
        return json.dumps({"destination": destination, "adults": adults, "currency": currency})

    context = {"topic": "Bali", "preferences": {"diet": "vegetarian", "budget": "USD 150/night"}}
    result, model = await invoke_specialist("travel_specialist", search_hotels,
        {"destination": "Bali", "adults": 2, "currency": "USD"}, context)
    response = next(message for message in result["tool_results"] if message.name == "search_hotels")
    assert json.loads(response.content) == {"destination": "Bali", "adults": 2, "currency": "USD"}
    assert any(message.type == "system" and "USD 150/night" in str(message.content) for message in model.observed_messages)


async def test_roamai_companion_vision_photo_analysis():
    @tool
    def analyze_attached_image(question: str) -> str:
        """Return an unreadable-image result without inventing a venue."""
        return json.dumps({"error": "No resolved image is attached to this request."})

    result, model = await invoke_specialist("vision_specialist", analyze_attached_image,
        {"question": "What is this place?"}, {"has_attached_image": False})
    response = next(message for message in result["tool_results"] if message.name == "analyze_attached_image")
    assert "error" in json.loads(response.content)
    assert all("analyze_venue_photo" not in names for names in model.bound_tool_names)


async def test_roamai_companion_expense_logging_and_balance():
    @tool
    def get_group_balances() -> str:
        """Return confirmed balances only; the supplied expense is pending."""
        return "{}"

    result, model = await invoke_specialist("expense_specialist", get_group_balances, {},
        {"tasks": {"expenses": [{"amount": "120", "currency": "USD", "state": "pending"}]}})
    response = next(message for message in result["tool_results"] if message.name == "get_group_balances")
    assert json.loads(response.content) == {}
    assert all(not {"record_expense", "confirm_expense_split"}.intersection(names) for names in model.bound_tool_names)
