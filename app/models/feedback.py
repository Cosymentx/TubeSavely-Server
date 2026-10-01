from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..db.base_class import Base


class Feedback(Base):
    """反馈模型"""
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    status = Column(String(50), default="pending")  # pending, processing, completed
    ip_address = Column(String(50), nullable=True)  # 存储提交反馈的IP地址
    type = Column(String(50), default="bug_report")  # feedback, bug_report, feature_request
    
    # 外键关联
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="feedbacks")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
