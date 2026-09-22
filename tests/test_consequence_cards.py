from manufacturing_agents.data.factory_data import create_state_of_world
from manufacturing_agents.state.models import LineStatus
from manufacturing_agents.tools.orchestrator_tools import calculate_consequence_cards


def _card(cards, subject):
    return next(card for card in cards if card["subject"] == subject)


def test_consequence_cards_reflect_seeded_line_two_failure() -> None:
    state = create_state_of_world()

    cards = calculate_consequence_cards(state)
    subjects = {card["subject"] for card in cards}

    assert subjects == {"EQUIPMENT", "PRODUCTION", "INVENTORY", "SAFETY", "QUALITY", "CUSTOMER"}
    assert _card(cards, "EQUIPMENT")["status"] == "CRITICAL"
    assert _card(cards, "PRODUCTION")["status"] == "CRITICAL"
    assert _card(cards, "CUSTOMER")["status"] == "CRITICAL"  # order-c is contractual and under-stocked


def test_consequence_cards_are_normal_when_lines_recover() -> None:
    state = create_state_of_world()
    state.update(lambda factory: setattr(factory.equipment["equipment-2"], "status", LineStatus.RUNNING))
    state.update(lambda factory: setattr(factory.production_lines["line-2"], "status", LineStatus.RUNNING))

    cards = calculate_consequence_cards(state)

    assert _card(cards, "EQUIPMENT")["status"] == "NORMAL"
    assert _card(cards, "PRODUCTION")["status"] == "NORMAL"
