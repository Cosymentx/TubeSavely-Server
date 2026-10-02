"""Runtime lookup and safe, actionable extraction errors."""

from pathlib import Path
from contextlib import contextmanager
import base64
import binascii
import logging
import os
import shutil
import tempfile
import json
from urllib.parse import urlparse

from deno import find_deno_bin


class VideoParseError(Exception):
    def __init__(self, reason, message, code=503):
        super().__init__(message)
        self.reason = reason
        self.code = code


class ExtractorLogger:
    def debug(self, message):
        pass

    def warning(self, message):
        logging.getLogger(__name__).debug('yt-dlp warning: %s', extraction_error(message).reason)

    def error(self, message):
        logging.getLogger(__name__).warning('yt-dlp error: %s', extraction_error(message).reason)


def is_youtube_url(url):
    hostname = (urlparse(url).hostname or '').lower()
    return hostname == 'youtu.be' or hostname == 'youtube.com' or hostname.endswith('.youtube.com')


def youtube_proxy():
    from app.core.config import settings
    return settings.VIDEO_PROXY if settings.YOUTUBE_PROXY is None else settings.YOUTUBE_PROXY


def initialize_youtube_guest(downloader):
    """Initialize public visitor data in the same HTTP session as playback.

    Protocol reference: YoutubeExplode VideoController.ResolveVisitorDataAsync.
    This provides an anonymous visitor identity, not an authenticated login.
    """
    from app.vendor.yt_dlp.networking import Request
    try:
        with downloader.urlopen(Request('https://www.youtube.com/sw.js_data', headers={
            'Accept': 'application/json',
            'User-Agent': 'com.google.android.youtube/20.10.38 (Linux; U; ANDROID 11) gzip',
        })) as response:
            raw = response.read(1024 * 1024).decode('utf-8')
        if raw.startswith(")]}'"):
            raw = raw[4:]
        visitor = json.loads(raw)[0][2][0][0][13]
        if not isinstance(visitor, str) or not visitor:
            return
        arguments = downloader.params.setdefault('extractor_args', {}).setdefault('youtube', {})
        arguments['visitor_data'] = [visitor]
        arguments['player_skip'] = ['webpage', 'configs']
    except Exception:
        logging.getLogger(__name__).debug('YouTube guest initialization unavailable')


def javascript_runtimes():
    executable = 'deno.exe' if os.name == 'nt' else 'deno'
    bundled = Path(__file__).resolve().parents[1] / 'runtime_bin' / executable
    candidates = [str(bundled), shutil.which('deno')]
    try:
        candidates.append(str(find_deno_bin()))
    except FileNotFoundError:
        pass
    for path in candidates:
        if path and Path(path).is_file() and os.access(path, os.X_OK):
            return {'deno': {'path': path}}
    node = shutil.which('node')
    return {'node': {'path': node}} if node else {}


@contextmanager
def youtube_cookie_file(encoded):
    """Materialize encrypted configuration only in a private temporary file."""
    filename = None
    try:
        if not encoded:
            yield None
            return
        try:
            text = base64.b64decode(encoded.strip(), validate=True).decode('utf-8')
        except (binascii.Error, UnicodeDecodeError, ValueError):
            raise VideoParseError('youtube_cookies_invalid', 'YouTube Cookies 配置格式无效，请管理员检查 YOUTUBE_COOKIES_BASE64。') from None
        lines = text.splitlines()
        if not lines or 'HTTP Cookie File' not in lines[0]:
            raise VideoParseError('youtube_cookies_invalid', 'YouTube Cookies 必须使用 Netscape 格式导出。')
        records = 0
        for line in lines[1:]:
            if not line.strip() or (line.startswith('#') and not line.startswith('#HttpOnly_')):
                continue
            fields = line.split('\t')
            if len(fields) != 7 or fields[1] not in {'TRUE', 'FALSE'} or fields[3] not in {'TRUE', 'FALSE'} or (fields[4] and not fields[4].lstrip('-').isdigit()):
                raise VideoParseError('youtube_cookies_invalid', 'YouTube Cookies 数据格式无效，请重新导出 Netscape Cookie 文件。')
            records += 1
        if not records:
            raise VideoParseError('youtube_cookies_invalid', 'YouTube Cookies 文件为空，请导出有效的 Cookie 数据。')
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', prefix='youtube-cookies-', suffix='.txt', delete=False) as file:
            filename = file.name
            file.write(text)
        yield filename
    finally:
        if filename:
            Path(filename).unlink(missing_ok=True)


def extraction_error(error):
    detail = str(error).lower()
    if 'confirm' in detail and ('not a bot' in detail or 'sign in' in detail):
        return VideoParseError('youtube_auth_required', 'YouTube 要求登录验证。请管理员配置有效的 YouTube Cookies 或检查服务器出口网络。')
    if any(message in detail for message in ['timed out', 'proxyerror', 'unable to connect', 'connection refused', 'connection reset']):
        return VideoParseError('video_network_error', '视频平台连接失败或超时，请稍后重试，并检查服务器代理与网络。')
    if 'private video' in detail:
        return VideoParseError('youtube_private_video', '该 YouTube 视频为私有视频，当前解析会话没有访问权限。', 403)
    if 'video unavailable' in detail or 'video is unavailable' in detail:
        return VideoParseError('youtube_video_unavailable', 'YouTube 当前无法提供该视频，请确认视频仍可播放及地区访问权限。', 404)
    return VideoParseError('youtube_extraction_failed', 'YouTube 视频解析失败，请稍后重试；管理员可查看解析日志定位原因。')
