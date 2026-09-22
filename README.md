# Manufacturing AI Agent System

A Python-based manufacturing decision-support prototype. The system models a factory with three production lines and coordinates four specialized AI agents through one shared **State of the World**, backed by a persistent, seeded SQLite factory database and a deterministic simulation engine.

This project is an academic demonstration of agent coordination, tool use, permissions, human escalation, explainability, ground-truth-versus-observed reasoning, and cascading manufacturing consequences. It uses simulated factory data and does not control real equipment.

## What The Program Does

The primary demonstration is a sudden failure on Line 2, now one scenario inside a broader, ticking factory simulation. The system evaluates:

- Equipment condition, sensor symptoms, and maintenance information
- Downtime and projected production loss
- Orders, product priorities, inventory, and delivery risk
- Alternative production capacity on Lines 1 and 3
- Labor reassignment and overtime implications
- Replacement-part availability and repair timing
- Quality, defects, weight anomalies, safety, cost, and customer impact
- Whether a human must approve the proposed action

The workflow is deliberately system-level. Product A (12x12) is high volume, Product B (24x24) has the highest margin, and Product C (36x36) has contractual delivery requirements. The system must consider the tradeoffs instead of treating volume as the only priority.

## Agent Architecture

```text
			    HUMAN / PLANT MANAGER
				      │
				      ▼
			    ORCHESTRATOR AGENT
			      gpt-5.6-sol / high
				      │
		   specialist agents exposed as tools
	   ┌──────────────────┼──────────────────┐
	   ▼                  ▼                  ▼
EQUIPMENT AGENT     PRODUCTION AGENT    INVENTORY AGENT
gpt-5.6-terra/med   gpt-5.6-terra/med   gpt-5.6-terra/med
	   └──────────────────┼──────────────────┘
				  ▼
			 STATE OF THE WORLD
			    one shared state
				  ▲
			  simulation engine
				  ▲
			  SQLite factory database
```

### Orchestrator Agent

The system-level decision owner. It compares specialist reports, evaluates factory-wide tradeoffs, calculates impact, detects conflicts between independent data sources, requests human approval, and records decisions.

Model: `gpt-5.6-sol` · Reasoning effort: `high`

### Equipment Agent

Handles machine status, faults, maintenance history, replacement parts, repair procedures, and estimated repair time. It can infer a candidate diagnosis with a confidence score from observable sensor symptoms (temperature, vibration, health score), but never sees or asserts hidden ground truth. It cannot independently reschedule factory production.

Model: `gpt-5.6-terra` · Reasoning effort: `medium`

### Production Agent

Handles capacity, production loss, orders, inventory, alternative lines, scheduling, overtime, and delivery impact. It provides production recommendations but cannot override Orchestrator authority.

Model: `gpt-5.6-terra` · Reasoning effort: `medium`

### Inventory Agent

The specialist source of inventory and quality intelligence. It calculates accepted, defective, reserved, and available finished goods; evaluates raw-material thresholds; determines material-supported production and limiting materials; monitors weight observations and repeated-versus-single deviations; and records defect observations. Recording a defect is an observation only, never an accept/reject decision. It cannot schedule production, purchase supplies, change customer commitments, or override safety and Orchestrator authority.

Model: `gpt-5.6-terra` · Reasoning effort: `medium`

The Orchestrator uses the OpenAI Agents SDK manager pattern. The specialist agents are called as tools rather than taking control through handoffs.

## Important Design Rules

- There is exactly one shared State of the World; agents do not create independent copies of factory reality.
- Python tools provide structured data, calculations, validation, permissions, and state changes. The LLM provides interpretation and flexible reasoning.
- Information access does not grant action authority. Safety rules cannot be bypassed by AI.
- Human approval is required for system-level production moves, labor changes, overtime, customer commitments, and other high-impact actions.
- Unknown or conflicting data is represented as unknown or conflicting rather than invented.
- Hidden simulated ground truth (for example, the real Line 2 failure cause) is never exposed directly to agents; agents only see observable symptoms and must infer with an explicit confidence score.
- Decision records contain evidence, concise reasoning summaries, risks, expected impact, approval status, and outcomes. Hidden chain-of-thought is never exposed.

## Requirements

- Python 3.11 or newer
- An OpenAI API key for live model calls
- Internet access for OpenAI API calls
- Windows PowerShell commands below assume the project root is the current directory

The offline workflow, simulation engine, and tests do not require an API key.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
```

Project dependencies include `openai-agents` (`Agent`/`Runner`), `python-dotenv`, `fastapi`/`uvicorn` for the visualization API, and `pytest` (via the optional `test` extra). Persistence uses Python's built-in `sqlite3`; no extra database dependency is required.

## Environment Configuration

```powershell
Copy-Item .env.example .env
```

Then edit `.env` locally and set `OPENAI_API_KEY=your-real-api-key`. Do not paste the key into source files, README files, terminal output, commits, or chat. `.env` is listed in `.gitignore`; `.env.example` is only a placeholder template. The workflow loads `.env` with `load_dotenv()` before the OpenAI Agents SDK runner is used; never print the key when testing configuration.

## Run The Offline Demonstration

```powershell
python -m manufacturing_agents.main
python -m manufacturing_agents.main --approve
python -m manufacturing_agents.main --part-update --product-c-update --line-3-quality-update
```

The command prints a JSON decision packet with the recommendation, evidence, expected impact, risks, scorecard, approval requirement, and decision ID. It does not call the live model. The scenario update flags mutate the shared state after the initial assessment.

## The Factory Database And Simulation Engine

A SQLite database ([data/database.py](src/manufacturing_agents/data/database.py)) is the persistent representation of the simulated factory: lines, equipment, products, raw materials and BOM requirements, suppliers, orders, employees, inventory, quality/weight/defect history, scenarios, and simulation run metadata.

A deterministic, seeded simulation engine ([simulation/engine.py](src/manufacturing_agents/simulation/engine.py)) advances a simulated clock in fixed ticks and applies probabilistic-but-reproducible events (equipment degradation, material consumption, supplier delay, quality anomalies, product defects, employee absence, Line 2 recovery) directly onto the same `StateOfWorld` instance the agents read — there is no second copy of reality. Applied events are also mirrored into dedicated database history tables (equipment measurements, weight measurements, defects, material inventory) for later analysis. The same seed always reproduces the same event sequence.

A hidden ground-truth store ([simulation/ground_truth.py](src/manufacturing_agents/simulation/ground_truth.py)) records what actually happened in the simulation (for example, the real Line 2 failure cause and repair time) strictly for evaluation scoring. It is never merged into Shared State and is never read by any agent tool; agents can only infer a diagnosis from observable symptoms.

An analytics module ([analytics.py](src/manufacturing_agents/analytics.py)) computes measurable, Python-derived evaluation metrics (downtime, production loss, defect rates, material shortages, weight anomalies, pending approvals) from Shared State and the database, and records reproducible run metadata (seed, tick count, final state version, metrics snapshot) for comparing scenarios.

## Run The Control Center UI

```powershell
python -m uvicorn manufacturing_agents.api.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`. The UI includes:

- Factory severity and safety status; Line 1, Line 2, and Line 3 status
- Equipment and agent model/status cards
- Shared State of the World snapshot, including inventory, orders, labor, and quality information
- Simulation clock (tick count and simulated time) and an "Advance Simulation" control
- Measured evaluation metrics panel
- Current decision and approval status
- Cascading manufacturing impact and a safe event journal
- Scenario controls for Line 2 failure and information updates

The dashboard polls the API and reads operational values from the backend-owned shared state; it does not maintain a second operational state, run the live model automatically, approve actions, control equipment, or send customer messages. Approval remains pending because no approval mutation endpoint has been added, which prevents the browser from bypassing the existing authority model.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Check API, shared state, and event availability |
| `GET` | `/api/dashboard` | Get the dashboard aggregate, including simulation clock and metrics |
| `GET` | `/api/state` | Get the serialized State of the World |
| `GET` | `/api/events` | Get safe dashboard events |
| `GET` | `/api/metrics` | Get measured evaluation metrics |
| `POST` | `/api/simulation/tick` | Advance the simulation clock (optional `ticks` query parameter, default 1) |
| `POST` | `/api/scenario/reset` | Reset the runtime-owned state and reseed the factory database |
| `POST` | `/api/scenario/line-2-failure` | Run the deterministic Line 2 assessment |
| `POST` | `/api/scenario/part` | Apply the replacement-part update |
| `POST` | `/api/scenario/product-c` | Apply the Product C priority update |
| `POST` | `/api/scenario/line-3-quality` | Put Line 3 on quality hold |

Example health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

## Live Model Execution

The live SDK path is available through `run_live_orchestrator()` in `src/manufacturing_agents/orchestration/workflow.py`. It creates the existing Orchestrator and calls `Runner.run()` with the configured model. The live path requires a valid `OPENAI_API_KEY` in `.env`, account access to `gpt-5.6-sol` and the specialist models, and available API credits and service access. Run a minimal connection test before a full scenario; do not print the key or raw exception data. The dashboard does not trigger live model calls automatically.

## Project Structure

```text
manufacturing_agents/
├── agents/
│   ├── contracts.py        # Agent contracts and structured reports
│   ├── equipment.py        # Equipment Agent
│   ├── inventory.py        # Inventory and quality Agent
│   ├── orchestrator.py     # Orchestrator, specialist-as-tools, conflict detection
│   └── production.py       # Production Agent
├── analytics.py            # Evaluation metrics and reproducible run metadata
├── api/
│   ├── app.py               # FastAPI routes and static UI serving
│   ├── events.py            # Bounded safe event journal
│   ├── runtime.py           # API-owned runtime: shared state + simulation engine
│   └── serializers.py       # JSON-safe dataclass/enum serialization
├── communication/
│   └── messages.py         # Versioned agent communication envelopes
├── data/
│   ├── database.py         # SQLite schema, seed data, connection helper
│   └── factory_data.py     # Simulated in-memory factory seed data
├── orchestration/
│   └── workflow.py         # Line 2 workflow and live Runner wrapper
├── permissions/
│   └── authority.py        # Decision ownership and approval rules
├── scenarios/
│   └── updates.py          # Changing-information scenario events
├── simulation/
│   ├── clock.py             # Deterministic simulated clock
│   ├── engine.py             # Seeded event loop, database sync
│   ├── events.py             # Individual seeded factory events
│   └── ground_truth.py       # Hidden simulated truth, evaluation-only
├── state/
│   ├── factory_state.py    # Versioned shared State of the World
│   └── models.py           # Typed factory and decision models
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

```powershell
python -m pytest
```

The tests cover:

- Shared-state versioning and snapshot isolation ([test_state.py](tests/test_state.py))
- Seeded Line 2 failure data and the deterministic workflow ([test_workflow.py](tests/test_workflow.py))
- Equipment, production, and inventory tool calculations ([test_inventory.py](tests/test_inventory.py), [test_permissions_and_tools.py](tests/test_permissions_and_tools.py))
- Permission and quality-hold enforcement
- Exact agent models, reasoning settings, and manager-style specialist tool wiring ([test_agents.py](tests/test_agents.py))
- Scenario updates ([test_scenarios.py](tests/test_scenarios.py))
- SQLite schema initialization and seed data ([test_database.py](tests/test_database.py))
- Deterministic, seed-reproducible simulation ticks and database sync ([test_simulation.py](tests/test_simulation.py))
- Ground-truth isolation, symptom-based diagnosis, defect observations, and conflict detection ([test_ground_truth.py](tests/test_ground_truth.py))
- Evaluation metrics and reproducible run metadata ([test_analytics.py](tests/test_analytics.py))
- API serialization and dashboard runtime behavior, including simulation/metrics endpoints ([test_api.py](tests/test_api.py), [test_serializers.py](tests/test_serializers.py))

No automated test makes a live OpenAI call. Live calls should be explicit and isolated from the offline test suite.

## Scope Boundaries

This project uses simulated data only. It does not:

- Connect to MES, ERP, WMS, supplier, warehouse, or shipping systems
- Control real machines or production lines
- Send customer notifications
- Automatically approve recommendations
- Provide authentication or multi-user access control
- Guarantee real-time agent token/activity streaming
- Replace plant-manager judgment or safety procedures

Human approval remains required for system-level production moves, labor and overtime actions, customer commitments, and safety-sensitive decisions. The UI is a monitoring window into the backend, not a replacement for the agents, shared state, tools, permissions, or human authority model.