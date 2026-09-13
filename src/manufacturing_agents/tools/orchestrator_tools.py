"""System-level tools owned by the Orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from manufacturing_agents.permissions.authority import authority_for
from manufacturing_agents.state.factory_state import StateOfWorld
from manufacturing_agents.state.models import ApprovalStatus, DecisionRecord


def get_factory_state(state: StateOfWorld) -> dict[str, object]:
    snapshot = state.snapshot()
    return {
        "version": snapshot.version,
        "factory_name": snapshot.state.factory_name,
        "employee_count": snapshot.state.employee_count,
        "line_status": {
            line_id: line.status.value
            for line_id, line in snapshot.state.production_lines.items()
        },
        "orders": len(snapshot.state.orders),
        "safety": snapshot.state.safety.status,
        "human_intervention_required": snapshot.state.safety.human_intervention_required,
    }


def calculate_system_impact(
    state: StateOfWorld,
    *,
    lost_units: int,
    overtime_hours: float,
    customer_risk: float,
    cost: float,
) -> dict[str, object]:
    return {
        "state_version": state.version,
        "lost_units": lost_units,
        "overtime_hours": overtime_hours,
        "customer_risk_percent": customer_risk,
        "estimated_cost": cost,
        "safety_gate": "BLOCKED" if state.read(lambda factory: factory.safety.restrictions) else "CLEAR",
    }


def calculate_scorecard(state: StateOfWorld) -> dict[str, object]:
    metrics = state.read(lambda factory: factory.scorecard)
    total_weight = sum(metric.weight_percent for metric in metrics)
    if total_weight != 100.0:
        raise ValueError(f"Scorecard weights must total 100%; got {total_weight}.")
    return {
        "total_weight_percent": total_weight,
        "metrics": [vars(metric) for metric in metrics],
    }


def request_human_approval(
    state: StateOfWorld,
    decision: str,
    explanation: str,
) -> dict[str, object]:
    authority = authority_for(decision)
    return {
        "decision": decision,
        "permission": authority.permission.value,
        "explanation": explanation,
        "state_version": state.version,
        "status": ApprovalStatus.PENDING.value,
    }


def record_decision(
    state: StateOfWorld,
    *,
    trigger: str,
    recommendation: str,
    reasoning_summary: str,
    evidence: list[str],
    expected_impact: dict[str, object],
    risks: list[str],
    approval_required: bool,
    approval_status: ApprovalStatus = ApprovalStatus.PENDING,
    human_decision: str | None = None,
    final_action: str | None = None,
    outcome: str | None = None,
) -> str:
    decision_id = f"decision-{uuid4().hex[:8]}"
    state.append_decision(
        DecisionRecord(
            decision_id=decision_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            trigger=trigger,
            state_version=state.version,
            recommendation=recommendation,
            reasoning_summary=reasoning_summary,
            evidence=evidence,
            expected_impact=expected_impact,
            risks=risks,
            approval_required=approval_required,
            approval_status=approval_status,
            human_decision=human_decision,
            final_action=final_action,
            outcome=outcome,
        )
    )
    return decision_id
