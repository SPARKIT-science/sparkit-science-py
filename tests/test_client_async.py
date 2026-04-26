"""Tests for sparkit_science.async_client.AsyncSparkitClient."""

from __future__ import annotations

import httpx
import respx


@respx.mock
async def test_async_submit_returns_job(
    api_key: str, base_url: str, job_payload_queued: dict
) -> None:
    from sparkit_science.async_client import AsyncSparkitClient
    from sparkit_science.models import Job

    respx.post(f"{base_url}/v1/research").respond(200, json=job_payload_queued)
    async with AsyncSparkitClient(api_key=api_key, base_url=base_url) as client:
        job = await client.submit("Q")
    assert isinstance(job, Job)
    assert job.id == "job_01HXYZ"


@respx.mock
async def test_async_get_job_returns_job(
    api_key: str, base_url: str, job_payload_completed: dict
) -> None:
    from sparkit_science.async_client import AsyncSparkitClient

    respx.get(f"{base_url}/v1/research/job_01HXYZ").respond(
        200, json=job_payload_completed
    )
    async with AsyncSparkitClient(api_key=api_key, base_url=base_url) as client:
        job = await client.get_job("job_01HXYZ")
    assert job.status == "completed"


@respx.mock
async def test_async_cancel_job(
    api_key: str, base_url: str, job_payload_queued: dict
) -> None:
    from sparkit_science.async_client import AsyncSparkitClient

    cancelled = {**job_payload_queued, "status": "cancelled"}
    respx.delete(f"{base_url}/v1/research/job_01HXYZ").respond(200, json=cancelled)
    async with AsyncSparkitClient(api_key=api_key, base_url=base_url) as client:
        job = await client.cancel_job("job_01HXYZ")
    assert job.status == "cancelled"


@respx.mock
async def test_async_usage(api_key: str, base_url: str, usage_payload: dict) -> None:
    from sparkit_science.async_client import AsyncSparkitClient

    respx.get(f"{base_url}/v1/usage").respond(200, json=usage_payload)
    async with AsyncSparkitClient(api_key=api_key, base_url=base_url) as client:
        usage = await client.usage()
    assert usage.plan == "pro"


@respx.mock
async def test_async_research_polls_until_completed(
    api_key: str,
    base_url: str,
    job_payload_queued: dict,
    job_payload_completed: dict,
) -> None:
    from sparkit_science.async_client import AsyncSparkitClient

    respx.post(f"{base_url}/v1/research").respond(200, json=job_payload_queued)
    respx.get(f"{base_url}/v1/research/job_01HXYZ").mock(
        side_effect=[
            httpx.Response(200, json=job_payload_queued),
            httpx.Response(200, json=job_payload_completed),
        ]
    )

    async with AsyncSparkitClient(
        api_key=api_key, base_url=base_url, poll_interval=(0.0, 0.0)
    ) as client:
        result = await client.research("Q")
    assert result.answer_text.startswith("## Summary")
