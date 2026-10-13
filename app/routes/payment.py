from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.order import Order
from app.models.payment import Payment
from app.models.voucher import Voucher
from app.services.clickpesa import ClickPesaError, ClickPesaService
from app.services.voucher import VoucherError, VoucherService


router = APIRouter(
    prefix="/payment",
    tags=["Payment"],
)


def create_or_get_voucher(
    db: Session,
    order: Order,
):
    """
    Create the MikroTik voucher if payment has been confirmed.

    VoucherService itself is idempotent, so if the webhook already
    created the voucher, this simply returns the existing voucher.
    """

    try:
        voucher_service = VoucherService(db)

        voucher = voucher_service.create_for_order(order)

        return voucher, None

    except VoucherError as exc:
        return None, str(exc)


def payment_response(
    *,
    order: Order,
    payment: Payment,
    voucher,
    voucher_error: str | None = None,
):
    response = {
        "order_reference": order.order_reference,
        "status": "SUCCESS",
        "amount": order.amount,
        "currency": order.currency,
        "payment_reference": payment.payment_reference,
        "voucherStatus": "ACTIVE" if voucher else "PENDING",
    }

    if voucher:
        response["message"] = "Malipo yamefanikiwa na voucher imetengenezwa."
    else:
        response["message"] = (
            "Malipo yamefanikiwa lakini voucher bado inatengenezwa."
        )

        if voucher_error:
            response["voucherError"] = voucher_error

    return response


@router.get("/status/{order_reference}")
def payment_status(
    order_reference: str,
    db: Session = Depends(get_db),
):
    """
    Check the current payment status.

    If payment is already PAID, this endpoint also ensures that
    the MikroTik voucher exists.
    """

    order = (
        db.query(Order)
        .filter(Order.order_reference == order_reference)
        .first()
    )

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    payment = (
        db.query(Payment)
        .filter(Payment.order_id == order.id)
        .order_by(Payment.id.desc())
        .first()
    )

    if not payment:
        return {
            "order_reference": order.order_reference,
            "status": "PENDING",
            "voucherStatus": "PENDING",
            "message": "Payment record bado haijapatikana.",
        }

    clickpesa = ClickPesaService()

    # ---------------------------------------------------------
    # Already paid
    # ---------------------------------------------------------
    #
    # This is important because a webhook may have already
    # processed the payment. We do not need to query ClickPesa
    # again.
    #
    if (
        order.status == "PAID"
        and payment.status in {"SUCCESS", "SETTLED"}
    ):
        voucher, voucher_error = create_or_get_voucher(
            db,
            order,
        )

        return payment_response(
            order=order,
            payment=payment,
            voucher=voucher,
            voucher_error=voucher_error,
        )

    # ---------------------------------------------------------
    # Mock payment mode
    # ---------------------------------------------------------

    if clickpesa.settings.mock_payments:
        payment.status = "SUCCESS"

        order.status = "PAID"

        if order.paid_at is None:
            order.paid_at = datetime.now(timezone.utc)

        db.commit()

        voucher, voucher_error = create_or_get_voucher(
            db,
            order,
        )

        return payment_response(
            order=order,
            payment=payment,
            voucher=voucher,
            voucher_error=voucher_error,
        )

    # ---------------------------------------------------------
    # Real ClickPesa payment
    # ---------------------------------------------------------

    try:
        results = clickpesa.query_payment(
            order.order_reference
        )

    except ClickPesaError as exc:
        return {
            "order_reference": order.order_reference,
            "status": payment.status or "PROCESSING",
            "voucherStatus": "PENDING",
            "message": str(exc),
        }

    if not results:
        return {
            "order_reference": order.order_reference,
            "status": "PROCESSING",
            "voucherStatus": "PENDING",
            "message": "Payment bado inasubiri uthibitisho.",
        }

    result = results[0]

    status = str(
        result.get("status", "PROCESSING")
    ).upper()

    payment_reference = (
        result.get("paymentReference")
        or payment.payment_reference
    )

    payment.status = status

    payment.payment_reference = payment_reference

    payment.raw_response = result

    # ---------------------------------------------------------
    # SUCCESS / SETTLED
    # ---------------------------------------------------------

    if status in {"SUCCESS", "SETTLED"}:

        # Normalize both ClickPesa statuses to SUCCESS
        # inside our own application.
        payment.status = "SUCCESS"

        order.status = "PAID"

        if order.paid_at is None:
            order.paid_at = datetime.now(timezone.utc)

        db.commit()

        voucher, voucher_error = create_or_get_voucher(
            db,
            order,
        )

        return payment_response(
            order=order,
            payment=payment,
            voucher=voucher,
            voucher_error=voucher_error,
        )

    # ---------------------------------------------------------
    # FAILED
    # ---------------------------------------------------------

    if status == "FAILED":

        order.status = "PAYMENT_FAILED"

        db.commit()

        return {
            "order_reference": order.order_reference,
            "status": "FAILED",
            "voucherStatus": "NONE",
            "amount": order.amount,
            "currency": order.currency,
            "payment_reference": payment.payment_reference,
            "message": result.get(
                "message",
                "Malipo yameshindwa.",
            ),
        }

    # ---------------------------------------------------------
    # PROCESSING / PENDING / OTHER
    # ---------------------------------------------------------

    order.status = "PAYMENT_PROCESSING"

    db.commit()

    return {
        "order_reference": order.order_reference,
        "status": "PROCESSING",
        "voucherStatus": "PENDING",
        "amount": order.amount,
        "currency": order.currency,
        "payment_reference": payment.payment_reference,
        "message": result.get(
            "message",
            "Payment bado inachakatwa.",
        ),
    }