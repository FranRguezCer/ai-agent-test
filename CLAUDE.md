# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI agent template built with LangGraph and Ollama. It implements an explicit state machine workflow (think→act→observe→respond) for tool-calling agents with persistent memory.

**Key Philosophy**: Explicit over implicit. The LangGraph state machine makes agent reasoning transparent and debuggable, unlike black-box agent frameworks.

## Development Commands

### Environment Setup
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Running the Agent
```bash
python main.py
```

Requires Ollama running locally:
```bash
ollama serve
ollama pull llama2  # or llama3.2
```

### Testing
```bash
# All tests
pytest

# Specific test file
pytest tests/test_sql_validator.py -v

# Single test
pytest tests/test_sql_validator.py::TestSQLValidator::test_valid_select_query -v

# With coverage
pytest --cov=src
```

### Configuration
Copy `.env.example` to `.env` to customize settings (Ollama URL, model, iteration limits, tool constraints).

## Architecture Deep Dive

### LangGraph State Machine Flow

The agent is a state machine defined in [src/agent/graph.py](src/agent/graph.py):

```
START → think_node → [conditional routing]
                         ↓                ↓
                    use tool?          respond?
                         ↓                ↓
                     act_node        respond_node → END
                         ↓
                   observe_node → [conditional routing]
                         ↓                ↓
                   continue?          finish?
                         ↓                ↓
                   think_node        respond_node → END
```

**Critical Concepts:**

1. **State Flow**: `AgentState` (defined in [src/agent/state.py](src/agent/state.py)) flows through nodes. The `messages` field uses an `add` reducer - new messages append rather than replace.

2. **Node Functions**: Each node ([src/agent/nodes.py](src/agent/nodes.py)) is a pure function that takes state and returns state updates as a dict.

3. **Conditional Edges**: Decision functions (`should_use_tool`, `should_continue_thinking`) examine state and return strings that map to next nodes.

4. **Iteration Limits**: The `iteration_count` prevents infinite loops. Max iterations configured via `MAX_ITERATIONS` env var.

### Tool System Architecture

**Registry Pattern** ([src/tools/registry.py](src/tools/registry.py)):
- Global singleton `_registry` maintains all available tools
- Tools auto-register on import (import side-effect in tool modules)
- `get_tool_schemas()` returns tools for LLM binding (function calling)
- `execute_tool()` dispatches by name

**Adding Tools**:
1. Create `@tool` decorated function in `src/tools/your_tool.py`
2. Add registration at bottom of file: `from src.tools.registry import register_tool; register_tool(your_tool)`
3. Tool is immediately available to agent (no graph changes needed)

**Tool Execution Flow**:
1. `think_node`: LLM with `.bind_tools()` can request tool via function calling
2. `should_use_tool()`: Checks if `last_message.tool_calls` exists
3. `act_node`: Executes tool, wraps result in `ToolMessage` with `tool_call_id` linkage
4. `observe_node`: Analyzes result, sets `should_continue` flag
5. `should_continue_thinking()`: Routes to either loop back or finish

### Memory Architecture

**Separation of Concerns**:
- **Chat History** ([src/memory/chat_history.py](src/memory/chat_history.py)): Conversational context, JSONL files
- **Vector Store** ([src/memory/vector_store.py](src/memory/vector_store.py)): Placeholder for semantic search over knowledge bases

**JSONL Format**: One JSON object per line. Appendable without loading entire file. Session-based files in `data/chat_history/`.

**Buffer Strategy**: Messages buffer in memory, flushed on demand or at session end.

### Configuration System

[src/config/settings.py](src/config/settings.py) uses Pydantic Settings:
- Environment variables override `.env` override defaults
- Type-safe with validation
- Cached with `@lru_cache` - loaded once per process
- Access via `get_settings()`

### LLM Abstraction

[src/llm/ollama_client.py](src/llm/ollama_client.py) wraps ChatOllama:
- Cached with `@lru_cache` to avoid multiple connections
- Configured from settings (model, base_url, temperature)
- Easy to swap providers (see README Future Extensions)

## Code Patterns and Conventions

### State Updates
Nodes return dict updates, not full state. Only changed fields:
```python
return {
    "messages": [response],  # Appends due to 'add' reducer
    "iteration_count": state["iteration_count"] + 1
}
```

### Error Handling in Nodes
Wrap tool execution in try/except, return errors as ToolMessages so LLM sees them:
```python
try:
    result = execute_tool(...)
    tool_message = ToolMessage(content=str(result), tool_call_id=...)
except Exception as e:
    tool_message = ToolMessage(content=f"Error: {str(e)}", tool_call_id=...)
```

### Tool Validation Pattern
See [src/tools/sql_validator.py](src/tools/sql_validator.py) for multi-layer validation:
1. Syntax parsing (sqlparse)
2. Statement type check (allowlist)
3. Keyword scanning (blocklist)
4. Complexity limits (recursive tree traversal)
5. Structured result object

## Testing Approach

Tests in [tests/test_sql_validator.py](tests/test_sql_validator.py) demonstrate:
- Positive cases (valid queries pass)
- Negative cases (blocked keywords, exceeded limits)
- Boundary cases (exactly at limit)
- Error cases (empty, invalid syntax)
- Tool function integration (invoke via LangChain interface)

**When testing new tools**: Follow this pattern - test validation logic separately from tool function wrapper.

## Extension Points

### Adding Vector DB (Future)
1. Implement `VectorStoreManager` in [src/memory/vector_store.py](src/memory/vector_store.py)
2. Create semantic search tool with `@tool` decorator
3. Register tool - agent can now search knowledge base

**Keep Separate**: Don't mix vector store with chat history. Different access patterns (semantic vs sequential).

### Modifying Agent Workflow
Edit [src/agent/graph.py](src/agent/graph.py):
- Add nodes to `graph.add_node()`
- Add edges (fixed or conditional)
- Update decision functions for new routing logic
- Recompile with `graph.compile()`

### Switching LLM Providers
Modify [src/llm/ollama_client.py](src/llm/ollama_client.py):
- Replace `ChatOllama` import
- Update `get_llm()` to return different provider
- Adjust settings for new provider's config needs

## Important Constraints

### SQL Validator Limits
Configurable via environment:
- `SQL_MAX_JOINS`: Default 3
- `SQL_MAX_SUBQUERIES`: Default 5
- Only SELECT allowed, all mutations blocked

### Agent Iteration Limits
- `MAX_ITERATIONS`: Default 3 (prevents infinite think-act loops)
- Enforced in `should_continue_thinking()` decision function

### Ollama Requirements
- Must be running on `OLLAMA_BASE_URL` (default: localhost:11434)
- Model must be pulled (`ollama pull <model>`)
- Agent fails fast if connection unavailable

## Debugging Tips

### LangGraph Execution
State machine is deterministic. To debug:
1. Print state at node entry/exit
2. Check decision function return values
3. Verify conditional edge mappings match decision outputs

### Tool Issues
1. Check tool registration completed (import side-effect)
2. Verify `get_tool_schemas()` includes your tool
3. Test tool function directly before testing through agent
4. Check `ToolMessage.tool_call_id` matches request

### Memory Issues
JSONL files corrupt? Each line must be valid JSON. Use `json.loads()` to validate.

## File Organization Principles

- **State/Logic Separation**: State definition ([state.py](src/agent/state.py)) separate from node logic ([nodes.py](src/agent/nodes.py)) separate from graph assembly ([graph.py](src/agent/graph.py))
- **Single Responsibility**: Each tool in own file, each node focused on one step
- **Registry Pattern**: Centralized discovery, decentralized implementation
- **Placeholder Pattern**: Empty files ([vector_store.py](src/memory/vector_store.py)) document future extensions with comments
