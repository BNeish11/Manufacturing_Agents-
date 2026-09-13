"""Safe, bounded dashboard events."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class DashboardEvent:
    event_id: str
    event_type: str
    actor: str
    state_version: int
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventJournal:
    def __init__(self, limit: int = 100) -> None:
        self._limit = limit
        self._events: list[DashboardEvent] = []

    def add(self, event_type: str, actor: str, state_version: int, summary: str, **metadata: Any) -> DashboardEvent:
        event = DashboardEvent(
            event_id=f"event-{uuid4().hex[:8]}",
            event_type=event_type,
            actor=actor,
            state_version=state_version,
            summary=summary,
            metadata=metadata,
        )
        self._events.append(event)
        del self._events[:-self._limit]
        return event

    def clear(self) -> None:
        self._events.clear()

    def as_dicts(self) -> list[dict[str, Any]]:
        return [asdict(event) for event in reversed(self._events)]