"""Editable simulated factory seed data for the assignment scenarios."""

from manufacturing_agents.state.factory_state import StateOfWorld
from manufacturing_agents.state.models import (
    CostState,
    DataQuality,
    Employee,
    Equipment,
    FactoryState,
    Inventory,
    LineStatus,
    MaterialPart,
    Order,
    Product,
    ProductionLine,
    QualityFinding,
    QualityStandard,
    RawMaterial,
    SafetyState,
    ScorecardMetric,
)


def create_initial_state() -> FactoryState:
    return FactoryState(
        factory_name="Example Manufacturing Factory",
        employee_count=125,
        affected_employee_count=12,
        reassigned_employee_count=4,
        system_severity=72,
        equipment={
            "equipment-1": Equipment(
                equipment_id="equipment-1",
                line_id="line-1",
                name="Line 1 Main Cell",
                status=LineStatus.RUNNING,
            ),
            "equipment-2": Equipment(
                equipment_id="equipment-2",
                line_id="line-2",
                name="Line 2 Main Cell",
                status=LineStatus.DOWN,
                current_fault=None,
                downtime_minutes=18,
                lost_units=420,
                projected_lost_units=2300,
                estimated_repair_minutes=95,
                data_quality=DataQuality.UNKNOWN,
            ),
            "equipment-3": Equipment(
                equipment_id="equipment-3",
                line_id="line-3",
                name="Line 3 Main Cell",
                status=LineStatus.RUNNING,
            ),
        },
        production_lines={
            "line-1": ProductionLine("line-1", "Production Line 1", LineStatus.RUNNING, 63.0, 240, ["A", "B"]),
            "line-2": ProductionLine("line-2", "Production Line 2", LineStatus.DOWN, 0.0, 220, ["A", "C"]),
            "line-3": ProductionLine("line-3", "Production Line 3", LineStatus.RUNNING, 81.0, 180, ["B", "C"]),
        },
        products={
            "A": Product("A", "Product A", "HIGH_VOLUME", 18.0, "12x12"),
            "B": Product("B", "Product B", "HIGHEST_MARGIN", 42.0, "24x24"),
            "C": Product("C", "Product C", "CONTRACTUAL_DELIVERY", 24.0, "36x36"),
        },
        orders={
            "order-a": Order("order-a", "A", "Northwind Retail", 5000, "2026-09-18", "HIGH"),
            "order-b": Order("order-b", "B", "Summit Components", 900, "2026-09-20", "LOW"),
            "order-c": Order("order-c", "C", "Atlas Industrial", 1200, "2026-09-19", "MEDIUM", True),
        },
        inventory=Inventory(
            finished_goods={"A": 1000, "B": 500, "C": 300},
            work_in_progress={"A": 300, "B": 150, "C": 150},
            raw_material_units=10000,
            days_of_inventory=3.5,
            produced_quantity={"A": 1200, "B": 600, "C": 350},
            accepted_quantity={"A": 1180, "B": 590, "C": 342},
            defective_quantity={"A": 20, "B": 10, "C": 8},
            reserved_quantity={"A": 700, "B": 200, "C": 60},
            quality_hold_quantity={"A": 0, "B": 0, "C": 0},
        ),
        employees={
            f"employee-{index}": Employee(
                employee_id=f"employee-{index}",
                skill="Production Technician",
                assignment="Line 2" if index <= 12 else "Available Pool",
                available=index > 12,
            )
            for index in range(1, 126)
        },
        materials={
            "part-line-2-special": MaterialPart(
                part_id="part-line-2-special",
                name="Line 2 Specialized Drive Module",
                supplier="Precision Industrial Supply",
                available=False,
                normal_delivery_days=None,
                normal_cost=1200.0,
            )
        },
        quality_findings={},
        raw_materials={
            "liner-board": RawMaterial(
                "liner-board", "Corrugated liner board", "m2", 5000.0, 1250.0, 500.0,
                {"A": 0.60, "B": 1.80, "C": 3.60},
            ),
            "corrugated-medium": RawMaterial(
                "corrugated-medium", "Corrugated medium", "m2", 2500.0, 625.0, 250.0,
                {"A": 0.30, "B": 0.90, "C": 1.80},
            ),
            "adhesive": RawMaterial(
                "adhesive", "Box adhesive", "kg", 120.0, 30.0, 12.0,
                {"A": 0.020, "B": 0.035, "C": 0.060},
            ),
            "printing-ink": RawMaterial(
                "printing-ink", "Printing ink", "L", 30.0, 7.5, 3.0,
                {"A": 0.004, "B": 0.007, "C": 0.012},
            ),
        },
        quality_standards={
            "A": QualityStandard("A", 0.40, 0.37, 0.43),
            "B": QualityStandard("B", 0.95, 0.89, 1.01),
            "C": QualityStandard("C", 1.80, 1.69, 1.91),
        },
        costs=CostState(),
        safety=SafetyState(human_intervention_required=True),
        scorecard=[
            ScorecardMetric("Production output", 0.0, 15.0, 90.0),
            ScorecardMetric("Downtime", 18.0, 10.0, 60.0),
            ScorecardMetric("On-time delivery", 100.0, 15.0, 95.0),
            ScorecardMetric("Defect rate", 0.0, 10.0, 2.0),
            ScorecardMetric("Labor utilization", 90.0, 8.0, 80.0),
            ScorecardMetric("Overtime", 0.0, 7.0, 10.0),
            ScorecardMetric("Energy consumption", 0.0, 5.0, 100.0),
            ScorecardMetric("Cost", 0.0, 10.0, 100000.0),
            ScorecardMetric("Customer impact", 0.0, 10.0, 20.0),
            ScorecardMetric("Inventory", 3.5, 5.0, 2.0),
            ScorecardMetric("Safety", 100.0, 5.0, 100.0),
        ],
        assumptions={
            "line-2-lost-units": DataQuality.SIMULATED,
            "line-2-fault-diagnosis": DataQuality.UNKNOWN,
            "raw-material-availability": DataQuality.SIMULATED,
        },
    )


def create_state_of_world() -> StateOfWorld:
    return StateOfWorld(create_initial_state())
