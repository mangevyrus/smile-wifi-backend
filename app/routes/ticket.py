from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.order import Order
from app.models.voucher import Voucher
from app.services.packages import get_package


router = APIRouter(prefix="/ticket", tags=["Ticket"])


# Customer-facing prices.
# Hizi ni tofauti na package.amount inayotumwa ClickPesa.
CUSTOMER_PRICES = {
    "1H": 500,
    "24H": 2000,
    "3D": 5000,
    "7D": 12000,
    "30D": 30000,
}


@router.get("/{order_reference}")
def get_ticket(
    order_reference: str,
    db: Session = Depends(get_db),
):
    """
    Return the voucher ticket for a successfully paid order.

    The voucher password is returned only after the order is PAID
    and the voucher has been created.
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

    # Payment has not yet been confirmed.
    if order.status != "PAID":
        return {
            "success": False,
            "orderReference": order.order_reference,
            "status": order.status,
            "voucherStatus": "PENDING",
            "message": "Malipo bado hayajathibitishwa.",
        }

    voucher = (
        db.query(Voucher)
        .filter(Voucher.order_id == order.id)
        .first()
    )

    # Payment is PAID but voucher creation is still pending.
    if not voucher:
        return {
            "success": False,
            "orderReference": order.order_reference,
            "status": order.status,
            "voucherStatus": "PENDING",
            "message": "Voucher bado inatengenezwa.",
        }

    try:
        package = get_package(order.package_code)
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    customer_amount = CUSTOMER_PRICES.get(
        package.code,
        package.amount,
    )

    return {
        "success": True,
        "orderReference": order.order_reference,
        "status": order.status,
        "voucherStatus": voucher.status,
        "ticket": {
            "package": package.name,
            "packageCode": package.code,
            "amount": customer_amount,
            "duration": package.duration,
            "username": voucher.username,
            "password": voucher.password,

            # Important:
            # limit-uptime means usage time, not a fixed calendar date.
            "expires": f"Baada ya kutumia {package.duration}",
        },
    }