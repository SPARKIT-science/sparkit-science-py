"""Tests for sparkit_science.models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_source_parses_full_payload() -> None:
    from sparkit_science.models import Source

    src = Source.model_validate(
        {
            "id": 1,
            "title": "BRCA1 in DNA repair",
            "url": "https://pubmed.ncbi.nlm.nih.gov/12345",
            "doi": "10.1038/nature12345",
            "year": 2024,
            "citation_count": 47,
        }
    )
    assert src.id == 1
    assert src.title == "BRCA1 in DNA repair"
    assert src.year == 2024


def test_source_allows_optional_fields_missing() -> None:
    from sparkit_science.models import Source

    src = Source.model_validate({"id": 2, "title": "X"})
    assert src.url is None
    assert src.doi is None
    assert src.year is None
    assert src.citation_count is None


def test_result_parses_payload_with_sources() -> None:
    from sparkit_science.models import Result

    result = Result.model_validate(
        {
            "answer_text": "## Summary\n[1]",
            "answer_letter": "B",
            "sources": [{"id": 1, "title": "X"}],
        }
    )
    assert result.answer_letter == "B"
    assert len(result.sources) == 1
    assert result.sources[0].id == 1


def test_result_defaults_sources_to_empty() -> None:
    from sparkit_science.models import Result

    result = Result.model_validate({"answer_text": "x"})
    assert result.sources == []


def test_progress_phase_is_validated() -> None:
    from sparkit_science.models import Progress

    p = Progress.model_validate({"phase": "searching"})
    assert p.phase == "searching"

    with pytest.raises(ValidationError):
        Progress.model_validate({"phase": "exploding"})


def test_progress_accepts_null_phase_for_queued_jobs() -> None:
    """The server sends `progress: {phase: null}` for freshly-queued jobs."""
    from sparkit_science.models import Progress

    p = Progress.model_validate({"phase": None})
    assert p.phase is None


def test_job_with_null_progress_phase_parses() -> None:
    """Regression: queued jobs from prod return progress.phase = null and
    must round-trip through Job without a ValidationError."""
    from sparkit_science.models import Job

    job = Job.model_validate(
        {
            "job_id": "job_queued_x",
            "status": "queued",
            "created_at": "2026-04-26T15:00:00Z",
            "completed_at": None,
            "progress": {"phase": None},
            "result": None,
        }
    )
    assert job.status == "queued"
    assert job.progress is not None
    assert job.progress.phase is None


def test_job_aliases_job_id_to_id(job_payload_queued: dict) -> None:
    from sparkit_science.models import Job

    job = Job.model_validate(job_payload_queued)
    assert job.id == "job_01HXYZ"
    assert job.status == "queued"
    assert job.completed_at is None


def test_job_completed_includes_result(job_payload_completed: dict) -> None:
    from sparkit_science.models import Job

    job = Job.model_validate(job_payload_completed)
    assert job.status == "completed"
    assert job.result is not None
    assert job.result.answer_text.startswith("## Summary")


def test_job_repr_does_not_include_result(job_payload_completed: dict) -> None:
    from sparkit_science.models import Job

    job = Job.model_validate(job_payload_completed)
    text = repr(job)
    # The full report MUST NOT appear in repr.
    assert "BRCA1 plays a central role" not in text
    # Identification fields SHOULD appear.
    assert "job_01HXYZ" in text
    assert "completed" in text


def test_usage_parses_payload(usage_payload: dict) -> None:
    from sparkit_science.models import Usage

    u = Usage.model_validate(usage_payload)
    assert u.queries_used == 7
    assert u.plan == "pro"


def test_webhook_event_parses_payload(webhook_payload: dict) -> None:
    from sparkit_science.models import WebhookEvent

    event = WebhookEvent.model_validate(webhook_payload)
    assert event.type == "research.completed"
    assert event.job.status == "completed"
