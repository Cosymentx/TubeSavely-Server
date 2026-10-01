from typing import List
import logging
from fastapi import APIRouter, Depends, Request, Response, HTTPException
from sqlalchemy.orm import Session
from fastapi_limiter.depends import RateLimiter
from fastapi_limiter import FastAPILimiter
from app.core import deps
from app.schemas.user import User
from app.schemas.video import Video, VideoCreate, VideoBase
from app.schemas.response import ApiResponse
from app.schemas.paging import PageResponse
from app.services.video import (
    extract,
    get_video_history,
    create_video as create_video_service,
    delete,
    test_proxy_connection
)
from app.services.video_runtime import VideoParseError

router = APIRouter()
logger = logging.getLogger(__name__)

async def rate_limiter(request: Request, response: Response):
    if FastAPILimiter.redis is None:
        raise HTTPException(status_code=503, detail="Rate limiting service is unavailable")
    await RateLimiter(times=1, seconds=5)(request, response)


@router.get("/parse", dependencies=[Depends(rate_limiter)], response_model=ApiResponse[VideoBase])
async def parse(
        url: str,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_user)
):
    """Parse video URL to get video information"""
    try:
        logger.info(f"comming here: {url}")
        if not url:
            return ApiResponse(
                code=400,
                msg="Please enter a video URL",
                data=None
            )

        data = await extract(url, current_user, db)
        if not data:
            return ApiResponse(
                code=400,
                msg="Unable to parse video URL, please ensure the URL is correct",
                data=None
            )

        return ApiResponse(data=data)
    except VideoParseError as e:
        logger.warning('Video extraction refused: %s', e.reason)
        return ApiResponse(code=e.code, msg=str(e), data=None)
    except Exception as e:
        logger.error(f"Error parsing video URL: {str(e)}")
        return ApiResponse(
            code=500,
            msg="Error parsing video URL, please try again later",
            data=None
        )

@router.post("/", response_model=ApiResponse[Video])
def create_video(
        video_in: VideoCreate,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_user)
):
    """Create new video"""
    try:
        if not video_in.url:
            return ApiResponse(
                code=400,
                msg="Video URL cannot be empty",
                data=None
            )

        # Check if user has enough credits
        if current_user.credits < video_in.credits_cost:
            return ApiResponse(
                code=400,
                msg="Insufficient credits to download this video",
                data=None
            )

        video = create_video_service(db, video_in, current_user)
        return ApiResponse(data=video)
    except Exception as e:
        logger.error(f"Error creating video: {str(e)}")
        return ApiResponse(
            code=500,
            msg="Failed to create video record, please try again later",
            data=None
        )

@router.delete("/{id}", response_model=ApiResponse)
def delete_video(
        id: int,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_user)
):
    """Delete video"""
    try:
        success = delete(id, current_user, db)
        if not success:
            return ApiResponse(
                code=400,
                msg="Failed to delete video, please ensure the video exists and you have permission to delete it",
            )
        return ApiResponse()
    except Exception as e:
        logger.error(f"Error deleting video: {str(e)}")
        return ApiResponse(
            code=500,
            msg="Failed to delete video, please try again later",
        )

@router.get("/history", response_model=ApiResponse[PageResponse[Video]])
def read_video_history(
        offset: int = 1,
        limit: int = 20,
        db: Session = Depends(deps.get_db),
        current_user: User = Depends(deps.get_current_user)
):
    """Get current user's videos"""
    try:
        videos = get_video_history(db, current_user, offset, limit)
        return ApiResponse(data=videos)
    except Exception as e:
        logger.error(f"Error fetching user videos: {str(e)}")
        return ApiResponse(
            code=500,
            msg="Failed to fetch video list, please try again later",
        )

@router.get("/test-proxy", response_model=ApiResponse)
async def test_proxy():
    """测试代理连接是否正常工作"""
    try:
        result = await test_proxy_connection()
        if result:
            return ApiResponse(
                data={"status": "success", "message": "代理连接正常工作"}
            )
        else:
            return ApiResponse(
                code=400,
                msg="代理连接测试失败，请检查日志获取详细信息",
                data={"status": "failed"}
            )
    except Exception as e:
        logger.error(f"Error testing proxy: {str(e)}")
        return ApiResponse(
            code=500,
            msg=f"测试代理时发生错误: {str(e)}",
            data={"status": "error"}
        )
