import json
from src.skills.mcp_skill_learner import (
    connect_external_mcp_server,
    list_connected_mcp_skills,
    disconnect_mcp_server
)
from src.agents.deep_companion import ambient_companion

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

async def test_ambient_companion_skill_query():
    # Ask the companion about its skills via chat
    channel = "group_skills_test"
    res = await ambient_companion.ainvoke(
        {
            "channel_id": channel,
            "platform": "telegram",
            "sender_name": "Alice",
            "sender_id": "u1",
            "text": "@companion what skills and MCP servers do you have?"
        },
        config={"configurable": {"thread_id": channel}}
    )

    assert "Active MCP Servers & Learned Skills" in res["output"]
    assert "search_flights" in res["output"]
