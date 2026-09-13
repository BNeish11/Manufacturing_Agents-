from manufacturing_agents.data.factory_data import create_state_of_world
from manufacturing_agents.state.factory_state import StateVersionConflict
from manufacturing_agents.state.models import DataQuality, LineStatus


def test_seed_matches_line_two_failure_scenario() -> None:
    state = create_state_of_world()
    snapshot = state.snapshot()

    assert snapshot.state.employee_count == 125
    assert snapshot.state.production_lines["line-2"].status is LineStatus.DOWN
    assert snapshot.state.equipment["equipment-2"].downtime_minutes == 18
    assert snapshot.state.equipment["equipment-2"].lost_units == 420
    assert snapshot.state.equipment["equipment-2"].projected_lost_units == 2300
    assert snapshot.state.system_severity == 72
    assert snapshot.state.affected_employee_count == 12
    assert snapshot.state.reassigned_employee_count == 4
    assert snapshot.state.production_lines["line-1"].utilization_percent == 63.0
    assert snapshot.state.production_lines["line-3"].utilization_percent == 81.0
    assert snapshot.state.inventory.finished_goods["A"] == 1000
    assert snapshot.state.inventory.work_in_progress["A"] == 300
    assert len(snapshot.state.employees) == 125
    assert snapshot.state.assumptions["line-2-fault-diagnosis"] is DataQuality.UNKNOWN


def test_updates_are_versioned_and_snapshots_are_isolated() -> None:
    state = create_state_of_world()
    original = state.snapshot()

    state.update(
        lambda factory: setattr(
            factory.production_lines["line-2"], "status", LineStatus.DEGRADED
        ),
        expected_version=original.version,
    )

    assert state.version == original.version + 1
    assert original.state.production_lines["line-2"].status is LineStatus.DOWN
    assert state.snapshot().state.production_lines["line-2"].status is LineStatus.DEGRADED


def test_stale_mutation_is_rejected() -> None:
    state = create_state_of_world()
    snapshot = state.snapshot()
    state.mark_assumption("new-fact", DataQuality.SIMULATED)

    try:
        state.update(lambda _: None, expected_version=snapshot.version)
    except StateVersionConflict:
        pass
    else:
        raise AssertionError("stale state mutation should be rejected")
