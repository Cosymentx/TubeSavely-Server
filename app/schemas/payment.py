from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel

class PaymentBase(BaseModel):
    """支付基础模型"""
    credits: int
    amount: Decimal
    payment_method: str

class PaymentCreate(PaymentBase):
    """创建支付订单模型"""
    order_id: str

class PaymentUpdate(BaseModel):
    """更新支付订单模型"""
    status: str
    trade_no: Optional[str] = None

class Payment(PaymentBase):
    """支付订单模型"""
    id: int
    user_id: int
    order_id: str
    trade_no: Optional[str] = None
    status: str
    created_at: datetime
    paid_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PaymentResponse(BaseModel):
    """支付响应模型"""
    order_id: str
    amount: Decimal
    credits: int
    payment_url: str

class PaymentCallback(BaseModel):
    order_id: str
    trade_no: str
    amount: Decimal
    status: str