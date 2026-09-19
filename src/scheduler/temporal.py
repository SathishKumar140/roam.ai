from typing import Callable
from datetime import datetime

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()
    _has_apscheduler = True
except ImportError:
    scheduler = None
    _has_apscheduler = False


def start_scheduler():
    if _has_apscheduler and scheduler and not scheduler.running:
        scheduler.start()


def schedule_trip_wakeup(channel_id: str, platform: str, send_callback: Callable, run_date: datetime):
    """
    Schedules an autonomous wake-up message to the group on the morning of departure.
    """
    job_id = f"trip_wakeup_{channel_id}"

    async def _job():
        trip = db.get_active_trip(channel_id)
        dest = trip.destination if trip else "your destination"
        msg = OutboundMessage(
            platform=platform,
            channel_id=channel_id,
            text=f"🌅 *Good morning team!* Today is departure day for **{dest}**! 🎒\n\nAre you all packed and ready? Tap below to confirm everyone is on the way!",
            buttons=[
                [{"id": "confirm_trip_yes", "label": "✅ We're on the way!", "type": "callback"}],
                [{"id": "trip_delay", "label": "⏳ Delayed / Need updates", "type": "callback"}],
            ],
        )
        await send_callback(msg)

    scheduler.add_job(_job, trigger="date", run_date=run_date, id=job_id, replace_existing=True)
    return job_id
