"""Tests for sparkit_science.exceptions."""

from __future__ import annotations

import pytest


def test_base_error_carries_code_and_message() -> None:
    from sparkit_science.exceptions import SparkitError

    err = SparkitError(code="some_code", message="boom", request_id="req_1")
    assert err.code == "some_code"
    assert err.message == "boom"
    assert err.request_id == "req_1"
    assert "boom" in str(err)


def test_typed_subclasses_inherit_from_base() -> None:
    from sparkit_science.exceptions import (
        AuthenticationError,
        CancelledError,
        CostCapExceededError,
        InternalError,
        InvalidRequestError,
        InvalidSignatureError,
        QuotaExhaustedError,
        RateLimitedError,
        SafetyBlockedError,
        SparkitError,
    )
    from sparkit_science.exceptions import (
        TimeoutError as SparkitTimeoutError,
    )

    typed = [
        InvalidRequestError,
        AuthenticationError,
        RateLimitedError,
        QuotaExhaustedError,
        CostCapExceededError,
        SafetyBlockedError,
        SparkitTimeoutError,
        CancelledError,
        InternalError,
        InvalidSignatureError,
    ]
    for cls in typed:
        assert issubclass(cls, SparkitError)


def test_rate_limited_error_carries_retry_after() -> None:
    from sparkit_science.exceptions import RateLimitedError

    err = RateLimitedError(
        code="rate_limited", message="slow down", retry_after=3.5
    )
    assert err.retry_after == pytest.approx(3.5)


def test_from_api_payload_picks_typed_subclass() -> None:
    from sparkit_science.exceptions import (
        QuotaExhaustedError,
        SparkitError,
    )

    err = SparkitError.from_api_payload(
        {"error": {"code": "quota_exhausted", "message": "nope"}},
        request_id="req_2",
    )
    assert isinstance(err, QuotaExhaustedError)
    assert err.code == "quota_exhausted"
    assert err.request_id == "req_2"


def test_from_api_payload_uses_base_for_unknown_code() -> None:
    from sparkit_science.exceptions import SparkitError

    err = SparkitError.from_api_payload(
        {"error": {"code": "future_code", "message": "?"}},
    )
    # Unknown code surfaces as the base class, not raises.
    assert type(err).__name__ == "SparkitError"
    assert err.code == "future_code"


def test_from_api_payload_handles_missing_error_object() -> None:
    from sparkit_science.exceptions import SparkitError

    err = SparkitError.from_api_payload({}, status_code=503)
    assert err.code == "internal_error"
