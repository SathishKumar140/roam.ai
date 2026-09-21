import json
import pytest
from src.mcp.client import mcp_manager


def test_hotel_search_preserves_traveler_count_dates_and_currency(monkeypatch):
    from datetime import date, timedelta
    from unittest.mock import Mock
    from src.mcp.travelassistant import hotel_server

    monkeypatch.setenv("SERPAPI_KEY", "test-key")
    response = Mock(status_code=200)
    response.json.return_value = {
        "properties": [
            {
                "name": "Provider hotel",
                "link": "https://example.com/hotel",
                "images": [{"thumbnail": "https://images.example.com/hotel.jpg"}],
                "gps_coordinates": {"latitude": 35.0, "longitude": 139.0},
                "serpapi_property_details_link": "https://serpapi.com/search.json?property_token=private",
            },
            {"name": "Search-only hotel", "serpapi_property_details_link": "https://serpapi.com/search.json?property_token=other"},
        ]
    }
    request = Mock(return_value=response)
    monkeypatch.setattr(hotel_server.requests, "get", request)
    check_in = (date.today() + timedelta(days=30)).isoformat()
    check_out = (date.today() + timedelta(days=33)).isoformat()
    result = hotel_server.search_hotels_handler(
        {
            "location": "Louvre, Paris",
            "check_in_date": check_in,
            "check_out_date": check_out,
            "adults": 1,
            "currency": "EUR",
        }
    )
    params = request.call_args.kwargs["params"]
    assert params["adults"] == 1
    assert params["currency"] == "EUR"
    assert params["check_in_date"] == check_in
    assert params["check_out_date"] == check_out
    assert result["search_metadata"]["adults"] == 1
    assert result["properties"][0]["link"] == "https://example.com/hotel"
    assert result["properties"][0]["link_type"] == "hotel_website"
    assert result["properties"][0]["image_url"] == "https://images.example.com/hotel.jpg"
    assert result["properties"][0]["google_maps_url"].startswith("https://www.google.com/maps/search/?api=1&query=Provider+hotel%2C+")
    assert result["properties"][1]["link"].startswith("https://www.google.com/travel/hotels?q=")
    assert result["properties"][1]["link_type"] == "public_hotel_search"
    assert all("serpapi_property_details_link" not in hotel for hotel in result["properties"])


def test_hotel_search_rejects_invalid_occupancy(monkeypatch):
    from unittest.mock import Mock
    from src.mcp.travelassistant import hotel_server

    request = Mock()
    monkeypatch.setattr(hotel_server.requests, "get", request)
    result = hotel_server.search_hotels_handler({"location": "Paris", "adults": 0})
    assert result["error"] and result["properties"] == []
    request.assert_not_called()


def test_flight_search_does_not_guess_route_and_preserves_travelers(monkeypatch):
    from datetime import date, timedelta
    from unittest.mock import Mock
    from src.mcp.travelassistant import flight_server

    request = Mock()
    monkeypatch.setattr(flight_server.requests, "get", request)
    assert flight_server.search_flights_handler({"arrival_id": "HND"})["error"]
    assert flight_server.search_cheapest_flights_in_month_handler({"arrival_id": "HND"})["error"]
    request.assert_not_called()
    monkeypatch.setenv("SERPAPI_KEY", "test-key")
    response = Mock(status_code=200)
    response.json.return_value = {"best_flights": [], "search_metadata": {"google_flights_url": "https://www.google.com/travel/flights"}}
    request.return_value = response
    outbound = (date.today() + timedelta(days=30)).isoformat()
    returning = (date.today() + timedelta(days=33)).isoformat()
    result = flight_server.search_flights_handler(
        {"departure_id": "MAA", "arrival_id": "HND", "outbound_date": outbound, "return_date": returning, "adults": 2, "currency": "USD"}
    )
    params = request.call_args.kwargs["params"]
    assert (params["departure_id"], params["arrival_id"], params["adults"], params["currency"]) == ("MAA", "HND", 2, "USD")
    assert (params["outbound_date"], params["return_date"], params["type"]) == (outbound, returning, 1)
    assert result["adults"] == 2 and result["return_date"] == returning


@pytest.mark.parametrize("month", ["", "2000-01", "2030-13", "October"])
def test_monthly_flights_require_explicit_valid_future_month(monkeypatch, month):
    from unittest.mock import Mock
    from src.mcp.travelassistant import flight_server

    request = Mock()
    monkeypatch.setattr(flight_server.requests, "get", request)
    assert flight_server.search_cheapest_flights_in_month_handler({"departure_id": "MAA", "arrival_id": "HND", "month": month})["error"]
    request.assert_not_called()


def test_monthly_flights_never_fabricate_fallback_fares(monkeypatch):
    from datetime import date
    from src.mcp.travelassistant import flight_server

    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    result = flight_server.search_cheapest_flights_in_month_handler(
        {
            "departure_id": "MAA",
            "arrival_id": "HND",
            "month": f"{date.today().year + 1}-01",
            "adults": 2,
        }
    )
    assert result["status"] == "unavailable"
    assert result["recommended_cheapest_dates"] is None
    assert result["best_flights_for_recommended_dates"] == []


def test_reversed_travel_dates_do_not_reach_provider(monkeypatch):
    from datetime import date, timedelta
    from unittest.mock import Mock
    from src.mcp.travelassistant import flight_server, hotel_server

    request = Mock()
    monkeypatch.setattr(flight_server.requests, "get", request)
    earlier = (date.today() + timedelta(days=30)).isoformat()
    later = (date.today() + timedelta(days=33)).isoformat()
    assert flight_server.search_flights_handler(
        {"departure_id": "MAA", "arrival_id": "HND", "outbound_date": later, "return_date": earlier}
    )["error"]
    assert hotel_server.search_hotels_handler({"location": "Kyoto", "check_in_date": later, "check_out_date": earlier})["error"]
    assert hotel_server.search_hotels_handler({"location": "Kyoto", "check_in_date": earlier, "check_out_date": earlier})["error"]
    request.assert_not_called()


@pytest.mark.parametrize("provider", ["flight", "hotel"])
@pytest.mark.parametrize("invalid_date", [None, "", "tomorrow", "2000-01-02", "2030-02-30"])
def test_invalid_travel_dates_do_not_reach_provider(monkeypatch, provider, invalid_date):
    from unittest.mock import Mock
    from src.mcp.travelassistant import flight_server, hotel_server

    request = Mock()
    monkeypatch.setattr(flight_server.requests, "get", request)
    if provider == "flight":
        result = flight_server.search_flights_handler({"departure_id": "MAA", "arrival_id": "HND", "outbound_date": invalid_date})
    else:
        result = hotel_server.search_hotels_handler({"location": "Kyoto", "check_in_date": invalid_date, "check_out_date": "2030-04-14"})
    assert result["error"]
    request.assert_not_called()


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
    assert res["source"] == "serpapi_google_events"
    assert isinstance(res["events_results"], list)
    assert res["status"] in {"ok", "empty", "unavailable"}
    if res["status"] == "unavailable":
        assert res["error"] and res["events_results"] == []


def test_travelassistant_flights_and_hotels():
    """Tests Google Flights and Google Hotels schema tools from mcp_travelassistant."""
    from datetime import date, timedelta

    departure = (date.today() + timedelta(days=30)).isoformat()
    returning = (date.today() + timedelta(days=37)).isoformat()
    flight_tool = next(t for t in mcp_manager.get_tools_for_server("travel_flights") if t.name == "search_flights")
    hotel_tool = next(t for t in mcp_manager.get_tools_for_server("travel_hotels") if t.name == "search_hotels")

    f_res = json.loads(flight_tool.invoke({"departure_id": "IAD", "arrival_id": "YYC", "outbound_date": departure}))
    assert f_res["date"] == departure
    assert isinstance(f_res["best_flights"], list)

    h_res = json.loads(hotel_tool.invoke({"location": "Banff", "check_in_date": departure, "check_out_date": returning}))
    assert h_res["search_metadata"]["check_in_date"] == departure
    assert isinstance(h_res["properties"], list)


def test_flight_search_tolerant_to_null_and_string_adults_and_duration(monkeypatch):
    from datetime import date
    from src.mcp.travelassistant import flight_server

    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    next_year_month = f"{date.today().year + 1}-01"

    # adults=None and duration_days=None must default gracefully without returning validation error
    res_monthly = flight_server.search_cheapest_flights_in_month_handler(
        {
            "departure_id": "SIN",
            "arrival_id": "DPS",
            "month": next_year_month,
            "adults": None,
            "duration_days": None,
        }
    )
    assert "error" not in res_monthly or not res_monthly["error"]
    assert res_monthly["adults"] == 1
    assert res_monthly["trip_duration_days"] == 5

    # string adults and string duration
    res_monthly_str = flight_server.search_cheapest_flights_in_month_handler(
        {
            "departure_id": "SIN",
            "arrival_id": "DPS",
            "month": next_year_month,
            "adults": "2",
            "duration_days": "7",
        }
    )
    assert "error" not in res_monthly_str or not res_monthly_str["error"]
    assert res_monthly_str["adults"] == 2
    assert res_monthly_str["trip_duration_days"] == 7
