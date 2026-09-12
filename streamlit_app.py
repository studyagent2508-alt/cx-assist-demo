from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests
import streamlit as st


API_URL = os.getenv("CX_ASSIST_API_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = 180

st.set_page_config(page_title="CX Assist", page_icon="🚚", layout="wide")
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.5rem; padding-bottom: 3rem;}
    [data-testid="stMetric"] {background: #f7f9fc; border: 1px solid #e3e8ef; padding: 12px; border-radius: 10px;}
    .status-box {padding: 0.8rem 1rem; border-radius: 0.6rem; background: #eef7ff; border-left: 5px solid #1677ff;}
    </style>
    """,
    unsafe_allow_html=True,
)


def api_request(method: str, path: str, **kwargs: Any) -> Any:
    try:
        response = requests.request(
            method,
            f"{API_URL}{path}",
            timeout=kwargs.pop("timeout", REQUEST_TIMEOUT),
            **kwargs,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Cannot reach CX Assist API at {API_URL}: {exc}") from exc
    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(f"API {response.status_code}: {detail}")
    return response.json()


@st.cache_data(ttl=15)
def load_health() -> dict[str, Any]:
    return api_request("GET", "/health", timeout=10)


@st.cache_data(ttl=30)
def load_cases() -> list[dict[str, Any]]:
    return api_request("GET", "/cases", timeout=20)


@st.cache_data(ttl=15)
def load_case(case_id: str) -> dict[str, Any]:
    return api_request("GET", f"/cases/{case_id}", timeout=20)


def reset_investigation() -> None:
    st.session_state.thread_id = None
    st.session_state.review_payload = None
    st.session_state.completed_result = None


for key, default in {
    "thread_id": None,
    "review_payload": None,
    "completed_result": None,
    "selected_case_id": None,
}.items():
    st.session_state.setdefault(key, default)


st.title("🚚 CX Assist")
st.caption("Internal investigation copilot • Evidence-grounded • Human approved")

try:
    health = load_health()
    backend_ready = health.get("status") == "healthy"
except RuntimeError as exc:
    backend_ready = False
    health = {}
    st.error(str(exc))
    st.info("Start Notebook 08 and keep its kernel running, then refresh this page.")
    st.stop()

with st.sidebar:
    st.header("System")
    st.success("Backend connected") if backend_ready else st.error("Backend unavailable")
    st.metric("Cases", health.get("case_count", 0))
    st.write("**Provider:**", health.get("provider", "Unknown"))
    st.write("**Model:**", health.get("model", "Unknown"))
    st.caption(API_URL)
    if st.button("Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

cases = load_cases()
if not cases:
    st.warning("No cases were returned by the backend.")
    st.stop()

case_lookup = {row["case_id"]: row for row in cases}
case_ids = list(case_lookup)
default_index = case_ids.index("CASE-3022") if "CASE-3022" in case_ids else 0

selected_case_id = st.selectbox(
    "Select a case to investigate",
    case_ids,
    index=default_index,
    format_func=lambda value: f"{value} — {case_lookup[value].get('issue_type', 'Unknown issue')}",
)
if st.session_state.selected_case_id != selected_case_id:
    st.session_state.selected_case_id = selected_case_id
    reset_investigation()

summary = case_lookup[selected_case_id]
metric_columns = st.columns(4)
metric_columns[0].metric("Case", selected_case_id)
metric_columns[1].metric("Issue", summary.get("issue_type", "—"))
metric_columns[2].metric("Priority", summary.get("priority", "—"))
metric_columns[3].metric("Status", summary.get("status", "—"))

investigation_tab, case_tab, audit_tab = st.tabs(
    ["Investigation", "Case 360", "Audit history"]
)

with investigation_tab:
    st.subheader("AI-assisted investigation")
    st.write(summary.get("subject", ""))

    if st.session_state.thread_id is None and st.session_state.completed_result is None:
        if st.button("Start investigation", type="primary", use_container_width=True):
            with st.spinner("Gathering Case 360, retrieving policies, and investigating..."):
                try:
                    started = api_request(
                        "POST",
                        "/investigations",
                        json={"case_id": selected_case_id},
                    )
                    st.session_state.thread_id = started["thread_id"]
                    st.session_state.review_payload = started["review_payload"]
                    st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc))

    payload = st.session_state.review_payload
    if payload:
        investigation = payload.get("investigation", {})
        st.markdown('<div class="status-box"><b>Status:</b> Awaiting human review</div>', unsafe_allow_html=True)
        st.progress(float(investigation.get("confidence", 0)), text=f"Model confidence: {float(investigation.get('confidence', 0)):.0%}")

        st.markdown("#### Case summary")
        st.write(investigation.get("case_summary", ""))

        left, right = st.columns(2)
        with left:
            st.markdown("#### Verified facts")
            for fact in investigation.get("verified_facts", []):
                st.markdown(f"- {fact}")
            st.markdown("#### Missing information")
            missing = investigation.get("missing_information", [])
            if missing:
                for item in missing:
                    st.warning(item)
            else:
                st.success("No missing information reported.")
        with right:
            st.markdown("#### Recommended action")
            st.write(investigation.get("recommended_action", ""))
            st.markdown("#### Required approval")
            st.info(investigation.get("approval_level", "Human review"))

        with st.expander("Evidence", expanded=True):
            evidence = investigation.get("evidence", [])
            st.dataframe(pd.DataFrame(evidence), use_container_width=True, hide_index=True)
        with st.expander("Policy citations", expanded=True):
            policies = investigation.get("policy_citations", [])
            st.dataframe(pd.DataFrame(policies), use_container_width=True, hide_index=True)
        with st.expander("Customer response draft", expanded=True):
            st.write(investigation.get("customer_response_draft", ""))

        st.markdown("### Human decision")
        decision = st.selectbox(
            "Decision",
            ["approve", "edit", "reject", "escalate"],
            key="review_decision",
        )
        with st.form("review_form"):
            reviewer_id = st.text_input("Reviewer ID", value="DEMO-REVIEWER")
            comments = st.text_area("Review comments", value="Evidence and recommendation reviewed.")
            edited_response = st.text_area(
                "Edited customer response",
                value=investigation.get("customer_response_draft", "") if decision == "edit" else "",
                disabled=decision != "edit",
            )
            submitted = st.form_submit_button("Submit decision", type="primary", use_container_width=True)
        if submitted:
            if decision == "edit" and not edited_response.strip():
                st.error("Provide the edited customer response.")
            else:
                with st.spinner("Applying reviewer decision and creating the audit record..."):
                    try:
                        completed = api_request(
                            "POST",
                            f"/investigations/{st.session_state.thread_id}/review",
                            json={
                                "decision": decision,
                                "reviewer_id": reviewer_id,
                                "comments": comments,
                                "edited_response": edited_response if decision == "edit" else None,
                            },
                        )
                        st.session_state.completed_result = completed
                        st.session_state.review_payload = None
                        st.session_state.thread_id = None
                        st.cache_data.clear()
                        st.rerun()
                    except RuntimeError as exc:
                        st.error(str(exc))

    completed = st.session_state.completed_result
    if completed:
        status = completed.get("status", "unknown")
        st.success(f"Workflow completed: {status}")
        if completed.get("final_response"):
            st.markdown("#### Final customer response")
            st.write(completed["final_response"])
        st.markdown("#### Audit record")
        st.json(completed.get("audit_record", {}), expanded=False)
        if st.button("Investigate another case", use_container_width=True):
            reset_investigation()
            st.rerun()

with case_tab:
    st.subheader(f"Case 360 — {selected_case_id}")
    case_context = load_case(selected_case_id)
    section_order = [
        "case", "customer", "vehicle", "contract", "invoices_under_review",
        "payments", "service_records", "interactions",
    ]
    for section in section_order:
        value = case_context.get(section)
        with st.expander(section.replace("_", " ").title(), expanded=section == "case"):
            if isinstance(value, list):
                st.dataframe(pd.DataFrame(value), use_container_width=True, hide_index=True)
            elif isinstance(value, dict):
                st.dataframe(pd.DataFrame([value]), use_container_width=True, hide_index=True)
            else:
                st.write(value or "No records")

with audit_tab:
    st.subheader("Recent human-review audit events")
    try:
        audit_events = api_request("GET", "/audit-events?limit=50", timeout=30)
        if audit_events:
            audit_df = pd.DataFrame(audit_events)
            visible_columns = [
                column for column in (
                    "recorded_at_utc", "case_id", "issue_type", "final_status",
                    "decision", "reviewer_id", "confidence", "duration_seconds",
                    "warning_count",
                ) if column in audit_df.columns
            ]
            st.dataframe(audit_df[visible_columns], use_container_width=True, hide_index=True)
        else:
            st.info("No audit events exist yet. Complete an investigation to create one.")
    except RuntimeError as exc:
        st.error(str(exc))

st.divider()
st.caption("CX Assist is an internal decision-support tool. Every recommendation requires human review before customer communication or operational action.")
