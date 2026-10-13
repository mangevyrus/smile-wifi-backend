import hashlib
import hmac
import json
import time
import uuid
from typing import Any

import httpx

from app.config import get_settings


class ClickPesaError(Exception):
    """Raised when ClickPesa returns an error."""


class ClickPesaService:
    _token: str | None = None
    _token_expires_at: float = 0

    def __init__(self):
        self.settings = get_settings()

    def _canonicalize(self, value: Any) -> Any:
        """
        Recursively sort dictionary keys.

        This follows ClickPesa's canonical checksum approach.
        Lists keep their original order.
        """
        if value is None:
            return None

        if isinstance(value, list):
            return [self._canonicalize(item) for item in value]

        if isinstance(value, dict):
            return {
                key: self._canonicalize(value[key])
                for key in sorted(value.keys())
            }

        return value

    def _create_checksum(self, payload: dict) -> str | None:
        checksum_key = self.settings.clickpesa_checksum_key

        if not checksum_key:
            return None

        canonical_payload = self._canonicalize(payload)

        payload_string = json.dumps(
            canonical_payload,
            separators=(",", ":"),
            ensure_ascii=False,
            sort_keys=False,
        )

        digest = hmac.new(
            checksum_key.encode("utf-8"),
            payload_string.encode("utf-8"),
            hashlib.sha256,
        )

        return digest.hexdigest()

    def get_token(self) -> str:
        """
        Generate and cache ClickPesa JWT token.

        ClickPesa says the token is valid for 1 hour.
        """
        now = time.time()

        if self._token and now < self._token_expires_at:
            return self._token

        if not self.settings.clickpesa_client_id:
            raise ClickPesaError(
                "CLICKPESA_CLIENT_ID is not configured."
            )

        if not self.settings.clickpesa_api_key:
            raise ClickPesaError(
                "CLICKPESA_API_KEY is not configured."
            )

        url = (
            f"{self.settings.clickpesa_base_url}"
            "/third-parties/generate-token"
        )

        headers = {
            "client-id": self.settings.clickpesa_client_id,
            "api-key": self.settings.clickpesa_api_key,
        }

        try:
            response = httpx.post(
                url,
                headers=headers,
                timeout=30.0,
            )
        except httpx.RequestError as exc:
            raise ClickPesaError(
                f"Unable to connect to ClickPesa: {exc}"
            ) from exc

        if response.status_code != 200:
            raise ClickPesaError(
                f"ClickPesa token error "
                f"({response.status_code}): {response.text}"
            )

        data = response.json()

        token = data.get("token")

        if not token:
            raise ClickPesaError(
                "ClickPesa did not return an authorization token."
            )

        self._token = token

        # Refresh slightly before the official 1-hour expiry.
        self._token_expires_at = now + 3500

        return token

    def _headers(self) -> dict[str, str]:
        token = self.get_token()

        return {
            "Authorization": token,
            "Content-Type": "application/json",
        }

    def preview_ussd_push(
        self,
        *,
        amount: int,
        currency: str,
        order_reference: str,
        phone_number: str,
    ) -> dict:
        """
        Validate a USSD-PUSH request before initiating it.
        """

        payload = {
            "amount": str(amount),
            "currency": currency,
            "orderReference": order_reference,
            "phoneNumber": phone_number,
            "fetchSenderDetails": True,
        }

        checksum = self._create_checksum(payload)

        if checksum:
            payload["checksum"] = checksum

        url = (
            f"{self.settings.clickpesa_base_url}"
            "/third-parties/payments/"
            "preview-ussd-push-request"
        )

        try:
            response = httpx.post(
                url,
                headers=self._headers(),
                json=payload,
                timeout=30.0,
            )
        except httpx.RequestError as exc:
            raise ClickPesaError(
                f"Unable to connect to ClickPesa: {exc}"
            ) from exc

        if response.status_code not in (200, 201):
            raise ClickPesaError(
                f"ClickPesa preview failed "
                f"({response.status_code}): {response.text}"
            )

        return response.json()

    def initiate_ussd_push(
        self,
        *,
        amount: int,
        currency: str,
        order_reference: str,
        phone_number: str,
    ) -> dict:
        """
        Send the actual USSD-PUSH request.
        """

        if self.settings.mock_payments:
            return {
                "id": f"MOCK-{uuid.uuid4().hex[:12].upper()}",
                "status": "MOCK_SUCCESS",
                "channel": "MOCK",
                "orderReference": order_reference,
                "collectedAmount": str(amount),
                "collectedCurrency": currency,
                "createdAt": None,
                "clientId": self.settings.clickpesa_client_id,
            }

        payload = {
            "amount": str(amount),
            "currency": currency,
            "orderReference": order_reference,
            "phoneNumber": phone_number,
        }

        checksum = self._create_checksum(payload)

        if checksum:
            payload["checksum"] = checksum

        url = (
            f"{self.settings.clickpesa_base_url}"
            "/third-parties/payments/"
            "initiate-ussd-push-request"
        )

        try:
            response = httpx.post(
                url,
                headers=self._headers(),
                json=payload,
                timeout=30.0,
            )
        except httpx.RequestError as exc:
            raise ClickPesaError(
                f"Unable to connect to ClickPesa: {exc}"
            ) from exc

        if response.status_code not in (200, 201):
            raise ClickPesaError(
                f"ClickPesa initiation failed "
                f"({response.status_code}): {response.text}"
            )

        return response.json()

    def query_payment(self, order_reference: str) -> list:
        """
        Query ClickPesa using our order reference.
        """

        if self.settings.mock_payments:
            return [
                {
                    "id": f"MOCK-{order_reference}",
                    "status": "MOCK_SUCCESS",
                    "paymentReference": f"MOCKPAY-{order_reference}",
                    "paymentPhoneNumber": None,
                    "orderReference": order_reference,
                    "collectedAmount": 0,
                    "collectedCurrency": "TZS",
                    "message": "Mock payment",
                }
            ]

        url = (
            f"{self.settings.clickpesa_base_url}"
            f"/third-parties/payments/{order_reference}"
        )

        try:
            response = httpx.get(
                url,
                headers=self._headers(),
                timeout=30.0,
            )
        except httpx.RequestError as exc:
            raise ClickPesaError(
                f"Unable to connect to ClickPesa: {exc}"
            ) from exc

        if response.status_code != 200:
            raise ClickPesaError(
                f"ClickPesa query failed "
                f"({response.status_code}): {response.text}"
            )

        data = response.json()

        if isinstance(data, list):
            return data

        return [data]