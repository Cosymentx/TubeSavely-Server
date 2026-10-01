from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.user import User
from app.models.video import Video
from app.models.credit import Credit
from app.schemas.video import VideoBase
from app.services import video_download as download
from app.services.video_transaction import complete_video_transaction
from app.services.credit import InsufficientCreditsError
from app.api.v1.endpoints.video import router
from app.api.v1.endpoints import video as video_endpoint
from app.core import deps

URL = 'https://www.tiktok.com/@example/video/1234567890123456789'


class OwnershipAndCredits(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.owner = User(user_id='fixture-owner', email='owner@example.com', username='Owner', hashed_password='fixture', credits=3)
        self.other = User(user_id='fixture-other', email='other@example.com', username='Other', hashed_password='fixture', credits=0)
        self.db.add_all([self.owner, self.other])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def video(self):
        return VideoBase(url=URL, title='中文标题', duration='9', video_id='1234567890123456789', platform='tiktok', formats=[{
            'format_id': 'play', 'ext': 'mp4', 'url': 'https://www.tiktok.com/aweme/v1/play/',
        }])

    def test_parse_charges_once_and_download_authorization_works_at_zero_credits(self):
        complete_video_transaction(self.db, self.owner, self.video())
        self.assertEqual(self.owner.credits, 0)
        record, selected = download.owned_format(self.db, self.owner.id, URL, 'play')
        self.assertEqual(record.title, '中文标题')
        self.assertEqual(selected['format_id'], 'play')
        self.assertEqual(self.db.query(Credit).filter(Credit.user_id == self.owner.id).count(), 1)
        with self.assertRaises(HTTPException) as error:
            download.owned_format(self.db, self.other.id, URL, 'play')
        self.assertEqual(error.exception.status_code, 404)
        with self.assertRaises(HTTPException):
            download.owned_format(self.db, self.owner.id, URL, 'unowned-format')

    def test_insufficient_credits_roll_back_video_and_ledger(self):
        with self.assertRaises(InsufficientCreditsError) as error:
            complete_video_transaction(self.db, self.other, self.video())
        self.assertEqual(self.db.query(Video).count(), 0)
        self.assertEqual(self.db.query(Credit).count(), 0)
        self.assertEqual(self.other.credits, 0)

    def test_stale_user_balance_cannot_spend_credits_twice(self):
        complete_video_transaction(self.db, self.owner, self.video())
        with self.assertRaises(InsufficientCreditsError):
            complete_video_transaction(self.db, self.owner, self.video())
        self.assertEqual(self.db.query(Video).count(), 1)
        self.assertEqual(self.db.query(Credit).count(), 1)

    def test_balance_is_refreshed_after_another_transaction_changes_it(self):
        self.assertEqual(self.owner.credits, 3)
        with sessionmaker(bind=self.engine)() as concurrent:
            current = concurrent.query(User).filter(User.id == self.owner.id).one()
            current.credits = 0
            concurrent.commit()
        # This session still contains its earlier snapshot until the row is read.
        self.assertEqual(self.owner.credits, 3)
        with self.assertRaises(InsufficientCreditsError):
            complete_video_transaction(self.db, self.owner, self.video())
        self.assertEqual(self.db.query(Video).count(), 0)


def fake_response(body=b'\x00\x00\x00\x18ftypmp42fixture', status=200, content_type='video/mp4', location=None):
    async def chunks():
        yield body
        yield b'end'
    return SimpleNamespace(status_code=status, headers={'content-type': content_type, **({'location': location} if location else {})},
                           aiter_content=chunks, aclose=AsyncMock())


class StreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_insufficient_balance_is_reported_before_platform_request(self):
        with patch.object(video_endpoint, 'extract', new=AsyncMock()) as parse:
            response = await video_endpoint.parse(URL, db=None, current_user=SimpleNamespace(credits=0))
        self.assertEqual(response.code, 402)
        parse.assert_not_awaited()

    async def test_stream_delivers_media_with_utf8_filename_and_closes_connections(self):
        upstream = fake_response()
        client = SimpleNamespace(get=AsyncMock(return_value=upstream), close=AsyncMock())
        record = SimpleNamespace(original_url=URL, title='中文标题')
        with patch.object(download, 'owned_format', return_value=(record, {'url': 'https://media.example/a.mp4', 'ext': 'mp4'})):
            with patch.object(download, 'public_media_url', new=AsyncMock()):
                with patch.object(download.requests, 'AsyncSession', return_value=client):
                    response = await download.download(None, 1, URL, 'play')
                    body = b''.join([chunk async for chunk in response.body_iterator])
                    await response.background()
        self.assertIn(b'ftyp', body)
        self.assertIn("filename*=UTF-8''%E4%B8%AD%E6%96%87", response.headers['content-disposition'])
        upstream.aclose.assert_awaited_once()
        client.close.assert_awaited_once()

    async def test_html_and_api_errors_are_not_saved_as_media(self):
        for upstream in (fake_response(b'<html>challenge</html>', content_type='text/html'), fake_response(b'{"error":"blocked"}', content_type='application/octet-stream'), fake_response(status=403)):
            client = SimpleNamespace(get=AsyncMock(return_value=upstream), close=AsyncMock())
            with patch.object(download, 'owned_format', return_value=(SimpleNamespace(original_url=URL, title='fixture'), {'url': 'https://media.example/a.mp4'})):
                with patch.object(download, 'public_media_url', new=AsyncMock()):
                    with patch.object(download.requests, 'AsyncSession', return_value=client):
                        with self.assertRaises(HTTPException) as error:
                            await download.download(None, 1, URL, 'play')
            self.assertEqual(error.exception.status_code, 502)
            client.close.assert_awaited_once()

    async def test_private_dns_targets_are_refused(self):
        with patch.object(download.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 80))]):
            with self.assertRaises(HTTPException):
                await download.public_media_url('https://attacker.example/video.mp4')

    async def test_redirect_is_validated_before_fetch(self):
        client = SimpleNamespace(get=AsyncMock(return_value=fake_response(status=302, location='http://127.0.0.1/admin')), close=AsyncMock())
        with patch.object(download, 'owned_format', return_value=(SimpleNamespace(original_url=URL, title='fixture'), {'url': 'https://media.example/a.mp4'})):
            with patch.object(download, 'public_media_url', new=AsyncMock(side_effect=[None, HTTPException(400, 'blocked')])):
                with patch.object(download.requests, 'AsyncSession', return_value=client):
                    with self.assertRaises(HTTPException):
                        await download.download(None, 1, URL, 'play')
        client.get.assert_awaited_once()


class DownloadRouteTests(unittest.TestCase):
    def test_post_download_is_registered_and_requires_authentication(self):
        app = FastAPI()
        app.include_router(router, prefix='/videos')
        app.dependency_overrides[deps.get_db] = lambda: None
        with TestClient(app) as client:
            response = client.post('/videos/download', json={'url': URL, 'format_id': 'play'})
        self.assertEqual(response.status_code, 401)
        self.assertNotEqual(response.status_code, 405)
