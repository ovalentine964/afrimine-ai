"""
AfriMine AI — Security Middleware
===================================

Input sanitization, output filtering, rate limiting, and injection detection.
Defense-in-depth: each layer is independent — if one fails, others contain
the blast radius.

Layers:
    1. Input classification (injection detection)
    2. State sanitization (per-agent input filtering)
    3. Output sanitization (PII stripping, credential redaction)
    4. Rate limiting (per-agent request/token budgets)
"""

from __future__ import annotations

import re
import time
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("afrimine.security")

# ── Injection Detection Patterns ──────────────────────────────────────────

INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore\s+(previous|all|above)\s+(instructions?|prompts?)"),
    re.compile(r"(?i)you\s+are\s+now\s+"),
    re.compile(r"(?i)system\s*:\s*"),
    re.compile(r"(?i)assistant\s*:\s*"),
    re.compile(r"(?i)new\s+instructions?\s*:"),
    re.compile(r"(?i)override\s+(safety|security|rules)"),
    re.compile(r"(?i)act\s+as\s+if"),
    re.compile(r"(?i)pretend\s+you\s+are"),
    re.compile(r"(?i)disregard\s+(your|the|all)\s+"),
    re.compile(r"(?i)forget\s+(everything|all|your)\s+"),
    re.compile(r"(?i)jailbreak"),
    re.compile(r"(?i)DAN\s+mode"),
]

# ── PII Patterns ──────────────────────────────────────────────────────────

PII_PATTERNS = {
    "national_id": (re.compile(r"\b\d{8,10}\b"), "[REDACTED_ID]"),
    "kenya_phone": (re.compile(r"\+?25[0-9]\d{8,}"), "[REDACTED_PHONE]"),
    "email": (
        re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        "[REDACTED_EMAIL]",
    ),
}

CREDENTIAL_PATTERN = re.compile(
    r"(?i)(supabase|api[_-]?key|secret|token|password)\s*[:=]\s*\S+"
)

GPS_PRECISION_PATTERN = re.compile(r"(-?\d{1,3})\.(\d{6,})")


# ── Agent Read-Key Map ────────────────────────────────────────────────────

AGENT_READ_KEYS: dict[str, list[str]] = {
    "sampling": ["location", "sample_data", "satellite_imagery", "analysis_result"],
    "analysis": ["sample_data", "satellite_imagery", "analysis_result", "sampling_result"],
    "geology": ["analysis_result", "location", "satellite_imagery", "sample_data"],
    "market": ["analysis_result", "location"],
    "report": [
        "analysis_result", "geology_result", "market_result",
        "compliance_result", "sampling_result", "location",
    ],
    "compliance": ["report_result", "analysis_result", "location", "market_result", "geology_result"],
}


# ── Input Classification ──────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    label: str  # "SAFE", "SUSPICIOUS", "MALICIOUS"
    confidence: float
    matches: int

    def __iter__(self):
        """Allow tuple unpacking: label, score, matches = classify_input(text)"""
        return iter((self.label, self.confidence, self.matches))


def classify_input(text: str) -> ClassificationResult:
    """
    Classify input text for prompt injection attempts.

    Returns:
        ClassificationResult with label and confidence.
    """
    text_lower = text.lower()
    matches = sum(1 for p in INJECTION_PATTERNS if p.search(text_lower))

    if matches >= 2:
        return ClassificationResult("MALICIOUS", 0.95, matches)
    elif matches == 1:
        return ClassificationResult("SUSPICIOUS", 0.7, matches)
    else:
        # Heuristic: long text with imperative language
        if len(text) > 5000 and "you must" in text_lower:
            return ClassificationResult("SUSPICIOUS", 0.6, 0)
        return ClassificationResult("SAFE", 0.9, 0)


def sanitize_input_text(text: str, max_length: int = 10000) -> tuple[str, bool]:
    """
    Sanitize raw input text.

    Returns:
        (sanitized_text, is_safe) — is_safe=False if injection detected.
    """
    result = classify_input(text)
    if result.label == "MALICIOUS":
        logger.warning(f"Malicious input detected (confidence={result.confidence})")
        return "", False

    # Truncate
    if len(text) > max_length:
        text = text[:max_length]

    # Strip null bytes
    text = text.replace("\x00", "")

    return text, result.label != "SUSPICIOUS"


# ── State Sanitization ────────────────────────────────────────────────────

def _sanitize_strings_recursive(value: Any) -> Any:
    """Recursively sanitize string values in dicts/lists."""
    if isinstance(value, str):
        for pattern in INJECTION_PATTERNS:
            value = pattern.sub("[FILTERED]", value)
        return value
    elif isinstance(value, dict):
        return {k: _sanitize_strings_recursive(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_sanitize_strings_recursive(v) for v in value]
    return value


def sanitize_state_for_agent(state: dict[str, Any], agent_role: str) -> dict[str, Any]:
    """
    Filter and sanitize state for a specific agent.
    Returns a copy with only the keys the agent should read,
    with injection patterns scrubbed from string values.
    """
    read_keys = AGENT_READ_KEYS.get(agent_role, list(state.keys()))
    filtered = {}

    for key in read_keys:
        value = state.get(key)
        if value is not None:
            filtered[key] = _sanitize_strings_recursive(value)

    return filtered


# ── Output Sanitization ───────────────────────────────────────────────────

@dataclass
class SanitizationResult:
    output: str
    redactions: int
    warnings: list[str] = field(default_factory=list)


def sanitize_output(
    output: str,
    agent_role: str,
    user_role: str = "field_worker",
    max_length: int = 50000,
) -> SanitizationResult:
    """
    Multi-layer output sanitization.

    Layers:
        1. Injection pattern removal
        2. PII stripping (unless admin)
        3. GPS precision reduction (unless admin/geologist)
        4. Credential redaction
        5. Length limiting
    """
    redactions = 0
    warnings = []

    # Layer 1: Strip injection attempts
    for pattern in INJECTION_PATTERNS:
        if pattern.search(output):
            output = pattern.sub("[FILTERED]", output)
            redactions += 1

    # Layer 2: Strip PII (unless admin)
    if user_role != "admin":
        for pii_type, (pattern, replacement) in PII_PATTERNS.items():
            matches = pattern.findall(output)
            if matches:
                output = pattern.sub(replacement, output)
                redactions += len(matches)

    # Layer 3: GPS precision reduction
    if user_role not in ("admin", "geologist"):
        gps_matches = GPS_PRECISION_PATTERN.findall(output)
        if gps_matches:
            output = GPS_PRECISION_PATTERN.sub(
                lambda m: f"{m.group(1)}.{m.group(2)[:2]}", output
            )
            redactions += len(gps_matches)

    # Layer 4: Credential redaction
    cred_matches = CREDENTIAL_PATTERN.findall(output)
    if cred_matches:
        output = CREDENTIAL_PATTERN.sub("[REDACTED_CREDENTIAL]", output)
        redactions += len(cred_matches)

    # Layer 5: Length limiting
    if len(output) > max_length:
        output = output[:max_length] + "\n[OUTPUT_TRUNCATED]"
        warnings.append("Output truncated to max length")

    return SanitizationResult(output, redactions, warnings)


# ── Rate Limiting ─────────────────────────────────────────────────────────

@dataclass
class RateLimit:
    requests_per_minute: int
    requests_per_hour: int
    max_concurrent: int


AGENT_RATE_LIMITS: dict[str, RateLimit] = {
    "sampling": RateLimit(10, 100, 2),
    "analysis": RateLimit(15, 150, 3),
    "geology": RateLimit(10, 100, 2),
    "market": RateLimit(30, 300, 5),
    "report": RateLimit(5, 50, 1),
    "compliance": RateLimit(10, 100, 2),
}


class RateLimiter:
    """Per-agent rate limiter applied at LangGraph node boundaries."""

    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._concurrent: dict[str, int] = defaultdict(int)

    def check(self, agent_role: str) -> bool:
        """Check if a request is allowed for this agent. Returns True if OK."""
        limits = AGENT_RATE_LIMITS.get(agent_role)
        if not limits:
            return True

        now = time.time()

        # Clean old entries
        self._requests[agent_role] = [
            t for t in self._requests[agent_role] if now - t < 3600
        ]

        # Check per-minute
        recent_minute = sum(
            1 for t in self._requests[agent_role] if now - t < 60
        )
        if recent_minute >= limits.requests_per_minute:
            logger.warning(f"Rate limit hit for {agent_role}: {recent_minute} req/min")
            return False

        # Check per-hour
        if len(self._requests[agent_role]) >= limits.requests_per_hour:
            logger.warning(f"Hourly rate limit hit for {agent_role}")
            return False

        # Check concurrent
        if self._concurrent[agent_role] >= limits.max_concurrent:
            logger.warning(f"Concurrent limit hit for {agent_role}")
            return False

        return True

    def record(self, agent_role: str) -> None:
        """Record a request for this agent."""
        self._requests[agent_role].append(time.time())

    def acquire(self, agent_role: str) -> bool:
        """Acquire a concurrent slot. Returns False if at limit."""
        limits = AGENT_RATE_LIMITS.get(agent_role)
        if not limits:
            return True
        if self._concurrent[agent_role] >= limits.max_concurrent:
            return False
        self._concurrent[agent_role] += 1
        return True

    def release(self, agent_role: str) -> None:
        """Release a concurrent slot."""
        self._concurrent[agent_role] = max(
            0, self._concurrent[agent_role] - 1
        )


# Singleton rate limiter
rate_limiter = RateLimiter()
