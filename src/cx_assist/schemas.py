from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field, model_validator


class EvidenceItem(BaseModel):
    source_system: str
    reference_id: str
    fact: str


class PolicyCitation(BaseModel):
    document_id: str
    version: str
    section: str
    relevance: str


class InvestigationResult(BaseModel):
    case_id: str
    issue_type: str
    case_summary: str
    verified_facts: list[str]
    evidence: list[EvidenceItem]
    policy_citations: list[PolicyCitation]
    missing_information: list[str]
    recommended_action: str
    approval_level: str
    confidence: float = Field(ge=0, le=1)
    requires_human_review: bool = True
    customer_response_draft: str


class WorkflowState(TypedDict, total=False):
    case_id: str
    case_context: dict[str, Any]
    retrieved_policies: list[dict[str, Any]]
    investigation: dict[str, Any]
    allowed_reference_ids: list[str]
    allowed_policy_ids: list[str]
    missing_evidence: list[str]
    warnings: list[str]
    errors: list[str]
    human_decision: dict[str, Any]
    final_status: str
    final_response: str | None
    audit_record: dict[str, Any]


class InvestigationRequest(BaseModel):
    case_id: str = Field(min_length=1)


class ReviewRequest(BaseModel):
    decision: Literal["approve", "edit", "reject", "escalate"]
    reviewer_id: str = Field(min_length=1)
    comments: str = ""
    edited_response: str | None = None

    @model_validator(mode="after")
    def validate_edit(self):
        if self.decision == "edit" and not self.edited_response:
            raise ValueError("edited_response is required for an edit decision")
        return self


class InvestigationStarted(BaseModel):
    thread_id: str
    case_id: str
    status: str
    review_payload: dict[str, Any]


class ReviewCompleted(BaseModel):
    thread_id: str
    case_id: str
    status: str
    investigation: dict[str, Any]
    final_response: str | None
    audit_record: dict[str, Any]

