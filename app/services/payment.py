from datetime import datetime
from typing import Optional, List
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import uuid

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException

from app.models.payment import Payment
from app.models.payment_event import PaymentEvent
from app.models.user import User
from app.schemas.payment import PaymentCreate
from app.models.credit import Credit


class PaymentStatus:
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    DISPUTED = "disputed"


def generate_order_id() -> str:
    return f"ORDER{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4().hex)[:6]}"


def validate_amount(amount: Decimal) -> Decimal:
    if amount <= 0:
        raise ValueError("Amount must be greater than 0")
    return Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def create_payment(db: Session, user: User, payment_create: PaymentCreate) -> Payment:
    try:
        validated_amount = validate_amount(payment_create.amount)
        db_payment = Payment(
            user_id=user.id,
            order_id=payment_create.order_id,
            amount=validated_amount,
            credits=payment_create.credits,
            payment_method=payment_create.payment_method,
            currency=payment_create.currency.upper(),
            status=PaymentStatus.PENDING,
        )
        db.add(db_payment)
        db.commit()
        db.refresh(db_payment)
        return db_payment
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create payment") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def get_payment_by_order_id(db: Session, order_id: str) -> Optional[Payment]:
    return db.query(Payment).filter(Payment.order_id == order_id).first()


def get_payment_by_trade_no(db: Session, trade_no: str) -> Optional[Payment]:
    if not trade_no:
        return None
    return db.query(Payment).filter(Payment.trade_no == trade_no).first()


def record_provider_event(
    db: Session,
    provider: str,
    provider_event_id: str,
    event_type: str,
    payload,
    payment: Optional[Payment] = None,
) -> bool:
    """Record a provider event without retaining sensitive webhook payloads.

    Returns False if this exact provider event was already processed.
    """
    if not provider_event_id:
        return True
    existing = (
        db.query(PaymentEvent)
        .filter(PaymentEvent.provider_event_id == provider_event_id)
        .first()
    )
    if existing:
        return False

    if isinstance(payload, (bytes, bytearray)):
        raw = bytes(payload)
    else:
        try:
            raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        except Exception:
            raw = str(payload).encode()

    db.add(PaymentEvent(
        payment_id=payment.id if payment else None,
        provider=provider,
        provider_event_id=provider_event_id,
        event_type=event_type,
        payload_sha256=hashlib.sha256(raw).hexdigest(),
    ))
    db.flush()
    return True


def update_payment_status(
    db: Session,
    payment: Payment,
    trade_no: str,
    status: str,
) -> Payment:
    try:
        payment = (
            db.query(Payment)
            .filter(Payment.id == payment.id)
            .populate_existing()
            .with_for_update()
            .one()
        )
        if status == PaymentStatus.COMPLETED and payment.status in (
            PaymentStatus.COMPLETED,
            PaymentStatus.REFUNDED,
            PaymentStatus.DISPUTED,
        ):
            db.commit()
            db.refresh(payment)
            return payment

        payment.trade_no = trade_no
        payment.status = status
        if status == PaymentStatus.COMPLETED:
            payment.paid_at = datetime.utcnow()
            user = db.query(User).filter(User.id == payment.user_id).with_for_update().one()
            user.credits += payment.credits
            db.add(Credit(
                user_id=payment.user_id,
                credits=payment.credits,
                action="Recharge",
                type=1,
                description=f"Recharge {payment.credits} Credits ({payment.order_id})",
            ))
        db.commit()
        db.refresh(payment)
        return payment
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update payment status") from exc


def reverse_payment_credits(
    db: Session,
    payment: Payment,
    *,
    status: str,
    reason: str,
) -> Payment:
    """Reverse purchased credits once. Negative balances represent account debt."""
    try:
        payment = (
            db.query(Payment)
            .filter(Payment.id == payment.id)
            .populate_existing()
            .with_for_update()
            .one()
        )
        if payment.status == PaymentStatus.PENDING:
            return payment

        if not payment.credit_reversal_applied:
            user = db.query(User).filter(User.id == payment.user_id).with_for_update().one()
            user.credits -= payment.credits
            db.add(Credit(
                user_id=payment.user_id,
                credits=-payment.credits,
                action="PaymentReversal",
                type=2,
                description=f"{reason}: reverse {payment.credits} Credits ({payment.order_id})",
            ))
            payment.credit_reversal_applied = True

        payment.reversal_reason = reason[:100]
        payment.status = status
        now = datetime.utcnow()
        if status == PaymentStatus.REFUNDED:
            payment.refunded_at = payment.refunded_at or now
        if status == PaymentStatus.DISPUTED:
            payment.disputed_at = payment.disputed_at or now
        db.commit()
        db.refresh(payment)
        return payment
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to reverse payment credits") from exc


def restore_disputed_credits(db: Session, payment: Payment, reason: str = "Dispute won") -> Payment:
    """Restore credits once when a dispute is won."""
    try:
        payment = (
            db.query(Payment)
            .filter(Payment.id == payment.id)
            .populate_existing()
            .with_for_update()
            .one()
        )
        if payment.status != PaymentStatus.DISPUTED or not payment.credit_reversal_applied:
            return payment

        user = db.query(User).filter(User.id == payment.user_id).with_for_update().one()
        user.credits += payment.credits
        db.add(Credit(
            user_id=payment.user_id,
            credits=payment.credits,
            action="DisputeWon",
            type=1,
            description=f"{reason}: restore {payment.credits} Credits ({payment.order_id})",
        ))
        payment.credit_reversal_applied = False
        payment.reversal_reason = None
        payment.status = PaymentStatus.COMPLETED
        db.commit()
        db.refresh(payment)
        return payment
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to restore disputed credits") from exc


def get_credit_amount_by_id(db: Session, credit_amount_id: int, currency: str) -> tuple[Decimal, int, str]:
    from app.services.credit_amount import CreditAmountService

    credit_amount = CreditAmountService.get_credit_amount_by_id(db, credit_amount_id)
    if not credit_amount:
        raise HTTPException(status_code=400, detail="Invalid credit amount configuration")
    if not credit_amount.is_active:
        raise HTTPException(status_code=400, detail="This credit package is unavailable")

    if currency.upper() == "CNY":
        return Decimal(str(credit_amount.amount_cny)), credit_amount.credits, credit_amount.creem_product_id
    if currency.upper() == "USD":
        return Decimal(str(credit_amount.amount_usd)), credit_amount.credits, credit_amount.creem_product_id
    raise HTTPException(status_code=400, detail=f"Unsupported currency: {currency}")


def get_user_payments(db: Session, user_id: int, offset: int = 0, limit: int = 10) -> List[Payment]:
    return (
        db.query(Payment)
        .filter(Payment.user_id == user_id)
        .order_by(Payment.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def verify_payment_sign(data: dict, sign: str) -> bool:
    return False


def refresh_checkout_payment(db: Session, payment: Payment) -> Payment:
    """Confirm payment using the provider API before granting credits."""
    if payment.status != PaymentStatus.PENDING or not payment.provider_checkout_id:
        return payment

    if payment.payment_method == "stripe":
        from app.services.payments.stripe import StripeService
        checkout = StripeService().retrieve_checkout(payment.provider_checkout_id)
        if not checkout or checkout.get("id") != payment.provider_checkout_id:
            return payment
        if checkout.get("payment_status") != "paid":
            return payment
        if checkout.get("metadata", {}).get("order_id") != payment.order_id:
            return payment
        if checkout.get("currency", "").upper() != payment.currency:
            return payment
        if checkout.get("amount_total") != int(payment.amount * 100):
            return payment
        intent = checkout.get("payment_intent")
        trade_no = intent.get("id") if isinstance(intent, dict) else intent
        trade_no = trade_no or checkout["id"]

    elif payment.payment_method == "creem":
        from app.services.payments.creem import CreemService
        checkout = CreemService().retrieve_checkout(payment.provider_checkout_id)
        if not checkout or checkout.get("id") != payment.provider_checkout_id:
            return payment
        if checkout.get("status") != "completed" or checkout.get("order", {}).get("status") != "paid":
            return payment
        if checkout.get("metadata", {}).get("order_id") != payment.order_id:
            return payment
        product = checkout.get("product")
        if not isinstance(product, dict) or product.get("id") != payment.provider_product_id:
            return payment
        if product.get("currency", "").upper() != payment.currency or product.get("price") != int(payment.amount * 100):
            return payment
        trade_no = checkout.get("order", {}).get("id")
        if not trade_no:
            return payment
    else:
        return payment

    return update_payment_status(db, payment, trade_no, PaymentStatus.COMPLETED)
