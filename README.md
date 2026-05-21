# tiqopay — official Python SDK

Escrow payments for Morocco. The SDK mirrors [`@tiqopay/sdk`](https://www.npmjs.com/package/@tiqopay/sdk) (Node) one-for-one — same resources, same field names, same retry behavior — so polyglot teams can move between languages without re-learning the API.

[![PyPI version](https://img.shields.io/pypi/v/tiqopay.svg)](https://pypi.org/project/tiqopay/)
[![Python versions](https://img.shields.io/pypi/pyversions/tiqopay.svg)](https://pypi.org/project/tiqopay/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Install

```bash
pip install tiqopay
```

Requires Python 3.9+. Zero runtime dependencies — uses stdlib `urllib` and `hmac` only.

## Quickstart

```python
from tiqopay import Tiqopay

client = Tiqopay(api_key="sk_test_...")

txn = client.transactions.create(
    amount=50000,                       # 500.00 MAD in centimes
    description="Logo design",
    seller={"email": "seller@example.ma"},
    buyer={"email": "buyer@example.ma"},
    delivery_deadline_days=7,
)

print(txn["payment_url"])
```

## Webhook verification

```python
import os
from tiqopay.webhooks import verify_webhook, WebhookVerificationError

# FastAPI / Starlette example
@app.post("/webhooks/tiqopay")
async def handle(request: Request):
    body = await request.body()
    try:
        event = verify_webhook(
            payload=body,
            signature=request.headers.get("tiqopay-signature"),
            secret=os.environ["WEBHOOK_SECRET"],
        )
    except WebhookVerificationError:
        return Response(status_code=400)

    if event["type"] == "transaction.funded":
        ...

    return {"received": True}
```

Pass the **raw** request body — any re-serialization breaks the signature. The verifier handles secret-rotation overlaps automatically.

## Resources

| Resource | Methods |
|---|---|
| `client.account` | `retrieve()` |
| `client.transactions` | `create`, `list`, `retrieve`, `deliver`, `dispute`, `refund`, `cancel` |
| `client.payment_links` | `create`, `list`, `retrieve`, `update`, `delete` |
| `client.webhook_endpoints` | `create`, `list`, `retrieve`, `delete` |
| `client.events` | `list`, `retrieve` |
| `client.payouts` | `list`, `retrieve` |
| `client.notifications` | `list`, `retrieve`, `update`, `mark_all_read` |

> Escrow release is intentionally not exposed. Funds are released by the buyer (via the confirm-receipt link) or automatically 48 h after delivery — not by the seller. See the API docs for the full rationale.

## Errors

```python
from tiqopay import TiqopayError

try:
    client.transactions.retrieve("txn_nope")
except TiqopayError as err:
    print(err.status, err.code, err.message)
```

`err.status == 0` means a transport-level failure (DNS, timeout, TLS) after the retry budget. Everything else is an HTTP status from the API; see [the error catalog](https://tiqopay.com/developers/errors) for `err.code` recovery guidance.

## Configuration

```python
Tiqopay(
    api_key="sk_test_...",
    base_url="https://tiqopay.com/api",  # override only for local dev
    timeout=30,                          # per-request seconds
    max_retries=3,                       # 429 / 5xx, exponential backoff
)
```

The SDK pins `Tiqopay-Version: 2026-04-18` on every request. Upgrading the package is what opts you into a newer API version — backend defaults never shift behavior under you.

## License

MIT.
