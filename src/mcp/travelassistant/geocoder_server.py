#!/usr/bin/env python3
import sys
import json
import math
from typing import Dict, Any

TOOLS_DEFINITIONS = [
    {
        "name": "geocode_location",
        "description": "Converts a location name or address into latitude and longitude coordinates via mcp_travelassistant geocoder.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "Location name (e.g. 'Banff, Alberta', 'Bali', 'Reston, Virginia')"}
            },
            "required": ["location"]
        }
    },
    {
        "name": "calculate_distance",
        "description": "Calculates the distance in kilometers and miles between two destinations for itinerary planning.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Origin location"},
                "destination": {"type": "string", "description": "Destination location"}
            },
            "required": ["origin", "destination"]
        }
    }
]

COORDINATE_DATABASE = {
    "banff": (51.1784, -115.5708, "Banff, Alberta, Canada"),
    "jasper": (52.8737, -118.0814, "Jasper, Alberta, Canada"),
    "calgary": (51.0447, -114.0719, "Calgary, Alberta, Canada"),
    "reston": (38.9687, -77.3411, "Reston, Virginia, USA"),
    "bali": (-8.4095, 115.1889, "Bali, Indonesia"),
    "tokyo": (35.6762, 139.6503, "Tokyo, Japan"),
    "singapore": (1.3521, 103.8198, "Singapore"),
    "paris": (48.8566, 2.3522, "Paris, France")
}

def geocode_handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
    loc = arguments.get("location", "").lower()
    for key, (lat, lon, full_name) in COORDINATE_DATABASE.items():
        if key in loc:
            return {
                "source": "mcp_travelassistant_geocoder",
                "query": loc,
                "display_name": full_name,
                "latitude": lat,
                "longitude": lon
            }
    # Generic fallback
    return {
        "source": "mcp_travelassistant_geocoder",
        "query": loc,
        "display_name": loc.title(),
        "latitude": 51.1784,
        "longitude": -115.5708
    }

def distance_handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
    orig = arguments.get("origin", "").lower()
    dest = arguments.get("destination", "").lower()

    orig_geo = geocode_handler({"location": orig})
    dest_geo = geocode_handler({"location": dest})

    lat1, lon1 = math.radians(orig_geo["latitude"]), math.radians(orig_geo["longitude"])
    lat2, lon2 = math.radians(dest_geo["latitude"]), math.radians(dest_geo["longitude"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    km = round(6371 * c, 1)
    miles = round(km * 0.621371, 1)

    return {
        "source": "mcp_travelassistant_geocoder",
        "origin": orig_geo["display_name"],
        "destination": dest_geo["display_name"],
        "distance_km": km,
        "distance_miles": miles,
        "approx_drive_time_hours": round(km / 90, 1) if km < 1000 else "Flight required"
    }

def handle_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "geocode_location":
        res = geocode_handler(arguments)
        return {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}
    elif name == "calculate_distance":
        res = distance_handler(arguments)
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
                    "serverInfo": {"name": "mcp-travelassistant-geocoder", "version": "1.0.0"},
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
