from typing import Literal

from pydantic import BaseModel, Field


class PreferenceUpdate(BaseModel):
    key: str = Field(max_length=80)
    value: str = Field(max_length=300)
    evidence_message_id: str
    scope: Literal["topic", "global"] = "topic"
    evidence_quote: str = Field(default="", max_length=500)


class TopicFact(BaseModel):
    key: Literal["destination", "departure", "dates", "travelers", "budget", "hotel_budget", "currency", "dietary_preference", "transportation_preference", "payer", "amount", "participants"]
    value: str = Field(min_length=1, max_length=300, description="Exact user wording for this field, contained in evidence_quote; do not normalize or infer")
    evidence_message_id: str
    evidence_quote: str = Field(min_length=1, max_length=500)


class Observation(BaseModel):
    topic_id: str | None = Field(default=None, description="Copy an existing id from group_context.topics, or return null for a new topic. Never create an id.")
    comparison_topic_ids: list[str] = Field(default_factory=list, max_length=4, description="Existing topic IDs explicitly requested for a read-only comparison; otherwise empty")
    title: str = Field(default="Conversation", max_length=120)
    summary: str = Field(default="", max_length=2000)
    intent: Literal["social", "planning", "expense", "poll", "question"] = "social"
    decision: Literal["silent", "offer", "respond", "decline"] = "silent"
    accepts_offer: bool = False
    continues_task: bool = Field(default=False, description="The latest speaker is clearly answering RoamAI's pending question in this existing active topic, not merely chatting or saying an ambiguous yes")
    confidence: float = Field(default=0, ge=0, le=1)
    evidence_message_ids: list[str] = Field(default_factory=list, max_length=10, description="The 'id' values from supplied messages, not platform message_id values")
    participant_ids: list[str] = Field(default_factory=list, max_length=50)
    preferences: list[PreferenceUpdate] = Field(default_factory=list, max_length=10)
    facts: list[TopicFact] = Field(default_factory=list, max_length=15)
    offer_evidence_message_id: str | None = Field(default=None, description="Current batch message from the person who paid or requested help; the offer will be addressed to its author")
    offer: str = Field(default="", max_length=300)
    reason: str = Field(default="", max_length=300)
    clarification_question: str = Field(default="", max_length=300, description="Ask a concise question when the target topic, field, unit, or requested change is ambiguous. No state may change until clarified.")