from pydantic import BaseModel
from datetime import datetime
from typing import Optional, TypeVar

T = TypeVar('T')

class CreditBase(BaseModel):
    credits: int
    action: str
    type: int
    description: Optional[str] = None

class CreditCreate(CreditBase):
    user_id: int

class CreditUpdate(BaseModel):
    description: Optional[str] = None

class Credit(CreditBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class CreditResponse(Credit):
    """Response model for credit operations"""
    pass

class CreditHistoryResponse(BaseModel):
    """Response model for credit history"""
    id: int
    user_id: int
    credits: int
    action: str
    type: int
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True