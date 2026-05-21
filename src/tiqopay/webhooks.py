"""Webhook signature verification for tiqopay.

The server signs each webhook payload as::

    tiqopay-Signature: t=<unix>,v1=<hmac_sha256(secret, "<t>.<body>")>

During a secret rotation, the header carries multiple ``v1=`` entries — one
per active secret. ``verify_webhook`` succeeds if your stored secret matches
ANY of them, so updating the secret on either side of the rotation works
without dropping events.
"""

import hmac
import json
import time
from hashlib import sha256
from typing import Any, Optional, Union


class WebhookVerificationError(Exception):
    """Raised when a webhook signature is missing, malformed, stale, or
    does not match the secret. Always reject the request with 400/401 when
    this is raised — never log the payload as if it were trusted."""


def verify_webhook(
    payload: Union[str, bytes],
    signature: Optional[str],
    secret: str,
    tolerance: int = 300,
) -> dict[str, Any]:
    """Verify the ``tiqopay-Signature`` header and return the parsed event.

    Args:
        payload:   Raw HTTP request body (string or bytes). Must be the exact
                   bytes received — any re-serialization will invalidate the
                   signature.
        signature: Value of the ``tiqopay-Signature`` request header.
        secret:    Your webhook endpoint secret (``whsec_...``). Find it on
                   the dashboard under Developers → Webhooks → <endpoint>.
        tolerance: Maximum payload age in seconds (default ``300`` = 5 min).
                   Rejects replays older than this.

    Returns:
        The parsed event as a ``dict``. Look at ``event["type"]`` to dispatch.

    Raises:
        WebhookVerificationError: signature missing/malformed, timestamp too
            old, or no signature entry matches ``secret``.

    Example::

        from tiqopay.webhooks import verify_webhook, WebhookVerificationError

        @app.post("/webhooks/tiqopay")
        def handle(request):
            try:
                event = verify_webhook(
                    payload=request.body,
                    signature=request.headers.get("tiqopay-signature"),
                    secret=os.environ["WEBHOOK_SECRET"],
                )
            except WebhookVerificationError:
                return Response(status=400)

            if event["type"] == "transaction.funded":
                ...
            return Response(status=200)
    """
    if not signature:
        raise WebhookVerificationError("Missing signature header")

    if isinstance(payload, bytes):
        payload_str = payload.decode("utf-8")
    else:
        payload_str = payload

    parts = [p.strip() for p in signature.split(",") if p.strip()]
    t_part = next((p for p in parts if p.startswith("t=")), None)
    # The server may sign with multiple secrets during a rotation overlap;
    # the header then carries one ``v1=`` entry per active secret. Accept the
    # payload if any matches the secret we hold.
    v1_parts = [p for p in parts if p.startswith("v1=")]

    if t_part is None or not v1_parts:
        raise WebhookVerificationError("Invalid signature format")

    try:
        timestamp = int(t_part[2:])
    except ValueError as err:
        raise WebhookVerificationError("Invalid timestamp in signature") from err

    age = int(time.time()) - timestamp
    if age > tolerance:
        raise WebhookVerificationError(
            f"Webhook timestamp too old ({age}s > {tolerance}s tolerance)"
        )

    signed_payload = f"{timestamp}.{payload_str}".encode("utf-8")
    expected_sig = hmac.new(
        secret.encode("utf-8"), signed_payload, sha256
    ).hexdigest()

    for entry in v1_parts:
        received_sig = entry[3:]
        # ``hmac.compare_digest`` is constant-time; safe for untrusted input.
        if hmac.compare_digest(expected_sig, received_sig):
            return json.loads(payload_str)

    raise WebhookVerificationError("Signature mismatch")
