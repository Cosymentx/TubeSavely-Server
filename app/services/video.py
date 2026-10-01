import re
import ipaddress
import socket
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from typing import Dict, Any
import traceback
import logging
from app.vendor import yt_dlp
from app.core.config import settings
from app.services.video_runtime import ExtractorLogger, VideoParseError, extraction_error, is_youtube_url, javascript_runtimes, youtube_cookie_file
from app.services.video_urls import extract_url, platform_of
from app.services import short_video
from app.models.video import Video
from app.schemas.video import VideoCreate, VideoBase, VideoFormatBase
from app.models.user import User
from app.vendor.yt_dlp.extractor.extend import parse_video_share_url
import requests
from app.services.video_transaction import complete_video_transaction
import os


logger = logging.getLogger(__name__)

def _ensure_public_video_url(url: str) -> None:
    """Reject local/private network targets before handing URLs to extractors."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").strip().lower()
    if parsed.scheme not in ("http", "https") or not host:
        raise VideoParseError("video_url_invalid", "请输入有效的视频链接。", 400)
    if host == "localhost" or host.endswith(".localhost"):
        raise VideoParseError("video_url_forbidden", "该视频地址不可访问。", 400)

    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)}
    except socket.gaierror:
        raise VideoParseError("video_url_invalid", "无法解析视频地址。", 400) from None

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise VideoParseError("video_url_forbidden", "该视频地址不可访问。", 400)


async def extract(url: str,
                          current_user: User,
                          db: Session = None):
    """
    解析视频URL，获取视频信息
    """
    try:
        url = extract_url(url)
        _ensure_public_video_url(url)
        if urlparse(url).scheme in ['http', 'https'] or url.startswith('www.'):
            video_data = await dispatch(url)
            if video_data is None:
                return None
            if video_data and current_user:
                if db is None:
                    from app.db.session import SessionLocal
                    db = SessionLocal()
                    should_close_db = True
                else:
                    should_close_db = False
                try:
                    video_base = _create_video_base(video_data)
                    complete_video_transaction(db=db,user=current_user, video_data=video_base)
                    return video_base
                finally:
                    if should_close_db:
                        db.close()
            if video_data:
                return _create_video_base(video_data)
        else:
            return 'the parameter {url} is invalid.'
    except VideoParseError:
        raise
    except Exception as e:
        logger.error(f'extract exception {str(e)}')
        return None


async def dispatch(url: str):
    """
    分发到不同的解析器
    """
    try:
        url = extract_url(url)
        _ensure_public_video_url(url)
        if platform_of(url):
            try:
                return await short_video.parse(url)
            except VideoParseError as error:
                logger.warning('Short video extraction failed: %s', error.reason)
                if error.code != 503 or error.reason.endswith('cookies_invalid'):
                    raise
                try:
                    return await yt_dlp_parse(url)
                except VideoParseError:
                    raise error from None
        data = await yt_dlp_parse(url)
        if data is None:
            data = openapi_parse(url)
        return data
    except VideoParseError:
        raise
    except Exception as e:
        logger.error(f'dispatch exception {str(e)}')
        return None


async def yt_dlp_parse(url: str):
    if platform_of(url):
        # The same per-platform cookie/proxy configuration also reaches yt-dlp.
        return await _yt_dlp_parse(url)
    encoded = settings.YOUTUBE_COOKIES_BASE64 if is_youtube_url(url) else ''
    with youtube_cookie_file(encoded) as cookiefile:
        return await _yt_dlp_parse(url, cookiefile)


async def _yt_dlp_parse(url: str, cookie_override=None):
    """
    使用yt-dlp解析视频信息
    """
    try:
        cookies_file = cookie_override or _get_cookies_file(url)
        runtimes = javascript_runtimes()
        if is_youtube_url(url) and not runtimes:
            raise VideoParseError('video_runtime_missing', '服务器的视频解析运行环境不可用，请管理员检查 Deno 构建配置。')
        logger.info('yt-dlp JavaScript runtime: %s', ','.join(runtimes) or 'unavailable')

        ydl_opts = {
            'quiet': True,
            'logger': ExtractorLogger(),
            'cachedir': False,
            'js_runtimes': runtimes,
            'socket_timeout': 8,
            'extractor_retries': 0,
            'extract_flat': False,  # 修改为False以获取完整的formats信息
            'force_generic_extractor': False,
             'proxy': settings.VIDEO_PROXY,
        }

        platform = platform_of(url)
        if platform:
            ydl_opts['proxy'] = short_video.platform_proxy(platform) or ''
            ydl_opts['http_headers'] = {'User-Agent': short_video.USER_AGENT}

        # 如果存在对应的cookies文件，添加到配置中
        if cookies_file:
            ydl_opts['cookiefile'] = cookies_file
            logger.info('A platform cookie file is configured')
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if platform:
                for cookie in short_video.load_cookies(platform):
                    ydl.cookiejar.set_cookie(cookie)
            try:
                try:
                    data = ydl.extract_info(url, download=False)
                except Exception as first_error:
                    if is_youtube_url(url) and settings.VIDEO_PROXY and extraction_error(first_error).reason == 'video_network_error':
                        logger.warning('Configured video proxy failed; trying a direct connection')
                        with yt_dlp.YoutubeDL({**ydl_opts, 'proxy': ''}) as direct_ydl:
                            data = direct_ydl.extract_info(url, download=False)
                    else:
                        raise
                if 'formats' in data and len(data['formats']) > 0:
                    # 确保返回的数据包含所有必要字段
                    if 'id' in data:
                        data['video_id'] = data['id']
                    else:
                        data['video_id'] = str(hash(url))

                    # 处理formats信息
                    processed_formats = []
                    for format in data['formats']:
                        # 只处理包含视频流的格式
                        if format.get('vcodec') != 'none':
                            processed_format = {
                                'format_id': format.get('format_id'),
                                'format_note': format.get('format_note'),
                                'ext': format.get('ext'),
                                'height': format.get('height'),
                                'width': format.get('width'),
                                'filesize': format.get('filesize'),
                                'filesize_approx': format.get('filesize_approx'),
                                'fps': format.get('fps'),
                                'tbr': format.get('tbr'),
                                'url': format.get('url'),
                                'vcodec': format.get('vcodec'),
                                'acodec': format.get('acodec'),
                                'dynamic_range': format.get('dynamic_range'),
                                'resolution': format.get('resolution')
                            }
                            # 确保格式包含分辨率信息
                            # if processed_format['height'] or processed_format['width']:
                            processed_formats.append(processed_format)

                    # 按分辨率降序排序
                    processed_formats.sort(key=lambda x: x['height'] or 0, reverse=True)

                    # 添加必需的url字段
                    data['url'] = url
                    logger.info(f'yt_dlp extract success {data.get("title", "")}')
                    formats_dict = [VideoFormatBase(**format_data) for format_data in processed_formats]
                    # 然后在返回前将它们转换为字典
                    formats_serializable = [format_obj.dict() for format_obj in formats_dict]
                    return {
                        'url': url,
                        'video_id': data['video_id'],
                        'title': data.get('title', ''),
                        'description': data.get('description'),
                        'thumbnail': data.get('thumbnail', ''),
                        'duration': str(int(data.get('duration') or 0)),
                        'platform': platform or data.get('platform',''),
                        'formats': formats_serializable,
                        'view_count' : str(data.get('view_count') if data.get('view_count') is not None else 0),
                        'like_count': str(data.get('like_count') if data.get('like_count') is not None else 0),
                        'author': data.get('uploader', '')
                    }
                else:
                    if platform:
                        raise short_video.failure(platform, 'upstream_changed')
                    logger.info('yt_dlp parse no formats found, trying extend parse')
                    return await yt_dlp_extend_parse(url)
            except Exception as e:
                if platform:
                    if isinstance(e, VideoParseError):
                        raise
                    raise short_video.failure(platform, 'risk_control') from None
                if is_youtube_url(url):
                    error = extraction_error(e)
                    logger.warning('YouTube extraction failed: %s', error.reason)
                    raise error from None
                logger.error('yt-dlp extraction failed (%s)', type(e).__name__)
                return await yt_dlp_extend_parse(url)
    except VideoParseError:
        raise
    except Exception as e:
        if platform_of(url):
            raise short_video.failure(platform_of(url), 'upstream_changed') from None
        if is_youtube_url(url):
            if isinstance(e, FileNotFoundError):
                raise VideoParseError('video_runtime_missing', '服务器的视频解析运行环境不可用，请管理员检查 Deno 构建配置。') from None
            raise extraction_error(e) from None
        logger.error('yt-dlp initialization failed (%s)', type(e).__name__)
        return await yt_dlp_extend_parse(url)


async def yt_dlp_extend_parse(url: str):
    """
    使用扩展的yt-dlp解析器解析视频信息
    """
    try:
        video_url = extract_url(url)
        if platform_of(video_url):
            return await short_video.parse(video_url)
        video_info = await parse_video_share_url(share_url=video_url)
        if hasattr(video_info, 'video_url'):
            formats = [{
                'url': video_info.video_url,
                'ext': 'mp4',
                'video_ext': 'mp4',
                'height': 720,  # 添加默认分辨率
                'width': 1280,
                'format_id': 'default',
                'format_note': 'default',
                'filesize': None,
                'filesize_approx': None,
                'fps': None,
                'tbr': None,
                'vcodec': 'h264',
                'acodec': 'aac',
                'dynamic_range': None,
                'resolution': '720p'
            }]

            data = {
                'title': video_info.title,
                'formats': formats,
                'url': video_url,
                'thumbnail': video_info.cover_url or '',
                'duration': '0',  # 添加默认时长,
                'author': video_info.author.name,
                'author_url': video_info.author.avatar ,
                'video_id': str(hash(video_info.video_url)),
                'description': video_info.title
            }
            logger.info('yt_dlp extend extract success')
            return data
        else:
            logger.error(f'yt_dlp extend parse exception no video_url field')
            return None
    except VideoParseError:
        raise
    except KeyError as error:
        logger.error(f'yt_dlp extend parse KeyError exception {str(error)}')
        return None
    except Exception as e:
        logger.error(f'yt_dlp extend parse exception {str(e)}')
        return None


def openapi_parse(url: str):
    """
    使用第三方API解析视频信息
    """
    if not settings.EXTERNAL_PARSE_TOKEN:
        return None
    response = requests.get('https://proxy.layzz.cn/lyz/getAnalyse',
                            params={'token': settings.EXTERNAL_PARSE_TOKEN, 'link': url}, timeout=20)
    json_data = response.json()
    if 'data' in json_data:
        data = {
            'title': json_data['data']['desc'],
            'formats': [{
                'url': json_data['data']['playAddr'],
                "ext": "mp4",
                "video_ext": "mp4",
                "height": 720,  # 添加默认分辨率
                "width": 1280,
                "format_id": "default",
                "format_note": "default"
            }],
            'url': json_data['data']['playAddr'],
            'thumbnail': json_data['data']['cover'],
            'music': json_data['data']['music'],
            'video_id': str(hash(json_data['data']['playAddr'])),
            'view_count': '0',
            'like_count': '0',
            'duration': '0'  # 添加默认时长
        }
        return data
    if json_data is None:
        response = requests.post('http://api.xiaofany.com/api/v1/remark', params={
            'client_id': settings.FALLBACK_PARSE_CLIENT_ID,
            'sign': settings.FALLBACK_PARSE_SIGN,
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
                    "height": 720,  # 添加默认分辨率
                    "width": 1280,
                    "format_id": "default",
                    "format_note": "default"
                }],
                'url': json_data['data']['playAddr'],
                'original_url': url,
                'thumbnail': json_data['data']['cover'],
                'music': json_data['data']['music'],
                'video_id': str(hash(json_data['data']['playAddr'])),
                'view_count': '0',
                'like_count': '0',
                'duration': '0'  # 添加默认时长
            }
            return data
    else:
        logger.error('{}'.format(json_data['message']))
        return None

def _create_video_base(video_data: dict) -> VideoBase:
    """创建VideoBase对象的辅助函数"""
    return VideoBase(
        url=video_data.get('url'),
        title=video_data.get('title', ''),
        description=video_data.get('description', ''),
        thumbnail=video_data.get('thumbnail', ''),
        duration=video_data.get('duration', '0'),
        formats=video_data.get('formats', []),
        video_id=str(video_data.get('video_id')),
        view_count=video_data.get('view_count', '0'),
        like_count=video_data.get('like_count', '0'),
        author=video_data.get('author', ''),
        platform=video_data.get('platform'),
    )

def create_video(
    video_in: VideoCreate,
    current_user: User
) -> Video:
    """Create new video"""
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        video = Video(
            url=video_in.url,
            title=video_in.title,
            description=video_in.description,
            thumbnail=video_in.thumbnail,
            duration=video_in.duration,
            platform=video_in.platform,
            user_id=current_user.id,
            credits_cost=video_in.credits_cost
        )
        db.add(video)
        db.commit()
        db.refresh(video)
        return video
    finally:
        db.close()


def get_video_history(
    db: Session,
    user: User,
    offset: int = 1,
    limit: int = 20,
) -> Dict[str, Any]:
    """Get user's videos with pagination"""
    from app.db.session import SessionLocal
    from math import ceil
    from typing import Dict, Any

    if offset < 1:
        offset = 1

    db = SessionLocal()
    try:
        query = db.query(Video).filter(Video.users.any(id=user.id))

        total = query.count()
        pages = ceil(total / limit)

        records = query.order_by(Video.created_at.desc())\
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
    finally:
        db.close()


def delete(id: int, current_user: User, db: Session = None) -> bool:
    """根据ID删除视频"""
    if db is None:
        from app.db.session import SessionLocal
        db = SessionLocal()
        should_close_db = True
    else:
        should_close_db = False

    try:
        # 查询视频是否存在
        video = db.query(Video).filter(Video.id == id).first()
        if not video:
            return False

        # 验证用户是否有权限删除该视频
        if not db.query(Video).join(Video.users).filter(Video.id == id, User.id == current_user.id).first():
            return False

        # 删除视频记录
        db.delete(video)
        db.commit()
        return True
    except Exception as e:
        logger.error(f'delete video exception {str(e)}')
        db.rollback()
        return False
    finally:
        if should_close_db:
            db.close()

def _get_cookies_file(url: str) -> str:
    """根据URL获取对应平台的cookies文件路径"""
    # 获取当前文件的绝对路径
    current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    if "youtube.com" in url or "youtu.be" in url:
        cookie_path = os.path.join(current_dir, "cookies", "youtube.txt")
    elif "tiktok.com" in url:
        cookie_path = os.path.join(current_dir, "cookies", "tiktok.txt")
    elif "douyin.com" in url:
        cookie_path = os.path.join(current_dir, "cookies", "douyin.txt")
    else:
        return None

    # 检查文件是否存在且可读
    if os.path.isfile(cookie_path) and os.access(cookie_path, os.R_OK):
        logger.info(f"Using cookies file: {cookie_path}")
        return cookie_path
    else:
        logger.debug('No platform cookie file is available')
        return None

async def test_proxy_connection():
    """
    测试代理连接是否正常工作
    """
    try:
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # 一个流行的YouTube视频
        logger.info("开始测试代理连接...")

        # 使用代理的配置
        proxy_opts = {
            'quiet': False,
            'verbose': True,
            'proxy': settings.VIDEO_PROXY,  # 使用你配置的代理
            'skip_download': True,
            'format': 'best',
            'dumpjson': True,
        }

        # 不使用代理的配置
        no_proxy_opts = {
            'quiet': False,
            'verbose': True,
            'skip_download': True,
            'format': 'best',
            'dumpjson': True,
        }

        # 测试使用代理
        logger.info("使用代理测试...")
        with yt_dlp.YoutubeDL(proxy_opts) as ydl:
            try:
                info = ydl.extract_info(test_url, download=False)
                if info and 'title' in info:
                    logger.info(f"使用代理成功获取视频信息: {info.get('title')}")
                    logger.info("代理配置正常工作!")
                    return True
                else:
                    logger.error("使用代理无法获取视频信息")
            except Exception as e:
                logger.error(f"使用代理测试失败: {str(e)}")

        # 测试不使用代理
        logger.info("不使用代理测试...")
        with yt_dlp.YoutubeDL(no_proxy_opts) as ydl:
            try:
                info = ydl.extract_info(test_url, download=False)
                if info and 'title' in info:
                    logger.info(f"不使用代理成功获取视频信息: {info.get('title')}")
                    logger.info("直接连接正常工作，但代理可能有问题")
                else:
                    logger.error("不使用代理也无法获取视频信息，可能是网络问题")
            except Exception as e:
                logger.error(f"不使用代理测试失败: {str(e)}")

        return False
    except Exception as e:
        logger.error(f"代理测试过程中发生错误: {str(e)}")
        return False
