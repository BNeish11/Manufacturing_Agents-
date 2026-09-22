"""Simulated factory clock that advances in fixed, deterministic ticks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

DEFAULT_TICK_MINUTES = 5
DEFAULT_START = datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc)


class SimulationClock:
    """Advances simulated time without waiting on real time."""

    def __init__(self, start: datetime | None = None, tick_minutes: int = DEFAULT_TICK_MINUTES) -> None:
        self._current = start or DEFAULT_START
        self._tick_minutes = tick_minutes
        self.tick_count = 0

    @property
    def current_time(self) -> datetime:
        return self._current

    def advance(self) -> datetime:
        self._current += timedelta(minutes=self._tick_minutes)
        self.tick_count += 1
        return self._current
