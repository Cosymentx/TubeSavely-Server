from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

from ..db.base_class import Base

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    original_url = Column(Text, nullable=False)
    title = Column(String(255), nullable=False)
    thumbnail = Column(Text)
    description = Column(Text)
    duration = Column(String(50))  # 视频时长（秒）
    platform = Column(String(50))  # 视频平台
    credits_cost = Column(Integer, nullable=False)  # 所需积分
    
    # 视频元数据
    video_id = Column(String(100))  # 平台上的视频ID
    author = Column(String(100), nullable=True)
    author_url = Column(Text, nullable=True)
    formats = Column(JSON, nullable=True)
    
    # 关联关系
    users = relationship(
        "User",
        secondary="video_user_relations",
        back_populates="videos",
        lazy="dynamic"
    )
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Video(title={self.title}, platform={self.platform}, video_id={self.video_id})>"
