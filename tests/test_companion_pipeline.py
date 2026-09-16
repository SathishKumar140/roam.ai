from src.storage.database import db
from src.models.channel import ChannelEvent, ChannelUser, ChannelMedia
from src.agents.deep_companion import ambient_companion

async def test_ambient_companion_travel_proposal():
    channel = "group_trip_99"

    # Seed some background conversation into SQLite buffer
    db.buffer_message(ChannelEvent(
        event_id="bg_1",
        platform="telegram",
        channel_id=channel,
        sender=ChannelUser(id="u1", name="Alice"),
        text="I prefer beach villas and vegetarian food."
    ))
    db.buffer_message(ChannelEvent(
        event_id="bg_2",
        platform="telegram",
        channel_id=channel,
        sender=ChannelUser(id="u2", name="Bob"),
        text="Keep it under $150 per night."
    ))

    # Ask the companion to plan
    res = await ambient_companion.ainvoke(
        {
            "channel_id": channel,
            "platform": "telegram",
            "sender_name": "Charlie",
            "sender_id": "u3",
            "text": "@companion let's plan a trip to Bali!",
            "history": db.get_recent_group_messages(channel)
        },
        config={"configurable": {"thread_id": channel}}
    )

    assert "Trip Proposal" in res["output"]
    assert "Recommended Flight" in res["output"]
    assert "Recommended Stay" in res["output"]
    assert "buttons" in res
    assert len(res["buttons"]) > 0

async def test_ambient_companion_vision_photo_analysis():
    channel = "group_trip_99"

    res = await ambient_companion.ainvoke(
        {
            "channel_id": channel,
            "platform": "telegram",
            "sender_name": "Alice",
            "sender_id": "u1",
            "text": "What do you think of this place?",
            "media": {"type": "photo", "file_id": "photo_xyz"}
        },
        config={"configurable": {"thread_id": channel}}
    )

    assert "Scout Analysis" in res["output"]
    assert "Vibe" in res["output"]
    assert "Pricing" in res["output"]
    assert "buttons" in res

async def test_ambient_companion_expense_logging_and_balance():
    channel = "group_trip_99"

    # 1. Log an expense
    log_res = await ambient_companion.ainvoke(
        {
            "channel_id": channel,
            "platform": "telegram",
            "sender_name": "Alice",
            "sender_id": "u1",
            "text": "I paid $120 for dinner"
        },
        config={"configurable": {"thread_id": channel}}
    )
    assert "Logged expense" in log_res["output"]

    # 2. Ask for balance
    bal_res = await ambient_companion.ainvoke(
        {
            "channel_id": channel,
            "platform": "telegram",
            "sender_name": "Bob",
            "sender_id": "u2",
            "text": "Who owes what right now?"
        },
        config={"configurable": {"thread_id": channel}}
    )
    assert "Group Expense Settlement Sheet" in bal_res["output"]
    assert "Alice" in bal_res["output"]
