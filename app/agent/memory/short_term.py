
from urllib.parse import urlsplit, urlunsplit
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.core.config import get_settings
from psycopg_pool import AsyncConnectionPool

settings = get_settings()
_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None



def _normalize_psycopg_dsn(dsn: str) -> str:
    parsed = urlsplit(dsn)
    scheme = parsed.scheme.split("+")[0]  
    if scheme == "postgres":
        scheme = "postgresql"             
    return urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment))

async def init_checkpointer() -> None:
    global _pool, _checkpointer
    _pool = AsyncConnectionPool(
        conninfo=_normalize_psycopg_dsn(str(settings.database_url)),
        min_size=2,
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0},
        open=False,
    )
    await _pool.open()
    _checkpointer = AsyncPostgresSaver(conn=_pool)
    await _checkpointer.setup()



def get_checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None:
        raise RuntimeError("Checkpointer not initialized — call init_checkpointer() at startup")
    return _checkpointer



async def close_checkpointer() -> None:
    global _pool
    if _pool:
        await _pool.close()



def get_thread_config(session_id: str, user_id: str) -> dict:
    return {
        "configurable": {
            "thread_id": f"{user_id}:{session_id}",
            "user_id": user_id,
        }
    }

