from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..db.base_class import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    order_id = Column(String(100), unique=True, index=True)  # 内部订单号
    trade_no = Column(String(100), unique=True, nullable=True)  # 支付平台交易号
    amount = Column(Numeric(10, 2))  # 支付金额
    credits = Column(Integer)  # 购买的积分数量
    payment_method = Column(String(20))  # 支付方式：alipay, wechat, paypal, airwallex
    status = Column(String(20))  # 状态：pending, paid, failed, refunded
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)  # 支付完成时间
        
    # 关联
    user = relationship("User", back_populates="payment_histories")

    def __repr__(self):
        return f"<Payment(order_id={self.order_id}, amount={self.amount}, status={self.status})>"