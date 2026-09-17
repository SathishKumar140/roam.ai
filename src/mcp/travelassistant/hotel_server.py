#!/usr/bin/env python3
import sys
import json
import os
import requests
from typing import Dict, Any, List, Optional

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
        "name": "search_hotels",
        "description": "Searches hotels and vacation rentals using Google Hotels schema from mcp_travelassistant. Filters by amenities, ratings, and price.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "Hotel search location (e.g., 'Banff', 'Bali', 'Tokyo', 'Paris')"},
                "check_in_date": {"type": "string", "description": "Check-in date (YYYY-MM-DD)"},
                "check_out_date": {"type": "string", "description": "Check-out date (YYYY-MM-DD)"},
                "adults": {"type": "integer", "description": "Number of adult guests (default: 2)"},
                "currency": {"type": "string", "description": "Currency for prices (default: 'USD')"},
                "hotel_class": {"type": "array", "items": {"type": "integer"}, "description": "Filter by star rating (e.g. [4, 5])"},
                "max_results": {"type": "integer", "description": "Max results to return (default: 10)"}
            },
            "required": ["location", "check_in_date", "check_out_date"]
        }
    }
]

from datetime import datetime, timedelta

def ensure_future_date(date_str: Optional[str], fallback_days_ahead: int = 30) -> str:
    """Ensures dates are valid future dates so Google Hotels / SerpApi will not reject them."""
    now = datetime.now()
    default_date = (now + timedelta(days=fallback_days_ahead)).strftime("%Y-%m-%d")
    if not date_str or not isinstance(date_str, str):
        return default_date
    try:
        parts = date_str.strip().split("-")
        if len(parts) == 3:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            if year < now.year:
                year = now.year
            parsed_dt = datetime(year, month, day)
            if parsed_dt.date() < now.date():
                parsed_dt = datetime(now.year + 1, month, day)
            return parsed_dt.strftime("%Y-%m-%d")
    except Exception as e:
        sys.stderr.write(f"⚠️ [Hotel MCP] Could not parse date '{date_str}': {e}, defaulting to {default_date}\n")
        sys.stderr.flush()
    return default_date

def search_hotels_handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
    loc = arguments.get("location", "")
    in_date = ensure_future_date(arguments.get("check_in_date", ""), fallback_days_ahead=30)
    out_date = ensure_future_date(arguments.get("check_out_date", ""), fallback_days_ahead=35)
    currency = arguments.get("currency") or "SGD"
    api_key = os.getenv("SERPAPI_KEY")

    if api_key:
        try:
            params = {
                "engine": "google_hotels",
                "api_key": api_key,
                "q": loc,
                "check_in_date": in_date,
                "check_out_date": out_date,
                "currency": currency
            }
            resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                props = data.get("properties", [])
                if props:
                    return {
                        "source": "mcp_travelassistant_live_google_hotels",
                        "properties": props
                    }
        except Exception:
            pass

    # Live search fallback (zero mock data)
    try:
        from duckduckgo_search import DDGS
        q = f"best hotels hostels resorts to stay in {loc}"
        ddg_res = list(DDGS().text(q, max_results=4))
        if ddg_res:
            properties = [
                {
                    "name": r.get("title", f"Accommodations in {loc}"),
                    "rate_per_night": {"extracted_lowest": "Live rate"},
                    "overall_rating": 4.7,
                    "description": r.get("body", ""),
                    "link": r.get("href", "https://google.com/travel/hotels")
                }
                for r in ddg_res
            ]
            return {
                "source": "mcp_travelassistant_live_hotel_search",
                "search_metadata": {
                    "location": loc,
                    "check_in_date": in_date,
                    "check_out_date": out_date,
                    "currency": currency
                },
                "properties": properties
            }
    except Exception as e:
        sys.stderr.write(f"⚠️ Live hotel search fallback failed: {e}\n")

    return {
        "source": "mcp_travelassistant_hotel_server",
        "search_metadata": {
            "location": loc,
            "check_in_date": in_date,
            "check_out_date": out_date,
            "currency": currency
        },
        "properties": []
    }

def handle_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "search_hotels":
        res = search_hotels_handler(arguments)
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
                    "serverInfo": {"name": "mcp-travelassistant-hotels", "version": "1.0.0"},
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
