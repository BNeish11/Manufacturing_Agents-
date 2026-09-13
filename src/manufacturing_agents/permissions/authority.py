"""Permission policy kept outside of agent prompts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Permission(str, Enum):
    AI_MAY_DECIDE = "AI MAY DECIDE"
    AI_MAY_RECOMMEND = "AI MAY RECOMMEND"
    HUMAN_APPROVAL_REQUIRED = "HUMAN APPROVAL REQUIRED"
    HUMAN_ONLY = "HUMAN ONLY"


class AuthorizationError(PermissionError):
    """Raised when an agent attempts an action outside its authority."""


@dataclass(frozen=True)
class DecisionAuthority:
    decision: str
    owner: str
    permission: Permission
    reason: str


AUTHORITY: dict[str, DecisionAuthority] = {
    "diagnose_equipment": DecisionAuthority(
        "diagnose_equipment", "equipment", Permission.AI_MAY_RECOMMEND, "Diagnosis requires evidence."
    ),
    "estimate_production_loss": DecisionAuthority(
        "estimate_production_loss", "production", Permission.AI_MAY_DECIDE, "This is a deterministic calculation."
    ),
    "recalculate_schedule": DecisionAuthority(
        "recalculate_schedule", "production", Permission.AI_MAY_RECOMMEND, "Schedule changes need system review."
    ),
    "move_production": DecisionAuthority(
        "move_production", "orchestrator", Permission.HUMAN_APPROVAL_REQUIRED, "Capacity and customer tradeoffs require approval."
    ),
    "reassign_employees": DecisionAuthority(
        "reassign_employees", "orchestrator", Permission.HUMAN_APPROVAL_REQUIRED, "Labor assignments require approval."
    ),
    "authorize_overtime": DecisionAuthority(
        "authorize_overtime", "orchestrator", Permission.HUMAN_APPROVAL_REQUIRED, "Overtime creates a labor and cost commitment."
    ),
    "notify_customer": DecisionAuthority(
        "notify_customer", "orchestrator", Permission.HUMAN_APPROVAL_REQUIRED, "Customer communication affects commitments."
    ),
    "stop_unsafe_equipment": DecisionAuthority(
        "stop_unsafe_equipment", "equipment", Permission.HUMAN_ONLY, "Safety controls cannot be overridden by AI."
    ),
    "change_customer_commitment": DecisionAuthority(
        "change_customer_commitment", "orchestrator", Permission.HUMAN_APPROVAL_REQUIRED, "Only a human can change a commitment."
    ),
    "ignore_safety_rule": DecisionAuthority(
        "ignore_safety_rule", "none", Permission.HUMAN_ONLY, "Safety rules are never bypassed."
    ),
}


def require_permission(decision: str, actor: str, *, human_approved: bool = False) -> DecisionAuthority:
    authority = AUTHORITY[decision]
    if authority.permission is Permission.AI_MAY_DECIDE:
        if authority.owner != actor:
            raise AuthorizationError(f"{actor} cannot perform {decision}.")
    elif authority.permission is Permission.AI_MAY_RECOMMEND:
        if authority.owner != actor:
            raise AuthorizationError(f"{actor} cannot recommend {decision}.")
    elif authority.permission is Permission.HUMAN_APPROVAL_REQUIRED:
        if actor != authority.owner or not human_approved:
            raise AuthorizationError(f"Human approval is required before {actor} performs {decision}.")
    else:
        raise AuthorizationError(f"{decision} is human-only and cannot be performed by {actor}.")
    return authority


def authority_for(decision: str) -> DecisionAuthority:
    return AUTHORITY[decision]
