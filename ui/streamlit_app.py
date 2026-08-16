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
    initial_sidebar_state="expanded",
)


def apply_custom_styles() -> None:
    """Apply a simple professional style to the application."""
    st.markdown(
        """
        <style>
            .block-container {
                max-width: 1400px;
                padding-top: 2rem;
                padding-bottom: 3rem;
            }

            .hero-card {
                background:
                    linear-gradient(
                        135deg,
                        #0f2747 0%,
                        #174a72 55%,
                        #147d80 100%
                    );
                border-radius: 18px;
                padding: 2.1rem 2.3rem;
                margin-bottom: 1.2rem;
                color: white;
                box-shadow: 0 12px 32px rgba(15, 39, 71, 0.18);
            }

            .hero-label {
                color: #bce9e7;
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.11rem;
                margin-bottom: 0.6rem;
                text-transform: uppercase;
            }

            .hero-title {
                color: white;
                font-size: 2.25rem;
                font-weight: 750;
                line-height: 1.15;
                margin: 0;
            }

            .hero-description {
                color: #e5f2f7;
                font-size: 1.02rem;
                line-height: 1.65;
                margin-top: 0.85rem;
                margin-bottom: 0;
                max-width: 850px;
            }

            div[data-testid="stMetric"] {
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(128, 145, 165, 0.28);
                border-radius: 14px;
                padding: 1rem 1.1rem;
                box-shadow: 0 5px 18px rgba(15, 39, 71, 0.06);
            }

            div[data-testid="stMetricLabel"] {
                font-weight: 600;
            }

            div[data-testid="stForm"] {
                border: 1px solid rgba(128, 145, 165, 0.28);
                border-radius: 16px;
                padding: 1.2rem;
                background: rgba(255, 255, 255, 0.02);
            }

            div[data-testid="stExpander"] {
                border-radius: 12px;
            }

            div[data-testid="stDataFrame"] {
                border: 1px solid rgba(128, 145, 165, 0.2);
                border-radius: 12px;
                overflow: hidden;
            }

            .section-label {
                color: #147d80;
                font-size: 0.76rem;
                font-weight: 700;
                letter-spacing: 0.09rem;
                margin-bottom: 0.25rem;
                text-transform: uppercase;
            }

            .section-description {
                color: #68778a;
                font-size: 0.92rem;
                margin-top: -0.25rem;
                margin-bottom: 1rem;
            }

            .workflow-step {
                border-left: 3px solid #1c7c83;
                margin-bottom: 0.8rem;
                padding-left: 0.8rem;
            }

            .workflow-step strong {
                color: #174a72;
            }

            button[kind="primary"] {
                border-radius: 10px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def check_backend() -> tuple[bool, str]:
    """Check whether the FastAPI backend is available."""
    try:
        response = httpx.get(
            f"{settings.api_base_url}/health",
            timeout=2.0,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        return False, f"Backend unavailable: {error}"

    if not isinstance(payload, dict):
        return (
            False,
            "Backend returned an unexpected health response.",
        )

    if payload.get("status") != "healthy":
        return (
            False,
            "Backend returned an unexpected health response.",
        )

    return True, "Backend connected"


def post_to_api(
    path: str,
    payload: dict[str, Any],
    *,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Send a POST request to the analytics API."""
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
            error_payload = response.json()
        except ValueError:
            error_payload = {}

        if isinstance(error_payload, dict):
            detail = error_payload.get(
                "detail",
                "The analytics request failed.",
            )
        else:
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
    """Ask the API to start an agent workflow."""
    return post_to_api(
        "/api/v1/agent/runs",
        {
            "question": question,
        },
    )


def submit_agent_decision(
    thread_id: str,
    *,
    approved: bool,
    feedback: str | None,
) -> dict[str, Any]:
    """Send an approval or rejection decision to the API."""
    return post_to_api(
        f"/api/v1/agent/runs/{thread_id}/decision",
        {
            "approved": approved,
            "feedback": feedback,
        },
    )


def reset_agent_state() -> None:
    """Clear the current workflow from Streamlit session state."""
    st.session_state.pop("agent_start", None)
    st.session_state.pop("agent_decision", None)


def format_currency(value: Any) -> str:
    """Format a value as US currency."""
    if value is None:
        return "—"

    return f"${float(value):,.2f}"


def render_page_header() -> None:
    """Display the main application header."""
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-label">Secure Agentic Analytics</div>
            <h1 class="hero-title">Agentic Analytics and BI Copilot</h1>
            <p class="hero-description">
                Turn a business question into a structured analysis plan,
                review the generated SQL, and approve execution before any
                analytical query reaches the database.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(
    backend_connected: bool,
    backend_message: str,
) -> None:
    """Display workflow guidance and connection status."""
    with st.sidebar:
        st.title("BI Copilot")
        st.caption("Human-approved analytics workflow")

        st.divider()
        st.subheader("Workflow")

        st.markdown(
            """
            <div class="workflow-step">
                <strong>1. Ask</strong><br>
                Enter a business question.
            </div>
            <div class="workflow-step">
                <strong>2. Review</strong><br>
                Inspect the plan, tables, safety checks, and SQL.
            </div>
            <div class="workflow-step">
                <strong>3. Approve</strong><br>
                Explicitly allow or reject query execution.
            </div>
            <div class="workflow-step">
                <strong>4. Analyze</strong><br>
                Explore the answer, findings, chart, and data.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()
        st.subheader("System status")

        if backend_connected:
            st.success(backend_message)
        else:
            st.error(backend_message)

        st.caption(
            "Database access is read-only and every generated "
            "query must pass safety validation."
        )


def render_connection_banner(
    backend_connected: bool,
    backend_message: str,
) -> None:
    """Display backend and approval status near the top."""
    connection_column, safety_column = st.columns([1, 2])

    with connection_column:
        if backend_connected:
            st.success(backend_message)
        else:
            st.error(backend_message)

    with safety_column:
        st.info(
            "SQL generation is automatic. Database execution "
            "always requires your explicit approval."
        )


def render_section_heading(
    label: str,
    title: str,
    description: str | None = None,
) -> None:
    """Display a consistent section heading."""
    st.markdown(
        f'<div class="section-label">{label}</div>',
        unsafe_allow_html=True,
    )
    st.subheader(title)

    if description:
        st.markdown(
            f'<div class="section-description">{description}</div>',
            unsafe_allow_html=True,
        )


def render_safety(
    validation: dict[str, Any],
) -> None:
    """Display SQL safety checks and errors."""
    if validation.get("is_safe"):
        st.success("SQL passed every required safety check.")
    else:
        st.error("SQL did not pass validation.")

    checks = validation.get("checks", [])

    if isinstance(checks, list):
        for check in checks:
            label = str(check).replace("_", " ").title()
            st.markdown(f"- ✅ {label}")

    errors = validation.get("errors", [])

    if isinstance(errors, list):
        for error in errors:
            st.markdown(f"- ❌ {error}")


def render_analysis_plan(plan: dict[str, Any]) -> None:
    """Display the model's structured analysis plan."""
    interpreted_question = plan.get("interpreted_question")

    if interpreted_question:
        st.markdown("**Interpreted question**")
        st.write(interpreted_question)

    steps = plan.get("steps", [])

    if isinstance(steps, list) and steps:
        st.markdown("**Analysis steps**")

        for step_number, step in enumerate(
            steps,
            start=1,
        ):
            st.markdown(f"{step_number}. {step}")

    assumptions = plan.get("assumptions", [])

    if isinstance(assumptions, list) and assumptions:
        with st.expander("View analysis assumptions"):
            for assumption in assumptions:
                st.markdown(f"- {assumption}")


def render_findings(
    analysis: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """Display unusual declines and follow-up questions."""
    render_section_heading(
        "Key findings",
        "Unusual revenue declines",
        "Months that crossed the agent's decline threshold.",
    )

    findings = analysis.get(
        "unusual_declines",
        [],
    )

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

    st.markdown("#### Suggested follow-up questions")

    follow_up_questions = result.get(
        "follow_up_questions",
        [],
    )

    if isinstance(follow_up_questions, list) and follow_up_questions:
        for number, follow_up in enumerate(
            follow_up_questions,
            start=1,
        ):
            st.markdown(f"{number}. {follow_up}")
    else:
        st.caption("No follow-up questions were returned.")


def render_chart_and_data(
    query_result: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """Display the chart and underlying query rows."""
    render_section_heading(
        "Visual analysis",
        "Regional revenue trend",
        "Monthly revenue by region with unusual declines highlighted.",
    )

    chart_spec = result.get("chart")

    if isinstance(chart_spec, dict):
        figure = go.Figure(chart_spec)

        st.plotly_chart(
            figure,
            width="stretch",
            config={
                "displaylogo": False,
                "responsive": True,
            },
        )
    else:
        st.info("No chart was returned.")

    with st.expander(
        "View the underlying query result",
        expanded=False,
    ):
        rows = query_result.get("rows", [])

        if isinstance(rows, list):
            st.dataframe(
                pd.DataFrame(rows),
                hide_index=True,
                width="stretch",
            )
        else:
            st.error("The query rows were not returned correctly.")

        st.caption(f"{query_result.get('row_count', 0)} rows returned.")


def render_agent_details(
    result: dict[str, Any],
    approval: dict[str, Any],
) -> None:
    """Display the plan and full SQL audit information."""
    render_section_heading(
        "Audit trail",
        "Agent and SQL details",
        "Review how the result was planned, validated, and executed.",
    )

    plan = result.get("plan", {})

    if isinstance(plan, dict):
        render_analysis_plan(plan)

    st.markdown("#### Referenced tables")

    referenced_tables = approval.get(
        "referenced_tables",
        [],
    )

    if isinstance(referenced_tables, list):
        st.write(", ".join(map(str, referenced_tables)))

    st.markdown("#### SQL safety")

    validation = approval.get("validation", {})

    if isinstance(validation, dict):
        render_safety(validation)

    explanation = approval.get("sql_explanation")

    if explanation:
        st.markdown("#### SQL explanation")
        st.write(explanation)

    with st.expander(
        "View approved and executed SQL",
        expanded=False,
    ):
        st.code(
            str(approval.get("sql", "")),
            language="sql",
        )


def render_completed_result(
    result: dict[str, Any],
    approval: dict[str, Any],
) -> None:
    """Display the final answer, metrics, chart, and audit details."""
    query_result = result.get(
        "query_result",
        {},
    )
    analysis = result.get("analysis", {})

    if not isinstance(query_result, dict):
        st.error("The API returned an invalid query result.")
        return

    if not isinstance(analysis, dict):
        st.error("The API returned an invalid analysis result.")
        return

    st.divider()

    with st.container(border=True):
        render_section_heading(
            "Executive summary",
            "Business answer",
        )
        st.write(
            result.get(
                "answer",
                "No business answer was returned.",
            )
        )

    total_column, region_column, revenue_column, time_column = st.columns(4)

    total_column.metric(
        "Six-month revenue",
        format_currency(analysis.get("total_revenue")),
    )

    region_column.metric(
        "Top region",
        str(analysis.get("top_region", "—")),
    )

    revenue_column.metric(
        "Top-region revenue",
        format_currency(analysis.get("top_region_revenue")),
    )

    execution_time = float(
        query_result.get(
            "execution_time_ms",
            0,
        )
    )

    time_column.metric(
        "Database execution",
        f"{execution_time:.2f} ms",
    )

    findings_tab, chart_tab, details_tab = st.tabs(
        [
            "Key findings",
            "Chart and data",
            "Audit trail",
        ]
    )

    with findings_tab:
        render_findings(
            analysis,
            result,
        )

    with chart_tab:
        render_chart_and_data(
            query_result,
            result,
        )

    with details_tab:
        render_agent_details(
            result,
            approval,
        )


def is_waiting_for_approval(
    agent_start: Any,
    agent_decision: Any,
) -> bool:
    """Check whether an agent run is waiting for review."""
    return (
        isinstance(agent_start, dict)
        and agent_start.get("status") == "awaiting_approval"
        and not isinstance(agent_decision, dict)
    )


def render_question_form(
    backend_connected: bool,
    awaiting_approval: bool,
) -> tuple[bool, str]:
    """Display the business-question form."""
    render_section_heading(
        "Start an analysis",
        "What would you like to understand?",
        "The agent will inspect the schema, create a plan, "
        "draft SQL, and run its safety checks.",
    )

    with st.form("business_question_form"):
        question = st.text_area(
            "Business question",
            value=PRIMARY_QUESTION,
            height=125,
            disabled=awaiting_approval,
            help=(
                "Ask a clear analytical question using the available retail dataset."
            ),
        )

        submitted = st.form_submit_button(
            "Generate analysis plan and SQL",
            type="primary",
            disabled=(not backend_connected or awaiting_approval),
            width="stretch",
        )

    return submitted, question


def handle_question_submission(
    submitted: bool,
    question: str,
) -> None:
    """Start a new agent run after form submission."""
    if not submitted:
        return

    cleaned_question = question.strip()

    if not cleaned_question:
        st.warning("Enter a business question before submitting.")
        return

    reset_agent_state()

    try:
        with st.spinner(
            "Discovering the schema, planning the analysis, "
            "generating SQL, and validating safety..."
        ):
            response = start_agent_run(cleaned_question)
            st.session_state["agent_start"] = response

        st.rerun()
    except (RuntimeError, TypeError) as error:
        st.error(str(error))


def render_approval_request(
    agent_start: dict[str, Any],
) -> None:
    """Display the SQL approval screen."""
    approval = agent_start.get("approval")
    thread_id = agent_start.get("thread_id")

    if not isinstance(approval, dict):
        st.error("The approval response is incomplete.")
        return

    if not isinstance(thread_id, str):
        st.error("The approval response is incomplete.")
        return

    st.divider()

    with st.container(border=True):
        render_section_heading(
            "Human review",
            "Approval required before execution",
            "Review the analytical plan and generated SQL carefully. "
            "The database has not been queried yet.",
        )

        st.warning(
            "Approving this request will execute the validated "
            "SQL using the read-only database account."
        )

        plan_column, safety_column = st.columns([3, 2])

        with plan_column:
            st.markdown("#### Analysis plan")

            plan = approval.get("plan", {})

            if isinstance(plan, dict):
                render_analysis_plan(plan)

            explanation = approval.get("sql_explanation")

            if explanation:
                st.markdown("#### SQL explanation")
                st.write(explanation)

            st.markdown("#### Referenced tables")

            referenced_tables = approval.get(
                "referenced_tables",
                [],
            )

            if isinstance(referenced_tables, list):
                st.write(", ".join(map(str, referenced_tables)))

        with safety_column:
            st.markdown("#### Safety validation")

            validation = approval.get(
                "validation",
                {},
            )

            if isinstance(validation, dict):
                render_safety(validation)

        st.markdown("#### Generated SQL")

        st.code(
            str(approval.get("sql", "")),
            language="sql",
        )

        rejection_feedback = st.text_input(
            "Optional feedback when rejecting this SQL",
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
            spinner_message = (
                "Executing the approved read-only query..."
                if approved
                else "Rejecting the query safely..."
            )

            with st.spinner(spinner_message):
                response = submit_agent_decision(
                    thread_id,
                    approved=approved,
                    feedback=feedback,
                )
                st.session_state["agent_decision"] = response

            st.rerun()
        except (RuntimeError, TypeError) as error:
            st.error(str(error))


def render_agent_start_status(
    agent_start: Any,
    awaiting_approval: bool,
) -> None:
    """Display the current agent-start status."""
    if not isinstance(agent_start, dict):
        return

    start_status = agent_start.get("status")

    if start_status == "awaiting_approval" and awaiting_approval:
        render_approval_request(agent_start)

    elif start_status == "failed":
        st.error(
            str(
                agent_start.get(
                    "error",
                    "The agent could not prepare the analysis.",
                )
            )
        )


def render_agent_decision_status(
    agent_decision: Any,
    agent_start: Any,
) -> None:
    """Display the result of an approval or rejection."""
    if not isinstance(agent_decision, dict):
        return

    decision_status = agent_decision.get("status")

    if decision_status == "completed":
        completed_result = agent_decision.get("result")

        if isinstance(agent_start, dict):
            approval = agent_start.get(
                "approval",
                {},
            )
        else:
            approval = {}

        if isinstance(completed_result, dict) and isinstance(approval, dict):
            render_completed_result(
                completed_result,
                approval,
            )
        else:
            st.error("The completed response is missing its result.")

    elif decision_status == "rejected":
        st.divider()

        with st.container(border=True):
            st.warning("The SQL was rejected. No analytical query was executed.")

            rejection_reason = agent_decision.get("error")

            if rejection_reason:
                st.caption(str(rejection_reason))

    elif decision_status == "failed":
        st.error(
            str(
                agent_decision.get(
                    "error",
                    "The agent workflow failed.",
                )
            )
        )


def render_new_analysis_button(
    agent_start: Any,
    awaiting_approval: bool,
) -> None:
    """Display a button for clearing a finished workflow."""
    if agent_start and not awaiting_approval:
        st.button(
            "Start a new analysis",
            on_click=reset_agent_state,
            width="stretch",
        )


def main() -> None:
    """Render the complete Streamlit application."""
    apply_custom_styles()
    render_page_header()

    backend_connected, backend_message = check_backend()

    render_sidebar(
        backend_connected,
        backend_message,
    )
    render_connection_banner(
        backend_connected,
        backend_message,
    )

    active_start = st.session_state.get("agent_start")
    active_decision = st.session_state.get("agent_decision")

    awaiting_approval = is_waiting_for_approval(
        active_start,
        active_decision,
    )

    submitted, question = render_question_form(
        backend_connected,
        awaiting_approval,
    )

    handle_question_submission(
        submitted,
        question,
    )

    agent_start = st.session_state.get("agent_start")
    agent_decision = st.session_state.get("agent_decision")

    awaiting_approval = is_waiting_for_approval(
        agent_start,
        agent_decision,
    )

    render_agent_start_status(
        agent_start,
        awaiting_approval,
    )
    render_agent_decision_status(
        agent_decision,
        agent_start,
    )
    render_new_analysis_button(
        agent_start,
        awaiting_approval,
    )


if __name__ == "__main__":
    main()
