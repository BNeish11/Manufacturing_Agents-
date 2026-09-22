"""Seeded factory events that mutate the shared State of the World.

Each function receives the running SimulationEngine (for its RNG and state
handle), applies one bounded, explainable change through StateOfWorld.update,
and returns a summary string, or None if the event had nothing to change.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from manufacturing_agents.state.models import DataQuality, DefectObservation, LineStatus, WeightObservation

if TYPE_CHECKING:
    from manufacturing_agents.simulation.engine import SimulationEngine

_DEFECT_CODES = {
    "crushed_corner": "Crushed corner",
    "glue_failure": "Incomplete glue seal",
    "incorrect_fold": "Incorrect fold line",
}

_MATERIAL_BASELINE_USAGE = {
    "liner-board": 40.0,
    "corrugated-medium": 20.0,
    "adhesive": 1.0,
    "printing-ink": 0.2,
}


def equipment_degradation(engine: "SimulationEngine") -> str | None:
    delta = 2.0 + engine.rng.random() * 3.0
    applied = {"changed": False}

    def mutate(factory: object) -> None:
        equipment = factory.equipment["equipment-3"]  # type: ignore[attr-defined]
        line = factory.production_lines["line-3"]  # type: ignore[attr-defined]
        if equipment.status is not LineStatus.RUNNING:
            return
        applied["changed"] = True
        equipment.temperature = round((equipment.temperature or 60.0) + delta, 1)
        equipment.vibration = round((equipment.vibration or 0.4) + delta / 20, 2)
        equipment.health_score = round(
            max(0.0, (equipment.health_score if equipment.health_score is not None else 1.0) - delta / 100), 3
        )
        if equipment.health_score is not None and equipment.health_score < 0.5:
            equipment.status = LineStatus.DEGRADED
            line.status = LineStatus.DEGRADED

    engine.state.update(mutate)
    if not applied["changed"]:
        return None
    return "Line 3 equipment shows rising temperature and vibration readings."


def material_consumption(engine: "SimulationEngine") -> str | None:
    usage_factor = 0.9 + engine.rng.random() * 0.2

    def mutate(factory: object) -> None:
        for material in factory.raw_materials.values():  # type: ignore[attr-defined]
            baseline = _MATERIAL_BASELINE_USAGE.get(material.material_id, 5.0)
            material.quantity_on_hand = max(0.0, material.quantity_on_hand - baseline * usage_factor)

    engine.state.update(mutate)
    return "Simulated production consumed raw materials for the tick."


def supplier_delay(engine: "SimulationEngine") -> str | None:
    applied = {"changed": False}

    def mutate(factory: object) -> None:
        part = factory.materials.get("part-line-2-special")  # type: ignore[attr-defined]
        if part is None or part.normal_delivery_days is None:
            return
        applied["changed"] = True
        part.normal_delivery_days += 1
        factory.assumptions["line-2-repair-plan"] = DataQuality.STALE  # type: ignore[attr-defined]

    engine.state.update(mutate)
    if not applied["changed"]:
        return None
    return "Supplier delivery update delayed the Line 2 replacement part."


def quality_anomaly(engine: "SimulationEngine") -> str | None:
    product_id = engine.rng.choice(["A", "B", "C"])
    deviation_pct = 8.0 + engine.rng.random() * 10.0
    direction = 1 if engine.rng.random() > 0.5 else -1
    applied = {"changed": False}

    def mutate(factory: object) -> None:
        standard = factory.quality_standards.get(product_id)  # type: ignore[attr-defined]
        if standard is None:
            return
        applied["changed"] = True
        observed = standard.expected_weight_kg * (1 + direction * deviation_pct / 100)
        factory.weight_observations.append(  # type: ignore[attr-defined]
            WeightObservation(
                observation_id=f"weight-{len(factory.weight_observations) + 1}",  # type: ignore[attr-defined]
                product_id=product_id,
                observed_weight_kg=round(observed, 3),
                source="SIMULATION",
                timestamp=datetime.now(timezone.utc).isoformat(),
                data_quality=DataQuality.SIMULATED,
            )
        )

    engine.state.update(mutate)
    if not applied["changed"]:
        return None
    return f"Recorded a simulated weight observation for Product {product_id}."


def employee_absence(engine: "SimulationEngine") -> str | None:
    applied = {"changed": False}

    def mutate(factory: object) -> None:
        available_ids = [
            employee_id for employee_id, employee in factory.employees.items() if employee.available  # type: ignore[attr-defined]
        ]
        if not available_ids:
            return
        chosen = available_ids[engine.rng.randrange(len(available_ids))]
        factory.employees[chosen].available = False  # type: ignore[attr-defined]
        applied["changed"] = True

    engine.state.update(mutate)
    if not applied["changed"]:
        return None
    return "An available employee became unavailable for the tick."


def line_two_recovery(engine: "SimulationEngine") -> str | None:
    applied = {"changed": False}

    def mutate(factory: object) -> None:
        equipment = factory.equipment["equipment-2"]  # type: ignore[attr-defined]
        line = factory.production_lines["line-2"]  # type: ignore[attr-defined]
        if equipment.status is not LineStatus.DOWN:
            return
        applied["changed"] = True
        equipment.status = LineStatus.RUNNING
        equipment.downtime_minutes = 0
        equipment.current_fault = None
        equipment.lost_units = 0
        equipment.projected_lost_units = 0
        line.status = LineStatus.RUNNING
        line.utilization_percent = 55.0

    engine.state.update(mutate)
    if not applied["changed"]:
        return None
    return "Line 2 returned to service after simulated repair completion."


def product_defect(engine: "SimulationEngine") -> str | None:
    product_id = engine.rng.choice(["A", "B", "C"])
    quantity = engine.rng.randint(1, 5)
    defect_code = engine.rng.choice(list(_DEFECT_CODES))
    description = _DEFECT_CODES[defect_code]
    severity = "MINOR" if quantity <= 2 else "WARNING"

    def mutate(factory: object) -> None:
        factory.defects.append(  # type: ignore[attr-defined]
            DefectObservation(
                defect_id=f"defect-{len(factory.defects) + 1}",  # type: ignore[attr-defined]
                product_id=product_id,
                defect_code=defect_code,
                description=description,
                severity=severity,
                quantity=quantity,
                detected_at=datetime.now(timezone.utc).isoformat(),
                source="SIMULATED",
            )
        )
        current = factory.inventory.defective_quantity.get(product_id, 0)  # type: ignore[attr-defined]
        factory.inventory.defective_quantity[product_id] = current + quantity  # type: ignore[attr-defined]

    engine.state.update(mutate)
    return f"Detected {quantity} simulated {description.lower()} defects for Product {product_id}."
