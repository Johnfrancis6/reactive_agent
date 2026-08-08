
from langgraph.types import interrupt
from app.agent.state import AgentState
from app.core.logging import get_logger
import time

log = get_logger(__name__)



async def human_loop_node(state: AgentState) -> dict:
    messages = state.get("messages", [])
    last_msg = messages[-1] if messages else None
    pending_action = None

    if last_msg and hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        tc = last_msg.tool_calls[0]
        pending_action = tc if isinstance(tc, dict) else {
            "name": getattr(tc, "name", "unknown"),
            "args": getattr(tc, "args", {}),
            "id":   getattr(tc, "id", None),
        }

    log.info("human_approval_requested: action=%s", pending_action)

    decision = interrupt({
        "type": "human_approval",
        "pending_action": pending_action,
        "message": (
            f"Action required: {pending_action['name'] if pending_action else 'unknown'}\n"
            f"Arguments: {pending_action['args'] if pending_action else {}}\n"
            "Run this action?"
        ),
        "risk_level": state.get("risk_level", "medium"),
    })

    if isinstance(decision, dict):
        approved = decision.get("approved", False)
    elif isinstance(decision, bool):
        approved = decision
    else:
        approved = False
        log.warning("human_loop_unexpected_decision_format: received=%s", type(decision).__name__)  

    workflow_trace = state.get("workflow_trace", [])
    workflow_trace.append({
        "node": "human_loop",
        "status": "approved" if approved else "rejected",
        "timestamp": time.time(),
    })

    if not approved:
        return {
            "blocked": True,
            "block_reason": "Action rejected by the user",
            "human_approved": False,
            "workflow_trace": workflow_trace,
        }

    return {
        "human_approved": True,
        "requires_human_approval": False,
        "workflow_trace": workflow_trace,
    }