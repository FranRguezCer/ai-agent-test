"""
Chat History Management with Persistent Storage.

This module handles saving and loading chat conversation history to/from disk.
Messages are stored in JSONL format (JSON Lines) for easy appending and reading.

Key Features:
- Session-based storage (each conversation is a separate file)
- JSONL format (one JSON object per line, appendable)
- Lazy loading (only load when needed)
- Write buffering (batch writes for performance)

Future Extension Point:
This is separate from vector DB functionality, which will be added later
in src/memory/vector_store.py for semantic search over knowledge bases.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage


class ChatHistoryManager:
    """
    Manages persistent chat history across sessions.

    Each chat session is stored as a separate JSONL file in the data directory.
    Messages can be appended to the current session and loaded from disk.

    Design Decisions:
    - JSONL format: Appendable without loading the entire file
    - Session-based: Each run creates a new session file
    - Lazy loading: Messages are only loaded when explicitly requested
    """

    def __init__(self, data_dir: Path):
        """
        Initialize the chat history manager.

        Args:
            data_dir: Base directory for data storage
        """
        self.data_dir = data_dir / "chat_history"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.current_session_file = None
        self.message_buffer = []

    def new_session(self) -> str:
        """
        Create a new chat session.

        Generates a unique session ID based on timestamp and creates
        a new JSONL file for this session.

        Returns:
            str: The session ID
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"session_{timestamp}"
        self.current_session_file = self.data_dir / f"{session_id}.jsonl"

        # Create empty file
        self.current_session_file.touch()

        return session_id

    def add_message(self, message: BaseMessage):
        """
        Add a message to the current session.

        Messages are buffered in memory and written to disk on flush().

        Args:
            message: A LangChain message object (HumanMessage, AIMessage, etc.)
        """
        # Convert message to dict for JSON serialization
        message_dict = {
            "timestamp": datetime.now().isoformat(),
            "type": message.__class__.__name__,
            "content": message.content,
        }

        # Add tool call information if present (for AIMessage)
        if hasattr(message, 'tool_calls') and message.tool_calls:
            message_dict["tool_calls"] = message.tool_calls

        # Add tool call ID if present (for ToolMessage)
        if hasattr(message, 'tool_call_id'):
            message_dict["tool_call_id"] = message.tool_call_id

        self.message_buffer.append(message_dict)

    def flush(self):
        """
        Write buffered messages to disk.

        This appends all buffered messages to the current session file
        and clears the buffer.
        """
        if not self.current_session_file or not self.message_buffer:
            return

        # Append messages to JSONL file
        with open(self.current_session_file, 'a', encoding='utf-8') as f:
            for message_dict in self.message_buffer:
                json_line = json.dumps(message_dict)
                f.write(json_line + '\n')

        # Clear buffer
        self.message_buffer.clear()

    def load_session(self, session_file: Path) -> List[dict]:
        """
        Load messages from a session file.

        Args:
            session_file: Path to the session JSONL file

        Returns:
            List[dict]: List of message dictionaries
        """
        messages = []

        if not session_file.exists():
            return messages

        with open(session_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    message_dict = json.loads(line)
                    messages.append(message_dict)

        return messages

    def get_recent_sessions(self, count: int = 5) -> List[Path]:
        """
        Get the most recent session files.

        Args:
            count: Number of recent sessions to return

        Returns:
            List[Path]: List of session file paths, most recent first
        """
        session_files = sorted(
            self.data_dir.glob("session_*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        return session_files[:count]


# Placeholder for future vector store integration
# This will be a separate module for semantic search over knowledge
