from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from app.services import youtube_download as youtube
from app.services import video_download
from app.schemas.video import VideoBase

URL = 'https://www.youtube.com/watch?v=XqJMIE6_9gY&t=332s'


class YouTubeDownloadTests(unittest.TestCase):
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
    async def test_youtube_does_not_use_the_old_direct_media_url(self):
        record = SimpleNamespace(original_url=URL, title='Fixture')
        selected = {'format_id': '137', 'url': 'https://expired.example/video.mp4'}
        with patch.object(video_download, 'owned_format', return_value=(record, selected)):
            with patch.object(youtube, 'download', new=AsyncMock(return_value='fresh-video')) as refreshed:
                with patch.object(video_download.requests, 'AsyncSession') as direct:
                    result = await video_download.download(None, 1, URL, '137')
        self.assertEqual(result, 'fresh-video')
        refreshed.assert_awaited_once_with(record, selected, True)
        direct.assert_not_called()

    async def test_stream_removes_temporary_files_after_delivery(self):
        paths = []
        def fixture(_url, _selected, directory, _audio, _cached):
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
