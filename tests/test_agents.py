from manufacturing_agents.agents.equipment import build_equipment_agent
from manufacturing_agents.agents.inventory import build_inventory_agent
from manufacturing_agents.agents.orchestrator import build_orchestrator_agent
from manufacturing_agents.agents.production import build_production_agent
from manufacturing_agents.data.factory_data import create_state_of_world


def test_agents_use_required_models_and_reasoning() -> None:
    state = create_state_of_world()
    equipment = build_equipment_agent(state)
    production = build_production_agent(state)
    inventory = build_inventory_agent(state)
    orchestrator = build_orchestrator_agent(state)

    assert equipment.model == "gpt-5.6-terra"
    assert production.model == "gpt-5.6-terra"
    assert inventory.model == "gpt-5.6-terra"
    assert orchestrator.model == "gpt-5.6-sol"
    assert equipment.model_settings.reasoning.effort == "medium"
    assert production.model_settings.reasoning.effort == "medium"
    assert inventory.model_settings.reasoning.effort == "medium"
    assert orchestrator.model_settings.reasoning.effort == "high"
    assert any(tool.name == "consult_equipment_agent" for tool in orchestrator.tools)
    assert any(tool.name == "consult_production_agent" for tool in orchestrator.tools)
    assert any(tool.name == "consult_inventory_agent" for tool in orchestrator.tools)
