"""Internal HTTP helper: builds requests via stdlib urllib, handles retries
with exponential backoff and jitter, and surfaces tiqopay errors.

Kept private (``_http``) because the contract belongs to ``client.Tiqopay``;
callers should never depend on this module directly.
"""

import json
import random
import time
from typing import Any, Mapping, Optional
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from .errors import TiqopayError


# API version this SDK build was developed against. Sent as ``Tiqopay-Version``
# on every request. Bump this in lockstep with each SDK release whenever the
# server publishes a new dated API version. Literal on purpose: upgrading the
# SDK package is what opts users into a newer API version — never let a
# backend default shift behavior under them.
SDK_API_VERSION = "2026-04-18"


def _build_url(base_url: str, path: str, params: Optional[Mapping[str, Any]]) -> str:
    """Compose ``base_url + path`` and append non-None query parameters."""
    base = base_url.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    url = base + path
    if params:
        cleaned = {k: str(v) for k, v in params.items() if v is not None}
        if cleaned:
            url = url + "?" + urllib_parse.urlencode(cleaned)
    return url


def request(
    api_key: str,
    base_url: str,
    timeout: float,
    max_retries: int,
    method: str,
    path: str,
    body: Optional[Mapping[str, Any]] = None,
    params: Optional[Mapping[str, Any]] = None,
) -> Any:
    """Perform an authenticated HTTP request against the tiqopay API.

    Retries 429 and 5xx responses with exponential backoff + jitter, up to
    ``max_retries`` times. On 429 we honour ``X-RateLimit-Reset`` (Unix
    timestamp) when it points within 60 seconds.

    Raises:
        TiqopayError: for any non-2xx response after retries, or for a
            transport-level failure after the retry budget is exhausted.
    """
    url = _build_url(base_url, path, params)
    payload: Optional[bytes] = None
    if body is not None:
        payload = json.dumps(body).encode("utf-8")

    last_error: Optional[TiqopayError] = None

    for attempt in range(max_retries + 1):
        if attempt > 0:
            # Exponential backoff with jitter: 500ms, 1s, 2s + random jitter.
            delay = min(0.5 * (2 ** (attempt - 1)), 4.0)
            jitter = random.random() * 0.2
            time.sleep(delay + jitter)

        req = urllib_request.Request(url, data=payload, method=method.upper())
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Tiqopay-Version", SDK_API_VERSION)

        try:
            with urllib_request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))

        except urllib_error.HTTPError as http_err:
            status = http_err.code
            data: dict[str, Any] = {}
            try:
                raw = http_err.read()
                if raw:
                    data = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError, OSError):
                # Fall back to status text — server returned a non-JSON body
                # (typically only on infra errors like 502 from a CDN).
                data = {}

            err_block = data.get("error") if isinstance(data.get("error"), dict) else {}
            message = (
                err_block.get("message")
                or data.get("message")
                or http_err.reason
                or f"HTTP {status}"
            )
            code = err_block.get("code") or data.get("code")
            last_error = TiqopayError(message, status, code)

            # Only retry on 429 (rate limit) and 5xx (server errors).
            should_retry = status == 429 or status >= 500
            if not should_retry or attempt == max_retries:
                raise last_error

            if status == 429:
                reset_header = http_err.headers.get("X-RateLimit-Reset")
                if reset_header:
                    try:
                        reset_at = int(reset_header)
                        wait = max(0.0, reset_at - time.time())
                        if 0 < wait < 60:
                            time.sleep(wait)
                            continue
                    except (TypeError, ValueError):
                        pass

        except urllib_error.URLError as url_err:
            # Network errors (DNS, refused, TLS, timeout). Retry until budget
            # is exhausted, then surface a transport-level TiqopayError with
            # status=0 so callers can branch on ``err.status == 0``.
            reason = getattr(url_err, "reason", url_err)
            if attempt == max_retries:
                raise TiqopayError(str(reason), 0, "network_error")

        except TimeoutError as timeout_err:
            if attempt == max_retries:
                raise TiqopayError(str(timeout_err) or "Request timed out", 0, "network_error")

    # Should never reach — loop either returns or raises.
    raise last_error or TiqopayError("Request failed after retries", 0, "max_retries_exceeded")
