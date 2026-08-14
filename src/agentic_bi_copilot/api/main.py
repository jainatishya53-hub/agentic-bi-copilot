from fastapi import FastAPI

from agentic_bi_copilot.config import get_settings
from agentic_bi_copilot.schemas import HealthResponse

settings = get_settings()

app = FastAPI(
    title="Agentic BI Copilot API",
    description="Safe natural-language analytics for retail data.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="healthy")