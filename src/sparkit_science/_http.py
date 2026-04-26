"""HTTP transport with retries, idempotency, and error mapping.

Both `SparkitClient` (sync) and `AsyncSparkitClient` (async) build on top
of this module. The sync path lives in `HttpTransport`; the async path
in `AsyncHttpTransport`. Both share the same retry policy and error
mapping logic via `_should_retry` and `SparkitError.from_api_payload`.
"""

from __future__ import annotations

import logging
import random
import time
import uuid
from typing import Any

import httpx

from sparkit_science._version import __version__
from sparkit_science.exceptions import RateLimitedError, SparkitError

DEFAULT_BASE_URL = "https://jlsteenwyk--sparkit-api-web.modal.run"
USER_AGENT = f"sparkit-science-py/{__version__}"

_log = logging.getLogger("sparkit_science")


def _should_retry(status_code: int) -> bool:
    """Return True for transient failures the SDK should retry."""
    return status_code == 429 or 500 <= status_code < 600


def _backoff_seconds(attempt: int, initial: float, cap: float = 30.0) -> float:
    """Exponential backoff with full jitter."""
    expo = min(cap, initial * (2**attempt))
    return random.uniform(0, expo)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _build_headers(
    api_key: str, idempotency_key: str | None
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _request_id(response: httpx.Response) -> str | None:
    value: str | None = response.headers.get("X-Request-ID") or response.headers.get(
        "X-Request-Id"
    )
    return value


def _parse_or_none(response: httpx.Response) -> dict[str, Any] | None:
    try:
        body = response.json()
    except Exception:
        return None
    if not isinstance(body, dict):
        return None
    return body


def _raise_from_response(response: httpx.Response) -> None:
    payload = _parse_or_none(response)
    raise SparkitError.from_api_payload(
        payload,
        request_id=_request_id(response),
        status_code=response.status_code,
        retry_after=_retry_after_seconds(response),
    )


class HttpTransport:
    """Synchronous HTTP transport."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        max_retries: int = 3,
        retry_initial_backoff: float = 0.5,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._retry_initial_backoff = retry_initial_backoff
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> HttpTransport:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Send a request, retrying on transient failures, and return the
        decoded JSON body plus the X-Request-ID header (if present).
        """
        # Generate a stable idempotency key for body-bearing requests so
        # that internal retries inside this loop hit the same job server-side.
        key = idempotency_key
        if json_body is not None and key is None:
            key = uuid.uuid4().hex

        url = f"{self._base_url}{path}"
        headers = _build_headers(self._api_key, key)
        last_response: httpx.Response | None = None

        for attempt in range(self._max_retries + 1):
            response = self._client.request(
                method, url, headers=headers, json=json_body, params=params
            )
            _log.debug(
                "sparkit-science %s %s -> %d",
                method,
                path,
                response.status_code,
            )
            last_response = response

            if response.is_success:
                payload = _parse_or_none(response) or {}
                return payload, _request_id(response)

            if not _should_retry(response.status_code):
                _raise_from_response(response)
                # Unreachable; for type-checker:
                raise AssertionError("error mapping must raise")

            if attempt >= self._max_retries:
                break

            wait = _retry_after_seconds(response)
            if wait is None:
                wait = _backoff_seconds(attempt, self._retry_initial_backoff)
            if wait > 0:
                time.sleep(wait)

        assert last_response is not None
        _raise_from_response(last_response)
        raise AssertionError("unreachable")


class AsyncHttpTransport:
    """Asynchronous HTTP transport. Mirror of HttpTransport."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        max_retries: int = 3,
        retry_initial_backoff: float = 0.5,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._retry_initial_backoff = retry_initial_backoff
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> AsyncHttpTransport:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        import asyncio

        key = idempotency_key
        if json_body is not None and key is None:
            key = uuid.uuid4().hex

        url = f"{self._base_url}{path}"
        headers = _build_headers(self._api_key, key)
        last_response: httpx.Response | None = None

        for attempt in range(self._max_retries + 1):
            response = await self._client.request(
                method, url, headers=headers, json=json_body, params=params
            )
            _log.debug(
                "sparkit-science async %s %s -> %d",
                method,
                path,
                response.status_code,
            )
            last_response = response

            if response.is_success:
                payload = _parse_or_none(response) or {}
                return payload, _request_id(response)

            if not _should_retry(response.status_code):
                _raise_from_response(response)
                raise AssertionError("error mapping must raise")

            if attempt >= self._max_retries:
                break

            wait = _retry_after_seconds(response)
            if wait is None:
                wait = _backoff_seconds(attempt, self._retry_initial_backoff)
            if wait > 0:
                await asyncio.sleep(wait)

        assert last_response is not None
        _raise_from_response(last_response)
        raise AssertionError("unreachable")


__all__ = [
    "DEFAULT_BASE_URL",
    "USER_AGENT",
    "HttpTransport",
    "AsyncHttpTransport",
    "RateLimitedError",  # re-export for convenience
]
