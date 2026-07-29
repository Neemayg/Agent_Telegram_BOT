import os
import socket
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_free_port() -> int:
    """Finds and returns an available port on the local system."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Core secrets & configurations
    OPENAI_API_KEY: str = ""
    BOT_TOKEN: str = ""
    BASE_URL: Optional[str] = None

    # Server binding details
    HOST: str = "0.0.0.0"
    
    # Read PORT from environment or assign a dynamic free port
    PORT: int = int(os.getenv("PORT") or get_free_port())

    # Paths and directories (based on the project root)
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    LOGS_DIR: Path = BASE_DIR / "logs"
    CACHE_DIR: Path = BASE_DIR / ".cache"
    
    @property
    def runs_log_path(self) -> Path:
        return self.LOGS_DIR / "runs.jsonl"

    @property
    def chat_history_path(self) -> Path:
        return self.LOGS_DIR / "chat_history.json"

    def setup_directories(self) -> None:
        """Create logs and cache directories if they don't exist."""
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)


# Instantiate settings globally
settings = Settings()
settings.setup_directories()
