from typing import Any

import httpx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from agentic_bi_copilot.config import get_settings

PRIMARY_QUESTION = (
    "Compare revenue across regions for the last six complete months, "
    "identify unusual declines, and generate a suitable chart."
)

settings = get_settings()

st.set_page_config(
    page_title="Agentic BI Copilot",
    page_icon="📊",
    layout="wide",
)


def check_backend() -> tuple[bool, str]:
    try:
        response = httpx.get(
            f"{settings.api_base_url}/health",
            timeout=2.0,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        return False, f"Backend unavailable: {error}"

    if payload.get("status") != "healthy":
        return False, "Backend returned an unexpected health response."

    return True, "Backend connected"


def post_to_api(
    path: str,
    payload: dict[str, Any],
    *,
    timeout: float = 120.0,
) -> dict[str, Any]:
    try:
        response = httpx.post(
            f"{settings.api_base_url}{path}",
            json=payload,
            timeout=timeout,
        )
    except httpx.HTTPError as error:
        raise RuntimeError(f"Could not reach the analytics API: {error}") from error

    if response.is_error:
        try:
            detail = response.json().get(
                "detail",
                "The analytics request failed.",
            )
        except ValueError:
            detail = "The analytics request failed."

        raise RuntimeError(str(detail))

    try:
        response_payload = response.json()
    except ValueError as error:
        raise RuntimeError("The analytics API returned invalid JSON.") from error

    if not isinstance(response_payload, dict):
        raise TypeError("The analytics API returned an unexpected response.")

    return response_payload


def start_agent_run(question: str) -> dict[str, Any]:
    return post_to_api(
        "/api/v1/agent/runs",
        {"question": question},
    )


def submit_agent_decision(
    thread_id: str,
    *,
    approved: bool,
    feedback: str | None,
) -> dict[str, Any]:
    return post_to_api(
        f"/api/v1/agent/runs/{thread_id}/decision",
        {
            "approved": approved,
            "feedback": feedback,
        },
    )


def reset_agent_state() -> None:
    st.session_state.pop("agent_start", None)
    st.session_state.pop("agent_decision", None)


def format_currency(value: Any) -> str:
    if value is None:
        return "—"

    return f"${float(value):,.2f}"


def render_safety(validation: dict[str, Any]) -> None:
    if validation.get("is_safe"):
        st.success("SQL passed every required safety check.")
    else:
        st.error("SQL did not pass validation.")

    for check in validation.get("checks", []):
        label = str(check).replace("_", " ").title()
        st.markdown(f"- ✅ {label}")

    for error in validation.get("errors", []):
        st.markdown(f"- ❌ {error}")


def render_completed_result(
    result: dict[str, Any],
    approval: dict[str, Any],
) -> None:
    query_result = result.get("query_result", {})
    analysis = result.get("analysis", {})

    if not isinstance(query_result, dict):
        st.error("The API returned an invalid query result.")
        return

    if not isinstance(analysis, dict):
        st.error("The API returned an invalid analysis result.")
        return

    st.divider()
    st.subheader("Business answer")
    st.write(result.get("answer", "No business answer was returned."))

    total_column, region_column, time_column = st.columns(3)

    total_column.metric(
        "Six-month revenue",
        format_currency(analysis.get("total_revenue")),
    )
    region_column.metric(
        "Top region",
        str(analysis.get("top_region", "—")),
        help=(f"Revenue: {format_currency(analysis.get('top_region_revenue'))}"),
    )
    time_column.metric(
        "Database execution",
        (f"{float(query_result.get('execution_time_ms', 0)):.2f} ms"),
    )

    findings_tab, data_tab, details_tab = st.tabs(
        [
            "Findings",
            "Data and chart",
            "Agent details",
        ]
    )

    with findings_tab:
        st.subheader("Unusual declines")

        findings = analysis.get("unusual_declines", [])

        if not isinstance(findings, list):
            findings = []

        findings_frame = pd.DataFrame(findings)

        if findings_frame.empty:
            st.info("No unusual declines were detected.")
        else:
            findings_frame = findings_frame.rename(
                columns={
                    "region": "Region",
                    "month": "Month",
                    "revenue": "Revenue",
                    "previous_month_revenue": ("Previous month revenue"),
                    "change_pct": "Change (%)",
                }
            )

            st.dataframe(
                findings_frame,
                hide_index=True,
                width="stretch",
            )

    with data_tab:
        st.subheader("Revenue trend")

        chart_spec = result.get("chart")

        if isinstance(chart_spec, dict):
            figure = go.Figure(chart_spec)
            st.plotly_chart(
                figure,
                width="stretch",
                config={"displaylogo": False},
            )
        else:
            st.info("No chart was returned.")

        st.subheader("Query result")

        rows = query_result.get("rows", [])

        if isinstance(rows, list):
            st.dataframe(
                pd.DataFrame(rows),
                hide_index=True,
                width="stretch",
            )

        st.caption(f"{query_result.get('row_count', 0)} rows returned.")

    with details_tab:
        st.subheader("Referenced tables")
        st.write(", ".join(approval.get("referenced_tables", [])))

        st.subheader("SQL safety")

        validation = approval.get("validation", {})

        if isinstance(validation, dict):
            render_safety(validation)

        explanation = approval.get("sql_explanation")

        if explanation:
            st.subheader("SQL explanation")
            st.write(explanation)

        st.subheader("Approved and executed SQL")
        st.code(str(approval.get("sql", "")), language="sql")


st.title("Agentic Analytics and BI Copilot")
st.caption(
    "Ask a business question, inspect the generated SQL, and approve "
    "execution before the database is queried."
)

backend_connected, backend_message = check_backend()

if backend_connected:
    st.success(backend_message)
else:
    st.error(backend_message)

st.info(
    "The agent can generate SQL, but it cannot execute the query until "
    "you explicitly approve it."
)

active_start = st.session_state.get("agent_start")
active_decision = st.session_state.get("agent_decision")

awaiting_approval = (
    isinstance(active_start, dict)
    and active_start.get("status") == "awaiting_approval"
    and not isinstance(active_decision, dict)
)

with st.form("business_question_form"):
    question = st.text_area(
        "Business question",
        value=PRIMARY_QUESTION,
        height=120,
        disabled=awaiting_approval,
    )

    submitted = st.form_submit_button(
        "Generate analysis plan and SQL",
        type="primary",
        disabled=not backend_connected or awaiting_approval,
    )

if submitted:
    cleaned_question = question.strip()

    if not cleaned_question:
        st.warning("Enter a business question before submitting.")
    else:
        reset_agent_state()

        try:
            with st.spinner(
                "Discovering the schema, planning the analysis, "
                "generating SQL, and validating safety..."
            ):
                st.session_state["agent_start"] = start_agent_run(cleaned_question)

            st.rerun()
        except (RuntimeError, TypeError) as error:
            st.error(str(error))

agent_start = st.session_state.get("agent_start")

if isinstance(agent_start, dict):
    start_status = agent_start.get("status")

    if start_status == "awaiting_approval" and awaiting_approval:
        approval = agent_start.get("approval")
        thread_id = agent_start.get("thread_id")

        if isinstance(approval, dict) and isinstance(thread_id, str):
            st.divider()
            st.subheader("Human approval required")
            st.warning(
                "Review the generated SQL carefully. The database has "
                "not been queried yet."
            )

            explanation = approval.get("sql_explanation")

            if explanation:
                st.write(explanation)

            st.subheader("Referenced tables")
            st.write(", ".join(approval.get("referenced_tables", [])))

            validation = approval.get("validation", {})

            if isinstance(validation, dict):
                st.subheader("Safety validation")
                render_safety(validation)

            st.subheader("Generated SQL")
            st.code(
                str(approval.get("sql", "")),
                language="sql",
            )

            rejection_feedback = st.text_input(
                "Optional feedback if you reject this SQL",
                placeholder=("Example: Use a different date range."),
            )

            approve_column, reject_column = st.columns(2)

            approve_clicked = approve_column.button(
                "Approve and execute",
                type="primary",
                width="stretch",
            )
            reject_clicked = reject_column.button(
                "Reject SQL",
                width="stretch",
            )

            if approve_clicked or reject_clicked:
                approved = approve_clicked
                feedback = rejection_feedback.strip() or None

                try:
                    with st.spinner(
                        "Executing the approved read-only query..."
                        if approved
                        else "Rejecting the query safely..."
                    ):
                        st.session_state["agent_decision"] = submit_agent_decision(
                            thread_id,
                            approved=approved,
                            feedback=feedback,
                        )

                    st.rerun()
                except (RuntimeError, TypeError) as error:
                    st.error(str(error))
        else:
            st.error("The approval response is incomplete.")

    elif start_status == "failed":
        st.error(
            str(
                agent_start.get(
                    "error",
                    "The agent could not prepare the analysis.",
                )
            )
        )

agent_decision = st.session_state.get("agent_decision")

if isinstance(agent_decision, dict):
    decision_status = agent_decision.get("status")

    if decision_status == "completed":
        completed_result = agent_decision.get("result")
        approval = (
            agent_start.get("approval", {}) if isinstance(agent_start, dict) else {}
        )

        if isinstance(completed_result, dict) and isinstance(
            approval,
            dict,
        ):
            render_completed_result(
                completed_result,
                approval,
            )
        else:
            st.error("The completed response is missing its result.")

    elif decision_status == "rejected":
        st.divider()
        st.warning("The SQL was rejected. No analytical query was executed.")

    elif decision_status == "failed":
        st.error(
            str(
                agent_decision.get(
                    "error",
                    "The agent workflow failed.",
                )
            )
        )

if agent_start:
    st.button(
        "Start a new analysis",
        on_click=reset_agent_state,
    )
