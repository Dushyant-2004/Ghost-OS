from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.tasks import router as tasks_router
from app.api.browser import router as browser_router
from app.api.coding import router as coding_router
from app.api.approvals import router as approvals_router
from app.api.events import router as events_router
from app.api.artifacts import router as artifacts_router
from app.api.desktop import router as desktop_router
from app.api.memory import router as memory_router
from app.core.config import get_settings
from app.database.session import init_db
from app.schemas.task import HealthResponse


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(tasks_router)
app.include_router(browser_router)
app.include_router(coding_router)
app.include_router(approvals_router)
app.include_router(events_router)
app.include_router(artifacts_router)
app.include_router(desktop_router)
app.include_router(memory_router)


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        planner_provider=settings.llm_provider,
        planner_configured=settings.has_llm_credentials or settings.llm_provider.lower() == "demo",
    )
