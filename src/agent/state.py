"""
LangGraph Agent State Definition.

This module defines the state structure that flows through the agent's graph.
Understanding state is key to understanding how LangGraph works.
"""

from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from operator import add


class AgentState(TypedDict):
    """
    State that flows through the LangGraph workflow.

    LangGraph Key Concept:
    ---------------------
    State is a dictionary that gets passed between nodes in the graph.
    Each node can read from the state and return updates to it.

    The `Annotated[Sequence[BaseMessage], add]` type means:
    - This field contains a sequence of messages
    - When a node returns new messages, they are ADDED to existing ones
    - This is controlled by the `add` reducer from the operator module

    Without the `add` reducer, returning messages would REPLACE the existing ones.

    Attributes:
        messages: The conversation history (user messages, AI responses, tool messages)
                 New messages are appended, not replaced
        user_input: The current user query
        tool_output: Result from the last tool execution (if any)
        iteration_count: Number of think-act cycles (prevents infinite loops)
        should_continue: Whether the agent should continue reasoning or finish
        sql_safe: Whether the response passes SQL validation (guard node)
        sql_violations: List of SQL security violations detected
        guard_checked: Flag indicating the SQL guard has run
    """

    # Conversation history - messages are appended (thanks to 'add' reducer)
    messages: Annotated[Sequence[BaseMessage], add]

    # Current user input
    user_input: str

    # Tool execution results (None if no tool was called)
    tool_output: str | None

    # Loop counter to prevent infinite reasoning
    iteration_count: int

    # Decision flag: should the agent continue thinking?
    should_continue: bool

    # SQL Safety Tracking (Guardrail System)
    # These fields are set by the sql_validation_guard node
    sql_safe: bool
    sql_violations: list
    guard_checked: bool
