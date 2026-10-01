"""Run without application/database fixtures: python -m unittest tests.test_yt_dlp_vendor."""

import sys
import unittest

from app.vendor import yt_dlp
from app.vendor.yt_dlp.extractor import gen_extractor_classes
from app.vendor.yt_dlp.extractor.youtube.jsc._director import initialize_jsc_director
from app.vendor.yt_dlp.extractor.youtube.jsc._builtin.deno import DenoJCP
from app.vendor.yt_dlp.extractor.youtube.jsc._builtin.ejs import ScriptSource
from app.vendor.yt_dlp.version import __version__


class VendoredYtDlpTests(unittest.TestCase):
    def test_platform_routing_uses_vendored_extractors(self):
        urls = {
            'https://www.youtube.com/watch?v=BaW_jenozKc': 'youtube',
            'https://www.youtube.com/playlist?list=PL1234567890': 'youtube:tab',
            'https://www.tiktok.com/@test/video/1234567890123456789': 'TikTok',
            'https://www.facebook.com/watch/?v=123456789': 'facebook',
        }
        self.assertEqual(__version__, '2026.08.19')
        extractors = gen_extractor_classes()
        with yt_dlp.YoutubeDL({'quiet': True, 'cachedir': False}) as ydl:
            for url, expected in urls.items():
                with self.subTest(url=url):
                    cls = next(ie for ie in extractors if ie.suitable(url))
                    self.assertEqual(cls.IE_NAME, expected)
                    instance = ydl.get_info_extractor(cls.ie_key())
                    self.assertTrue(type(instance).__module__.startswith('app.vendor.yt_dlp.'))
        self.assertNotIn('yt_dlp', sys.modules)

    def test_custom_extension_still_imports(self):
        from app.vendor.yt_dlp.extractor.extend import parse_video_share_url
        self.assertTrue(callable(parse_video_share_url))

    def test_youtube_deno_and_local_ejs_scripts(self):
        with yt_dlp.YoutubeDL({'quiet': True, 'cachedir': False}) as ydl:
            director = initialize_jsc_director(ydl.get_info_extractor('Youtube'))
            provider = next(p for p in director.providers.values() if isinstance(p, DenoJCP))
            self.assertTrue(provider.is_available(), 'Install requirements and add Deno to PATH')
            for script in (provider._lib_script, provider._core_script):
                self.assertEqual(script.source, ScriptSource.PYPACKAGE)
                self.assertEqual(script.version, '0.8.0')
            self.assertEqual(provider._run_js_runtime('console.log(JSON.stringify({ok: true}));').strip(), '{"ok":true}')


if __name__ == '__main__':
    unittest.main()
