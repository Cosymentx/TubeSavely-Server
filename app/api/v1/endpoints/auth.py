from datetime import timedelta
import logging
import traceback
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.auth import authenticate_user, create_access_token, verify_password
from app.core.config import settings
from app.core.security import create_refresh_token, verify_refresh_token
from app.core import deps
from app.schemas.user import UserCreate, UserLogin, User, SetPasswordRequest,UserUpdate, ChangePasswordRequest
from app.schemas.response import ApiResponse
from app.services.user import create_user, get_user_by_email, update_user

router = APIRouter()
logger = logging.getLogger(__name__)


def set_refresh_cookie(response: Response, email: str) -> None:
    token = create_refresh_token(email)
    response.set_cookie(
        key="refresh_token",
        value=token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.PRODUCTION,
        samesite="none" if settings.PRODUCTION else "lax",
        path=f"{settings.API_V1_STR}/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key="refresh_token",
        path=f"{settings.API_V1_STR}/auth",
        secure=settings.PRODUCTION,
        samesite="none" if settings.PRODUCTION else "lax",
    )

def create_user_response(user: User) -> Dict[str, Any]:
    """
    创建统一的用户响应数据
    """
    return {        
        "id": user.id,
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "credits": user.credits,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
        "is_superuser": user.is_superuser,
        "avatar": user.avatar,
        "bio": user.bio,
        "oauth_provider": user.oauth_provider,
        "oauth_id": user.oauth_id,
        "has_password": user.has_password
    }

def create_auth_response(user: User, access_token: str) -> Dict[str, Any]:
    """
    创建统一的认证响应数据
    """
    return {    
        "access_token": access_token,
        "token_type": "bearer",
        "user": create_user_response(user)
    }

def generate_access_token(user: User) -> str:
    """
    生成访问令牌
    """
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )

async def authenticate_and_get_token(
    email: str,
    password: str,
    db: Session
) -> Optional[Dict[str, Any]]:
    """
    认证用户并获取令牌
    """
    try:
        # 检查用户是否存在
        db_user = get_user_by_email(db, email)
        if not db_user:
            logger.warning(f"User not found: {email}")
            return None

        # 认证用户
        user = authenticate_user(db, email, password)
        if not user:
            logger.warning(f"Authentication failed for user: {email}")
            return None

        # 生成访问令牌
        access_token = generate_access_token(user)
        return create_auth_response(user, access_token)

    except Exception as e:
        logger.error(f"Authentication error for {email}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

@router.post("/register", response_model=ApiResponse[dict])
async def register(
    user_in: UserCreate,
    response: Response,
    db: Session = Depends(deps.get_db)
):
    """
    Register a new user and return access token.
    """
    try:
        logger.debug(f"Attempting to register user with email: {user_in.email}")
        
        # Check if user already exists
        if get_user_by_email(db, user_in.email):
            logger.warning(f"Registration failed: Email {user_in.email} is already registered")
            return ApiResponse(
                code=400,
                msg="Email is already registered",
            )
        
        # Validate password length
        if len(user_in.password) < 6:
            logger.warning(f"Registration failed: Password too short for user {user_in.email}")
            return ApiResponse(
                code=400,
                msg="Password must be at least 6 characters long",
            )
            
        # Create new user
        user = create_user(db, user_in)
        logger.info(f"Successfully created user with email: {user_in.email}")
        
        # Generate access token and create response
        access_token = generate_access_token(user)
        response_data = create_auth_response(user, access_token)
        set_refresh_cookie(response, user.email)

        return ApiResponse(
            data=response_data
        )
    except Exception as e:
        logger.error(f"Registration error for {user_in.email}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return ApiResponse(
            code=500,
            msg="Registration failed",
        )

@router.post("/login", response_model=ApiResponse[dict])
async def login(
    login_data: UserLogin,
    response: Response,
    db: Session = Depends(deps.get_db)
):
    """
    User login endpoint.
    """
    try:
        logger.info(f"Login attempt for email: {login_data.email}")
        response_data = await authenticate_and_get_token(
            login_data.email,
            login_data.password,
            db
        )
        
        if not response_data:
            return ApiResponse(
                code=401,
                msg="Incorrect email or password",
            )

        set_refresh_cookie(response, login_data.email)
        return ApiResponse(
            data=response_data
        )
            
    except Exception as e:
        logger.error(f"Login error for {login_data.email}: {str(e)}")
        logger.error(f"Login error traceback: {traceback.format_exc()}")
        return ApiResponse(
            code=500,
            msg="Login failed",
        )

@router.post("/oauth/token", response_model=ApiResponse[dict])
async def oauth_login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(deps.get_db)
):
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    try:
        logger.info(f"OAuth login attempt for username: {form_data.username}")
        response_data = await authenticate_and_get_token(
            form_data.username,
            form_data.password,
            db
        )
        
        if not response_data:
            return ApiResponse(
                code=401,
                msg="Invalid credentials",
            )

        set_refresh_cookie(response, form_data.username)
        return ApiResponse(
            data=response_data
        )
            
    except Exception as e:
        logger.error(f"OAuth login error for {form_data.username}: {str(e)}")
        logger.error(f"OAuth login error traceback: {traceback.format_exc()}")
        return ApiResponse(
            code=500,
            msg=f"Login failed: {str(e)}",
        )

@router.post("/refresh", response_model=ApiResponse[dict])
async def refresh_access_token(
    request: Request,
    response: Response,
    db: Session = Depends(deps.get_db),
):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return ApiResponse(code=401, msg="Refresh session is missing", data=None)

    email = verify_refresh_token(refresh_token)
    if not email:
        clear_refresh_cookie(response)
        return ApiResponse(code=401, msg="Refresh session has expired", data=None)

    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        clear_refresh_cookie(response)
        return ApiResponse(code=401, msg="Account is unavailable", data=None)

    access_token = generate_access_token(user)
    set_refresh_cookie(response, user.email)
    return ApiResponse(data=create_auth_response(user, access_token))


@router.post("/logout", response_model=ApiResponse[dict])
async def logout(response: Response):
    clear_refresh_cookie(response)
    return ApiResponse()


@router.post("/set-password", response_model=ApiResponse[dict])
async def set_password(
    password_data: SetPasswordRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    为第三方登录的用户设置密码
    """
    try:
        logger.info(f"Setting password for user: {current_user.email}")
        
        # Validate password length
        if len(password_data.new_password) < 6:
            logger.warning(f"Password too short for user: {current_user.email}")
            return ApiResponse(
                code=400,
                msg="Password must be at least 6 characters long",
            )
        
        # If user already has a password, don't allow using this endpoint
        if current_user.has_password:
            logger.warning(f"User already has password: {current_user.email}")
            return ApiResponse(
                code=400,
                msg="Password is already set. Please use change-password endpoint",
            )
        
        # Update user password
        user = update_user(db, current_user, UserUpdate(password=password_data.new_password))
        logger.info(f"Successfully set password for user: {current_user.email}")
        
        return ApiResponse()
        
    except Exception as e:
        logger.error(f"Error setting password for user {current_user.email}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return ApiResponse(
            code=500,
            msg="Failed to set password",
        )

@router.post("/change-password", response_model=ApiResponse[dict])
async def change_password(
    password_data: ChangePasswordRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    修改用户密码
    """
    try:
        logger.info(f"Changing password for user: {current_user.email}")
        
        # Verify if user has set password
        if not current_user.has_password:
            logger.warning(f"User has no password set: {current_user.email}")
            return ApiResponse(
                code=400,
                msg="No password is set. Please use set-password endpoint",
            )
        
        # Verify current password
        if not verify_password(password_data.current_password, current_user.hashed_password):
            logger.warning(f"Current password verification failed for user: {current_user.email}")
            return ApiResponse(
                code=400,
                msg="Current password is incorrect",
            )
        
        # Validate new password length
        if len(password_data.new_password) < 6:
            logger.warning(f"New password too short for user: {current_user.email}")
            return ApiResponse(
                code=400,
                msg="New password must be at least 6 characters long",
            )
        
        # Update user password
        user = update_user(db, current_user, UserUpdate(password=password_data.new_password))
        logger.info(f"Successfully changed password for user: {current_user.email}")
        
        return ApiResponse()
        
    except Exception as e:
        logger.error(f"Error changing password for user {current_user.email}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return ApiResponse(
            code=500,
            msg="Failed to change password",
        )


