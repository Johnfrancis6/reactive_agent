
import re
from app.agent.state import AgentState
from app.core.logging import get_logger
from langchain_core.messages import AIMessage
import time

log = get_logger(__name__)

HALLUCINATION_SIGNALS = [re.compile(p, re.IGNORECASE) for p in [
    r"as of (my|my knowledge|training)",
    r"i (believe|think|assume) (that )?the (price|date|value)",
    r"approximately \$[\d,]+",
]]

SENSITIVE_PATTERNS = [re.compile(p) for p in [
    r"\b\d{16}\b",
    r"\b[A-Z0-9]{20,}\b",
    r"password\s*[:=]\s*\S+",
]]


async def output_validation_node(state: AgentState) -> dict:
    messages = state.get("messages", [])
    if not messages:
        return {"output_validated": False}


    last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
    if not last_ai:
        return {"output_validated": False}

    content = last_ai.content if hasattr(last_ai, "content") else ""

    
    if not content.strip():
        return {"output_validated": False}

    hallucination_warning = False
    for pattern in HALLUCINATION_SIGNALS:
        if pattern.search(content):
            log.warning("hallucination_signal_detected: pattern=%s", pattern.pattern)
            hallucination_warning = True 

    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(content):
            log.error("sensitive_data_in_output: pattern=%s", pattern.pattern)
            return {
                "output_validated": False,
                "block_reason": "Sensitive data detected in output",
            }

    workflow_trace = state.get("workflow_trace", [])
    workflow_trace.append({
        "node": "output_validation",
        "status": "passed",
        "timestamp": time.time(),
    })

    return {
        "output_validated": True,
        "final_response": content,
        "hallucination_warning": hallucination_warning,
        "workflow_trace": workflow_trace,
    }