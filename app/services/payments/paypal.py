import paypalrestsdk
from typing import Optional
from decimal import Decimal

from app.core.config import settings

class PayPalService:
    def __init__(self):
        """初始化PayPal客户端"""
        paypalrestsdk.configure({
            "mode": "sandbox" if not settings.PRODUCTION else "live",  # sandbox or live
            "client_id": settings.PAYPAL_CLIENT_ID,
            "client_secret": settings.PAYPAL_CLIENT_SECRET
        })

    def create_payment(self, order_id: str, amount: Decimal, description: str) -> Optional[str]:
        """创建PayPal支付"""
        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {
                "payment_method": "paypal"
            },
            "redirect_urls": {
                "return_url": f"{settings.FRONTEND_URL}/payment/result?internal_order_id={order_id}&status=success",
                "cancel_url": f"{settings.FRONTEND_URL}/payment/cancel"
            },
            "transactions": [{
                "item_list": {
                    "items": [{
                        "name": description,
                        "price": str(amount),
                        "currency": "USD",
                        "quantity": 1
                    }]
                },
                "amount": {
                    "total": str(amount),
                    "currency": "USD"
                },
                "description": f"Order: {order_id}"
            }]
        })

        if payment.create():
            # 返回PayPal支付链接
            for link in payment.links:
                if link.method == "REDIRECT":
                    return link.href
        return None

    def verify_payment(self, payment_id: str) -> tuple[bool, Optional[str]]:
        """验证PayPal支付状态"""
        try:
            payment = paypalrestsdk.Payment.find(payment_id)
            if payment.state == "approved":
                # 返回支付成功和交易号
                return True, payment.transactions[0].related_resources[0].sale.id
            return False, None
        except Exception as e:
            print(f"PayPal payment verification error: {str(e)}")
            return False, None

    def execute_payment(self, payment_id: str, payer_id: str) -> bool:
        """执行PayPal支付"""
        try:
            payment = paypalrestsdk.Payment.find(payment_id)
            if payment.execute({"payer_id": payer_id}):
                return True
            return False
        except Exception as e:
            print(f"PayPal payment execution error: {str(e)}")
            return False

    def refund_payment(self, sale_id: str, amount: Decimal) -> bool:
        """退款"""
        try:
            sale = paypalrestsdk.Sale.find(sale_id)
            refund = sale.refund({
                "amount": {
                    "total": str(amount),
                    "currency": "USD"
                }
            })
            return refund.success()
        except Exception as e:
            print(f"PayPal refund error: {str(e)}")
            return False 