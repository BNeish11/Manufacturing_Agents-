"""Seeded simulation engine that advances simulated time and syncs events into the database."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from random import Random
from typing import Callable

from manufacturing_agents.data.database import get_connection
from manufacturing_agents.simulation.clock import SimulationClock
from manufacturing_agents.simulation.events import (
    employee_absence,
    equipment_degradation,
    line_two_recovery,
    material_consumption,
    product_defect,
    quality_anomaly,
    supplier_delay,
)
from manufacturing_agents.simulation.ground_truth import GroundTruthStore
from manufacturing_agents.state.factory_state import StateOfWorld


@dataclass(frozen=True)
class SimulationEvent:
    event_type: str
    entity_type: str
    entity_id: str
    probability: float
    apply: Callable[["SimulationEngine"], str | None]


def _default_events() -> list[SimulationEvent]:
    return [
        SimulationEvent("EQUIPMENT_DEGRADATION", "equipment", "equipment-3", 0.6, equipment_degradation),
        SimulationEvent("MATERIAL_CONSUMPTION", "raw_materials", "all", 1.0, material_consumption),
        SimulationEvent("SUPPLIER_DELAY", "material", "part-line-2-special", 0.2, supplier_delay),
        SimulationEvent("QUALITY_ANOMALY", "product", "dynamic", 0.3, quality_anomaly),
        SimulationEvent("PRODUCT_DEFECT", "product", "dynamic", 0.15, product_defect),
        SimulationEvent("EMPLOYEE_ABSENCE", "employee", "dynamic", 0.25, employee_absence),
        SimulationEvent("RECOVERY", "equipment", "equipment-2", 0.15, line_two_recovery),
    ]


class SimulationEngine:
    """Advances simulated time, applies seeded events, and keeps one shared State of the World current."""

    def __init__(
        self,
        state: StateOfWorld,
        *,
        db_path: str | Path | None = None,
        seed: int = 42,
        clock: SimulationClock | None = None,
        events: list[SimulationEvent] | None = None,
        ground_truth: GroundTruthStore | None = None,
    ) -> None:
        self.state = state
        self.db_path = db_path
        self.seed = seed
        self.rng = Random(seed)
        self.clock = clock or SimulationClock()
        self.events = events if events is not None else _default_events()
        # Evaluation-only hidden truth; never merged into StateOfWorld or read by agent tools.
        self.ground_truth = ground_truth or GroundTruthStore()

    def tick(self) -> dict[str, object]:
        simulation_time = self.clock.advance()
        applied: list[dict[str, object]] = []

        for event in self.events:
            if self.rng.random() < event.probability:
                summary = event.apply(self)
                if summary is None:
                    continue
                applied.append(self._log_event(simulation_time, event, summary))
                self._sync_domain_tables(event, simulation_time)

        self._persist_simulation_state(simulation_time)
        return {
            "simulation_time": simulation_time.isoformat(),
            "tick": self.clock.tick_count,
            "state_version": self.state.version,
            "applied_events": applied,
        }

    def run(self, ticks: int) -> list[dict[str, object]]:
        return [self.tick() for _ in range(ticks)]

    def _log_event(self, simulation_time: datetime, event: SimulationEvent, summary: str) -> dict[str, object]:
        record = {
            "event_type": event.event_type,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "simulation_time": simulation_time.isoformat(),
            "summary": summary,
            "state_version": self.state.version,
        }
        if self.db_path is not None:
            conn = get_connection(self.db_path)
            try:
                factory_row = conn.execute("SELECT id FROM factories LIMIT 1").fetchone()
                conn.execute(
                    "INSERT INTO simulation_events(factory_id, simulation_time, event_type, entity_type, entity_id, source, payload_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        factory_row["id"] if factory_row else None,
                        simulation_time.isoformat(),
                        event.event_type,
                        event.entity_type,
                        event.entity_id,
                        "SIMULATION_ENGINE",
                        json.dumps({"summary": summary, "state_version": self.state.version}),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        return record

    def _sync_domain_tables(self, event: SimulationEvent, simulation_time: datetime) -> None:
        """Mirror the just-applied change into its dedicated history table, when a matching seeded row exists."""
        if self.db_path is None:
            return
        conn = get_connection(self.db_path)
        try:
            factory_row = conn.execute("SELECT id FROM factories LIMIT 1").fetchone()
            if factory_row is None:
                return
            factory_id = factory_row["id"]

            if event.event_type == "EQUIPMENT_DEGRADATION":
                self._sync_equipment_measurement(conn, factory_id, simulation_time)
            elif event.event_type == "QUALITY_ANOMALY":
                self._sync_weight_measurement(conn, factory_id, simulation_time)
            elif event.event_type == "PRODUCT_DEFECT":
                self._sync_defect(conn, factory_id)
            elif event.event_type == "MATERIAL_CONSUMPTION":
                self._sync_material_inventory(conn, factory_id)

            conn.commit()
        finally:
            conn.close()

    def _sync_equipment_measurement(self, conn: object, factory_id: int, simulation_time: datetime) -> None:
        equipment = self.state.read(lambda factory: factory.equipment["equipment-3"])  # type: ignore[attr-defined]
        row = conn.execute(  # type: ignore[attr-defined]
            "SELECT id FROM equipment WHERE factory_id = ? AND equipment_code = ?", (factory_id, "equipment-3")
        ).fetchone()
        if row is None:
            return
        equipment_row_id = row["id"]
        conn.execute(  # type: ignore[attr-defined]
            "INSERT INTO equipment_measurements(equipment_id, measured_at, temperature, vibration, speed, status_observed, health_score, source, data_quality) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                equipment_row_id,
                simulation_time.isoformat(),
                equipment.temperature,
                equipment.vibration,
                None,
                equipment.status.value,
                equipment.health_score,
                "SIMULATION_ENGINE",
                "SIMULATED",
            ),
        )
        conn.execute(  # type: ignore[attr-defined]
            "UPDATE equipment SET status = ?, health_score = ?, temperature = ?, vibration = ?, updated_at = ? WHERE id = ?",
            (equipment.status.value, equipment.health_score, equipment.temperature, equipment.vibration, simulation_time.isoformat(), equipment_row_id),
        )

    def _sync_weight_measurement(self, conn: object, factory_id: int, simulation_time: datetime) -> None:
        observation = self.state.read(  # type: ignore[attr-defined]
            lambda factory: factory.weight_observations[-1] if factory.weight_observations else None
        )
        if observation is None:
            return
        product_row = conn.execute(  # type: ignore[attr-defined]
            "SELECT id FROM products WHERE factory_id = ? AND product_code = ?", (factory_id, observation.product_id)
        ).fetchone()
        if product_row is None:
            return
        standard = self.state.read(lambda factory: factory.quality_standards.get(observation.product_id))  # type: ignore[attr-defined]
        expected = standard.expected_weight_kg if standard else observation.observed_weight_kg
        variance_pct = round(((observation.observed_weight_kg - expected) / expected) * 100, 2) if expected else 0.0
        status = "NORMAL"
        if standard and abs(variance_pct) > standard.minor_deviation_percent:
            status = "MINOR_DEVIATION"
        conn.execute(  # type: ignore[attr-defined]
            "INSERT INTO weight_measurements(factory_id, product_id, observed_weight_kg, expected_weight_kg, acceptable_min_kg, acceptable_max_kg, variance_pct, measured_at, source, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                factory_id,
                product_row["id"],
                observation.observed_weight_kg,
                expected,
                standard.accepted_min_weight_kg if standard else expected,
                standard.accepted_max_weight_kg if standard else expected,
                variance_pct,
                simulation_time.isoformat(),
                "SIMULATION_ENGINE",
                status,
            ),
        )

    def _sync_defect(self, conn: object, factory_id: int) -> None:
        defect = self.state.read(lambda factory: factory.defects[-1] if factory.defects else None)  # type: ignore[attr-defined]
        if defect is None:
            return
        product_row = conn.execute(  # type: ignore[attr-defined]
            "SELECT id FROM products WHERE factory_id = ? AND product_code = ?", (factory_id, defect.product_id)
        ).fetchone()
        conn.execute(  # type: ignore[attr-defined]
            "INSERT INTO defects(factory_id, product_id, line_id, defect_code, description, severity, quantity, detected_at, root_cause) "
            "VALUES (?, ?, NULL, ?, ?, ?, ?, ?, NULL)",
            (
                factory_id,
                product_row["id"] if product_row else None,
                defect.defect_code,
                defect.description,
                defect.severity,
                defect.quantity,
                defect.detected_at,
            ),
        )

    def _sync_material_inventory(self, conn: object, factory_id: int) -> None:
        materials = self.state.read(lambda factory: dict(factory.raw_materials))  # type: ignore[attr-defined]
        for material in materials.values():
            row = conn.execute(  # type: ignore[attr-defined]
                "SELECT id FROM raw_materials WHERE factory_id = ? AND material_code = ?", (factory_id, material.material_id)
            ).fetchone()
            if row is None:
                continue
            available = max(0.0, material.quantity_on_hand - material.quantity_reserved)
            conn.execute(  # type: ignore[attr-defined]
                "UPDATE material_inventory SET quantity_on_hand = ?, quantity_available = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE factory_id = ? AND material_id = ?",
                (material.quantity_on_hand, available, factory_id, row["id"]),
            )

    def _persist_simulation_state(self, simulation_time: datetime) -> None:
        if self.db_path is None:
            return
        conn = get_connection(self.db_path)
        try:
            factory_row = conn.execute("SELECT id FROM factories LIMIT 1").fetchone()
            if factory_row is None:
                return
            factory_id = factory_row["id"]
            conn.execute(
                "INSERT INTO simulation_state(factory_id, simulation_time, tick, random_seed, state_version, state_hash) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(factory_id) DO UPDATE SET "
                "simulation_time = excluded.simulation_time, tick = excluded.tick, "
                "random_seed = excluded.random_seed, state_version = excluded.state_version, "
                "state_hash = excluded.state_hash",
                (
                    factory_id,
                    simulation_time.isoformat(),
                    self.clock.tick_count,
                    self.seed,
                    self.state.version,
                    f"v{self.state.version}",
                ),
            )
            conn.commit()
        finally:
            conn.close()
