import sys
import json
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

TOOLS_DEFINITIONS = [
    {
        "name": "search_flights",
        "description": "Searches real-time flight options between origin and destination for a given date via MCP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Origin IATA code or city (e.g. SIN, NYC)"},
                "destination": {"type": "string", "description": "Destination IATA code or city (e.g. DPS, TYO)"},
                "date": {"type": "string", "description": "Flight departure date (YYYY-MM-DD)"},
                "max_budget": {"type": "number", "description": "Maximum price in USD"},
            },
            "required": ["origin", "destination", "date"],
        },
    },
    {
        "name": "search_hotels",
        "description": "Discovers lodging, private pool villas, and boutique hotels matching group budget via MCP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "Destination city or region"},
                "checkin_date": {"type": "string", "description": "Check-in date (YYYY-MM-DD)"},
                "checkout_date": {"type": "string", "description": "Check-out date (YYYY-MM-DD)"},
                "max_price": {"type": "number", "description": "Maximum price per night in USD"},
            },
            "required": ["destination", "checkin_date", "checkout_date"],
        },
    },
    {
        "name": "generate_itinerary",
        "description": "Synthesizes an optimal day-by-day travel itinerary balancing group preferences via MCP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "Destination city"},
                "days": {"type": "integer", "description": "Number of days"},
                "preferences": {"type": "string", "description": "Collective group preferences"},
            },
            "required": ["destination", "days"],
        },
    },
]


def handle_tool_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "search_flights":
        origin = arguments.get("origin", "")
        dest = arguments.get("destination", "")
        date = arguments.get("date", "")
        try:
            from src.mcp.travelassistant.flight_server import search_flights_handler

            res = search_flights_handler(
                {"departure_id": origin, "arrival_id": dest, "outbound_date": date, "currency": arguments.get("currency") or "SGD"}
            )
            res["source"] = "Travel-MCP-Server"
            if "flights" not in res or not res["flights"]:
                res["flights"] = res.get("best_flights") or res.get("other_flights") or []
            return {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}
        except Exception as e:
            fallback = {"source": "Travel-MCP-Server", "route": f"{origin}->{dest}", "date": date, "flights": [], "error": str(e)}
            return {"content": [{"type": "text", "text": json.dumps(fallback)}]}

    elif name == "search_hotels":
        dest = arguments.get("destination", "")
        checkin = arguments.get("checkin_date", "")
        checkout = arguments.get("checkout_date", "")
        try:
            from src.mcp.travelassistant.hotel_server import search_hotels_handler

            res = search_hotels_handler(
                {"location": dest, "check_in_date": checkin, "check_out_date": checkout, "currency": arguments.get("currency") or "SGD"}
            )
            return {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": json.dumps({"source": "travel_mcp", "destination": dest, "error": str(e)})}]}

    elif name == "generate_itinerary":
        dest = arguments.get("destination", "")
        days = arguments.get("days", 3)
        pref = arguments.get("preferences", "")
        try:
            from duckduckgo_search import DDGS

            q = f"best {days} day itinerary route attractions {dest} {pref}".strip()
            results = list(DDGS().text(q, max_results=4))
            res = {
                "source": "Travel-MCP-Server-Live",
                "destination": dest,
                "days": days,
                "highlights": [{"title": r.get("title"), "snippet": r.get("body"), "link": r.get("href")} for r in results],
            }
            return {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": json.dumps({"source": "travel_mcp", "destination": dest, "error": str(e)})}]}

    else:
        return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {name}"}]}


def run_mcp_server():
    """Main loop handling MCP JSON-RPC 2.0 requests over stdio."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except Exception:
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "travel-mcp-server", "version": "1.0.0"},
                    "capabilities": {"tools": {}},
                },
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            # Client acknowledgement notification - no response required
            pass

        elif method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS_DEFINITIONS}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            call_res = handle_tool_call(tool_name, tool_args)
            resp = {"jsonrpc": "2.0", "id": req_id, "result": call_res}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        else:
            if req_id is not None:
                resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method '{method}' not found"}}
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    run_mcp_server()
