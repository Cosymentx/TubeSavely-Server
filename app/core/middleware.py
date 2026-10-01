from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse
import logging

logger = logging.getLogger(__name__)

class PreserveHeadersMiddleware(BaseHTTPMiddleware):
    """
    自定义中间件，用于在重定向过程中保留请求头信息，特别是Authorization头
    同时将重定向响应转换为200响应，防止客户端自动跟随重定向
    """
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # 检查是否是重定向响应
        if 300 <= response.status_code < 400:
            logger.debug(f"处理重定向响应: {response.status_code}")
            
            # 获取重定向目标URL
            redirect_url = None
            if 'location' in response.headers:
                redirect_url = response.headers['location']
            
            # 创建包含重定向信息但状态码为200的响应
            new_response = JSONResponse(
                status_code=200,  # 将重定向状态码改为200
                content={
                    "code": 200,
                    "msg": "重定向已被拦截",
                    "data": {"original_status": response.status_code, "redirect_url": redirect_url}
                }
            )
            
            # 获取原始请求中的Authorization头
            auth_header = request.headers.get("Authorization")
            if auth_header:
                logger.debug("在重定向中保留Authorization头")
                new_response.headers["Authorization"] = auth_header
                
                # 确保CORS头信息允许Authorization头
                new_response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
                new_response.headers["Access-Control-Expose-Headers"] = "Authorization"
            
            # 保留原始响应中的其他头信息（除了location和content-length）
            for header_name, header_value in response.headers.items():
                if header_name.lower() not in ['location', 'content-length']:  # 不添加location头和content-length头
                    new_response.headers[header_name] = header_value
            return new_response
        return response