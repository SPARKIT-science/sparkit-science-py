# Changelog

All notable changes to this project will be documented in this file. Format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.1] — 2026-04-26

### Fixed
- `Progress.phase` now accepts `None` so the SDK tolerates the
  `progress: {phase: null}` shape the server returns for freshly-queued
  jobs. Previously `client.submit()` raised `pydantic.ValidationError`
  on every call. Regression tests added.

## [0.1.0] — 2026-04-26

### Added
- Initial public release.
- `SparkitClient` and `AsyncSparkitClient` with `research()`, `submit()`,
  `get_job()`, `cancel_job()`, and `usage()` methods.
- `verify_webhook()` for HMAC-SHA256 webhook signature verification.
- Typed exception hierarchy keyed off the API's stable error codes.
- Pydantic v2 models for `Job`, `Result`, `Source`, `Usage`, `WebhookEvent`.
