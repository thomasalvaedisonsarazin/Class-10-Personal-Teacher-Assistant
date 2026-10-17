"""Server-side checks of Google Play purchases (Google Play Developer API).

The app never decides access by itself: it sends the purchase token here, we ask Google
what was really bought, then acknowledge (subscriptions) or consume (one-time products,
so they can be bought again for another topic or child).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from app.config import settings
from app.exceptions import AppError

logger = logging.getLogger(__name__)

API = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"
SCOPE = "https://www.googleapis.com/auth/androidpublisher"

# Subscription states that still give access (cancelled = runs until the paid period ends).
ACTIVE_SUBSCRIPTION_STATES = {
    "SUBSCRIPTION_STATE_ACTIVE",
    "SUBSCRIPTION_STATE_IN_GRACE_PERIOD",
    "SUBSCRIPTION_STATE_CANCELED",
}


class BillingNotConfiguredError(AppError):
    """503: the server has no Google Play service account."""

    status_code = 503
    code = "billing_not_configured"
    message = "Payments are not set up on the server yet"


class PlayApiError(AppError):
    """502: Google Play could not be reached or refused the request."""

    status_code = 502
    code = "play_unavailable"
    message = "Could not check the payment with Google Play. Please try again."


@dataclass(frozen=True)
class PlaySubscription:
    """What Google says about a subscription purchase token."""

    product_id: str
    state: str
    expires_at: datetime | None
    auto_renewing: bool
    acknowledged: bool
    account_id: str | None
    profile_id: str | None
    order_id: str | None

    @property
    def active(self) -> bool:
        """True while the subscription gives access."""
        return self.state in ACTIVE_SUBSCRIPTION_STATES and (
            self.expires_at is None or self.expires_at > datetime.now(UTC)
        )


@dataclass(frozen=True)
class PlayProduct:
    """What Google says about a one-time product purchase token."""

    purchased: bool
    consumed: bool
    account_id: str | None
    profile_id: str | None
    order_id: str | None


class PlayVerifier(Protocol):
    """Google Play Developer API calls (a fake replaces it in tests)."""

    def get_subscription(self, token: str) -> PlaySubscription: ...

    def acknowledge_subscription(self, product_id: str, token: str) -> None: ...

    def get_product(self, product_id: str, token: str) -> PlayProduct: ...

    def consume_product(self, product_id: str, token: str) -> None: ...


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class GooglePlayVerifier:
    """Real Google Play Developer API client using a service account."""

    def __init__(self, service_account_json: str, package_name: str) -> None:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account

        raw = service_account_json.strip()
        info = json.loads(raw if raw.startswith("{") else Path(raw).read_text(encoding="utf-8"))
        credentials = service_account.Credentials.from_service_account_info(info, scopes=[SCOPE])
        self._session = AuthorizedSession(credentials)
        self._base = f"{API}/{package_name}/purchases"

    def _call(self, method: str, path: str) -> dict[str, Any]:
        try:
            response = self._session.request(method, f"{self._base}/{path}", timeout=20)
        except Exception as exc:  # network / auth errors from google-auth or requests
            logger.error("Play API %s failed: %s", path.split("/")[0], type(exc).__name__)
            raise PlayApiError() from exc
        if response.status_code in (400, 404, 410):
            return {"_invalid": True}
        if response.status_code >= 300:
            logger.error("Play API %s returned %s", path.split("/")[0], response.status_code)
            raise PlayApiError()
        if not response.content:
            return {}
        data: dict[str, Any] = response.json()
        return data

    def get_subscription(self, token: str) -> PlaySubscription:
        """Look up a subscription token (subscriptionsv2)."""
        data = self._call("GET", f"subscriptionsv2/tokens/{token}")
        items = data.get("lineItems") or [{}]
        item = items[0]
        ids = data.get("externalAccountIdentifiers") or {}
        return PlaySubscription(
            product_id=str(item.get("productId", "")),
            state="INVALID" if data.get("_invalid") else str(data.get("subscriptionState", "")),
            expires_at=_parse_time(item.get("expiryTime")),
            auto_renewing=bool((item.get("autoRenewingPlan") or {}).get("autoRenewEnabled")),
            acknowledged=data.get("acknowledgementState") == "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED",
            account_id=ids.get("obfuscatedExternalAccountId"),
            profile_id=ids.get("obfuscatedExternalProfileId"),
            order_id=data.get("latestOrderId"),
        )

    def acknowledge_subscription(self, product_id: str, token: str) -> None:
        """Acknowledge within 3 days, otherwise Google refunds the purchase."""
        self._call("POST", f"subscriptions/{product_id}/tokens/{token}:acknowledge")

    def get_product(self, product_id: str, token: str) -> PlayProduct:
        """Look up a one-time product token."""
        data = self._call("GET", f"products/{product_id}/tokens/{token}")
        if data.get("_invalid"):
            return PlayProduct(False, False, None, None, None)
        return PlayProduct(
            purchased=data.get("purchaseState") == 0,
            consumed=data.get("consumptionState") == 1,
            account_id=data.get("obfuscatedExternalAccountId"),
            profile_id=data.get("obfuscatedExternalProfileId"),
            order_id=data.get("orderId"),
        )

    def consume_product(self, product_id: str, token: str) -> None:
        """Consume so the same product can be bought again (another topic / child)."""
        self._call("POST", f"products/{product_id}/tokens/{token}:consume")


@lru_cache(maxsize=1)
def get_play_verifier() -> PlayVerifier:
    """FastAPI dependency: the configured Google Play client."""
    if not settings.PLAY_SERVICE_ACCOUNT_JSON:
        raise BillingNotConfiguredError()
    return GooglePlayVerifier(settings.PLAY_SERVICE_ACCOUNT_JSON, settings.PLAY_PACKAGE_NAME)
