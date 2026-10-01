from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from jose import jwt
import logging

from ..core.config import settings
from ..core.security import verify_password
from ..models.user import User
from ..services.user import get_user_by_email

logger = logging.getLogger(__name__)

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Authenticate user by username/email and password.
    """
    logger.debug(f"Attempting to authenticate user with email: {username}")
    
    user = get_user_by_email(db, email=username)
    if not user:
        logger.warning(f"No user found with email: {username}")
        return None
        
    if not user.hashed_password:  # OAuth user without password
        logger.warning(f"User {username} has no password (OAuth user)")
        return None
        
    if not verify_password(password, user.hashed_password):
        logger.warning(f"Invalid password for user: {username}")
        return None
        
    logger.info(f"Successfully authenticated user: {username}")
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create access token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt
