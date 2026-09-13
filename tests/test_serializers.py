from manufacturing_agents.api.serializers import to_jsonable
from manufacturing_agents.data.factory_data import create_initial_state


def test_serializer_converts_enums_and_dataclasses() -> None:
    serialized = to_jsonable(create_initial_state())

    assert serialized["production_lines"]["line-2"]["status"] == "DOWN"
    assert serialized["safety"]["human_intervention_required"] is True
