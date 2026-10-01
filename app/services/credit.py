from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from math import ceil
from app.models.user import User
from app.models.credit import Credit
import logging

logger = logging.getLogger(__name__)

class InsufficientCreditsError(Exception):
    pass

def add_credits(
    db: Session,
    user: User,
    credits: int,
    action: str,
    type: int,
    description: Optional[str] = None
) -> None:
    """Add credits to user's account"""
    user.credits += credits
    credit_history = Credit(
        user_id=user.id,
        credits=credits,
        action=action,
        type=type,
        description=description
    )
    db.add(credit_history)
    db.commit()
    db.refresh(user)

def deduct_credits(
    db: Session,
    user: User,
    credits: int,
    action: str,
    description: Optional[str] = None
) -> None:
    """Deduct credits from user's account"""
    if user.credits < credits:
        raise InsufficientCreditsError("Insufficient credits for this operation")
    
    user.credits -= credits
    credit_history = Credit(
        user_id=user.id,
        credits=-credits,
        action=action,
        description=description
    )
    db.add(credit_history)
    db.commit()
    db.refresh(user)

def get_credit_history(
    db: Session,
    user: User,
    offset: int = 1,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Get user's credit history with pagination
    
    Returns:
        Dict containing:
        - records: List of credit records
        - total: Total number of records
        - size: Page size
        - current: Current page number
        - pages: Total number of pages
    """
    if offset < 1:
        offset = 1
    
    query = db.query(Credit).filter(Credit.user_id == user.id)
    
    total = query.count()
    
    pages = ceil(total / limit)
    
    records = query.order_by(Credit.created_at.desc())\
        .offset((offset - 1) * limit)\
        .limit(limit)\
        .all()
    
    return {
        "records": records,
        "total": total,
        "size": limit,
        "current": offset,
        "pages": pages
    }

def get_user_credits(db: Session, user: User) -> int:
    """Get current credits balance for a user"""
    return user.credits