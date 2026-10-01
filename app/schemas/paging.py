from pydantic import BaseModel
from typing import Optional, List, Generic, TypeVar

T = TypeVar('T')

class PageResponse(BaseModel, Generic[T]):
    """通用分页响应模型"""
    records: List[T]
    total: int
    size: int
    current: int
    pages: int