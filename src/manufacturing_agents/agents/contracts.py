"""Structured contracts shared by the three agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentReport:
    agent: str
    state_version: int
    summary: str
    evidence: list[str] = field(default_factory=list)
    recommendation: str | None = None
    expected_impact: dict[str, Any] = field(default_factory=dict)
    risks: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    escalation_required: bool = False


@dataclass
class OrchestratorRecommendation(AgentReport):
    alternatives: list[str] = field(default_factory=list)
    affected_metrics: list[str] = field(default_factory=list)
    approval_required: bool = False
    required_permission: str | None = None


@dataclass(frozen=True)
class AgentContract:
    name: str
    purpose: str
    trigger: str
    inputs: tuple[str, ...]
    tools: tuple[str, ...]
    outputs: tuple[str, ...]
    recipients: tuple[str, ...]
    decisions_allowed: tuple[str, ...]
    failure_behavior: str
    guardrails: tuple[str, ...]
    human_escalation: tuple[str, ...]
    success_measure: str


EQUIPMENT_CONTRACT = AgentContract(
    name="Equipment Agent",
    purpose="Diagnose equipment conditions and recommend maintenance responses.",
    trigger="Equipment status change, failure, or Orchestrator request.",
    inputs=("equipment", "faults", "maintenance history", "parts", "safety"),
    tools=("get_machine_status", "get_fault_information", "check_replacement_part", "create_maintenance_request"),
    outputs=("diagnosis", "severity", "repair estimate", "part options", "risks"),
    recipients=("Orchestrator Agent",),
    decisions_allowed=("diagnose_equipment",),
    failure_behavior="Identify missing or conflicting data and escalate; never invent a diagnosis.",
    guardrails=("Cannot make production scheduling decisions", "Cannot bypass safety rules"),
    human_escalation=("Unsafe condition", "Conflicting critical evidence", "Restart or safety override"),
    success_measure="Accurate, evidence-based diagnosis and useful repair options.",
)

PRODUCTION_CONTRACT = AgentContract(
    name="Production Agent",
    purpose="Analyze capacity, schedules, inventory, labor, and delivery consequences.",
    trigger="Capacity, order, inventory, quality, or equipment change.",
    inputs=("lines", "capacity", "orders", "inventory", "labor", "quality", "shipping"),
    tools=("get_production_status", "calculate_production_loss", "simulate_schedule_change", "calculate_delivery_impact"),
    outputs=("loss", "at-risk orders", "schedule options", "overtime", "delivery impact"),
    recipients=("Orchestrator Agent",),
    decisions_allowed=("estimate_production_loss", "recalculate_schedule"),
    failure_behavior="Report unavailable inputs and bound the analysis instead of assuming values.",
    guardrails=("Cannot override Orchestrator authority", "Cannot schedule onto quality-held capacity"),
    human_escalation=("Contractual delivery risk", "Labor approval", "Conflicting capacity data"),
    success_measure="Accurate system-impact inputs and feasible recovery options.",
)

INVENTORY_CONTRACT = AgentContract(
    name="Inventory Agent",
    purpose="Maintain accurate inventory, material, and product-quality intelligence.",
    trigger="Inventory change, material threshold, quality observation, weight anomaly, or Orchestrator request.",
    inputs=("finished goods", "WIP", "raw materials", "reservations", "orders", "quality", "weights"),
    tools=("get_inventory_status", "get_material_inventory", "get_finished_goods", "calculate_max_production", "check_supply_thresholds", "calculate_defect_rate", "calculate_weight_variance"),
    outputs=("available inventory", "material constraint", "limiting material", "quality status", "inventory risks"),
    recipients=("Orchestrator Agent", "Production Agent", "Equipment Agent"),
    decisions_allowed=("calculate_inventory_availability", "identify_limiting_material", "classify_quality_risk"),
    failure_behavior="Mark missing, invalid, or conflicting inventory data explicitly and never invent quantities.",
    guardrails=("Uses one shared state", "Cannot schedule production", "Cannot purchase materials", "Cannot bypass safety or quality rules"),
    human_escalation=("Critical shortage", "Contractual order risk", "High defect rate", "Conflicting counts", "Potential safety issue"),
    success_measure="Accurate deterministic inventory constraints and timely, evidence-based escalation.",
)

ORCHESTRATOR_CONTRACT = AgentContract(
    name="Orchestrator Agent",
    purpose="Coordinate specialists and select the safest overall factory response.",
    trigger="Significant event, new information, or invalidated decision.",
    inputs=("full shared state", "Equipment report", "Production report", "Inventory report", "scorecard", "permissions"),
    tools=("Equipment Agent as tool", "Production Agent as tool", "Inventory Agent as tool", "calculate_system_impact", "request_human_approval", "record_decision"),
    outputs=("system recommendation", "alternatives", "tradeoffs", "approval packet", "decision record"),
    recipients=("Human plant manager", "Equipment Agent", "Production Agent", "Inventory Agent"),
    decisions_allowed=("system-level coordination", "human approval request"),
    failure_behavior="Pause unsafe or under-specified actions, state what is missing, and escalate.",
    guardrails=("One shared state", "Safety is a hard constraint", "No hidden chain-of-thought", "No unauthorized action"),
    human_escalation=("Safety issue", "Customer commitment", "High cost", "Labor action", "Critical conflict"),
    success_measure="Safe, explainable, system-level decisions with reconstructable evidence.",
)
