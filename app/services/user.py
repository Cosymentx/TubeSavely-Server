from typing import Optional
import logging
import traceback
from datetime import datetime
import uuid
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from fastapi import HTTPException, status

from app.core.security import get_password_hash
from app.models.user import User
from app.services.credit import add_credits
from app.schemas.user import UserCreate, UserUpdate

logger = logging.getLogger(__name__)

def get_user_by_email(db: Session, email: str, oauth_provider: Optional[str] = None) -> Optional[User]:
    """
    Get user by email and optionally oauth_provider.
    """
    try:
        logger.debug(f"Looking up user by email: {email} and oauth_provider: {oauth_provider}")
        query = db.query(User).filter(User.email == email)
        if oauth_provider:
            query = query.filter(User.oauth_provider == oauth_provider)
        user = query.first()
        if user:
            logger.debug(f"Found user with email: {email}")
        else:
            logger.debug(f"No user found with email: {email}")
        return user
    except Exception as e:
        logger.error(f"Error looking up user by email {email}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """
    Get user by username.
    """
    try:
        logger.debug(f"Looking up user by username: {username}")
        user = db.query(User).filter(User.username == username).first()
        if user:
            logger.debug(f"Found user with username: {username}")
        else:
            logger.debug(f"No user found with username: {username}")
        return user
    except Exception as e:
        logger.error(f"Error looking up user by username {username}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """
    Get user by ID.
    """
    return db.query(User).filter(User.id == user_id).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    """
    Get list of users.
    """
    return db.query(User).offset(skip).limit(limit).all()

def validate_new_user(db: Session, email: str, username: str, password: str, oauth_provider: Optional[str] = None) -> None:
    """
    验证新用户的信息
    :raises HTTPException: 当验证失败时抛出异常
    """
    # 验证邮箱是否已存在（仅针对非OAuth用户）
    if not oauth_provider:
        existing_user = get_user_by_email(db, email, oauth_provider=None)
        if existing_user:
            logger.warning(f"Attempted to create user with existing email: {email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered"
            )
    
    # 验证密码长度（仅针对非OAuth用户）
    if not oauth_provider and password and len(password) < 6:
        logger.warning(f"Attempted to create user with short password: {email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )

def _create_user_in_db(
    db: Session,
    email: str,
    username: str,
    is_active: bool = True,
    is_superuser: bool = False,
    has_password: bool = False,
    hashed_password: Optional[str] = None,
    oauth_provider: Optional[str] = None,
    oauth_id: Optional[str] = None,
) -> User:
    """
    Internal function to create a new user in the database with common defaults
    """
    try:
        logger.debug(f"Creating user object for: {email}")
        # 生成唯一的user_id：时间戳前缀 + UUID后缀的前8位
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        uuid_suffix = str(uuid.uuid4()).replace('-', '')[:8]
        unique_user_id = f"U{timestamp}{uuid_suffix}"
        
        print(f'unique_user_id: {unique_user_id}')
        db_user = User(
            email=email,
            user_id=unique_user_id,
            username=username,
            hashed_password=hashed_password,
            has_password=has_password,
            is_active=is_active,
            is_superuser=is_superuser,
            oauth_provider=oauth_provider,
            oauth_id=oauth_id,
            credits=0,  # Default credits
            avatar=f"https://api.dicebear.com/7.x/micah/svg?seed={username}",  # Default avatar
            bio='Hello, I am new here!'  # Default bio
        )
        
        logger.debug(f"Adding user to database: {email}")
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        logger.info(f"Successfully created user: {email}")
        add_credits(
            db=db,
            user=db_user,
            credits=50,
            action="Signup Bonus",
            type=0,
            description=f"New user grant 50 credits"
            )
        return db_user
        
    except Exception as e:
        logger.error(f"Database error while creating user {email}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )

def create_user(db: Session, user_in: UserCreate) -> User:
    """
    Create new user through regular registration.
    """ 
    try:
        logger.debug(f"Starting user creation for email: {user_in.email}")
        
        # 验证用户信息
        validate_new_user(db, user_in.email, user_in.username, user_in.password)
        
        # Hash password
        logger.debug(f"Hashing password for user: {user_in.email}")
        hashed_password = get_password_hash(user_in.password)
        
        # Create user using common function
        return _create_user_in_db(
            db=db,
            email=user_in.email,
            username=user_in.username,
            is_superuser=False,
            has_password=True,
            hashed_password=hashed_password
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error while creating user {user_in.email}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )

def update_user(db: Session, db_user: User, user_in: UserUpdate) -> User:
    """
    Update user.
    """
    update_data = user_in.model_dump(exclude_unset=True)
    if update_data.get("password"):
        hashed_password = get_password_hash(update_data["password"])
        del update_data["password"]
        update_data["hashed_password"] = hashed_password
        update_data["has_password"] = True
        
    for field, value in update_data.items():
        setattr(db_user, field, value)
        
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )

def create_or_update_user(
    db: Session,
    email: str,
    name: Optional[str] = None,
    oauth_provider: Optional[str] = None,
    oauth_id: Optional[str] = None
) -> User:
    """
    Create or update user from OAuth login.
    """
    logger.debug(f"Attempting to create or update user with email: {email}, oauth_provider: {oauth_provider}")
    
    try:
        # 首先查找是否存在使用相同邮箱和OAuth提供商的用户
        existing_user = get_user_by_email(db, email=email, oauth_provider=oauth_provider)
        
        if existing_user:
            logger.debug(f"Found existing user with email: {email} and oauth_provider: {oauth_provider}")
            # 更新用户的 OAuth 信息
            existing_user.oauth_id = oauth_id
            db.add(existing_user)
            logger.info(f"Updated OAuth info for existing user: {email}")
        else:
            logger.debug(f"No existing user found, creating new user with email: {email}")
            # 如果用户不存在，创建新用户
            username = name if name else email.split('@')[0]
            existing_user = _create_user_in_db(
                db=db,
                email=email,
                username=username,
                oauth_provider=oauth_provider,
                oauth_id=oauth_id,
                has_password=False
            )
            logger.info(f"Created new user with OAuth: {email}")
        
        db.commit()
        db.refresh(existing_user)
        return existing_user
        
    except Exception as e:
        logger.error(f"Error in create_or_update_user for {email}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create or update user: {str(e)}"
        )
    
    try:
        db.commit()
        db.refresh(existing_user)
        return existing_user
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create or update user: {str(e)}"
        )
