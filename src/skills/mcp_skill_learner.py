import json
from typing import List, Dict, Any
from langchain_core.tools import tool
from src.mcp.client import mcp_manager
from src.storage.database import db

@tool
def connect_external_mcp_server(server_name: str, command: str, args_json: str = "[]") -> str:
    """
    Dynamically connects to a new Model Context Protocol (MCP) server.
    Learns and ingests all tools exposed by the server into the companion's capabilities.
    'args_json' is a JSON array string of arguments (e.g. '["-m", "my_mcp_server"]').
    """
    try:
        args = json.loads(args_json) if isinstance(args_json, str) else list(args_json)
    except Exception:
        args = []

    try:
        new_tools = mcp_manager.connect_server(server_name, command, args)
        tool_names = [t.name for t in new_tools]
        return (
            f"✅ Successfully connected to MCP Server '{server_name}'!\n"
            f"Learned {len(new_tools)} new skill(s):\n"
            + "\n".join([f"• `{name}`: {t.description}" for name, t in zip(tool_names, new_tools)])
        )
    except Exception as e:
        return f"❌ Failed to connect to MCP Server '{server_name}': {str(e)}"

@tool
def list_connected_mcp_skills() -> str:
    """
    Lists all currently connected MCP servers and the skills/tools they provide to the companion.
    """
    tools = mcp_manager.get_all_tools()
    if not tools:
        return "No MCP servers are currently connected."

    lines = [f"🔌 **Active MCP Servers & Learned Skills ({len(tools)} total tools)**:"]
    for t in tools:
        lines.append(f"• **`{t.name}`**: {t.description}")
    return "\n".join(lines)

@tool
def disconnect_mcp_server(server_name: str) -> str:
    """
    Disconnects an MCP server and removes its associated skills from the agent.
    """
    if server_name in mcp_manager.connections:
        mcp_manager.connections[server_name].close()
        del mcp_manager.connections[server_name]
        return f"Disconnected MCP server '{server_name}'."
    return f"MCP server '{server_name}' was not active."

skill_learner_tools = [connect_external_mcp_server, list_connected_mcp_skills, disconnect_mcp_server]
