"""Synchronous client for the SPARKIT API."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from sparkit_science._http import DEFAULT_BASE_URL, HttpTransport
from sparkit_science.exceptions import (
    CancelledError,
    SparkitError,
)
from sparkit_science.models import Job, Result, Usage

_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"completed", "failed", "cancelled"}
)


class SparkitClient:
    """Synchronous SPARKIT API client.

    The high-level `research()` method blocks-and-polls until the job is
    terminal. Lower-level methods (`submit()`, `get_job()`, `cancel_job()`,
    `usage()`) wrap individual endpoints for agent loops and webhook flows.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        max_retries: int = 3,
        poll_interval: tuple[float, float] = (1.0, 15.0),
        http_client: httpx.Client | None = None,
    ) -> None:
        resolved = api_key or os.environ.get("SPARKIT_API_KEY")
        if not resolved:
            raise ValueError(
                "api_key is required; pass api_key=... or set SPARKIT_API_KEY"
            )
        self._transport = HttpTransport(
            api_key=resolved,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            client=http_client,
        )
        self._poll_initial, self._poll_max = poll_interval

    # ----- Lifecycle -----

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> SparkitClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ----- Endpoints -----

    def submit(
        self,
        question: str,
        *,
        callback_url: str | None = None,
        max_cost_usd: float | None = None,
        response_format: str | None = None,
        max_answer_tokens: int | None = None,
        include_citations: bool | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Job:
        body = _build_submit_body(
            question=question,
            callback_url=callback_url,
            max_cost_usd=max_cost_usd,
            response_format=response_format,
            max_answer_tokens=max_answer_tokens,
            include_citations=include_citations,
            metadata=metadata,
        )
        payload, _ = self._transport.request(
            "POST",
            "/v1/research",
            json_body=body,
            idempotency_key=idempotency_key,
        )
        return Job.model_validate(payload)

    def get_job(self, job_id: str) -> Job:
        payload, _ = self._transport.request(
            "GET", f"/v1/research/{job_id}"
        )
        return _parse_job_or_raise(payload)

    def cancel_job(self, job_id: str) -> Job:
        payload, _ = self._transport.request(
            "DELETE", f"/v1/research/{job_id}"
        )
        return Job.model_validate(payload)

    def usage(self) -> Usage:
        payload, _ = self._transport.request("GET", "/v1/usage")
        return Usage.model_validate(payload)

    # ----- High-level -----

    def research(
        self,
        question: str,
        *,
        callback_url: str | None = None,
        max_cost_usd: float | None = None,
        response_format: str | None = None,
        max_answer_tokens: int | None = None,
        include_citations: bool | None = None,
        metadata: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Result:
        """Submit a question, poll until terminal, return the Result.

        Raises a typed `SparkitError` subclass if the job ends in `failed`
        or `cancelled` status.
        """
        job = self.submit(
            question,
            callback_url=callback_url,
            max_cost_usd=max_cost_usd,
            response_format=response_format,
            max_answer_tokens=max_answer_tokens,
            include_citations=include_citations,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )
        wait = self._poll_initial
        while job.status not in _TERMINAL_STATUSES:
            if wait > 0:
                time.sleep(wait)
            wait = min(self._poll_max, wait * 2 if wait > 0 else self._poll_initial)
            job = self.get_job(job.id)

        if job.status == "completed" and job.result is not None:
            return job.result
        if job.status == "cancelled":
            raise CancelledError(
                code="cancelled",
                message="Job was cancelled before completion.",
                job_id=job.id,
            )
        # Failed: server should have included an error code in the payload,
        # which `_parse_job_or_raise` already mapped. Defensive fallback:
        raise SparkitError(
            code="internal_error",
            message="Job ended in unexpected state.",
            job_id=job.id,
        )


def _build_submit_body(
    *,
    question: str,
    callback_url: str | None,
    max_cost_usd: float | None,
    response_format: str | None,
    max_answer_tokens: int | None,
    include_citations: bool | None,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"question": question}
    if callback_url is not None:
        body["callback_url"] = callback_url
    if max_cost_usd is not None:
        body["max_cost_usd"] = max_cost_usd
    if response_format is not None:
        body["response_format"] = response_format
    if max_answer_tokens is not None:
        body["max_answer_tokens"] = max_answer_tokens
    if include_citations is not None:
        body["include_citations"] = include_citations
    if metadata is not None:
        body["metadata"] = metadata
    return body


def _parse_job_or_raise(payload: dict[str, Any]) -> Job:
    """Parse a Job. If the payload also carries an `error` object (server
    convention for terminal-failed jobs), raise the corresponding typed
    exception so `research()`'s polling loop surfaces it cleanly.
    """
    if "error" in payload and isinstance(payload["error"], dict):
        raise SparkitError.from_api_payload(payload)
    return Job.model_validate(payload)
