from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..db.base_class import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    order_id = Column(String(100), unique=True, index=True)
    trade_no = Column(String(100), unique=True, nullable=True)
    amount = Column(Numeric(10, 2))
    credits = Column(Integer)
    payment_method = Column(String(20))
    currency = Column(String(3), nullable=False, default="USD", server_default="USD")
    provider_checkout_id = Column(String(255), unique=True, index=True, nullable=True)
    provider_product_id = Column(String(255), nullable=True)
    status = Column(String(20))
    credit_reversal_applied = Column(Boolean, nullable=False, default=False, server_default="0")
    reversal_reason = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    disputed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="payment_histories")
    events = relationship("PaymentEvent", back_populates="payment", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Payment(order_id={self.order_id}, amount={self.amount}, status={self.status})>"
