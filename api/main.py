"""HTTP API for the Instant Solver.

Two shapes for the same operation:

``POST /api/solve``
    Synchronous. Returns the complete result once the pipeline finishes.
    Right for scripts, batch jobs and the public API.

``POST /api/solve/stream``
    Server-Sent Events. Emits each pipeline stage as it happens, then the full
    result. Right for the web UI: a solve takes tens of seconds and a spinner
    over a blank screen is the difference between "it's thinking" and "it's
    broken". Watching the stages also teaches — the user sees the budget being
    derived and the counterexample hunt running, which is most of the value.
"""
from __future__ import annotations

import asyncio
import json
import os
import queue
import threading
import time
from typing import Any, Iterator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import Solver, SolveConfig                     # noqa: E402
from engine.ingest import ingest                           # noqa: E402
from engine.models import Language, Stage                  # noqa: E402
from engine.providers import build_provider                # noqa: E402
from engine.sandbox import (                               # noqa: E402
    CompileError, available_languages, compile_source, pick_runner,
)

app = FastAPI(
    title="Instant Solver API",
    version="0.1.0",
    description="Solve a competitive programming problem, verify the solution, explain it.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CPSOLVE_CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_provider = None
_provider_lock = threading.Lock()

# A solve compiles and runs hundreds of programs, so a public server must cap how
# many run at once. Past the cap a request is refused with 503 instead of queued:
# a queue only turns overload into timeouts for everyone.
_solve_slots = threading.BoundedSemaphore(int(os.environ.get("CPSOLVE_MAX_SOLVES", "2")))
_run_slots = threading.BoundedSemaphore(int(os.environ.get("CPSOLVE_MAX_RUNS", "4")))


SOLVE_STREAM_TIMEOUT_S = 15 * 60


def _take(slots: threading.BoundedSemaphore) -> None:
    if not slots.acquire(blocking=False):
        raise HTTPException(503, "The server is busy. Try again in a few seconds.")


def get_provider():
    """Build the provider once; it holds a client and a retrieval cache."""
    global _provider
    with _provider_lock:
        if _provider is None:
            _provider = build_provider()
        return _provider


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------

class SolveRequest(BaseModel):
    statement: str = Field(..., min_length=10, max_length=60_000,
                           description="The problem statement, pasted as-is.")
    sample_input: str = Field("", max_length=200_000)
    sample_output: str = Field("", max_length=200_000)
    title: str = Field("", max_length=200)
    language: str = Field("cpp", description="cpp | c | python | java")
    stress: bool = True
    perf_probe: bool = True
    explain: bool = True
    max_attempts: int = Field(4, ge=1, le=6)
    stress_cases: int = Field(400, ge=0, le=5000)


class RunRequest(BaseModel):
    """Run arbitrary code on a custom input — the 'custom test' panel."""
    code: str = Field(..., min_length=1, max_length=200_000)
    language: str = "cpp"
    stdin: str = Field("", max_length=1_000_000)
    time_limit_ms: int = Field(5000, ge=100, le=15_000)
    memory_limit_mb: int = Field(256, ge=16, le=1024)


class AnalyzeRequest(BaseModel):
    statement: str = Field(..., min_length=10, max_length=60_000)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _language(name: str) -> Language:
    try:
        return Language(name.lower())
    except ValueError:
        raise HTTPException(400, f"Unsupported language '{name}'. "
                                 f"Supported: {', '.join(l.value for l in Language)}")


def _config(req: SolveRequest) -> SolveConfig:
    return SolveConfig(
        language=_language(req.language),
        max_attempts=req.max_attempts,
        stress_cases=req.stress_cases,
        run_stress=req.stress and req.stress_cases > 0,
        run_perf_probe=req.perf_probe,
        explain=req.explain,
    )


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    provider = get_provider()
    return {
        "status": "ok",
        "version": app.version,
        "provider": getattr(provider, "name", "unknown"),
        "model_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "sandbox": pick_runner().name,
        "languages": available_languages(),
    }


@app.post("/api/analyze")
def analyze_only(req: AnalyzeRequest) -> dict:
    """Parse and analyse without solving — instant, and free.

    Useful on its own: it shows the user the complexity budget their constraints
    imply before any code exists, which is the single most transferable habit in
    competitive programming.
    """
    from engine.analyze import analyze as run_analysis
    problem = ingest(req.statement)
    analysis = run_analysis(problem)
    return {
        "title": problem.title,
        "time_limit_ms": problem.time_limit_ms,
        "memory_limit_mb": problem.memory_limit_mb,
        "max_n": problem.max_n,
        "max_value": problem.max_value,
        "multi_test": problem.multi_test,
        "interactive": problem.interactive,
        "output_is_float": problem.output_is_float,
        "constraints": [
            {"symbol": c.symbol, "lo": c.lo, "hi": c.hi, "kind": c.kind}
            for c in problem.constraints
        ],
        "topics": analysis.topics,
        "difficulty": analysis.difficulty_estimate,
        "rating_estimate": analysis.rating_estimate,
        "budget": {
            "ops": analysis.budget.ops_budget,
            "allowed": analysis.budget.allowed,
            "forbidden": analysis.budget.forbidden,
            "reasoning": analysis.budget.reasoning,
        } if analysis.budget else None,
        "candidate_techniques": analysis.candidate_techniques,
        "pitfalls": analysis.pitfalls,
    }


@app.post("/api/solve")
def solve(req: SolveRequest) -> dict:
    config = _config(req)
    _take(_solve_slots)
    try:
        solver = Solver(provider=get_provider(), config=config)
        result = solver.solve_text(req.statement, req.sample_input, req.sample_output,
                                   title=req.title)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    finally:
        _solve_slots.release()
    payload = result.to_dict()
    payload["headline"] = result.headline()
    return payload


@app.post("/api/solve/stream")
def solve_stream(req: SolveRequest) -> StreamingResponse:
    """Stream pipeline stages as they happen, then the final result."""
    config = _config(req)
    _take(_solve_slots)   # released by the worker thread when the solve ends
    events: "queue.Queue[Optional[tuple[str, Any]]]" = queue.Queue()

    def on_progress(stage: Stage, message: str, extra: dict) -> None:
        events.put(("stage", {
            "stage": stage.value, "message": message,
            "ok": extra.get("ok", True), "at": round(time.time() * 1000),
            **{k: v for k, v in extra.items() if k != "ok"},
        }))

    def work() -> None:
        try:
            solver = Solver(provider=get_provider(), config=config)
            result = solver.solve_text(req.statement, req.sample_input, req.sample_output,
                                       title=req.title, progress=on_progress)
            payload = result.to_dict()
            payload["headline"] = result.headline()
            events.put(("result", payload))
        except Exception as exc:                            # noqa: BLE001
            events.put(("error", {"message": str(exc)}))
        finally:
            _solve_slots.release()
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream() -> Iterator[str]:
        yield _sse("open", {"ok": True})
        # One model call can think for minutes without a stage event, so the
        # stream sends SSE comments as keepalives (proxies drop idle
        # connections) and only gives up on the solve as a whole.
        deadline = time.monotonic() + SOLVE_STREAM_TIMEOUT_S
        while True:
            try:
                item = events.get(timeout=15)
            except queue.Empty:
                if time.monotonic() > deadline:
                    yield _sse("error", {"message": "The solve timed out."})
                    return
                yield ": keepalive\n\n"
                continue
            if item is None:
                yield _sse("done", {"ok": True})
                return
            yield _sse(item[0], item[1])

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"},
    )


@app.post("/api/run")
def run_custom(req: RunRequest) -> dict:
    """Compile and run code on a custom input, inside the same sandbox."""
    language = _language(req.language)
    _take(_run_slots)
    try:
        try:
            program = compile_source(req.code, language, pick_runner())
        except CompileError as exc:
            return {"verdict": "COMPILATION_ERROR", "compile_log": exc.log,
                    "stdout": "", "stderr": "", "time_ms": 0, "memory_kb": 0}

        try:
            result = program.run(req.stdin, req.time_limit_ms, req.memory_limit_mb)
        finally:
            program.cleanup()
    finally:
        _run_slots.release()

    return {
        "verdict": result.verdict.value,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "time_ms": result.time_ms,
        "memory_kb": result.memory_kb,
        "message": result.message,
        "compile_log": "",
    }


@app.get("/api/examples")
def examples() -> list[dict]:
    """Starter problems, so a first-time visitor can see a solve in one click."""
    from tests import problems as sample_problems
    return [
        {"key": key, "title": p["title"], "statement": p["statement"],
         "sample_input": p["sample_input"], "sample_output": p["sample_output"]}
        for key, p in sample_problems.ALL.items()
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
