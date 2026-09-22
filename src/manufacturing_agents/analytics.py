"""Deterministic evaluation metrics and reproducible run metadata, computed from Shared State and the database."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from manufacturing_agents.data.database import get_connection
from manufacturing_agents.state.factory_state import StateOfWorld
from manufacturing_agents.tools.inventory_tools import calculate_defect_rate, calculate_weight_variance

_COUNTABLE_TABLES = ("simulation_events", "defects", "weight_measurements", "equipment_measurements")


def compute_evaluation_metrics(state: StateOfWorld, db_path: str | Path | None = None) -> dict[str, Any]:
    """Compute measurable, Python-derived metrics; never inferred by an LLM."""
    full_snapshot = state.snapshot()
    factory = full_snapshot.state

    downtime_minutes = sum(equipment.downtime_minutes for equipment in factory.equipment.values())
    production_loss_units = sum(
        equipment.lost_units + equipment.projected_lost_units for equipment in factory.equipment.values()
    )
    material_shortages = [
        material.material_id
        for material in factory.raw_materials.values()
        if material.quantity_on_hand <= material.critical_threshold
    ]
    defect_rates = {product_id: calculate_defect_rate(state, product_id) for product_id in factory.products}
    weight_status = {product_id: calculate_weight_variance(state, product_id) for product_id in factory.products}
    weight_anomaly_products = [
        product_id for product_id, result in weight_status.items() if result["status"] not in ("NORMAL", "UNKNOWN")
    ]
    pending_human_approvals = sum(
        1 for decision in factory.decisions if decision.approval_status.value == "PENDING"
    )
    defect_count_total = sum(defect.quantity for defect in factory.defects)

    metrics: dict[str, Any] = {
        "state_version": full_snapshot.version,
        "downtime_minutes": downtime_minutes,
        "production_loss_units": production_loss_units,
        "material_shortages": material_shortages,
        "defect_rates": {product_id: result["defect_rate_percent"] for product_id, result in defect_rates.items()},
        "defect_count_total": defect_count_total,
        "weight_anomaly_products": weight_anomaly_products,
        "pending_human_approvals": pending_human_approvals,
        "safety_status": factory.safety.status,
    }

    if db_path is not None:
        conn = get_connection(db_path)
        try:
            for table in _COUNTABLE_TABLES:
                row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()  # noqa: S608 - fixed internal table name
                metrics[f"{table}_logged"] = row[0]
        finally:
            conn.close()

    return metrics


def start_simulation_run(db_path: str | Path, seed: int, scenario_name: str = "default") -> int:
    conn = get_connection(db_path)
    try:
        factory_row = conn.execute("SELECT id FROM factories LIMIT 1").fetchone()
        cursor = conn.execute(
            "INSERT INTO simulation_runs(factory_id, scenario_name, seed, started_at, tick_count) VALUES (?, ?, ?, ?, 0)",
            (factory_row["id"] if factory_row else None, scenario_name, seed, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def update_simulation_run(
    db_path: str | Path,
    run_id: int,
    *,
    tick_count: int,
    state_version: int,
    metrics: dict[str, Any],
) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE simulation_runs SET tick_count = ?, final_state_version = ?, metrics_json = ?, ended_at = ? WHERE id = ?",
            (tick_count, state_version, json.dumps(metrics), datetime.now(timezone.utc).isoformat(), run_id),
        )
        conn.commit()
    finally:
        conn.close()
