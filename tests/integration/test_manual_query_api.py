from fastapi.testclient import TestClient

from agentic_bi_copilot.api.main import app
from agentic_bi_copilot.services.manual_pipeline import (
    PRIMARY_QUESTION,
)

client = TestClient(app)


def test_manual_query_endpoint() -> None:
    response = client.post(
        "/api/v1/manual-query",
        json={"question": PRIMARY_QUESTION},
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["mode"] == "manual"
    assert payload["safety"]["is_safe"]
    assert len(payload["rows"]) == 24
    assert payload["top_region"] == "North"
    assert len(payload["findings"]) == 3
    assert payload["findings"][0]["region"] == "West"
    assert payload["findings"][0]["month"] == "2026-07-01"
    assert len(payload["chart"]["data"]) == 5
    assert len(payload["follow_up_questions"]) == 3


def test_manual_query_rejects_unsupported_question() -> None:
    response = client.post(
        "/api/v1/manual-query",
        json={"question": "Which products sold the most?"},
    )

    assert response.status_code == 400
    assert "currently supports only" in response.json()["detail"]


def test_manual_query_validates_request_body() -> None:
    response = client.post(
        "/api/v1/manual-query",
        json={"question": "short"},
    )

    assert response.status_code == 422