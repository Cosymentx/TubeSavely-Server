from typing import List
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
import json
import math
from decimal import Decimal
from app.schemas.paging import PageResponse
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


@router.get('/methods', response_model=ApiResponse[List[dict]])
def get_payment_methods():
    methods = []
    if settings.STRIPE_SECRET_KEY:
        methods.append({'id': 'stripe', 'name': 'Card (Stripe)', 'currencies': ['USD', 'CNY']})
    if settings.CREEM_API_KEY:
        methods.append({'id': 'creem', 'name': 'Card (Creem)', 'currencies': ['USD']})
    if settings.ALIPAY_APP_ID and settings.ALIPAY_PRIVATE_KEY and settings.ALIPAY_PUBLIC_KEY:
        methods.append({'id': 'alipay', 'name': 'Alipay', 'currencies': ['CNY']})
    return ApiResponse(data=methods)


@router.get('/history', response_model=ApiResponse[PageResponse[Payment]])
def get_payment_history(
    page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(deps.get_db), current_user: User = Depends(deps.get_current_user),
):
    query = db.query(payment_service.Payment).filter(payment_service.Payment.user_id == current_user.id)
    total = query.count()
    records = query.order_by(payment_service.Payment.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return ApiResponse(data=PageResponse(records=records, total=total, size=limit,
                                        current=page, pages=math.ceil(total / limit)))


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
        currency = currency.upper()
        if currency not in {'CNY', 'USD'}:
            return ApiResponse(code=400, msg='Unsupported currency')
        available = {method['id']: method for method in get_payment_methods().data}
        if payment_method not in available or currency not in available[payment_method]['currencies']:
            return ApiResponse(code=400, msg='This payment method does not support the selected currency')
        # get credit amount creem_product_id
        amount, credits, creem_product_id = payment_service.get_credit_amount_by_id(db, credit_amount_id, currency)
        
        # Generate order ID
        order_id = payment_service.generate_order_id()
        
        # Create payment record
        payment_record = payment_service.create_payment(
            db=db,
            user=current_user,
            payment_create=PaymentCreate(
                amount=amount,
                currency=currency,
                credits=credits,
                payment_method=payment_method,
                order_id=order_id
            )   
        )
        
        # Generate payment URL based on payment method
        payment_url = None
        provider_checkout_id = None
        if payment_method == "paypal":
            payment_url = paypal_service.create_payment(
                order_id=order_id,
                amount=amount,
                description=f"TubeSavely {credits} Credits"
            )
        elif payment_method == "stripe":
            checkout = stripe_service.create_checkout_session(
                order_id=order_id,
                amount=amount,
                currency=currency,
                description=f"TubeSavely {credits} Credits",
                customer_email=current_user.email,
            )
            if checkout:
                payment_url, provider_checkout_id = checkout["url"], checkout["id"]
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
            checkout = creem_service.create_payment(
                order_id=order_id,
                product_id=creem_product_id,
                customer_email=current_user.email,
            )
            if checkout:
                payment_url, provider_checkout_id = checkout["url"], checkout["id"]
        else:
            return ApiResponse(
                code=400,
                msg="Unsupported payment method",
                data=None
            )
        
        if not payment_url:
            payment_record.status = payment_service.PaymentStatus.FAILED
            db.commit()
            return ApiResponse(
                code=400,
                msg="Failed to create payment",
                data=None
            )
        
        payment_record.provider_checkout_id = provider_checkout_id
        payment_record.provider_product_id = creem_product_id if payment_method == 'creem' else None
        db.commit()
        return ApiResponse(data={
            "order_id": order_id,
            "amount": amount,
            "currency": currency,
            "credits": credits,
            "payment_url": payment_url
        })
    except Exception as e:
        return ApiResponse(
            code=500,
            msg=f"Failed to create payment: {str(e)}",
            data=None
        )

@router.get("/webhook/{provider}", response_model=ApiResponse[dict], operation_id="payment_webhook_get")
@router.post("/webhook/{provider}", response_model=ApiResponse[dict], operation_id="payment_webhook_post")
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
            signature = request.headers.get('stripe-signature', '')
            if not settings.STRIPE_WEBHOOK_SECRET:
                return PlainTextResponse('Webhook is not configured', status_code=503)
            try:
                event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
            except (ValueError, stripe.error.SignatureVerificationError):
                return PlainTextResponse('Invalid webhook signature', status_code=400)
            obj = event.data.object
            order_id = obj.get('metadata', {}).get('order_id')
            payment = payment_service.get_payment_by_order_id(db, order_id) if order_id else None
            if payment and payment.payment_method == 'stripe':
                if event.type == 'checkout.session.completed':
                    if obj.get('id') == payment.provider_checkout_id:
                        payment_service.refresh_checkout_payment(db, payment)
                elif event.type == 'payment_intent.succeeded':
                    if (obj.get('currency', '').upper() == payment.currency
                            and obj.get('amount_received') == int(payment.amount * 100)):
                        payment_service.update_payment_status(db, payment, obj['id'], payment_service.PaymentStatus.COMPLETED)
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
                if (payment and payment.payment_method == 'alipay'
                        and payment.currency == 'CNY'
                        and Decimal(str(data.get('total_amount', '0'))) == payment.amount):
                    payment_service.update_payment_status(
                        db=db, payment=payment, status=payment_service.PaymentStatus.COMPLETED,
                        trade_no=transaction_id)
                    return PlainTextResponse('success')
            return PlainTextResponse('failure', status_code=400)

        elif provider == "creem":
            payload = await request.body()
            if not settings.CREEM_WEBHOOK_SECRET:
                return PlainTextResponse('Webhook is not configured', status_code=503)
            if not creem_service.verify_signature(payload, request.headers.get('creem-signature', '')):
                return PlainTextResponse('Invalid webhook signature', status_code=400)
            data = json.loads(payload)
            if data.get('eventType') == 'checkout.completed':
                checkout = data.get('object', {})
                order_id = checkout.get('metadata', {}).get('order_id')
                payment = payment_service.get_payment_by_order_id(db, order_id) if order_id else None
                if payment and payment.payment_method == 'creem' and checkout.get('id') == payment.provider_checkout_id:
                    payment_service.refresh_checkout_payment(db, payment)
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
def check_payment_status(
    order_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """Check payment status"""
    try:
        payment = payment_service.get_payment_by_order_id(db, order_id)
        if not payment or payment.user_id != current_user.id:
            return ApiResponse(
                code=404,
                msg="Payment not found",
            )
            
        payment = payment_service.refresh_checkout_payment(db, payment)
        return ApiResponse(data={
            "amount": payment.amount,
            "currency": payment.currency,
            "credits": payment.credits,
            "status": payment.status
        })
    except Exception as e:
        return ApiResponse(
            code=500,
            msg=f"Failed to check payment status: {str(e)}",
        )
