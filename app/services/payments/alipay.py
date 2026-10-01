from typing import Optional
from decimal import Decimal
from functools import cached_property
from alipay import AliPay
from alipay.utils import AliPayConfig

from app.core.config import settings

class AlipayService:
    def __init__(self):
        self.return_url_template = f"{settings.FRONTEND_URL}/payment/result?internal_order_id={{order_id}}&status=success"
        self.notify_url = f"{settings.API_URL}/api/v1/payments/webhook/alipay"

    @cached_property
    def client(self):
        """Load payment credentials when an Alipay operation is requested."""
        return AliPay(
            appid=settings.ALIPAY_APP_ID,
            app_notify_url=None,
            app_private_key_string=settings.ALIPAY_PRIVATE_KEY,
            alipay_public_key_string=settings.ALIPAY_PUBLIC_KEY,
            sign_type="RSA2",
            debug=not settings.PRODUCTION,
            config=AliPayConfig(timeout=15) 
        )

    def create_payment(self, order_id: str, amount: Decimal, currency: str, description: str) -> Optional[str]:
        """创建支付宝支付订单"""
        try:
            # 使用实际的order_id动态生成return_url
            return_url = self.return_url_template.format(order_id=order_id)
            
            order_string = self.client.api_alipay_trade_page_pay(
                out_trade_no=order_id,
                total_amount=str(amount),
                subject=description,
                currency=currency,
                return_url=return_url,
                notify_url=self.notify_url  
            )
                       
            return f"{settings.ALIPAY_GATEWAY}?{order_string}"
        except Exception as e:
            print(f"Alipay payment creation error: {str(e)}")
            return None

    def verify_payment(self, data: dict) -> tuple[bool, Optional[str]]:
        """验证支付宝支付状态"""
        try:
            if not data or 'sign' not in data:
                print(f"Received data: {data}")
                return False, None
                
            signature = data.pop('sign')
            
            # 尝试验证签名
            try:
                verify_result = self.client.verify(data, signature)
            except Exception as verify_error:
                print(f"Signature verification error: {str(verify_error)}")
                return False, None
            
            if verify_result:
                trade_status = data.get('trade_status')
                if trade_status in ('TRADE_SUCCESS', 'TRADE_FINISHED'):
                    trade_no = data.get('trade_no')
                    return True, trade_no
                else:
                    print(f"Payment not successful, trade status: {trade_status}")
            else:
                # 打印签名验证失败的详细信息
                print(f"Data used for verification: {data}")
            return False, None
        except Exception as e:
            print(f"Alipay payment verification error: {str(e)}")
            return False, None

    def refund_payment(self, order_id: str, amount: Decimal, reason: str = "") -> bool:
        """退款"""
        try:
            result = self.client.api_alipay_trade_refund(
                out_trade_no=order_id,
                refund_amount=str(amount),
                refund_reason=reason
            )
            if result.get("code") == "10000":
                return True
            return False
        except Exception as e:
            print(f"Alipay refund error: {str(e)}")
            return False

    def query_payment(self, order_id: str) -> tuple[str, Optional[str]]:
        """查询支付状态"""
        try:
            result = self.client.api_alipay_trade_query(out_trade_no=order_id)
            if result.get("code") == "10000":
                trade_status = result.get("trade_status")
                if trade_status in ("TRADE_SUCCESS", "TRADE_FINISHED"):
                    return "completed", result.get("trade_no")
                elif trade_status == "WAIT_BUYER_PAY":
                    return "pending", None
                else:
                    return "failed", None
            return "failed", None
        except Exception as e:
            print(f"Alipay query error: {str(e)}")
            return "failed", None
