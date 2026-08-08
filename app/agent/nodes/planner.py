
import json
import re
import time
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from app.agent.state import AgentState
from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)
settings = get_settings()


_planner_llm = ChatGroq(
    model=settings.llm_clarifier,
    temperature=0,
    max_tokens=1024,
)

AVAILABLE_TOOLS = ["web_search", "calculator", "send_email"]
VALID_RISK_LEVELS = {"low", "medium", "high"}


PLANNER_PROMPT = """
You are an expert task planner. Analyze the user's request and produce:

1. A plan with a maximum of 3-5 steps
2. A list of required tools selected only from: {available_tools}
3. A risk level: low | medium | high
4. Whether human approval is required

Rules:
- Be precise and concise.
- Plan only what is necessary.
- Use only the tools listed above.
- Do not select a tool if the task can be completed without it.
- Sending an email always requires human approval.
- If the task is simple, do not over-plan.
- Never invent tools that are not available.

Respond ONLY with valid JSON (no markdown, no explanation):
{{
  "plan": ["step 1", "step 2"],
  "required_tools": ["web_search", "calculator"],
  "risk_level": "low",
  "requires_human_approval": false,
  "reasoning": "Brief explanation"
}}
"""



def _extract_json(text: str) -> dict | None:
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    else:
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            text = match.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None



async def planner_node(state: AgentState) -> dict:
    last_user_message = ""
    for message in reversed(state.get("messages", [])):
        if hasattr(message, "type") and message.type == "human":
            last_user_message = message.content
            break

    if not last_user_message:
        log.warning("planner_no_user_message: using fallback")
        last_user_message = "Process the user's request."

    user_context = state.get("user_context", {})
    context_string = json.dumps(user_context, ensure_ascii=False)[:1000] if user_context else "No context available"

    tool_history = state.get("tool_call_history", [])[-2:]
    history_str = json.dumps(tool_history, ensure_ascii=False) if tool_history else "None"

    response = await _planner_llm.ainvoke([
        SystemMessage(content=PLANNER_PROMPT.format(
            available_tools=", ".join(AVAILABLE_TOOLS)
        )),
        HumanMessage(content=(
            f"Task: {last_user_message}\n"
            f"User context: {context_string}\n"
            f"Recent tool calls: {history_str}"
        )),
    ])

    plan_data = _extract_json(response.content)
    log.info("planner_output: %s", plan_data)
    if not plan_data or not isinstance(plan_data, dict):
        log.warning("planner_json_parse_error: content=%s", response.content[:200])
        plan_data = {}

    # Validate plan
    plan = plan_data.get("plan", [])
    if not plan or not isinstance(plan, list):
        plan = ["Process the request directly"]

    # Validate and filter tools
    required_tools = plan_data.get("required_tools", [])
    if not isinstance(required_tools, list):
        required_tools = []
    invalid_tools = [t for t in required_tools if t not in AVAILABLE_TOOLS]
    if invalid_tools:
        log.warning("planner_invalid_tools: %s", invalid_tools)
        required_tools = [t for t in required_tools if t in AVAILABLE_TOOLS]
    if not required_tools:
        log.warning("planner_no_valid_tools: falling back to empty tool list")

    # Validate risk level
    risk_level = plan_data.get("risk_level", "low")
    if risk_level not in VALID_RISK_LEVELS:
        log.warning("planner_invalid_risk: %s -> low", risk_level)
        risk_level = "low"

    # Validate approval flag
    requires_human_approval = plan_data.get("requires_human_approval", False)
    if not isinstance(requires_human_approval, bool):
        requires_human_approval = False

    reasoning = plan_data.get("reasoning", "Default plan")

    log.info(
        "plan_created: steps=%d tools=%s risk=%s",
        len(plan), required_tools, risk_level,
    )

    workflow_trace = list(state.get("workflow_trace", []))
    workflow_trace.append({
        "node": "planner",
        "status": "completed",
        "data": {
            "plan": plan,
            "required_tools": required_tools,
            "risk_level": risk_level,
            "requires_human_approval": requires_human_approval,
            "reasoning": reasoning,
        },
        "timestamp": time.time(),
    })

    return {
        "current_plan": plan,
        "selected_tools": required_tools,
        "risk_level": risk_level,
        "requires_human_approval": requires_human_approval,
        "workflow_trace": workflow_trace,
        "current_step": 0,
        "task_complete": False,
    }