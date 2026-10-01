from calendar import c
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.credit_amount import CreditAmount
from app.schemas.credit_amount import CreditAmountCreate, CreditAmountUpdate
from app.services.payments import creem

class CreditAmountService:
    @staticmethod
    def get_credit_amounts(db: Session, skip: int = 0, limit: int = 100) -> List[CreditAmount]:
        return db.query(CreditAmount).offset(skip).limit(limit).all()

    @staticmethod
    def get_active_credit_amounts(db: Session) -> List[CreditAmount]:
        return db.query(CreditAmount).filter(CreditAmount.is_active == True).all()

    @staticmethod
    def get_credit_amount_by_id(db: Session, credit_amount_id: int) -> Optional[CreditAmount]:
        return db.query(CreditAmount).filter(CreditAmount.id == credit_amount_id).first()

    @staticmethod
    def create_credit_amount(db: Session, credit_amount: CreditAmountCreate) -> CreditAmount:
        db_credit_amount = CreditAmount(
            credits=credit_amount.credits,
            amount_cny=credit_amount.amount_cny,
            amount_usd=credit_amount.amount_usd,
            creem_product_id=credit_amount.creem_product_id,
            is_active=credit_amount.is_active
        )
        db.add(db_credit_amount)
        db.commit()
        db.refresh(db_credit_amount)
        return db_credit_amount

    @staticmethod
    def update_credit_amount(db: Session, credit_amount_id: int, credit_amount: CreditAmountUpdate) -> Optional[CreditAmount]:
        db_credit_amount = CreditAmountService.get_credit_amount_by_id(db, credit_amount_id)
        if not db_credit_amount:
            return None

        update_data = credit_amount.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_credit_amount, field, value)

        db.commit()
        db.refresh(db_credit_amount)
        return db_credit_amount

    @staticmethod
    def delete_credit_amount(db: Session, credit_amount_id: int) -> bool:
        db_credit_amount = CreditAmountService.get_credit_amount_by_id(db, credit_amount_id)
        if not db_credit_amount:
            return False

        db.delete(db_credit_amount)
        db.commit()
        return True