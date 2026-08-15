def main() -> None:
    print("Agentic Analytics and BI Copilot")
    print()
    print(
        "Start the API: uv run uvicorn "
        "agentic_bi_copilot.api.main:app "
        "--host 127.0.0.1 --port 8000"
    )
    print("Start the UI: uv run streamlit run ui/streamlit_app.py")
