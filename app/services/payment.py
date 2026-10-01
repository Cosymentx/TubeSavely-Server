from datetime import datetime
from typing import Optional, List
from decimal import Decimal, ROUND_HALF_UP
import uuid
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException

from app.models.payment import Payment
from app.models.user import User
from app.services.credit import add_credits
from app.schemas.payment import PaymentCreate

# 支付状态枚举
class PaymentStatus:
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

def generate_order_id() -> str:
    """生成订单号"""
    return f"ORDER{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4().hex)[:6]}"

def validate_amount(amount: Decimal) -> Decimal:
    """验证并格式化金额"""
    if amount <= 0:
        raise ValueError("Amount must be greater than 0")
    # 确保金额精度为2位小数
    return Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def create_payment(
    db: Session,
    user: User,
    payment_create: PaymentCreate
) -> Payment:
    """创建支付订单"""
    try:
        # 验证金额
        validated_amount = validate_amount(payment_create.amount)
        
        db_payment = Payment(
            user_id=user.id,
            order_id=payment_create.order_id,
            amount=validated_amount,
            credits=payment_create.credits,
            payment_method=payment_create.payment_method,
            status=PaymentStatus.PENDING
        )
        db.add(db_payment)
        db.commit()
        db.refresh(db_payment)
        return db_payment
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create payment: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

def get_payment_by_order_id(db: Session, order_id: str) -> Optional[Payment]:
    """通过订单号获取支付订单"""
    return db.query(Payment).filter(Payment.order_id == order_id).first()

def update_payment_status(
    db: Session,
    payment: Payment,
    trade_no: str,
    status: str
) -> Payment:
    """更新支付状态"""
    try:
        payment.trade_no = trade_no
        payment.status = status
        if status == PaymentStatus.COMPLETED:
            payment.paid_at = datetime.utcnow()
            # 支付成功后给用户增加积分
            add_credits(
                db=db,
                user=payment.user,
                credits=payment.credits,
                action="Recharge",
                type=1,
                description=f"Recharge {payment.credits} Credits"
            )
        db.commit()
        db.refresh(payment)
        return payment
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update payment status: {str(e)}"
        )

def get_credit_amount_by_id(db: Session, credit_amount_id: int, currency: str) -> tuple[Decimal, int, str]:
    """从credit_amount表中获取指定积分配置的价格和积分数量"""
    from app.services.credit_amount import CreditAmountService
    
    credit_amount = CreditAmountService.get_credit_amount_by_id(db, credit_amount_id)
    if not credit_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid credit amount configuration. No price configuration found for ID {credit_amount_id}"
        )
    
    # 根据货币类型返回对应价格和积分数量
    if currency.upper() == "CNY":
        return Decimal(str(credit_amount.amount_cny)), credit_amount.credits, credit_amount.creem_product_id
    elif currency.upper() == "USD":
        return Decimal(str(credit_amount.amount_usd)), credit_amount.credits, credit_amount.creem_product_id
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported currency: {currency}"
        )

def get_user_payments(
    db: Session,
    user_id: int,
    offset: int = 0,
    limit: int = 10
) -> List[Payment]:
    """获取用户的支付订单列表"""
    return (
        db.query(Payment)
        .filter(Payment.user_id == user_id)
        .order_by(Payment.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

def verify_payment_sign(data: dict, sign: str) -> bool:
    """验证支付回调签名"""
    # TODO: 实现签名验证逻辑
    return True