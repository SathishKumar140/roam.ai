import json
from src.mcp.client import mcp_manager

def test_travelassistant_mcp_servers_loaded():
    """Verifies that all 6 servers from skarlekar/mcp_travelassistant are connected and active."""
    tools = mcp_manager.get_all_tools()
    tool_names = [t.name for t in tools]

    # Verify all tools across the 6 servers are exposed
    assert "search_flights" in tool_names
    assert "search_hotels" in tool_names
    assert "get_weather_forecast" in tool_names
    assert "geocode_location" in tool_names
    assert "calculate_distance" in tool_names
    assert "convert_currency" in tool_names
    assert "search_events" in tool_names

def test_travelassistant_geocoder():
    """Tests the Geocoder and Distance tools."""
    geo_tool = next(t for t in mcp_manager.get_all_tools() if t.name == "geocode_location")
    dist_tool = next(t for t in mcp_manager.get_all_tools() if t.name == "calculate_distance")

    geo_res = json.loads(geo_tool.invoke({"location": "Banff, Alberta"}))
    assert geo_res["source"] == "mcp_travelassistant_geocoder"
    assert "latitude" in geo_res
    assert "longitude" in geo_res

    dist_res = json.loads(dist_tool.invoke({"origin": "Reston, Virginia", "destination": "Banff, Alberta"}))
    assert dist_res["source"] == "mcp_travelassistant_geocoder"
    assert dist_res["distance_km"] > 0

def test_travelassistant_weather():
    """Tests the Weather forecast tool."""
    weather_tool = next(t for t in mcp_manager.get_all_tools() if t.name == "get_weather_forecast")
    res = json.loads(weather_tool.invoke({"destination": "Banff"}))
    assert "current" in res
    assert "temperature" in res["current"]
    assert "forecast_summary" in res

def test_travelassistant_finance():
    """Tests currency conversion tool converting CAD to USD as in the Banff example."""
    finance_tool = next(t for t in mcp_manager.get_all_tools() if t.name == "convert_currency")
    res = json.loads(finance_tool.invoke({"from_currency": "CAD", "to_currency": "USD", "amount": 5000.0}))
    assert res["source"] == "mcp_travelassistant_finance_server"
    assert res["from_currency"] == "CAD"
    assert res["to_currency"] == "USD"
    assert res["converted_amount"] > 0

def test_travelassistant_events():
    """Tests event discovery for Banff."""
    event_tool = next(t for t in mcp_manager.get_all_tools() if t.name == "search_events")
    res = json.loads(event_tool.invoke({"query": "hiking & cultural festivals", "location": "Banff"}))
    assert res["source"] == "mcp_travelassistant_event_server"
    assert len(res["events"]) > 0

def test_travelassistant_flights_and_hotels():
    """Tests Google Flights and Google Hotels schema tools from mcp_travelassistant."""
    flight_tool = next(t for t in mcp_manager.get_tools_for_server("travel_flights") if t.name == "search_flights")
    hotel_tool = next(t for t in mcp_manager.get_tools_for_server("travel_hotels") if t.name == "search_hotels")

    f_res = json.loads(flight_tool.invoke({
        "departure_id": "IAD",
        "arrival_id": "YYC",
        "outbound_date": "2025-06-07"
    }))
    assert len(f_res["best_flights"]) > 0

    h_res = json.loads(hotel_tool.invoke({
        "location": "Banff",
        "check_in_date": "2025-06-07",
        "check_out_date": "2025-06-14"
    }))
    assert len(h_res["properties"]) > 0
