from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.core import deps
from app.schemas.feedback import FeedbackCreate, Feedback
from app.services.feedback import create_feedback
from app.models.user import User
from app.schemas.response import ApiResponse

router = APIRouter()

@router.post("/", response_model=ApiResponse)
def submit_feedback(
    request: Request,
    feedback: FeedbackCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Submit feedback
    """
    try:
        # 获取客户端IP地址
        client_ip = request.client.host
        # 如果使用了代理，尝试从X-Forwarded-For获取真实IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
                    
        result = create_feedback(db=db, feedback=feedback, ip_address=client_ip, user_id=current_user.id)
        if not result:
            return ApiResponse(code=400, msg="Failed to submit feedback")
        else:
            return ApiResponse()
    except Exception as e:
        return ApiResponse(code=500, msg=str(e))
