import json
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from src.skills.mcp_skill_learner import (
    connect_external_mcp_server,
    list_connected_mcp_skills,
    disconnect_mcp_server
)
from src.agents.deep_companion import create_roamai_companion
from tests.test_deepagents_skills import HarnessTestModel

def test_dynamic_mcp_skill_learning():
    # 1. Connect a new MCP server dynamically
    connect_res = connect_external_mcp_server.invoke({
        "server_name": "extra_travel_hub",
        "command": "python3",
        "args_json": "[\"-m\", \"src.mcp.servers.travel_mcp_server\"]"
    })
    assert "Successfully connected to MCP Server 'extra_travel_hub'" in connect_res
    assert "Learned" in connect_res

    # 2. List connected skills
    skills_list = list_connected_mcp_skills.invoke({})
    assert "search_flights" in skills_list
    assert "search_hotels" in skills_list

    # 3. Disconnect
    disc_res = disconnect_mcp_server.invoke({"server_name": "extra_travel_hub"})
    assert "Disconnected MCP server" in disc_res

async def test_roamai_companion_skill_query():
    @tool
    def search_flights() -> str:
        """An authorized flight capability for this inventory test."""
        raise AssertionError("A capability query must not search flights")

    model = HarnessTestModel(messages=iter([
        AIMessage(content="", tool_calls=[{"name": "task", "id": "delegate", "args": {
            "subagent_type": "skill_specialist", "description": "List the tools actually available to this request."}}]),
        AIMessage(content="search_flights is authorized. MCP installation is administrator-only."),
        AIMessage(content="search_flights is authorized. MCP installation is administrator-only."),
    ]))
    companion = create_roamai_companion(model=model, tools=[search_flights], request_context={"sender_name": "Alice"})
    result = await companion.ainvoke({"messages": [HumanMessage(content="What skills and MCP tools are active?")]})
    inventory = next(str(message.content) for message in model.observed_messages
        if message.type == "system" and "Actual authorized tools by specialist" in str(message.content))
    assert '"travel_specialist": ["search_flights"]' in inventory
    assert '"skill_specialist": []' in inventory
    assert [call["name"] for call in result["tool_calls"]] == ["subagent:skill_specialist"]
