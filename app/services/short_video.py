"""Douyin/TikTok detail extraction with one cookie, proxy and browser session.

Protocol references: Evil0ctal/Douyin_TikTok_Download_API at d8f874c.
Media selection also informed by JoeanAmier/TikTokDownloader (no code copied).
Only the pure signing primitives are vendored; their Apache licence is retained.
"""

import asyncio
from http.cookiejar import MozillaCookieJar
import json
import logging
from pathlib import Path
import re
import secrets
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlsplit

from curl_cffi import requests

from app.core.config import settings
from app.services.video_runtime import VideoParseError, youtube_cookie_file
from app.services.video_urls import content_id, platform_of, validate_platform_url
from app.vendor.short_video_signing.abogus import ABogus, browser_info_from_screen
from app.vendor.short_video_signing import tiktok_sign, websign

logger = logging.getLogger(__name__)
USER_AGENT = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
NAMES = {'douyin': '抖音', 'tiktok': 'TikTok'}


def failure(platform, reason, code=503):
    name = NAMES[platform]
    messages = {
        'risk_control': f'{name} 要求验证当前访问会话，请管理员更新平台 Cookies 并检查出口网络。',
        'network_error': f'{name} 连接失败或超时，请稍后重试，并检查该平台的代理配置。',
        'signature_rejected': f'{name} 拒绝了请求签名，请管理员检查平台 Cookies 或更新解析器。',
        'content_unavailable': f'{name} 当前无法提供该作品，可能已删除、设为私密或限制访问。',
        'upstream_changed': f'{name} 返回的数据缺少视频信息，请稍后重试或更新解析器。',
        'cookies_invalid': f'{name} Cookies 配置无效，请管理员重新导出 Netscape 格式文件。',
        'unsupported_album': f'该{name}链接是图集，当前视频接口暂不支持图集下载。',
        'unsupported_url': f'请输入{name}单个作品的链接或分享短链接。',
    }
    return VideoParseError(f'{platform}_{reason}', messages[reason], code)


def platform_proxy(platform):
    # None inherits VIDEO_PROXY; an explicit empty value selects a direct route.
    override = getattr(settings, f'{platform.upper()}_PROXY')
    return settings.VIDEO_PROXY if override is None else override


def load_cookies(platform):
    jar = MozillaCookieJar()
    encoded = getattr(settings, f'{platform.upper()}_COOKIES_BASE64')
    local = Path('cookies') / f'{platform}.txt'
    try:
        with youtube_cookie_file(encoded) as temporary:
            path = temporary or (str(local) if local.is_file() else None)
            if path:
                jar.load(path, ignore_discard=True, ignore_expires=True)
    except (VideoParseError, OSError, ValueError):
        raise failure(platform, 'cookies_invalid') from None
    # Never forward cookies from an accidentally exported, unrelated site.
    for cookie in list(jar):
        if cookie.expires == 0:
            cookie.expires = None
            cookie.discard = True
        domain = cookie.domain.lstrip('.').lower()
        if not (domain == f'{platform}.com' or domain.endswith(f'.{platform}.com')):
            jar.clear(cookie.domain, cookie.path, cookie.name)
    jar.clear_expired_cookies()
    if encoded and not list(jar):
        raise failure(platform, 'cookies_invalid')
    return jar


def cookie_values(session, platform):
    host = f'www.{platform}.com'
    values = {}
    for cookie in session.cookies.jar:
        domain = cookie.domain.lstrip('.').lower()
        if not cookie.is_expired() and (host == domain or (cookie.domain_initial_dot and host.endswith('.' + domain))):
            values[cookie.name] = cookie.value
    return values


def signed_detail_url(platform, video_id, cookies):
    common = {
        'aid': '6383' if platform == 'douyin' else '1988',
        'cookie_enabled': 'true', 'browser_online': 'true',
        'browser_platform': 'MacIntel', 'screen_width': '1920', 'screen_height': '1080',
    }
    if platform == 'douyin':
        params = {
            **common, 'device_platform': 'webapp', 'channel': 'channel_pc_web',
            'pc_client_type': '1', 'version_code': '290100', 'version_name': '29.1.0',
            'update_version_code': '170400', 'browser_language': 'zh-CN',
            'browser_name': 'Chrome', 'browser_version': '131.0.0.0',
            'engine_name': 'Blink', 'engine_version': '131.0.0.0',
            'os_name': 'Mac OS', 'os_version': '10.15.7', 'cpu_core_num': '12',
            'device_memory': '8', 'platform': 'PC', 'downlink': '10',
            'effective_type': '4g', 'round_trip_time': '0', 'aweme_id': video_id,
        }
        if cookies.get('msToken'):
            params['msToken'] = cookies['msToken']
        query = urlencode(params, quote_via=quote)
        signer = ABogus(USER_AGENT, browser_info=browser_info_from_screen(1920, 1080, 'MacIntel'))
        query += '&a_bogus=' + quote(signer.get_value(query), safe='')
        uifid = websign.pick_uifid(cookies)
        if not uifid:
            raise failure(platform, 'risk_control')
        pairs = parse_qsl(query, keep_blank_values=True)
        if cookies.get('s_v_web_id'):
            pairs.extend((key, cookies['s_v_web_id']) for key in ('verifyFp', 'fp'))
        query, _, headers = websign.sign(pairs, uifid)
        return 'https://www.douyin.com/aweme/v1/web/aweme/detail/?' + query, headers
    params = {
        **common, 'app_language': 'en', 'app_name': 'tiktok_web',
        'browser_language': 'en-US', 'browser_name': 'Mozilla',
        'browser_version': '5.0 (Macintosh)', 'channel': 'tiktok_web',
        'device_id': cookies.get('tt_webid_v2') or cookies.get('tt_webid') or str(secrets.randbelow(9 * 10**18) + 10**18),
        'device_platform': 'web_pc', 'focus_state': 'true', 'from_page': 'video',
        'history_len': '1', 'is_fullscreen': 'false', 'is_page_visible': 'true',
        'language': 'en', 'os': 'mac', 'priority_region': 'US', 'region': 'US',
        'referer': '', 'root_referer': 'https://www.tiktok.com/',
        'tz_name': 'America/Los_Angeles', 'webcast_language': 'en', 'itemId': video_id,
    }
    query, _ = tiktok_sign.sign(list(params.items()), USER_AGENT, ms_token=tiktok_sign.pick_ms_token(cookies))
    return 'https://www.tiktok.com/api/item/detail/?' + query, {}


def check_response(response, platform):
    status = response.status_code
    head = response.text[:4096].lower()
    if any(marker in head for marker in ('uifid not found', 'signature not found', 'sign invalid', 'sign expired')):
        raise failure(platform, 'signature_rejected')
    if status in (404, 410, 451):
        raise failure(platform, 'content_unavailable', 404)
    if status in (407, 408) or status >= 500:
        raise failure(platform, 'network_error')
    if status in (401, 403, 405, 412, 429, 444) or response.headers.get('tt_orcas_res') == '1':
        raise failure(platform, 'risk_control')
    if not response.text.strip():
        raise failure(platform, 'risk_control')
    if status >= 400:
        raise failure(platform, 'upstream_changed')


def check_payload(payload, platform):
    if not isinstance(payload, dict) or not payload:
        raise failure(platform, 'risk_control')
    code = payload.get('status_code', payload.get('statusCode', 0))
    message = str(payload.get('status_msg', payload.get('statusMsg', ''))).lower()
    if any(marker in message for marker in ('private', 'deleted', 'not found', '私密', '不存在', '已删除')):
        raise failure(platform, 'content_unavailable', 404)
    if code not in (0, '0', None):
        if str(code) in ('10204', '10216', '10222'):
            raise failure(platform, 'content_unavailable', 404)
        raise failure(platform, 'risk_control')


def item_from_payload(payload, platform, video_id):
    check_payload(payload, platform)
    if platform == 'douyin':
        item = payload.get('aweme_detail')
        if not item:
            item = next((x for x in payload.get('item_list', []) if isinstance(x, dict) and str(x.get('aweme_id')) == video_id), None)
    else:
        item = (payload.get('itemInfo') or {}).get('itemStruct')
    if not isinstance(item, dict) or not item:
        raise failure(platform, 'risk_control')
    return item


def embedded_item(html, platform, video_id):
    """Read known page envelopes, always matching the requested work's ID."""
    blobs = []
    for match in re.finditer(r'<script\b([^>]*)>(.*?)</script\s*>', html, re.I | re.S):
        attrs, body = match.groups()
        if re.search(r'\bid\s*=\s*[\'"](?:__UNIVERSAL_DATA_FOR_REHYDRATION__|SIGI_STATE|RENDER_DATA)[\'"]', attrs):
            try:
                blobs.append(json.loads(unquote(body) if 'RENDER_DATA' in attrs else body))
            except (ValueError, TypeError):
                continue
        if 'window._ROUTER_DATA' in body:
            match_data = re.search(r'window\._ROUTER_DATA\s*=\s*', body)
            if match_data:
                try:
                    blobs.append(json.JSONDecoder().raw_decode(body[match_data.end():].lstrip())[0])
                except ValueError:
                    continue
    # Iterative traversal tolerates loader key changes without recursion overflow.
    pending = blobs
    visited = 0
    while pending and visited < 20000:
        node = pending.pop()
        visited += 1
        if isinstance(node, dict):
            identity = node.get('aweme_id') if platform == 'douyin' else node.get('id')
            if str(identity) == video_id and any(key in node for key in ('video', 'images', 'imagePost')):
                return node
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    return None


def urls(value):
    if isinstance(value, dict):
        value = value.get('url_list', value.get('UrlList', value.get('urlList', [])))
    if isinstance(value, str):
        value = [value]
    return [x for x in (value or []) if isinstance(x, str) and urlsplit(x).scheme in ('http', 'https') and urlsplit(x).hostname]


def number(value):
    try:
        return max(0, int(float(value))) if value is not None else None
    except (TypeError, ValueError, OverflowError):
        return None


def parse_item(item, platform, video_id, original_url):
    identity = item.get('aweme_id') if platform == 'douyin' else item.get('id')
    if str(identity) != video_id:
        raise failure(platform, 'upstream_changed')
    state = item.get('status') or {}
    if state.get('is_delete') or number(state.get('private_status')) or item.get('privateItem') or item.get('takeDown'):
        raise failure(platform, 'content_unavailable', 404)
    if item.get('images') or (item.get('imagePost') or {}).get('images'):
        raise failure(platform, 'unsupported_album', 422)
    video = item.get('video') or {}
    formats, seen = [], set()

    def add(address, label, gear=None, watermark=False):
        gear = gear or {}
        meta = address if isinstance(address, dict) else {}
        width = number(meta.get('width', meta.get('Width'))) or number(video.get('width'))
        height = number(meta.get('height', meta.get('Height'))) or number(video.get('height'))
        for index, stream_url in enumerate(urls(address)):
            if stream_url in seen:
                continue
            seen.add(stream_url)
            bitrate = number(gear.get('bit_rate', gear.get('Bitrate', video.get('bitrate'))))
            formats.append({
                'format_id': f'{label}-{index}', 'format_note': '带水印' if watermark else label,
                'url': stream_url, 'ext': 'mp4', 'width': width, 'height': height,
                'resolution': f'{width}x{height}' if width and height else None,
                'filesize': number(meta.get('data_size', meta.get('DataSize'))),
                'fps': number(gear.get('FPS', gear.get('fps'))),
                'tbr': bitrate / 1000 if bitrate else None,
                'vcodec': gear.get('CodecType') or ('h265' if gear.get('is_h265') else None),
            })

    if platform == 'douyin':
        for index, gear in enumerate(video.get('bit_rate') or []):
            add(gear.get('play_addr'), f'bitrate-{index}', gear)
        add(video.get('play_addr'), 'play')
        if not formats:
            add(video.get('download_addr'), 'download', watermark=True)
        thumbnail = urls(video.get('cover') or video.get('origin_cover'))
        duration = (number(video.get('duration', item.get('duration'))) or 0) / 1000
        stats = item.get('statistics') or {}
    else:
        for index, gear in enumerate(video.get('bitrateInfo') or []):
            add(gear.get('PlayAddr'), f'bitrate-{index}', gear)
        add(video.get('playAddr'), 'play')
        if not formats:
            add(video.get('downloadAddr'), 'download', watermark=True)
        thumbnail = urls(video.get('cover') or video.get('originCover'))
        duration = number(video.get('duration')) or 0
        stats = item.get('stats') or {}
    if not formats:
        raise failure(platform, 'upstream_changed')
    # TikTok's regional CDN can return 403 while its same-quality web play
    # endpoint works. Prefer that alternative within each quality group.
    formats.sort(key=lambda x: (
        max(x['height'] or 0, x['width'] or 0), x['fps'] or 0, x['tbr'] or 0,
        platform == 'tiktok' and urlsplit(x['url']).hostname == 'www.tiktok.com',
    ), reverse=True)
    author = item.get('author') or {}
    return {
        'url': original_url, 'video_id': video_id, 'platform': platform,
        'title': item.get('desc') or f'{NAMES[platform]} {video_id}',
        'description': item.get('desc') or '', 'thumbnail': next(iter(thumbnail), ''),
        'duration': str(int(duration)), 'author': author.get('nickname') or author.get('uniqueId') or '',
        'formats': formats, 'view_count': number(stats.get('play_count', stats.get('playCount'))) or 0,
        'like_count': number(stats.get('digg_count', stats.get('diggCount'))) or 0,
    }


async def get_page(session, url, platform):
    seen = set()
    for _ in range(6):
        validate_platform_url(url, platform)
        if url in seen:
            raise VideoParseError('video_redirect_loop', '分享链接循环跳转，请使用作品完整链接。', 400)
        seen.add(url)
        response = await session.get(url, allow_redirects=False)
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get('location')
            if not location:
                raise failure(platform, 'upstream_changed')
            url = urljoin(url, location)
            continue
        check_response(response, platform)
        return url, response
    raise VideoParseError('video_redirect_limit', '分享链接跳转次数过多，请使用作品完整链接。', 400)


async def parse(url):
    platform = platform_of(url)
    if not platform:
        raise VideoParseError('video_url_invalid', '不支持的视频平台。', 400)
    language = 'zh-CN,zh;q=0.9' if platform == 'douyin' else 'en-US,en;q=0.9'
    headers = {
        'User-Agent': USER_AGENT, 'Accept-Language': language,
        'sec-ch-ua-platform': '"macOS"', 'Referer': f'https://www.{platform}.com/',
    }
    try:
        async with asyncio.timeout(40):
            async with requests.AsyncSession(
                impersonate='chrome131', headers=headers, cookies=load_cookies(platform),
                proxy=platform_proxy(platform) or None, trust_env=False,
                timeout=10, max_clients=1,
            ) as session:
                video_id = content_id(url, platform)
                page_url = f'https://www.iesdouyin.com/share/video/{video_id}/' if platform == 'douyin' and video_id else url
                page_error = None
                try:
                    resolved, response = await get_page(session, page_url, platform)
                    video_id = video_id or content_id(resolved, platform)
                    if video_id:
                        item = embedded_item(response.text, platform, video_id)
                        if item:
                            return parse_item(item, platform, video_id, url)
                except VideoParseError as error:
                    if error.code in (400, 404, 422):
                        raise
                    page_error = error
                if not video_id:
                    if page_error:
                        raise page_error
                    if urlsplit(url).hostname in ('v.douyin.com', 'vm.tiktok.com', 'vt.tiktok.com') or '/t/' in url:
                        raise failure(platform, 'risk_control')
                    raise failure(platform, 'unsupported_url', 400)
                api_url, api_headers = signed_detail_url(platform, video_id, cookie_values(session, platform))
                response = await session.get(api_url, headers={**api_headers, 'Accept': 'application/json'}, allow_redirects=False, quote=False)
                check_response(response, platform)
                if 300 <= response.status_code < 400:
                    raise failure(platform, 'risk_control')
                try:
                    payload = response.json()
                except ValueError:
                    raise failure(platform, 'risk_control') from None
                item = item_from_payload(payload, platform, video_id)
                return parse_item(item, platform, video_id, url)
    except (requests.RequestsError, TimeoutError):
        # RequestsError often embeds proxy credentials or signed URLs.
        raise failure(platform, 'network_error') from None
    except VideoParseError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError):
        raise failure(platform, 'upstream_changed') from None
