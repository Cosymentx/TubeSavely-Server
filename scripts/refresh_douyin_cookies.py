"""Create an anonymous Douyin session locally; never print cookie values.

Optional local tool: pip install playwright && playwright install chromium
The browser is not part of the Vercel function or production requirements.
"""

import argparse
import asyncio
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.short_video import USER_AGENT
from app.vendor.short_video_signing.websign import UIFID_COOKIE_NAMES


async def refresh(output, headed=False):
    from playwright.async_api import async_playwright

    async with async_playwright() as runtime:
        browser = await runtime.chromium.launch(headless=not headed)
        try:
            context = await browser.new_context(
                locale='zh-CN', user_agent=USER_AGENT,
                viewport={'width': 1920, 'height': 1080},
            )
            page = await context.new_page()
            await page.goto('https://www.douyin.com/', wait_until='domcontentloaded', timeout=30000)
            # Wait only for normal site initialization. No challenge solving.
            cookies = []
            for _ in range(15):
                await page.wait_for_timeout(1000)
                cookies = await context.cookies()
                if any(c['name'] in UIFID_COOKIE_NAMES and c['value'] for c in cookies):
                    break
            else:
                raise RuntimeError('未获得可用的抖音匿名会话；请在浏览器中正常访问平台后手动导出 Netscape Cookies。')
            lines = ['# Netscape HTTP Cookie File']
            for cookie in cookies:
                domain = cookie['domain']
                if not (domain.lstrip('.') == 'douyin.com' or domain.endswith('.douyin.com')):
                    continue
                fields = [
                    ('#HttpOnly_' if cookie.get('httpOnly') else '') + domain,
                    'TRUE' if domain.startswith('.') else 'FALSE', cookie['path'],
                    'TRUE' if cookie.get('secure') else 'FALSE',
                    str(max(0, int(cookie.get('expires', 0)))), cookie['name'], cookie['value'],
                ]
                if any('\n' in value or '\t' in value or '\r' in value for value in fields):
                    raise RuntimeError('平台 Cookie 包含不支持的字符，未写入文件。')
                lines.append('\t'.join(fields))
            output.parent.mkdir(parents=True, exist_ok=True)
            # Refuse symlinks and set permissions even when refreshing an old file.
            descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0), 0o600)
            with os.fdopen(descriptor, 'w') as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write('\n'.join(lines) + '\n')
            print(f'已保存 {len(lines) - 1} 条匿名会话 Cookie 至 {output}（权限 600）。')
        finally:
            await browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('cookies/douyin.txt'))
    parser.add_argument('--headed', action='store_true')
    arguments = parser.parse_args()
    try:
        asyncio.run(refresh(arguments.output, arguments.headed))
    except Exception as error:
        # Browser/network exceptions may contain request context; keep it local.
        print(f'匿名会话刷新失败（{type(error).__name__}）。请检查浏览器安装、网络，或手动导出 Cookie。', file=sys.stderr)
        sys.exit(1)
