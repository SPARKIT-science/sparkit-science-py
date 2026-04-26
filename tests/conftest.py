"""Shared test fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def api_key() -> str:
    return "sk_sparkit_test_abc123"


@pytest.fixture
def base_url() -> str:
    return "https://api.example.invalid"


@pytest.fixture
def job_payload_queued() -> dict:
    return {
        "job_id": "job_01HXYZ",
        "status": "queued",
        "created_at": "2026-04-26T15:00:00Z",
        "completed_at": None,
        "progress": {"phase": "routing"},
        "result": None,
    }


@pytest.fixture
def job_payload_completed() -> dict:
    return {
        "job_id": "job_01HXYZ",
        "status": "completed",
        "created_at": "2026-04-26T15:00:00Z",
        "completed_at": "2026-04-26T15:02:00Z",
        "progress": {"phase": "drafting"},
        "result": {
            "answer_text": "## Summary\nBRCA1 plays a central role [1].",
            "answer_letter": None,
            "sources": [
                {
                    "id": 1,
                    "title": "BRCA1 in DNA repair",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/12345",
                    "doi": "10.1038/nature12345",
                    "year": 2024,
                    "citation_count": 47,
                }
            ],
        },
    }


@pytest.fixture
def usage_payload() -> dict:
    return {
        "period_start": "2026-04-01",
        "period_end": "2026-04-30",
        "queries_used": 7,
        "queries_included": 25,
        "overage_queries": 0,
        "estimated_cost_usd": 0.0,
        "plan": "pro",
    }


@pytest.fixture
def webhook_payload(job_payload_completed: dict) -> dict:
    return {"type": "research.completed", "job": job_payload_completed}
