# Manufacturing AI Agent System

A Python-based manufacturing decision-support prototype. The system models a factory with three production lines and coordinates specialized AI agents through one shared **State of the World**.

This project is intended for an academic demonstration of agent coordination, tool use, permissions, human escalation, explainability, and cascading manufacturing consequences. It uses simulated factory data and does not control real equipment.

## What The Program Does

The primary demonstration is a sudden failure on Line 2. The system evaluates:

- Equipment condition and maintenance information
- Downtime and projected production loss
- Orders, product priorities, inventory, and delivery risk
- Alternative production capacity on Lines 1 and 3
- Labor reassignment and overtime implications
- Replacement-part availability and repair timing
- Quality, safety, cost, and customer impact
- Whether a human must approve the proposed action

The workflow is deliberately system-level. Product A is high volume, Product B has the highest margin, and Product C has contractual delivery requirements. The system must consider the tradeoffs instead of treating volume as the only priority.

## Agent Architecture

```text
			    HUMAN / PLANT MANAGER
				      │
				      ▼
			    ORCHESTRATOR AGENT
			      gpt-5.6-sol / high
				      │
		   specialist agents exposed as tools
		      ┌────────────┴────────────┐
		      ▼                         ▼
	      EQUIPMENT AGENT           PRODUCTION AGENT
	      gpt-5.6-terra / medium    gpt-5.6-terra / medium
		      └────────────┬────────────┘
				     ▼
			 STATE OF THE WORLD
			    one shared state
```

### Orchestrator Agent

The Orchestrator is the system-level decision owner. It compares specialist reports, evaluates factory-wide tradeoffs, calculates impact, identifies conflicts, requests human approval, and records decisions.

Model: `gpt-5.6-sol`  
Reasoning effort: `high`

### Equipment Agent

The Equipment Agent handles machine status, faults, maintenance history, replacement parts, repair procedures, and estimated repair time. It can recommend equipment actions but cannot independently reschedule factory production.

Model: `gpt-5.6-terra`  
Reasoning effort: `medium`

### Production Agent

The Production Agent handles capacity, production loss, orders, inventory, alternative lines, scheduling, overtime, and delivery impact. It provides production recommendations but cannot override Orchestrator authority.

Model: `gpt-5.6-terra`  
Reasoning effort: `medium`

The Orchestrator uses the OpenAI Agents SDK manager pattern. The specialist agents are called as tools rather than taking control through handoffs.

## Important Design Rules

- There is exactly one shared State of the World.
- Agents do not create independent copies of factory reality.
- Python tools provide structured data, calculations, validation, permissions, and state changes.
- The LLM provides interpretation and flexible reasoning.
- Information access does not grant action authority.
- Safety rules cannot be bypassed by AI.
- Human approval is required for system-level production moves, labor changes, overtime, customer commitments, and other high-impact actions.
- Unknown or conflicting data is represented as unknown or conflicting rather than invented.
- Decision records contain evidence, concise reasoning summaries, risks, expected impact, approval status, and outcomes.
- Hidden chain-of-thought is not exposed; the system displays concise explanations and auditable evidence instead.

## Requirements

- Python 3.11 or newer
- An OpenAI API key for live model calls
- Internet access for OpenAI API calls
- Windows PowerShell commands below assume the project root is the current directory

The offline workflow and tests do not require an API key.

## Installation

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the project and test dependencies:

```powershell
python -m pip install -e ".[test]"
```

The project dependencies include:

- `openai-agents` for `Agent` and `Runner`
- `python-dotenv` for loading the local `.env` file
- `fastapi` and `uvicorn` for the visualization API
- `pytest` through the optional `test` dependency

## Environment Configuration

Create a local `.env` file from the template:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` locally and set:

```text
OPENAI_API_KEY=your-real-api-key
```

Do not paste the key into source files, README files, terminal output, commits, or chat. `.env` is intentionally listed in `.gitignore`; `.env.example` is only a placeholder template.

The workflow loads `.env` with `load_dotenv()` before the OpenAI Agents SDK runner is used. Never print the value when testing configuration.

## Run The Offline Demonstration

Run the deterministic Line 2 failure workflow:

```powershell
python -m manufacturing_agents.main
```

The command prints a JSON decision packet containing the recommendation, evidence, expected impact, risks, scorecard, approval requirement, and decision ID. It does not call the live model.

Simulate the human-approved branch:

```powershell
python -m manufacturing_agents.main --approve
```

Apply the changing-information scenarios to the same in-memory state:

```powershell
python -m manufacturing_agents.main --part-update
python -m manufacturing_agents.main --product-c-update
python -m manufacturing_agents.main --line-3-quality-update
```

Run all three updates together:

```powershell
python -m manufacturing_agents.main --part-update --product-c-update --line-3-quality-update
```

The deterministic workflow uses the seeded scenario values, including Line 2 downtime, current and projected loss, alternative capacity, affected employees, inventory, and severity. The scenario update flags mutate the shared state after the initial assessment; a production deployment would re-run the assessment after each new event.

## Run The Control Center UI

Start the local FastAPI dashboard with the active Python environment:

```powershell
python -m uvicorn manufacturing_agents.api.app:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/
```

The UI includes:

- Factory severity and safety status
- Line 1, Line 2, and Line 3 status
- Equipment and production agent model/status cards
- Shared State of the World snapshot
- Inventory, orders, labor, and quality information
- Current decision and approval status
- Cascading manufacturing impact
- Safe event journal
- Scenario controls for Line 2 failure and information updates

The dashboard polls the API and reads operational values from the backend-owned shared state. It does not maintain a second operational state. The dashboard does not automatically run the live model, approve actions, control equipment, or send customer messages.

The UI currently represents approval as pending because no approval mutation endpoint has been added. This prevents the browser from bypassing the existing authority model.

## API Endpoints

The local server exposes:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Check API, shared state, and event availability |
| `GET` | `/api/dashboard` | Get the dashboard aggregate |
| `GET` | `/api/state` | Get the serialized State of the World |
| `GET` | `/api/events` | Get safe dashboard events |
| `POST` | `/api/scenario/reset` | Reset the runtime-owned state |
| `POST` | `/api/scenario/line-2-failure` | Run the deterministic Line 2 assessment |
| `POST` | `/api/scenario/part` | Apply the replacement-part update |
| `POST` | `/api/scenario/product-c` | Apply the Product C priority update |
| `POST` | `/api/scenario/line-3-quality` | Put Line 3 on quality hold |

Example health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

## Live Model Execution

The live SDK path is available through `run_live_orchestrator()` in `src/manufacturing_agents/orchestration/workflow.py`. It creates the existing Orchestrator and calls `Runner.run()` with the configured model.

The live path requires:

1. A valid `OPENAI_API_KEY` in `.env`.
2. Account access to `gpt-5.6-sol` and the specialist models.
3. Available API credits and service access.

Run a minimal connection test before a full scenario. Do not print the key or raw exception data. A connection test does not run the manufacturing workflow.

The dashboard does not trigger live model calls automatically. This is intentional so that opening the UI does not unexpectedly spend API credits or execute an agent action.

## Project Structure

```text
manufacturing_agents/
├── agents/
│   ├── contracts.py       # Agent contracts and structured reports
│   ├── equipment.py       # Equipment Agent
│   ├── inventory.py       # Inventory and quality Agent
│   ├── orchestrator.py    # Orchestrator and specialist-as-tools wiring
│   └── production.py      # Production Agent
├── api/
│   ├── app.py             # FastAPI routes and static UI serving
│   ├── events.py          # Bounded safe event journal
│   ├── runtime.py         # API-owned runtime using one shared state
│   └── serializers.py     # JSON-safe dataclass/enum serialization
├── communication/
│   └── messages.py        # Versioned agent communication envelopes
├── data/
│   └── factory_data.py    # Simulated factory seed data
├── orchestration/
│   └── workflow.py        # Line 2 workflow and live Runner wrapper
├── permissions/
│   └── authority.py       # Decision ownership and approval rules
├── scenarios/
│   └── updates.py         # Changing-information scenario events
├── state/
│   ├── factory_state.py   # Versioned shared State of the World
│   └── models.py          # Typed factory and decision models
└── tools/
    ├── equipment_tools.py
	├── inventory_tools.py
    ├── orchestrator_tools.py
    └── production_tools.py

web/
├── app.js                 # API polling and presentation rendering
├── index.html             # Dashboard structure
└── styles.css             # Operations-center visual system
```

## Testing

Run the full offline suite:

```powershell
python -m pytest
```

The tests cover:

- Shared-state versioning and snapshot isolation
- Seeded Line 2 failure data
- Equipment and production tool calculations
- Permission and quality-hold enforcement
- Exact agent models and reasoning settings
- Manager-style specialist tool wiring
- Scenario updates
- Workflow approval status
- API serialization and dashboard runtime behavior
- Safe event and response behavior

No automated test makes a live OpenAI call. Live calls should be explicit and isolated from the offline test suite.

## Operational Limitations

## What The Program Does


- Connect to MES, ERP, WMS, supplier, warehouse, or shipping systems
- Control real machines or production lines
- Send customer notifications
- Automatically approve recommendations
- Provide authentication or multi-user access control
- Persist state in a database
- Guarantee real-time agent token/activity streaming
- Replace plant-manager judgment or safety procedures

The UI is a monitoring window into the backend, not a replacement for the agents, shared state, tools, permissions, or human authority model.
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
			    
### Inventory Agent

The Inventory Agent is the specialist source of inventory and quality intelligence. It calculates accepted, defective, reserved, and available finished goods; evaluates raw-material thresholds; determines material-supported production and limiting materials; and monitors quality and weight observations. It can recommend and escalate, but cannot schedule production, purchase supplies, change customer commitments, or override safety and Orchestrator authority.

Model: `gpt-5.6-terra`  
Reasoning effort: `medium`
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