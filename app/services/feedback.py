from sqlalchemy.orm import Session
from app.models.feedback import Feedback
from app.schemas.feedback import FeedbackCreate

def create_feedback(db: Session, feedback: FeedbackCreate, ip_address: str, user_id: int) -> Feedback:
    db_feedback = Feedback(
        name=feedback.name,
        email=feedback.email,
        content=feedback.content,
        ip_address=ip_address,
        type=feedback.type,
        user_id=user_id
    )   
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback
