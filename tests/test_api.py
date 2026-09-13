from manufacturing_agents.api.runtime import DashboardRuntime


def test_dashboard_runtime_uses_one_state_and_safe_events() -> None:
    runtime = DashboardRuntime()
    initial_version = runtime.state.version
    initial = runtime.dashboard()

    assert initial["lines"]["line-2"]["status"] == "DOWN"
    assert initial["version"] == initial_version
    assert "OPENAI_API_KEY" not in str(initial)

    result = runtime.run_failure()

    assert result["latest_result"]["approval"]["status"] == "PENDING"
    assert any(event["event_type"] == "workflow_completed" for event in result["events"])
    assert "CONNECTION_OK" not in str(result)


def test_scenario_update_changes_shared_state_and_clears_stale_result() -> None:
    runtime = DashboardRuntime()
    runtime.run_failure()
    previous_version = runtime.state.version

    result = runtime.apply_update("line-3-quality")

    assert runtime.state.version == previous_version + 1
    assert result["lines"]["line-3"]["status"] == "QUALITY_HOLD"
    assert result["latest_result"] is None
