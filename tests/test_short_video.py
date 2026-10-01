import base64
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, quote, urlsplit

from curl_cffi.requests import Cookies

from app.services import short_video as sv, video
from app.services.video_runtime import VideoParseError
from app.services.video_urls import content_id, extract_url, platform_of
from app.vendor.short_video_signing import sm3, tiktok_sign, websign

ID = '1234567890123456789'
DY = f'https://www.douyin.com/video/{ID}'
TT = f'https://www.tiktok.com/@example/video/{ID}'


def response(body='', status=200, headers=None):
    return SimpleNamespace(text=body, status_code=status, headers=headers or {}, json=lambda: json.loads(body))


def item(platform):
    if platform == 'douyin':
        return {'aweme_id': ID, 'desc': 'Fixture', 'author': {'nickname': 'Author'}, 'video': {
            'duration': 12500, 'width': 720, 'height': 1280,
            'play_addr': {'url_list': ['https://media.example/low.mp4']},
            'bit_rate': [{'bit_rate': 2000000, 'FPS': 30, 'play_addr': {
                'width': 1080, 'height': 1920, 'data_size': 12345,
                'url_list': ['https://media.example/high.mp4', 'https://backup.example/high.mp4']}}],
        }}
    return {'id': ID, 'desc': 'Fixture', 'author': {'nickname': 'Author'}, 'video': {
        'duration': 12, 'width': 1080, 'height': 1920, 'playAddr': 'https://media.example/video.mp4',
        'bitrateInfo': [{'Bitrate': 4000000, 'CodecType': 'h264', 'PlayAddr': {
            'Width': 720, 'Height': 1280, 'DataSize': 3456, 'UrlList': ['https://media.example/720.mp4']}}],
    }}


class UrlAndMediaTests(unittest.TestCase):
    def test_share_text_keeps_tiktok_handle_and_query(self):
        self.assertEqual(extract_url(f'打开看看 {TT}?lang=en。'), TT + '?lang=en')
        self.assertEqual(content_id(TT, 'tiktok'), ID)
        self.assertEqual(content_id(f'https://www.douyin.com/?modal_id={ID}', 'douyin'), ID)
        self.assertEqual(content_id(f'https://www.douyin.com/note/{ID}?x=1', 'douyin'), ID)
        self.assertEqual(content_id(f'https://www.tiktok.com/@example/photo/{ID}', 'tiktok'), ID)

    def test_platform_detection_checks_host_not_substring(self):
        self.assertIsNone(platform_of('https://evil.example/www.douyin.com/video/1'))
        self.assertIsNone(platform_of('https://www.tiktok.com.evil.example/video/1'))
        with self.assertRaises(VideoParseError):
            extract_url('https://www.tiktok.com@evil.example/video/1')

    def test_embedded_json_matches_requested_id(self):
        target = item('douyin')
        other = {**target, 'aweme_id': '999'}
        payload = {'loaderData': {'new-layout': {'item_list': [target, other]}}}
        page = '<script>window._ROUTER_DATA = ' + json.dumps(payload) + '; window.other = 1;</script>'
        self.assertEqual(sv.embedded_item(page, 'douyin', ID), target)
        self.assertIsNone(sv.embedded_item(page, 'douyin', '123'))

    def test_tiktok_hydration_and_percent_encoded_douyin(self):
        for platform, script_id, payload in (
            ('tiktok', '__UNIVERSAL_DATA_FOR_REHYDRATION__', {'__DEFAULT_SCOPE__': {'webapp.video-detail': {'itemInfo': {'itemStruct': item('tiktok')}}}}),
            ('tiktok', 'SIGI_STATE', {'ItemModule': {ID: item('tiktok')}}),
            ('douyin', 'RENDER_DATA', {'aweme': item('douyin')}),
        ):
            raw = json.dumps(payload)
            if script_id == 'RENDER_DATA':
                raw = quote(raw)
            self.assertEqual(sv.embedded_item(f'<script id="{script_id}">{raw}</script>', platform, ID), item(platform))

    def test_douyin_formats_preserve_quality_alternates_and_duration(self):
        result = sv.parse_item(item('douyin'), 'douyin', ID, DY)
        self.assertEqual(len(result['formats']), 3)
        self.assertEqual([f['height'] for f in result['formats']], [1920, 1920, 1280])
        self.assertEqual(result['formats'][0]['tbr'], 2000)
        self.assertEqual(result['duration'], '12')
        self.assertEqual(result['video_id'], ID)
        self.assertEqual(video._create_video_base(result).platform, 'douyin')

    def test_tiktok_uses_per_stream_dimensions(self):
        result = sv.parse_item(item('tiktok'), 'tiktok', ID, TT)
        self.assertEqual(result['formats'][1]['height'], 1280)
        self.assertEqual(result['formats'][1]['filesize'], 3456)
        self.assertEqual(result['duration'], '12')

    def test_tiktok_empty_caption_uses_author_not_internal_id(self):
        target = item('tiktok')
        target['desc'] = ''
        target['author'] = {'nickname': 'まいか', 'uniqueId': 'mai.mai3588'}
        result = sv.parse_item(target, 'tiktok', ID, TT)
        self.assertEqual(result['title'], 'まいか 的视频')
        self.assertEqual(result['description'], '')
        self.assertNotIn(ID, result['title'])

    def test_missing_dimensions_remain_unknown(self):
        target = {'id': ID, 'video': {'playAddr': 'https://media.example/a.mp4'}}
        result = sv.parse_item(target, 'tiktok', ID, TT)
        self.assertIsNone(result['formats'][0]['height'])
        self.assertIsNone(result['formats'][0]['resolution'])

    def test_tiktok_prefers_first_party_play_address_at_equal_quality(self):
        target = item('tiktok')
        target['video']['playAddr'] = ''
        target['video']['bitrateInfo'][0]['PlayAddr']['UrlList'] = [
            'https://v19-webapp-prime.tiktok.com/video.mp4',
            'https://www.tiktok.com/aweme/v1/play/?video_id=fixture',
        ]
        result = sv.parse_item(target, 'tiktok', ID, TT)
        self.assertEqual(urlsplit(result['formats'][0]['url']).hostname, 'www.tiktok.com')

    def test_album_private_and_wrong_id_never_become_success(self):
        for update, reason, code in (
            ({'images': [{'url_list': ['https://media.example/a.jpg']}]}, 'unsupported_album', 422),
            ({'status': {'private_status': 1}}, 'content_unavailable', 404),
            ({'aweme_id': '999'}, 'upstream_changed', 503),
            ({'video': {}}, 'upstream_changed', 503),
        ):
            with self.assertRaises(VideoParseError) as error:
                sv.parse_item({**item('douyin'), **update}, 'douyin', ID, DY)
            self.assertTrue(error.exception.reason.endswith(reason))
            self.assertEqual(error.exception.code, code)

    def test_risk_empty_and_signature_errors_are_distinct(self):
        for value, reason in (
            (response('', 200), 'risk_control'),
            (response('{}', 200, {'tt_orcas_res': '1'}), 'risk_control'),
            (response('Blocked by ArgusSecurityPlugin Sign Invalid', 403), 'signature_rejected'),
            (response('not found', 404), 'content_unavailable'),
            (response('gateway error', 502), 'network_error'),
        ):
            with self.assertRaises(VideoParseError) as error:
                sv.check_response(value, 'douyin')
            self.assertTrue(error.exception.reason.endswith(reason))

    def test_cookie_loading_filters_domains_expiry_and_keeps_session_cookie(self):
        raw = ('# Netscape HTTP Cookie File\n'
               '.tiktok.com\tTRUE\t/\tTRUE\t0\tmsToken\tfixture-session\n'
               '.tiktok.com\tTRUE\t/\tTRUE\t1\texpired\tfixture-expired\n'
               '.youtube.com\tTRUE\t/\tTRUE\t0\tother\tfixture-other\n')
        with patch.object(sv.settings, 'TIKTOK_COOKIES_BASE64', base64.b64encode(raw.encode()).decode()):
            jar = sv.load_cookies('tiktok')
        self.assertEqual([(c.name, c.value) for c in jar], [('msToken', 'fixture-session')])

    def test_invalid_cookie_configuration_does_not_expose_input(self):
        with patch.object(sv.settings, 'TIKTOK_COOKIES_BASE64', 'private-invalid-value'):
            with self.assertRaises(VideoParseError) as error:
                sv.load_cookies('tiktok')
        self.assertEqual(error.exception.reason, 'tiktok_cookies_invalid')
        self.assertNotIn('private-invalid-value', str(error.exception))

    def test_platform_proxy_can_select_direct_connection(self):
        with patch.object(sv.settings, 'VIDEO_PROXY', 'http://global.example:8080'):
            with patch.object(sv.settings, 'DOUYIN_PROXY', ''):
                self.assertEqual(sv.platform_proxy('douyin'), '')
            with patch.object(sv.settings, 'DOUYIN_PROXY', None):
                self.assertEqual(sv.platform_proxy('douyin'), 'http://global.example:8080')


class SigningTests(unittest.TestCase):
    def test_sm3_published_vector(self):
        self.assertEqual(bytes(sm3.sm3_to_array(b'abc')).hex(), '66c7f0f462eeedd9d1f2d46bdc10e4e24167c4875cf2f7a2297da02b8f4ba8e0')

    def test_tiktok_matches_pinned_upstream_vector(self):
        # Generated from unmodified upstream d8f874c using synthetic inputs.
        query, _ = tiktok_sign.sign(
            [('aid', '1988'), ('itemId', ID)], 'fixture-agent', ms_token='',
            timestamp=1789010742, nonce=123, nonce2=456,
            key=list(range(12)), key2=list(range(12, 24)),
        )
        self.assertEqual(hashlib.sha256(query.encode()).hexdigest(), '76467c0f7f11a61b60b9791f11500a6791e4256278828d52328dd59a84e4f0e1')

    def test_douyin_web_signature_covers_exact_sent_query(self):
        url, headers = sv.signed_detail_url('douyin', ID, {'UIFID_TEMP': 'fixture', 's_v_web_id': 'verify_fixture'})
        query, signature = urlsplit(url).query.rsplit('&x-secsdk-web-signature=', 1)
        params = parse_qs(query)
        expected = hashlib.md5(f"fixture_{params['timestamp'][0]}_{websign.SALT}_{query}".encode()).hexdigest()
        self.assertEqual(signature, expected)
        self.assertEqual(headers['x-secsdk-web-signature'], expected)
        self.assertEqual(params['verifyFp'], ['verify_fixture'])
        self.assertIn('a_bogus', params)

    def test_tiktok_signature_order_and_token(self):
        url, _ = sv.signed_detail_url('tiktok', ID, {'msToken': 'fixture-token'})
        query = urlsplit(url).query
        names = [part.split('=', 1)[0] for part in query.split('&')]
        self.assertEqual(names[-4:], ['X-Dynosaur', 'msToken', 'X-Bogus', 'X-Gnarly'])
        self.assertEqual(names.count('msToken'), 1)
        self.assertIn('&msToken=fixture-token&X-Bogus=1&', query)


class AsyncParserTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Parser tests mock transport; DNS must be deterministic as well.
        self.dns = patch.object(video.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('93.184.216.34', 443))])
        self.dns.start()
        self.addCleanup(self.dns.stop)

    async def test_multi_hop_relative_redirect_and_single_session(self):
        session = SimpleNamespace(get=AsyncMock(side_effect=[
            response('', 302, {'location': '/second'}),
            response('', 302, {'location': DY}), response('page'),
        ]))
        final, _ = await sv.get_page(session, 'https://v.douyin.com/first', 'douyin')
        self.assertEqual(final, DY)
        self.assertEqual(session.get.call_args_list[1].args[0], 'https://v.douyin.com/second')
        self.assertTrue(all(call.kwargs['allow_redirects'] is False for call in session.get.call_args_list))

    async def test_redirect_rejected_before_contacting_another_host(self):
        for target in ('http://127.0.0.1/admin', 'https://www.douyin.com.evil.example/', 'file:///etc/passwd', 'https://www.tiktok.com/'):
            session = SimpleNamespace(get=AsyncMock(return_value=response('', 302, {'location': target})))
            with self.assertRaises(VideoParseError):
                await sv.get_page(session, 'https://v.douyin.com/first', 'douyin')
            session.get.assert_awaited_once()

    async def test_signed_api_fallback_preserves_query_bytes_and_session(self):
        session = MagicMock()
        session.cookies = Cookies()
        session.get = AsyncMock(side_effect=[response('<html>no hydration data</html>'), response(json.dumps({'itemInfo': {'itemStruct': item('tiktok')}}))])
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=session)
        context.__aexit__ = AsyncMock(return_value=None)
        with patch.object(sv.requests, 'AsyncSession', return_value=context) as factory:
            with patch.object(sv, 'load_cookies', return_value=Cookies().jar):
                result = await sv.parse(TT)
        self.assertEqual(result['video_id'], ID)
        self.assertEqual(factory.call_args.kwargs['headers']['User-Agent'], sv.USER_AGENT)
        request = session.get.call_args_list[1]
        self.assertIn('X-Gnarly=', request.args[0])
        self.assertIs(request.kwargs['quote'], False)
        self.assertIs(request.kwargs['allow_redirects'], False)

    async def test_platform_error_survives_ytdlp_failure(self):
        error = sv.failure('tiktok', 'signature_rejected')
        with patch.object(sv, 'parse', new=AsyncMock(side_effect=error)):
            with patch.object(video, 'yt_dlp_parse', new=AsyncMock(side_effect=sv.failure('tiktok', 'upstream_changed'))):
                with patch.object(video, 'openapi_parse') as external:
                    with self.assertRaises(VideoParseError) as caught:
                        await video.dispatch(TT)
        self.assertIs(caught.exception, error)
        external.assert_not_called()

    async def test_failed_parse_does_not_charge_credits(self):
        with patch.object(video, 'dispatch', new=AsyncMock(side_effect=sv.failure('douyin', 'risk_control'))):
            with patch.object(video, 'complete_video_transaction') as charge:
                with self.assertRaises(VideoParseError):
                    await video.extract('分享文字 ' + DY, current_user=object(), db=object())
        charge.assert_not_called()

    async def test_successful_share_text_reaches_transaction_with_stable_id(self):
        data = sv.parse_item(item('tiktok'), 'tiktok', ID, TT)
        with patch.object(video, 'dispatch', new=AsyncMock(return_value=data)) as dispatch:
            with patch.object(video, 'complete_video_transaction') as charge:
                result = await video.extract('分享文字 ' + TT, current_user=object(), db=object())
        dispatch.assert_awaited_once_with(TT)
        self.assertEqual(result.video_id, ID)
        self.assertEqual(charge.call_args.kwargs['video_data'].platform, 'tiktok')
