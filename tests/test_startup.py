import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.update({
    'VERCEL': '1', 'PRODUCTION': 'true', 'DATABASE_URL': 'sqlite://',
    'SECRET_KEY': 'temporary-test-secret-that-is-long-enough-for-ci',
    'BACKEND_CORS_ORIGINS': '["https://tube-savely-vue.vercel.app"]',
})

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.core.deps import get_db
from app.db.session import get_db as health_db
from app.db.base_class import Base
from app.services.payments.alipay import AlipayService
from fastapi.middleware.cors import CORSMiddleware


class FullBackendTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        factory = sessionmaker(bind=self.engine)

        def database():
            with factory() as session:
                yield session

        app.dependency_overrides[get_db] = database
        app.dependency_overrides[health_db] = database
        self.redis = AsyncMock()
        cors = next(middleware for middleware in app.user_middleware if middleware.cls is CORSMiddleware)
        # Each test owns its CORS fixture regardless of module import order.
        app.middleware_stack = None
        self.patches = [
            patch.dict(cors.kwargs, {'allow_origins': ['https://tube-savely-vue.vercel.app', 'https://tubesavely.vercel.app']}),
            patch('app.main.redis.from_url', return_value=self.redis),
            patch('app.main.FastAPILimiter.init', new=AsyncMock()),
            patch('app.main.FastAPILimiter.close', new=AsyncMock()),
            patch('app.main.FastAPILimiter.redis', self.redis),
        ]
        for item in self.patches:
            item.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        app.dependency_overrides.clear()
        app.middleware_stack = None
        self.engine.dispose()

    def test_production_openapi_exposes_only_enabled_business_routes(self):
        self.assertEqual(self.client.get('/docs').status_code, 404)
        paths = self.client.get('/api/v1/openapi.json').json()['paths']
        for path in ['/api/v1/auth/register', '/api/v1/auth/login', '/api/v1/users/profile',
                     '/api/v1/videos/parse', '/api/v1/payments/create', '/api/v1/payments/orders',
                     '/api/v1/credits/', '/api/v1/feedback/']:
            self.assertIn(path, paths)
        self.assertNotIn('/api/v1/tasks/convert', paths)

    def test_register_login_profile_and_payment_history(self):
        account = {'email': 'deployment@example.com', 'username': 'deployment', 'password': 'test-password-123'}
        registration = self.client.post('/api/v1/auth/register', json=account).json()
        self.assertEqual(registration['code'], 200, registration.get('msg'))
        login = self.client.post('/api/v1/auth/login', json={k: account[k] for k in ['email', 'password']}).json()
        self.assertEqual(login['code'], 200, login.get('msg'))
        headers = {'Authorization': 'Bearer ' + login['data']['access_token']}
        profile = self.client.get('/api/v1/users/profile', headers=headers).json()
        self.assertEqual(profile['data']['email'], account['email'])
        orders = self.client.get('/api/v1/payments/orders', headers=headers).json()
        self.assertEqual(orders['code'], 200)
        self.assertEqual(orders['data'], [])

    def test_protected_routes_require_login(self):
        self.assertEqual(self.client.get('/api/v1/users/profile').status_code, 401)
        self.assertEqual(self.client.get('/api/v1/payments/orders').status_code, 401)

    def test_frontend_cors_preflight(self):
        response = self.client.options('/api/v1/auth/login', headers={
            'Origin': 'https://tube-savely-vue.vercel.app',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'content-type,authorization',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['access-control-allow-origin'], 'https://tube-savely-vue.vercel.app')

    def test_health_checks_database_and_redis(self):
        response = self.client.get('/api/v1/health')
        self.assertEqual(response.json()['status'], 'healthy')

    def test_alipay_credentials_are_loaded_only_on_payment_use(self):
        with patch('app.services.payments.alipay.AliPay') as factory:
            service = AlipayService()
            factory.assert_not_called()
            self.assertIs(service.client, factory.return_value)
            self.assertIs(service.client, factory.return_value)
            factory.assert_called_once()


if __name__ == '__main__':
    unittest.main()
