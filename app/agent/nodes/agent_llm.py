
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage
from app.agent.state import AgentState
from app.agent.tools.web_search import web_search
from app.agent.tools.calculator import calculator
from app.agent.tools.email_sender import send_email
from app.prompts.system_prompt import build_system_prompt
from app.core.config import get_settings
from app.core.logging import get_logger
from functools import lru_cache
import time

log = get_logger(__name__)
settings = get_settings()

ALL_TOOLS = {
    "web_search": web_search,
    "calculator": calculator,
    "send_email": send_email,
}

TOOLS_DESCRIPTION = """
- web_search(query)                    : search the web for current information
- calculator(expression)               : evaluate a math expression safely
- send_email(to, subject, body, cc)    : send an email (human approval required)
"""



@lru_cache(maxsize=8)
def _get_bound_llm(tool_names: tuple) -> ChatGroq:
    tools = [ALL_TOOLS[n] for n in tool_names if n in ALL_TOOLS]
    return ChatGroq(
        model=settings.llm_generator,
        temperature=0,
        max_tokens=2048,
    ).bind_tools(tools or list(ALL_TOOLS.values()))



async def agent_llm_node(state: AgentState) -> dict:
    selected_tool_names = state.get("selected_tools", list(ALL_TOOLS.keys()))

    tool_key = tuple(sorted(name for name in selected_tool_names if name in ALL_TOOLS))
    if not tool_key:
        tool_key = tuple(sorted(ALL_TOOLS.keys()))

    llm = _get_bound_llm(tool_key)

    system_prompt = build_system_prompt(
        tools_description=TOOLS_DESCRIPTION,
        user_context=state.get("user_context", {}),
        current_plan=state.get("current_plan", []),
    )

    MAX_HISTORY_MESSAGES = 10
    history = state["messages"][-MAX_HISTORY_MESSAGES:]
    messages = [SystemMessage(content=system_prompt)] + history

    response = await llm.ainvoke(messages)

    messages_list = state.get("messages", [])
    last_is_human = (
        messages_list
        and hasattr(messages_list[-1], "type")
        and messages_list[-1].type == "human"
    )
    new_iterations = 1 if last_is_human else state.get("iterations", 0) + 1

    log.info(
        "agent_llm_invoked: iteration=%s has_tool_calls=%s active_tools=%s",
        new_iterations,
        bool(getattr(response, "tool_calls", [])),
        list(tool_key),
    )

    workflow_trace = state.get("workflow_trace", [])
    workflow_trace.append({
        "node": "agent",
        "status": "completed",
        "iteration": new_iterations,
        "tool_calls": [tc["name"] for tc in (response.tool_calls or []) if isinstance(tc, dict)],
        "timestamp": time.time(),
    })

    return {
        "messages": [response],
        "iterations": new_iterations,
        "selected_tools": list(tool_key),
        "workflow_trace": workflow_trace,
        "tool_call_history": [] if last_is_human else state.get("tool_call_history", []),
        "requires_human_approval": state.get("requires_human_approval", False),  
        "human_approved": state.get("human_approved"),                            
    }