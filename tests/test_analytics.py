import sqlite3
from pathlib import Path

from manufacturing_agents.analytics import compute_evaluation_metrics, start_simulation_run, update_simulation_run
from manufacturing_agents.data.database import seed_default_factory
from manufacturing_agents.data.factory_data import create_state_of_world


def test_compute_evaluation_metrics_reports_seeded_downtime_and_state_version() -> None:
    state = create_state_of_world()

    metrics = compute_evaluation_metrics(state)

    assert metrics["state_version"] == state.version
    assert metrics["downtime_minutes"] == 18
    assert metrics["production_loss_units"] == 420 + 2300
    assert metrics["defect_rates"]["C"] > 0
    assert metrics["pending_human_approvals"] == 0


def test_compute_evaluation_metrics_includes_db_backed_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "metrics.db"
    seed_default_factory(db_path)
    state = create_state_of_world()

    metrics = compute_evaluation_metrics(state, db_path)

    assert "simulation_events_logged" in metrics
    assert "defects_logged" in metrics
    assert metrics["defects_logged"] == 0


def test_start_and_update_simulation_run_persists_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "runs.db"
    seed_default_factory(db_path)
    state = create_state_of_world()

    run_id = start_simulation_run(db_path, seed=42, scenario_name="line-2-failure-baseline")
    update_simulation_run(db_path, run_id, tick_count=3, state_version=state.version, metrics={"downtime_minutes": 18})

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT scenario_name, seed, tick_count, final_state_version, metrics_json FROM simulation_runs WHERE id = ?",
            (run_id,),
        ).fetchone()

    assert row is not None
    assert row[0] == "line-2-failure-baseline"
    assert row[1] == 42
    assert row[2] == 3
    assert row[3] == state.version
    assert "downtime_minutes" in row[4]
