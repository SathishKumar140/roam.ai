import json
import subprocess
import sys
import os


def test_travel_mcp_server_stdio():
    """Tests the Travel MCP Server by launching it as a subprocess and sending JSON-RPC messages."""
    server_path = os.path.join(os.path.dirname(__file__), "../src/mcp/servers/travel_mcp_server.py")
    proc = subprocess.Popen(
        [sys.executable, server_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
    )

    try:
        # 1. Initialize request
        init_req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}) + "\n"
        proc.stdin.write(init_req)
        proc.stdin.flush()

        init_resp_line = proc.stdout.readline()
        init_resp = json.loads(init_resp_line)
        assert init_resp.get("id") == 1
        assert "serverInfo" in init_resp.get("result", {})
        assert init_resp["result"]["serverInfo"]["name"] == "travel-mcp-server"

        # 2. List tools
        tools_req = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n"
        proc.stdin.write(tools_req)
        proc.stdin.flush()

        tools_resp_line = proc.stdout.readline()
        tools_resp = json.loads(tools_resp_line)
        assert tools_resp.get("id") == 2
        tools = tools_resp.get("result", {}).get("tools", [])
        tool_names = [t["name"] for t in tools]
        assert "search_flights" in tool_names
        assert "search_hotels" in tool_names
        assert "generate_itinerary" in tool_names

        # 3. Call tool: search_flights
        call_req = (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": "search_flights", "arguments": {"origin": "SIN", "destination": "DPS", "date": "2026-10-15"}},
                }
            )
            + "\n"
        )
        proc.stdin.write(call_req)
        proc.stdin.flush()

        call_resp_line = proc.stdout.readline()
        call_resp = json.loads(call_resp_line)
        assert call_resp.get("id") == 3
        content = call_resp.get("result", {}).get("content", [])
        assert len(content) > 0
        flight_data = json.loads(content[0]["text"])
        assert flight_data["source"] == "Travel-MCP-Server"
        assert len(flight_data["flights"]) > 0

    finally:
        proc.terminate()
        proc.wait(timeout=2)
