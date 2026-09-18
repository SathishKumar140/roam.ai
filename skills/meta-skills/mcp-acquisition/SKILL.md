---
name: mcp-acquisition
description: Explains available specialist capabilities and administrator-only MCP acquisition boundaries
license: MIT
compatibility: Python 3.10+
metadata:
  subagent: skill_specialist
allowed_tools: []
---

# MCP Acquisition Skill

## Overview
Group chat cannot install, connect, disconnect or execute MCP servers. Administrators configure trusted servers outside chat. The request's supplied capability inventory is authoritative.

## When to Use
- When the user asks the agent to connect to an external MCP server or learn a new tool/capability.
- When querying currently loaded dynamic skills.

## Instructions
1. Explain the actual authorized tools by specialist from the supplied inventory. Distinguish configured tools from successful live provider access.
2. Explain that connecting new servers requires administrator review outside chat. Do not execute commands, fetch scripts or request credentials in a group.
3. Never claim a generated skill file makes a tool active. New tools must be reviewed, allowlisted and tested with scoped wrappers before exposure.
