"""Asynchronous client for the SPARKIT API."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from sparkit_science._http import AsyncHttpTransport, DEFAULT_BASE_URL
from sparkit_science.client import (
    _TERMINAL_STATUSES,
    _build_submit_body,
    _parse_job_or_raise,
)
from sparkit_science.exceptions import (
    CancelledError,
    SparkitError,
)
from sparkit_science.models import Job, Result, Usage


class AsyncSparkitClient:
    """Asynchronous SPARKIT API client. Mirrors `SparkitClient`."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        max_retries: int = 3,
        poll_interval: tuple[float, float] = (1.0, 15.0),
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        resolved = api_key or os.environ.get("SPARKIT_API_KEY")
        if not resolved:
            raise ValueError(
                "api_key is required; pass api_key=... or set SPARKIT_API_KEY"
            )
        self._transport = AsyncHttpTransport(
            api_key=resolved,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            client=http_client,
        )
        self._poll_initial, self._poll_max = poll_interval

    async def aclose(self) -> None:
        await self._transport.aclose()

    async def __aenter__(self) -> "AsyncSparkitClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def submit(
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
        payload, _ = await self._transport.request(
            "POST",
            "/v1/research",
            json_body=body,
            idempotency_key=idempotency_key,
        )
        return Job.model_validate(payload)

    async def get_job(self, job_id: str) -> Job:
        payload, _ = await self._transport.request(
            "GET", f"/v1/research/{job_id}"
        )
        return _parse_job_or_raise(payload)

    async def cancel_job(self, job_id: str) -> Job:
        payload, _ = await self._transport.request(
            "DELETE", f"/v1/research/{job_id}"
        )
        return Job.model_validate(payload)

    async def usage(self) -> Usage:
        payload, _ = await self._transport.request("GET", "/v1/usage")
        return Usage.model_validate(payload)

    async def research(
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
        job = await self.submit(
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
                await asyncio.sleep(wait)
            wait = min(self._poll_max, wait * 2 if wait > 0 else self._poll_initial)
            job = await self.get_job(job.id)

        if job.status == "completed" and job.result is not None:
            return job.result
        if job.status == "cancelled":
            raise CancelledError(
                code="cancelled",
                message="Job was cancelled before completion.",
                job_id=job.id,
            )
        raise SparkitError(
            code="internal_error",
            message="Job ended in unexpected state.",
            job_id=job.id,
        )
