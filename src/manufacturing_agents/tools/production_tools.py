"""Production-domain calculations and guarded plan proposals."""

from __future__ import annotations

from manufacturing_agents.permissions.authority import require_permission
from manufacturing_agents.state.factory_state import StateOfWorld


def get_production_status(state: StateOfWorld) -> dict[str, object]:
    return state.read(
        lambda factory: {
            line_id: {
                "status": line.status.value,
                "utilization_percent": line.utilization_percent,
                "hourly_capacity": line.hourly_capacity,
                "quality_hold": line.quality_hold,
            }
            for line_id, line in factory.production_lines.items()
        }
    )  # type: ignore[return-value]


def calculate_production_loss(state: StateOfWorld, line_id: str, downtime_minutes: int) -> int:
    capacity = state.read(lambda factory: factory.production_lines[line_id].hourly_capacity)
    return int(capacity * downtime_minutes / 60)


def get_line_capacity(state: StateOfWorld, line_id: str) -> dict[str, object]:
    return state.read(
        lambda factory: {
            "line_id": line_id,
            "hourly_capacity": factory.production_lines[line_id].hourly_capacity,
            "utilization_percent": factory.production_lines[line_id].utilization_percent,
            "supported_products": factory.production_lines[line_id].supported_products,
            "quality_hold": factory.production_lines[line_id].quality_hold,
        }
    )  # type: ignore[return-value]


def get_order_status(state: StateOfWorld) -> list[dict[str, object]]:
    return state.read(
        lambda factory: [
            {
                "order_id": order.order_id,
                "product_id": order.product_id,
                "quantity": order.quantity,
                "due_date": order.due_date,
                "priority": order.priority,
                "contractual_delivery": order.contractual_delivery,
                "status": order.status,
            }
            for order in factory.orders.values()
        ]
    )  # type: ignore[return-value]


def get_inventory_status(state: StateOfWorld) -> dict[str, object]:
    return state.read(
        lambda factory: {
            "finished_goods": factory.inventory.finished_goods,
            "work_in_progress": factory.inventory.work_in_progress,
            "raw_material_units": factory.inventory.raw_material_units,
            "days_of_inventory": factory.inventory.days_of_inventory,
        }
    )  # type: ignore[return-value]


def simulate_schedule_change(
    state: StateOfWorld,
    product_id: str,
    target_line_id: str,
    quantity: int,
) -> dict[str, object]:
    capacity = get_line_capacity(state, target_line_id)
    if capacity["quality_hold"]:
        return {"feasible": False, "reason": f"{target_line_id} is on quality hold."}
    if product_id not in capacity["supported_products"]:
        return {"feasible": False, "reason": f"{target_line_id} does not support Product {product_id}."}
    hourly_capacity = int(capacity["hourly_capacity"])
    return {
        "feasible": True,
        "line_id": target_line_id,
        "product_id": product_id,
        "quantity": quantity,
        "estimated_hours": round(quantity / hourly_capacity, 2),
    }


def calculate_delivery_impact(state: StateOfWorld, product_id: str, lost_units: int) -> dict[str, object]:
    return state.read(
        lambda factory: {
            "product_id": product_id,
            "lost_units": lost_units,
            "affected_orders": [
                order.order_id
                for order in factory.orders.values()
                if order.product_id == product_id and order.status == "OPEN"
            ],
            "contractual_risk": any(
                order.product_id == product_id and order.contractual_delivery
                for order in factory.orders.values()
            ),
        }
    )  # type: ignore[return-value]


def calculate_overtime_requirement(state: StateOfWorld, quantity: int, line_id: str) -> float:
    capacity = int(state.read(lambda factory: factory.production_lines[line_id].hourly_capacity))
    return round(quantity / capacity, 2)


def update_production_plan(
    state: StateOfWorld,
    product_id: str,
    target_line_id: str,
    quantity: int,
    *,
    actor: str = "production",
    human_approved: bool = False,
) -> int:
    require_permission("move_production", actor, human_approved=human_approved)
    result = simulate_schedule_change(state, product_id, target_line_id, quantity)
    if not result["feasible"]:
        raise ValueError(str(result["reason"]))
    return state.update(
        lambda factory: setattr(
            factory.orders[next(order_id for order_id, order in factory.orders.items() if order.product_id == product_id)],
            "status",
            f"PLAN_PROPOSED_{target_line_id}",
        )
    )
