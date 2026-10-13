import re
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.order import Order
from app.models.payment import Payment
from app.services.clickpesa import ClickPesaError, ClickPesaService
from app.services.packages import get_package


router = APIRouter(
    prefix="/checkout",
    tags=["Checkout"],
)

templates = Jinja2Templates(
    directory="app/templates"
)


NETWORKS = {
    "MPESA": "M-Pesa",
    "AIRTEL": "Airtel Money",
    "MIXX": "Mixx by Yas",
    "HALOPESA": "HaloPesa",
}


CLICKPESA_PROVIDERS = {
    "MPESA": [
        "M-PESA",
        "MPESA",
    ],
    "AIRTEL": [
        "AIRTEL-MONEY",
        "AIRTEL MONEY",
        "AIRTEL",
    ],
    "MIXX": [
        "TIGO-PESA",
        "TIGO PESA",
        "MIXX BY YAS",
        "MIXX",
    ],
    "HALOPESA": [
        "HALOPESA",
        "HALO PESA",
    ],
}


# Customer-facing prices.
#
# These are intentionally different from package.amount
# because package.amount is the amount sent to ClickPesa.
CUSTOMER_PRICES = {
    "1H": 500,
    "24H": 2000,
    "3D": 5000,
    "7D": 12000,
    "30D": 30000,
}


def normalize_tanzania_phone(phone: str) -> str:
    phone = (
        phone
        .strip()
        .replace(" ", "")
        .replace("-", "")
    )

    if phone.startswith("+255"):
        phone = phone[1:]

    elif phone.startswith("255"):
        pass

    elif phone.startswith("0"):
        phone = "255" + phone[1:]

    else:
        raise ValueError(
            "Invalid Tanzanian phone number"
        )

    if not re.fullmatch(
        r"255\d{9}",
        phone,
    ):
        raise ValueError(
            "Invalid Tanzanian phone number"
        )

    return phone


def normalize_provider_name(
    provider: str | None,
) -> str:

    if not provider:
        return ""

    return re.sub(
        r"[^A-Z0-9]",
        "",
        provider.upper(),
    )


def normalize_login_url(
    login_url: str | None,
) -> str:

    login_url = (
        login_url or ""
    ).strip()

    if not login_url:
        return "http://10.10.10.1/login"

    if not re.match(
        r"^https?://",
        login_url,
        re.IGNORECASE,
    ):
        return "http://10.10.10.1/login"

    return login_url


def validate_selected_network(
    *,
    selected_network: str,
    preview_response: dict,
) -> str:

    if selected_network not in CLICKPESA_PROVIDERS:
        raise ValueError(
            "Unsupported payment network"
        )

    accepted_providers = {
        normalize_provider_name(name)
        for name in CLICKPESA_PROVIDERS[
            selected_network
        ]
    }

    active_methods = preview_response.get(
        "activeMethods",
        [],
    )

    available_providers = {
        normalize_provider_name(
            method.get("name")
        )
        for method in active_methods
        if method.get("status") == "AVAILABLE"
    }

    if not accepted_providers.intersection(
        available_providers
    ):
        raise ValueError(
            f"{NETWORKS[selected_network]} "
            "haijawezeshwa/haipatikani kwa sasa."
        )

    sender = preview_response.get(
        "sender",
        {},
    )

    actual_provider_raw = sender.get(
        "accountProvider"
    )

    actual_provider = normalize_provider_name(
        actual_provider_raw
    )

    if not actual_provider:
        raise ValueError(
            "ClickPesa haikuweza kutambua "
            "mtandao wa namba hii."
        )

    if actual_provider not in accepted_providers:

        display_names = {
            "MPESA": "M-Pesa",
            "AIRTELMONEY": "Airtel Money",
            "TIGOPESA": "Mixx by Yas",
            "MIXXBYYAS": "Mixx by Yas",
            "MIXX": "Mixx by Yas",
            "HALOPESA": "HaloPesa",
        }

        actual_display = display_names.get(
            actual_provider,
            actual_provider_raw or "unknown",
        )

        raise ValueError(
            f"Namba hii ni ya "
            f"{actual_display}, si "
            f"{NETWORKS[selected_network]}."
        )

    return actual_provider_raw


@router.get(
    "/{package_code}",
    response_class=HTMLResponse,
)
def checkout_page(
    request: Request,
    package_code: str,
    login_url: str = "",
):

    try:
        package = get_package(
            package_code
        )

    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Package not found",
        )

    login_url = normalize_login_url(
        login_url
    )

    customer_price = CUSTOMER_PRICES.get(
        package.code,
        package.amount,
    )

    return templates.TemplateResponse(
        request=request,
        name="checkout.html",
        context={
            "package": package,
            "customer_price": customer_price,
            "networks": NETWORKS,
            "login_url": login_url,
            "error": None,
        },
    )


@router.post(
    "/{package_code}/start",
    response_class=HTMLResponse,
)
def start_checkout(
    request: Request,
    package_code: str,
    network: str = Form(...),
    phone: str = Form(...),
    login_url: str = Form(""),
    db: Session = Depends(get_db),
):

    login_url = normalize_login_url(
        login_url
    )

    try:
        package = get_package(
            package_code
        )

    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Package not found",
        )

    customer_price = CUSTOMER_PRICES.get(
        package.code,
        package.amount,
    )

    network = network.upper()

    if network not in NETWORKS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported mobile money network",
        )

    try:
        normalized_phone = normalize_tanzania_phone(
            phone
        )

    except ValueError:

        return templates.TemplateResponse(
            request=request,
            name="checkout.html",
            context={
                "package": package,
                "customer_price": customer_price,
                "networks": NETWORKS,
                "login_url": login_url,
                "error": (
                    "Tafadhali weka namba sahihi "
                    "ya Tanzania."
                ),
            },
            status_code=400,
        )

    # ---------------------------------------------------------
    # Create order
    # ---------------------------------------------------------

    order_reference = (
        f"SMILE"
        f"{uuid.uuid4().hex[:12].upper()}"
    )

    order = Order(
        order_reference=order_reference,
        package_code=package.code,
        amount=package.amount,
        currency="TZS",
        phone=normalized_phone,
        selected_network=network,
        status="PENDING",
    )

    db.add(order)
    db.commit()
    db.refresh(order)

    clickpesa = ClickPesaService()

    # ---------------------------------------------------------
    # Preview
    # ---------------------------------------------------------

    try:
        preview = clickpesa.preview_ussd_push(
            amount=package.amount,
            currency="TZS",
            order_reference=order.order_reference,
            phone_number=normalized_phone,
        )

    except ClickPesaError as exc:

        order.status = (
            "PAYMENT_PREVIEW_FAILED"
        )

        db.commit()

        return templates.TemplateResponse(
            request=request,
            name="checkout.html",
            context={
                "package": package,
                "customer_price": customer_price,
                "networks": NETWORKS,
                "login_url": login_url,
                "error": str(exc),
            },
            status_code=502,
        )

    # ---------------------------------------------------------
    # Validate selected network
    # ---------------------------------------------------------

    try:

        clickpesa_provider = (
            validate_selected_network(
                selected_network=network,
                preview_response=preview,
            )
        )

    except ValueError as exc:

        order.status = (
            "NETWORK_VALIDATION_FAILED"
        )

        db.commit()

        return templates.TemplateResponse(
            request=request,
            name="checkout.html",
            context={
                "package": package,
                "customer_price": customer_price,
                "networks": NETWORKS,
                "login_url": login_url,
                "error": str(exc),
            },
            status_code=400,
        )

    # ---------------------------------------------------------
    # Initiate USSD push
    # ---------------------------------------------------------

    try:

        response = clickpesa.initiate_ussd_push(
            amount=package.amount,
            currency="TZS",
            order_reference=order.order_reference,
            phone_number=normalized_phone,
        )

    except ClickPesaError as exc:

        order.status = (
            "PAYMENT_INITIATION_FAILED"
        )

        db.commit()

        return templates.TemplateResponse(
            request=request,
            name="checkout.html",
            context={
                "package": package,
                "customer_price": customer_price,
                "networks": NETWORKS,
                "login_url": login_url,
                "error": str(exc),
            },
            status_code=502,
        )

    # ---------------------------------------------------------
    # Save payment
    # ---------------------------------------------------------

    clickpesa_status = response.get(
        "status",
        "PROCESSING",
    )

    if clickpesa_status == "MOCK_SUCCESS":
        order.status = "MOCK_SUCCESS"

    else:
        order.status = "PAYMENT_PROCESSING"

    payment = Payment(
        order_id=order.id,
        provider="CLICKPESA",
        payment_reference=response.get(
            "paymentReference"
        ),
        amount=package.amount,
        currency="TZS",
        status=clickpesa_status,
        raw_response={
            "preview": preview,
            "initiation": response,
        },
    )

    db.add(payment)

    db.commit()

    db.refresh(payment)

    # ---------------------------------------------------------
    # Payment pending page
    # ---------------------------------------------------------

    return templates.TemplateResponse(
        request=request,
        name="payment_pending.html",
        context={
            "package": package,
            "customer_price": customer_price,
            "network": NETWORKS[network],
            "phone": normalized_phone,
            "order": order,
            "payment": payment,
            "mock_mode": clickpesa.settings.mock_payments,
            "clickpesa_provider": clickpesa_provider,
            "login_url": login_url,
        },
    )