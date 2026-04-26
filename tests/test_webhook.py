"""Tests for sparkit_science.webhook.verify_webhook."""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest


def _sign(secret: str, timestamp: int, payload: bytes) -> str:
    msg = f"{timestamp}.".encode() + payload
    sig = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"


def test_verify_webhook_returns_typed_event(webhook_payload: dict) -> None:
    from sparkit_science.webhook import verify_webhook

    secret = "whsec_test"
    body = json.dumps(webhook_payload).encode()
    ts = int(time.time())
    header = _sign(secret, ts, body)

    event = verify_webhook(payload=body, sig_header=header, secret=secret)
    assert event.type == "research.completed"
    assert event.job.status == "completed"


def test_verify_webhook_raises_on_bad_signature(webhook_payload: dict) -> None:
    from sparkit_science.exceptions import InvalidSignatureError
    from sparkit_science.webhook import verify_webhook

    body = json.dumps(webhook_payload).encode()
    ts = int(time.time())
    header = _sign("the_wrong_secret", ts, body)

    with pytest.raises(InvalidSignatureError):
        verify_webhook(payload=body, sig_header=header, secret="whsec_test")


def test_verify_webhook_raises_on_stale_timestamp(webhook_payload: dict) -> None:
    from sparkit_science.exceptions import InvalidSignatureError
    from sparkit_science.webhook import verify_webhook

    secret = "whsec_test"
    body = json.dumps(webhook_payload).encode()
    ts = int(time.time()) - 600  # 10 minutes ago
    header = _sign(secret, ts, body)

    with pytest.raises(InvalidSignatureError):
        verify_webhook(
            payload=body, sig_header=header, secret=secret, tolerance_seconds=300
        )


def test_verify_webhook_raises_on_malformed_header(webhook_payload: dict) -> None:
    from sparkit_science.exceptions import InvalidSignatureError
    from sparkit_science.webhook import verify_webhook

    body = json.dumps(webhook_payload).encode()
    with pytest.raises(InvalidSignatureError):
        verify_webhook(
            payload=body,
            sig_header="this is not a signature",
            secret="whsec_test",
        )
