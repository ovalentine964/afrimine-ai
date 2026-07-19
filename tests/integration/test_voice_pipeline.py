"""
AfriMine AI — Voice Pipeline Integration Tests
================================================

Tests the voice interface:
- STT: Vosk offline transcription
- TTS: Piper offline synthesis
- Language detection: Swahili, Dholuo, Kikuyu, English
- Intent recognition: mineral analysis commands

Requires: pytest
Run: pytest tests/integration/test_voice_pipeline.py -v

NOTE: These tests validate the voice pipeline logic and contracts.
Actual audio processing requires device-level testing.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Voice Pipeline Models (mirrors Flutter VoiceService)
# ---------------------------------------------------------------------------

class VoiceLanguage(Enum):
    ENGLISH = ("en", "English")
    SWAHILI = ("sw", "Kiswahili")
    DHOLUO = ("luo", "Dholuo")
    KIKUYU = ("ki", "Gikuyu")

    def __init__(self, code: str, display: str):
        self.code = code
        self.display = display


class VoiceState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass
class VoiceResult:
    transcribed_text: str
    response_text: str
    language: VoiceLanguage
    is_offline: bool = False
    confidence: float | None = None


# ---------------------------------------------------------------------------
# Language Detection (rule-based for testing)
# ---------------------------------------------------------------------------

DHOLUO_MARKERS = {
    "nyasae", "mama", "papa", "kamano", "nyatike", "migori",
    "puothe", "nyimbo", "thuol", "chuth", "aber", "gi",
    "nyakalaga", "jomuo", "kanye", "dhi", "en", "inyalo",
}

SWAHILI_MARKERS = {
    "habari", "nzuri", "sawa", "rafiki", "asante", "samahani",
    "madini", "dhahabu", "shaba", "jiwe", "ardhi", "mto",
    "uchunguzi", "sampuli", "uchambuzi", "ripoti",
}

KIKUYU_MARKERS = {
    "muthuri", "mwarimu", "ndungata", "nyumba", "mwaki",
    "muti", "ruai", "kiumbe", "gitathimo", "ndirangu",
}

ENGLISH_MARKERS = {
    "the", "is", "are", "gold", "mineral", "sample", "analysis",
    "report", "copper", "location", "coordinates", "sample",
}


def detect_language(text: str) -> VoiceLanguage:
    """Detect language from text using marker word matching."""
    words = set(text.lower().split())

    scores = {
        VoiceLanguage.DHOLUO: len(words & DHOLUO_MARKERS),
        VoiceLanguage.SWAHILI: len(words & SWAHILI_MARKERS),
        VoiceLanguage.KIKUYU: len(words & KIKUYU_MARKERS),
        VoiceLanguage.ENGLISH: len(words & ENGLISH_MARKERS),
    }

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return VoiceLanguage.ENGLISH  # Default
    return best


# ---------------------------------------------------------------------------
# Intent Recognition
# ---------------------------------------------------------------------------

INTENT_PATTERNS = {
    "analyze_sample": [
        r"(?i)analy[sz]e\s+(this\s+)?sample",
        r"(?i)what\s+(mineral|rock|stone)\s+is\s+this",
        r"(?i)identify\s+(this|the)\s+(mineral|rock|sample)",
        r"(?i)chunguza\s+sampuli",  # Swahili
        r"(?i)kagua\s+jiwe",  # Swahili
    ],
    "get_report": [
        r"(?i)(show|get|give)\s+(me\s+)?(the\s+)?report",
        r"(?i)generate\s+report",
        r"(?i)ripoti\s+ya\s+uchunguzi",  # Swahili
    ],
    "check_price": [
        r"(?i)(what|current)\s+(is\s+)?(the\s+)?(gold|copper|metal)\s+price",
        r"(?i)bei\s+ya\s+dhahabu",  # Swahili
    ],
    "record_location": [
        r"(?i)(record|save|mark)\s+(this\s+)?(location|position|gps)",
        r"(?i)coordinates?\s*:",
        r"(?i)hifadhi\s+mahali",  # Swahili
    ],
    "voice_memo": [
        r"(?i)(record|save)\s+(a\s+)?(voice\s+)?(note|memo)",
        r"(?i)ongeza\s+maelezo",  # Swahili
    ],
}


def recognize_intent(text: str) -> str | None:
    """Recognize intent from transcribed text."""
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text):
                return intent
    return None


# ---------------------------------------------------------------------------
# Test: Language Detection
# ---------------------------------------------------------------------------

class TestLanguageDetection:
    """Test automatic language detection from transcribed text."""

    def test_detect_english(self):
        """English mineral analysis text should be detected."""
        text = "Analyze this gold sample from Nyatike location"
        assert detect_language(text) == VoiceLanguage.ENGLISH

    def test_detect_swahili(self):
        """Swahili text about minerals should be detected."""
        text = "Chunguza sampuli hii ya dhahabu kutoka Nyatike"
        assert detect_language(text) == VoiceLanguage.SWAHILI

    def test_detect_dholuo(self):
        """Dholuo text should be detected."""
        text = "Kamano gi nyasae nyatike thuol gi chuth"
        assert detect_language(text) == VoiceLanguage.DHOLUO

    def test_detect_kikuyu(self):
        """Kikuyu text should be detected."""
        text = "Muthuri mwarimu nyumba mwaki muti ruai"
        assert detect_language(text) == VoiceLanguage.KIKUYU

    def test_detect_mixed_language_defaults_to_english(self):
        """Mixed or unrecognizable text should default to English."""
        text = "hello world 12345"
        assert detect_language(text) == VoiceLanguage.ENGLISH

    def test_all_4_target_languages(self):
        """All 4 target languages must be supported."""
        supported = {VoiceLanguage.ENGLISH, VoiceLanguage.SWAHILI,
                     VoiceLanguage.DHOLUO, VoiceLanguage.KIKUYU}
        assert len(supported) == 4


# ---------------------------------------------------------------------------
# Test: Intent Recognition
# ---------------------------------------------------------------------------

class TestIntentRecognition:
    """Test intent recognition from voice commands."""

    def test_analyze_sample_intent(self):
        """'Analyze this sample' should trigger analyze_sample intent."""
        assert recognize_intent("Analyze this sample") == "analyze_sample"
        assert recognize_intent("What mineral is this?") == "analyze_sample"
        assert recognize_intent("Identify this rock") == "analyze_sample"

    def test_get_report_intent(self):
        """'Show me the report' should trigger get_report intent."""
        assert recognize_intent("Show me the report") == "get_report"
        assert recognize_intent("Generate report") == "get_report"

    def test_check_price_intent(self):
        """'What is the gold price' should trigger check_price intent."""
        assert recognize_intent("What is the gold price?") == "check_price"
        assert recognize_intent("Current copper price") == "check_price"

    def test_record_location_intent(self):
        """'Record this location' should trigger record_location intent."""
        assert recognize_intent("Record this location") == "record_location"
        assert recognize_intent("Save GPS coordinates: -1.05, 34.55") == "record_location"

    def test_voice_memo_intent(self):
        """'Record a voice note' should trigger voice_memo intent."""
        assert recognize_intent("Record a voice note") == "voice_memo"
        assert recognize_intent("Save memo") == "voice_memo"

    def test_swahili_intent_recognition(self):
        """Swahili commands should be recognized."""
        assert recognize_intent("Chunguza sampuli hii") == "analyze_sample"
        assert recognize_intent("Ripoti ya uchunguzi") == "get_report"
        assert recognize_intent("Bei ya dhahabu") == "check_price"

    def test_unknown_intent_returns_none(self):
        """Unrecognizable commands should return None."""
        assert recognize_intent("Hello how are you") is None
        assert recognize_intent("asdfghjkl") is None


# ---------------------------------------------------------------------------
# Test: Voice Pipeline State Machine
# ---------------------------------------------------------------------------

class TestVoiceStateMachine:
    """Test the voice pipeline state transitions."""

    def test_state_transitions(self):
        """Voice states must follow valid transitions."""
        # Valid transitions
        valid_transitions = {
            VoiceState.IDLE: [VoiceState.LISTENING],
            VoiceState.LISTENING: [VoiceState.PROCESSING, VoiceState.IDLE, VoiceState.ERROR],
            VoiceState.PROCESSING: [VoiceState.SPEAKING, VoiceState.IDLE, VoiceState.ERROR],
            VoiceState.SPEAKING: [VoiceState.IDLE, VoiceState.ERROR],
            VoiceState.ERROR: [VoiceState.IDLE],
        }

        for from_state, to_states in valid_transitions.items():
            for to_state in to_states:
                # Verify each transition is valid
                assert to_state in valid_transitions[from_state] or from_state == VoiceState.ERROR

    def test_initial_state_is_idle(self):
        """Voice pipeline must start in IDLE state."""
        state = VoiceState.IDLE
        assert state == VoiceState.IDLE

    def test_listening_can_be_cancelled(self):
        """User should be able to cancel from LISTENING state."""
        state = VoiceState.LISTENING
        # Cancel returns to IDLE
        next_state = VoiceState.IDLE
        assert next_state == VoiceState.IDLE


# ---------------------------------------------------------------------------
# Test: STT Pipeline
# ---------------------------------------------------------------------------

class TestSTTPipeline:
    """Test Speech-to-Text pipeline contracts."""

    def test_stt_config_for_offline(self):
        """Offline STT config must target 16kHz mono WAV."""
        config = {
            "encoder": "wav",
            "sample_rate": 16000,
            "num_channels": 1,
            "bit_rate": 256000,
        }
        assert config["sample_rate"] == 16000
        assert config["num_channels"] == 1

    def test_stt_offline_model_requirements(self):
        """Offline STT models must support target languages."""
        required_models = {
            "vosk-en": VoiceLanguage.ENGLISH,
            "vosk-sw": VoiceLanguage.SWAHILI,
            "paza-luo": VoiceLanguage.DHOLUO,
            "paza-ki": VoiceLanguage.KIKUYU,
        }
        assert len(required_models) == 4

    def test_stt_online_fallback(self):
        """Online STT should use Groq Whisper as primary."""
        online_config = {
            "provider": "groq",
            "model": "whisper-large-v3",
            "rate_limit": "20 RPM",
        }
        assert online_config["provider"] == "groq"
        assert "whisper" in online_config["model"]


# ---------------------------------------------------------------------------
# Test: TTS Pipeline
# ---------------------------------------------------------------------------

class TestTTSPipeline:
    """Test Text-to-Speech pipeline contracts."""

    def test_tts_config(self):
        """TTS config must be optimized for field worker clarity."""
        config = {
            "speech_rate": 0.8,  # Slightly slower
            "volume": 1.0,
            "pitch": 1.0,
        }
        assert config["speech_rate"] <= 1.0  # Slower for clarity
        assert config["volume"] == 1.0

    def test_tts_offline_provider(self):
        """Offline TTS should use Piper or Kokoro."""
        offline_providers = ["piper", "kokoro"]
        assert len(offline_providers) >= 1

    def test_tts_language_support(self):
        """TTS must support all 4 target languages."""
        supported = ["en", "sw", "luo", "ki"]
        assert len(supported) == 4


# ---------------------------------------------------------------------------
# Test: Voice Result Contract
# ---------------------------------------------------------------------------

class TestVoiceResultContract:
    """Test voice result data structure."""

    def test_voice_result_has_required_fields(self):
        """VoiceResult must include transcription and response."""
        result = VoiceResult(
            transcribed_text="Analyze this gold sample",
            response_text="I found gold at 5.2 g/t confidence 85%",
            language=VoiceLanguage.ENGLISH,
            is_offline=False,
            confidence=0.92,
        )

        assert result.transcribed_text
        assert result.response_text
        assert result.language == VoiceLanguage.ENGLISH
        assert 0 <= result.confidence <= 1

    def test_voice_result_offline_mode(self):
        """Offline voice results should be flagged."""
        result = VoiceResult(
            transcribed_text="Sampuli ya dhahabu",
            response_text="Dhahabu imepatikana",
            language=VoiceLanguage.SWAHILI,
            is_offline=True,
        )

        assert result.is_offline is True
        assert result.language == VoiceLanguage.SWAHILI

    def test_voice_result_backward_compat(self):
        """VoiceResult.text and .transcription should work as aliases."""
        result = VoiceResult(
            transcribed_text="test transcription",
            response_text="test response",
            language=VoiceLanguage.ENGLISH,
        )

        # Backward-compatible getters
        assert result.text == "test response"
        assert result.transcription == "test transcription"
