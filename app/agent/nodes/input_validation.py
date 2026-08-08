
import re
from app.agent.state import AgentState
from app.core.logging import get_logger
import time

log = get_logger(__name__)



_BLOCKED_PATTERNS_RAW = [
    r"ignore (all|previous|above) instructions",
    r"jailbreak",
    r"act as (DAN|an AI without restrictions)",
    r"bypass (safety|guardrails|filters)",
    r"you are now",
    r"pretend (you are|to be)",
    r"prompt injection",
]

BLOCKED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _BLOCKED_PATTERNS_RAW]

HIGH_RISK_KEYWORDS = [
    "remove", "erase", "delete",
    "drop table", "all data", "all users",
    "bank transfer", "transfer", "payment",
]

MAX_INPUT_LENGTH = 4000



async def input_validation_node(state: AgentState) -> dict:
    messages = state.get("messages", [])
    if not messages:
        return {"blocked": True, "block_reason": "No message received"}

    last_message = messages[-1]
    content = last_message.content if hasattr(last_message, "content") else str(last_message)

    if len(content) > MAX_INPUT_LENGTH:
        return {
            "blocked": True,
            "block_reason": f"Content too large: {len(content)} chars (max {MAX_INPUT_LENGTH})",
        }

    content_lower = content.lower()

    for pattern in BLOCKED_PATTERNS:
        if pattern.search(content_lower):
            log.warning("prompt_injection_detected: pattern=%s", pattern.pattern)
            return {
                "blocked": True,
                "block_reason": "Prompt injection detected",
            }

    risk_level = "low"
    requires_human = False
    for keyword in HIGH_RISK_KEYWORDS:
        if keyword in content_lower:
            risk_level = "high"
            requires_human = True
            log.warning("high_risk_keyword: keyword=%s", keyword)
            break

    workflow_trace = state.get("workflow_trace", [])
    workflow_trace.append({
        "node": "input_guard",
        "status": "passed",
        "risk_level": risk_level,
        "timestamp": time.time(),
    })

    return {
        "input_validated": True,
        "blocked": False,
        "risk_level": risk_level,
        "requires_human_approval": requires_human,
        "iterations": state.get("iterations", 0),
        "max_iterations": state.get("max_iterations", 10),
        "workflow_trace": workflow_trace,
    }