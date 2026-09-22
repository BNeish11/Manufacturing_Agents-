"""Typed domain models for the simulated factory State of the World."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class LineStatus(str, Enum):
    RUNNING = "RUNNING"
    DOWN = "DOWN"
    DEGRADED = "DEGRADED"
    QUALITY_HOLD = "QUALITY_HOLD"


class DataQuality(str, Enum):
    VERIFIED = "VERIFIED"
    SIMULATED = "SIMULATED"
    UNKNOWN = "UNKNOWN"
    CONFLICTING = "CONFLICTING"
    STALE = "STALE"
    INFERRED = "INFERRED"


class ApprovalStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class Equipment:
    equipment_id: str
    line_id: str
    name: str
    status: LineStatus
    current_fault: str | None = None
    fault_code: str | None = None
    downtime_minutes: int = 0
    lost_units: int = 0
    projected_lost_units: int = 0
    estimated_repair_minutes: int | None = None
    required_part_id: str | None = None
    data_quality: DataQuality = DataQuality.SIMULATED
    maintenance_history: list[str] = field(default_factory=list)
    temperature: float | None = None
    vibration: float | None = None
    health_score: float | None = None
    operating_hours: float = 0.0


@dataclass
class ProductionLine:
    line_id: str
    name: str
    status: LineStatus
    utilization_percent: float
    hourly_capacity: int
    supported_products: list[str]
    quality_hold: bool = False


@dataclass
class Product:
    product_id: str
    name: str
    business_priority: str
    margin_per_unit: float
    dimensions: str = "UNKNOWN"


@dataclass
class Order:
    order_id: str
    product_id: str
    customer: str
    quantity: int
    due_date: str
    priority: str
    contractual_delivery: bool = False
    status: str = "OPEN"


@dataclass
class Inventory:
    finished_goods: dict[str, int]
    work_in_progress: dict[str, int]
    raw_material_units: int
    days_of_inventory: float
    data_quality: DataQuality = DataQuality.SIMULATED
    produced_quantity: dict[str, int] = field(default_factory=dict)
    accepted_quantity: dict[str, int] = field(default_factory=dict)
    defective_quantity: dict[str, int] = field(default_factory=dict)
    reserved_quantity: dict[str, int] = field(default_factory=dict)
    quality_hold_quantity: dict[str, int] = field(default_factory=dict)


@dataclass
class RawMaterial:
    material_id: str
    name: str
    unit: str
    quantity_on_hand: float
    reorder_threshold: float
    critical_threshold: float
    requirements_per_product: dict[str, float]
    quantity_reserved: float = 0.0
    data_quality: DataQuality = DataQuality.SIMULATED
    source: str = "SIMULATED"


@dataclass
class QualityStandard:
    product_id: str
    expected_weight_kg: float
    accepted_min_weight_kg: float
    accepted_max_weight_kg: float
    minor_deviation_percent: float = 10.0
    critical_defect_rate_percent: float = 5.0


@dataclass
class WeightObservation:
    observation_id: str
    product_id: str
    observed_weight_kg: float
    source: str
    timestamp: str
    data_quality: DataQuality = DataQuality.SIMULATED


@dataclass
class HumanInspectionObservation:
    observation_id: str
    product_id: str
    category: str
    severity: str
    quantity: int
    timestamp: str
    source: str = "HUMAN_PROVIDED"


@dataclass
class InventoryRisk:
    risk_id: str
    subject: str
    risk_type: str
    severity: str
    evidence: list[str] = field(default_factory=list)
    affected_orders: list[str] = field(default_factory=list)
    escalation_required: bool = False


@dataclass
class DefectObservation:
    defect_id: str
    product_id: str
    defect_code: str
    description: str
    severity: str
    quantity: int
    detected_at: str
    line_id: str | None = None
    source: str = "SIMULATED"


@dataclass
class StateConflict:
    conflict_id: str
    subject: str
    description: str
    sources: list[str] = field(default_factory=list)
    severity: str = "WARNING"


@dataclass
class Employee:
    employee_id: str
    skill: str
    assignment: str
    available: bool = False


@dataclass
class MaterialPart:
    part_id: str
    name: str
    supplier: str
    available: bool
    normal_delivery_days: int | None
    expedited_delivery: str | None = None
    normal_cost: float = 0.0
    expedited_cost_multiplier: float = 1.0


@dataclass
class QualityFinding:
    finding_id: str
    line_id: str
    description: str
    severity: str
    active: bool = True


@dataclass
class CostState:
    repair_cost: float = 0.0
    expedited_shipping_cost: float = 0.0
    overtime_cost: float = 0.0
    estimated_revenue_impact: float = 0.0


@dataclass
class SafetyState:
    status: str = "CLEAR"
    restrictions: list[str] = field(default_factory=list)
    human_intervention_required: bool = False


@dataclass
class ScorecardMetric:
    name: str
    value: float
    weight_percent: float
    threshold: float
    status: str = "WITHIN_THRESHOLD"


@dataclass
class DecisionRecord:
    decision_id: str
    timestamp: str
    trigger: str
    state_version: int
    recommendation: str
    reasoning_summary: str
    evidence: list[str]
    expected_impact: dict[str, Any]
    risks: list[str]
    approval_required: bool
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    human_decision: str | None = None
    final_action: str | None = None
    outcome: str | None = None


@dataclass
class FactoryState:
    factory_name: str
    employee_count: int
    affected_employee_count: int
    reassigned_employee_count: int
    system_severity: int
    equipment: dict[str, Equipment]
    production_lines: dict[str, ProductionLine]
    products: dict[str, Product]
    orders: dict[str, Order]
    inventory: Inventory
    employees: dict[str, Employee]
    materials: dict[str, MaterialPart]
    quality_findings: dict[str, QualityFinding]
    costs: CostState
    safety: SafetyState
    scorecard: list[ScorecardMetric]
    decisions: list[DecisionRecord] = field(default_factory=list)
    assumptions: dict[str, DataQuality] = field(default_factory=dict)
    raw_materials: dict[str, RawMaterial] = field(default_factory=dict)
    quality_standards: dict[str, QualityStandard] = field(default_factory=dict)
    weight_observations: list[WeightObservation] = field(default_factory=list)
    human_inspections: list[HumanInspectionObservation] = field(default_factory=list)
    inventory_risks: list[InventoryRisk] = field(default_factory=list)
    defects: list[DefectObservation] = field(default_factory=list)
    version: int = 0
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class StateSnapshot:
    state: FactoryState
    version: int
    captured_at: str
