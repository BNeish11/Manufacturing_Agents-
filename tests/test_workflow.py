from manufacturing_agents.data.factory_data import create_state_of_world
from manufacturing_agents.orchestration.workflow import run_line_two_failure
from manufacturing_agents.scenarios.updates import line_three_quality_update, product_c_priority_update, specialized_part_update
from manufacturing_agents.state.models import LineStatus


def test_line_two_workflow_creates_pending_human_decision() -> None:
    state = create_state_of_world()
    result = run_line_two_failure(state)

    assert result["approval"]["status"] == "PENDING"
    assert result["decision_id"].startswith("decision-")
    assert result["impact"]["lost_units"] == 2300
    assert state.snapshot().state.decisions[-1].approval_required is True


def test_updates_mutate_one_shared_state_and_mark_assumptions() -> None:
    state = create_state_of_world()
    specialized_part_update(state)
    product_c_priority_update(state)
    line_three_quality_update(state)
    snapshot = state.snapshot().state

    assert snapshot.materials["part-line-2-special"].expedited_cost_multiplier == 10.0
    assert snapshot.orders["order-c"].priority == "HIGH"
    assert snapshot.production_lines["line-3"].status is LineStatus.QUALITY_HOLD
    assert snapshot.production_lines["line-3"].quality_hold is True
