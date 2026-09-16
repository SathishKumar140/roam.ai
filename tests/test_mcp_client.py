import json
from src.mcp.client import mcp_manager

def test_mcp_client_tool_discovery():
    """Verifies that MCPClientManager connects to the Travel MCP server and loads tools as LangChain tools."""
    tools = mcp_manager.get_all_tools()
    assert len(tools) > 0

    tool_names = [t.name for t in tools]
    assert "search_flights" in tool_names
    assert "search_hotels" in tool_names
    assert "generate_itinerary" in tool_names

def test_mcp_client_tool_invocation():
    """Verifies executing an MCP tool through its LangChain wrapper."""
    flight_tool = next(t for t in mcp_manager.get_all_tools() if t.name == "search_flights")
    assert flight_tool is not None

    # Invoke tool via LangChain tool protocol
    result_str = flight_tool.invoke({
        "origin": "SIN",
        "destination": "DPS",
        "date": "2026-10-15",
        "max_budget": 200.0
    })

    data = json.loads(result_str)
    assert data["source"] == "Travel-MCP-Server"
    assert "flights" in data
    assert len(data["flights"]) > 0
