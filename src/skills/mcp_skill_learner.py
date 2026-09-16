import json
import re
from pathlib import Path
from typing import List, Dict, Any
from langchain_core.tools import tool
from src.mcp.client import mcp_manager
from src.storage.database import db

def create_mcp_skill_folder(server_name: str, new_tools: list) -> Path:
    """
    Creates a standardized DeepAgents skill folder with SKILL.md for a newly learned MCP server.
    """
    clean_name = re.sub(r"[^a-z0-9-]", "-", f"mcp-{server_name.lower()}").strip("-")
    clean_name = re.sub(r"-+", "-", clean_name)[:64]
    
    skill_dir = Path("skills/meta-skills") / clean_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    
    tool_names = [t.name for t in new_tools]
    tool_lines = "\n".join([f"  - {t}" for t in tool_names])
    tool_descriptions = "\n".join([f"- **`{t.name}`**: {t.description}" for t in new_tools])
    
    content = f"""---
name: {clean_name}
description: Dynamically learned capabilities from MCP server '{server_name}'
license: MIT
compatibility: Python 3.10+
metadata:
  server_name: {server_name}
allowed_tools:
{tool_lines}
---

# {server_name.title()} MCP Skill

## Overview
Dynamic capabilities provided by the external Model Context Protocol (MCP) server `{server_name}`.

## Tools Available
{tool_descriptions}

## Usage
Invoke the respective tools above when a user request matches this server's domain.
"""
    skill_md.write_text(content, encoding="utf-8")
    return skill_md

@tool
def connect_external_mcp_server(server_name: str, command: str, args_json: str = "[]") -> str:
    """
    Dynamically connects to a new Model Context Protocol (MCP) server.
    Learns and ingests all tools exposed by the server into the companion's capabilities
    and registers a standardized SKILL.md skill folder.
    'args_json' is a JSON array string of arguments (e.g. '["-m", "my_mcp_server"]').
    """
    try:
        args = json.loads(args_json) if isinstance(args_json, str) else list(args_json)
    except Exception:
        args = []

    try:
        new_tools = mcp_manager.connect_server(server_name, command, args)
        tool_names = [t.name for t in new_tools]
        skill_file = create_mcp_skill_folder(server_name, new_tools)
        return (
            f"✅ Successfully connected to MCP Server '{server_name}'!\n"
            f"Registered standard skill at: `{skill_file}`\n"
            f"Learned {len(new_tools)} new tool(s):\n"
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
