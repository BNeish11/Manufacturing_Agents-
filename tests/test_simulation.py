import sqlite3
from pathlib import Path

from manufacturing_agents.data.database import seed_default_factory
from manufacturing_agents.data.factory_data import create_state_of_world
from manufacturing_agents.simulation.engine import SimulationEngine


def _event_type_trace(results: list[dict[str, object]]) -> list[list[str]]:
    return [[event["event_type"] for event in tick["applied_events"]] for tick in results]


def test_same_seed_produces_same_event_sequence() -> None:
    state_a = create_state_of_world()
    engine_a = SimulationEngine(state_a, seed=42)
    result_a = engine_a.run(10)

    state_b = create_state_of_world()
    engine_b = SimulationEngine(state_b, seed=42)
    result_b = engine_b.run(10)

    assert _event_type_trace(result_a) == _event_type_trace(result_b)
    assert state_a.version == state_b.version
    assert result_a[-1]["tick"] == 10


def test_different_seed_can_diverge() -> None:
    state_a = create_state_of_world()
    result_a = SimulationEngine(state_a, seed=1).run(10)

    state_b = create_state_of_world()
    result_b = SimulationEngine(state_b, seed=2).run(10)

    assert _event_type_trace(result_a) != _event_type_trace(result_b)


def test_tick_mutates_the_same_shared_state_object() -> None:
    state = create_state_of_world()
    initial_version = state.version
    engine = SimulationEngine(state, seed=42)

    engine.run(5)

    assert state.version > initial_version
    assert engine.state is state


def test_simulation_persists_tick_and_state_version(tmp_path: Path) -> None:
    db_path = tmp_path / "sim.db"
    seed_default_factory(db_path)
    state = create_state_of_world()
    engine = SimulationEngine(state, db_path=db_path, seed=42)

    engine.tick()
    engine.tick()

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT tick, state_version, random_seed FROM simulation_state LIMIT 1").fetchone()
        assert row is not None
        assert row[0] == 2
        assert row[1] == state.version
        assert row[2] == 42

        event_count = conn.execute("SELECT COUNT(*) FROM simulation_events").fetchone()[0]
        assert event_count >= 0
