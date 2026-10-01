"""Share-text extraction and strict platform URL classification."""

import re
from urllib.parse import parse_qs, urlsplit, urlunsplit

from app.services.video_runtime import VideoParseError

HOSTS = {
    'douyin': frozenset({'douyin.com', 'www.douyin.com', 'v.douyin.com', 'iesdouyin.com', 'www.iesdouyin.com'}),
    'tiktok': frozenset({'tiktok.com', 'www.tiktok.com', 'm.tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com'}),
}


def extract_url(text):
    # Preserve @, percent escapes and queries in links pasted with share text.
    match = re.search(r'https?://[^\s<>"\u3000]+', text or '', re.I)
    if not match and (text or '').strip().startswith('www.'):
        return extract_url('https://' + text.strip())
    if not match:
        raise VideoParseError('video_url_invalid', '请输入有效的视频链接。', 400)
    url = match.group().rstrip("。，、！!；;：:）)]}》>’'\"")
    try:
        parts = urlsplit(url)
        if not parts.hostname or parts.username or parts.password or parts.port not in (None, 80, 443):
            raise ValueError
    except ValueError:
        raise VideoParseError('video_url_invalid', '视频链接格式无效。', 400) from None
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ''))


def platform_of(url):
    host = (urlsplit(url).hostname or '').lower()
    return next((name for name, hosts in HOSTS.items() if host in hosts), None)


def validate_platform_url(url, platform):
    try:
        parts = urlsplit(url)
        valid = (parts.scheme in ('http', 'https') and parts.hostname in HOSTS[platform]
                 and not parts.username and not parts.password and parts.port in (None, 80, 443))
    except ValueError:
        valid = False
    if not valid:
        raise VideoParseError('video_redirect_invalid', '视频分享链接跳转到了不支持的地址。', 400)


def content_id(url, platform):
    parts = urlsplit(url)
    patterns = (r'/(?:share/)?(?:video|note)/(\d+)(?:/|$)',) if platform == 'douyin' else (
        r'/@[^/]+/(?:video|photo)/(\d+)(?:/|$)', r'/embed(?:/v2)?/(\d+)(?:/|$)',
    )
    for pattern in patterns:
        if match := re.search(pattern, parts.path):
            return match.group(1)
    if platform == 'douyin':
        query = parse_qs(parts.query)
        for name in ('modal_id', 'vid', 'aweme_id'):
            value = query.get(name, [''])[0]
            if value.isdigit():
                return value
    return None
