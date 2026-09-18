#!/usr/bin/env python3
import sys
import json
import os
import requests
from datetime import datetime, timezone
from typing import Dict, Any, Optional

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


TOOLS_DEFINITIONS = [
    {
        "name": "search_events",
        "description": "Searches local events, festivals, concerts, and cultural activities for a destination via mcp_travelassistant.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for events (e.g., 'hiking', 'festivals', 'live music', 'food market')"},
                "location": {"type": "string", "description": "Destination city (e.g., 'Banff', 'Bali', 'Tokyo')"},
                "date_filter": {"type": "string", "description": "Optional date filter (e.g., 'today', 'this_weekend', 'next_month')"}
            },
            "required": ["query", "location"]
        }
    }
]

def search_events_handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
    query = arguments.get("query") or ""
    loc = arguments.get("location") or ""
    date_filter = arguments.get("date_filter") or "upcoming"
    api_key = os.getenv("SERPAPI_KEY") or os.getenv("SERP_API_KEY")
    result = {"source": "serpapi_google_events", "query": query, "location": loc,
              "date_filter": date_filter, "events_results": [],
              "retrieved_at": datetime.now(timezone.utc).isoformat()}
    filters = {"upcoming": None, "today": "today", "tomorrow": "tomorrow", "this_week": "week",
               "this_weekend": "weekend", "next_week": "next_week",
               "this_month": "month", "next_month": "next_month"}
    if date_filter not in filters:
        return result | {"status": "unavailable", "error": "Unsupported date filter; use " + ", ".join(filters)}
    if not query.strip() or not loc.strip():
        return result | {"status": "unavailable", "error": "A query and confirmed location are required"}
    if not api_key:
        return result | {"status": "unavailable", "error": "Event search is not configured"}
    params = {"engine": "google_events", "api_key": api_key, "q": f"{query} in {loc}"}
    if filters[date_filter]:
        params["htichips"] = "date:" + filters[date_filter]
    try:
        response = requests.get("https://serpapi.com/search", params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            return result | {"status": "unavailable", "error": "Event provider returned an error"}
        events = data.get("events_results", [])
        return result | {"status": "ok" if events else "empty", "events_results": events}
    except (requests.RequestException, ValueError):
        return result | {"status": "unavailable", "error": "Live event search failed; no events have been verified"}

def handle_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "search_events":
        res = search_events_handler(arguments)
        return {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}
    return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {name}"}]}

def run_server():
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
                    "serverInfo": {"name": "mcp-travelassistant-events", "version": "1.0.0"},
                    "capabilities": {"tools": {}}
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        elif method == "notifications/initialized":
            pass
        elif method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS_DEFINITIONS}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        elif method == "tools/call":
            call_res = handle_call(params.get("name"), params.get("arguments", {}))
            resp = {"jsonrpc": "2.0", "id": req_id, "result": call_res}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    run_server()
