from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid
from ..db.base_class import Base
from .video_user_relation import VideoUserRelation

class User(Base):
    """用户模型"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), unique=True, index=True, nullable=False)
    username = Column(String(50))
    email = Column(String(100), index=True)
    hashed_password = Column(String(255))
    has_password = Column(Boolean, default=False)
    avatar = Column(String(255))
    credits = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    
    # OAuth2相关字段
    oauth_provider = Column(String(20), nullable=True)  # 'google', 'github', 'facebook' 等
    oauth_id = Column(String(100), nullable=True, index=True)  # 第三方平台的用户ID
    bio = Column(String(255), nullable=True)  # 用户简介
    
    # 关联关系
    videos = relationship(
        "Video",
        secondary=VideoUserRelation.__tablename__,
        back_populates="users",
        lazy="dynamic",
        cascade="all, delete"
    )
    credit_histories = relationship("Credit", back_populates="user", lazy="dynamic")
    payment_histories = relationship("Payment", back_populates="user", lazy="dynamic")
    feedbacks = relationship("Feedback", back_populates="user", lazy="dynamic")
    tasks = relationship("Task", back_populates="user", lazy="dynamic")
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)