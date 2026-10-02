import asyncio
from pathlib import Path
import tempfile
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from app.services import youtube_download as youtube
from app.services import video_download
from app.schemas.video import VideoBase
from app.services.video_runtime import initialize_youtube_guest

URL = 'https://www.youtube.com/watch?v=XqJMIE6_9gY&t=332s'


class YouTubeDownloadTests(unittest.TestCase):
    def test_guest_visitor_initialization_reuses_existing_session(self):
        payload = [[None, None, [[[None] * 13 + ['fixture-visitor']]]]]
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = ( ")]}'\n" + json.dumps(payload)).encode()
        downloader = SimpleNamespace(urlopen=MagicMock(return_value=response), params={})
        self.assertTrue(initialize_youtube_guest(downloader))
        self.assertEqual(downloader.params['extractor_args']['youtube']['visitor_data'], ['fixture-visitor'])
        self.assertEqual(downloader.params['extractor_args']['youtube']['player_skip'], ['webpage', 'configs'])
        self.assertEqual(downloader.urlopen.call_args.args[0].url, 'https://www.youtube.com/sw.js_data')

    def test_guest_initialization_falls_back_cleanly(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'<html>unexpected</html>'
        downloader = SimpleNamespace(urlopen=MagicMock(return_value=response), params={})
        self.assertFalse(initialize_youtube_guest(downloader))
        self.assertNotIn('extractor_args', downloader.params)

    def test_download_limits_reject_long_or_oversized_media(self):
        with patch.object(youtube.settings, 'YOUTUBE_MAX_DURATION_SECONDS', 60):
            with self.assertRaises(HTTPException) as duration_error:
                youtube._validate_download_limits(SimpleNamespace(duration='61'), {'filesize': 1})
            self.assertEqual(duration_error.exception.status_code, 413)
        with patch.object(youtube.settings, 'YOUTUBE_MAX_FILE_MB', 1):
            with self.assertRaises(HTTPException) as size_error:
                youtube._validate_download_limits(SimpleNamespace(duration='10'), {'filesize': 2 * 1024 * 1024})
            self.assertEqual(size_error.exception.status_code, 413)

    def test_video_only_formats_include_audio_by_default(self):
        selected = {'format_id': '137', 'ext': 'mp4', 'vcodec': 'avc1', 'acodec': 'none'}
        self.assertEqual(youtube.format_selector(selected), '137+bestaudio[ext=m4a]/137+bestaudio')
        self.assertEqual(youtube.format_selector(selected, include_audio=False), '137')

    def test_untrusted_format_expressions_are_rejected(self):
        with self.assertRaises(HTTPException):
            youtube.format_selector({'format_id': 'best+anything'})

    def test_transport_context_is_kept_private_in_api_response(self):
        value = VideoBase(url=URL, formats=[{'format_id': '137', 'ext': 'mp4',
            'download_headers': {'User-Agent': 'Fixture Safari'}, 'direct_download': True}])
        self.assertEqual(value.formats[0].download_headers['User-Agent'], 'Fixture Safari')
        self.assertNotIn('download_headers', value.model_dump()['formats'][0])
        self.assertNotIn('direct_download', value.model_dump()['formats'][0])

    def test_reextracts_original_url_and_downloads_in_one_session(self):
        downloader = MagicMock()
        context = MagicMock()
        context.__enter__.return_value = downloader
        with tempfile.TemporaryDirectory() as directory:
            downloader.extract_info.side_effect = lambda *_args, **_kwargs: (Path(directory) / 'video.mp4').write_bytes(b'\x00\x00\x00\x18ftypmp42fixture')
            with patch.object(youtube.yt_dlp, 'YoutubeDL', return_value=context) as factory:
                with patch.object(youtube, 'javascript_runtimes', return_value={'deno': {}}):
                    with patch.object(youtube.settings, 'VIDEO_PROXY', ''):
                        with patch.object(youtube.settings, 'YOUTUBE_COOKIES_BASE64', ''):
                            path = youtube.fetch(URL, {'format_id': '137', 'ext': 'mp4', 'vcodec': 'avc1', 'acodec': 'none'}, directory)
            downloader.extract_info.assert_called_once_with(URL, download=True)
            options = factory.call_args.args[0]
            self.assertIn('bestaudio', options['format'])
            self.assertEqual(options['http_chunk_size'], 5 * 1024 * 1024)
            self.assertTrue(Path(options['ffmpeg_location']).is_file())
            self.assertTrue(path.is_file())

    def test_valid_cached_manifest_preserves_headers_without_second_player_request(self):
        downloader = MagicMock()
        context = MagicMock()
        context.__enter__.return_value = downloader
        cached = {'id': 'fixture', 'title': 'Fixture', 'formats': [{'format_id': '137', 'http_headers': {'User-Agent': 'Fixture Safari'}}]}
        with tempfile.TemporaryDirectory() as directory:
            downloader.process_ie_result.side_effect = lambda *_args, **_kwargs: (Path(directory) / 'video.mp4').write_bytes(b'ftyp-fixture')
            with patch.object(youtube.yt_dlp, 'YoutubeDL', return_value=context):
                with patch.object(youtube, 'javascript_runtimes', return_value={'deno': {}}):
                    with patch.object(youtube.settings, 'VIDEO_PROXY', ''):
                        with patch.object(youtube.settings, 'YOUTUBE_COOKIES_BASE64', ''):
                            youtube.fetch(URL, {'format_id': '137', 'ext': 'mp4'}, directory, cached_info=cached)
        downloader.process_ie_result.assert_called_once_with(cached, download=True)
        downloader.extract_info.assert_not_called()


class YouTubeStreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_user_cannot_start_two_youtube_downloads(self):
        original_global = youtube._global_download_semaphore
        original_users = youtube._user_download_semaphores
        youtube._global_download_semaphore = asyncio.Semaphore(2)
        youtube._user_download_semaphores = {}
        try:
            first = await youtube._acquire_download_slots(42)
            with self.assertRaises(HTTPException) as error:
                await youtube._acquire_download_slots(42)
            self.assertEqual(error.exception.status_code, 429)
            first.release()
            youtube._global_download_semaphore.release()
        finally:
            youtube._global_download_semaphore = original_global
            youtube._user_download_semaphores = original_users

    async def test_queue_full_rejects_another_user(self):
        original_global = youtube._global_download_semaphore
        original_users = youtube._user_download_semaphores
        original_waiting = youtube._global_waiting_downloads
        youtube._global_download_semaphore = asyncio.Semaphore(0)
        youtube._user_download_semaphores = {}
        youtube._global_waiting_downloads = 0
        try:
            with patch.object(youtube.settings, 'YOUTUBE_DOWNLOAD_QUEUE_SIZE', 1):
                first = asyncio.create_task(youtube._acquire_download_slots(1))
                await asyncio.sleep(0.06)
                with self.assertRaises(HTTPException) as error:
                    await youtube._acquire_download_slots(2)
                self.assertEqual(error.exception.status_code, 429)
                first.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await first
        finally:
            youtube._global_download_semaphore = original_global
            youtube._user_download_semaphores = original_users
            youtube._global_waiting_downloads = original_waiting

    async def test_queued_download_stops_waiting_when_client_disconnects(self):
        original_global = youtube._global_download_semaphore
        original_users = youtube._user_download_semaphores
        original_waiting = youtube._global_waiting_downloads
        youtube._global_download_semaphore = asyncio.Semaphore(0)
        youtube._user_download_semaphores = {}
        youtube._global_waiting_downloads = 0
        request = SimpleNamespace(is_disconnected=AsyncMock(return_value=True))
        try:
            with patch.object(youtube.settings, 'YOUTUBE_DOWNLOAD_QUEUE_SIZE', 2):
                with self.assertRaises(youtube.ClientDisconnected):
                    await youtube._acquire_download_slots(9, request=request)
        finally:
            youtube._global_download_semaphore = original_global
            youtube._user_download_semaphores = original_users
            youtube._global_waiting_downloads = original_waiting

    def test_cancel_event_aborts_yt_dlp_progress(self):
        event = __import__('threading').Event()
        event.set()
        downloader = MagicMock()
        context = MagicMock()
        context.__enter__.return_value = downloader

        def invoke_progress(*_args, **_kwargs):
            progress = context_factory.call_args.args[0]['progress_hooks'][0]
            progress({'downloaded_bytes': 1})

        with tempfile.TemporaryDirectory() as directory:
            downloader.extract_info.side_effect = invoke_progress
            with patch.object(youtube.yt_dlp, 'YoutubeDL', return_value=context) as context_factory:
                with patch.object(youtube, 'javascript_runtimes', return_value={'deno': {}}):
                    with patch.object(youtube.settings, 'YOUTUBE_COOKIES_BASE64', 'configured'):
                        with self.assertRaises(Exception):
                            youtube.fetch(
                                URL,
                                {'format_id': '137', 'ext': 'mp4'},
                                directory,
                                cancel_event=event,
                            )

    async def test_youtube_does_not_use_the_old_direct_media_url(self):
        record = SimpleNamespace(original_url=URL, title='Fixture')
        selected = {'format_id': '137', 'url': 'https://expired.example/video.mp4'}
        with patch.object(video_download, 'owned_format', return_value=(record, selected)):
            with patch.object(youtube, 'download', new=AsyncMock(return_value='fresh-video')) as refreshed:
                with patch.object(video_download.requests, 'AsyncSession') as direct:
                    result = await video_download.download(None, 1, URL, '137')
        self.assertEqual(result, 'fresh-video')
        refreshed.assert_awaited_once_with(record, selected, True, user_id=1, request=None)
        direct.assert_not_called()

    async def test_stream_removes_temporary_files_after_delivery(self):
        paths = []
        def fixture(_url, _selected, directory, _audio, _cached, _cancel):
            path = Path(directory) / 'video.mp4'
            path.write_bytes(b'\x00\x00\x00\x18ftypmp42fixture')
            paths.append(path)
            return path
        with patch.object(youtube, 'fetch', side_effect=fixture):
            response = await youtube.download(SimpleNamespace(original_url=URL, title='Fixture'), {'format_id': '137'})
            data = b''.join([chunk async for chunk in response.body_iterator])
            await response.background()
        self.assertIn(b'ftyp', data)
        self.assertFalse(paths[0].parent.exists())
