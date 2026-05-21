"""tiqopay client and resource classes.

The public surface mirrors the Node SDK so that integration teams can move
between languages without re-learning the API shape. Methods accept keyword
arguments matching the REST field names (snake_case) and return raw ``dict``
objects parsed from the JSON response — no model wrapping, so new server
fields show up immediately without an SDK release.
"""

from typing import Any, Optional

from . import _http


class _Resource:
    """Base class — holds the per-client config shared by every resource."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float,
        max_retries: int,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._max_retries = max_retries

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        return _http.request(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout,
            max_retries=self._max_retries,
            method=method,
            path=path,
            body=body,
            params=params,
        )


class Accounts(_Resource):
    """Account information for the authenticated key."""

    def retrieve(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/account")


class Transactions(_Resource):
    """Escrow transactions — create, deliver, dispute, refund, cancel."""

    def create(self, **params: Any) -> dict[str, Any]:
        return self._request("POST", "/api/v1/transactions", body=params)

    def list(self, **params: Any) -> dict[str, Any]:
        return self._request("GET", "/api/v1/transactions", params=params)

    def retrieve(self, transaction_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/transactions/{transaction_id}")

    def deliver(self, transaction_id: str, **params: Any) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/transactions/{transaction_id}/deliver", body=params)

    # Release is intentionally NOT in the public SDK. Escrow release is
    # buyer-driven (confirm-receipt token) or time-driven (cron auto-release).
    # A seller-callable release would let a fraudulent merchant skip the
    # dispute window. Keep in lockstep with the Node SDK.

    def dispute(self, transaction_id: str, **params: Any) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/transactions/{transaction_id}/dispute", body=params)

    def refund(self, transaction_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/transactions/{transaction_id}/refund")

    def cancel(self, transaction_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/transactions/{transaction_id}/cancel")


class PaymentLinks(_Resource):
    """Reusable payment links — buyers fund a transaction via a shareable URL."""

    def create(self, **params: Any) -> dict[str, Any]:
        return self._request("POST", "/api/v1/payment-links", body=params)

    def list(self, **params: Any) -> dict[str, Any]:
        return self._request("GET", "/api/v1/payment-links", params=params)

    def retrieve(self, link_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/payment-links/{link_id}")

    def update(self, link_id: str, **params: Any) -> dict[str, Any]:
        return self._request("PATCH", f"/api/v1/payment-links/{link_id}", body=params)

    def delete(self, link_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/api/v1/payment-links/{link_id}")


class WebhookEndpoints(_Resource):
    """Webhook subscriptions — pick which events to receive on which URL."""

    def create(self, **params: Any) -> dict[str, Any]:
        return self._request("POST", "/api/v1/webhook-endpoints", body=params)

    def list(self, **params: Any) -> dict[str, Any]:
        return self._request("GET", "/api/v1/webhook-endpoints", params=params)

    def retrieve(self, endpoint_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/webhook-endpoints/{endpoint_id}")

    def delete(self, endpoint_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/api/v1/webhook-endpoints/{endpoint_id}")


class Events(_Resource):
    """Historical events — replay anything the webhook missed."""

    def list(self, **params: Any) -> dict[str, Any]:
        return self._request("GET", "/api/v1/events", params=params)

    def retrieve(self, event_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/events/{event_id}")


class Payouts(_Resource):
    """Bank-wire payouts settled to the seller's RIB."""

    def list(self, **params: Any) -> dict[str, Any]:
        return self._request("GET", "/api/v1/payouts", params=params)

    def retrieve(self, payout_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/payouts/{payout_id}")


class Notifications(_Resource):
    """Dashboard notifications surfaced to the authenticated account."""

    def list(self, **params: Any) -> dict[str, Any]:
        return self._request("GET", "/api/v1/notifications", params=params)

    def retrieve(self, notification_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/notifications/{notification_id}")

    def update(self, notification_id: str, *, is_read: bool) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/api/v1/notifications/{notification_id}",
            body={"is_read": is_read},
        )

    def mark_all_read(self) -> dict[str, Any]:
        return self._request("POST", "/api/v1/notifications/mark-all-read")


class Tiqopay:
    """Top-level tiqopay client.

    Args:
        api_key:     Your secret API key (``sk_test_...`` or ``sk_live_...``).
        base_url:    Override the API origin. Defaults to
                     ``https://tiqopay.com/api``. Only override for local
                     development or self-hosted setups — point at the API
                     origin without ``/v1``; resource methods append the
                     versioned path themselves.
        timeout:     Per-request timeout in seconds. Default ``30``.
        max_retries: Retries on 429 / 5xx with exponential backoff + jitter.
                     Default ``3``.

    Example:
        >>> client = Tiqopay(api_key="sk_test_...")
        >>> txn = client.transactions.create(
        ...     amount=50000,
        ...     description="Logo design",
        ...     seller={"email": "seller@example.ma"},
        ...     buyer={"email": "buyer@example.ma"},
        ...     delivery_deadline_days=7,
        ... )
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://tiqopay.com/api",
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise ValueError("tiqopay: api_key is required")

        self.account = Accounts(api_key, base_url, timeout, max_retries)
        self.transactions = Transactions(api_key, base_url, timeout, max_retries)
        self.payment_links = PaymentLinks(api_key, base_url, timeout, max_retries)
        self.webhook_endpoints = WebhookEndpoints(api_key, base_url, timeout, max_retries)
        self.events = Events(api_key, base_url, timeout, max_retries)
        self.payouts = Payouts(api_key, base_url, timeout, max_retries)
        self.notifications = Notifications(api_key, base_url, timeout, max_retries)
