from langchain_core.tools import tool
from src.storage.database import db
from src.models.session import ActiveTripSession, TripParticipant

@tool
def schedule_trip_departure_checkin(channel_id: str, destination: str, trip_date: str) -> str:
    """
    Schedules an autonomous wake-up check-in for the trip departure day.
    """
    trip = db.get_active_trip(channel_id)
    if not trip:
        session_id = f"trip_{channel_id}"
        trip = ActiveTripSession(
            session_id=session_id,
            channel_id=channel_id,
            status="planning",
            destination=destination,
            start_date=trip_date
        )
    else:
        trip.destination = destination
        trip.start_date = trip_date
        trip.status = "planning"
    
    db.save_active_trip(trip)
    return f"Scheduled wake-up concierge for trip to {destination} on {trip_date}. The companion will autonomously check in on departure morning!"

@tool
def confirm_trip_departure(channel_id: str, user_name: str) -> str:
    """
    Records a participant's confirmation for departing on the trip.
    Switches status to 'in_progress' when confirmed.
    """
    trip = db.get_active_trip(channel_id)
    if not trip:
        return "No active trip found to confirm."

    # Update participant or trip status
    trip.status = "in_progress"
    db.save_active_trip(trip)
    return f"✅ Trip departure confirmed by {user_name}! Status updated to 'in_progress'. Have an incredible journey to {trip.destination or 'your destination'}! Let me know if you need to log any expenses or find great food along the way."

@tool
def get_trip_status(channel_id: str) -> str:
    """
    Retrieves the current status, dates, and destination of the active trip for the group.
    """
    trip = db.get_active_trip(channel_id)
    if not trip:
        return "No active trip currently on record for this group."

    return f"Trip to {trip.destination or 'TBD'} | Status: {trip.status.upper()} | Dates: {trip.start_date or 'TBD'} to {trip.end_date or 'TBD'}."

proactive_tools = [schedule_trip_departure_checkin, confirm_trip_departure, get_trip_status]
