

import time
from langchain_core.messages import ToolMessage
from app.agent.state import AgentState
from app.agent.tools.web_search import web_search
from app.agent.tools.calculator import calculator
from app.agent.tools.email_sender import send_email
from app.core.logging import get_logger

log = get_logger(__name__)



ALL_TOOLS = {
    "web_search": web_search,
    "calculator": calculator,
    "send_email": send_email,
}

async def tool_executor_node(state: AgentState) -> dict:
    """
    Run tools suggested by the last AIMessage.
    Returns updated messages (original + tool results) and trace information.
    """
    messages = list(state.get("messages", []))
    if not messages:
        return {
            "messages": messages,
            "workflow_trace": state.get("workflow_trace", []),
            "tool_call_history": state.get("tool_call_history", []),
        }

    last_message = messages[-1]
    tool_calls = getattr(last_message, "tool_calls", []) or []

    if not tool_calls:
        return {
            "messages": messages,
            "workflow_trace": state.get("workflow_trace", []),
            "tool_call_history": state.get("tool_call_history", []),
        }

    tool_messages = []
    executed_results = []

    for tool_call in tool_calls:
        # Extract tool call details (supports both dict and object)
        if isinstance(tool_call, dict):
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("args") or {}
            tool_call_id = tool_call.get("id")
        else:
            tool_name = getattr(tool_call, "name", None)
            tool_args = getattr(tool_call, "args", None) or {}
            tool_call_id = getattr(tool_call, "id", None)

        tool = ALL_TOOLS.get(tool_name)

        if tool is None:
            log.error("tool_not_found: %s", tool_name)
            error_message = f"Tool not available: {tool_name}"
            tool_messages.append(
                ToolMessage(content=error_message, tool_call_id=tool_call_id, name=tool_name)
            )
            executed_results.append({
                "tool": tool_name,
                "error": error_message,
            })
            continue


        try:
            log.info("executing_tool : %s args: %s", tool_name, tool_args)
            result = await tool.ainvoke(tool_args)

        
            tool_messages.append(
                ToolMessage(content=str(result), tool_call_id=tool_call_id, name=tool_name)
            )
            executed_results.append({
                "tool": tool_name,
                "args": tool_args,
                "result": result,
            })

        except Exception as e:
            log.exception("tool_execution_error: %s", tool_name)
            error_message = f"Error during {tool_name} tool execution: {e}"
            tool_messages.append(
                ToolMessage(content=error_message, tool_call_id=tool_call_id, name=tool_name)
            )
            executed_results.append({
                "tool": tool_name,
                "args": tool_args,
                "error": str(e),
            })

    # Update workflow trace
    workflow_trace = list(state.get("workflow_trace", []))
    workflow_trace.append({
        "node": "tool_executor",
        "status": "completed",
        "executed_results": executed_results,
        "timestamp": time.time(),
    })

    # Update tool call history
    tool_call_history = list(state.get("tool_call_history", []))
    tool_call_history.append(executed_results)

    return {
        "messages": messages + tool_messages,
        "workflow_trace": workflow_trace,
        "tool_call_history": tool_call_history,
    }






