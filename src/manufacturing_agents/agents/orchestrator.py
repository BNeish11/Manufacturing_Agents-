"""System-level Orchestrator using specialists as manager-style tools."""

from __future__ import annotations

from agents import Agent, ModelSettings, function_tool
from agents.model_settings import Reasoning

from manufacturing_agents.state.factory_state import StateOfWorld
from manufacturing_agents.agents.equipment import build_equipment_agent
from manufacturing_agents.agents.inventory import build_inventory_agent
from manufacturing_agents.agents.production import build_production_agent


def build_orchestrator_agent(state: StateOfWorld) -> Agent:
    equipment_agent = build_equipment_agent(state)
    production_agent = build_production_agent(state)
    inventory_agent = build_inventory_agent(state)

    @function_tool
    def factory_snapshot() -> dict[str, object]:
        """Read a complete shared-state snapshot for system reasoning."""
        snapshot = state.snapshot()
        return {
            "version": snapshot.version,
            "factory_name": snapshot.state.factory_name,
            "equipment": {key: vars(value) for key, value in snapshot.state.equipment.items()},
            "production_lines": {key: vars(value) for key, value in snapshot.state.production_lines.items()},
            "orders": {key: vars(value) for key, value in snapshot.state.orders.items()},
            "inventory": vars(snapshot.state.inventory),
            "safety": vars(snapshot.state.safety),
            "assumptions": {key: value.value for key, value in snapshot.state.assumptions.items()},
        }

    @function_tool
    def system_impact(summary: str, affected_metrics: list[str]) -> dict[str, object]:
        """Record the metrics that a proposed system decision must consider."""
        return {"summary": summary, "affected_metrics": affected_metrics, "state_version": state.version}

    return Agent(
        name="Orchestrator Agent",
        model="gpt-5.6-sol",
        model_settings=ModelSettings(reasoning=Reasoning(effort="high")),
        instructions=(
            "You are the Orchestrator Agent and system-level decision owner. Use the "
            "shared state and call the Equipment Agent, Production Agent, and Inventory Agent as specialist "
            "tools. Compare their evidence, identify conflicts, evaluate production, cost, "
            "quality, safety, labor, inventory, shipping, and customer consequences, then "
            "produce a concise recommendation with alternatives, evidence, expected impact, "
            "risks, affected metrics, assumptions, confidence, authority, and human approval. "
            "Never expose hidden chain-of-thought. Safety violations and unauthorized actions "
            "must be escalated, never rationalized away."
        ),
        tools=[factory_snapshot, system_impact],
        handoffs=[],
        # Specialists are intentionally exposed as tools, not handoffs.
        tool_use_behavior="run_llm_again",
    ).clone(
        tools=[
            factory_snapshot,
            system_impact,
            equipment_agent.as_tool("consult_equipment_agent", "Request equipment analysis."),
            production_agent.as_tool("consult_production_agent", "Request production analysis."),
            inventory_agent.as_tool("consult_inventory_agent", "Request inventory and quality analysis."),
        ]
    )
