import asyncio
import json
import os
import subprocess
import sys
import logging
from typing import Dict, Any, List, Optional
from langchain_core.tools import StructuredTool
from pydantic import create_model, Field

logger = logging.getLogger("roam.ai.mcp")

class MCPProcessConnection:
    """Manages a single MCP server running as a local subprocess over stdio."""
    def __init__(self, name: str, command: str, args: List[str]):
        self.name = name
        self.command = command
        self.args = args
        self.proc: Optional[subprocess.Popen] = None
        self.tools_cache: List[Dict[str, Any]] = []
        self._req_id = 0

    def start(self):
        env = os.environ.copy()
        # Ensure python unbuffered stdout and proper PYTHONPATH
        env["PYTHONUNBUFFERED"] = "1"
        cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        env["PYTHONPATH"] = cwd + (f":{env['PYTHONPATH']}" if "PYTHONPATH" in env else "")

        cmd = sys.executable if self.command in ("python3", "python") else self.command
        self.proc = subprocess.Popen(
            [cmd] + self.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,  # Stream server logs and errors straight to console/uvicorn
            text=True,
            bufsize=1,
            cwd=cwd,
            env=env
        )

        # 1. Initialize
        self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "ambient-mcp-client", "version": "1.0.0"}
        })
        init_res = self._read_response()

        # 2. Initialized notification
        self._send_notification("notifications/initialized", {})

        # 3. List tools
        self._send_request("tools/list", {})
        list_res = self._read_response()
        self.tools_cache = list_res.get("result", {}).get("tools", [])

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _send_request(self, method: str, params: Dict[str, Any]) -> int:
        req_id = self._next_id()
        msg = json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})
        if self.proc and self.proc.stdin:
            self.proc.stdin.write(msg + "\n")
            self.proc.stdin.flush()
        return req_id

    def _send_notification(self, method: str, params: Dict[str, Any]):
        msg = json.dumps({"jsonrpc": "2.0", "method": method, "params": params})
        if self.proc and self.proc.stdin:
            self.proc.stdin.write(msg + "\n")
            self.proc.stdin.flush()

    def _read_response(self) -> Dict[str, Any]:
        if not self.proc or not self.proc.stdout:
            return {}
        line = self.proc.stdout.readline()
        if not line:
            return {}
        return json.loads(line.strip())

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        formatted_args = json.dumps(arguments, indent=2)
        logger.info(f"\n==================== [MCP CALL: {self.name} -> {tool_name}] ====================\nArguments:\n{formatted_args}")
        self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        res = self._read_response()
        content = res.get("result", {}).get("content", [])
        if content and len(content) > 0:
            output_text = content[0].get("text", "")
            try:
                parsed = json.loads(output_text)
                pretty_output = json.dumps(parsed, indent=2)
            except Exception:
                pretty_output = output_text
            logger.info(f"\n==================== [MCP RESULT: {self.name} -> {tool_name}] ====================\nPayload ({len(output_text)} chars):\n{pretty_output}\n=======================================================================")
            return output_text
        out_json = json.dumps(res, indent=2)
        logger.info(f"\n==================== [MCP RESULT (RAW): {self.name} -> {tool_name}] ====================\n{out_json}\n=======================================================================")
        return out_json

    def close(self):
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except Exception:
                pass


class MCPClientManager:
    """
    Unified Multi-Server MCP Client that discovers tools from all registered
    MCP servers and exposes them as native LangChain tools.
    """
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "config.json")
        self.connections: Dict[str, MCPProcessConnection] = {}
        self.server_tools: Dict[str, List[StructuredTool]] = {}
        self._load_and_connect_servers()

    def _load_and_connect_servers(self):
        if not os.path.exists(self.config_path):
            return

        with open(self.config_path, "r") as f:
            config = json.load(f)

        for name, srv_conf in config.get("mcpServers", {}).items():
            if srv_conf.get("transport") == "stdio":
                self.connect_server(
                    name=name,
                    command=srv_conf.get("command", "python3"),
                    args=srv_conf.get("args", [])
                )

        # Ensure the travel_flights MCP server pointing to flight_server.py is connected
        if "travel_flights" not in self.connections:
            self.connect_server(
                name="travel_flights",
                command="python3",
                args=["-m", "src.mcp.travelassistant.flight_server"]
            )

    def connect_server(self, name: str, command: str, args: List[str]) -> List[StructuredTool]:
        """Connects to an MCP server, retrieves its tools, and wraps them for LangChain."""
        if name in self.connections:
            self.connections[name].close()

        conn = MCPProcessConnection(name, command, args)
        conn.start()
        self.connections[name] = conn

        # Convert discovered MCP tools to LangChain StructuredTool objects
        new_tools = []
        for tool_meta in conn.tools_cache:
            lc_tool = self._wrap_mcp_tool(conn, tool_meta)
            new_tools.append(lc_tool)

        self.server_tools[name] = new_tools
        return new_tools

    def _wrap_mcp_tool(self, conn: MCPProcessConnection, tool_meta: Dict[str, Any]) -> StructuredTool:
        tool_name = tool_meta["name"]
        description = tool_meta.get("description", f"MCP tool from {conn.name}")
        schema = tool_meta.get("inputSchema", {})

        # Dynamically construct Pydantic schema so LangChain passes arguments accurately
        fields = {}
        type_mapping = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict
        }
        required_set = set(schema.get("required", []))
        for prop_name, prop_info in schema.get("properties", {}).items():
            base_type = type_mapping.get(prop_info.get("type", "string"), Any)
            desc = prop_info.get("description", "")
            if prop_name in required_set:
                fields[prop_name] = (base_type, Field(..., description=desc))
            else:
                fields[prop_name] = (Optional[base_type], Field(default=None, description=desc))

        args_schema = create_model(f"{tool_name}_Args", **fields) if fields else None

        def _runner(**kwargs):
            logger.info(f"🛠️ [MCP Tool Invoked] Server '{conn.name}' -> Tool '{tool_name}' with args: {kwargs}")
            try:
                res = conn.call_tool(tool_name, kwargs)
                res_str = str(res)
                logger.info(f"✨ [MCP Tool Success] '{tool_name}' returned ({len(res_str)} chars). Preview: {res_str[:120].strip()}...")
                return res
            except Exception as e:
                logger.error(f"❌ [MCP Tool Error] '{tool_name}' failed: {e}")
                raise

        return StructuredTool.from_function(
            func=_runner,
            name=tool_name,
            description=f"[MCP:{conn.name}] {description}",
            args_schema=args_schema
        )

    def get_all_tools(self) -> List[StructuredTool]:
        all_tools = []
        for tools in self.server_tools.values():
            all_tools.extend(tools)
        return all_tools

    def get_travel_tools(self) -> List[StructuredTool]:
        """
        Returns unified live travel tools powered by SerpApi Google Flights, Google Hotels,
        Open-Meteo Weather, Local Events, and Currency conversion.
        """
        tools = []
        seen_names = set()

        # Add all specialized live travel assistant tools first
        for srv in ["travel_flights", "travel_hotels", "travel_events", "travel_weather", "travel_finance"]:
            for t in self.server_tools.get(srv, []):
                if t.name not in seen_names:
                    tools.append(t)
                    seen_names.add(t.name)

        # Other travel tools from travel server (e.g. generate_itinerary)
        for t in self.server_tools.get("travel", []):
            if t.name not in seen_names:
                tools.append(t)
                seen_names.add(t.name)

        return tools

    def get_tools_for_server(self, server_name: str) -> List[StructuredTool]:
        if server_name == "travel":
            return self.get_travel_tools()
        return self.server_tools.get(server_name, [])

    def shutdown(self):
        for conn in self.connections.values():
            conn.close()

# Global MCP Client Manager instance
mcp_manager = MCPClientManager()

