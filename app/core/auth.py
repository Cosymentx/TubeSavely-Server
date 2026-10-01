from typing import Optional
from sqlalchemy.orm import Session
import logging

from ..models.user import User
from ..services.user import get_user_by_email
from .security import verify_password, create_access_token

logger = logging.getLogger(__name__)


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate user by email and password."""
    logger.debug("Attempting to authenticate user")
    user = get_user_by_email(db, email=username)
    if not user or not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
