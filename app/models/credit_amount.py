from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float
from app.db.base_class import Base

class CreditAmount(Base):
    __tablename__ = "credit_amount"

    id = Column(Integer, primary_key=True, index=True)
    credits = Column(Integer, nullable=False)  # 积分数量
    amount_cny = Column(Float, nullable=False)  # 人民币价格
    amount_usd = Column(Float, nullable=False)  # 美元价格
    creem_product_id = Column(String, nullable=False)  # Creem产品ID
    is_active = Column(Boolean, default=True)  # 是否激活
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<CreditAmount(id={self.id}, credits={self.credits}, amount_cny={self.amount_cny}, amount_usd={self.amount_usd})>"