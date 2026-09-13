"""Single in-memory source of truth for all agents and tools."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Callable

from .models import DataQuality, FactoryState, StateSnapshot


class StateVersionConflict(RuntimeError):
    """Raised when a mutation was based on an outdated state snapshot."""


class StateOfWorld:
    """Versioned state boundary that can later be backed by a database."""

    def __init__(self, initial_state: FactoryState) -> None:
        self._state = initial_state

    @property
    def version(self) -> int:
        return self._state.version

    def snapshot(self) -> StateSnapshot:
        return StateSnapshot(
            state=deepcopy(self._state),
            version=self._state.version,
            captured_at=datetime.now(timezone.utc).isoformat(),
        )

    def read(self, reader: Callable[[FactoryState], object]) -> object:
        return reader(deepcopy(self._state))

    def update(
        self,
        mutator: Callable[[FactoryState], None],
        *,
        expected_version: int | None = None,
    ) -> int:
        if expected_version is not None and expected_version != self._state.version:
            raise StateVersionConflict(
                f"Expected state version {expected_version}, "
                f"but current version is {self._state.version}."
            )
        next_state = deepcopy(self._state)
        mutator(next_state)
        next_state.version += 1
        next_state.updated_at = datetime.now(timezone.utc).isoformat()
        self._state = next_state
        return next_state.version

    def mark_assumption(self, name: str, quality: DataQuality) -> int:
        return self.update(lambda state: state.assumptions.__setitem__(name, quality))

    def append_decision(self, decision: object) -> int:
        return self.update(lambda state: state.decisions.append(decision))
