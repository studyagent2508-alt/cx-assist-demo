from __future__ import annotations

import threading
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command

from .audit import persist_audit, recent_events
from .config import settings
from .data import repository
from .model_factory import build_chat_model
from .schemas import InvestigationRequest, InvestigationStarted, ReviewCompleted, ReviewRequest
from .workflow import workflow


pending_runs: dict[str, dict[str, Any]] = {}
completed_runs: dict[str, dict[str, Any]] = {}
lock = threading.Lock()


@asynccontextmanager
async def lifespan(_: FastAPI):
    repository.load()
    # Fail startup early if the selected model configuration is invalid.
    _, model_name = build_chat_model()
    app.state.model_name = model_name
    yield


app = FastAPI(title="CX Assist API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/")
def root():
    return {"application": "CX Assist API", "status": "running", "docs": "/docs"}


@app.get("/health")
def health():
    return {
        "status": "healthy", "provider": settings.model_provider,
        "model": app.state.model_name, "case_count": len(repository.datasets["cases"]),
    }


@app.get("/cases")
def cases():
    frame = repository.datasets["cases"]
    columns = [column for column in ("case_id", "issue_type", "priority", "status", "subject") if column in frame.columns]
    return frame[columns].fillna("").to_dict("records")


@app.get("/cases/{case_id}")
def case(case_id: str):
    try:
        return repository.case_context(case_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/investigations", response_model=InvestigationStarted)
def start(request: InvestigationRequest):
    case_id = request.case_id.strip().upper()
    if case_id not in set(repository.datasets["cases"]["case_id"].astype(str)):
        raise HTTPException(404, f"Unknown case_id: {case_id}")
    thread_id = f"api-{case_id}-{uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    started = time.perf_counter()
    state = workflow.invoke({"case_id": case_id}, config=config)
    interrupts = state.get("__interrupt__", [])
    if not interrupts:
        raise HTTPException(500, "Workflow did not reach human review")
    with lock:
        pending_runs[thread_id] = {"case_id": case_id, "started": started}
    return InvestigationStarted(
        thread_id=thread_id, case_id=case_id, status="awaiting_review",
        review_payload=interrupts[0].value,
    )


@app.post("/investigations/{thread_id}/review", response_model=ReviewCompleted)
def review(thread_id: str, request: ReviewRequest):
    with lock:
        run = pending_runs.get(thread_id)
    if not run:
        raise HTTPException(404, "Pending workflow not found or already reviewed")
    state = workflow.invoke(
        Command(resume=request.model_dump()),
        config={"configurable": {"thread_id": thread_id}},
    )
    audit = persist_audit(state, thread_id, time.perf_counter() - run["started"])
    with lock:
        pending_runs.pop(thread_id, None)
        completed_runs[thread_id] = {"case_id": run["case_id"], "status": state["final_status"]}
    return ReviewCompleted(
        thread_id=thread_id, case_id=run["case_id"], status=state["final_status"],
        investigation=state["investigation"], final_response=state.get("final_response"),
        audit_record=audit,
    )


@app.get("/runs/{thread_id}")
def run_status(thread_id: str):
    with lock:
        if thread_id in pending_runs:
            return {"thread_id": thread_id, "status": "awaiting_review", **pending_runs[thread_id]}
        if thread_id in completed_runs:
            return {"thread_id": thread_id, **completed_runs[thread_id]}
    raise HTTPException(404, "Run not found")


@app.get("/audit-events")
def audit_events(limit: int = Query(20, ge=1, le=100)):
    return recent_events(limit)

