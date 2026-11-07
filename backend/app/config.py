"""Runtime configuration. All secrets are read server-side from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'brandguard.db'}"))
    # LLM provider: "none" (default), "anthropic", "openai" (any OpenAI-compatible endpoint) or "mock" (tests only)
    llm_provider: str = field(default_factory=lambda: os.getenv("BRANDGUARD_LLM_PROVIDER", "none").lower())
    llm_api_key: str = field(default_factory=lambda: os.getenv("BRANDGUARD_LLM_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("BRANDGUARD_LLM_MODEL", ""))
    llm_base_url: str = field(default_factory=lambda: os.getenv("BRANDGUARD_LLM_BASE_URL", ""))
    llm_timeout_s: int = field(default_factory=lambda: _int("BRANDGUARD_LLM_TIMEOUT", 25))
    max_upload_mb: int = field(default_factory=lambda: _int("BRANDGUARD_MAX_UPLOAD_MB", 10))
    max_content_chars: int = field(default_factory=lambda: _int("BRANDGUARD_MAX_CONTENT_CHARS", 20000))
    sandbox_ttl_hours: int = field(default_factory=lambda: _int("BRANDGUARD_SANDBOX_TTL_HOURS", 72))
    demo_rate_limit_per_hour: int = field(default_factory=lambda: _int("BRANDGUARD_DEMO_RATE_LIMIT", 30))
    cors_origins: list[str] = field(default_factory=lambda: [
        o.strip() for o in os.getenv("BRANDGUARD_CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()])
    frontend_dist: Path = field(default_factory=lambda: Path(os.getenv(
        "BRANDGUARD_FRONTEND_DIST", str(BASE_DIR.parent / "frontend" / "dist"))))


settings = Settings()
