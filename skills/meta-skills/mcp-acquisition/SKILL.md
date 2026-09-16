---
name: mcp-acquisition
description: Discovers, tests, and hot-loads external Model Context Protocol (MCP) servers into active skills
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: skill_specialist
allowed_tools:
  - learn_mcp_skill
  - list_learned_skills
---

# MCP Acquisition Skill

## Overview
Dynamically expands the agent's capabilities by connecting to external MCP servers at runtime, registering their JSON-RPC tools, and compiling standard SKILL.md records.

## When to Use
- When the user asks the agent to connect to an external MCP server or learn a new tool/capability.
- When querying currently loaded dynamic skills.

## Instructions
1. Extract server name, executable command, and command-line arguments.
2. Invoke `learn_mcp_skill(server_name, command, args)`.
3. Verify that the MCP handshake succeeds and tools are discovered.
4. Auto-generate a standardized `SKILL.md` file in the appropriate skill parent directory.
5. Notify the group that the new capability is immediately available without server restart.
