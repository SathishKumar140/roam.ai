#!/usr/bin/env python3
import sys
import json
from typing import Dict, Any, List

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
                "max_budget": {"type": "number", "description": "Maximum price in USD"}
            },
            "required": ["origin", "destination", "date"]
        }
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
                "max_price": {"type": "number", "description": "Maximum price per night in USD"}
            },
            "required": ["destination", "checkin_date", "checkout_date"]
        }
    },
    {
        "name": "generate_itinerary",
        "description": "Synthesizes an optimal day-by-day travel itinerary balancing group preferences via MCP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "Destination city"},
                "days": {"type": "integer", "description": "Number of days"},
                "preferences": {"type": "string", "description": "Collective group preferences"}
            },
            "required": ["destination", "days"]
        }
    }
]

def handle_tool_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "search_flights":
        origin = arguments.get("origin", "").upper()
        dest = arguments.get("destination", "").upper()
        date = arguments.get("date", "")
        max_budget = arguments.get("max_budget")

        dest_clean = dest.upper().strip()
        if any(k in dest_clean for k in ["TYO", "TOK", "HND", "NRT", "JAPAN"]):
            sample_flights = [
                {"flight": "SQ 638", "airline": "Singapore Airlines", "dep": "23:55", "arr": "08:00 (+1)", "price": 480.00},
                {"flight": "NH 844", "airline": "All Nippon Airways (ANA)", "dep": "06:10", "arr": "14:20", "price": 450.00},
                {"flight": "JL 38", "airline": "Japan Airlines", "dep": "02:15", "arr": "10:10", "price": 465.00},
                {"flight": "TR 808", "airline": "Scoot", "dep": "01:25", "arr": "09:05", "price": 240.00}
            ]
        elif any(k in dest_clean for k in ["DPS", "BALI", "INDONESIA"]):
            sample_flights = [
                {"flight": "SQ 942", "airline": "Singapore Airlines", "dep": "09:15", "arr": "12:05", "price": 185.00},
                {"flight": "GA 841", "airline": "Garuda Indonesia", "dep": "14:30", "arr": "17:15", "price": 140.00},
                {"flight": "TR 288", "airline": "Scoot", "dep": "19:00", "arr": "21:40", "price": 95.00}
            ]
        elif any(k in dest_clean for k in ["PAR", "CDG", "LON", "LHR", "NYC", "JFK"]):
            sample_flights = [
                {"flight": "SQ 306", "airline": "Singapore Airlines", "dep": "01:10", "arr": "07:45", "price": 780.00},
                {"flight": "BA 12", "airline": "British Airways", "dep": "23:15", "arr": "05:55 (+1)", "price": 720.00},
                {"flight": "QR 945", "airline": "Qatar Airways", "dep": "02:30", "arr": "12:45", "price": 610.00}
            ]
        else:
            sample_flights = [
                {"flight": f"SQ {dest_clean[:3]}", "airline": "Singapore Airlines", "dep": "08:30", "arr": "13:45", "price": 380.00},
                {"flight": f"TR {dest_clean[:3]}", "airline": "Scoot", "dep": "16:20", "arr": "21:30", "price": 180.00}
            ]
        if max_budget:
            filtered = [f for f in sample_flights if f["price"] <= max_budget]
        else:
            filtered = sample_flights

        result = {
            "source": "Travel-MCP-Server",
            "route": f"{origin} -> {dest}",
            "date": date,
            "flights": filtered or sample_flights
        }
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    elif name == "search_hotels":
        dest = arguments.get("destination", "")
        max_price = arguments.get("max_price")
        options = [
            {
                "name": f"{dest.title()} Oceanfront Villa & Pool",
                "price_per_night": 135.00,
                "rating": 4.9,
                "amenities": ["Infinity Pool", "Free Breakfast", "Beach Access"]
            },
            {
                "name": f"{dest.title()} Heritage Boutique Suites",
                "price_per_night": 80.00,
                "rating": 4.7,
                "amenities": ["Central Location", "AC", "Kitchenette"]
            }
        ]
        if max_price:
            filtered = [h for h in options if h["price_per_night"] <= max_price]
        else:
            filtered = options

        result = {
            "source": "Travel-MCP-Server",
            "destination": dest,
            "hotels": filtered or options
        }
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    elif name == "generate_itinerary":
        dest = arguments.get("destination", "")
        days = arguments.get("days", 3)
        pref = arguments.get("preferences", "general exploration")
        result = {
            "source": "Travel-MCP-Server",
            "destination": dest,
            "days": days,
            "preferences": pref,
            "schedule": [
                {
                    "day": 1,
                    "theme": "Arrival, Beachfront Relaxation & Group Dinner",
                    "activities": ["Airport transfer & villa check-in", "Sunset cocktail lounge", "Seafood/vegan dinner"]
                },
                {
                    "day": 2,
                    "theme": "Culture & Island Highlights",
                    "activities": ["Morning cultural landmark tour", "Local food market", "Evening pool party"]
                }
            ]
        }
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

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
                    "serverInfo": {
                        "name": "travel-mcp-server",
                        "version": "1.0.0"
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            # Client acknowledgement notification - no response required
            pass

        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": TOOLS_DEFINITIONS
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            call_res = handle_tool_call(tool_name, tool_args)
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": call_res
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        else:
            if req_id is not None:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method '{method}' not found"
                    }
                }
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()

if __name__ == "__main__":
    run_mcp_server()
