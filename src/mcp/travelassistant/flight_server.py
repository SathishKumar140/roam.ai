#!/usr/bin/env python3
import sys
import json
import os
import requests
import re
from typing import Dict, Any, Optional

# Inject system truststore for SSL verification through enterprise proxies (e.g. Zscaler)
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:
    pass

# Load environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

CITY_TO_IATA = {
    "SINGAPORE": "SIN",
    "TOKYO": "HND",
    "TYO": "HND",
    "HANEDA": "HND",
    "NARITA": "NRT",
    "BALI": "DPS",
    "DENPASAR": "DPS",
    "BANGKOK": "BKK",
    "KUALA LUMPUR": "KUL",
    "LONDON": "LHR",
    "PARIS": "CDG",
    "NEW YORK": "JFK",
    "NYC": "JFK",
    "LOS ANGELES": "LAX",
    "SAN FRANCISCO": "SFO",
    "SEOUL": "ICN",
    "SYDNEY": "SYD",
    "HONG KONG": "HKG",
    "DUBAI": "DXB",
    "OSAKA": "KIX",
    "BLR": "BLR",
    "BANGALORE": "BLR",
    "BENGALURU": "BLR",
    "DELHI": "DEL",
    "NEW DELHI": "DEL",
    "DEL": "DEL",
    "MUMBAI": "BOM",
    "BOM": "BOM",
    "CHENNAI": "MAA",
    "MAA": "MAA",
    "HYDERABAD": "HYD",
    "KOLKATA": "CCU",
    "CCU": "CCU",
    "HANOI": "HAN",
    "HAN": "HAN",
    "HO CHI MINH": "SGN",
    "SAIGON": "SGN",
    "SGN": "SGN",
    "DA NANG": "DAD",
    "DAD": "DAD",
    "VIETNAM": "HAN",
    "HA GIANG": "HAN",
    "GIANG LOOP": "HAN",
    "PHUKET": "HKT",
    "HKT": "HKT",
}

from datetime import datetime, timedelta


def ensure_future_date(date_str: Optional[str], fallback_days_ahead: int = 30) -> str:
    """Validate the supplied date without changing the user's travel plans."""
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError("Ask for a valid travel date in YYYY-MM-DD format") from None
    if parsed.isoformat() != date_str or parsed < datetime.now().date():
        raise ValueError("Travel date is past or invalid; ask the user to confirm a future date")
    return date_str


TOOLS_DEFINITIONS = [
    {
        "name": "search_flights",
        "description": "Searches real-time live flights using Google Flights engine (via SerpApi). Returns live pricing, airlines, schedules, and flight numbers for specific departure/return dates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "departure_id": {"type": "string", "description": "Departure airport or city code (e.g. 'SIN', 'LAX', 'JFK', 'Singapore')"},
                "arrival_id": {"type": "string", "description": "Arrival airport or city code (e.g. 'TYO', 'DPS', 'BLR', 'Tokyo')"},
                "outbound_date": {"type": "string", "description": "Departure date in YYYY-MM-DD format (e.g. '2026-10-15')"},
                "origin": {"type": "string", "description": "Alias for departure_id"},
                "destination": {"type": "string", "description": "Alias for arrival_id"},
                "date": {"type": "string", "description": "Alias for outbound_date"},
                "return_date": {"type": "string", "description": "Return date in YYYY-MM-DD format (optional)"},
                "adults": {"type": "integer", "description": "Number of adult travelers (default: 1); use the confirmed trip participants"},
                "currency": {"type": "string", "description": "Currency code (default: 'USD')"},
            },
            "required": [],
        },
    },
    {
        "name": "search_cheapest_flights_in_month",
        "description": "Samples up to four departure windows in an explicitly supplied month and year using Google Flights. Reports the lowest returned fare among those samples, not a guaranteed monthly minimum.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "departure_id": {"type": "string", "description": "Departure airport or city (e.g. 'SIN', 'BLR', 'Singapore')"},
                "arrival_id": {"type": "string", "description": "Arrival airport or city (e.g. 'TYO', 'HND', 'Tokyo')"},
                "month": {"type": "string", "description": "Target month in YYYY-MM format (e.g. '2026-10') or name (e.g. 'October 2026')"},
                "duration_days": {"type": "integer", "description": "Trip duration in days (default: 5)"},
                "adults": {"type": "integer", "description": "Confirmed number of adult travelers (default: 1)"},
                "origin": {"type": "string", "description": "Alias for departure_id"},
                "destination": {"type": "string", "description": "Alias for arrival_id"},
                "currency": {"type": "string", "description": "Currency code (default: 'USD')"},
            },
            "required": [],
        },
    },
]


def normalize_airport(val: str) -> str:
    cleaned = (val or "").strip().upper()
    if cleaned in CITY_TO_IATA:
        return CITY_TO_IATA[cleaned]
    match = re.fullmatch(r"(.+?)\s*\(([A-Z]{3})\)", cleaned)
    if match and CITY_TO_IATA.get(match[1], match[2]) == match[2]:
        return match[2]
    return cleaned


def parse_serpapi_flights(raw_list: list) -> list:
    results = []
    for item in raw_list[:6]:
        legs = item.get("flights", [])
        if not legs:
            continue
        first_leg = legs[0]
        last_leg = legs[-1]

        airline = first_leg.get("airline", "Airline")
        flight_num = first_leg.get("flight_number", "")
        dep_time = first_leg.get("departure_airport", {}).get("time", "")
        arr_time = last_leg.get("arrival_airport", {}).get("time", "")
        price = item.get("price")
        total_duration = item.get("total_duration")

        results.append(
            {
                "flight": flight_num or airline,
                "airline": airline,
                "departure": dep_time,
                "arrival": arr_time,
                "duration_minutes": total_duration,
                "price": price,
                "stops": len(legs) - 1,
            }
        )
    return results


def search_flights_handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
    dep_raw = arguments.get("departure_id") or arguments.get("origin")
    arr_raw = arguments.get("arrival_id") or arguments.get("destination")
    raw_date = arguments.get("outbound_date") or arguments.get("date")
    if not dep_raw or not arr_raw or not raw_date:
        return {"error": "Ask for departure, destination and departure date before searching", "best_flights": [], "flights": []}
    adults = arguments.get("adults") if arguments.get("adults") is not None else 1
    if type(adults) is not int or adults < 1:
        return {"error": "adults must be a positive integer", "best_flights": [], "flights": []}
    ret_date_raw = arguments.get("return_date")
    try:
        date = ensure_future_date(raw_date)
        ret_date = ensure_future_date(ret_date_raw) if ret_date_raw else None
        if ret_date and ret_date < date:
            raise ValueError("Return date must not precede departure; ask the user to clarify")
    except ValueError as error:
        return {"error": str(error), "best_flights": [], "flights": []}
    currency = arguments.get("currency") or "USD"
    api_key = os.getenv("SERPAPI_KEY")

    dep = normalize_airport(dep_raw)
    arr = normalize_airport(arr_raw)

    if api_key and api_key.strip():
        try:
            sys.stderr.write(f"✈️ [Live Google Flights] Querying SerpApi for {dep} -> {arr} on {date} (type={1 if ret_date else 2})...\n")
            sys.stderr.flush()
            params = {
                "engine": "google_flights",
                "api_key": api_key.strip(),
                "departure_id": dep,
                "arrival_id": arr,
                "outbound_date": date,
                "type": 1 if ret_date else 2,
                "currency": currency,
                "adults": adults,
                "hl": "en",
            }
            if ret_date:
                params["return_date"] = ret_date

            resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                best = parse_serpapi_flights(data.get("best_flights", []))
                other = parse_serpapi_flights(data.get("other_flights", []))
                all_flights = best or other

                sys.stderr.write(f"✅ [Live Google Flights] Successfully fetched {len(all_flights)} live options from Google Flights.\n")
                sys.stderr.flush()
                return {
                    "source": "mcp_travelassistant_live_google_flights",
                    "route": f"{dep} -> {arr}",
                    "date": date,
                    "return_date": ret_date,
                    "adults": adults,
                    "currency": currency,
                    "link": data.get("search_metadata", {}).get("google_flights_url"),
                    "price_insights": data.get("price_insights", {}),
                    "best_flights": best,
                    "other_flights": other,
                    "flights": all_flights,
                }
            else:
                sys.stderr.write(f"⚠️ [Live Google Flights] SerpApi HTTP {resp.status_code}: {resp.text[:150]}\n")
                sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f"⚠️ [Live Google Flights] SerpApi request failed: {e}\n")
            sys.stderr.flush()

    # Live search fallback (zero mock data)
    try:
        from duckduckgo_search import DDGS

        q = f"flights from {dep} to {arr} {date}"
        ddg_res = list(DDGS().text(q, max_results=3))
        if ddg_res:
            flights = [
                {
                    "flight": r.get("title", f"Flight {dep}->{arr}"),
                    "airline": r.get("title", "").split("-")[0].strip() if "-" in r.get("title", "") else "Scheduled Airline",
                    "dep": "See live link",
                    "arr": "See live link",
                    "price": "Live market rate",
                    "link": r.get("href", ""),
                }
                for r in ddg_res
            ]
            return {
                "source": "mcp_travelassistant_live_flights_search",
                "route": f"{dep} -> {arr}",
                "date": date,
                "currency": currency,
                "best_flights": flights,
                "flights": flights,
            }
    except Exception as e:
        sys.stderr.write(f"⚠️ Live flight search fallback failed: {e}\n")

    return {
        "source": "mcp_travelassistant_flight_server",
        "route": f"{dep} -> {arr}",
        "date": date,
        "currency": currency,
        "best_flights": [],
        "flights": [],
        "message": f"No live flights found for route {dep} -> {arr} on {date}. Please verify airport codes or try alternative dates.",
    }


def search_cheapest_flights_in_month_handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
    import calendar
    from concurrent.futures import ThreadPoolExecutor

    dep_raw = arguments.get("departure_id") or arguments.get("origin")
    arr_raw = arguments.get("arrival_id") or arguments.get("destination")
    if not dep_raw or not arr_raw:
        return {"error": "Ask for departure and destination before searching", "best_flights": [], "flights": []}
    month_raw = str(arguments.get("month") or "").lower()
    duration = arguments.get("duration_days", 5)
    adults = arguments.get("adults", 1)
    if type(duration) is not int or not 1 <= duration <= 28 or type(adults) is not int or adults < 1:
        return {"error": "Confirm a trip duration of 1-28 days and a positive adult count", "best_flights": [], "flights": []}
    currency = arguments.get("currency") or "USD"
    api_key = os.getenv("SERPAPI_KEY")

    dep = normalize_airport(dep_raw)
    arr = normalize_airport(arr_raw)

    now = datetime.now()
    parsed_month = None
    for date_format in ("%Y-%m", "%B %Y"):
        try:
            parsed_month = datetime.strptime(month_raw, date_format)
            break
        except ValueError:
            pass
    if parsed_month is None or (parsed_month.year, parsed_month.month) < (now.year, now.month):
        return {"error": "Ask for a future travel month with explicit year (YYYY-MM)", "best_flights": [], "flights": []}
    target_year, target_month = parsed_month.year, parsed_month.month

    _, num_days = calendar.monthrange(target_year, target_month)

    first_day = now.day if (target_year, target_month) == (now.year, now.month) else 1
    start_days = sorted({first_day + (num_days - first_day) * index // 3 for index in range(4)})

    candidate_windows = []
    for d in start_days:
        out_d = datetime(target_year, target_month, d)
        ret_d = out_d + timedelta(days=duration)
        candidate_windows.append((out_d.strftime("%Y-%m-%d"), ret_d.strftime("%Y-%m-%d")))

    sys.stderr.write(
        f"🔍 [Flight MCP] Scanning {len(candidate_windows)} travel windows across {target_year}-{target_month:02d} for {dep}->{arr} ({duration} days)...\n"
    )
    sys.stderr.flush()

    def check_window(window):
        dep_date, ret_date = window
        if not api_key:
            return None
        try:
            params = {
                "engine": "google_flights",
                "api_key": api_key.strip(),
                "departure_id": dep,
                "arrival_id": arr,
                "outbound_date": dep_date,
                "return_date": ret_date,
                "type": 1,
                "currency": currency,
                "adults": adults,
                "hl": "en",
            }
            resp = requests.get("https://serpapi.com/search", params=params, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                best = parse_serpapi_flights(data.get("best_flights", []))
                other = parse_serpapi_flights(data.get("other_flights", []))
                all_f = best or other
                lowest = all_f[0].get("price") if all_f else None
                return {
                    "departure_date": dep_date,
                    "return_date": ret_date,
                    "lowest_price": lowest,
                    "flights": all_f,
                    "top_flight": all_f[0] if all_f else None,
                }
        except Exception as e:
            sys.stderr.write(f"⚠️ [Flight MCP] Window {dep_date}->{ret_date} failed: {e}\n")
            sys.stderr.flush()
        return None

    windows_results = []
    if api_key and api_key.strip():
        with ThreadPoolExecutor(max_workers=min(4, len(candidate_windows))) as ex:
            windows_results = [r for r in ex.map(check_window, candidate_windows) if r and r.get("lowest_price")]

    if windows_results:
        windows_results.sort(key=lambda x: x["lowest_price"] or 999999)
        best_window = windows_results[0]

        summary_windows = [
            {
                "dates": f"{w['departure_date']} to {w['return_date']}",
                "lowest_price": f"{currency} {w['lowest_price']}",
                "airline": w["top_flight"]["airline"] if w.get("top_flight") else "Unknown",
                "is_cheapest": (w == best_window),
            }
            for w in windows_results
        ]

        sys.stderr.write(
            f"✅ [Flight MCP] Found cheapest travel window: {best_window['departure_date']} to {best_window['return_date']} at {currency} {best_window['lowest_price']}\n"
        )
        sys.stderr.flush()

        return {
            "source": "mcp_travelassistant_live_google_flights_month_scanner",
            "route": f"{dep} -> {arr}",
            "month": f"{target_year}-{target_month:02d}",
            "trip_duration_days": duration,
            "adults": adults,
            "search_scope": "Lowest fare among sampled windows, not an exhaustive monthly minimum",
            "recommended_cheapest_dates": {
                "departure_date": best_window["departure_date"],
                "return_date": best_window["return_date"],
                "lowest_price": best_window["lowest_price"],
                "currency": currency,
            },
            "tested_date_windows": summary_windows,
            "best_flights_for_recommended_dates": best_window["flights"],
        }

    return {
        "source": "mcp_travelassistant_flight_server",
        "route": f"{dep} -> {arr}",
        "month": f"{target_year}-{target_month:02d}",
        "trip_duration_days": duration,
        "adults": adults,
        "status": "unavailable",
        "message": "No live fares were returned; no cheapest dates or price can be recommended.",
        "recommended_cheapest_dates": None,
        "tested_date_windows": [],
        "best_flights_for_recommended_dates": [],
    }


def handle_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "search_flights":
        # If no specific date was given, or duration_days was provided without explicit date, route to month scanner
        if not arguments.get("outbound_date") and not arguments.get("date") and arguments.get("duration_days"):
            res = search_cheapest_flights_in_month_handler(arguments)
        else:
            res = search_flights_handler(arguments)
        return {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}
    elif name == "search_cheapest_flights_in_month":
        res = search_cheapest_flights_in_month_handler(arguments)
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
                    "serverInfo": {"name": "mcp-travelassistant-flights", "version": "1.0.0"},
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
