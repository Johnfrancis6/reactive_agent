
import json
from datetime import datetime, timezone
from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.logging import get_logger
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage

log = get_logger(__name__)


class LongTermMemory:

    async def load_user_context(
        self,
        user_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        result = await db.execute(
            text("SELECT memory_data FROM agent_memory WHERE user_id = :uid"),
            {"uid": user_id}
        )
        row = result.fetchone()

        if row and row[0] is not None:
            log.info("ltm_loaded: user_id=%s", user_id)
            if isinstance(row[0], dict):
                return row[0]
            return json.loads(row[0]) if isinstance(row[0], str) else {}

        return {}


    async def update_user_context(
        self,
        user_id: str,
        new_facts: Dict[str, Any],
        db: AsyncSession,
    ) -> None:
        if not new_facts:
            log.debug("ltm_update_skipped: no new facts for user_id=%s", user_id)
            return

        new_facts["last_updated"] = datetime.now(timezone.utc).isoformat()

        await db.execute(
            text("""
                INSERT INTO agent_memory (user_id, memory_data, updated_at)
                VALUES (:uid, CAST(:data AS jsonb), NOW())
                ON CONFLICT (user_id)
                DO UPDATE SET
                    memory_data = agent_memory.memory_data || CAST(:data AS jsonb),
                    updated_at  = NOW()
            """),
            {"uid": user_id, "data": json.dumps(new_facts)}
        )
        await db.commit()
        log.info("ltm_updated: user_id=%s keys=%s", user_id, list(new_facts.keys()))


    async def extract_facts_from_session(
        self,
        messages: List[BaseMessage],
        llm,
    ) -> Dict[str, Any]:
        conversation = "\n".join(
            f"{m.type}: {m.content[:200]}"
            for m in messages[-10:]
        )

        response = await llm.ainvoke([
            SystemMessage(content=(
                "Extract durable facts from this conversation "
                "(preferences, user information, habits). "
                'Respond in JSON format: {"facts": {"key": "value"}}. '
                'If no durable facts are found, respond with {"facts": {}}.'
            )),
            HumanMessage(content=conversation),
        ])

        try:
            raw = response.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw)
            return parsed.get("facts", {})
        except Exception as e:
            log.warning(
                "ltm_extract_parse_error: error=%s raw=%s",
                str(e),
                response.content[:200]
            )
            return {}