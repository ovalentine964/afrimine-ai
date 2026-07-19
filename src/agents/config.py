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
import pathlib
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("afrimine.config")


# ---------------------------------------------------------------------------
# .env file loading (runs at import time, before Settings creation)
# ---------------------------------------------------------------------------

def _try_load_dotenv() -> None:
    """Attempt to load a .env file from common locations into os.environ."""
    candidates = [
        pathlib.Path(__file__).parent / ".env",
        pathlib.Path(__file__).parent.parent / ".env",
        pathlib.Path.cwd() / ".env",
    ]
    for env_path in candidates:
        if env_path.is_file():
            try:
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and key not in os.environ:
                            os.environ[key] = value
                logger.info("Loaded environment from %s", env_path)
                return
            except Exception as exc:
                logger.debug("Could not load %s: %s", env_path, exc)
    logger.debug("No .env file found — using system environment only")


# Load .env before any Settings instantiation
_try_load_dotenv()


# ---------------------------------------------------------------------------
# Env helpers
# ---------------------------------------------------------------------------

def _env(key: str, default: str = "", required: bool = False) -> str:
    """Load an environment variable with optional requirement check.

    NOTE: required=True no longer raises at import time — it only logs a
    warning.  Call settings.validate() before pipeline execution to get a
    list of missing required variables.
    """
    value = os.environ.get(key, default)
    if required and not value:
        logger.warning(
            "Environment variable '%s' is not set (required for production). "
            "Pipeline will use defaults/fallbacks until configured.",
            key,
        )
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


# ---------------------------------------------------------------------------
# Settings dataclass
# ---------------------------------------------------------------------------

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
        """Validate configuration. Returns list of warnings/errors."""
        warnings = []
        if not self.SUPABASE_URL:
            warnings.append("CRITICAL: SUPABASE_URL not set — checkpointing and persistence disabled")
        if not self.SUPABASE_KEY:
            warnings.append("CRITICAL: SUPABASE_KEY not set — cannot connect to Supabase")
        if not self.GOOGLE_API_KEY:
            warnings.append("CRITICAL: GOOGLE_API_KEY not set — LLM calls will fail")
        if not self.GROQ_API_KEY:
            warnings.append("GROQ_API_KEY not set — no speed fallback")
        if not self.LANGSMITH_API_KEY:
            warnings.append("LANGSMITH_API_KEY not set — no tracing")
        return warnings

    def validate_or_raise(self) -> None:
        """Raise ValueError if required settings are missing. Call before production use."""
        missing = []
        if not self.SUPABASE_URL:
            missing.append("SUPABASE_URL")
        if not self.SUPABASE_KEY:
            missing.append("SUPABASE_KEY")
        if not self.GOOGLE_API_KEY:
            missing.append("GOOGLE_API_KEY")
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Set them in .env or as system environment variables."
            )


# Singleton — import this everywhere
settings = Settings()

# Configure logging level
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
