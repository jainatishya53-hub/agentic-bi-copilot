from typing import Any, Literal

import httpx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from agentic_bi_copilot.config import get_settings
from agentic_bi_copilot.services.question_catalog import QUESTION_EXAMPLES

DEFAULT_QUESTION = QUESTION_EXAMPLES[0].question
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
                background: linear-gradient(
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

            .history-card {
                border: 1px solid rgba(128, 145, 165, 0.25);
                border-radius: 14px;
                padding: 1rem 1.1rem;
                margin-bottom: 0.8rem;
                background: rgba(255, 255, 255, 0.02);
            }

            button[kind="primary"] {
                border-radius: 10px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_error_detail(
    response: httpx.Response,
    default_message: str,
) -> str:
    """Read a useful error message from an API response."""

    try:
        payload = response.json()
    except ValueError:
        return default_message

    if not isinstance(payload, dict):
        return default_message

    return str(payload.get("detail", default_message))


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

    if not isinstance(payload, dict) or payload.get("status") != "healthy":
        return False, "Backend returned an unexpected health response."

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
        raise RuntimeError(
            get_error_detail(
                response,
                "The analytics request failed.",
            )
        )

    try:
        response_payload = response.json()
    except ValueError as error:
        raise RuntimeError("The analytics API returned invalid JSON.") from error

    if not isinstance(response_payload, dict):
        raise TypeError("The analytics API returned an unexpected response.")

    return response_payload


def get_from_api(
    path: str,
    *,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Send a GET request to the analytics API."""

    try:
        response = httpx.get(
            f"{settings.api_base_url}{path}",
            timeout=timeout,
        )
    except httpx.HTTPError as error:
        raise RuntimeError(f"Could not reach the analytics API: {error}") from error

    if response.is_error:
        raise RuntimeError(
            get_error_detail(
                response,
                "The analytics request failed.",
            )
        )

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
        {"question": question},
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


def get_agent_history(limit: int = 20) -> dict[str, Any]:
    """Get recent agent runs from the API."""

    return get_from_api(f"/api/v1/agent/runs/history?limit={limit}")


def get_agent_run(thread_id: str) -> dict[str, Any]:
    """Get the stored details for one agent run."""

    return get_from_api(f"/api/v1/agent/runs/{thread_id}")


def retry_agent_run(thread_id: str) -> dict[str, Any]:
    """Start another run using an earlier question."""

    return post_to_api(
        f"/api/v1/agent/runs/{thread_id}/retry",
        {},
    )


def download_agent_export(
    thread_id: str,
    export_format: Literal["json", "csv"],
) -> bytes:
    """Download a completed run from the API."""

    url = (
        f"{settings.api_base_url}"
        f"/api/v1/agent/runs/{thread_id}/export"
        f"?format={export_format}"
    )

    try:
        response = httpx.get(url, timeout=30.0)
    except httpx.HTTPError as error:
        raise RuntimeError(f"Could not reach the analytics API: {error}") from error

    if response.is_error:
        raise RuntimeError(
            get_error_detail(
                response,
                "The export request failed.",
            )
        )

    return response.content


def reset_agent_state() -> None:
    """Clear the current workflow from Streamlit session state."""

    st.session_state.pop("agent_start", None)
    st.session_state.pop("agent_decision", None)
    st.session_state.pop("history_detail", None)


def initialize_question_state() -> None:
    """Set the initial question shown in the text area."""

    if "business_question" not in st.session_state:
        st.session_state["business_question"] = DEFAULT_QUESTION


def select_example_question(question: str) -> None:
    """Place an example question in the editable text area."""

    reset_agent_state()
    st.session_state["business_question"] = question


def format_currency(value: Any) -> str:
    """Format a value as US currency."""

    if value is None:
        return "—"

    return f"${float(value):,.2f}"


def format_label(value: Any) -> str:
    """Convert a stored identifier into a readable label."""

    if value is None:
        return "—"

    return str(value).replace("_", " ").title()


def format_history_time(value: Any) -> str:
    """Create a short readable date and time for history rows."""

    if value is None:
        return "—"

    text = str(value).replace("T", " ")
    return text[:19]


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
                Inspect the plan, safety checks, and SQL.
            </div>
            <div class="workflow-step">
                <strong>3. Approve</strong><br>
                Explicitly allow or reject execution.
            </div>
            <div class="workflow-step">
                <strong>4. Analyze</strong><br>
                Explore the answer, chart, and data.
            </div>
            <div class="workflow-step">
                <strong>5. Revisit</strong><br>
                Reopen, retry, or export earlier runs.
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


def render_example_questions(awaiting_approval: bool) -> None:
    """Display examples without restricting free-form input."""

    st.markdown("#### Try an example")
    st.caption(
        "Select an example or write your own question below. "
        "Selecting an example does not submit it automatically."
    )

    columns = st.columns(3)

    for index, example in enumerate(QUESTION_EXAMPLES):
        with columns[index % 3]:
            st.button(
                example.title,
                key=f"example_question_{example.key}",
                help=example.question,
                disabled=awaiting_approval,
                on_click=select_example_question,
                args=(example.question,),
                width="stretch",
            )


def render_safety(validation: dict[str, Any]) -> None:
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

        for step_number, step in enumerate(steps, start=1):
            st.markdown(f"{step_number}. {step}")

    assumptions = plan.get("assumptions", [])

    if isinstance(assumptions, list) and assumptions:
        with st.expander("View analysis assumptions"):
            for assumption in assumptions:
                st.markdown(f"- {assumption}")


def is_regional_revenue_analysis(
    analysis: dict[str, Any],
) -> bool:
    """Check whether this is the original regional analysis."""

    required_fields = {
        "total_revenue",
        "top_region",
        "top_region_revenue",
        "unusual_declines",
    }

    return required_fields.issubset(analysis)


def render_result_metrics(
    query_result: dict[str, Any],
    analysis: dict[str, Any],
) -> None:
    """Display metrics that match the type of analysis."""

    first_column, second_column, third_column, time_column = st.columns(4)

    if is_regional_revenue_analysis(analysis):
        first_column.metric(
            "Six-month revenue",
            format_currency(analysis.get("total_revenue")),
        )
        second_column.metric(
            "Top region",
            str(analysis.get("top_region", "—")),
        )
        third_column.metric(
            "Top-region revenue",
            format_currency(analysis.get("top_region_revenue")),
        )
    else:
        first_column.metric(
            "Rows returned",
            str(query_result.get("row_count", 0)),
        )
        second_column.metric(
            "Analysis type",
            format_label(analysis.get("analysis_type")),
        )

        chart_information = analysis.get("chart", {})
        chart_type = None

        if isinstance(chart_information, dict):
            chart_type = chart_information.get("chart_type")

        third_column.metric(
            "Visualization",
            format_label(chart_type),
        )

    execution_time = float(query_result.get("execution_time_ms", 0))
    time_column.metric(
        "Database execution",
        f"{execution_time:.2f} ms",
    )


def render_findings(
    analysis: dict[str, Any],
    result: dict[str, Any],
) -> None:
    """Display findings and suggested follow-up questions."""

    if is_regional_revenue_analysis(analysis):
        render_section_heading(
            "Key findings",
            "Unusual revenue declines",
            "Months that crossed the agent's decline threshold.",
        )

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
                    "previous_month_revenue": "Previous month revenue",
                    "change_pct": "Change (%)",
                }
            )
            st.dataframe(
                findings_frame,
                hide_index=True,
                width="stretch",
            )
    else:
        render_section_heading(
            "Key findings",
            "Business findings",
            "Important observations grounded in the query result.",
        )

        key_findings = analysis.get("key_findings", [])

        if isinstance(key_findings, list) and key_findings:
            for number, finding in enumerate(key_findings, start=1):
                st.markdown(f"{number}. {finding}")
        else:
            st.info("No key findings were returned.")

    st.markdown("#### Suggested follow-up questions")
    follow_up_questions = result.get("follow_up_questions", [])

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
        "Query result visualization",
        "A chart or table selected for the approved query result.",
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

    with st.expander("View the underlying query result"):
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


def build_approval_from_result(
    result: dict[str, Any],
) -> dict[str, Any]:
    """Build audit details for older completed history records."""

    return {
        "question": result.get("question", ""),
        "plan": result.get("plan", {}),
        "sql": result.get("sql", ""),
        "sql_explanation": result.get("sql_explanation", ""),
        "referenced_tables": result.get("referenced_tables", []),
        "validation": result.get("validation", {}),
    }


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
    referenced_tables = approval.get("referenced_tables", [])

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

    with st.expander("View approved and executed SQL"):
        st.code(
            str(approval.get("sql", "")),
            language="sql",
        )


def render_export_buttons(
    thread_id: str,
    key_prefix: str,
) -> None:
    """Display JSON and CSV download buttons for a completed run."""

    export_cache = st.session_state.setdefault("export_cache", {})

    if not isinstance(export_cache, dict):
        export_cache = {}
        st.session_state["export_cache"] = export_cache

    if thread_id not in export_cache:
        try:
            export_cache[thread_id] = {
                "json": download_agent_export(thread_id, "json"),
                "csv": download_agent_export(thread_id, "csv"),
            }
        except RuntimeError as error:
            st.warning(f"Exports are currently unavailable: {error}")
            return

    exports = export_cache.get(thread_id, {})

    if not isinstance(exports, dict):
        return

    st.markdown("#### Export result")
    json_column, csv_column = st.columns(2)

    json_column.download_button(
        "Download JSON",
        data=exports.get("json", b""),
        file_name=f"analysis-{thread_id}.json",
        mime="application/json",
        key=f"{key_prefix}_json_export_{thread_id}",
        width="stretch",
    )
    csv_column.download_button(
        "Download CSV",
        data=exports.get("csv", b""),
        file_name=f"analysis-{thread_id}.csv",
        mime="text/csv",
        key=f"{key_prefix}_csv_export_{thread_id}",
        width="stretch",
    )


def render_completed_result(
    result: dict[str, Any],
    approval: dict[str, Any],
    thread_id: str | None = None,
    key_prefix: str = "current",
) -> None:
    """Display the final answer, chart, data, and audit details."""

    query_result = result.get("query_result", {})
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
        render_result_metrics(query_result, analysis)

    findings_tab, chart_tab, details_tab = st.tabs(
        ["Key findings", "Chart and data", "Audit trail"]
    )

    with findings_tab:
        render_findings(analysis, result)

    with chart_tab:
        render_chart_and_data(query_result, result)

    with details_tab:
        render_agent_details(result, approval)

        if thread_id:
            render_export_buttons(thread_id, key_prefix)


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
    """Display examples and the business-question form."""

    initialize_question_state()

    render_section_heading(
        "Start an analysis",
        "What would you like to understand?",
        "The agent will inspect the schema, create a plan, "
        "draft SQL, and run its safety checks.",
    )

    render_example_questions(awaiting_approval)

    with st.form("business_question_form"):
        question = st.text_area(
            "Business question",
            key="business_question",
            height=125,
            disabled=awaiting_approval,
            help=(
                "Select an example above or enter any analytical "
                "question that can be answered from the retail dataset."
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

    if not isinstance(approval, dict) or not isinstance(thread_id, str):
        st.error("The approval response is incomplete.")
        return

    st.divider()

    with st.container(border=True):
        render_section_heading(
            "Human review",
            "Approval required before execution",
            "Review the plan and SQL carefully. "
            "The analytical query has not been executed yet.",
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
            referenced_tables = approval.get("referenced_tables", [])

            if isinstance(referenced_tables, list):
                st.write(", ".join(map(str, referenced_tables)))

        with safety_column:
            st.markdown("#### Safety validation")
            validation = approval.get("validation", {})

            if isinstance(validation, dict):
                render_safety(validation)

        st.markdown("#### Generated SQL")
        st.code(str(approval.get("sql", "")), language="sql")

        rejection_feedback = st.text_input(
            "Optional feedback when rejecting this SQL",
            placeholder="Example: Use a different date range.",
            key=f"rejection_feedback_{thread_id}",
        )

        approve_column, reject_column = st.columns(2)
        approve_clicked = approve_column.button(
            "Approve and execute",
            type="primary",
            width="stretch",
            key=f"approve_{thread_id}",
        )
        reject_clicked = reject_column.button(
            "Reject SQL",
            width="stretch",
            key=f"reject_{thread_id}",
        )

    if not (approve_clicked or reject_clicked):
        return

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
        approval: Any = {}
        thread_id: Any = None

        if isinstance(agent_start, dict):
            approval = agent_start.get("approval", {})
            thread_id = agent_start.get("thread_id")

        if isinstance(completed_result, dict) and isinstance(approval, dict):
            render_completed_result(
                completed_result,
                approval,
                thread_id if isinstance(thread_id, str) else None,
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


def build_history_frame(
    runs: list[dict[str, Any]],
) -> pd.DataFrame:
    """Create a readable table of recent runs."""

    records = []

    for run in runs:
        records.append(
            {
                "Status": format_label(run.get("status")),
                "Question": run.get("question", ""),
                "Updated": format_history_time(run.get("updated_at")),
                "Source run": run.get("source_thread_id") or "—",
            }
        )

    return pd.DataFrame(records)


def history_option_label(
    thread_id: str,
    run_lookup: dict[str, dict[str, Any]],
) -> str:
    """Create a readable label for the run selector."""

    run = run_lookup.get(thread_id, {})
    status_text = format_label(run.get("status"))
    question = str(run.get("question", "Analysis run"))

    if len(question) > 75:
        question = f"{question[:72]}..."

    return f"{status_text} — {question}"


def open_history_run(thread_id: str) -> None:
    """Load one history record into session state."""

    try:
        with st.spinner("Loading the selected analysis..."):
            st.session_state["history_detail"] = get_agent_run(thread_id)
    except (RuntimeError, TypeError) as error:
        st.error(str(error))


def continue_paused_run(detail: dict[str, Any]) -> None:
    """Move a stored paused run back to the approval screen."""

    thread_id = detail.get("thread_id")
    approval = detail.get("approval")

    if not isinstance(thread_id, str) or not isinstance(approval, dict):
        st.error("This paused run does not contain its approval details.")
        return

    st.session_state["agent_start"] = {
        "thread_id": thread_id,
        "status": "awaiting_approval",
        "approval": approval,
        "error": None,
    }
    st.session_state.pop("agent_decision", None)
    st.session_state.pop("history_detail", None)
    st.session_state["business_question"] = str(detail.get("question", ""))
    st.rerun()


def retry_history_run(detail: dict[str, Any]) -> None:
    """Retry a finished run and open its new approval request."""

    thread_id = detail.get("thread_id")

    if not isinstance(thread_id, str):
        st.error("The selected run does not have a valid identifier.")
        return

    try:
        with st.spinner("Creating a new run from this question..."):
            response = retry_agent_run(thread_id)

        st.session_state["agent_start"] = response
        st.session_state.pop("agent_decision", None)
        st.session_state.pop("history_detail", None)
        st.session_state["business_question"] = str(detail.get("question", ""))
        st.rerun()
    except (RuntimeError, TypeError) as error:
        st.error(str(error))


def render_history_detail(detail: dict[str, Any]) -> None:
    """Display one selected history record and its available actions."""

    thread_id = detail.get("thread_id")
    run_status = detail.get("status")

    if not isinstance(thread_id, str):
        st.error("The selected history record is incomplete.")
        return

    st.divider()

    with st.container(border=True):
        render_section_heading(
            "Selected run",
            str(detail.get("question", "Analysis history")),
        )

        status_column, updated_column, source_column = st.columns(3)
        status_column.metric("Status", format_label(run_status))
        updated_column.metric(
            "Last updated",
            format_history_time(detail.get("updated_at")),
        )
        source_column.metric(
            "Retry source",
            str(detail.get("source_thread_id") or "Original run"),
        )

        st.caption(f"Run ID: {thread_id}")

    if run_status == "awaiting_approval":
        approval = detail.get("approval")

        if isinstance(approval, dict):
            st.info(
                "This run is paused and can continue from its stored "
                "human-approval checkpoint."
            )
            st.button(
                "Continue approval review",
                type="primary",
                width="stretch",
                key=f"continue_{thread_id}",
                on_click=continue_paused_run,
                args=(detail,),
            )
        else:
            st.warning(
                "This older paused run does not contain stored approval details."
            )
        return

    if run_status == "completed":
        result = detail.get("result")

        if isinstance(result, dict):
            approval = detail.get("approval")

            if not isinstance(approval, dict):
                approval = build_approval_from_result(result)

            render_completed_result(
                result,
                approval,
                thread_id,
                key_prefix="history",
            )
        else:
            st.error("The completed run does not contain its result.")

    elif run_status == "rejected":
        st.warning("This run was rejected before SQL execution.")

        if detail.get("error"):
            st.caption(str(detail["error"]))

    elif run_status == "failed":
        st.error(str(detail.get("error") or "This run failed."))

    if run_status in {"completed", "rejected", "failed"}:
        st.button(
            "Retry this analysis",
            type="primary",
            width="stretch",
            key=f"retry_{thread_id}",
            on_click=retry_history_run,
            args=(detail,),
        )


def render_history_panel(backend_connected: bool) -> None:
    """Display recent runs and allow users to reopen them."""

    render_section_heading(
        "Analysis history",
        "Recent agent runs",
        "Reopen paused work, inspect completed results, retry a "
        "question, or download approved query data.",
    )

    if not backend_connected:
        st.warning("Connect the backend to load analysis history.")
        return

    try:
        history = get_agent_history(limit=20)
    except (RuntimeError, TypeError) as error:
        st.error(str(error))
        return

    runs = history.get("runs", [])

    if not isinstance(runs, list):
        st.error("The history API returned an unexpected response.")
        return

    valid_runs = [run for run in runs if isinstance(run, dict)]

    if not valid_runs:
        st.info(
            "No analysis history is available yet. "
            "Complete your first agent run to create it."
        )
        return

    history_column, refresh_column = st.columns([5, 1])
    history_column.caption(f"Showing {len(valid_runs)} most recently updated runs.")
    refresh_column.button(
        "Refresh",
        key="refresh_history",
        width="stretch",
    )

    st.dataframe(
        build_history_frame(valid_runs),
        hide_index=True,
        width="stretch",
    )

    run_lookup = {
        str(run["thread_id"]): run for run in valid_runs if run.get("thread_id")
    }
    thread_ids = list(run_lookup)

    selected_thread_id = st.selectbox(
        "Select a run",
        options=thread_ids,
        format_func=lambda value: history_option_label(
            value,
            run_lookup,
        ),
    )

    if st.button(
        "Open selected run",
        type="primary",
        width="stretch",
        key="open_history_run",
    ):
        open_history_run(selected_thread_id)
        st.rerun()

    history_detail = st.session_state.get("history_detail")

    if isinstance(history_detail, dict):
        render_history_detail(history_detail)


def render_analysis_workspace(backend_connected: bool) -> None:
    """Display the question, approval, and result workflow."""

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
    handle_question_submission(submitted, question)

    agent_start = st.session_state.get("agent_start")
    agent_decision = st.session_state.get("agent_decision")
    awaiting_approval = is_waiting_for_approval(
        agent_start,
        agent_decision,
    )

    render_agent_start_status(agent_start, awaiting_approval)
    render_agent_decision_status(agent_decision, agent_start)
    render_new_analysis_button(agent_start, awaiting_approval)


def main() -> None:
    """Render the complete Streamlit application."""

    apply_custom_styles()
    render_page_header()

    backend_connected, backend_message = check_backend()

    render_sidebar(backend_connected, backend_message)
    render_connection_banner(backend_connected, backend_message)

    analysis_tab, history_tab = st.tabs(["New analysis", "Run history"])

    with analysis_tab:
        render_analysis_workspace(backend_connected)

    with history_tab:
        render_history_panel(backend_connected)


if __name__ == "__main__":
    main()
