"""Runtime-owned state and dashboard operations."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from manufacturing_agents.analytics import compute_evaluation_metrics, start_simulation_run, update_simulation_run
from manufacturing_agents.api.events import EventJournal
from manufacturing_agents.api.serializers import to_jsonable
from manufacturing_agents.data.database import seed_default_factory
from manufacturing_agents.data.factory_data import create_state_of_world
from manufacturing_agents.orchestration.workflow import run_line_two_failure
from manufacturing_agents.scenarios.updates import (
    line_three_quality_update,
    product_c_priority_update,
    specialized_part_update,
)
from manufacturing_agents.simulation.engine import SimulationEngine
from manufacturing_agents.state.factory_state import StateOfWorld

SIMULATION_SEED = 42


class DashboardRuntime:
    def __init__(self) -> None:
        self.events = EventJournal()
        self._db_dir = Path(tempfile.mkdtemp(prefix="manufacturing_agents_runtime_"))
        self.reset()

    def reset(self) -> dict[str, Any]:
        self.state: StateOfWorld = create_state_of_world()
        self.latest_result: dict[str, Any] | None = None
        self.events.clear()

        self.db_path = self._db_dir / "factory.db"
        if self.db_path.exists():
            self.db_path.unlink()
        seed_default_factory(self.db_path)

        self.engine = SimulationEngine(self.state, db_path=self.db_path, seed=SIMULATION_SEED)
        self.run_id = start_simulation_run(self.db_path, SIMULATION_SEED, scenario_name="line-2-failure-baseline")

        self.events.add("state_reset", "SYSTEM", self.state.version, "Shared State of the World reset.")
        return self.dashboard()

    def snapshot(self) -> dict[str, Any]:
        return to_jsonable(self.state.snapshot())

    def metrics(self) -> dict[str, Any]:
        return compute_evaluation_metrics(self.state, self.db_path)

    def dashboard(self) -> dict[str, Any]:
        snapshot = self.state.snapshot()
        state = snapshot.state
        return {
            "version": snapshot.version,
            "updated_at": state.updated_at,
            "factory": {
                "name": state.factory_name,
                "severity": state.system_severity,
                "safety": to_jsonable(state.safety),
                "human_intervention_required": state.safety.human_intervention_required,
            },
            "simulation": {
                "tick": self.engine.clock.tick_count,
                "simulation_time": self.engine.clock.current_time.isoformat(),
                "seed": self.engine.seed,
            },
            "lines": to_jsonable(state.production_lines),
            "equipment": to_jsonable(state.equipment),
            "inventory": to_jsonable(state.inventory),
            "orders": to_jsonable(state.orders),
            "labor": {
                "total": state.employee_count,
                "affected": state.affected_employee_count,
                "reassigned": state.reassigned_employee_count,
            },
            "materials": to_jsonable(state.materials),
            "raw_materials": to_jsonable(state.raw_materials),
            "quality_standards": to_jsonable(state.quality_standards),
            "weight_observations": to_jsonable(state.weight_observations),
            "human_inspections": to_jsonable(state.human_inspections),
            "inventory_risks": to_jsonable(state.inventory_risks),
            "defects": to_jsonable(state.defects),
            "quality": to_jsonable(state.quality_findings),
            "scorecard": to_jsonable(state.scorecard),
            "assumptions": to_jsonable(state.assumptions),
            "decisions": to_jsonable(state.decisions),
            "metrics": self.metrics(),
            "latest_result": to_jsonable(self.latest_result),
            "events": self.events.as_dicts(),
        }

    def run_failure(self, human_approved: bool = False) -> dict[str, Any]:
        self.events.add("workflow_started", "ORCHESTRATOR", self.state.version, "Line 2 failure assessment started.")
        self.events.add("agent_activity", "EQUIPMENT AGENT", self.state.version, "Equipment analysis requested.", status="ANALYZING")
        self.events.add("agent_activity", "PRODUCTION AGENT", self.state.version, "Production impact analysis requested.", status="ANALYZING")
        self.events.add("agent_activity", "Inventory Agent", self.state.version, "Inventory and quality analysis requested.", status="ANALYZING")
        self.latest_result = run_line_two_failure(self.state, human_approved=human_approved)
        self.events.add("approval_requested", "ORCHESTRATOR", self.state.version, "Human approval required for system-level recovery action.")
        self.events.add("workflow_completed", "ORCHESTRATOR", self.state.version, "Line 2 assessment completed.")
        return self.dashboard()

    def apply_update(self, name: str) -> dict[str, Any]:
        updates = {
            "part": specialized_part_update,
            "product-c": product_c_priority_update,
            "line-3-quality": line_three_quality_update,
        }
        if name not in updates:
            raise KeyError(name)
        updates[name](self.state)
        self.latest_result = None
        self.events.add("scenario_updated", "SYSTEM", self.state.version, f"Scenario update applied: {name}.", update=name)
        return self.dashboard()

    def advance_simulation(self, ticks: int = 1) -> dict[str, Any]:
        if ticks < 1:
            raise ValueError("ticks must be at least 1.")
        tick_results = self.engine.run(ticks)
        for tick_result in tick_results:
            for applied in tick_result["applied_events"]:
                self.events.add(
                    "simulation_event",
                    str(applied["event_type"]),
                    int(applied["state_version"]),
                    str(applied["summary"]),
                    entity=applied["entity_id"],
                )
        self.latest_result = None
        update_simulation_run(
            self.db_path,
            self.run_id,
            tick_count=self.engine.clock.tick_count,
            state_version=self.state.version,
            metrics=self.metrics(),
        )
        self.events.add(
            "simulation_tick",
            "SYSTEM",
            self.state.version,
            f"Simulation advanced to tick {self.engine.clock.tick_count} ({self.engine.clock.current_time.isoformat()}).",
        )
        return self.dashboard()