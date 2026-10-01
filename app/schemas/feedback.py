from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, constr

class FeedbackBase(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    content: constr(min_length=1, max_length=2000)
    status: Optional[str] = 'pending'
    type: Optional[str] = 'bug'

class FeedbackCreate(FeedbackBase):
    pass

class FeedbackUpdate(BaseModel):
    content: Optional[constr(min_length=1, max_length=2000)] = None
    status: Optional[str] = None

class Feedback(FeedbackBase):
    id: int
    ip_address: str
    created_at: datetime

    class Config:
        from_attributes = True
