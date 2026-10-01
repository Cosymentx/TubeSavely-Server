from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, Literal
from datetime import datetime

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str
    is_superuser: Literal[False] = False
    is_active: Optional[bool] = True

class UserUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    avatar: Optional[str] = None

class SetPasswordRequest(BaseModel):
    new_password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class User(UserBase):
    id: int
    user_id: str
    credits: int
    created_at: datetime
    updated_at: datetime
    is_superuser: bool
    is_active: bool
    avatar: Optional[str] = None
    bio: Optional[str] = None
    oauth_provider: Optional[str] = None
    oauth_id: Optional[str] = None
    has_password: bool = False  # 是否设置密码

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

from .token import Token

class UserLogin(BaseModel):
    email: str
    password: str
