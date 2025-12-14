"""
Ollama LLM client wrapper.

This module provides a simple interface to connect to a local Ollama instance.
The client is cached to avoid creating multiple connections.
"""

from functools import lru_cache
from langchain_ollama import ChatOllama
from src.config.settings import get_settings


@lru_cache(maxsize=1)
def get_llm(temperature: float = 0.7) -> ChatOllama:
    """
    Get Ollama LLM instance (cached).

    The LLM is configured from settings and cached for reuse across the application.
    This prevents creating multiple connections to Ollama.

    Args:
        temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative)
                    Default is 0.7 for balanced responses

    Returns:
        ChatOllama: Configured Ollama chat model

    Example:
        >>> llm = get_llm()
        >>> response = llm.invoke("Hello, how are you?")
    """
    settings = get_settings()

    return ChatOllama(
        model=settings.ollama_model,
        temperature=temperature,
        base_url=settings.ollama_base_url,
        # Enable JSON mode if configured (useful for structured outputs)
        format="json" if settings.ollama_json_mode else None,
    )
