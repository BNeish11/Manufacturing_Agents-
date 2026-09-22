"""Hidden simulated ground truth, kept out of Shared State and never read by agent tools.

Agents only ever see the observable Equipment fields in FactoryState (status,
symptoms, estimated repair time). This store holds what "actually" happened in
the simulation so evaluation code can score how good an agent's inferred
diagnosis is, without the diagnosis tool ever importing this module.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EquipmentGroundTruth:
    equipment_id: str
    actual_fault: str
    actual_repair_minutes: int


class GroundTruthStore:
    """Simulation-only source of truth, separate from the agent-visible Shared State."""

    def __init__(self) -> None:
        self._facts: dict[str, EquipmentGroundTruth] = {
            # Simulation assumption: matches the seeded Line 2 scenario in factory_data.py.
            "equipment-2": EquipmentGroundTruth("equipment-2", "bearing failure", 137),
        }

    def get(self, equipment_id: str) -> EquipmentGroundTruth | None:
        return self._facts.get(equipment_id)

    def score_confidence(self, equipment_id: str, candidate_diagnosis: str | None) -> float:
        """Evaluation-only scoring of a diagnosis candidate against hidden ground truth."""
        fact = self._facts.get(equipment_id)
        if fact is None or not candidate_diagnosis:
            return 0.0
        keyword = candidate_diagnosis.split("_")[0].lower()
        return 1.0 if keyword in fact.actual_fault.lower() else 0.0
