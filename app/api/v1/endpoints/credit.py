from typing import List
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import deps
from app.schemas.credit import CreditHistoryResponse
from app.schemas.paging import PageResponse
from app.schemas.response import ApiResponse
from app.models.user import User
from app.services.credit import (
    get_credit_history,
    get_user_credits,
    add_credits,
    deduct_credits,
    InsufficientCreditsError
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=ApiResponse[int])
def read_credits(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get current user's credits balance"""
    try:
        credits = get_user_credits(db, current_user)
        return ApiResponse(data=credits)
    except Exception as e:
        logger.error(f"Error getting user credits: {str(e)}")
        return ApiResponse(
            code=500,
            msg="Failed to fetch credits balance, please try again later",
            data=None
        )

@router.get("/history", response_model=ApiResponse[PageResponse[CreditHistoryResponse]])
def read_credit_history(
    offset: int = 1,
    limit: int = 20,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get current user's credit history"""
    try:
        result = get_credit_history(db, current_user, offset, limit)
        return ApiResponse(data=result)
    except Exception as e:
        logger.error(f"Error getting credit history: {str(e)}")
        return ApiResponse(
            code=500,
            msg="Failed to fetch credits history, please try again later",
            data=None
        )

@router.post("/add", response_model=ApiResponse[dict])
def add_user_credits(
    credits: int,
    action: str,
    description: str = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_superuser)
):
    """Administrative credit adjustment endpoint."""
    try:
        if credits <= 0:
            return ApiResponse(
                code=400,
                msg="Credits to add must be greater than 0",
                data=None
            )
            
        add_credits(db, current_user, credits, action, type=0, description=description)
        return ApiResponse(data={"credits": credits})
    except Exception as e:
        logger.error(f"Error adding credits: {str(e)}")
        return ApiResponse(
            code=500,
            msg="Failed to add credits, please try again later",
            data=None
        )

@router.post("/deduct", response_model=ApiResponse[dict])
def deduct_user_credits(
    credits: int,
    action: str,
    description: str = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_superuser)
):
    """Administrative credit deduction endpoint."""
    try:
        if credits <= 0:
            return ApiResponse(
                code=400,
                msg="Credits to deduct must be greater than 0",
                data=None
            )
            
        deduct_credits(db, current_user, credits, action, description)
        return ApiResponse(data={"credits": credits})
    except InsufficientCreditsError:
        return ApiResponse(
            code=400,
            msg="Insufficient credits balance",
            data=None
        )
    except Exception as e:
        logger.error(f"Error deducting credits: {str(e)}")
        return ApiResponse(
            code=500,
            msg="Failed to deduct credits, please try again later",
            data=None
        )
