#!/usr/bin/env python3
"""
AI Agent Template - Main Entry Point

This is the entry point for the AI agent application.
It initializes all components and starts the chat interface.

Usage:
    python main.py

Requirements:
    - Ollama must be running locally (default: http://localhost:11434)
    - A model must be downloaded (e.g., ollama pull llama2)

Environment Variables:
    See .env.example for configuration options
"""

from src.agent.graph import create_agent_graph
from src.cli.chat import ChatCLI
from src.memory.chat_history import ChatHistoryManager
from src.config.settings import get_settings


def main():
    """
    Initialize and run the AI agent.

    Steps:
    1. Load configuration from environment
    2. Initialize chat history manager
    3. Create the LangGraph agent
    4. Start the terminal chat interface
    """

    # Load settings from environment/.env
    settings = get_settings()

    print(f"Initializing AI Agent...")
    print(f"LLM: {settings.ollama_model} @ {settings.ollama_base_url}")
    print(f"Max iterations: {settings.max_iterations}")
    print()

    # Initialize chat history manager
    history_manager = ChatHistoryManager(settings.data_dir)
    session_id = history_manager.new_session()
    print(f"Started new session: {session_id}")
    print()

    # Create the LangGraph agent
    # This compiles the think→act→observe→respond workflow
    agent = create_agent_graph()

    # Start the chat interface
    cli = ChatCLI(agent, history_manager)
    cli.run()

    # Save history on exit
    history_manager.flush()
    print("Session saved.")


if __name__ == "__main__":
    main()
