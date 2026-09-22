"""FastAPI application for the Manufacturing AI Control Center."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from manufacturing_agents.api.runtime import DashboardRuntime

app = FastAPI(title="Manufacturing AI Control Center")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
runtime = DashboardRuntime()
WEB_ROOT = Path(__file__).resolve().parents[3] / "web"


@app.get("/api/health")
def health() -> dict[str, object]:
    return {"status": "ok", "shared_state": "available", "events": "available"}


@app.get("/api/dashboard")
def dashboard() -> dict[str, object]:
    return runtime.dashboard()


@app.get("/api/state")
def state() -> dict[str, object]:
    return runtime.snapshot()


@app.get("/api/events")
def events() -> list[dict[str, object]]:
    return runtime.events.as_dicts()


@app.get("/api/metrics")
def metrics() -> dict[str, object]:
    return runtime.metrics()


@app.post("/api/simulation/tick")
def simulation_tick(ticks: int = 1) -> dict[str, object]:
    try:
        return runtime.advance_simulation(ticks)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/scenario/reset")
def reset() -> dict[str, object]:
    return runtime.reset()


@app.post("/api/scenario/line-2-failure")
def line_two_failure() -> dict[str, object]:
    return runtime.run_failure()


@app.post("/api/scenario/{name}")
def scenario_update(name: str) -> dict[str, object]:
    try:
        return runtime.apply_update(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown scenario update") from exc


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html")


@app.get("/styles.css")
def styles() -> FileResponse:
    return FileResponse(WEB_ROOT / "styles.css", media_type="text/css")


@app.get("/app.js")
def javascript() -> FileResponse:
    return FileResponse(WEB_ROOT / "app.js", media_type="text/javascript")


def main() -> None:
    import uvicorn

    uvicorn.run("manufacturing_agents.api.app:app", host="127.0.0.1", port=8000, reload=False)