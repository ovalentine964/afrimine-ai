"""
AfriMine AI — Configuration Management
========================================

Centralized configuration with environment variable loading, validation,
feature flags, and sensible defaults. All secrets come from env vars —
never hardcoded.

Usage:
    from config import settings
    print(settings.GEMINI_MODEL)
    print(settings.SUPABASE_URL)
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("afrimine.config")


def _env(key: str, default: str = "", required: bool = False) -> str:
    """Load an environment variable with optional requirement check."""
    value = os.environ.get(key, default)
    if required and not value:
        raise EnvironmentError(f"Required environment variable '{key}' is not set")
    return value


def _env_bool(key: str, default: bool = False) -> bool:
    """Load a boolean environment variable."""
    return os.environ.get(key, str(default)).lower() in ("true", "1", "yes")


def _env_int(key: str, default: int = 0) -> int:
    """Load an integer environment variable."""
    try:
        return int(os.environ.get(key, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable application settings loaded from environment."""

    # ── Supabase ───────────────────────────────────────────────────────────
    SUPABASE_URL: str = field(default_factory=lambda: _env("SUPABASE_URL", required=True))
    SUPABASE_KEY: str = field(default_factory=lambda: _env("SUPABASE_KEY", required=True))
    SUPABASE_DB_HOST: str = field(default_factory=lambda: _env("SUPABASE_DB_HOST"))
    SUPABASE_DB_PASSWORD: str = field(default_factory=lambda: _env("SUPABASE_DB_PASSWORD"))

    # ── LLM API Keys ──────────────────────────────────────────────────────
    GOOGLE_API_KEY: str = field(default_factory=lambda: _env("GOOGLE_API_KEY", required=True))
    GROQ_API_KEY: str = field(default_factory=lambda: _env("GROQ_API_KEY"))
    MISTRAL_API_KEY: str = field(default_factory=lambda: _env("MISTRAL_API_KEY"))

    # ── LLM Models ────────────────────────────────────────────────────────
    GEMINI_MODEL: str = field(default_factory=lambda: _env("GEMINI_MODEL", "gemini-2.5-flash"))
    GROQ_MODEL: str = field(default_factory=lambda: _env("GROQ_MODEL", "llama-3.3-70b-versatile"))
    MISTRAL_MODEL: str = field(default_factory=lambda: _env("MISTRAL_MODEL", "mistral-large-latest"))

    # ── Observability ─────────────────────────────────────────────────────
    LANGSMITH_API_KEY: str = field(default_factory=lambda: _env("LANGSMITH_API_KEY"))
    LANGSMITH_PROJECT: str = field(default_factory=lambda: _env("LANGSMITH_PROJECT", "afrimine-ai"))
    SENTRY_DSN: str = field(default_factory=lambda: _env("SENTRY_DSN"))

    # ── Earth Engine ──────────────────────────────────────────────────────
    EARTH_ENGINE_KEY: str = field(default_factory=lambda: _env("EARTH_ENGINE_KEY"))

    # ── Security ──────────────────────────────────────────────────────────
    RATE_LIMIT_RPM: int = field(default_factory=lambda: _env_int("RATE_LIMIT_RPM", 60))
    MAX_INPUT_LENGTH: int = field(default_factory=lambda: _env_int("MAX_INPUT_LENGTH", 10000))
    MAX_OUTPUT_LENGTH: int = field(default_factory=lambda: _env_int("MAX_OUTPUT_LENGTH", 50000))

    # ── Pipeline ──────────────────────────────────────────────────────────
    MAX_REFINEMENT_LOOPS: int = field(default_factory=lambda: _env_int("MAX_REFINEMENT_LOOPS", 3))
    NODE_TIMEOUT_SECONDS: int = field(default_factory=lambda: _env_int("NODE_TIMEOUT_SECONDS", 120))
    MAX_RETRIES: int = field(default_factory=lambda: _env_int("MAX_RETRIES", 3))
    RETRY_BASE_DELAY: float = field(default_factory=lambda: float(os.environ.get("RETRY_BASE_DELAY", "1.0")))

    # ── Checkpoint ────────────────────────────────────────────────────────
    MAX_CHECKPOINTS_PER_THREAD: int = field(
        default_factory=lambda: _env_int("MAX_CHECKPOINTS_PER_THREAD", 50)
    )
    CHECKPOINT_ENABLED: bool = field(default_factory=lambda: _env_bool("CHECKPOINT_ENABLED", True))

    # ── Feature Flags ─────────────────────────────────────────────────────
    ENABLE_SATELLITE: bool = field(default_factory=lambda: _env_bool("ENABLE_SATELLITE", False))
    ENABLE_VOICE: bool = field(default_factory=lambda: _env_bool("ENABLE_VOICE", False))
    ENABLE_QUANTUM: bool = field(default_factory=lambda: _env_bool("ENABLE_QUANTUM", False))
    ENABLE_HITL: bool = field(default_factory=lambda: _env_bool("ENABLE_HITL", False))
    DEBUG: bool = field(default_factory=lambda: _env_bool("DEBUG", False))

    # ── LLM Fallback Chain ────────────────────────────────────────────────
    @property
    def llm_fallback_chain(self) -> list[str]:
        """Ordered list of LLM providers to try on failure."""
        chain = ["gemini"]
        if self.GROQ_API_KEY:
            chain.append("groq")
        if self.MISTRAL_API_KEY:
            chain.append("mistral")
        return chain

    def validate(self) -> list[str]:
        """Validate configuration. Returns list of warnings."""
        warnings = []
        if not self.SUPABASE_URL:
            warnings.append("SUPABASE_URL not set — checkpointing disabled")
        if not self.GOOGLE_API_KEY:
            warnings.append("GOOGLE_API_KEY not set — LLM calls will fail")
        if not self.GROQ_API_KEY:
            warnings.append("GROQ_API_KEY not set — no speed fallback")
        if not self.LANGSMITH_API_KEY:
            warnings.append("LANGSMITH_API_KEY not set — no tracing")
        return warnings


# Singleton — import this everywhere
settings = Settings()

# Configure logging level
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
