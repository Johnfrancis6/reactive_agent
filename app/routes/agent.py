
import json
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.agent.graph import get_agent
from app.agent.memory.short_term import get_thread_config
from app.agent.memory.long_term import LongTermMemory
from app.core.config import get_settings
from app.agent.state import DEFAULT_MAX_ITERATIONS
from langgraph.types import Command
from langchain_groq import ChatGroq

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["Agent"])

settings = get_settings()
LTM = LongTermMemory()
_ltm_llm: ChatGroq | None = None


def _get_ltm_llm() -> ChatGroq:
    global _ltm_llm
    if _ltm_llm is None:
        _ltm_llm = ChatGroq(model=settings.llm_clarifier, temperature=0)
    return _ltm_llm





class AgentRequest(BaseModel):
    message: str
    session_id: str
    user_id: str = "anonymous"
    max_iterations: int = DEFAULT_MAX_ITERATIONS


class HumanApprovalRequest(BaseModel):
    session_id: str
    user_id: str
    approved: bool
    feedback: str = ""



@router.post("/chat")
async def chat(req: AgentRequest, db: AsyncSession = Depends(get_db)):
    try:
        agent = get_agent()
        config = get_thread_config(req.session_id, req.user_id)
        user_context = await LTM.load_user_context(req.user_id, db)

        result = await agent.ainvoke(
            {
                "messages": [{"role": "user", "content": req.message}],
                "session_id": req.session_id,
                "user_id": req.user_id,
                "user_context": user_context,
                "max_iterations": req.max_iterations,
                "workflow_trace": [],
                "tool_call_history": [],
            },
            config=config,
        )

        new_facts = await LTM.extract_facts_from_session(result["messages"], _get_ltm_llm())
        if new_facts:
            await LTM.update_user_context(req.user_id, new_facts, db)

        return {
            "response":                result.get("final_response", ""),
            "workflow_trace":          result.get("workflow_trace", []),
            "selected_tools":          result.get("selected_tools", []),
            "iterations":              result.get("iterations", 0),
            "blocked":                 result.get("blocked", False),
            "requires_human_approval": result.get("requires_human_approval", False),
            "hallucination_warning":   result.get("hallucination_warning", False),
        }
    except Exception as e:
        logger.error("chat_error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stream/{session_id}")
async def stream_workflow(session_id: str, user_id: str = "anonymous"):
    try:
        agent = get_agent()
        config = get_thread_config(session_id, user_id)
    except Exception as e:
        logger.error("stream_init_error: %s", e, exc_info=True)

        async def error_generator():
            yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'code': 'initialization_error'})}\n\n"

        return StreamingResponse(
            error_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def event_generator():
        try:
            async for event in agent.astream_events(None, config=config, version="v2"):
                event_type = event.get("event")
                node_name  = event.get("name", "")

                if event_type == "on_chain_start":
                    yield f"data: {json.dumps({'type': 'node_start', 'node': node_name})}\n\n"
                elif event_type == "on_chain_end":
                    yield f"data: {json.dumps({'type': 'node_end', 'node': node_name})}\n\n"
                elif event_type == "on_tool_start":
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': node_name})}\n\n"
                elif event_type == "on_tool_end":
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool': node_name})}\n\n"

                await asyncio.sleep(0)
        except Exception as e:
            logger.error("stream_execution_error: %s", e, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'code': 'execution_error'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/approve")
async def approve_action(req: HumanApprovalRequest, db: AsyncSession = Depends(get_db)):
    try:
        agent = get_agent()
        config = get_thread_config(req.session_id, req.user_id)

        result = await agent.ainvoke(
            Command(resume={"approved": req.approved, "feedback": req.feedback}),
            config=config,
        )

        if "messages" in result:
            new_facts = await LTM.extract_facts_from_session(result["messages"], _get_ltm_llm())
            if new_facts:
                await LTM.update_user_context(req.user_id, new_facts, db)

        return {
            "response":      result.get("final_response", ""),
            "approved":      req.approved,
            "workflow_trace": result.get("workflow_trace", []),
        }
    except Exception as e:
        logger.error("approval_error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")