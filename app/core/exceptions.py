from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
import traceback
from typing import Any

from .config import settings

logger = logging.getLogger(__name__)

def create_error_response(status_code: int, message: str, data: Any = None) -> dict:
    """
    创建统一的错误响应格式
    """
    return {
        "code": status_code,
        "msg": message,
        "data": data
    }

async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    处理HTTP异常
    """
    logger.error(f"HTTP Exception: {exc.detail}")
    # 保留原始状态码，特别是对于重定向状态码，这样可以确保Authorization头被正确传递
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(exc.status_code, str(exc.detail))
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    处理请求参数验证异常
    """
    logger.error(f"Validation error: {str(exc)}")
    return JSONResponse(
        status_code=200,
        content=create_error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Invalid request parameters",
            {"errors": exc.errors()}
        )
    )

async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    处理所有其他异常
    """
    error_msg = f"Internal server error: {str(exc)}"
    logger.error(error_msg)
    logger.error(traceback.format_exc())
    
    return JSONResponse(
        status_code=200,
        content=create_error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_msg,
            {"traceback": traceback.format_exc()} if not settings.PRODUCTION else None
        )
    )