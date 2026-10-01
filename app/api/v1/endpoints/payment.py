from typing import List
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
import stripe

from app.schemas.payment import PaymentResponse, Payment
from app.schemas.response import ApiResponse
from app.core import deps
from app.services.payments.paypal import PayPalService
from app.services.payments.stripe import StripeService
from app.services.payments.alipay import AlipayService
from app.services.payments.wechat import WeChatPayService
from app.services.payments.airwallex import AirwallexService
from app.services.payments.creem import CreemService
from app.services import payment as payment_service
from app.core.config import settings
from app.models.user import User
from app.schemas.payment import PaymentCreate

router = APIRouter()
paypal_service = PayPalService()
stripe_service = StripeService()
creem_service = CreemService()
alipay_service = AlipayService()
# wechat_service = WeChatPayService()
airwallex_service = AirwallexService()


@router.post("/create", response_model=ApiResponse[PaymentResponse])
def create_payment(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    credit_amount_id: int,
    currency: str,
    payment_method: str
):
    """Create payment order"""
    try:
        # get credit amount creem_product_id
        amount, credits, creem_product_id = payment_service.get_credit_amount_by_id(db, credit_amount_id, currency)
        
        # Generate order ID
        order_id = payment_service.generate_order_id()
        
        # Create payment record
        payment_service.create_payment(
            db=db,
            user=current_user,
            payment_create=PaymentCreate(
                amount=amount,
                credits=credits,
                payment_method=payment_method,
                order_id=order_id
            )   
        )
        
        # Generate payment URL based on payment method
        payment_url = None
        if payment_method == "paypal":
            payment_url = paypal_service.create_payment(
                order_id=order_id,
                amount=amount,
                description=f"TubeSavely {credits} Credits"
            )
        elif payment_method == "stripe":
            payment_url = stripe_service.create_checkout_session(
                order_id=order_id,
                amount=amount,
                currency=currency,
                description=f"TubeSavely {credits} Credits"
            )
        elif payment_method == "alipay":
            payment_url = alipay_service.create_payment(
                order_id=order_id,
                amount=amount,
                currency=currency,
                description=f"TubeSavely {credits} Credits"
            )
        elif payment_method == "wechat":
            payment_url = wechat_service.create_payment(
                order_id=order_id,
                amount=amount,
                description=f"TubeSavely {credits} Credits"
            )
        elif payment_method == "airwallex":
            payment_url = airwallex_service.create_payment(
                order_id=order_id,
                amount=amount,
                currency=currency,
                description=f"TubeSavely {credits} Credits"
            )
        elif payment_method == "creem":
            payment_url = creem_service.create_payment(
                order_id=order_id,
                product_id=creem_product_id,
            )
        else:
            return ApiResponse(
                code=400,
                msg="Unsupported payment method",
                data=None
            )
        
        if not payment_url:
            return ApiResponse(
                code=400,
                msg="Failed to create payment",
                data=None
            )
        
        return ApiResponse(data={
            "order_id": order_id,
            "amount": amount,
            "credits": credits,
            "payment_url": payment_url
        })
    except Exception as e:
        return ApiResponse(
            code=500,
            msg=f"Failed to create payment: {str(e)}",
            data=None
        )

@router.api_route("/webhook/{provider}", methods=["GET", "POST"], response_model=ApiResponse[dict])
async def payment_webhook(
    provider: str,
    request: Request,
    db: Session = Depends(deps.get_db)
):
    """Process payment webhook
    
    Args:
        provider: Payment provider (paypal/stripe/alipay/wechat)
        request: Request object
        db: Database session
    """
    try:
        if provider == "paypal":
            # Get PayPal payment_id
            data = await request.json()
            payment_id = data.get("resource", {}).get("id")
            if not payment_id:
                return ApiResponse(
                    code=400,
                    msg="Invalid PayPal webhook data",
                    data=None
                )
            
            # Verify payment using PayPal service
            success, transaction_id = paypal_service.verify_payment(payment_id)
            if success and transaction_id:
                # Update payment status
                payment = payment_service.get_payment_by_order_id(db, payment_id)
                if payment:
                    payment_service.update_payment_status(
                        db=db,
                        payment=payment,
                        status=payment_service.PaymentStatus.COMPLETED,
                        trade_no=transaction_id
                    )
                    return ApiResponse()
                    
        elif provider == "stripe":
            payload = await request.body()
            signature = request.headers.get("stripe-signature")
            if not signature:
                return ApiResponse(
                    code=400,
                    msg="Missing Stripe signature"
                )
                
            if not settings.STRIPE_WEBHOOK_SECRET:
                return ApiResponse(
                    code=500,
                    msg="Stripe webhook secret not configured"
                )
                
            try:
                # 将payload转换为字符串
                payload_str = payload.decode('utf-8')
                event = stripe.Webhook.construct_event(
                    payload_str,
                    signature,
                    settings.STRIPE_WEBHOOK_SECRET
                )
                if event.type == "payment_intent.succeeded":
                    payment_intent = event.data.object
                    order_id = payment_intent.metadata.order_id
                    if order_id:
                        payment = payment_service.get_payment_by_order_id(db, order_id)
                        if payment:
                            payment_service.update_payment_status(
                                db=db,
                                payment=payment,
                                status=payment_service.PaymentStatus.COMPLETED,
                                trade_no=payment_intent.id
                            )
            except stripe.SignatureVerificationError as e:
                print(f"Stripe webhook signature verification error: {str(e)}")
                return ApiResponse(
                    code=400,
                    msg=f"Invalid Stripe webhook signature: {str(e)}"
                )
            except Exception as e:
                print(f"Stripe webhook processing error: {str(e)}")
                return ApiResponse(
                    code=400,
                    msg=f"Failed to process Stripe webhook: {str(e)}"
                )
            return ApiResponse()
                
        elif provider == "alipay":
            # 获取表单数据和请求头
            form_data = await request.form()
            data = dict(form_data)
            
            # 如果表单数据为空，尝试获取查询参数
            if not data:
                data = dict(request.query_params)
            
            success, transaction_id = alipay_service.verify_payment(data)
            
            if success and transaction_id:
                payment = payment_service.get_payment_by_order_id(
                    db, 
                    data.get("out_trade_no")
                )
                if payment:
                    payment_service.update_payment_status(
                        db=db,
                        payment=payment,
                        status=payment_service.PaymentStatus.COMPLETED,
                        trade_no=transaction_id
                    )
                    return ApiResponse()
        
        elif provider == "creem":
            data = await request.json()
            print(f"creem request json {data}")
            success, transaction_id, order_id = creem_service.verify_payment(data)
            if success and transaction_id:
                payment = payment_service.get_payment_by_order_id(
                    db, 
                    order_id
                )
                if payment:
                    payment_service.update_payment_status(
                        db=db,
                        payment=payment,
                        status=payment_service.PaymentStatus.COMPLETED,
                        trade_no=transaction_id
                    )
                    return ApiResponse()
        # elif provider == "wechat":
            # data = await request.json()
            # success, transaction_id = wechat_service.verify_payment(data)
            
            # if success and transaction_id:
            #     payment = payment_service.get_payment_by_order_id(
            #         db, 
            #         data.get("out_trade_no")
            #     )
            #     if payment:
            #         payment_service.update_payment_status(
            #             db=db,
            #             payment=payment,
            #             status=payment_service.PaymentStatus.COMPLETED,
            #             trade_no=transaction_id
            #         )
            #         return ApiResponse()
        
        elif provider == "airwallex":
            data = await request.json()
            signature = request.headers.get("x-signature")
            if not signature:
                return ApiResponse(
                    code=400,
                    msg="Missing Airwallex signature"
                )
            
            if airwallex_service.verify_webhook_signature(signature, data):
                event_type = data.get("type")
                event_data = data.get("data")
                payment = airwallex_service.handle_webhook(db, event_type, event_data)
                if payment:
                    return ApiResponse()
                    
            return ApiResponse(
                code=400,
                msg="Invalid Airwallex webhook data"
            )
       
        else:
            return ApiResponse(
                code=400,
                msg=f"Unsupported payment provider: {provider}",
            )

        return ApiResponse(
            code=400,
            msg="Payment verification failed",
        )
        
    except Exception as e:
        return ApiResponse(
            code=500,
            msg=f"Failed to process {provider} webhook: {str(e)}",
        )

@router.get("/orders", response_model=ApiResponse[List[Payment]])
def get_payment_orders(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    offset: int = 0,
    limit: int = 10
):
    """Get user's payment order list"""
    try:
        orders = payment_service.get_user_payments(
            db=db,
            user_id=current_user.id,
            offset=offset,
            limit=limit
        )
        return ApiResponse(data=orders)
    except Exception as e:
        return ApiResponse(
            code=500,
            msg=f"Failed to fetch payment orders: {str(e)}",
        )

@router.get("/status/{order_id}", response_model=ApiResponse[dict])
async def check_payment_status(
    order_id: str,
    db: Session = Depends(deps.get_db)
):
    """Check payment status"""
    try:
        payment = payment_service.get_payment_by_order_id(db, order_id)
        if not payment:
            return ApiResponse(
                code=404,
                msg="Payment not found",
            )
            
        return ApiResponse(data={
            "amount": payment.amount,
            "credits": payment.credits,
            "status": payment.status
        })
    except Exception as e:
        return ApiResponse(
            code=500,
            msg=f"Failed to check payment status: {str(e)}",
        )