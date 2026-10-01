from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.deps import get_db
import logging
from app.models import credit_amount
from app.schemas.response import ApiResponse
from app.services.credit_amount import CreditAmountService
from app.schemas.credit_amount import CreditAmount, CreditAmountCreate, CreditAmountUpdate

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/list", response_model=ApiResponse[List[CreditAmount]])
def get_credit_amounts(db: Session = Depends(get_db)):
    """获取所有积分价格配置"""
    try:
        credit_amounts = CreditAmountService.get_credit_amounts(db)
        if not credit_amounts:
            return ApiResponse(code=404, msg="Credit amount not found")
        return ApiResponse(data=credit_amounts)
    except Exception as e:
        logger.error(f"Error getting credit amounts: {e}")
        return ApiResponse(code=500, msg=f"{e}")

@router.get("/active/list", response_model=ApiResponse[List[CreditAmount]])
def get_active_credit_amounts(db: Session = Depends(get_db)):
    """获取所有激活的积分价格配置"""
    try:
        credit_amounts = CreditAmountService.get_active_credit_amounts(db)
        if not credit_amounts:
            return ApiResponse(code=404, msg="Active credit amount not found")
        return ApiResponse(data=credit_amounts)
    except Exception as e:
        logger.error(f"Error getting active credit amounts: {e}")
        return ApiResponse(code=500, msg=f"{e}")

@router.get("/{credit_amount_id}", response_model=ApiResponse[CreditAmount])
def get_credit_amount(credit_amount_id: int, db: Session = Depends(get_db)):
    """根据ID获取积分价格配置"""
    try:
        credit_amount = CreditAmountService.get_credit_amount_by_id(db, credit_amount_id)
        if not credit_amount:
            return ApiResponse(code=404, msg="Credit amount not found")
        return ApiResponse(data=credit_amount)
    except Exception as e:
        logger.error(f"Error getting credit amount: {e}")
        return ApiResponse(code=500, msg=f"{e}")

@router.post("/", response_model=ApiResponse[CreditAmount])
def create_credit_amount(credit_amount: CreditAmountCreate, db: Session = Depends(get_db)):
    """创建新的积分价格配置"""
    try:
        create_credit_amount = CreditAmountService.create_credit_amount(db, credit_amount)
        return ApiResponse(data=create_credit_amount)
    except Exception as e:
        logger.error(f"Error creating credit amount: {e}")
        return ApiResponse(code=500, msg=f"{e}")

@router.put("/{credit_amount_id}", response_model=ApiResponse[CreditAmount])
def update_credit_amount(credit_amount_id: int, credit_amount: CreditAmountUpdate, db: Session = Depends(get_db)):
    """更新积分价格配置"""
    try:
        updated_credit_amount = CreditAmountService.update_credit_amount(db, credit_amount_id, credit_amount)
        if not updated_credit_amount:
            return ApiResponse(code=404, msg="Credit amount not found")
        return ApiResponse(data=updated_credit_amount)
    except Exception as e:
        logger.error(f"Error updating credit amount: {e}")
        return ApiResponse(code=500, msg=f"{e}")

@router.delete("/{credit_amount_id}")
def delete_credit_amount(credit_amount_id: int, db: Session = Depends(get_db)):
    """删除积分价格配置"""
    try:
        if not CreditAmountService.delete_credit_amount(db, credit_amount_id):
            return ApiResponse(code=404, msg="Credit amount not found")
        return ApiResponse()
    except Exception as e:
        logger.error(f"Error deleting credit amount: {e}")
        return ApiResponse(code=500, msg=f"{e}")