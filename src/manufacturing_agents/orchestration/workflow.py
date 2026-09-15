"""Offline and live coordination flows for the Line 2 failure scenario."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from agents import Runner

from manufacturing_agents.agents.orchestrator import build_orchestrator_agent
from manufacturing_agents.communication.messages import AgentMessage
from manufacturing_agents.data.factory_data import create_state_of_world
from manufacturing_agents.state.factory_state import StateOfWorld
from manufacturing_agents.state.models import ApprovalStatus, LineStatus
from manufacturing_agents.tools.equipment_tools import (
    check_replacement_part,
    get_fault_information,
    get_machine_status,
    estimate_repair_time,
)
from manufacturing_agents.tools.inventory_tools import inventory_report_for_state
from manufacturing_agents.tools.orchestrator_tools import (
    calculate_scorecard,
    calculate_system_impact,
    record_decision,
    request_human_approval,
)
from manufacturing_agents.tools.production_tools import (
    calculate_delivery_impact,
    calculate_overtime_requirement,
    calculate_production_loss,
    get_inventory_status,
    get_production_status,
    simulate_schedule_change,
)


def run_line_two_failure(
    state: StateOfWorld | None = None,
    *,
    human_approved: bool = False,
) -> dict[str, Any]:
    """Run a deterministic, explainable baseline without an API call."""
    state = state or create_state_of_world()
    initial_version = state.version
    fault = get_fault_information(state, "equipment-2")
    machine = get_machine_status(state, "equipment-2")
    repair_minutes = estimate_repair_time(state, "equipment-2") or 0
    lost_units = calculate_production_loss(state, "line-2", machine.downtime_minutes)
    calculated_projection = calculate_production_loss(state, "line-2", repair_minutes)
    projected_loss = machine.projected_lost_units or calculated_projection
    inventory = get_inventory_status(state)
    production = get_production_status(state)
    part = check_replacement_part(state, "part-line-2-special")
    delivery = calculate_delivery_impact(state, "A", projected_loss)
    overtime_hours = calculate_overtime_requirement(state, projected_loss, "line-1")
    alternative = simulate_schedule_change(state, "A", "line-1", projected_loss)
    inventory_report = inventory_report_for_state(state)

    evidence = [
        f"Line 2 status is {machine.status.value} with {machine.downtime_minutes} minutes downtime.",
        f"Observed fault data quality is {fault['data_quality']}.",
        f"Current loss is {machine.lost_units or lost_units} units; projected loss is {projected_loss} units.",
        f"Finished goods inventory is {sum(inventory['finished_goods'].values())} units.",
        f"Line 1 utilization is {production['line-1']['utilization_percent']}%.",
        f"Line 2 specialized part available: {part['available']}.",
        f"Inventory supports {inventory_report['supported_production']['C']['maximum_supported_quantity']} additional Product C units.",
    ]
    risks = [
        "Fault diagnosis is unknown and requires equipment investigation.",
        "Moving production affects labor, cost, and Product A delivery risk.",
        "Human approval is required for production movement and overtime.",
    ]
    recommendation = "Investigate Line 2 and prepare a human-approved recovery plan; do not move production automatically."
    if alternative["feasible"]:
        recommendation += " Line 1 is a feasible simulated alternative pending capacity and approval review."

    impact = calculate_system_impact(
        state,
        lost_units=projected_loss,
        overtime_hours=overtime_hours,
        customer_risk=100.0 if delivery["affected_orders"] else 0.0,
        cost=0.0,
    )
    scorecard = calculate_scorecard(state)
    approval = request_human_approval(
        state,
        "move_production",
        "Line 2 failure affects capacity and customer commitments; review alternatives and overtime.",
    )
    approval_status = ApprovalStatus.APPROVED if human_approved else ApprovalStatus.PENDING
    decision_id = record_decision(
        state,
        trigger="Line 2 failure",
        recommendation=recommendation,
        reasoning_summary="The available evidence supports analysis and preparation, but not an automatic system-level action.",
        evidence=evidence,
        expected_impact=impact,
        risks=risks,
        approval_required=True,
        approval_status=approval_status,
        human_decision="APPROVED" if human_approved else None,
        final_action="Recovery plan approved for execution" if human_approved else None,
        outcome="Pending human approval" if not human_approved else "Approved action recorded",
    )
    message = AgentMessage(
        sender="Orchestrator Agent",
        receiver="Human Plant Manager",
        trigger="Line 2 failure",
        state_version=initial_version,
        facts=evidence,
        evidence=["Shared State of the World", "Equipment tools", "Production tools"],
        recommendation=recommendation,
        risks=risks,
        permission_needed=approval["permission"],
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    return {
        "decision_id": decision_id,
        "state_version": state.version,
        "recommendation": recommendation,
        "evidence": evidence,
        "risks": risks,
        "inventory_report": inventory_report,
        "impact": impact,
        "scorecard": scorecard,
        "approval": approval,
        "message": message,
    }


async def run_live_orchestrator(state: StateOfWorld, event: str) -> Any:
    """Run the SDK Orchestrator; credentials and model access are required."""
    agent = build_orchestrator_agent(state)
    return await Runner.run(agent, event)
