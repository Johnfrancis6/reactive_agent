
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.core.database import init_database, close_db
from app.core.logging import get_logger
from app.routes.agent import router as api_router
from app.agent.graph import init_agent
from app.agent.memory.short_term import close_checkpointer

settings = get_settings()
logger = get_logger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if settings.database_url:
        await init_database()
        await init_agent()
        logger.info("agent_ready")
    else:
        logger.warning("DATABASE_URL not configured — agent disabled")

    yield

    # Shutdown
    await close_checkpointer()
    await close_db()


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins, 
    allow_credentials=True,
    allow_headers=["*"],
    allow_methods=["*"],
)

app.include_router(api_router)


@app.get("/", tags=["Root"])
async def root() -> dict:
    return {
        "message": "React Agent API is running.",
        "health":  "/health",
        "docs":    "/docs",
        "agent":   "/agent/chat",
    }


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Returns environment name — confirms whether you're hitting dev or prod."""
    return {"status": "ok", "environment": settings.environment}





