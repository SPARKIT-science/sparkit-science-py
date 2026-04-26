"""Webhook signature verifier."""

from __future__ import annotations

import hashlib
import hmac
import json
import time

from sparkit_science.exceptions import InvalidSignatureError
from sparkit_science.models import WebhookEvent

_SCHEME = "v1"


def verify_webhook(
    *,
    payload: bytes,
    sig_header: str,
    secret: str,
    tolerance_seconds: int = 300,
) -> WebhookEvent:
    """Verify the HMAC-SHA256 signature on a webhook delivery.

    The header is expected to look like ``t=<unix_ts>,v1=<hex_signature>``.
    The signed message is ``f"{timestamp}." + payload``, identical to the
    Stripe scheme.

    Raises:
        InvalidSignatureError: if the header is malformed, the signature
            is wrong, or the timestamp drifts beyond ``tolerance_seconds``.

    Returns:
        A typed `WebhookEvent` parsed from the JSON payload.
    """
    timestamp, signature = _parse_header(sig_header)
    expected = _compute_signature(secret, timestamp, payload)
    if not hmac.compare_digest(expected, signature):
        raise InvalidSignatureError(
            code="invalid_signature",
            message="Webhook signature does not match.",
        )
    if abs(int(time.time()) - timestamp) > tolerance_seconds:
        raise InvalidSignatureError(
            code="invalid_signature",
            message=(
                f"Webhook timestamp drift exceeds tolerance of "
                f"{tolerance_seconds}s."
            ),
        )

    try:
        body = json.loads(payload)
    except Exception as exc:  # pragma: no cover - guard against future drift
        raise InvalidSignatureError(
            code="invalid_signature",
            message=f"Webhook payload is not valid JSON: {exc}",
        ) from exc
    return WebhookEvent.model_validate(body)


def _parse_header(header: str) -> tuple[int, str]:
    parts = [p.strip() for p in header.split(",")]
    fields: dict[str, str] = {}
    for p in parts:
        if "=" not in p:
            raise InvalidSignatureError(
                code="invalid_signature",
                message="Webhook signature header is malformed.",
            )
        k, v = p.split("=", 1)
        fields[k.strip()] = v.strip()

    raw_ts = fields.get("t")
    sig = fields.get(_SCHEME)
    if raw_ts is None or sig is None:
        raise InvalidSignatureError(
            code="invalid_signature",
            message="Webhook signature header is missing required fields.",
        )

    try:
        ts = int(raw_ts)
    except ValueError as exc:
        raise InvalidSignatureError(
            code="invalid_signature",
            message="Webhook timestamp is not an integer.",
        ) from exc

    return ts, sig


def _compute_signature(secret: str, timestamp: int, payload: bytes) -> str:
    msg = f"{timestamp}.".encode() + payload
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
