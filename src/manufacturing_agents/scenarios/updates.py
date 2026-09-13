"""Changing-information events for reconsideration tests."""

from __future__ import annotations

from manufacturing_agents.state.factory_state import StateOfWorld
from manufacturing_agents.state.models import DataQuality, LineStatus, QualityFinding


def specialized_part_update(state: StateOfWorld, *, expedited: bool = True) -> int:
    def apply(factory: object) -> None:
        part = factory.materials["part-line-2-special"]  # type: ignore[attr-defined]
        part.available = False
        part.normal_delivery_days = 5
        if expedited:
            part.expedited_delivery = "tomorrow 10:00 AM"
            part.expedited_cost_multiplier = 10.0
        factory.assumptions["line-2-repair-plan"] = DataQuality.STALE  # type: ignore[attr-defined]

    return state.update(apply)


def product_c_priority_update(state: StateOfWorld) -> int:
    def apply(factory: object) -> None:
        order = factory.orders["order-c"]  # type: ignore[attr-defined]
        order.priority = "HIGH"
        factory.inventory.finished_goods["C"] = 100  # type: ignore[attr-defined]
        factory.assumptions["product-c-inventory"] = DataQuality.VERIFIED  # type: ignore[attr-defined]

    return state.update(apply)


def line_three_quality_update(state: StateOfWorld) -> int:
    def apply(factory: object) -> None:
        factory.production_lines["line-3"].status = LineStatus.QUALITY_HOLD  # type: ignore[attr-defined]
        factory.production_lines["line-3"].quality_hold = True  # type: ignore[attr-defined]
        factory.quality_findings["quality-line-3-001"] = QualityFinding(  # type: ignore[attr-defined]
            finding_id="quality-line-3-001",
            line_id="line-3",
            description="Abnormal quality reading",
            severity="HIGH",
        )
        factory.assumptions["line-3-capacity"] = DataQuality.STALE  # type: ignore[attr-defined]

    return state.update(apply)
