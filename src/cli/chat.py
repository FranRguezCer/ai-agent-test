"""
Terminal-based Chat Interface.

This module provides a beautiful command-line interface for interacting
with the AI agent using Rich for formatting and prompt_toolkit for input.

Features:
- Rich formatted output (colors, panels, markdown)
- Command history (up/down arrow keys)
- Graceful shutdown (Ctrl+C)
- Clear conversation display
"""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from langchain_core.messages import HumanMessage


class ChatCLI:
    """
    Terminal-based chat interface for the AI agent.

    Uses Rich for beautiful formatting and prompt_toolkit for
    advanced input features like command history.
    """

    def __init__(self, agent_graph, history_manager=None):
        """
        Initialize the chat CLI.

        Args:
            agent_graph: Compiled LangGraph agent
            history_manager: Optional ChatHistoryManager for persistence
        """
        self.console = Console()
        self.agent = agent_graph
        self.history_manager = history_manager

        # Create prompt session with command history
        # History is saved to .chat_history file in the current directory
        self.session = PromptSession(
            history=FileHistory('.chat_history')
        )

    def print_welcome(self):
        """Display welcome message."""
        welcome_text = Text()
        welcome_text.append("AI Agent Chat\n", style="bold blue")
        welcome_text.append("Powered by LangGraph + Ollama\n\n", style="dim")
        welcome_text.append("Commands:\n", style="bold")
        welcome_text.append("  • Type your message and press Enter\n")
        welcome_text.append("  • 'quit' or 'exit' to end the session\n")
        welcome_text.append("  • Ctrl+C to interrupt\n")

        self.console.print(Panel(welcome_text, border_style="blue"))

    def print_user_message(self, message: str):
        """
        Display user message with formatting.

        Args:
            message: User's input message
        """
        self.console.print(f"\n[bold cyan]You:[/bold cyan] {message}")

    def print_agent_message(self, message: str):
        """
        Display agent response with markdown formatting.

        Args:
            message: Agent's response message
        """
        self.console.print("\n[bold green]Agent:[/bold green]")
        # Render as markdown for nice formatting of code blocks, lists, etc.
        self.console.print(Markdown(message))

    def print_thinking(self):
        """Display thinking indicator."""
        self.console.print("[dim]Agent is thinking...[/dim]")

    def print_error(self, error: str):
        """
        Display error message.

        Args:
            error: Error message to display
        """
        self.console.print(f"\n[bold red]Error:[/bold red] {error}")

    def run(self):
        """
        Main chat loop.

        Handles user input, agent execution, and display of responses.
        Runs until user types 'quit' or 'exit', or presses Ctrl+C.
        """
        self.print_welcome()

        while True:
            try:
                # Get user input with prompt
                user_input = self.session.prompt("\n> ")

                # Check for exit commands
                if user_input.lower().strip() in ['quit', 'exit', 'q']:
                    self.console.print("\n[bold blue]Goodbye![/bold blue]\n")
                    break

                # Skip empty inputs
                if not user_input.strip():
                    continue

                # Display user message
                self.print_user_message(user_input)

                # Save to history if manager is available
                if self.history_manager:
                    self.history_manager.add_message(
                        HumanMessage(content=user_input)
                    )

                # Show thinking indicator
                self.print_thinking()

                # Initialize agent state
                # This is the starting state for the LangGraph execution
                initial_state = {
                    "messages": [HumanMessage(content=user_input)],
                    "user_input": user_input,
                    "tool_output": None,
                    "iteration_count": 0,
                    "should_continue": False
                }

                # Run the agent graph
                # This executes the think→act→observe loop
                final_state = self.agent.invoke(initial_state)

                # Extract AI response from final state
                # The last message should be the agent's final response
                ai_message = final_state["messages"][-1]

                # Save to history if manager is available
                if self.history_manager:
                    self.history_manager.add_message(ai_message)
                    self.history_manager.flush()

                # Display response
                self.print_agent_message(ai_message.content)

            except KeyboardInterrupt:
                # Handle Ctrl+C gracefully
                self.console.print("\n\n[bold yellow]Interrupted[/bold yellow]")
                self.console.print("[bold blue]Goodbye![/bold blue]\n")
                break

            except Exception as e:
                # Display errors but don't crash
                self.print_error(str(e))
                # Continue the loop so user can try again
