"""Deterministic inventory and quality calculations over the shared state."""

from __future__ import annotations

from datetime import datetime, timezone
from math import floor
from statistics import mean
from typing import Any
from uuid import uuid4

from manufacturing_agents.state.factory_state import StateOfWorld
from manufacturing_agents.state.models import DataQuality, DefectObservation, HumanInspectionObservation


def get_inventory_status(state: StateOfWorld) -> dict[str, object]:
    return state.read(
        lambda factory: {
            "finished_goods": factory.inventory.finished_goods,
            "work_in_progress": factory.inventory.work_in_progress,
            "produced_quantity": factory.inventory.produced_quantity,
            "accepted_quantity": factory.inventory.accepted_quantity,
            "defective_quantity": factory.inventory.defective_quantity,
            "reserved_quantity": factory.inventory.reserved_quantity,
            "quality_hold_quantity": factory.inventory.quality_hold_quantity,
            "raw_material_units": factory.inventory.raw_material_units,
            "days_of_inventory": factory.inventory.days_of_inventory,
            "data_quality": factory.inventory.data_quality.value,
        }
    )  # type: ignore[return-value]


def get_material_inventory(
    state: StateOfWorld,
    material_id: str | None = None,
) -> dict[str, dict[str, object]]:
    def read(factory: Any) -> dict[str, dict[str, object]]:
        materials = factory.raw_materials
        if material_id is not None:
            materials = {material_id: materials[material_id]}
        return {
            key: {
                "material_id": material.material_id,
                "name": material.name,
                "unit": material.unit,
                "quantity_on_hand": material.quantity_on_hand,
                "quantity_reserved": material.quantity_reserved,
                "available_quantity": material.quantity_on_hand - material.quantity_reserved,
                "reorder_threshold": material.reorder_threshold,
                "critical_threshold": material.critical_threshold,
                "status": _material_status(material.quantity_on_hand, material.reorder_threshold, material.critical_threshold),
                "data_quality": material.data_quality.value,
                "source": material.source,
            }
            for key, material in materials.items()
        }

    return state.read(read)  # type: ignore[return-value]


def get_finished_goods(state: StateOfWorld, product_id: str | None = None) -> dict[str, dict[str, int]]:
    def read(factory: Any) -> dict[str, dict[str, int]]:
        product_ids = [product_id] if product_id is not None else list(factory.products)
        return {
            current_id: {
                "produced": factory.inventory.produced_quantity.get(current_id, 0),
                "accepted": factory.inventory.accepted_quantity.get(current_id, 0),
                "defective": factory.inventory.defective_quantity.get(current_id, 0),
                "finished_goods": factory.inventory.finished_goods.get(current_id, 0),
                "reserved": factory.inventory.reserved_quantity.get(current_id, 0),
                "quality_hold": factory.inventory.quality_hold_quantity.get(current_id, 0),
                "available": max(
                    0,
                    factory.inventory.finished_goods.get(current_id, 0)
                    - factory.inventory.reserved_quantity.get(current_id, 0)
                    - factory.inventory.quality_hold_quantity.get(current_id, 0),
                ),
            }
            for current_id in product_ids
        }

    return state.read(read)  # type: ignore[return-value]


def calculate_material_requirements(
    state: StateOfWorld,
    product_id: str,
    quantity: int,
) -> dict[str, object]:
    if quantity < 0:
        raise ValueError("Quantity cannot be negative.")

    def calculate(factory: Any) -> dict[str, object]:
        requirements = {}
        for material in factory.raw_materials.values():
            requirement = material.requirements_per_product.get(product_id)
            if requirement is None:
                return {"available": False, "reason": f"Missing requirement for {material.material_id}."}
            if requirement <= 0:
                raise ValueError(f"Requirement for {material.material_id} must be positive.")
            requirements[material.material_id] = requirement * quantity
        return {"available": True, "product_id": product_id, "quantity": quantity, "requirements": requirements}

    return state.read(calculate)  # type: ignore[return-value]


def calculate_max_production(state: StateOfWorld, product_id: str) -> dict[str, object]:
    def calculate(factory: Any) -> dict[str, object]:
        supports: dict[str, int] = {}
        for material in factory.raw_materials.values():
            requirement = material.requirements_per_product.get(product_id)
            if requirement is None:
                return {"available": False, "reason": f"Missing requirement for {material.material_id}."}
            if requirement <= 0:
                raise ValueError(f"Requirement for {material.material_id} must be positive.")
            if material.data_quality is DataQuality.CONFLICTING or material.quantity_on_hand < 0:
                return {"available": False, "reason": f"Invalid or conflicting quantity for {material.material_id}."}
            available = max(0.0, material.quantity_on_hand - material.quantity_reserved)
            supports[material.material_id] = floor(available / requirement)
        if not supports:
            return {"available": False, "reason": "No raw materials are configured."}
        limiting_material, maximum = min(supports.items(), key=lambda item: item[1])
        return {
            "available": True,
            "product_id": product_id,
            "maximum_supported_quantity": maximum,
            "limiting_material": limiting_material,
            "material_support": supports,
        }

    return state.read(calculate)  # type: ignore[return-value]


def check_supply_thresholds(state: StateOfWorld, material_id: str | None = None) -> dict[str, dict[str, object]]:
    materials = get_material_inventory(state, material_id)
    return {
        key: {
            **value,
            "coverage_note": "Coverage requires product mix and demand context.",
        }
        for key, value in materials.items()
    }


def calculate_defect_rate(state: StateOfWorld, product_id: str) -> dict[str, object]:
    finished = get_finished_goods(state, product_id)[product_id]
    inspected = finished["accepted"] + finished["defective"]
    rate = (finished["defective"] / inspected * 100.0) if inspected else None
    return {
        "product_id": product_id,
        "inspected_quantity": inspected,
        "defective_quantity": finished["defective"],
        "defect_rate_percent": rate,
        "status": "UNKNOWN" if rate is None else "CRITICAL" if rate > 5 else "WARNING" if rate >= 2 else "NORMAL",
    }


def calculate_weight_variance(state: StateOfWorld, product_id: str) -> dict[str, object]:
    def calculate(factory: Any) -> dict[str, object]:
        standard = factory.quality_standards.get(product_id)
        observations = [item for item in factory.weight_observations if item.product_id == product_id]
        if standard is None or not observations:
            return {"product_id": product_id, "status": "UNKNOWN", "observation_count": len(observations)}
        deviations = [((item.observed_weight_kg - standard.expected_weight_kg) / standard.expected_weight_kg) * 100 for item in observations]
        abnormal = [deviation for deviation in deviations if abs(deviation) > standard.minor_deviation_percent]
        return {
            "product_id": product_id,
            "observation_count": len(observations),
            "average_weight_kg": mean(item.observed_weight_kg for item in observations),
            "average_variance_percent": mean(deviations),
            "consecutive_abnormal": _consecutive_abnormal(deviations, standard.minor_deviation_percent),
            "status": "MAJOR_DEVIATION" if abnormal and len(abnormal) >= 3 else "MINOR_DEVIATION" if abnormal else "NORMAL",
        }

    return state.read(calculate)  # type: ignore[return-value]


def inventory_report_for_state(state: StateOfWorld) -> dict[str, object]:
    """Build a deterministic inventory report for orchestration and tests."""
    finished = get_finished_goods(state)
    products = state.read(lambda factory: list(factory.products))
    orders = state.read(lambda factory: list(factory.orders.values()))
    return {
        "state_version": state.version,
        "finished_goods": finished,
        "materials": get_material_inventory(state),
        "supported_production": {
            product_id: calculate_max_production(state, product_id)
            for product_id in products
        },
        "quality": {
            product_id: calculate_defect_rate(state, product_id)
            for product_id in products
        },
        "risks": [
            {
                "product_id": product_id,
                "risk": "AVAILABLE_INVENTORY_BELOW_OPEN_ORDER",
                "orders": [
                    order.order_id
                    for order in orders
                    if order.product_id == product_id
                    and order.status == "OPEN"
                    and finished[product_id]["available"] < order.quantity
                ],
            }
            for product_id in products
            if any(
                order.product_id == product_id
                and order.status == "OPEN"
                and finished[product_id]["available"] < order.quantity
                for order in orders
            )
        ],
    }


def record_human_inspection(
    state: StateOfWorld,
    product_id: str,
    category: str,
    severity: str,
    quantity: int,
) -> int:
    if quantity <= 0:
        raise ValueError("Inspection quantity must be positive.")
    return state.update(
        lambda factory: factory.human_inspections.append(
            HumanInspectionObservation(
                observation_id=f"inspection-{uuid4().hex[:8]}",
                product_id=product_id,
                category=category,
                severity=severity,
                quantity=quantity,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )
    )


def record_defect(
    state: StateOfWorld,
    product_id: str,
    defect_code: str,
    description: str,
    severity: str,
    quantity: int,
    *,
    line_id: str | None = None,
) -> int:
    """Record an observed defect. This is an observation only, not an accept/reject decision."""
    if quantity <= 0:
        raise ValueError("Defect quantity must be positive.")
    return state.update(
        lambda factory: factory.defects.append(
            DefectObservation(
                defect_id=f"defect-{uuid4().hex[:8]}",
                product_id=product_id,
                defect_code=defect_code,
                description=description,
                severity=severity,
                quantity=quantity,
                detected_at=datetime.now(timezone.utc).isoformat(),
                line_id=line_id,
                source="HUMAN_PROVIDED",
            )
        )
    )


def _material_status(quantity: float, reorder: float, critical: float) -> str:
    if quantity < 0:
        return "UNKNOWN"
    if quantity <= critical:
        return "CRITICAL"
    if quantity <= reorder:
        return "WARNING"
    return "NORMAL"


def _consecutive_abnormal(deviations: list[float], threshold: float) -> int:
    count = 0
    for deviation in reversed(deviations):
        if abs(deviation) > threshold:
            count += 1
        else:
            break
    return count