from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class VideoFormatBase(BaseModel):
    format_id: str
    format_note: Optional[str] = None
    ext: str
    height: Optional[int] = None
    width: Optional[int] = None
    filesize: Optional[int] = None
    filesize_approx: Optional[int] = None
    fps: Optional[int] = None
    tbr: Optional[float] = None
    url: Optional[str] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    dynamic_range: Optional[str] = None
    resolution: Optional[str] = None

class VideoBase(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None
    duration: Optional[str] = None     
    thumbnail: Optional[str] = None
    formats: List[VideoFormatBase]
    video_id: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None    
    platform: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None

class VideoCreate(VideoBase):
    pass

class VideoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnail: Optional[str] = None

class Video(VideoBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True