"""
AfriMine AI — Unified LLM Provider
=====================================

Provides a single interface for all LLM calls with automatic fallback:
    NVIDIA NIM (primary) → Groq → Mistral → Ollama (offline)

NVIDIA NIM uses OpenAI-compatible API format, so we use langchain-openai's
ChatOpenAI pointed at the NVIDIA endpoint.

Usage:
    from llm_provider import get_llm, get_llm_with_fallback

    llm = get_llm()  # Returns primary (NVIDIA NIM)
    llm = get_llm_with_fallback()  # Returns first available provider
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_openai import ChatOpenAI

from config import settings

logger = logging.getLogger("afrimine.llm_provider")


# ---------------------------------------------------------------------------
# Provider constructors
# ---------------------------------------------------------------------------

def _create_nvidia_llm(
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> ChatOpenAI:
    """Create NVIDIA NIM LLM via OpenAI-compatible endpoint."""
    return ChatOpenAI(
        model=settings.NVIDIA_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        openai_api_key=settings.NVIDIA_API_KEY,
        openai_api_base=settings.NVIDIA_BASE_URL,
        # NVIDIA NIM specific headers
        default_headers={"Authorization": f"Bearer {settings.NVIDIA_API_KEY}"},
    )


def _create_groq_llm(
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> ChatOpenAI:
    """Create Groq LLM via OpenAI-compatible endpoint."""
    return ChatOpenAI(
        model=settings.GROQ_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        openai_api_key=settings.GROQ_API_KEY,
        openai_api_base="https://api.groq.com/openai/v1",
    )


def _create_mistral_llm(
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> ChatOpenAI:
    """Create Mistral LLM via OpenAI-compatible endpoint."""
    return ChatOpenAI(
        model=settings.MISTRAL_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        openai_api_key=settings.MISTRAL_API_KEY,
        openai_api_base="https://api.mistral.ai/v1",
    )


def _create_ollama_llm(
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> ChatOpenAI:
    """Create Ollama LLM for local/offline inference (Jetson, etc.)."""
    ollama_base = settings.OLLAMA_BASE_URL or "http://localhost:11434/v1"
    ollama_model = settings.OLLAMA_MODEL or "llama3.3:70b"
    return ChatOpenAI(
        model=ollama_model,
        temperature=temperature,
        max_tokens=max_tokens,
        openai_api_key="ollama",  # Ollama doesn't need a real key
        openai_api_base=ollama_base,
    )


# ---------------------------------------------------------------------------
# Provider registry (ordered by priority)
# ---------------------------------------------------------------------------

_PROVIDERS = [
    ("nvidia", _create_nvidia_llm, lambda: bool(settings.NVIDIA_API_KEY)),
    ("groq", _create_groq_llm, lambda: bool(settings.GROQ_API_KEY)),
    ("mistral", _create_mistral_llm, lambda: bool(settings.MISTRAL_API_KEY)),
    ("ollama", _create_ollama_llm, lambda: True),  # Always available as last resort
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_llm(
    provider: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> ChatOpenAI:
    """
    Get an LLM instance from the specified provider.

    Args:
        provider: Provider name ("nvidia", "groq", "mistral", "ollama").
                  If None, uses the primary provider (NVIDIA).
        temperature: Sampling temperature
        max_tokens: Maximum output tokens

    Returns:
        ChatOpenAI instance configured for the requested provider

    Raises:
        ValueError: If the requested provider is not configured
    """
    if provider is None:
        provider = "nvidia"

    constructors = {
        "nvidia": _create_nvidia_llm,
        "groq": _create_groq_llm,
        "mistral": _create_mistral_llm,
        "ollama": _create_ollama_llm,
    }

    if provider not in constructors:
        raise ValueError(f"Unknown LLM provider: {provider}. Choose from: {list(constructors.keys())}")

    return constructors[provider](temperature=temperature, max_tokens=max_tokens)


def get_llm_with_fallback(
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> tuple[ChatOpenAI, str]:
    """
    Get an LLM instance, trying providers in fallback order.

    Tries: NVIDIA NIM → Groq → Mistral → Ollama

    Args:
        temperature: Sampling temperature
        max_tokens: Maximum output tokens

    Returns:
        Tuple of (ChatOpenAI instance, provider name)

    Raises:
        RuntimeError: If no providers are available
    """
    errors = []

    for name, constructor, is_configured in _PROVIDERS:
        if not is_configured():
            logger.debug("Skipping %s — not configured", name)
            continue

        try:
            llm = constructor(temperature=temperature, max_tokens=max_tokens)
            logger.info("LLM provider selected: %s", name)
            return llm, name
        except Exception as e:
            errors.append(f"{name}: {e}")
            logger.warning("Failed to create %s LLM: %s", name, e)

    raise RuntimeError(
        f"No LLM providers available. Errors:\n" + "\n".join(errors)
    )


def get_provider_status() -> dict[str, dict[str, Any]]:
    """
    Get the configuration status of all LLM providers.

    Returns:
        Dict mapping provider name to status info
    """
    status = {}
    for name, _, is_configured in _PROVIDERS:
        configured = is_configured()
        status[name] = {
            "configured": configured,
            "available": configured,  # Could add health checks here
        }
    return status
