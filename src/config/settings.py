"""
Application settings loaded from environment variables.

This module uses Pydantic Settings to manage configuration from:
1. Environment variables
2. .env file
3. Default values
"""

from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with type validation.

    All settings can be overridden via environment variables or .env file.
    For example, to change the Ollama model, set OLLAMA_MODEL=llama3.2
    """

    # Ollama LLM Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama2"
    ollama_json_mode: bool = False

    # Data paths
    data_dir: Path = Path("data")

    # Agent configuration
    max_iterations: int = 3
    max_history_messages: int = 50

    # SQL Tool limits
    sql_max_joins: int = 3
    sql_max_subqueries: int = 5

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False
    )


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are loaded only once per process.

    Returns:
        Settings: The application settings
    """
    return Settings()
