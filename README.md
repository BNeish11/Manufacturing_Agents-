# Manufacturing AI Agent System

A terminal-first academic prototype demonstrating three specialized AI agents coordinating through one shared State of the World.

## Architecture

- **Orchestrator Agent**: `gpt-5.6-sol`, high reasoning; system-level coordination and tradeoffs.
- **Equipment Agent**: `gpt-5.6-terra`, medium reasoning; equipment, faults, maintenance, and repair.
- **Production Agent**: `gpt-5.6-terra`, medium reasoning; capacity, orders, inventory, labor, schedules, and delivery.
- **Shared state**: typed, versioned, in-memory factory state.
- **Tools**: deterministic Python functions for reads, calculations, validation, guarded mutations, and audit records.

The Orchestrator uses the OpenAI Agents SDK manager pattern: specialist agents are exposed as tools, not handoffs. Information access and action authority are separate. Safety rules cannot be overridden by an agent.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
```

For live SDK execution, create `.env` from `.env.example` and provide `OPENAI_API_KEY`. The requested model IDs remain literal in the agent definitions; account access must be verified before running live calls.

## Run the offline scenario

```powershell
python -m manufacturing_agents.main
python -m manufacturing_agents.main --approve
python -m manufacturing_agents.main --part-update --product-c-update --line-3-quality-update
```

The offline workflow does not require an API key. It demonstrates the Line 2 failure, production loss, alternative capacity, customer risk, scorecard, human approval gate, and decision record. `run_live_orchestrator` provides the opt-in `Runner` path for model-backed reasoning.

## Test

```powershell
python -m pytest
```

Tests cover state versioning, permission enforcement, quality holds, exact agent models and reasoning settings, the Line 2 workflow, and changing-information scenarios.

## Scope boundaries

This project uses simulated data only. It does not control real equipment, send customer messages, connect to factory systems, train a model, or provide a production deployment. Human approval remains required for system-level production moves, labor and overtime actions, customer commitments, and safety-sensitive decisions.

## Control Center UI

Install the project and start the local dashboard:

```powershell
python -m pip install -e "."
manufacturing-agents-ui
```

Open `http://127.0.0.1:8000`. The dashboard reads the existing shared state through a thin FastAPI adapter and polls for updates. Use **Start Line 2 Failure** to run the deterministic demonstration, then use the scenario buttons to apply new information. Human approval remains pending because the existing backend does not expose an approval mutation endpoint; the UI never bypasses that authority boundary.

The dashboard does not run the live model automatically and does not expose API credentials, prompts, or hidden reasoning.