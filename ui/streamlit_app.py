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


def request_analysis(question: str) -> dict[str, Any]:
    try:
        response = httpx.post(
            f"{settings.api_base_url}/api/v1/manual-query",
            json={"question": question},
            timeout=30.0,
        )
    except httpx.HTTPError as error:
        raise RuntimeError(
            f"Could not reach the analytics API: {error}"
        ) from error

    if response.is_error:
        try:
            detail = response.json().get(
                "detail",
                "The analytics request failed.",
            )
        except ValueError:
            detail = "The analytics request failed."

        raise RuntimeError(str(detail))

    payload = response.json()

    if not isinstance(payload, dict):
        raise TypeError(
            "The analytics API returned an unexpected response."
        )

    return payload


def format_currency(value: Any) -> str:
    return f"${float(value):,.2f}"


st.title("Agentic Analytics and BI Copilot")
st.caption(
    "Ask questions about retail performance and receive safe, "
    "explainable analysis."
)

backend_connected, backend_message = check_backend()

if backend_connected:
    st.success(backend_message)
else:
    st.error(backend_message)

st.info(
    "Development checkpoint: this screen uses a predefined analytical "
    "query. Human approval and LLM-generated SQL will be added next."
)

with st.form("business_question_form"):
    question = st.text_area(
        "Business question",
        value=PRIMARY_QUESTION,
        height=120,
    )

    submitted = st.form_submit_button(
        "Analyze",
        type="primary",
        disabled=not backend_connected,
    )

if submitted:
    cleaned_question = question.strip()

    if not cleaned_question:
        st.warning("Enter a business question before submitting.")
    else:
        st.session_state.pop("query_result", None)

        try:
            with st.spinner(
                "Validating SQL and analyzing retail data..."
            ):
                st.session_state["query_result"] = (
                    request_analysis(cleaned_question)
                )
        except (RuntimeError, TypeError) as error:
            st.error(str(error))

result = st.session_state.get("query_result")

if result:
    st.divider()
    st.subheader("Business answer")
    st.write(result["answer"])

    total_column, region_column, time_column = st.columns(3)

    total_column.metric(
        "Six-month revenue",
        format_currency(result["total_revenue"]),
    )
    region_column.metric(
        "Top region",
        result["top_region"],
        help=(
            "Revenue: "
            f"{format_currency(result['top_region_revenue'])}"
        ),
    )
    time_column.metric(
        "Database execution",
        f"{result['execution_time_ms']:.2f} ms",
    )

    overview_tab, data_tab, details_tab = st.tabs(
        [
            "Findings",
            "Data and chart",
            "Query details",
        ]
    )

    with overview_tab:
        st.subheader("Unusual declines")

        findings_frame = pd.DataFrame(result["findings"])

        if findings_frame.empty:
            st.info("No unusual declines were detected.")
        else:
            findings_frame = findings_frame.rename(
                columns={
                    "region": "Region",
                    "month": "Month",
                    "revenue": "Revenue",
                    "previous_month_revenue": (
                        "Previous month revenue"
                    ),
                    "change_pct": "Change (%)",
                }
            )
            st.dataframe(
                findings_frame,
                hide_index=True,
                width="stretch",
            )

        st.subheader("Suggested follow-up questions")

        for follow_up in result["follow_up_questions"]:
            st.markdown(f"- {follow_up}")

    with data_tab:
        st.subheader("Revenue trend")

        figure = go.Figure(result["chart"])
        st.plotly_chart(
            figure,
            width="stretch",
            config={"displaylogo": False},
        )

        st.subheader("Query result")

        result_frame = pd.DataFrame(result["rows"])
        st.dataframe(
            result_frame,
            hide_index=True,
            width="stretch",
        )

    with details_tab:
        st.subheader("Analysis plan")

        for step_number, plan_step in enumerate(
            result["analysis_plan"],
            start=1,
        ):
            st.markdown(f"{step_number}. {plan_step}")

        st.subheader("Selected tables")
        st.write(", ".join(result["selected_tables"]))

        st.subheader("SQL safety")

        safety = result["safety"]

        if safety["is_safe"]:
            st.success("SQL passed every required safety check.")
        else:
            st.error("SQL did not pass validation.")

        for check in safety["checks"]:
            st.markdown(f"- ✅ {check.replace('_', ' ').title()}")

        for error in safety["errors"]:
            st.markdown(f"- ❌ {error}")

        st.subheader("Executed SQL")
        st.code(result["sql"], language="sql")