from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core import deps
from app.api.v1.endpoints import credit, credit_amount, user
from app.schemas.user import UserCreate, UserUpdate
from app.services import user as user_service


class AccountPermissions(unittest.TestCase):
    def test_registration_cannot_request_administrator_role(self):
        with self.assertRaises(ValidationError):
            UserCreate(email='fixture@example.com', username='Fixture', password='fixture-password', is_superuser=True)
        # The service remains safe even if called with an unvalidated object.
        account = SimpleNamespace(email='fixture@example.com', username='Fixture', password='fixture-password', is_superuser=True)
        with patch.object(user_service, 'validate_new_user'):
            with patch.object(user_service, 'get_password_hash', return_value='fixture'):
                with patch.object(user_service, '_create_user_in_db') as create:
                    user_service.create_user(None, account)
        self.assertIs(create.call_args.kwargs['is_superuser'], False)

    def test_profile_update_does_not_accept_balance_or_account_controls(self):
        for payload in ({'credits': 999999}, {'is_superuser': True}, {'is_active': True}):
            with self.assertRaises(ValidationError):
                UserUpdate(**payload)

    def test_normal_account_cannot_modify_prices_or_grant_credits(self):
        app = FastAPI()
        app.include_router(credit.router, prefix='/credits')
        app.include_router(credit_amount.router, prefix='/credit_amount')
        app.include_router(user.router, prefix='/users')
        app.dependency_overrides[deps.get_db] = lambda: None
        app.dependency_overrides[deps.get_current_user] = lambda: SimpleNamespace(id=1, is_superuser=False)
        with TestClient(app) as client:
            for method, path, kwargs in (
                ('post', '/credits/add?credits=100&action=fixture', {}),
                ('post', '/credits/deduct?credits=1&action=fixture', {}),
                ('post', '/credit_amount/', {'json': {'credits': 100, 'amount_cny': 9.99, 'amount_usd': 9.99, 'creem_product_id': 'fixture'}}),
                ('put', '/credit_amount/1', {'json': {'amount_usd': 0.01}}),
                ('delete', '/credit_amount/1', {}),
                ('get', '/users/', {}),
            ):
                with self.subTest(path=path):
                    self.assertEqual(getattr(client, method)(path, **kwargs).status_code, 403)
