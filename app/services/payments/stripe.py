import stripe
from typing import Optional
from decimal import Decimal

from app.core.config import settings

class StripeService:
    def __init__(self):
        """初始化Stripe客户端"""
        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.public_key = settings.STRIPE_PUBLIC_KEY

    def create_payment_intent(self, order_id: str, amount: Decimal, currency: str = "usd") -> Optional[str]:
        """创建Stripe支付意图"""
        try:    
            # Stripe金额以最小单位计算（例如，美元以分为单位）
            amount_cents = int(amount * 100)
            
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency,
                metadata={"order_id": order_id},
                automatic_payment_methods={"enabled": True}
            )
            return intent.client_secret
        except Exception as e:
            print(f"Stripe payment intent creation error: {str(e)}")
            return None

    def verify_payment(self, payment_intent_id: str) -> tuple[bool, Optional[str]]:
        """验证Stripe支付状态"""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            if intent.status == "succeeded":
                return True, intent.id
            return False, None
        except Exception as e:
            print(f"Stripe payment verification error: {str(e)}")
            return False, None

    def refund_payment(self, payment_intent_id: str, amount: Optional[Decimal] = None) -> bool:
        """退款"""
        try:
            refund_params = {"payment_intent": payment_intent_id}
            if amount:
                refund_params["amount"] = int(amount * 100)
            
            refund = stripe.Refund.create(**refund_params)
            return refund.status == "succeeded"
        except Exception as e:
            print(f"Stripe refund error: {str(e)}")
            return False

    def create_checkout_session(self, order_id: str, amount: Decimal, currency: str, description: str) -> Optional[str]:
        """创建Stripe结账会话（用于快速集成）"""
        try:            
            amount_cents = int(amount * 100)
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                payment_intent_data={"metadata": {"order_id": order_id}},
                line_items=[{
                    "price_data": {
                        "currency": currency,
                        "unit_amount": amount_cents,
                        "product_data": {
                            "name": description,
                        },
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=f"{settings.FRONTEND_URL}/payment/result?internal_order_id={order_id}&status=success",
                cancel_url=f"{settings.FRONTEND_URL}/profile",
                metadata={"order_id": order_id}
            )
            return session.url
        except Exception as e:
            print(f"Stripe checkout session creation error: {str(e)}")
            return None

    def handle_webhook(self, payload: bytes, signature: str) -> bool:
        """处理Stripe Webhook"""
        try:
            if not signature:
                print("Stripe webhook error: Missing signature in request header")
                return False
                
            if not settings.STRIPE_WEBHOOK_SECRET:
                print("Stripe webhook error: Webhook secret not configured")
                return False
                
            try:
                event = stripe.Webhook.construct_event(
                    payload,
                    signature,
                    settings.STRIPE_WEBHOOK_SECRET
                )
            except stripe.error.SignatureVerificationError as e:
                print(f"Stripe webhook signature verification error: {str(e)}")
                return False
            except Exception as e:
                print(f"Stripe webhook event construction error: {str(e)}")
                return False
            
            if event.type == "payment_intent.succeeded":
                payment_intent = event.data.object
                order_id = payment_intent.metadata.get("order_id")
                print(f"Stripe webhook: Payment intent {payment_intent} received")
                print(f"Stripe webhook: Order ID {order_id}")
                return True
            return False
        except stripe.error.SignatureVerificationError as e:
            print(f"Stripe webhook signature verification failed: {str(e)}")
            return False
        except Exception as e:
            print(f"Stripe webhook error: {str(e)}")
            return False