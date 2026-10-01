from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class DownloadBase(BaseModel):
    video_url: str
    video_title: str
    format: str
    status: str = "pending"
    error: Optional[str] = None

class DownloadCreate(DownloadBase):
    user_id: int
    video_id: int

class DownloadUpdate(BaseModel):
    status: Optional[str] = None
    error: Optional[str] = None

class Download(DownloadBase):
    id: int
    user_id: int
    video_id: int
    download_time: datetime

    class Config:
        from_attributes = True