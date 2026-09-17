from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime

class TripParticipant(BaseModel):
    user_id: str
    name: str
    confirmed: bool = False
    preferences: List[str] = Field(default_factory=list)

class ItineraryDay(BaseModel):
    day: int
    date: str
    activities: List[str] = Field(default_factory=list)
    hotel: Optional[Dict[str, str]] = None

class ExpenseItem(BaseModel):
    expense_id: str
    paid_by_user_id: str
    paid_by_name: str
    amount: float
    currency: str = "SGD"
    description: str
    split_between_user_ids: List[str] = Field(default_factory=list)
    confirmed_by_user_ids: List[str] = Field(default_factory=list)
    status: Literal["pending_confirmation", "confirmed"] = "pending_confirmation"
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class DebtTransfer(BaseModel):
    debtor_id: str
    debtor_name: str
    creditor_id: str
    creditor_name: str
    amount: float
    currency: str = "USD"

class ActiveTripSession(BaseModel):
    session_id: str
    channel_id: str
    status: Literal["planning", "confirmed", "in_progress", "completed"] = "planning"
    destination: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    participants: List[TripParticipant] = Field(default_factory=list)
    itinerary: List[ItineraryDay] = Field(default_factory=list)
    expenses: List[ExpenseItem] = Field(default_factory=list)
