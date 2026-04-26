"""Tests for sparkit_science.client.SparkitClient (sync)."""

from __future__ import annotations

import httpx
import pytest
import respx


def test_client_reads_api_key_from_constructor(api_key: str, base_url: str) -> None:
    from sparkit_science.client import SparkitClient

    client = SparkitClient(api_key=api_key, base_url=base_url)
    # Round-trip through internal: header is set on requests, not exposed.
    assert client._transport._api_key == api_key  # type: ignore[attr-defined]


def test_client_reads_api_key_from_env(
    monkeypatch: pytest.MonkeyPatch, base_url: str
) -> None:
    from sparkit_science.client import SparkitClient

    monkeypatch.setenv("SPARKIT_API_KEY", "sk_env")
    client = SparkitClient(base_url=base_url)
    assert client._transport._api_key == "sk_env"  # type: ignore[attr-defined]


def test_client_raises_without_api_key(
    monkeypatch: pytest.MonkeyPatch, base_url: str
) -> None:
    from sparkit_science.client import SparkitClient

    monkeypatch.delenv("SPARKIT_API_KEY", raising=False)
    with pytest.raises(ValueError, match="api_key"):
        SparkitClient(base_url=base_url)


@respx.mock
def test_submit_returns_job(api_key: str, base_url: str, job_payload_queued: dict) -> None:
    from sparkit_science.client import SparkitClient
    from sparkit_science.models import Job

    respx.post(f"{base_url}/v1/research").respond(200, json=job_payload_queued)
    with SparkitClient(api_key=api_key, base_url=base_url) as client:
        job = client.submit("What is BRCA1?")
    assert isinstance(job, Job)
    assert job.id == "job_01HXYZ"
    assert job.status == "queued"


@respx.mock
def test_submit_passes_options_through(
    api_key: str, base_url: str, job_payload_queued: dict
) -> None:
    from sparkit_science.client import SparkitClient

    captured: dict[str, object] = {}

    def callback(request: httpx.Request) -> httpx.Response:
        import json
        captured["body"] = json.loads(request.content)
        captured["idem"] = request.headers.get("idempotency-key")
        return httpx.Response(200, json=job_payload_queued)

    respx.post(f"{base_url}/v1/research").mock(side_effect=callback)
    with SparkitClient(api_key=api_key, base_url=base_url) as client:
        client.submit(
            "Q",
            callback_url="https://x.example/cb",
            max_cost_usd=2.0,
            response_format="brief",
            include_citations=False,
            metadata={"user_id": "u1"},
            idempotency_key="my-key",
        )
    body = captured["body"]
    assert body == {  # type: ignore[comparison-overlap]
        "question": "Q",
        "callback_url": "https://x.example/cb",
        "max_cost_usd": 2.0,
        "response_format": "brief",
        "include_citations": False,
        "metadata": {"user_id": "u1"},
    }
    assert captured["idem"] == "my-key"


@respx.mock
def test_get_job_returns_job(
    api_key: str, base_url: str, job_payload_completed: dict
) -> None:
    from sparkit_science.client import SparkitClient

    respx.get(f"{base_url}/v1/research/job_01HXYZ").respond(
        200, json=job_payload_completed
    )
    with SparkitClient(api_key=api_key, base_url=base_url) as client:
        job = client.get_job("job_01HXYZ")
    assert job.status == "completed"
    assert job.result is not None


@respx.mock
def test_cancel_job_returns_job(
    api_key: str, base_url: str, job_payload_queued: dict
) -> None:
    from sparkit_science.client import SparkitClient

    cancelled = {**job_payload_queued, "status": "cancelled"}
    respx.delete(f"{base_url}/v1/research/job_01HXYZ").respond(200, json=cancelled)
    with SparkitClient(api_key=api_key, base_url=base_url) as client:
        job = client.cancel_job("job_01HXYZ")
    assert job.status == "cancelled"


@respx.mock
def test_usage_returns_usage(api_key: str, base_url: str, usage_payload: dict) -> None:
    from sparkit_science.client import SparkitClient

    respx.get(f"{base_url}/v1/usage").respond(200, json=usage_payload)
    with SparkitClient(api_key=api_key, base_url=base_url) as client:
        usage = client.usage()
    assert usage.queries_used == 7
    assert usage.plan == "pro"


@respx.mock
def test_research_polls_until_completed(
    api_key: str,
    base_url: str,
    job_payload_queued: dict,
    job_payload_completed: dict,
) -> None:
    from sparkit_science.client import SparkitClient

    respx.post(f"{base_url}/v1/research").respond(200, json=job_payload_queued)
    respx.get(f"{base_url}/v1/research/job_01HXYZ").mock(
        side_effect=[
            httpx.Response(200, json=job_payload_queued),
            httpx.Response(200, json={**job_payload_queued, "status": "running"}),
            httpx.Response(200, json=job_payload_completed),
        ]
    )

    with SparkitClient(
        api_key=api_key, base_url=base_url, poll_interval=(0.0, 0.0)
    ) as client:
        result = client.research("Q")
    assert result.answer_text.startswith("## Summary")


@respx.mock
def test_research_raises_typed_exception_on_failed(
    api_key: str, base_url: str, job_payload_queued: dict
) -> None:
    from sparkit_science.client import SparkitClient
    from sparkit_science.exceptions import SafetyBlockedError

    failed = {
        **job_payload_queued,
        "status": "failed",
        "result": None,
    }
    respx.post(f"{base_url}/v1/research").respond(200, json=job_payload_queued)
    respx.get(f"{base_url}/v1/research/job_01HXYZ").respond(
        200,
        json={
            **failed,
            "error": {"code": "safety_blocked", "message": "no", "job_id": "job_01HXYZ"},
        },
    )

    with SparkitClient(
        api_key=api_key, base_url=base_url, poll_interval=(0.0, 0.0)
    ) as client, pytest.raises(SafetyBlockedError) as exc_info:
        client.research("Q")
    assert exc_info.value.job_id == "job_01HXYZ"


@respx.mock
def test_research_raises_cancelled_when_status_cancelled(
    api_key: str, base_url: str, job_payload_queued: dict
) -> None:
    from sparkit_science.client import SparkitClient
    from sparkit_science.exceptions import CancelledError

    cancelled = {**job_payload_queued, "status": "cancelled"}
    respx.post(f"{base_url}/v1/research").respond(200, json=job_payload_queued)
    respx.get(f"{base_url}/v1/research/job_01HXYZ").respond(200, json=cancelled)

    with SparkitClient(
        api_key=api_key, base_url=base_url, poll_interval=(0.0, 0.0)
    ) as client, pytest.raises(CancelledError):
        client.research("Q")
