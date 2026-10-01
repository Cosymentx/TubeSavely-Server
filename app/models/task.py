from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..db.base_class import Base


class Task(Base):
    """任务模型"""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    input_url = Column(String(2048))
    input_params = Column(JSON)
    output_format = Column(String(50))
    output_url = Column(String(2048))
    task_type = Column(String(50), nullable=False)  # convert 或 generate
    status = Column(String(50), nullable=False)  # pending, processing, completed, failed, cancelled
    error_message = Column(Text)
    progress = Column(Integer, default=0)  # 0-100 的进度值
    credits_cost = Column(Integer, nullable=False)  # 任务所需积分
    
    # 外键关联
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user = relationship("User", back_populates="tasks", lazy="joined")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)