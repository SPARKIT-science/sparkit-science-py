"""Python SDK for the SPARKIT scientific research API."""

from sparkit_science._version import __version__
from sparkit_science.exceptions import (
    AuthenticationError,
    CancelledError,
    CostCapExceededError,
    EmbeddedCodeError,
    InternalError,
    InvalidRequestError,
    InvalidSignatureError,
    QuotaExhaustedError,
    RateLimitedError,
    SafetyBlockedError,
    SparkitError,
    TimeoutError,
)
from sparkit_science.models import (
    Job,
    Progress,
    Result,
    Source,
    Usage,
    WebhookEvent,
)

__all__ = [
    "__version__",
    # models
    "Job",
    "Progress",
    "Result",
    "Source",
    "Usage",
    "WebhookEvent",
    # exceptions
    "AuthenticationError",
    "CancelledError",
    "CostCapExceededError",
    "EmbeddedCodeError",
    "InternalError",
    "InvalidRequestError",
    "InvalidSignatureError",
    "QuotaExhaustedError",
    "RateLimitedError",
    "SafetyBlockedError",
    "SparkitError",
    "TimeoutError",
]
