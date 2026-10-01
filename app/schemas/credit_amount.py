from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class CreditAmountBase(BaseModel):
    credits: int
    amount_cny: float
    amount_usd: float
    creem_product_id: str
    is_active: Optional[bool] = True

class CreditAmountCreate(CreditAmountBase):
    pass

class CreditAmountUpdate(BaseModel):
    credits: Optional[int] = None
    amount_cny: Optional[float] = None
    amount_usd: Optional[float] = None
    is_active: Optional[bool] = None

class CreditAmountInDBBase(CreditAmountBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class CreditAmount(CreditAmountInDBBase):
    pass

class CreditAmountInDB(CreditAmountInDBBase):
    pass