from typing import List
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core import deps
from fastapi import UploadFile, File, HTTPException
from app.schemas.user import User, UserCreate, UserUpdate
from app.schemas.response import ApiResponse
from app.services.user import create_user, get_users, update_user, get_user_by_email

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=ApiResponse[List[User]])
def read_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_superuser)
):
    """
    Retrieve users.
    """
    try:
        users = get_users(db, skip=skip, limit=limit)
        return ApiResponse(data=users)
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        return ApiResponse(
            code=500,
            msg="Failed to fetch user list",
            data=None
        )

@router.post("/", response_model=ApiResponse[User])
def create_new_user(
    user_in: UserCreate,
    db: Session = Depends(deps.get_db)
):
    """
    Create new user.
    """
    try:
        # Check if email already exists
        if get_user_by_email(db, user_in.email):
            return ApiResponse(
                code=400,
                msg="Email is already registered",
                data=None
            )
        
        user = create_user(db, user_in)
        return ApiResponse(data=user)
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return ApiResponse(
            code=500,
            msg="Failed to create user",
            data=None
        )

@router.get("/profile", response_model=ApiResponse[User])
def get_user_profile(
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get current user profile.
    """
    try:
        return ApiResponse(data=current_user)
    except Exception as e:
        logger.error(f"Error fetching user profile: {str(e)}")
        return ApiResponse(
            code=500,
            msg="Failed to fetch user profile",
            data=None
        )

@router.put("/profile", response_model=ApiResponse[User])
def update_user_profile(
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    Update current user profile.
    """
    try:
        # 如果要更新邮箱，检查新邮箱是否已被使用
        if user_in.email and user_in.email != current_user.email:
            if get_user_by_email(db, user_in.email):
                return ApiResponse(
                    code=400,
                    msg="Email is already in use by another user",
                    data=None
                )

        user = update_user(db, current_user, user_in)
        return ApiResponse(data=user)
    except Exception as e:
        logger.error(f"Error updating user profile: {str(e)}")
        return ApiResponse(
            code=500,
            msg="Failed to update user profile",
            data=None
        )

@router.post("/avatar", response_model=ApiResponse[dict])
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    上传用户头像
    """
    # 验证文件类型
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # 验证文件大小（限制为2MB）
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:  # 2MB
        raise HTTPException(status_code=400, detail="File size must be less than 2MB")
    
    # 重置文件指针
    await file.seek(0)
    
    # 上传到MinIO
    avatar_url = await minio_service.upload_avatar(file, current_user.id)
    if not avatar_url:
        raise HTTPException(status_code=500, detail="Failed to upload avatar")
    
    # 更新用户头像URL
    updated_user = update_user(db, current_user, UserUpdate(avatar=avatar_url))
    
    return ApiResponse(
        data={"avatar_url": avatar_url}
    )
