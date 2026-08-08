

from typing import AsyncGenerator, Optional
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings

_engine: Optional[AsyncEngine] = None
_sessionmaker: Optional[sessionmaker] = None
_init_lock: Optional[asyncio.Lock] = None


def _get_init_lock() -> asyncio.Lock:
    global _init_lock
    if _init_lock is None:
        _init_lock = asyncio.Lock()
    return _init_lock


def _create_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is required to create the async engine")
        _engine = create_async_engine(
            str(settings.database_url),
            echo=settings.debug,
            future=True,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        _sessionmaker = sessionmaker(
            bind=_engine,
            class_=AsyncSession,        # BUG 1 fix
            expire_on_commit=False,
            autoflush=False,
        )
    return _engine




def get_engine() -> AsyncEngine:
    return _create_engine()              # BUG 2 fix


def get_async_session() -> AsyncSession:
    if _sessionmaker is None:
        _create_engine()
    return _sessionmaker()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if _sessionmaker is None:
        _create_engine()
    async with _sessionmaker() as session:
        yield session


async def init_database() -> None:      # BUG 3 fix : one definition with lock
    async with _get_init_lock():
        if _engine is not None:
            return
        _create_engine()

    async with get_engine().begin() as conn:
        await conn.execute(text("SELECT 1"))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS agent_memory (
                user_id     TEXT PRIMARY KEY,
                memory_data JSONB NOT NULL,
                updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """))


async def close_db() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None


