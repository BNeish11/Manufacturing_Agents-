import pytest

from manufacturing_agents.data.factory_data import create_state_of_world
from manufacturing_agents.tools.inventory_tools import (
    calculate_defect_rate,
    calculate_max_production,
    calculate_material_requirements,
    get_finished_goods,
    record_human_inspection,
)


def test_material_limit_uses_all_required_materials() -> None:
    state = create_state_of_world()

    result = calculate_max_production(state, "C")

    assert result["available"] is True
    assert result["maximum_supported_quantity"] == 1388
    assert result["limiting_material"] == "liner-board"


def test_reserved_finished_goods_are_not_available() -> None:
    state = create_state_of_world()

    result = get_finished_goods(state, "C")["C"]

    assert result["finished_goods"] == 300
    assert result["reserved"] == 60
    assert result["available"] == 240


def test_quality_rate_is_deterministic_and_human_observation_is_recorded() -> None:
    state = create_state_of_world()
    before = state.version

    assert calculate_defect_rate(state, "C")["status"] == "WARNING"
    record_human_inspection(state, "C", "Crushed corner", "MINOR", 1)

    assert state.version == before + 1
    assert state.snapshot().state.human_inspections[-1].source == "HUMAN_PROVIDED"


def test_negative_inventory_calculation_is_rejected_without_state_change() -> None:
    state = create_state_of_world()
    version = state.version

    with pytest.raises(ValueError):
        calculate_material_requirements(state, "C", -1)

    assert state.version == version