from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..db.base_class import Base


class Credit(Base):
    __tablename__ = "credits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    credits = Column(Integer, nullable=False)  # 积分数量，可以是正数或负数
    action = Column(String(100), nullable=False)  # 积分变动行为  Signup_Bonus, Consume, Recharge
    type = Column(Integer, nullable=False)  # 积分变动类型 0: 系统赠送 1: 充值 2: 消费
    description = Column(String(500), nullable=True)  # 积分变动描述
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关联
    user = relationship("User", back_populates="credit_histories", lazy="joined")

    def __repr__(self):
        return f"<Credit(id={self.id}, user_id={self.user_id}, credits={self.credits}, action={self.action}),type={self.type}, description={self.description}>"