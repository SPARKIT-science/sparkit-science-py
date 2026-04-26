"""Tests for sparkit_science._http retry + error-mapping behavior."""

from __future__ import annotations

import httpx
import pytest
import respx


@pytest.fixture
def base_url() -> str:
    return "https://api.example.invalid"


@respx.mock
def test_request_succeeds_on_first_try(base_url: str) -> None:
    from sparkit_science._http import HttpTransport

    route = respx.get(f"{base_url}/v1/usage").respond(
        200, json={"plan": "pro"}, headers={"X-Request-ID": "req_1"}
    )
    transport = HttpTransport(
        api_key="sk_test", base_url=base_url, max_retries=3
    )
    payload, request_id = transport.request("GET", "/v1/usage")
    assert payload == {"plan": "pro"}
    assert request_id == "req_1"
    assert route.call_count == 1


@respx.mock
def test_5xx_triggers_retry_then_succeeds(base_url: str) -> None:
    from sparkit_science._http import HttpTransport

    route = respx.get(f"{base_url}/v1/usage").mock(
        side_effect=[
            httpx.Response(503, json={"error": {"code": "internal_error", "message": "x"}}),
            httpx.Response(200, json={"plan": "pro"}),
        ]
    )
    transport = HttpTransport(
        api_key="sk_test",
        base_url=base_url,
        max_retries=3,
        retry_initial_backoff=0.0,  # no actual sleep in tests
    )
    payload, _ = transport.request("GET", "/v1/usage")
    assert payload == {"plan": "pro"}
    assert route.call_count == 2


@respx.mock
def test_429_honors_retry_after_header(base_url: str) -> None:
    from sparkit_science._http import HttpTransport

    route = respx.get(f"{base_url}/v1/usage").mock(
        side_effect=[
            httpx.Response(
                429,
                headers={"Retry-After": "0"},
                json={"error": {"code": "rate_limited", "message": "x"}},
            ),
            httpx.Response(200, json={"plan": "pro"}),
        ]
    )
    transport = HttpTransport(
        api_key="sk_test",
        base_url=base_url,
        max_retries=3,
        retry_initial_backoff=0.0,
    )
    payload, _ = transport.request("GET", "/v1/usage")
    assert payload == {"plan": "pro"}
    assert route.call_count == 2


@respx.mock
def test_4xx_other_than_429_does_not_retry(base_url: str) -> None:
    from sparkit_science._http import HttpTransport
    from sparkit_science.exceptions import InvalidRequestError

    route = respx.get(f"{base_url}/v1/usage").respond(
        400,
        json={"error": {"code": "invalid_request", "message": "bad"}},
    )
    transport = HttpTransport(
        api_key="sk_test", base_url=base_url, max_retries=3
    )
    with pytest.raises(InvalidRequestError):
        transport.request("GET", "/v1/usage")
    assert route.call_count == 1


@respx.mock
def test_max_retries_exhaustion_raises_last_error(base_url: str) -> None:
    from sparkit_science._http import HttpTransport
    from sparkit_science.exceptions import InternalError

    respx.get(f"{base_url}/v1/usage").respond(
        500, json={"error": {"code": "internal_error", "message": "boom"}}
    )
    transport = HttpTransport(
        api_key="sk_test",
        base_url=base_url,
        max_retries=2,
        retry_initial_backoff=0.0,
    )
    with pytest.raises(InternalError):
        transport.request("GET", "/v1/usage")


@respx.mock
def test_idempotency_key_is_reused_across_retries(base_url: str) -> None:
    from sparkit_science._http import HttpTransport

    seen_keys: list[str] = []

    def callback(request: httpx.Request) -> httpx.Response:
        seen_keys.append(request.headers["Idempotency-Key"])
        if len(seen_keys) == 1:
            return httpx.Response(503, json={"error": {"code": "internal_error", "message": "x"}})
        return httpx.Response(200, json={"job_id": "j", "status": "queued",
                                          "created_at": "2026-04-26T00:00:00Z"})

    respx.post(f"{base_url}/v1/research").mock(side_effect=callback)
    transport = HttpTransport(
        api_key="sk_test",
        base_url=base_url,
        max_retries=3,
        retry_initial_backoff=0.0,
    )
    transport.request(
        "POST",
        "/v1/research",
        json_body={"question": "x"},
        idempotency_key="my-key",
    )
    assert seen_keys == ["my-key", "my-key"]


@respx.mock
def test_authorization_header_is_sent(base_url: str) -> None:
    from sparkit_science._http import HttpTransport

    captured: dict[str, str] = {}

    def callback(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization", "")
        return httpx.Response(200, json={})

    respx.get(f"{base_url}/v1/usage").mock(side_effect=callback)
    transport = HttpTransport(api_key="sk_test", base_url=base_url)
    transport.request("GET", "/v1/usage")
    assert captured["auth"] == "Bearer sk_test"


@respx.mock
def test_user_agent_header_includes_version(base_url: str) -> None:
    from sparkit_science import __version__
    from sparkit_science._http import HttpTransport

    captured: dict[str, str] = {}

    def callback(request: httpx.Request) -> httpx.Response:
        captured["ua"] = request.headers.get("user-agent", "")
        return httpx.Response(200, json={})

    respx.get(f"{base_url}/v1/usage").mock(side_effect=callback)
    transport = HttpTransport(api_key="sk_test", base_url=base_url)
    transport.request("GET", "/v1/usage")
    assert f"sparkit-science-py/{__version__}" in captured["ua"]
