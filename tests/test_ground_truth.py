import sqlite3
from pathlib import Path

from manufacturing_agents.data.database import seed_default_factory
from manufacturing_agents.data.factory_data import create_state_of_world
from manufacturing_agents.simulation.engine import SimulationEngine, SimulationEvent
from manufacturing_agents.simulation.events import equipment_degradation, product_defect, quality_anomaly
from manufacturing_agents.simulation.ground_truth import GroundTruthStore
from manufacturing_agents.state.models import LineStatus
from manufacturing_agents.tools.equipment_tools import investigate_equipment_fault
from manufacturing_agents.tools.inventory_tools import calculate_weight_variance, record_defect
from manufacturing_agents.tools.orchestrator_tools import detect_state_conflicts


def test_ground_truth_is_never_exposed_on_agent_visible_equipment() -> None:
    state = create_state_of_world()
    equipment = state.snapshot().state.equipment["equipment-2"]

    assert not hasattr(equipment, "actual_fault")
    assert not hasattr(equipment, "actual_repair_minutes")
    assert equipment.current_fault is None  # Agents see unknown fault, not the hidden ground truth.


def test_ground_truth_store_matches_seeded_line_two_scenario() -> None:
    ground_truth = GroundTruthStore()
    fact = ground_truth.get("equipment-2")

    assert fact is not None
    assert fact.actual_fault == "bearing failure"
    assert fact.actual_repair_minutes == 137


def test_investigate_equipment_fault_is_deterministic_and_symptom_based() -> None:
    state = create_state_of_world()
    state.update(
        lambda factory: (
            setattr(factory.equipment["equipment-3"], "temperature", 90.0),
            setattr(factory.equipment["equipment-3"], "vibration", 1.4),
        )
    )

    first = investigate_equipment_fault(state, "equipment-3")
    second = investigate_equipment_fault(state, "equipment-3")

    assert first == second
    assert first["candidate_diagnosis"] == "bearing_wear"
    assert first["confidence"] > 0.0
    assert first["data_quality"] == "INFERRED"


def test_investigate_equipment_fault_reports_unknown_without_sensor_data() -> None:
    state = create_state_of_world()

    result = investigate_equipment_fault(state, "equipment-2")

    assert result["candidate_diagnosis"] is None
    assert result["data_quality"] == "UNKNOWN"


def test_ground_truth_confidence_scoring_rewards_matching_keyword() -> None:
    ground_truth = GroundTruthStore()

    assert ground_truth.score_confidence("equipment-2", "bearing_wear") == 1.0
    assert ground_truth.score_confidence("equipment-2", "overheating") == 0.0
    assert ground_truth.score_confidence("equipment-2", None) == 0.0


def test_record_defect_is_observation_only() -> None:
    state = create_state_of_world()
    before_version = state.version
    before_accepted = state.snapshot().state.inventory.accepted_quantity["C"]

    record_defect(state, "C", "crushed_corner", "Crushed corner", "MINOR", 2)

    snapshot = state.snapshot().state
    assert state.version == before_version + 1
    assert snapshot.defects[-1].product_id == "C"
    assert snapshot.defects[-1].quantity == 2
    assert snapshot.inventory.accepted_quantity["C"] == before_accepted  # Observation only; no accept/reject decision.


def test_detect_state_conflicts_flags_disagreement_between_sources() -> None:
    state = create_state_of_world()
    state.update(lambda factory: setattr(factory.equipment["equipment-2"], "status", LineStatus.RUNNING))
    # Production line status intentionally left DOWN, creating a source disagreement.

    conflicts = detect_state_conflicts(state)

    assert any(conflict["subject"] == "line-2" for conflict in conflicts)


def test_detect_state_conflicts_is_empty_for_consistent_seed_state() -> None:
    state = create_state_of_world()

    assert detect_state_conflicts(state) == []


def test_weight_variance_distinguishes_single_from_repeated_deviation() -> None:
    state = create_state_of_world()

    state.update(
        lambda factory: factory.weight_observations.append(
            _weight_observation(factory, "A", deviation_pct=15.0)
        )
    )
    single = calculate_weight_variance(state, "A")
    assert single["status"] == "MINOR_DEVIATION"
    assert single["consecutive_abnormal"] == 1

    for _ in range(2):
        state.update(
            lambda factory: factory.weight_observations.append(
                _weight_observation(factory, "A", deviation_pct=15.0)
            )
        )
    repeated = calculate_weight_variance(state, "A")
    assert repeated["status"] == "MAJOR_DEVIATION"
    assert repeated["consecutive_abnormal"] == 3


def _weight_observation(factory: object, product_id: str, deviation_pct: float):
    from datetime import datetime, timezone

    from manufacturing_agents.state.models import DataQuality, WeightObservation

    standard = factory.quality_standards[product_id]  # type: ignore[attr-defined]
    observed = standard.expected_weight_kg * (1 + deviation_pct / 100)
    return WeightObservation(
        observation_id=f"weight-test-{len(factory.weight_observations) + 1}",  # type: ignore[attr-defined]
        product_id=product_id,
        observed_weight_kg=round(observed, 3),
        source="TEST",
        timestamp=datetime.now(timezone.utc).isoformat(),
        data_quality=DataQuality.SIMULATED,
    )


def test_simulation_syncs_degradation_and_defect_history_into_database(tmp_path: Path) -> None:
    db_path = tmp_path / "sim_quality.db"
    seed_default_factory(db_path)
    state = create_state_of_world()
    forced_events = [
        SimulationEvent("EQUIPMENT_DEGRADATION", "equipment", "equipment-3", 1.0, equipment_degradation),
        SimulationEvent("PRODUCT_DEFECT", "product", "dynamic", 1.0, product_defect),
        SimulationEvent("QUALITY_ANOMALY", "product", "dynamic", 1.0, quality_anomaly),
    ]
    engine = SimulationEngine(state, db_path=db_path, seed=42, events=forced_events)

    engine.run(3)

    with sqlite3.connect(db_path) as conn:
        measurement_count = conn.execute("SELECT COUNT(*) FROM equipment_measurements").fetchone()[0]
        defect_count = conn.execute("SELECT COUNT(*) FROM defects").fetchone()[0]
        weight_count = conn.execute("SELECT COUNT(*) FROM weight_measurements").fetchone()[0]

    assert measurement_count > 0
    assert defect_count == 3
    assert weight_count == 3
