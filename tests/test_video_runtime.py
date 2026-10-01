import base64
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import video
from app.services import video_runtime
from app.api.v1.endpoints import video as video_endpoint
from app.vendor.yt_dlp.utils import DownloadError


class RuntimeTests(unittest.TestCase):
    def test_bundled_runtime_survives_missing_build_machine_path(self):
        with tempfile.TemporaryDirectory() as root:
            app = Path(root) / 'app'
            bundled = app / 'runtime_bin' / 'deno'
            bundled.parent.mkdir(parents=True)
            bundled.write_text('#!/bin/sh\n')
            bundled.chmod(0o755)
            with patch.object(video_runtime, '__file__', str(app / 'services' / 'video_runtime.py')):
                with patch.object(video_runtime, 'find_deno_bin', side_effect=FileNotFoundError('/build/bin/deno')):
                    self.assertEqual(video_runtime.javascript_runtimes()['deno']['path'], str(bundled.resolve()))

    def test_no_runtime_does_not_raise_during_lookup(self):
        with patch.object(video_runtime.Path, 'is_file', return_value=False):
            with patch.object(video_runtime.shutil, 'which', return_value=None):
                with patch.object(video_runtime, 'find_deno_bin', side_effect=FileNotFoundError):
                    self.assertEqual(video_runtime.javascript_runtimes(), {})

    def test_cookie_file_is_private_and_removed(self):
        text = '# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tVISITOR_INFO1_LIVE\tfixture\n'
        encoded = base64.b64encode(text.encode()).decode()
        with video_runtime.youtube_cookie_file(encoded) as filename:
            path = Path(filename)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.read_text(), text)
        self.assertFalse(path.exists())

    def test_cookie_file_is_removed_after_extraction_error(self):
        encoded = base64.b64encode(b'# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tVISITOR_INFO1_LIVE\tfixture\n').decode()
        with self.assertRaises(RuntimeError):
            with video_runtime.youtube_cookie_file(encoded) as filename:
                raise RuntimeError('extraction failed')
        self.assertFalse(Path(filename).exists())


class ExtractionErrors(unittest.IsolatedAsyncioTestCase):
    async def test_missing_runtime_is_reported_before_youtube_request(self):
        with patch.object(video, 'javascript_runtimes', return_value={}):
            with patch.object(video, '_get_cookies_file', return_value=None):
                with patch.object(video.yt_dlp, 'YoutubeDL') as factory:
                    with self.assertRaises(video_runtime.VideoParseError) as error:
                        await video.yt_dlp_parse('https://www.youtube.com/watch?v=XqJMIE6_9gY')
        self.assertEqual(error.exception.reason, 'video_runtime_missing')
        factory.assert_not_called()

    async def test_youtube_auth_error_is_not_replaced_by_invalid_url(self):
        downloader = MagicMock()
        downloader.extract_info.side_effect = DownloadError('Sign in to confirm you are not a bot')
        context = MagicMock()
        context.__enter__.return_value = downloader
        with patch.object(video.yt_dlp, 'YoutubeDL', return_value=context):
            with patch.object(video, '_get_cookies_file', return_value=None):
                with patch.object(video, 'yt_dlp_extend_parse', new=AsyncMock()) as fallback:
                    with self.assertRaises(video_runtime.VideoParseError) as error:
                        await video.yt_dlp_parse('https://www.youtube.com/watch?v=XqJMIE6_9gY')
        self.assertEqual(error.exception.reason, 'youtube_auth_required')
        fallback.assert_not_awaited()

    async def test_proxy_connection_failure_can_retry_directly(self):
        first = MagicMock()
        first.extract_info.side_effect = DownloadError('Connection timed out')
        second = MagicMock()
        second.extract_info.return_value = {
            'id': 'example', 'title': 'Example', 'duration': None,
            'formats': [{'format_id': '18', 'ext': 'mp4', 'height': 720, 'vcodec': 'avc', 'url': 'https://example.com/video.mp4'}],
        }
        first_context, second_context = MagicMock(), MagicMock()
        first_context.__enter__.return_value = first
        second_context.__enter__.return_value = second
        with patch.object(video.yt_dlp, 'YoutubeDL', side_effect=[first_context, second_context]) as factory:
            with patch.object(video.settings, 'VIDEO_PROXY', 'http://proxy.invalid:8888'):
                with patch.object(video, '_get_cookies_file', return_value=None):
                    result = await video.yt_dlp_parse('https://www.youtube.com/watch?v=XqJMIE6_9gY')
        self.assertEqual(result['title'], 'Example')
        self.assertEqual(result['duration'], '0')
        self.assertEqual(factory.call_args_list[1].args[0]['proxy'], '')

    async def test_api_returns_the_actual_platform_failure(self):
        error = video_runtime.VideoParseError('youtube_auth_required', 'YouTube 要求登录验证')
        with patch.object(video_endpoint, 'extract', new=AsyncMock(side_effect=error)):
            response = await video_endpoint.parse('https://www.youtube.com/watch?v=XqJMIE6_9gY', db=None, current_user=None)
        self.assertEqual(response.code, 503)
        self.assertEqual(response.msg, 'YouTube 要求登录验证')
