from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

class TaskBase(BaseModel):
    """任务基础模型"""
    title: str
    description: Optional[str] = None
    input_url: Optional[str] = None
    input_params: Optional[Dict[str, Any]] = None
    output_format: Optional[str] = None
    credits_cost: int

class TaskCreate(TaskBase):
    """创建任务请求模型"""
    pass

class Task(TaskBase):
    """任务响应模型"""
    id: int
    user_id: int
    task_type: str  # convert 或 generate
    status: str  # pending, processing, completed, failed, cancelled
    error_message: Optional[str] = None
    output_url: Optional[str] = None
    progress: Optional[int] = None  # 0-100 的进度值
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True