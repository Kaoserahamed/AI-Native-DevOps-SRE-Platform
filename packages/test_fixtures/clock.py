"""Controllable time double for retry, timeout and budget tests.

``time.monotonic`` and ``time.sleep`` are the two library calls that make retry logic untestable: a real test
would either sleep for seconds or assert nothing. :class:`FakeClock` is a monotonic clock the test advances by
hand, and :class:`SleepRecorder` records the delays a retry policy asked for without waiting for them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

#: Default instant the fake clock starts at, kept far from any real timer value.
DEFAULT_START_TIME: Final[float] = 1_000.0


@dataclass(slots=True)
class FakeClock:
    """A monotonic clock the test advances explicitly."""

    current: float = DEFAULT_START_TIME

    def __call__(self) -> float:
        """Return the current instant in seconds."""
        return self.current

    def advance(self, seconds: float) -> None:
        """Move the clock forward, for example to simulate time spent inside a call."""
        if seconds < 0.0:
            raise ValueError("a monotonic clock must not move backwards")
        self.current += seconds

    def deadline_in(self, seconds: float) -> float:
        """Return an absolute deadline ``seconds`` from now."""
        return self.current + seconds


@dataclass(slots=True)
class SleepRecorder:
    """Records requested delays instead of sleeping."""

    delays: list[float] = field(default_factory=list)

    def __call__(self, seconds: float) -> None:
        """Record one requested delay."""
        self.delays.append(seconds)

    @property
    def total_seconds(self) -> float:
        """Return the sum of every recorded delay."""
        return sum(self.delays)


__all__ = [
    "DEFAULT_START_TIME",
    "FakeClock",
    "SleepRecorder",
]
