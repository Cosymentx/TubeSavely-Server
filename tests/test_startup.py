import builtins
import importlib
import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

with patch.dict(os.environ, {"REDIS_URL": "", "BACKEND_CORS_ORIGINS": '["https://frontend.example.com"]'}):
    import main


class StartupTests(unittest.TestCase):
    def test_application_import_does_not_require_uvicorn(self):
        original_import = builtins.__import__

        def without_uvicorn(name, *args, **kwargs):
            if name == 'uvicorn':
                raise ModuleNotFoundError("No module named 'uvicorn'")
            return original_import(name, *args, **kwargs)

        with patch.dict(os.environ, {"REDIS_URL": "", "BACKEND_CORS_ORIGINS": '["https://frontend.example.com"]'}):
            with patch('builtins.__import__', side_effect=without_uvicorn):
                importlib.reload(main)
        self.assertIsNotNone(main.app)

    def test_docs_and_health_without_redis(self):
        with patch.object(main, 'REDIS_URL', ''):
            with patch.object(main.redis, 'from_url') as redis_factory:
                with TestClient(main.app) as client:
                    self.assertEqual(client.get('/docs').status_code, 200)
                    self.assertEqual(client.get('/openapi.json').status_code, 200)
                    self.assertEqual(client.get('/health').json()['services']['redis'], 'disabled')
                    self.assertEqual(client.get('/test', params={'params': 'hello'}).json(), {'hi': 'hello'})
                redis_factory.assert_not_called()

    def test_cors_preflight(self):
        with patch.object(main, 'REDIS_URL', ''):
            with TestClient(main.app) as client:
                response = client.options('/parse', headers={
                    'Origin': 'https://frontend.example.com',
                    'Access-Control-Request-Method': 'GET',
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['access-control-allow-origin'], 'https://frontend.example.com')

    def test_redis_failure_keeps_docs_available_and_blocks_limited_routes(self):
        connection = AsyncMock()
        with patch.object(main, 'REDIS_URL', 'redis://test.invalid:6379'):
            with patch.object(main.redis, 'from_url', return_value=connection):
                with patch.object(main.FastAPILimiter, 'init', new=AsyncMock(side_effect=ConnectionError('unavailable'))):
                    with TestClient(main.app) as client:
                        self.assertEqual(client.get('/docs').status_code, 200)
                        self.assertEqual(client.get('/health').json()['status'], 'unhealthy')
                        self.assertEqual(client.get('/test', params={'params': 'hello'}).status_code, 503)
        connection.aclose.assert_awaited_once()

    def test_configured_redis_applies_rate_limiter(self):
        connection = AsyncMock()
        with patch.object(main, 'REDIS_URL', 'redis://test.invalid:6379'):
            with patch.object(main.redis, 'from_url', return_value=connection):
                with patch.object(main.FastAPILimiter, 'init', new=AsyncMock()):
                    with patch.object(main.FastAPILimiter, 'close', new=AsyncMock()) as close:
                        with patch.object(main, 'RateLimiter', return_value=AsyncMock()) as factory:
                            with TestClient(main.app) as client:
                                self.assertEqual(client.get('/test', params={'params': 'hello'}).status_code, 200)
                            factory.assert_called_once_with(times=1, seconds=5)
                            factory.return_value.assert_awaited_once()
                        close.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
