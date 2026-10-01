from contextlib import asynccontextmanager
import json
import logging
import os

import requests
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as redis

from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

from vendor import yt_dlp
from vendor.yt_dlp.extractor.extend import parse_video_share_url
from urllib.parse import urlparse

logger = logging.getLogger(__name__)
REDIS_URL = os.environ.get("REDIS_URL", "")
BACKEND_CORS_ORIGINS = json.loads(os.environ.get("BACKEND_CORS_ORIGINS", "[]"))
if not isinstance(BACKEND_CORS_ORIGINS, list) or not all(
    isinstance(origin, str) for origin in BACKEND_CORS_ORIGINS
):
    raise ValueError("BACKEND_CORS_ORIGINS must be a JSON array of origins")


@asynccontextmanager
async def lifespan(_: FastAPI):
    app.state.limiter_ready = False
    redis_connection = None
    try:
        if REDIS_URL:
            redis_connection = redis.from_url(
                REDIS_URL, encoding="utf8", socket_connect_timeout=5, socket_timeout=5,
            )
            try:
                await FastAPILimiter.init(redis_connection)
                app.state.limiter_ready = True
            except Exception:
                logger.exception("Redis initialization failed; check REDIS_URL")
        else:
            logger.warning("REDIS_URL is unset; request rate limiting is disabled")
        yield
    finally:
        if app.state.limiter_ready:
            await FastAPILimiter.close()
        elif redis_connection is not None:
            await redis_connection.aclose()


app = FastAPI(lifespan=lifespan)
app.state.limiter_ready = False
if BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=BACKEND_CORS_ORIGINS,
        allow_methods=["GET"],
        allow_headers=["Authorization", "Content-Type"],
    )


async def rate_limiter(request: Request, response: Response):
    if not REDIS_URL:
        return
    if not app.state.limiter_ready:
        raise HTTPException(status_code=503, detail="Rate limiting service is unavailable")
    await RateLimiter(times=1, seconds=5)(request, response)


@app.get("/health")
async def health():
    redis_status = "disabled"
    if REDIS_URL:
        redis_status = "unhealthy"
        if app.state.limiter_ready:
            try:
                await FastAPILimiter.redis.ping()
                redis_status = "healthy"
            except Exception:
                pass
    return {
        "status": "unhealthy" if redis_status == "unhealthy" else "healthy",
        "services": {"redis": redis_status},
    }


@app.get("/test", dependencies=[Depends(rate_limiter)])
async def test(params: str):
    return {"hi": params}


@app.get('/parse', dependencies=[Depends(rate_limiter)])
async def parse(url: str):
    try:
        if urlparse(url).scheme in ['http', 'https'] or url.startswith('www.'):
            # if url.__contains__("x.com") or url.__contains__("youtube.com") or url.__contains__(
            #         "youtu.be") or url.__contains__("facebook.com") or url.__contains__("tiktok.com"):
            #     return {'code': 401, 'msg': 'Not Supported'}
            return {'code': 200, 'msg': 'success', 'data': dispatch(url)}
        return {'code': 400, 'msg': f'the parameter {url} is invalid.'}
    except Exception as e:
        return {"code": 500, "msg": f"{str(e)}"}


def dispatch(url: str):
    try:
        data = yt_dlp_parse(url)
        if data is None:
            data = openapi_parse(url)
        return data
    except Exception as e:
        print(f'parse exception {str(e)}')
        raise e


def yt_dlp_parse(url: str):
    try:
        # ydl_opts = {
        #     'format': 'best',  # 你可以根据需要设置不同的选项
        #     'outtmpl': '/Users/Waiting/Downloads/video/video.%(ext)s'  # 设置输出路径模板
        # }
        with yt_dlp.YoutubeDL({'cachedir': False}) as ydl:
            data = ydl.extract_info(url, download=False)
            # ydl.download(url)
            # data = extend_parse(url)
            # 存在播放地址
            if 'formats' in data:
                return data
            else:
                return yt_dlp_extend_parse(url)
    except Exception as e:
        print(f'yt_dlp parse exception {str(e)}')
        return yt_dlp_extend_parse(url)


def yt_dlp_extend_parse(url: str):
    try:
        video_info = parse_video_share_url(share_url=url)
        if hasattr(video_info, 'video_url'):
            data = {
                'title': video_info.title,
                'formats': [{
                    'url': video_info.video_url,
                    "ext": "mp4",
                    "video_ext": "mp4",
                }],
                'url': video_info.video_url,
                'original_url': url,
                'thumbnail': video_info.cover_url,
                'uploader': video_info.author.name
            }
            return data
        else:
            print(f'yt_dlp extend parse exception no video_url field')
            return None
    except KeyError as error:
        print(f'yt_dlp extend parse KeyError exception {str(error)}')
        return None
    except Exception as e:
        print(f'yt_dlp extend parse exception {str(e)}')
        return None


def openapi_parse(url: str):
    response = requests.get(f'https://proxy.layzz.cn/lyz/getAnalyse?token=rzwewdzrckc-auther-523ddd&link={url}')
    json_data = response.json()
    if 'data' in json_data:
        data = {
            'title': json_data['data']['desc'],
            'formats': [{
                'url': json_data['data']['playAddr'],
                "ext": "mp4",
                "video_ext": "mp4",
            }],
            'url': json_data['data']['playAddr'],
            'original_url': url,
            'thumbnail': json_data['data']['cover'],
            'music': json_data['data']['music']
        }
        return data
    if json_data is None:
        response = requests.post('http://api.xiaofany.com/api/v1/remark', params={
            'client_id': "16655792287608",
            'sign': "6B089F0A6E25D98D4196A57CFE0A23F2",
            'url': url
        })
        json_data = response.json()
        if 'data' in json_data:
            data = {
                'title': json_data['data']['desc'],
                'formats': [{
                    'url': json_data['data']['playAddr'],
                    "ext": "mp4",
                    "video_ext": "mp4",
                }],
                'url': json_data['data']['playAddr'],
                'original_url': url,
                'thumbnail': json_data['data']['cover'],
                'music': json_data['data']['music']
            }
            return data
    else:
        print('{}'.format(json_data['message']))
        raise json_data['message']


def main():
    import uvicorn
    uvicorn.run('main:app', host="0.0.0.0", port=9527, reload=True)


if __name__ == '__main__':
    # 运行fastapi程序
    main()
