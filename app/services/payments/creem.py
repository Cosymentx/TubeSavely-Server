from typing import Optional
from decimal import Decimal
import requests
import hashlib
import hmac
import json
from app.core.config import settings
from app.models.payment import Payment

class CreemService:
    def __init__(self):
        self.api_key = settings.CREEM_API_KEY
        self.base_url = settings.CREEM_API_BASE_URL
        # self.base_url = "https://test-api.creem.io/v1/checkouts"
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        self.return_url_template = f"{settings.FRONTEND_URL}/payment/result?internal_order_id={{order_id}}&status=success"
        self.notify_url = f"{settings.API_URL}/api/v1/payments/webhook/creem"

    def create_payment(self, order_id: str, product_id: str, customer_email: str = "") -> Optional[dict]:
        try:
            payload = {
                'product_id': product_id,
                'request_id': order_id,
                'units': 1,
                'success_url': self.return_url_template.format(order_id=order_id),
                'metadata': {'order_id': order_id},
            }
            if customer_email:
                payload['customer'] = {'email': customer_email}
            response = requests.post(self.base_url, json=payload, headers=self.headers, timeout=20)
            if response.status_code in (200, 201):
                data = response.json()
                if data.get('checkout_url') and data.get('id'):
                    return {'url': data['checkout_url'], 'id': data['id']}
            return None
        except Exception:
            return None

    def retrieve_checkout(self, checkout_id: str) -> Optional[dict]:
        try:
            response = requests.get(self.base_url, params={'checkout_id': checkout_id},
                                    headers=self.headers, timeout=20)
            return response.json() if response.ok else None
        except Exception:
            return None

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        if not settings.CREEM_WEBHOOK_SECRET or not signature:
            return False
        expected = hmac.new(settings.CREEM_WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def verify_payment(self, webhook_data: dict) -> tuple[bool, Optional[str], Optional[str]]:
        """
        验证 Creem 支付回调
        
        Args:
            webhook_data: Webhook 回调数据
            
        Returns:
            tuple[bool, Optional[str], Optional[str]]: (验证是否成功, 交易号, 订单ID)
        """
        try:
            # 检查事件类型
            if webhook_data.get('eventType') != 'checkout.completed':
                return False, None, None
                
            # 获取 checkout 对象
            checkout = webhook_data.get('object')
            if not checkout:
                return False, None, None
                
            # 检查支付状态
            if checkout.get('status') != 'completed':
                return False, None, None
                
            # 获取订单信息
            order = checkout.get('order')
            if not order or order.get('status') != 'paid':
                return False, None, None
            transaction_id = order.get('id')
                
            # 从 metadata 中获取我们的订单 ID
            metadata = checkout.get('metadata', {})
            if not metadata.get('order_id'):
                return False, None, None

            # 返回成功和交易号（使用 Creem 的 checkout ID 作为交易号）
            return True, transaction_id, metadata.get('order_id')
            
        except Exception as e:
            print(f"Creem verify_payment error: {str(e)}")
            return False, None, None

    def query_payment(self, order_id: str) -> tuple[str, Optional[str]]:
        """查询支付状态"""
        try:
            query_url = f"{self.base_url}/{order_id}"
            response = requests.get(query_url, headers=self.headers)
            
            if response.status_code == 200:
                result = response.json()
                status = result.get("status")
                if status == "completed":
                    return "completed", result.get("transaction_id")
                elif status == "pending":
                    return "pending", None
                else:
                    return "failed", None
            return "failed", None
        except Exception as e:
            print(f"Creem payment query error: {str(e)}")
            return "failed", None

    def refund_payment(self, transaction_id: str, amount: Decimal, reason: str = "") -> bool:
        """退款"""
        try:
            refund_url = f"{self.base_url}/refund"
            payload = {
                "transaction_id": transaction_id,
                "amount": str(amount),
                "reason": reason
            }
            response = requests.post(refund_url, json=payload, headers=self.headers)
            
            if response.status_code == 200:
                result = response.json()
                return result.get("status") == "success"
            return False
        except Exception as e:
            print(f"Creem refund error: {str(e)}")
            return False
