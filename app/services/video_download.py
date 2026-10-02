"""Stream an already purchased parse result without charging a second time."""

import asyncio
import ipaddress
import re
import socket
from urllib.parse import quote, urljoin, urlsplit

from curl_cffi import requests
from fastapi import HTTPException
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse

from app.models.video import Video
from app.services.short_video import USER_AGENT, platform_proxy
from app.services.video_urls import extract_url, platform_of
from app.services.video_runtime import is_youtube_url
from app.services import youtube_download


async def public_media_url(url):
    try:
        parts = urlsplit(url)
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password or parts.port not in (None, 80, 443):
            raise ValueError
        addresses = await asyncio.to_thread(socket.getaddrinfo, parts.hostname, parts.port or (443 if parts.scheme == 'https' else 80), type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(entry[4][0]).is_global for entry in addresses):
            raise ValueError
    except (ValueError, OSError):
        raise HTTPException(400, 'The media address is not publicly accessible.') from None


def owned_format(db, user_id, original_url, format_id):
    record = db.query(Video).filter(
        Video.users.any(id=user_id), Video.original_url == extract_url(original_url),
    ).order_by(Video.created_at.desc(), Video.id.desc()).first()
    if record is None:
        raise HTTPException(404, 'Please parse this video before downloading it.')
    selected = next((entry for entry in (record.formats or []) if entry.get('format_id') == format_id), None)
    if not selected or not selected.get('url'):
        raise HTTPException(404, 'This format is unavailable. Please parse the video again.')
    if not is_youtube_url(record.original_url) and urlsplit(selected['url']).path.lower().endswith(('.m3u8', '.mpd')):
        raise HTTPException(422, 'Select a direct media format for browser download.')
    return record, selected


async def download(db, user_id, original_url, format_id, include_audio=True):
    record, selected = owned_format(db, user_id, original_url, format_id)
    if is_youtube_url(record.original_url):
        return await youtube_download.download(record, selected, include_audio, user_id=user_id)
    platform = platform_of(record.original_url)
    headers = {'User-Agent': USER_AGENT, 'Accept-Encoding': 'identity'}
    if platform:
        headers['Referer'] = f'https://www.{platform}.com/'
    session = requests.AsyncSession(
        impersonate='chrome131', headers=headers, trust_env=False,
        proxy=(platform_proxy(platform) or None) if platform else None,
        timeout=(10, 240), max_clients=1,
    )
    response = None
    closed = False

    async def close():
        nonlocal closed
        if closed:
            return
        closed = True
        if response is not None:
            if getattr(response, 'quit_now', None) is not None:
                response.quit_now.set()
            await response.aclose()
        await session.close()

    try:
        url = selected['url']
        for _ in range(6):
            await public_media_url(url)
            response = await session.get(url, stream=True, allow_redirects=False)
            if response.status_code in (301, 302, 303, 307, 308):
                target = response.headers.get('location')
                await response.aclose()
                response = None
                if not target:
                    raise HTTPException(502, 'The video platform returned an invalid redirect.')
                url = urljoin(url, target)
                continue
            break
        else:
            raise HTTPException(502, 'The video platform returned too many redirects.')
        if response.status_code not in (200, 206):
            raise HTTPException(502, 'The video address expired or was refused. Please parse it again.')
        media_type = response.headers.get('content-type', '').split(';')[0].strip().lower()
        if not media_type.startswith(('video/', 'audio/')) and media_type not in ('application/octet-stream', 'binary/octet-stream'):
            raise HTTPException(502, 'The platform returned a web page instead of a video file.')
        iterator = response.aiter_content()
        first = await anext(iterator, b'')
        if not first or first.lstrip().lower().startswith((b'<!doctype', b'<html', b'<?xml', b'{', b'[')):
            raise HTTPException(502, 'The platform did not return a valid media file.')
        extension = selected.get('ext') or 'mp4'
        if not re.fullmatch(r'[a-zA-Z0-9]{1,8}', extension):
            extension = 'mp4'
        name = re.sub(r'[\\/:*?"<>|\x00-\x1f\x7f]', '_', record.title or 'video')[:150]
        filename = quote(f'{name}.{extension}', safe='')

        async def chunks():
            try:
                yield first
                async for chunk in iterator:
                    if chunk:
                        yield chunk
            finally:
                await close()

        return StreamingResponse(chunks(), media_type=media_type, headers={
            'Content-Disposition': f"attachment; filename=video.{extension}; filename*=UTF-8''{filename}",
            'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
        }, background=BackgroundTask(close))
    except HTTPException:
        await close()
        raise
    except (requests.RequestsError, OSError, TimeoutError):
        await close()
        raise HTTPException(502, 'Unable to download from the video platform. Please try again.') from None
