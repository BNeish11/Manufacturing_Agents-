import pytest

from manufacturing_agents.api.runtime import DashboardRuntime
from manufacturing_agents.data.factory_data import create_state_of_world
from manufacturing_agents.orchestration.workflow import run_line_two_failure
from manufacturing_agents.tools.orchestrator_tools import record_human_decision


def test_approve_resolves_decision_through_existing_permission_gate() -> None:
    state = create_state_of_world()
    result = run_line_two_failure(state)
    decision_id = result["decision_id"]

    outcome = record_human_decision(state, decision_id, "APPROVE")

    assert outcome["approval_status"] == "APPROVED"
    resolved = next(d for d in state.snapshot().state.decisions if d.decision_id == decision_id)
    assert resolved.human_decision == "APPROVE"
    assert resolved.final_action == resolved.recommendation


def test_reject_does_not_require_permission_check() -> None:
    state = create_state_of_world()
    result = run_line_two_failure(state)
    decision_id = result["decision_id"]

    outcome = record_human_decision(state, decision_id, "REJECT")

    assert outcome["approval_status"] == "REJECTED"


def test_hold_keeps_decision_open_for_later_review() -> None:
    state = create_state_of_world()
    result = run_line_two_failure(state)
    decision_id = result["decision_id"]

    outcome = record_human_decision(state, decision_id, "HOLD")

    assert outcome["approval_status"] == "ON_HOLD"


def test_cannot_resolve_an_already_resolved_decision() -> None:
    state = create_state_of_world()
    result = run_line_two_failure(state)
    decision_id = result["decision_id"]
    record_human_decision(state, decision_id, "REJECT")

    with pytest.raises(ValueError):
        record_human_decision(state, decision_id, "APPROVE")


def test_unknown_decision_id_is_rejected() -> None:
    state = create_state_of_world()

    with pytest.raises(ValueError):
        record_human_decision(state, "decision-does-not-exist", "APPROVE")


def test_runtime_submit_decision_updates_dashboard_and_agent_status() -> None:
    runtime = DashboardRuntime()
    result = runtime.run_failure()
    decision_id = result["decisions"][-1]["decision_id"]
    assert result["agent_status"]["orchestrator"] == "NEEDS_HUMAN_APPROVAL"

    updated = runtime.submit_decision(decision_id, "APPROVE")

    assert updated["decisions"][-1]["approval_status"] == "APPROVED"
    assert updated["agent_status"]["orchestrator"] == "COMPLETED"
    assert any(event["event_type"] == "human_decision_recorded" for event in updated["events"])
