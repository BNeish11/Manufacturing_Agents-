"""Production Agent definition and its scoped tools."""

from __future__ import annotations

from agents import Agent, ModelSettings, function_tool
from agents.model_settings import Reasoning

from manufacturing_agents.state.factory_state import StateOfWorld
from manufacturing_agents.tools.production_tools import (
    calculate_delivery_impact,
    calculate_overtime_requirement,
    calculate_production_loss,
    get_inventory_status,
    get_line_capacity,
    get_order_status,
    get_production_status,
    simulate_schedule_change,
)


def build_production_agent(state: StateOfWorld) -> Agent:
    @function_tool
    def production_status() -> dict[str, object]:
        """Read all production-line status and utilization."""
        return get_production_status(state)

    @function_tool
    def production_loss(line_id: str, downtime_minutes: int) -> int:
        """Calculate lost units from line capacity and downtime."""
        return calculate_production_loss(state, line_id, downtime_minutes)

    @function_tool
    def line_capacity(line_id: str) -> dict[str, object]:
        """Read capacity and product support for one line."""
        return get_line_capacity(state, line_id)

    @function_tool
    def orders() -> list[dict[str, object]]:
        """Read current customer orders."""
        return get_order_status(state)

    @function_tool
    def inventory() -> dict[str, object]:
        """Read finished goods, WIP, and material inventory."""
        return get_inventory_status(state)

    @function_tool
    def schedule_simulation(product_id: str, target_line_id: str, quantity: int) -> dict[str, object]:
        """Test a schedule option without mutating the plan."""
        return simulate_schedule_change(state, product_id, target_line_id, quantity)

    @function_tool
    def delivery_impact(product_id: str, lost_units: int) -> dict[str, object]:
        """Estimate affected open orders and contractual risk."""
        return calculate_delivery_impact(state, product_id, lost_units)

    @function_tool
    def overtime(quantity: int, line_id: str) -> float:
        """Estimate hours needed to recover a quantity."""
        return calculate_overtime_requirement(state, quantity, line_id)

    return Agent(
        name="Production Agent",
        model="gpt-5.6-terra",
        model_settings=ModelSettings(reasoning=Reasoning(effort="medium")),
        instructions=(
            "You are the Production Agent. Analyze capacity, orders, inventory, labor, "
            "quality, schedules, and delivery. Use tools for calculations and clearly "
            "separate facts from assumptions. Return feasible alternatives, losses, "
            "delivery impact, overtime, risks, confidence, and escalation. Do not "
            "execute system-level changes or override the Orchestrator."
        ),
        tools=[production_status, production_loss, line_capacity, orders, inventory, schedule_simulation, delivery_impact, overtime],
    )
