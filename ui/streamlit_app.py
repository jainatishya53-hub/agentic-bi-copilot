import httpx
import streamlit as st

from agentic_bi_copilot.config import get_settings

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

with st.form("business_question_form"):
    question = st.text_area(
        "Business question",
        placeholder=(
            "Compare revenue across regions for the last six complete "
            "months and identify unusual declines."
        ),
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
        st.info(
            "Question received. The analytical workflow will be "
            "connected in a later step."
        )
        st.code(cleaned_question, language=None)