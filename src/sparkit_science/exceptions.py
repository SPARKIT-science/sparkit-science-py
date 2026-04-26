"""Typed exception hierarchy for SPARKIT API errors."""

from __future__ import annotations

from typing import Any


class SparkitError(Exception):
    """Base class for all SPARKIT API errors.

    Subclasses correspond to the API's stable error codes. Unknown server
    codes surface as the base class so callers can still match on `e.code`
    even before the SDK is updated.
    """

    code: str
    message: str
    request_id: str | None
    job_id: str | None

    def __init__(
        self,
        *,
        code: str,
        message: str,
        request_id: str | None = None,
        job_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.request_id = request_id
        self.job_id = job_id

    @classmethod
    def from_api_payload(
        cls,
        payload: dict[str, Any] | None,
        *,
        request_id: str | None = None,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> SparkitError:
        """Build the most-specific exception type for an API error payload.

        Falls back to `SparkitError(code='internal_error')` if the payload
        does not contain a recognizable `error` object — this happens when
        the gateway returns a 5xx without a JSON body.
        """
        body = payload or {}
        err_obj = body.get("error") if isinstance(body, dict) else None
        if not isinstance(err_obj, dict):
            return InternalError(
                code="internal_error",
                message=f"Unexpected response (status {status_code})"
                if status_code is not None
                else "Unexpected response",
                request_id=request_id,
            )

        code = str(err_obj.get("code") or "internal_error")
        message = str(err_obj.get("message") or "")
        job_id = err_obj.get("job_id")

        klass = _CODE_TO_CLASS.get(code, SparkitError)
        kwargs: dict[str, Any] = {
            "code": code,
            "message": message,
            "request_id": request_id,
            "job_id": job_id if isinstance(job_id, str) else None,
        }
        if klass is RateLimitedError:
            kwargs["retry_after"] = retry_after
        return klass(**kwargs)


class InvalidRequestError(SparkitError):
    """400-level: request was malformed or missing required fields."""


class AuthenticationError(SparkitError):
    """401: API key invalid or missing."""


class RateLimitedError(SparkitError):
    """429: too many requests. `retry_after` is the server-suggested wait."""

    retry_after: float | None

    def __init__(
        self,
        *,
        code: str,
        message: str,
        request_id: str | None = None,
        job_id: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(
            code=code, message=message, request_id=request_id, job_id=job_id
        )
        self.retry_after = retry_after


class QuotaExhaustedError(SparkitError):
    """402: monthly query quota is exhausted."""


class CostCapExceededError(SparkitError):
    """402: per-job `max_cost_usd` was exceeded; job aborted."""


class SafetyBlockedError(SparkitError):
    """422: query rejected by safety screening."""


class EmbeddedCodeError(SparkitError):
    """422: query contained embedded code, which is not permitted."""


class TimeoutError(SparkitError):  # noqa: A001 - shadowing the builtin is intentional
    """504: the job exceeded the server-side timeout."""


class CancelledError(SparkitError):
    """The job was cancelled (terminal status, surfaced from research())."""


class InternalError(SparkitError):
    """5xx or otherwise unexpected server response."""


class InvalidSignatureError(SparkitError):
    """Webhook signature verification failed."""


_CODE_TO_CLASS: dict[str, type[SparkitError]] = {
    "invalid_request": InvalidRequestError,
    "unauthorized": AuthenticationError,
    "rate_limited": RateLimitedError,
    "quota_exhausted": QuotaExhaustedError,
    "cost_cap_exceeded": CostCapExceededError,
    "safety_blocked": SafetyBlockedError,
    "embedded_code": EmbeddedCodeError,
    "timeout": TimeoutError,
    "cancelled": CancelledError,
    "internal_error": InternalError,
}
