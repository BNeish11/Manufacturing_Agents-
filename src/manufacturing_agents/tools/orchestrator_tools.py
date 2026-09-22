"""System-level tools owned by the Orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from manufacturing_agents.permissions.authority import authority_for, require_permission
from manufacturing_agents.state.factory_state import StateOfWorld
from manufacturing_agents.state.models import ApprovalStatus, DecisionRecord, LineStatus


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


def calculate_system_severity(state: StateOfWorld) -> int:
    """Derive a 0-100 severity score from current equipment, safety, material, order, and quality signals."""
    from manufacturing_agents.tools.inventory_tools import inventory_report_for_state

    def read(factory: object) -> float:
        score = 5.0
        for line in factory.production_lines.values():  # type: ignore[attr-defined]
            if line.status is LineStatus.DOWN:
                score += 30.0
            elif line.status in (LineStatus.DEGRADED, LineStatus.QUALITY_HOLD):
                score += 12.0
        if factory.safety.status != "CLEAR":  # type: ignore[attr-defined]
            score += 20.0
        for material in factory.raw_materials.values():  # type: ignore[attr-defined]
            if material.quantity_on_hand <= material.critical_threshold:
                score += 10.0
            elif material.quantity_on_hand <= material.reorder_threshold:
                score += 4.0
        pending = sum(1 for decision in factory.decisions if decision.approval_status.value == "PENDING")  # type: ignore[attr-defined]
        score += pending * 8.0
        return score

    score = state.read(read)
    report = inventory_report_for_state(state)
    at_risk_orders = sum(len(risk["orders"]) for risk in report["risks"])
    score += at_risk_orders * 12.0
    for quality in report["quality"].values():
        if quality["status"] == "CRITICAL":
            score += 10.0
        elif quality["status"] == "WARNING":
            score += 5.0

    return max(0, min(100, round(score)))


def calculate_consequence_cards(state: StateOfWorld) -> list[dict[str, object]]:
    """Derive independent, data-driven consequence dimensions for the dashboard."""
    from manufacturing_agents.tools.inventory_tools import inventory_report_for_state

    def read(factory: object) -> list[dict[str, object]]:
        cards: list[dict[str, object]] = []
        updated_at = factory.updated_at  # type: ignore[attr-defined]

        down_equipment = [e for e in factory.equipment.values() if e.status is LineStatus.DOWN]  # type: ignore[attr-defined]
        degraded_equipment = [e for e in factory.equipment.values() if e.status is LineStatus.DEGRADED]  # type: ignore[attr-defined]
        if down_equipment:
            cause = down_equipment[0].current_fault or "Fault diagnosis unknown"
            cards.append({
                "subject": "EQUIPMENT",
                "status": "CRITICAL",
                "reason": f"{len(down_equipment)} unit(s) down: {', '.join(e.name for e in down_equipment)}.",
                "metric": f"{sum(e.downtime_minutes for e in down_equipment)} min downtime",
                "cause": cause,
                "affected": [e.equipment_id for e in down_equipment],
                "action": "Equipment Agent diagnosing; repair or replacement part required.",
                "updated_at": updated_at,
            })
        elif degraded_equipment:
            cards.append({
                "subject": "EQUIPMENT",
                "status": "WARNING",
                "reason": f"{len(degraded_equipment)} unit(s) showing degraded readings.",
                "metric": f"health score {min(round(e.health_score, 2) for e in degraded_equipment if e.health_score is not None) if any(e.health_score is not None for e in degraded_equipment) else 'n/a'}",
                "cause": "Rising temperature/vibration trend.",
                "affected": [e.equipment_id for e in degraded_equipment],
                "action": "Equipment Agent monitoring for further decline.",
                "updated_at": updated_at,
            })
        else:
            cards.append({
                "subject": "EQUIPMENT", "status": "NORMAL", "reason": "All equipment running normally.",
                "metric": "0 units down", "cause": None, "affected": [], "action": "No action required.",
                "updated_at": updated_at,
            })

        down_lines = [l for l in factory.production_lines.values() if l.status is LineStatus.DOWN]  # type: ignore[attr-defined]
        restricted_lines = [l for l in factory.production_lines.values() if l.status in (LineStatus.DEGRADED, LineStatus.QUALITY_HOLD)]  # type: ignore[attr-defined]
        lost_capacity = sum(l.hourly_capacity for l in down_lines)
        if down_lines:
            cards.append({
                "subject": "PRODUCTION", "status": "CRITICAL",
                "reason": f"{len(down_lines)} line(s) offline: {', '.join(l.name for l in down_lines)}.",
                "metric": f"{lost_capacity} units/hour capacity lost",
                "cause": "Line stoppage.", "affected": [l.line_id for l in down_lines],
                "action": "Production Agent evaluating alternate capacity.", "updated_at": updated_at,
            })
        elif restricted_lines:
            cards.append({
                "subject": "PRODUCTION", "status": "WARNING",
                "reason": f"{len(restricted_lines)} line(s) capacity-restricted.",
                "metric": f"{sum(l.hourly_capacity for l in restricted_lines)} units/hour restricted",
                "cause": "Quality hold or degraded status.", "affected": [l.line_id for l in restricted_lines],
                "action": "Production Agent recalculating schedule.", "updated_at": updated_at,
            })
        else:
            cards.append({
                "subject": "PRODUCTION", "status": "NORMAL", "reason": "All lines producing at expected capacity.",
                "metric": "0 units/hour lost", "cause": None, "affected": [], "action": "No action required.",
                "updated_at": updated_at,
            })

        critical_materials = [m for m in factory.raw_materials.values() if m.quantity_on_hand <= m.critical_threshold]  # type: ignore[attr-defined]
        low_materials = [m for m in factory.raw_materials.values() if m.critical_threshold < m.quantity_on_hand <= m.reorder_threshold]  # type: ignore[attr-defined]
        if critical_materials:
            cards.append({
                "subject": "INVENTORY", "status": "CRITICAL",
                "reason": f"{len(critical_materials)} material(s) at or below critical threshold.",
                "metric": ", ".join(m.material_id for m in critical_materials),
                "cause": "Consumption outpacing replenishment.", "affected": [m.material_id for m in critical_materials],
                "action": "Inventory Agent recommends expedited resupply.", "updated_at": updated_at,
            })
        elif low_materials:
            cards.append({
                "subject": "INVENTORY", "status": "WARNING",
                "reason": f"{len(low_materials)} material(s) below reorder point.",
                "metric": ", ".join(m.material_id for m in low_materials),
                "cause": "Approaching reorder threshold.", "affected": [m.material_id for m in low_materials],
                "action": "Inventory Agent recommends reorder review.", "updated_at": updated_at,
            })
        else:
            cards.append({
                "subject": "INVENTORY", "status": "NORMAL", "reason": "All materials above reorder thresholds.",
                "metric": "0 materials constrained", "cause": None, "affected": [], "action": "No action required.",
                "updated_at": updated_at,
            })

        if factory.safety.status != "CLEAR":  # type: ignore[attr-defined]
            cards.append({
                "subject": "SAFETY", "status": "CRITICAL",
                "reason": f"Safety status is {factory.safety.status}.",  # type: ignore[attr-defined]
                "metric": f"{len(factory.safety.restrictions)} active restriction(s)",  # type: ignore[attr-defined]
                "cause": "Unsafe operating condition detected.",
                "affected": list(factory.safety.restrictions),  # type: ignore[attr-defined]
                "action": "Human intervention required; AI cannot override safety rules.", "updated_at": updated_at,
            })
        else:
            cards.append({
                "subject": "SAFETY", "status": "NORMAL", "reason": "No unsafe conditions detected.",
                "metric": "0 restrictions", "cause": None, "affected": [], "action": "No action required.",
                "updated_at": updated_at,
            })
        return cards

    cards = state.read(read)
    report = inventory_report_for_state(state)

    quality_statuses = [q["status"] for q in report["quality"].values()]
    if "CRITICAL" in quality_statuses:
        quality_status, quality_reason = "CRITICAL", "One or more products exceed the critical defect rate."
    elif "WARNING" in quality_statuses:
        quality_status, quality_reason = "WARNING", "One or more products show an elevated defect rate."
    else:
        quality_status, quality_reason = "NORMAL", "Defect rates within expected range."
    affected_quality = [pid for pid, q in report["quality"].items() if q["status"] in ("CRITICAL", "WARNING")]
    cards.append({
        "subject": "QUALITY", "status": quality_status, "reason": quality_reason,
        "metric": ", ".join(f"{pid}: {q['defect_rate_percent']}%" for pid, q in report["quality"].items() if q["defect_rate_percent"] is not None),
        "cause": "Inspection/production defect trend.", "affected": affected_quality,
        "action": "Inventory Agent monitoring defect rate." if quality_status != "NORMAL" else "No action required.",
        "updated_at": cards[0]["updated_at"] if cards else None,
    })

    at_risk_orders = [order_id for risk in report["risks"] for order_id in risk["orders"]]
    contractual_at_risk = state.read(
        lambda factory: any(  # type: ignore[attr-defined]
            order.order_id in at_risk_orders and order.contractual_delivery
            for order in factory.orders.values()
        )
    )
    if contractual_at_risk:
        customer_status, customer_reason = "CRITICAL", "A contractual order is at risk of missing its delivery date."
    elif at_risk_orders:
        customer_status, customer_reason = "WARNING", "One or more open orders exceed available inventory."
    else:
        customer_status, customer_reason = "NORMAL", "All open orders are covered by available inventory."
    cards.append({
        "subject": "CUSTOMER", "status": customer_status, "reason": customer_reason,
        "metric": f"{len(at_risk_orders)} order(s) at risk", "cause": "Available inventory below order quantity.",
        "affected": at_risk_orders,
        "action": "Orchestrator evaluating alternatives." if customer_status != "NORMAL" else "No action required.",
        "updated_at": cards[0]["updated_at"] if cards else None,
    })

    return cards


def detect_state_conflicts(state: StateOfWorld) -> list[dict[str, object]]:
    """Flag disagreements between equipment status and its production line status."""

    def find(factory: object) -> list[dict[str, object]]:
        conflicts: list[dict[str, object]] = []
        for equipment in factory.equipment.values():  # type: ignore[attr-defined]
            line = factory.production_lines.get(equipment.line_id)  # type: ignore[attr-defined]
            if line is None:
                continue
            equipment_running = equipment.status is LineStatus.RUNNING
            line_running = line.status is LineStatus.RUNNING
            if equipment_running != line_running:
                conflicts.append(
                    {
                        "subject": equipment.line_id,
                        "description": (
                            f"Equipment {equipment.equipment_id} reports {equipment.status.value} "
                            f"while line {line.line_id} reports {line.status.value}."
                        ),
                        "sources": ["equipment status", "production line status"],
                        "severity": "HIGH",
                    }
                )
        return conflicts

    return state.read(find)  # type: ignore[return-value]


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
    required_permission: str | None = None,
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
            required_permission=required_permission,
        )
    )
    return decision_id


def record_human_decision(state: StateOfWorld, decision_id: str, action: str) -> dict[str, object]:
    """Resolve a pending DecisionRecord as APPROVE, REJECT, or HOLD. APPROVE only is permission-gated."""
    if action not in ("APPROVE", "REJECT", "HOLD"):
        raise ValueError(f"Unknown decision action: {action}")

    existing = state.read(
        lambda factory: next((d for d in factory.decisions if d.decision_id == decision_id), None)  # type: ignore[attr-defined]
    )
    if existing is None:
        raise ValueError(f"No decision found with id {decision_id}.")
    if existing.approval_status is not ApprovalStatus.PENDING:
        raise ValueError(f"Decision {decision_id} is already resolved ({existing.approval_status.value}).")

    if action == "APPROVE":
        require_permission(existing.required_permission or "move_production", "orchestrator", human_approved=True)
        new_status = ApprovalStatus.APPROVED
        outcome = "Approved by human reviewer; recovery action authorized."
        final_action = existing.recommendation
    elif action == "REJECT":
        new_status = ApprovalStatus.REJECTED
        outcome = "Rejected by human reviewer; no system action taken."
        final_action = None
    else:
        new_status = ApprovalStatus.ON_HOLD
        outcome = "Held by human reviewer pending further information."
        final_action = None

    def mutate(factory: object) -> None:
        for decision in factory.decisions:  # type: ignore[attr-defined]
            if decision.decision_id == decision_id:
                decision.approval_status = new_status
                decision.human_decision = action
                decision.final_action = final_action
                decision.outcome = outcome
                break

    state.update(mutate)
    return {"decision_id": decision_id, "approval_status": new_status.value, "outcome": outcome}
