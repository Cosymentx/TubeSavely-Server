from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal
import json
import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.payment import Payment

class AirwallexService:
    def __init__(self):
        self.api_key = settings.AIRWALLEX_API_KEY
        self.client_id = settings.AIRWALLEX_CLIENT_ID
        # 根据环境变量决定使用哪个环境
        self.base_url = "https://api.airwallex.com/api/v1"
        self.checkout_url = "https://checkout.airwallex.com/pay"
        self.access_token = None
        self.headers = {
            "x-api-key": self.api_key,
            "x-client-id": self.client_id,
            "Content-Type": "application/json"
        }

    
    def get_access_token(self) -> Optional[str]:
        """获取访问令牌"""
        url = f"{self.base_url}/authentication/login"
        
        try:
            print(f"Attempting to get access token from: {url}")
            response = requests.post(url, headers=self.headers)
            if not response.ok:
                print(f"Authentication error response: {response.text}")
            response.raise_for_status()
            result = response.json()
            
            self.access_token = result.get("token")

            if self.access_token:
                self.headers["Authorization"] = f"Bearer {self.access_token}"
                print("Successfully obtained access token")
            else:
                print("No access token in response")
            return self.access_token
        except requests.exceptions.RequestException as e:
            print(f"Airwallex authentication error: {str(e)}")
            if hasattr(e.response, 'text'):
                print(f"Authentication error details: {e.response.text}")
            return None
    
    def create_payment(self, order_id: str, amount: Decimal, description: str, currency: str = "USD") -> Optional[str]:
        """创建支付意向"""
        # 确保有访问令牌
        if not self.access_token and not self.get_access_token():
            print("Failed to get access token")
            return None
            
        url = f"{self.base_url}/pa/payment_intents/create"
        print(f"Creating payment intent at: {url}")
        
        # 确保金额格式正确（保留两位小数）
        formatted_amount = float(round(amount, 2))
        
        # 简化请求结构，移除可能需要特殊配置的字段
        payload = {
            "amount": formatted_amount,
            "currency": currency,
            "request_id": order_id,  # 唯一请求ID
            "merchant_order_id": order_id,  # 商户订单号
            "return_url": f"{settings.FRONTEND_URL}/payment/result?internal_order_id={order_id}",
            "metadata": {
                "order_id": order_id
            }
        }
        
        print(f"Payment request payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            if not response.ok:
                print(f"Airwallex error response: {response.text}")
                if hasattr(response, 'json'):
                    error_data = response.json()
                    if error_data.get('code') == 'configuration_error':
                        print("Configuration error details:", json.dumps(error_data, indent=2))
            response.raise_for_status()
            result = response.json()
            print(f"Payment intent creation response: {json.dumps(result, indent=2)}")
            
            # 获取支付链接
            payment_intent_id = result.get("id")
            if payment_intent_id:
                # 使用 Hosted Payment Page
                checkout_url = f"{self.checkout_url}/{payment_intent_id}?intent_id={payment_intent_id}&client_id={self.client_id}"
                print(f"Generated checkout URL: {checkout_url}")
                return checkout_url
            print("No payment_intent_id in response")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Airwallex payment creation error: {str(e)}")
            if hasattr(e.response, 'text'):
                print(f"Error details: {e.response.text}")
            return None
    
    def verify_webhook_signature(self, signature: str, payload: str) -> bool:
        """验证 Webhook 签名"""
        # TODO: 实现签名验证逻辑
        return True
    
    def handle_webhook(self, db: Session, event_type: str, data: Dict[str, Any]) -> Optional[Payment]:
        """处理 Webhook 回调"""
        if event_type != "payment_intent.succeeded":
            return None
            
        order_id = data.get("merchant_order_id")
        if not order_id:
            return None
            
        payment = db.query(Payment).filter(Payment.order_id == order_id).first()
        if not payment or payment.status == "completed":
            return None
            
        payment.status = "completed"
        payment.trade_no = data.get("id")  # Airwallex 支付意向 ID
        payment.paid_at = datetime.utcnow()
        
        db.commit()
        db.refresh(payment)
        
        return payment