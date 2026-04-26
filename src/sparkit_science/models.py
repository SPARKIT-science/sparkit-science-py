"""Pydantic models for SPARKIT API responses."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
Phase = Literal[
    "routing", "searching", "reading", "thinking", "computing", "drafting"
]
Plan = Literal["try_it", "pro", "max", "enterprise", "none"]
EventType = Literal[
    "research.completed", "research.failed", "research.cancelled"
]


class Source(BaseModel):
    """A cited source returned with a Result."""

    model_config = ConfigDict(extra="ignore")

    id: int
    title: str
    url: str | None = None
    doi: str | None = None
    year: int | None = None
    citation_count: int | None = None


class Result(BaseModel):
    """The structured Markdown report returned for a completed Job."""

    model_config = ConfigDict(extra="ignore")

    answer_text: str
    answer_letter: str | None = None
    sources: list[Source] = Field(default_factory=list)


class Progress(BaseModel):
    """Coarse-grained progress signal for an in-flight Job."""

    model_config = ConfigDict(extra="ignore")

    phase: Phase


class Job(BaseModel):
    """A research job, returned by submit/get_job/cancel_job."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = Field(alias="job_id")
    status: JobStatus
    created_at: datetime
    completed_at: datetime | None = None
    progress: Progress | None = None
    result: Result | None = None

    def __repr__(self) -> str:
        # Deliberately omit `result` from repr — protects the proprietary
        # report contents and prevents accidental log leakage.
        phase = self.progress.phase if self.progress else None
        return (
            f"Job(id={self.id!r}, status={self.status!r}, phase={phase!r})"
        )


class Usage(BaseModel):
    """Customer usage / quota / billing summary for the current period."""

    model_config = ConfigDict(extra="ignore")

    period_start: date
    period_end: date
    queries_used: int
    queries_included: int
    overage_queries: int
    estimated_cost_usd: float
    plan: Plan


class WebhookEvent(BaseModel):
    """Payload delivered to the customer's `callback_url`."""

    model_config = ConfigDict(extra="ignore")

    type: EventType
    job: Job
