"""
LangGraph Node Functions.

Nodes are the building blocks of a LangGraph workflow. Each node is a function
that takes the current state and returns updates to that state.

This module implements all nodes for the agent workflow:
- think_node: LLM decides what to do (call tool or respond)
- act_node: Execute requested tool
- observe_node: Process tool results
- respond_node: Generate final response
"""

from langchain_core.messages import AIMessage, ToolMessage, SystemMessage
from src.agent.state import AgentState
from src.llm.ollama_client import get_llm
from src.tools.registry import get_tool_schemas, execute_tool


# System prompt to enforce SQL validation
SYSTEM_PROMPT = """You are a helpful AI assistant with access to SQL validation tools.

CRITICAL SECURITY RULES FOR SQL QUERIES:
========================================
1. ALWAYS use the 'sql_query_constructor' tool to validate ANY SQL query
2. NEVER write raw SQL queries directly in your response without validation
3. If a user provides SQL, you MUST validate it with the tool before discussing it
4. If you need to suggest SQL, use the tool FIRST, then present the validated result

Workflow for SQL-related requests:
1. User asks about SQL → Call sql_query_constructor tool
2. Tool validates the query → You explain the validation results
3. NEVER output SQL without going through the tool

This ensures all SQL queries are checked for security violations (destructive operations, complexity limits, etc.).
"""


def think_node(state: AgentState) -> dict:
    """
    THINK Node: The LLM analyzes the conversation and decides what to do.

    This is the core reasoning node. The LLM looks at the conversation history
    and decides whether to:
    1. Call a tool (via function calling)
    2. Respond directly to the user

    System Prompt Injection:
    -----------------------
    On the first message, we inject a system prompt with security rules.
    This instructs the LLM to ALWAYS use the sql_query_constructor tool
    for SQL-related queries.

    LangGraph Concept:
    -----------------
    A node is just a function that:
    1. Receives the current state
    2. Performs some operation (here: call the LLM)
    3. Returns a dict of state updates

    Args:
        state: Current agent state with conversation history

    Returns:
        dict: State updates (new messages, incremented iteration count)
    """
    # Get the LLM and bind available tools to it
    llm = get_llm()

    # Bind tools so the LLM knows what functions it can call
    # This enables function calling / tool use
    llm_with_tools = llm.bind_tools(get_tool_schemas())

    # Prepare messages with system prompt if this is the first turn
    messages = state["messages"]

    # Inject system prompt on first user message
    # Check if first message is NOT a SystemMessage
    if messages and not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

    # Invoke the LLM with the current conversation history
    # The LLM will either:
    # - Return a regular message (wants to respond)
    # - Return a message with tool_calls (wants to use a tool)
    response = llm_with_tools.invoke(messages)

    # Return state updates:
    # - Add the LLM's response to messages
    # - Increment the iteration counter
    return {
        "messages": [response],
        "iteration_count": state["iteration_count"] + 1,
    }


def respond_node(state: AgentState) -> dict:
    """
    RESPOND Node: Prepare the final response to the user.

    This node is called when the agent has finished reasoning and is ready
    to return a response. Currently, it's a pass-through since think_node
    already generated the response.

    In a more complex agent, this might format the response, add citations, etc.

    Args:
        state: Current agent state

    Returns:
        dict: Empty dict (no state changes needed)
    """
    # The response is already in the messages from think_node
    # This node just marks the end of the workflow
    return {}


def act_node(state: AgentState) -> dict:
    """
    ACT Node: Execute the tool requested by the LLM.

    This node is called when the LLM has decided to use a tool.
    It extracts the tool call from the last message, executes it,
    and returns the result as a ToolMessage.

    Error Handling:
    --------------
    If the tool execution fails, we catch the error and return it
    as a ToolMessage. This allows the LLM to see the error and
    potentially retry or respond differently.

    Args:
        state: Current agent state

    Returns:
        dict: State updates with tool execution result
    """
    # Get the last message (should be from think_node with tool_calls)
    last_message = state["messages"][-1]

    # Extract the first tool call
    # In a more advanced agent, you might handle multiple tool calls
    tool_call = last_message.tool_calls[0]

    try:
        # Execute the tool using the registry
        result = execute_tool(
            tool_name=tool_call["name"],
            tool_input=tool_call["args"]
        )

        # Create a ToolMessage with the result
        # The tool_call_id links this result back to the request
        tool_message = ToolMessage(
            content=str(result),
            tool_call_id=tool_call["id"]
        )
    except Exception as e:
        # If tool execution fails, return error as ToolMessage
        # The LLM can see this error and handle it
        tool_message = ToolMessage(
            content=f"Error: {str(e)}",
            tool_call_id=tool_call["id"]
        )

    # Return state updates
    return {
        "messages": [tool_message],
        "tool_output": tool_message.content
    }


def observe_node(state: AgentState) -> dict:
    """
    OBSERVE Node: Process tool results and decide next steps.

    After a tool executes, this node analyzes the result and decides
    whether the agent should:
    1. Continue thinking (e.g., if tool failed or needs more reasoning)
    2. Finish and respond to user

    This is a simple implementation. In a more advanced agent, you might
    add logic to parse tool outputs, check for specific conditions, etc.

    Args:
        state: Current agent state with tool execution results

    Returns:
        dict: State updates with should_continue flag
    """
    # Simple heuristic: if the tool returned an error, allow retry
    # Otherwise, proceed to respond
    should_continue = False

    if state.get("tool_output", "").startswith("Error:"):
        # Tool failed - let the LLM try again (if iterations allow)
        should_continue = True

    return {"should_continue": should_continue}
