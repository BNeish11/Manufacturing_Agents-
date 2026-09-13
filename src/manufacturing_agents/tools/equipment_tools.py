"""Equipment-domain tools backed by the shared State of the World."""

from __future__ import annotations

from manufacturing_agents.permissions.authority import require_permission
from manufacturing_agents.state.factory_state import StateOfWorld
from manufacturing_agents.state.models import Equipment, LineStatus


def get_machine_status(state: StateOfWorld, equipment_id: str) -> Equipment:
    return state.read(lambda factory: factory.equipment[equipment_id])  # type: ignore[return-value]


def get_fault_information(state: StateOfWorld, equipment_id: str) -> dict[str, object]:
    return state.read(
        lambda factory: {
            "equipment_id": equipment_id,
            "fault": factory.equipment[equipment_id].current_fault,
            "fault_code": factory.equipment[equipment_id].fault_code,
            "data_quality": factory.equipment[equipment_id].data_quality.value,
        }
    )  # type: ignore[return-value]


def get_maintenance_history(state: StateOfWorld, equipment_id: str) -> list[str]:
    return state.read(lambda factory: factory.equipment[equipment_id].maintenance_history)  # type: ignore[return-value]


def check_replacement_part(state: StateOfWorld, part_id: str) -> dict[str, object]:
    return state.read(
        lambda factory: vars(factory.materials[part_id]).copy()
    )  # type: ignore[return-value]


def estimate_repair_time(state: StateOfWorld, equipment_id: str) -> int | None:
    return state.read(lambda factory: factory.equipment[equipment_id].estimated_repair_minutes)  # type: ignore[return-value]


def get_maintenance_procedure(equipment_id: str) -> str:
    return f"Follow the approved maintenance procedure for {equipment_id}; isolate energy before service."


def update_machine_status(
    state: StateOfWorld,
    equipment_id: str,
    status: LineStatus,
    *,
    actor: str = "equipment",
) -> int:
    if status is LineStatus.DOWN:
        require_permission("stop_unsafe_equipment", actor)
    return state.update(lambda factory: setattr(factory.equipment[equipment_id], "status", status))


def create_maintenance_request(
    state: StateOfWorld,
    equipment_id: str,
    reason: str,
    *,
    actor: str = "equipment",
) -> int:
    require_permission("diagnose_equipment", actor)
    return state.update(
        lambda factory: factory.equipment[equipment_id].maintenance_history.append(
            f"REQUESTED: {reason}"
        )
    )
