import pytest

from manufacturing_agents.data.factory_data import create_state_of_world
from manufacturing_agents.permissions.authority import AuthorizationError
from manufacturing_agents.tools.production_tools import (
    calculate_production_loss,
    simulate_schedule_change,
    update_production_plan,
)


def test_production_loss_uses_line_capacity() -> None:
    state = create_state_of_world()
    assert calculate_production_loss(state, "line-2", 60) == 220


def test_quality_hold_blocks_schedule_simulation() -> None:
    state = create_state_of_world()
    state.update(lambda factory: setattr(factory.production_lines["line-3"], "quality_hold", True))

    result = simulate_schedule_change(state, "C", "line-3", 100)

    assert result["feasible"] is False
    assert "quality hold" in str(result["reason"])


def test_production_agent_cannot_execute_system_level_move_without_approval() -> None:
    state = create_state_of_world()

    with pytest.raises(AuthorizationError):
        update_production_plan(state, "B", "line-3", 100, actor="production")
