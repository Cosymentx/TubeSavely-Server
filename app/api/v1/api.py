from fastapi import APIRouter
from app.api.v1 import health

from .endpoints import auth, user, video, oauth, feedback, credit_amount, credit, payment, task

api_router = APIRouter()

# 添加健康检查路由
api_router.include_router(health.router, tags=["health"])

# Auth routes
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(oauth.router, prefix="/auth/oauth", tags=["oauth"])

# Resource routes
api_router.include_router(user.router, prefix="/users", tags=["users"])
api_router.include_router(video.router, prefix="/videos", tags=["videos"])
api_router.include_router(task.router, prefix="/tasks", tags=["tasks"])

# Business routes
api_router.include_router(credit_amount.router, prefix="/credit_amount", tags=["credit_amount"])
api_router.include_router(credit.router, prefix="/credits", tags=["credits"])
api_router.include_router(payment.router, prefix="/payments", tags=["payments"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
