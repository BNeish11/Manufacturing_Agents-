from manufacturing_agents.data.factory_data import create_state_of_world
from manufacturing_agents.state.models import LineStatus
from manufacturing_agents.tools.orchestrator_tools import calculate_system_severity


def test_severity_is_derived_not_the_static_seed_value() -> None:
    state = create_state_of_world()

    severity = calculate_system_severity(state)

    # The seed's hardcoded system_severity=72 must not simply pass through.
    assert severity != 72
    assert 0 <= severity <= 100


def test_severity_increases_when_additional_line_goes_down() -> None:
    state = create_state_of_world()
    before = calculate_system_severity(state)

    state.update(lambda factory: setattr(factory.production_lines["line-1"], "status", LineStatus.DOWN))
    after = calculate_system_severity(state)

    assert after > before


def test_severity_increases_with_pending_human_approval() -> None:
    from manufacturing_agents.state.models import ApprovalStatus, DecisionRecord

    state = create_state_of_world()
    before = calculate_system_severity(state)

    state.update(
        lambda factory: factory.decisions.append(
            DecisionRecord(
                decision_id="decision-test",
                timestamp="2026-01-01T00:00:00+00:00",
                trigger="test",
                state_version=state.version,
                recommendation="test",
                reasoning_summary="test",
                evidence=[],
                expected_impact={},
                risks=[],
                approval_required=True,
                approval_status=ApprovalStatus.PENDING,
            )
        )
    )
    after = calculate_system_severity(state)

    assert after > before
