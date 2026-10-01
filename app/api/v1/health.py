from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from redis.asyncio import Redis
from fastapi_limiter import FastAPILimiter
from sqlalchemy import text

from app.db.session import get_db

router = APIRouter()

@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    health_status = {
        "status": "healthy",
        "services": {
            "database": "unhealthy",
            "redis": "unhealthy"
        }
    }

    try:
        # 检查数据库连接
        db.execute(text("SELECT 1"))
        health_status["services"]["database"] = "healthy"
    except Exception as e:
        print(f'MySQL连接失败：{e}')
        health_status["status"] = "unhealthy"

    try:
        # 检查Redis连接
        redis = FastAPILimiter.redis
        await redis.ping()
        health_status["services"]["redis"] = "healthy"
    except Exception as e:
        print(f'Redis连接失败：{e}')
        health_status["status"] = "unhealthy"

    return health_status