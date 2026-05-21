"""tiqopay — official Python SDK for the tiqopay escrow API.

Basic usage:

    from tiqopay import Tiqopay

    client = Tiqopay(api_key="sk_test_...")
    txn = client.transactions.create(
        amount=50000,
        description="Logo design",
        seller={"email": "seller@example.ma"},
        buyer={"email": "buyer@example.ma"},
        delivery_deadline_days=7,
    )

Webhook verification:

    from tiqopay.webhooks import verify_webhook

    event = verify_webhook(
        payload=request.body,
        signature=request.headers["tiqopay-signature"],
        secret=os.environ["WEBHOOK_SECRET"],
    )
"""

from .client import Tiqopay
from .errors import TiqopayError
from .webhooks import WebhookVerificationError, verify_webhook

__all__ = [
    "Tiqopay",
    "TiqopayError",
    "WebhookVerificationError",
    "verify_webhook",
]

__version__ = "1.0.0"
