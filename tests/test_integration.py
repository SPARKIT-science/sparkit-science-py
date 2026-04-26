"""Integration test against prod, gated on SPARKIT_API_KEY env.

Runs locally for manual verification; skipped in CI by default. Does NOT
exercise research() (which would actually run a paid query). Verifies the
submit -> cancel -> usage round trip.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    "SPARKIT_API_KEY" not in os.environ,
    reason="SPARKIT_API_KEY not set; integration test skipped.",
)


def test_submit_cancel_usage_round_trip() -> None:
    from sparkit_science import SparkitClient
    from sparkit_science.models import Job, Usage

    api_key = os.environ["SPARKIT_API_KEY"]
    with SparkitClient(api_key=api_key) as client:
        # Submit a trivially short question; immediately cancel it so we
        # don't burn a query credit.
        job = client.submit("ping")
        assert isinstance(job, Job)

        cancelled = client.cancel_job(job.id)
        assert cancelled.status == "cancelled"

        usage = client.usage()
        assert isinstance(usage, Usage)
        assert usage.plan in {"try_it", "pro", "max", "enterprise", "none"}
