from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .data import repository
from .model_factory import build_chat_model
from .schemas import InvestigationResult, WorkflowState


SYSTEM_PROMPT = """You are an internal customer-experience investigation copilot.
Use only supplied case data and policy excerpts. Never invent facts, reference IDs,
policy IDs, approvals, or completed actions. Put gaps in missing_information.
Customer remedies must be described as pending human review. requires_human_review
must always be true."""


def collect_ids(value: Any) -> set[str]:
    output: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith("_id") and child:
                output.add(str(child))
            output.update(collect_ids(child))
    elif isinstance(value, list):
        for child in value:
            output.update(collect_ids(child))
    return output


def validate_case(state: WorkflowState) -> dict[str, Any]:
    case_id = state.get("case_id", "").strip().upper()
    valid = set(repository.datasets["cases"]["case_id"].astype(str))
    if case_id not in valid:
        return {"case_id": case_id, "errors": [f"Unknown case_id: {case_id}"], "final_status": "validation_failed"}
    return {"case_id": case_id, "errors": [], "warnings": [], "final_status": "validated"}


def load_context(state: WorkflowState) -> dict[str, Any]:
    context = repository.case_context(state["case_id"])
    return {
        "case_context": context,
        "allowed_reference_ids": sorted(collect_ids(context) | {state["case_id"]}),
        "final_status": "context_loaded",
    }


def retrieve_policy(state: WorkflowState) -> dict[str, Any]:
    policies = repository.retrieve_policies(state["case_context"])
    return {
        "retrieved_policies": policies,
        "allowed_policy_ids": sorted({item["document_id"] for item in policies}),
        "final_status": "policies_retrieved",
    }


def evidence_check(state: WorkflowState) -> dict[str, Any]:
    context = state["case_context"]
    missing = [name for name in ("customer", "vehicle", "contract") if not context.get(name)]
    if not context.get("invoices_under_review"):
        missing.append("invoice")
    if not state.get("retrieved_policies"):
        missing.append("policy evidence")
    return {"missing_evidence": missing, "final_status": "evidence_checked"}


def investigate(state: WorkflowState) -> dict[str, Any]:
    model, _ = build_chat_model()
    prompt = {
        "case_context": state["case_context"],
        "policy_excerpts": state["retrieved_policies"],
        "allowed_reference_ids": state["allowed_reference_ids"],
        "allowed_policy_ids": state["allowed_policy_ids"],
        "deterministically_missing_evidence": state.get("missing_evidence", []),
    }
    structured_model = model.with_structured_output(InvestigationResult)
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            result = structured_model.invoke([
                ("system", SYSTEM_PROMPT),
                ("human", json.dumps(prompt, default=str)),
            ])
            return {"investigation": result.model_dump(), "final_status": "investigated"}
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(2 ** (attempt - 1))
    return {
        "errors": state.get("errors", []) + [f"Model call failed: {last_error}"],
        "final_status": "model_failed",
    }


def guardrail(state: WorkflowState) -> dict[str, Any]:
    result = InvestigationResult.model_validate(state["investigation"])
    allowed_refs = set(state["allowed_reference_ids"])
    allowed_policies = set(state["allowed_policy_ids"])
    invalid_refs = sorted({e.reference_id for e in result.evidence if e.reference_id not in allowed_refs})
    invalid_policies = sorted({p.document_id for p in result.policy_citations if p.document_id not in allowed_policies})
    result.evidence = [e for e in result.evidence if e.reference_id in allowed_refs]
    result.policy_citations = [p for p in result.policy_citations if p.document_id in allowed_policies]
    result.case_id = state["case_id"]
    result.requires_human_review = True
    result.missing_information = list(dict.fromkeys(result.missing_information + state.get("missing_evidence", [])))
    warnings = list(state.get("warnings", []))
    if invalid_refs:
        warnings.append(f"Removed ungrounded evidence IDs: {invalid_refs}")
    if invalid_policies:
        warnings.append(f"Removed ungrounded policy IDs: {invalid_policies}")
    return {"investigation": result.model_dump(), "warnings": warnings, "final_status": "guardrails_passed"}


def human_review(state: WorkflowState) -> dict[str, Any]:
    decision = interrupt({
        "instruction": "Review and resume with approve, edit, reject, or escalate.",
        "case_id": state["case_id"],
        "investigation": state["investigation"],
        "warnings": state.get("warnings", []),
    })
    return {"human_decision": decision, "final_status": "reviewed"}


def finalize(state: WorkflowState) -> dict[str, Any]:
    decision = state["human_decision"]
    action = decision["decision"].lower()
    response = None
    if action == "approve":
        response = state["investigation"]["customer_response_draft"]
    elif action == "edit":
        response = decision["edited_response"]
    return {
        "final_status": "edited_and_approved" if action == "edit" else action,
        "final_response": response,
    }


def audit(state: WorkflowState) -> dict[str, Any]:
    return {"audit_record": {
        "event_id": str(uuid4()),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "case_id": state["case_id"],
        "status": state["final_status"],
        "reviewer_id": state["human_decision"].get("reviewer_id"),
        "decision": state["human_decision"].get("decision"),
        "warnings": state.get("warnings", []),
    }}


def route(state: WorkflowState) -> Literal["continue", "stop"]:
    return "stop" if state.get("errors") else "continue"


def build_workflow():
    builder = StateGraph(WorkflowState)
    for name, node in {
        "validate_case": validate_case, "load_context": load_context,
        "retrieve_policies": retrieve_policy, "evidence_check": evidence_check, "investigate": investigate,
        "grounding_guardrail": guardrail, "human_review": human_review,
        "finalize": finalize, "audit": audit,
    }.items():
        builder.add_node(name, node)
    builder.add_edge(START, "validate_case")
    builder.add_conditional_edges("validate_case", route, {"continue": "load_context", "stop": END})
    builder.add_edge("load_context", "retrieve_policies")
    builder.add_edge("retrieve_policies", "evidence_check")
    builder.add_edge("evidence_check", "investigate")
    builder.add_conditional_edges(
        "investigate", route,
        {"continue": "grounding_guardrail", "stop": END},
    )
    builder.add_edge("grounding_guardrail", "human_review")
    builder.add_edge("human_review", "finalize")
    builder.add_edge("finalize", "audit")
    builder.add_edge("audit", END)
    return builder.compile(checkpointer=InMemorySaver())


workflow = build_workflow()
