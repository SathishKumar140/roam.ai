import json
from src.agents.tools.travel_tools import search_flights, search_hotels, generate_itinerary
from src.agents.tools.vision_tools import analyze_venue_photo
from src.agents.tools.proactive_tools import schedule_trip_departure_checkin, confirm_trip_departure, get_trip_status


def test_travel_tools_execution():
    # 1. Flight search
    flights_res = search_flights.invoke({"origin": "SIN", "destination": "DPS", "date": "2026-10-15", "max_budget": 150.0})
    data = json.loads(flights_res)
    assert "route" in data
    assert len(data["available_options"]) > 0
    assert all(f["price"] <= 150.0 for f in data["available_options"])

    # 2. Hotel search
    hotels_res = search_hotels.invoke({"destination": "Bali", "checkin_date": "2026-10-15", "checkout_date": "2026-10-18"})
    h_data = json.loads(hotels_res)
    assert "hotels" in h_data
    assert len(h_data["hotels"]) > 0

    # 3. Itinerary generation
    itin_res = generate_itinerary.invoke({"destination": "Bali", "days": 2, "preferences": "beach, dining"})
    i_data = json.loads(itin_res)
    assert i_data["days"] == 2
    assert len(i_data["schedule"]) == 2


def test_vision_tools_execution():
    res = analyze_venue_photo.invoke({"photo_url_or_id": "file_123", "context_caption": "Should we eat here?"})
    v_data = json.loads(res)
    assert v_data["status"] == "success"
    assert "detected_place" in v_data
    assert "recommendation" in v_data


def test_proactive_concierge_lifecycle():
    channel = "test_group_789"
    # Schedule check-in
    sched_msg = schedule_trip_departure_checkin.invoke({"channel_id": channel, "destination": "Bali", "trip_date": "2026-10-15"})
    assert "Scheduled wake-up" in sched_msg

    # Verify status is planning
    status_msg = get_trip_status.invoke({"channel_id": channel})
    assert "PLANNING" in status_msg

    # Confirm departure
    conf_msg = confirm_trip_departure.invoke({"channel_id": channel, "user_name": "Bob"})
    assert "confirmed by Bob" in conf_msg

    # Verify status is now in_progress
    updated_status = get_trip_status.invoke({"channel_id": channel})
    assert "IN_PROGRESS" in updated_status
