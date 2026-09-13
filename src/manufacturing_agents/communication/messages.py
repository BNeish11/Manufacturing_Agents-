"""Versioned messages between specialists, Orchestrator, and human."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from manufacturing_agents.state.factory_state import StateVersionConflict, StateOfWorld


@dataclass(frozen=True)
class AgentMessage:
    sender: str
    receiver: str
    trigger: str
    state_version: int
    facts: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    recommendation: str | None = None
    assumptions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    permission_needed: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def ensure_current(message: AgentMessage, state: StateOfWorld) -> None:
    if message.state_version != state.version:
        raise StateVersionConflict(
            f"Message from {message.sender} uses version {message.state_version}; "
            f"current state is {state.version}. Re-run the analysis."
        )
