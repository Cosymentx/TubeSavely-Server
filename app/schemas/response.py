from typing import TypeVar, Generic, Optional, Any
from pydantic import BaseModel

T = TypeVar('T')

class ApiResponse(BaseModel, Generic[T]):
    """Base API response model that wraps all API responses"""
    code: int = 200
    msg: str = "success"
    data: Optional[T] = None 