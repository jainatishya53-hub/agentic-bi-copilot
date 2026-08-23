from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agentic_bi_copilot.agent.graph import get_agent_graph
from agentic_bi_copilot.agent.persistence import (
    close_checkpoint_pool,
    setup_checkpoint_database,
)
from agentic_bi_copilot.api.routes import router
from agentic_bi_copilot.schemas import HealthResponse
from agentic_bi_copilot.services.run_history import (
    setup_run_history_table,
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown tasks."""

    # Prepare both LangGraph storage and application history.
    setup_checkpoint_database()
    setup_run_history_table()

    try:
        yield
    finally:
        # Remove the cached graph before closing its database pool.
        get_agent_graph.cache_clear()
        close_checkpoint_pool()


app = FastAPI(
    title="Agentic BI Copilot API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return the current API health status."""

    return HealthResponse(status="healthy")
