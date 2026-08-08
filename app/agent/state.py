
from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

DEFAULT_MAX_ITERATIONS: int = 10



class AgentState(TypedDict):

    # Conversation
    messages: Annotated[list[BaseMessage], add_messages]

    # Planning
    current_plan: list[str]
    current_step: int
    task_complete: bool

    # Tools
    selected_tools: list[str]
    tool_call_history: list[dict]

    # Memory
    user_context: dict
    session_id: str
    user_id: str

    # Guardrails
    input_validated: bool
    output_validated: bool
    iterations: int
    max_iterations: int
    requires_human_approval: bool
    human_approved: bool | None

    # UI flow
    workflow_trace: list[dict]      # [{node, status, timestamp}]
    intermediate_results: list[dict]
    final_response: str | None

    # Security
    risk_level: Literal["low", "medium", "high"]
    blocked: bool
    block_reason: str | None
    hallucination_warning: bool     # surfaced by output_guard