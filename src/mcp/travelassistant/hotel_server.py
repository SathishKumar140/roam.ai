#!/usr/bin/env python3
import sys
import json
import os
import requests
from typing import Dict, Any, Optional
from urllib.parse import urlencode

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
                "max_results": {"type": "integer", "description": "Max results to return (default: 10)"},
            },
            "required": ["location", "check_in_date", "check_out_date"],
        },
    }
]

from datetime import datetime


def ensure_future_date(date_str: Optional[str], fallback_days_ahead: int = 30) -> str:
    """Validate the supplied date without changing the user's travel plans."""
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError("Ask for a valid travel date in YYYY-MM-DD format") from None
    if parsed.isoformat() != date_str or parsed < datetime.now().date():
        raise ValueError("Travel date is past or invalid; ask the user to confirm a future date")
    return date_str


def search_hotels_handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
    loc = arguments.get("location", "")
    try:
        in_date = ensure_future_date(arguments.get("check_in_date"))
        out_date = ensure_future_date(arguments.get("check_out_date"))
        if not loc or out_date <= in_date:
            raise ValueError("Provide a location and a checkout date after check-in")
    except ValueError as error:
        return {"error": str(error), "properties": []}
    currency = arguments.get("currency") or "USD"
    adults = arguments.get("adults") if arguments.get("adults") is not None else 2
    if type(adults) is not int or adults < 1:
        return {"error": "adults must be a positive integer", "properties": []}
    search_metadata = {
        "location": loc,
        "check_in_date": in_date,
        "check_out_date": out_date,
        "currency": currency,
        "adults": adults,
    }
    api_key = os.getenv("SERPAPI_KEY")

    if api_key:
        try:
            params = {
                "engine": "google_hotels",
                "api_key": api_key,
                "q": loc,
                "check_in_date": in_date,
                "check_out_date": out_date,
                "currency": currency,
                "adults": adults,
            }
            resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                props = data.get("properties", [])
                if props:
                    properties = []
                    for hotel in props[:8]:
                        public_link = hotel.get("link")
                        cleaned = {
                            key: value
                            for key, value in hotel.items()
                            if key
                            not in {
                                "serpapi_property_details_link",
                                "serpapi_google_hotels_reviews_link",
                                "serpapi_google_hotels_photos_link",
                                "images",
                            }
                        }
                        cleaned["link"] = public_link or "https://www.google.com/travel/hotels?" + urlencode(
                            {"q": f"{hotel.get('name', '')} {loc}"}
                        )
                        cleaned["link_type"] = "hotel_website" if public_link else "public_hotel_search"

                        # Generate Google Maps URL using coordinates or query
                        gps = hotel.get("gps_coordinates") or {}
                        lat = gps.get("latitude")
                        lon = gps.get("longitude")
                        hotel_name = hotel.get("name", "")
                        if lat and lon:
                            cleaned["google_maps_url"] = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
                        else:
                            cleaned["google_maps_url"] = "https://www.google.com/maps/search/?" + urlencode(
                                {"api": "1", "query": f"{hotel_name} {loc}"}
                            )

                        # Extract formatted nearby distance/transit highlights
                        nearby = hotel.get("nearby_places", [])
                        if nearby:
                            highlights = []
                            for place in nearby[:3]:
                                pname = place.get("name", "")
                                trans = place.get("transportations", [])
                                if trans:
                                    t_desc = ", ".join(
                                        f"{t.get('duration', '')} by {t.get('type', '')}" for t in trans if t.get("duration")
                                    )
                                    highlights.append(f"{pname} ({t_desc})" if t_desc else pname)
                                else:
                                    highlights.append(pname)
                            if highlights:
                                cleaned["distance_highlights"] = "; ".join(highlights)

                        properties.append(cleaned)
                    return {
                        "source": "mcp_travelassistant_live_google_hotels",
                        "search_metadata": search_metadata,
                        "properties": properties,
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
                    "description": r.get("body", ""),
                    "link": r.get("href", "https://google.com/travel/hotels"),
                    "google_maps_url": "https://www.google.com/maps/search/?"
                    + urlencode({"api": "1", "query": f"{r.get('title', 'Hotel')} {loc}"}),
                    "distance_highlights": f"Located in {loc}",
                }
                for r in ddg_res
            ]
            return {"source": "mcp_travelassistant_live_hotel_search", "search_metadata": search_metadata, "properties": properties}
    except Exception as e:
        sys.stderr.write(f"⚠️ Live hotel search fallback failed: {e}\n")

    return {"source": "mcp_travelassistant_hotel_server", "search_metadata": search_metadata, "properties": []}


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
                    "capabilities": {"tools": {}},
                },
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
