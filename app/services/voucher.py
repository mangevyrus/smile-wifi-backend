from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.voucher import Voucher
from app.services.mikrotik import MikroTikError, MikroTikService
from app.services.packages import get_package


class VoucherError(Exception):
    """Raised when voucher creation fails."""


class VoucherService:
    """
    Service responsible for creating and retrieving hotspot vouchers.

    Voucher creation is only allowed for PAID orders.

    Idempotency:
        If the order already has a voucher, the existing voucher
        is returned instead of creating another MikroTik user.
    """

    def __init__(self, db: Session):
        self.db = db
        self.mikrotik = MikroTikService()

    def create_for_order(self, order: Order) -> Voucher:
        """
        Create a MikroTik HotSpot voucher for a paid order.

        If a voucher already exists for the order, return it.

        Raises:
            VoucherError: if the order is not eligible or MikroTik
                          voucher creation fails.
        """

        # ---------------------------------------------------------
        # 1. IDEMPOTENCY CHECK
        # ---------------------------------------------------------
        # If this order already has a voucher, never create another.
        existing_voucher = (
            self.db.query(Voucher)
            .filter(Voucher.order_id == order.id)
            .first()
        )

        if existing_voucher:
            return existing_voucher

        # ---------------------------------------------------------
        # 2. PAYMENT VALIDATION
        # ---------------------------------------------------------
        if order.status != "PAID":
            raise VoucherError(
                f"Order '{order.order_reference}' is not paid. "
                f"Current status: {order.status}"
            )

        # ---------------------------------------------------------
        # 3. GET PACKAGE CONFIGURATION
        # ---------------------------------------------------------
        try:
            package = get_package(order.package_code)
        except ValueError as exc:
            raise VoucherError(str(exc)) from exc

        # ---------------------------------------------------------
        # 4. GENERATE UNIQUE CREDENTIALS
        # ---------------------------------------------------------
        username = self.mikrotik.generate_username()
        password = self.mikrotik.generate_password()

        # ---------------------------------------------------------
        # 5. CREATE USER ON MIKROTIK
        # ---------------------------------------------------------
        try:
            self.mikrotik.create_hotspot_user(
                username=username,
                password=password,
                profile=package.mikrotik_profile,
                limit_uptime=package.limit_uptime,
                comment=f"Order: {order.order_reference}",
            )

        except MikroTikError as exc:
            raise VoucherError(
                f"Failed to create MikroTik voucher: {exc}"
            ) from exc

        # ---------------------------------------------------------
        # 6. SAVE VOUCHER IN DATABASE
        # ---------------------------------------------------------
        voucher = Voucher(
            order_id=order.id,
            username=username,
            password=password,
            mikrotik_profile=package.mikrotik_profile,
            limit_uptime=package.limit_uptime,
            status="ACTIVE",
        )

        self.db.add(voucher)

        try:
            self.db.commit()
            self.db.refresh(voucher)

        except IntegrityError:
            self.db.rollback()

            # Another request may have created the voucher
            # concurrently for the same order.
            existing_voucher = (
                self.db.query(Voucher)
                .filter(Voucher.order_id == order.id)
                .first()
            )

            if existing_voucher:
                return existing_voucher

            raise VoucherError(
                "Voucher could not be saved because of a database "
                "integrity error."
            )

        return voucher

    def get_for_order(self, order: Order) -> Voucher | None:
        """
        Retrieve the voucher belonging to an order.

        Returns None when the order has no voucher.
        """

        return (
            self.db.query(Voucher)
            .filter(Voucher.order_id == order.id)
            .first()
        )
