from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class BookingRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class TimeSlot(BaseModel):
    start_time: datetime
    end_time: datetime
    available: bool


class BookingConfirmation(BaseModel):
    event_id: str
    title: str
    start_time: datetime
    end_time: datetime
    attendee_email: Optional[str] = None
    event_url: Optional[str] = None


class ChatResponse(BaseModel):
    message: str
    conversation_id: str
    suggested_slots: Optional[List[TimeSlot]] = None
    booking_confirmed: Optional[BookingConfirmation] = None
    requires_input: bool = True
