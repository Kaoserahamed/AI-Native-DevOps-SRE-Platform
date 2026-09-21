"""Deterministic test doubles shared by every test tier.

The repository's testing strategy needs one thing above all: determinism. Clocks, sleeping and randomness are
the three sources of flakiness that appear in retry, timeout and budget tests, so they live here as small,
typed doubles that a test drives explicitly instead of patching library internals.

Anything in this package is test-support code: it ships with the platform wheel, is covered by unit tests, and
must never be imported by production paths.
"""

from __future__ import annotations

from packages.test_fixtures.clock import FakeClock, SleepRecorder

__all__ = [
    "FakeClock",
    "SleepRecorder",
]
