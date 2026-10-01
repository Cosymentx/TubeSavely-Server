from typing import Optional
from decimal import Decimal
from wechatpayv3 import WeChatPay
import qrcode
from io import BytesIO
import base64

from ...core.config import settings

class WeChatPayService:
    def __init__(self):
        """初始化微信支付客户端"""
        try:
            self.client = WeChatPay(
                appid=settings.WECHAT_PAY_APP_ID,
                mchid=settings.WECHAT_PAY_MCH_ID,
                key=settings.WECHAT_PAY_KEY,
                cert_string=settings.WECHAT_PAY_CERT,
                cert_key_string=settings.WECHAT_PAY_KEY_STRING,
                notify_url=f"{settings.API_URL}/api/v1/payment/webhook/wechat"
            )
        except Exception as e:
            print(f"WeChat Pay initialization error: {str(e)}")
            self.client = None

    def create_payment(self, order_id: str, amount: Decimal, description: str) -> Optional[str]:
        """创建微信支付订单"""
        try:
            # 微信支付金额单位为分
            amount_cents = int(amount * 100)
            
            result = self.client.order.create(
                trade_type="NATIVE",  # 生成支付二维码
                out_trade_no=order_id,
                total_fee=amount_cents,
                body=description
            )
            
            if result.get("return_code") == "SUCCESS" and result.get("result_code") == "SUCCESS":
                # 获取支付二维码URL
                code_url = result.get("code_url")
                if code_url:
                    # 生成二维码图片
                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr.add_data(code_url)
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    
                    # 转换为base64
                    buffered = BytesIO()
                    img.save(buffered, format="PNG")
                    qr_base64 = base64.b64encode(buffered.getvalue()).decode()
                    
                    return f"data:image/png;base64,{qr_base64}"
            return None
        except Exception as e:
            print(f"WeChat payment creation error: {str(e)}")
            return None

    def verify_payment(self, data: dict) -> tuple[bool, Optional[str]]:
        """验证微信支付状态"""
        try:
            if self.client.order.check_sign(data):
                if data.get("result_code") == "SUCCESS":
                    return True, data.get("transaction_id")
            return False, None
        except Exception as e:
            print(f"WeChat payment verification error: {str(e)}")
            return False, None

    def refund_payment(self, order_id: str, amount: Decimal, total_amount: Decimal) -> bool:
        """退款"""
        try:
            # 微信支付金额单位为分
            refund_fee = int(amount * 100)
            total_fee = int(total_amount * 100)
            
            result = self.client.refund.apply(
                out_trade_no=order_id,
                out_refund_no=f"refund_{order_id}",
                total_fee=total_fee,
                refund_fee=refund_fee
            )
            
            if result.get("return_code") == "SUCCESS" and result.get("result_code") == "SUCCESS":
                return True
            return False
        except Exception as e:
            print(f"WeChat refund error: {str(e)}")
            return False

    def query_payment(self, order_id: str) -> tuple[str, Optional[str]]:
        """查询支付状态"""
        try:
            result = self.client.order.query(out_trade_no=order_id)
            
            if result.get("return_code") == "SUCCESS" and result.get("result_code") == "SUCCESS":
                trade_state = result.get("trade_state")
                if trade_state == "SUCCESS":
                    return "completed", result.get("transaction_id")
                elif trade_state in ["NOTPAY", "USERPAYING"]:
                    return "pending", None
                else:
                    return "failed", None
            return "failed", None
        except Exception as e:
            print(f"WeChat query error: {str(e)}")
            return "failed", None