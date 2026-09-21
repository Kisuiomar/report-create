"""
Configuration module for Offline Dossier Pipeline.
Air-gapped and offline settings with local LLM connectivity.
"""

from pathlib import Path
from typing import List, Literal, Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Project metadata
    PROJECT_NAME: str = "Offline Dossier & Entity Extraction Pipeline"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Base filesystem paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "data" / "uploads"
    OUTPUT_DIR: Path = BASE_DIR / "data" / "outputs"
    TEMP_DIR: Path = BASE_DIR / "data" / "temp"

    # Local LLM settings
    # Supports 'ollama' or 'vllm'
    LLM_PROVIDER: Literal["ollama", "vllm"] = "ollama"
    
    # Provider endpoints
    # Ollama default: http://localhost:11434
    # vLLM default: http://localhost:8000/v1
    LLM_BASE_URL: str = "http://localhost:11434"
    
    # Model identifier (e.g. qwen2.5:14b, qwen2.5:32b, Qwen/Qwen2.5-14B-Instruct)
    LLM_MODEL: str = "qwen2.5:3b"
    
    # Analytical parameters
    LLM_TEMPERATURE: float = 0.1
    LLM_NUM_CTX: int = 32768  # 32k context window support for 3b model
    LLM_REQUEST_TIMEOUT: float = 300.0  # 5 minutes for heavy dossiers
    LLM_MAX_RETRIES: int = 3

    # OCR and Parser Settings
    OCR_ENABLED: bool = True
    OCR_LANGUAGES: List[str] = Field(default_factory=lambda: ["ru", "en", "ch"])
    PDF_OCR_THRESHOLD_CHARS: int = 50  # Pages with fewer chars trigger OCR
    
    # Web & API settings
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8080  # 8080 to avoid conflict with vLLM default :8000
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["*"])

    @model_validator(mode="after")
    def _resolve_directories(self) -> "Settings":
        """Ensure directory paths are resolved relative to BASE_DIR when not overridden."""
        if self.UPLOAD_DIR == self.BASE_DIR / "data" / "uploads":
            self.UPLOAD_DIR = self.BASE_DIR / "data" / "uploads"
        if self.OUTPUT_DIR == self.BASE_DIR / "data" / "outputs":
            self.OUTPUT_DIR = self.BASE_DIR / "data" / "outputs"
        if self.TEMP_DIR == self.BASE_DIR / "data" / "temp":
            self.TEMP_DIR = self.BASE_DIR / "data" / "temp"
        return self

    def ensure_directories(self) -> None:
        """Create necessary directories if they do not exist."""
        for path in [self.UPLOAD_DIR, self.OUTPUT_DIR, self.TEMP_DIR]:
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
