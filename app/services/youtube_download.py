"""Refresh and download YouTube in one extractor session, including audio."""

import asyncio
import logging
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import quote, urlsplit

import imageio_ffmpeg
from fastapi import HTTPException
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

from app.core.config import settings
from app.vendor import yt_dlp
from app.services.video_runtime import (
    ExtractorLogger, VideoParseError, extraction_error,
    javascript_runtimes, youtube_cookie_file, youtube_proxy, initialize_youtube_guest,
)

logger = logging.getLogger(__name__)


def format_selector(selected, include_audio=True):
    identity = str(selected.get('format_id', ''))
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', identity):
        raise HTTPException(400, 'Invalid YouTube format.')
    if include_audio and selected.get('vcodec') != 'none' and selected.get('acodec') == 'none':
        audio_ext = 'webm' if selected.get('ext') == 'webm' else 'm4a'
        return f'{identity}+bestaudio[ext={audio_ext}]/{identity}+bestaudio'
    return identity


def fetch(original_url, selected, directory, include_audio=True, cached_info=None):
    """Re-extract URLs and use yt-dlp's headers, cookies and chunked downloader."""
    runtime = javascript_runtimes()
    if not runtime:
        raise HTTPException(503, 'The YouTube download runtime is unavailable.')
    deadline = time.monotonic() + 240

    def progress(_):
        if time.monotonic() > deadline:
            raise yt_dlp.utils.DownloadError('YouTube download timed out')

    output_ext = 'webm' if selected.get('ext') == 'webm' else 'mp4'
    options = {
        'quiet': True, 'noprogress': True, 'logger': ExtractorLogger(),
        'cachedir': False, 'noplaylist': True, 'js_runtimes': runtime,
        'socket_timeout': 10, 'retries': 1, 'fragment_retries': 1,
        'extractor_retries': 0, 'http_chunk_size': 5 * 1024 * 1024,
        'format': format_selector(selected, include_audio), 'merge_output_format': output_ext,
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'outtmpl': str(Path(directory) / 'video.%(ext)s'),
        'progress_hooks': [progress], 'proxy': youtube_proxy(),
    }
    with youtube_cookie_file(settings.YOUTUBE_COOKIES_BASE64) as cookies:
        if cookies:
            options['cookiefile'] = cookies
        else:
            options['extractor_args'] = {'youtube': {'player_client': ['visionos']}}
        preferred_proxy = '' if selected.get('direct_download') is True else youtube_proxy()
        attempts = [(preferred_proxy, cached_info)]
        if cached_info:
            attempts.append((preferred_proxy, None))
        if preferred_proxy:
            attempts.append(('', None))
        for attempt, (proxy, current_info) in enumerate(attempts):
            try:
                with yt_dlp.YoutubeDL({**options, 'proxy': proxy}) as downloader:
                    if current_info:
                        downloader.process_ie_result(current_info, download=True)
                    else:
                        if not cookies:
                            initialize_youtube_guest(downloader)
                        downloader.extract_info(original_url, download=True)
                break
            except Exception as error:
                reason = extraction_error(error).reason
                if current_info and '403' in str(error):
                    logger.warning('Cached YouTube stream was refused; refreshing its manifest')
                    continue
                if proxy and reason == 'video_network_error' and attempt + 1 < len(attempts):
                    logger.warning('YouTube download proxy failed; retrying direct')
                    continue
                logger.warning('YouTube native download failed: %s', reason)
                if reason == 'youtube_auth_required':
                    raise HTTPException(503, str(extraction_error(error))) from None
                if reason == 'video_network_error':
                    raise HTTPException(504, 'YouTube download timed out. Please try again.') from None
                raise HTTPException(502, 'YouTube refused the download session. Please check the platform Cookies or server network.') from None
    path = Path(directory) / f'video.{output_ext}'
    if not path.is_file() or not path.stat().st_size:
        # A progressive/audio-only source can have a different native extension.
        candidates = [p for p in Path(directory).glob('video.*') if p.suffix in ('.mp4', '.webm', '.m4a', '.mp3')]
        if len(candidates) != 1:
            raise HTTPException(502, 'YouTube did not produce a complete media file.')
        path = candidates[0]
    return path


async def download(record, selected, include_audio=True):
    temporary = tempfile.TemporaryDirectory(prefix='tubesavely-youtube-')
    cached_formats = []
    for candidate in getattr(record, 'formats', None) or []:
        host = (urlsplit(candidate.get('url') or '').hostname or '').lower()
        if not host.endswith('.googlevideo.com'):
            continue
        safe_headers = {key: value for key, value in (candidate.get('download_headers') or {}).items()
                        if key.lower() in ('user-agent', 'referer', 'origin', 'accept', 'accept-language')
                        and isinstance(value, str) and '\r' not in value and '\n' not in value}
        cached_formats.append({**candidate, 'http_headers': safe_headers})
    cached_info = {'id': getattr(record, 'video_id', None) or 'video',
                   'title': record.title or 'video', 'webpage_url': record.original_url,
                   'extractor': 'youtube', 'formats': cached_formats} if cached_formats and selected.get('download_headers') else None
    try:
        path = await asyncio.to_thread(fetch, record.original_url, selected, temporary.name, include_audio, cached_info)
    except VideoParseError as error:
        temporary.cleanup()
        raise HTTPException(error.code, str(error)) from None
    except BaseException:
        temporary.cleanup()
        raise

    async def body():
        try:
            with path.open('rb') as source:
                while chunk := await asyncio.to_thread(source.read, 256 * 1024):
                    yield chunk
        finally:
            temporary.cleanup()

    title = re.sub(r'[\\/:*?"<>|\x00-\x1f\x7f]', '_', record.title or 'video')[:150]
    extension = path.suffix.lstrip('.')
    media_kind = 'audio' if selected.get('vcodec') == 'none' else 'video'
    mime_type = f'{media_kind}/webm' if extension == 'webm' else ('audio/mp4' if extension == 'm4a' else f'{media_kind}/mp4')
    return StreamingResponse(body(), media_type=mime_type, headers={
        'Content-Disposition': f"attachment; filename=video.{extension}; filename*=UTF-8''{quote(title + path.suffix, safe='')}",
        'Content-Length': str(path.stat().st_size), 'Cache-Control': 'private, no-store',
        'X-Content-Type-Options': 'nosniff',
    }, background=BackgroundTask(temporary.cleanup))
