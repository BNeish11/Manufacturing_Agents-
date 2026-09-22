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
from manufacturing_agents.tools.inventory_tools import inventory_report_for_state
from manufacturing_agents.tools.orchestrator_tools import (
    calculate_consequence_cards,
    calculate_system_severity,
    record_human_decision,
)

SIMULATION_SEED = 42

# High-level, tool-call-free mapping of which specialist domain each scenario/event touches.
SCENARIO_DOMAINS: dict[str, set[str]] = {
    "part": {"equipment"},
    "product-c": {"production", "inventory"},
    "line-3-quality": {"equipment", "production"},
}
EVENT_DOMAINS: dict[str, str] = {
    "EQUIPMENT_DEGRADATION": "equipment",
    "RECOVERY": "equipment",
    "MATERIAL_CONSUMPTION": "inventory",
    "SUPPLIER_DELAY": "inventory",
    "PRODUCT_DEFECT": "inventory",
    "QUALITY_ANOMALY": "inventory",
    "EMPLOYEE_ABSENCE": "production",
}
SPECIALIST_KEYS = ("equipment", "production", "inventory")


class DashboardRuntime:
    def __init__(self) -> None:
        self.events = EventJournal()
        self._db_dir = Path(tempfile.mkdtemp(prefix="manufacturing_agents_runtime_"))
        self.reset()

    def reset(self) -> dict[str, Any]:
        self.state: StateOfWorld = create_state_of_world()
        self.latest_result: dict[str, Any] | None = None
        self._agent_status: dict[str, str] = {key: "IDLE" for key in SPECIALIST_KEYS}
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

    def _mark_domains(self, touched: set[str]) -> None:
        self._agent_status = {key: ("COMPLETED" if key in touched else "IDLE") for key in SPECIALIST_KEYS}

    def _mark_error(self, touched: set[str]) -> None:
        for key in touched or SPECIALIST_KEYS:
            self._agent_status[key] = "ERROR"

    def agent_status(self) -> dict[str, str]:
        decisions = self.state.snapshot().state.decisions
        if decisions and decisions[-1].approval_status.value == "PENDING":
            orchestrator = "NEEDS_HUMAN_APPROVAL"
        elif decisions:
            orchestrator = "COMPLETED"
        else:
            orchestrator = "IDLE"
        return {"orchestrator": orchestrator, **self._agent_status}

    def simulation_status(self) -> str:
        statuses = self.agent_status()
        if any(status == "NEEDS_HUMAN_APPROVAL" for status in statuses.values()):
            return "WAITING_FOR_HUMAN"
        if any(status == "ERROR" for status in statuses.values()):
            return "ERROR"
        if self.engine.clock.tick_count == 0 and all(status == "IDLE" for status in self._agent_status.values()):
            return "IDLE"
        return "RUNNING"

    def dashboard(self) -> dict[str, Any]:
        snapshot = self.state.snapshot()
        state = snapshot.state
        return {
            "version": snapshot.version,
            "updated_at": state.updated_at,
            "factory": {
                "name": state.factory_name,
                "severity": calculate_system_severity(self.state),
                "safety": to_jsonable(state.safety),
                "human_intervention_required": state.safety.human_intervention_required,
            },
            "simulation": {
                "tick": self.engine.clock.tick_count,
                "simulation_time": self.engine.clock.current_time.isoformat(),
                "seed": self.engine.seed,
                "status": self.simulation_status(),
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
            "inventory_report": to_jsonable(inventory_report_for_state(self.state)),
            "consequence_cards": to_jsonable(calculate_consequence_cards(self.state)),
            "agent_status": self.agent_status(),
            "latest_result": to_jsonable(self.latest_result),
            "events": self.events.as_dicts(),
        }

    def run_failure(self, human_approved: bool = False) -> dict[str, Any]:
        self.events.add("workflow_started", "ORCHESTRATOR", self.state.version, "Line 2 failure assessment started.")
        try:
            self.latest_result = run_line_two_failure(self.state, human_approved=human_approved)
        except Exception:
            self._mark_error({"equipment", "production", "inventory"})
            raise
        self._mark_domains({"equipment", "production", "inventory"})
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
        touched = SCENARIO_DOMAINS.get(name, set())
        try:
            updates[name](self.state)
        except Exception:
            self._mark_error(touched)
            raise
        self._mark_domains(touched)
        self.latest_result = None
        self.events.add("scenario_updated", "SYSTEM", self.state.version, f"Scenario update applied: {name}.", update=name)
        return self.dashboard()

    def advance_simulation(self, ticks: int = 1) -> dict[str, Any]:
        if ticks < 1:
            raise ValueError("ticks must be at least 1.")
        try:
            tick_results = self.engine.run(ticks)
        except Exception:
            self._mark_error(set())
            raise
        touched: set[str] = set()
        for tick_result in tick_results:
            for applied in tick_result["applied_events"]:
                event_type = str(applied["event_type"])
                if event_type in EVENT_DOMAINS:
                    touched.add(EVENT_DOMAINS[event_type])
                self.events.add(
                    "simulation_event",
                    event_type,
                    int(applied["state_version"]),
                    str(applied["summary"]),
                    entity=applied["entity_id"],
                )
        self._mark_domains(touched)
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

    def submit_decision(self, decision_id: str, action: str) -> dict[str, Any]:
        record_human_decision(self.state, decision_id, action)
        self.events.add(
            "human_decision_recorded",
            "HUMAN",
            self.state.version,
            f"Human recorded decision: {action} for {decision_id}.",
            decision_id=decision_id,
            action=action,
        )
        return self.dashboard()