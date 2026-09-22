"""Equipment Agent definition and its scoped tools."""

from __future__ import annotations

from agents import Agent, ModelSettings, function_tool
from agents.model_settings import Reasoning

from manufacturing_agents.state.factory_state import StateOfWorld
from manufacturing_agents.tools.equipment_tools import (
    check_replacement_part,
    get_fault_information,
    get_machine_status,
    get_maintenance_history,
    get_maintenance_procedure,
    estimate_repair_time,
    investigate_equipment_fault,
)


def build_equipment_agent(state: StateOfWorld) -> Agent:
    @function_tool
    def machine_status(equipment_id: str) -> dict[str, object]:
        """Read current status for one piece of equipment."""
        equipment = get_machine_status(state, equipment_id)
        return vars(equipment)

    @function_tool
    def fault_information(equipment_id: str) -> dict[str, object]:
        """Read observed fault information without inferring missing values."""
        return get_fault_information(state, equipment_id)

    @function_tool
    def maintenance_history(equipment_id: str) -> list[str]:
        """Read recorded maintenance history."""
        return get_maintenance_history(state, equipment_id)

    @function_tool
    def replacement_part(part_id: str) -> dict[str, object]:
        """Check simulated replacement-part information."""
        return check_replacement_part(state, part_id)

    @function_tool
    def repair_time(equipment_id: str) -> int | None:
        """Read the current repair estimate."""
        return estimate_repair_time(state, equipment_id)

    @function_tool
    def maintenance_procedure(equipment_id: str) -> str:
        """Retrieve a concise maintenance procedure reference."""
        return get_maintenance_procedure(equipment_id)

    @function_tool
    def fault_investigation(equipment_id: str) -> dict[str, object]:
        """Infer a candidate diagnosis and confidence from observable sensor symptoms only."""
        return investigate_equipment_fault(state, equipment_id)

    return Agent(
        name="Equipment Agent",
        model="gpt-5.6-terra",
        model_settings=ModelSettings(reasoning=Reasoning(effort="medium")),
        instructions=(
            "You are the Equipment Agent. Analyze equipment and maintenance only. "
            "Use tools for evidence, identify unknown or conflicting data explicitly, "
            "and return a concise report with diagnosis, evidence, repair duration, "
            "part options, risks, confidence, and escalation. Use fault_investigation "
            "to infer a candidate diagnosis with confidence from observable symptoms; "
            "never assert a diagnosis as certain when confidence is low. Never make "
            "system-wide production scheduling decisions or bypass safety."
        ),
        tools=[machine_status, fault_information, maintenance_history, replacement_part, repair_time, maintenance_procedure, fault_investigation],
    )
