from manufacturing_agents.data.factory_data import create_state_of_world
from manufacturing_agents.scenarios.updates import line_three_quality_update, product_c_priority_update, specialized_part_update


def test_part_update_supports_normal_and_expedited_delivery_facts() -> None:
    state = create_state_of_world()
    specialized_part_update(state)
    part = state.snapshot().state.materials["part-line-2-special"]

    assert part.normal_delivery_days == 5
    assert part.expedited_delivery == "tomorrow 10:00 AM"
    assert part.expedited_cost_multiplier == 10.0


def test_product_c_update_changes_inventory_and_priority() -> None:
    state = create_state_of_world()
    product_c_priority_update(state)
    snapshot = state.snapshot().state

    assert snapshot.inventory.finished_goods["C"] == 100
    assert snapshot.orders["order-c"].priority == "HIGH"


def test_line_three_quality_update_blocks_line_three() -> None:
    state = create_state_of_world()
    line_three_quality_update(state)
    line = state.snapshot().state.production_lines["line-3"]

    assert line.quality_hold is True
    assert line.status.value == "QUALITY_HOLD"
