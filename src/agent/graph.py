"""
LangGraph Workflow Definition.

This module creates the agent's state machine (graph) that defines how
the agent thinks, acts, and responds.

LangGraph Concept:
-----------------
A graph is a state machine where:
- Nodes are functions that process state
- Edges define the flow between nodes
- Conditional edges choose paths based on state

Workflow (with SQL Guardrail):
START → THINK → (tool?) → ACT → OBSERVE → (continue?) → THINK/RESPOND → SQL_GUARD → (safe?) → END/THINK
"""

from langgraph.graph import StateGraph, END
from src.agent.state import AgentState
from src.agent.nodes import think_node, act_node, observe_node, respond_node
from src.agent.guards import sql_validation_guard
from src.config.settings import get_settings


def should_use_tool(state: AgentState) -> str:
    """
    Decision function: Does the LLM want to use a tool?

    Checks if the last message from the LLM contains tool calls.
    This is how LangChain indicates the LLM wants to execute a function.

    Args:
        state: Current agent state

    Returns:
        str: "use_tool" if tool requested, "respond" otherwise
    """
    last_message = state["messages"][-1]

    # Check if the message has tool_calls attribute and it's not empty
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "use_tool"

    return "respond"


def should_continue_thinking(state: AgentState) -> str:
    """
    Decision function: Should the agent continue reasoning?

    After observing tool results, decide whether to:
    1. Continue thinking (loop back to think_node)
    2. Finish and respond to user

    This prevents infinite loops and handles error cases.

    Args:
        state: Current agent state

    Returns:
        str: "continue" to keep thinking, "finish" to respond
    """
    settings = get_settings()

    # Check iteration limit to prevent infinite loops
    if state["iteration_count"] >= settings.max_iterations:
        return "finish"

    # Check the should_continue flag set by observe_node
    if state.get("should_continue", False):
        return "continue"

    return "finish"


def is_sql_safe(state: AgentState) -> str:
    """
    Decision function: Is the response safe from SQL perspective?

    This guard ensures no unvalidated SQL reaches the user.
    If unsafe SQL is detected, the response is regenerated.

    Args:
        state: Current agent state

    Returns:
        str: "safe" if no SQL violations, "unsafe" to force regeneration
    """
    # Default to safe if guard hasn't run (shouldn't happen)
    if not state.get("guard_checked", False):
        return "safe"

    # Check SQL safety flag set by sql_validation_guard
    return "safe" if state.get("sql_safe", True) else "unsafe"


def create_agent_graph():
    """
    Create the LangGraph workflow for the agent with tool support and SQL guardrail.

    Workflow Flow (with SQL Security Guard):
    -------------
    1. START → think_node
    2. think_node → (decision)
       - If tool requested → act_node
       - If no tool → respond_node
    3. act_node → observe_node
    4. observe_node → (decision)
       - If should continue → think_node (loop)
       - If finished → respond_node
    5. respond_node → sql_guard
    6. sql_guard → (decision)
       - If SQL safe → END
       - If SQL unsafe → think_node (regenerate response)

    Security Layer:
    --------------
    The SQL guard is a critical security layer that:
    - Scans all LLM responses for SQL content
    - Validates any SQL found against security rules
    - Forces response regeneration if unsafe SQL detected
    - Prevents prompt injection attacks that bypass tool use

    This creates a defense-in-depth approach:
    - Layer 1: System prompt instructs LLM to use sql_validator
    - Layer 2: SQL guard enforces validation (this layer)

    Returns:
        CompiledGraph: The compiled LangGraph workflow ready to execute
    """

    # Initialize the graph with our state schema
    graph = StateGraph(AgentState)

    # Add all nodes to the graph
    graph.add_node("think", think_node)
    graph.add_node("act", act_node)
    graph.add_node("observe", observe_node)
    graph.add_node("respond", respond_node)
    graph.add_node("sql_guard", sql_validation_guard)

    # Set the entry point
    graph.set_entry_point("think")

    # Add conditional edge from think_node
    # This decides whether to use a tool or respond directly
    graph.add_conditional_edges(
        "think",
        should_use_tool,
        {
            "use_tool": "act",
            "respond": "respond"
        }
    )

    # Add fixed edge from act to observe
    # After executing a tool, always observe the result
    graph.add_edge("act", "observe")

    # Add conditional edge from observe_node
    # This decides whether to continue thinking or finish
    graph.add_conditional_edges(
        "observe",
        should_continue_thinking,
        {
            "continue": "think",
            "finish": "respond"
        }
    )

    # Add SQL security guard after respond
    # This ensures all responses are checked for unvalidated SQL
    graph.add_edge("respond", "sql_guard")

    # Add conditional edge from sql_guard
    # If SQL violations found, regenerate response
    graph.add_conditional_edges(
        "sql_guard",
        is_sql_safe,
        {
            "safe": END,
            "unsafe": "think"  # Force regeneration
        }
    )

    # Compile the graph
    # This validates the structure and prepares it for execution
    return graph.compile()
