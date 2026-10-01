import os
import sys
import logging

# Add the parent directory to the Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import redis.asyncio as redis
from fastapi_limiter import FastAPILimiter

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import http_exception_handler, validation_exception_handler, general_exception_handler
from app.api.v1.api import api_router

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("App is starting up")
    redis_connection = redis.from_url(
        settings.REDIS_URL, encoding="utf8",
        socket_connect_timeout=5, socket_timeout=5,
    )
    initialized = False
    try:
        try:
            await FastAPILimiter.init(redis_connection)
            initialized = True
        except Exception:
            if not os.environ.get("VERCEL"):
                raise
            FastAPILimiter.redis = None
            logger.exception("Redis initialization failed; check REDIS_URL and /api/v1/health")
        yield
    finally:
        if initialized:
            await FastAPILimiter.close()
        else:
            await redis_connection.aclose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "TubeSavely Python API for users, video extraction, credits, and payments.\n\n"
        "Related projects: [Flutter app](https://github.com/Cosymentx/TubeSavely), "
        "[Vue web client](https://github.com/Cosymentx/TubeSavely-Vue), "
        "[Python backend](https://github.com/Cosymentx/TubeSavely-Server)."
    ),
    docs_url=None if settings.PRODUCTION else "/docs",
    redoc_url=None if settings.PRODUCTION else "/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# 添加异常处理器
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Configure CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "Origin"],
        expose_headers=["Location", "Authorization"],  # 重要：暴露Location头
        max_age=3600,
    )

# 添加自定义中间件，用于在重定向过程中保留请求头信息
# app.add_middleware(PreserveHeadersMiddleware)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=9527, reload=True)
