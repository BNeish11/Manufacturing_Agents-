"""Inventory Agent definition and scoped inventory/quality tools."""

from __future__ import annotations

from agents import Agent, ModelSettings, function_tool
from agents.model_settings import Reasoning

from manufacturing_agents.state.factory_state import StateOfWorld
from manufacturing_agents.tools.inventory_tools import (
    calculate_defect_rate,
    calculate_max_production,
    calculate_weight_variance,
    check_supply_thresholds,
    get_finished_goods,
    get_inventory_status,
    get_material_inventory,
    record_defect,
)


def build_inventory_agent(state: StateOfWorld) -> Agent:
    @function_tool
    def inventory_status() -> dict[str, object]:
        """Read finished goods, WIP, reservations, quality holds, and raw-material totals."""
        return get_inventory_status(state)

    @function_tool
    def material_inventory(material_id: str | None = None) -> dict[str, dict[str, object]]:
        """Read raw-material quantities, thresholds, status, and data quality."""
        return get_material_inventory(state, material_id)

    @function_tool
    def finished_goods(product_id: str | None = None) -> dict[str, dict[str, int]]:
        """Read produced, accepted, defective, reserved, held, and available quantities."""
        return get_finished_goods(state, product_id)

    @function_tool
    def material_supported_production(product_id: str) -> dict[str, object]:
        """Calculate the maximum quantity supported by every configured raw material."""
        return calculate_max_production(state, product_id)

    @function_tool
    def supply_thresholds(material_id: str | None = None) -> dict[str, dict[str, object]]:
        """Evaluate explicit material thresholds without changing state."""
        return check_supply_thresholds(state, material_id)

    @function_tool
    def defect_rate(product_id: str) -> dict[str, object]:
        """Calculate the deterministic accepted-versus-defective rate."""
        return calculate_defect_rate(state, product_id)

    @function_tool
    def weight_variance(product_id: str) -> dict[str, object]:
        """Analyze recorded weight observations and repeated deviations."""
        return calculate_weight_variance(state, product_id)

    @function_tool
    def defect_observation(product_id: str, defect_code: str, description: str, severity: str, quantity: int) -> int:
        """Record an observed defect. This logs an observation only; it is not an accept/reject decision."""
        return record_defect(state, product_id, defect_code, description, severity, quantity)

    return Agent(
        name="Inventory Agent",
        model="gpt-5.6-terra",
        model_settings=ModelSettings(reasoning=Reasoning(effort="medium")),
        instructions=(
            "You are the Inventory Agent. Provide accurate inventory, raw-material, "
            "finished-goods, and quality intelligence from tools and the shared state. "
            "Use deterministic calculations for material-supported production, limiting "
            "materials, reservations, defect rates, and weight trends. Clearly identify "
            "unknown or conflicting data. You may recommend or escalate, but you may not "
            "schedule production, purchase supplies, change customer commitments, override "
            "quality or safety rules, or replace the Orchestrator. Do not invent human "
            "inspection results or measurements. Recording a defect observation is not the "
            "same as an accept/reject decision."
        ),
        tools=[inventory_status, material_inventory, finished_goods, material_supported_production, supply_thresholds, defect_rate, weight_variance, defect_observation],
    )