"""Payment integration tests use fake provider responses and a disposable SQLite database."""

from decimal import Decimal
from unittest.mock import patch

from test_startup import FullBackendTests, app
from app.api.v1.endpoints import payment as payment_endpoint
from app.core.config import settings
from app.models.credit import Credit
from app.models.credit_amount import CreditAmount
from app.models.payment import Payment
from app.services import payment as payment_service
from sqlalchemy.orm import sessionmaker


class CheckoutTests(FullBackendTests):
    def create_account(self):
        credentials = {
            'email': 'checkout@example.com',
            'username': 'checkout-user',
            'password': 'checkout-password-123',
        }
        response = self.client.post('/api/v1/auth/register', json=credentials).json()
        self.assertEqual(response['code'], 200, response['msg'])
        return {'Authorization': f"Bearer {response['data']['access_token']}"}

    def add_price(self):
        with sessionmaker(bind=self.engine)() as session:
            session.add(CreditAmount(
                credits=100, amount_cny=9.99, amount_usd=9.99,
                creem_product_id='prod_51FPgJ7cgMp49sXIWdFqx6', is_active=True,
            ))
            session.commit()

    def test_stripe_checkout_tracks_order_and_grants_credits_only_once(self):
        headers = self.create_account()
        self.add_price()
        with patch.object(settings, 'STRIPE_SECRET_KEY', 'sk_test_configured'):
            with patch.object(payment_endpoint.stripe_service, 'create_checkout_session', return_value={
                'url': 'https://checkout.stripe.com/c/pay/session', 'id': 'cs_test_12345',
            }):
                created = self.client.post(
                    '/api/v1/payments/create?credit_amount_id=1&currency=USD&payment_method=stripe',
                    headers=headers,
                ).json()

        self.assertEqual(created['code'], 200, created['msg'])
        order_id = created['data']['order_id']
        with sessionmaker(bind=self.engine)() as session:
            payment = session.query(Payment).filter_by(order_id=order_id).one()
            self.assertEqual(payment.provider_checkout_id, 'cs_test_12345')
            self.assertEqual(payment.currency, 'USD')
            user_id = payment.user_id

        checkout = {
            'id': 'cs_test_12345', 'payment_status': 'paid', 'currency': 'usd',
            'amount_total': 999, 'metadata': {'order_id': order_id},
            'payment_intent': {'id': 'pi_test_12345'},
        }
        with patch('app.services.payments.stripe.StripeService.retrieve_checkout', return_value=checkout):
            for _ in range(2):
                result = self.client.get(f"/api/v1/payments/status/{order_id}", headers=headers).json()
                self.assertEqual(result['data']['status'], 'completed')

        with sessionmaker(bind=self.engine)() as session:
            user = session.get(__import__('app.models.user', fromlist=['User']).User, user_id)
            self.assertEqual(user.credits, 150)  # 50 signup credits + 100 paid credits
            self.assertEqual(session.query(Credit).filter_by(user_id=user_id, action='Recharge').count(), 1)

    def test_failed_checkout_does_not_grant_credits(self):
        headers = self.create_account()
        self.add_price()
        with patch.object(settings, 'STRIPE_SECRET_KEY', 'sk_test_configured'):
            with patch.object(payment_endpoint.stripe_service, 'create_checkout_session', return_value={
                'url': 'https://checkout.stripe.com/c/pay/session', 'id': 'cs_test_67890',
            }):
                created = self.client.post(
                    '/api/v1/payments/create?credit_amount_id=1&currency=USD&payment_method=stripe',
                    headers=headers,
                ).json()

        order_id = created['data']['order_id']
        checkout = {
            'id': 'cs_test_67890', 'payment_status': 'paid', 'currency': 'usd',
            'amount_total': 1000, 'metadata': {'order_id': order_id},
            'payment_intent': {'id': 'pi_test_wrong_amount'},
        }
        with patch('app.services.payments.stripe.StripeService.retrieve_checkout', return_value=checkout):
            result = self.client.get(f"/api/v1/payments/status/{order_id}", headers=headers).json()
        self.assertEqual(result['data']['status'], 'pending')

    def test_refund_reverses_credits_once_and_allows_debt(self):
        headers = self.create_account()
        self.add_price()
        with patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_configured"):
            with patch.object(payment_endpoint.stripe_service, "create_checkout_session", return_value={
                "url": "https://checkout.stripe.com/c/pay/session", "id": "cs_refund_123",
            }):
                created = self.client.post(
                    "/api/v1/payments/create?credit_amount_id=1&currency=USD&payment_method=stripe",
                    headers=headers,
                ).json()

        order_id = created["data"]["order_id"]
        checkout = {
            "id": "cs_refund_123", "payment_status": "paid", "currency": "usd",
            "amount_total": 999, "metadata": {"order_id": order_id},
            "payment_intent": {"id": "pi_refund_123"},
        }
        with patch("app.services.payments.stripe.StripeService.retrieve_checkout", return_value=checkout):
            self.client.get(f"/api/v1/payments/status/{order_id}", headers=headers)

        with sessionmaker(bind=self.engine)() as session:
            payment = session.query(Payment).filter_by(order_id=order_id).one()
            user = session.get(__import__("app.models.user", fromlist=["User"]).User, payment.user_id)
            user.credits = 10
            session.commit()

            payment_service.reverse_payment_credits(
                session, payment,
                status=payment_service.PaymentStatus.REFUNDED,
                reason="test refund",
            )
            payment_service.reverse_payment_credits(
                session, payment,
                status=payment_service.PaymentStatus.REFUNDED,
                reason="duplicate refund",
            )

            session.refresh(user)
            session.refresh(payment)
            self.assertEqual(user.credits, -90)
            self.assertEqual(payment.status, "refunded")
            self.assertTrue(payment.credit_reversal_applied)
            self.assertEqual(
                session.query(Credit).filter_by(user_id=user.id, action="PaymentReversal").count(),
                1,
            )

    def test_won_dispute_restores_reversed_credits_once(self):
        headers = self.create_account()
        self.add_price()
        with patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_configured"):
            with patch.object(payment_endpoint.stripe_service, "create_checkout_session", return_value={
                "url": "https://checkout.stripe.com/c/pay/session", "id": "cs_dispute_123",
            }):
                created = self.client.post(
                    "/api/v1/payments/create?credit_amount_id=1&currency=USD&payment_method=stripe",
                    headers=headers,
                ).json()

        order_id = created["data"]["order_id"]
        checkout = {
            "id": "cs_dispute_123", "payment_status": "paid", "currency": "usd",
            "amount_total": 999, "metadata": {"order_id": order_id},
            "payment_intent": {"id": "pi_dispute_123"},
        }
        with patch("app.services.payments.stripe.StripeService.retrieve_checkout", return_value=checkout):
            self.client.get(f"/api/v1/payments/status/{order_id}", headers=headers)

        with sessionmaker(bind=self.engine)() as session:
            payment = session.query(Payment).filter_by(order_id=order_id).one()
            user = session.get(__import__("app.models.user", fromlist=["User"]).User, payment.user_id)
            starting = user.credits

            payment_service.reverse_payment_credits(
                session, payment,
                status=payment_service.PaymentStatus.DISPUTED,
                reason="test dispute",
            )
            payment_service.restore_disputed_credits(session, payment)
            payment_service.restore_disputed_credits(session, payment)

            session.refresh(user)
            session.refresh(payment)
            self.assertEqual(user.credits, starting)
            self.assertEqual(payment.status, "completed")
            self.assertFalse(payment.credit_reversal_applied)
            self.assertEqual(
                session.query(Credit).filter_by(user_id=user.id, action="DisputeWon").count(),
                1,
            )
