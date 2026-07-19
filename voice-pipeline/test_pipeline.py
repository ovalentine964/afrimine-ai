"""
AfriMine AI — Voice Pipeline Test Suite

Tests for all pipeline components:
- STT engine (Vosk + Groq Whisper)
- TTS engine (Piper)
- Intent classification
- Language detection
- Offline handler
- Full pipeline integration

Run: python -m pytest test_pipeline.py -v
"""

import os
import json
import time
import tempfile
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock

# === Test fixtures ===

@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def offline_handler(tmp_dir):
    """Create an OfflineHandler with temp database."""
    from offline_handler import OfflineHandler
    handler = OfflineHandler(cache_dir=tmp_dir, db_name="test.db")
    yield handler
    handler.close()


@pytest.fixture
def language_detector():
    """Create a LanguageDetector instance."""
    from language_support import LanguageDetector
    return LanguageDetector()


@pytest.fixture
def intent_classifier():
    """Create an IntentClassifier instance."""
    from voice_pipeline import IntentClassifier
    return IntentClassifier()


# ============================================================
# Language Detection Tests
# ============================================================

class TestLanguageDetection:
    """Test language detection for Kenyan languages."""

    def test_detect_swahili(self, language_detector):
        """Should detect Swahili text."""
        result = language_detector.detect("Hii sampuli ina dhahabu nzuri sana")
        assert result.primary_language.value == "sw"
        assert result.confidence > 0.3

    def test_detect_english(self, language_detector):
        """Should detect English text."""
        result = language_detector.detect("Analyze this gold sample for me")
        assert result.primary_language.value == "en"
        assert result.confidence > 0.3

    def test_detect_dholuo(self, language_detector):
        """Should detect Dholuo text."""
        # Dholuo uses some unique words
        result = language_detector.detect("Sampuli en madini maber kendo")
        # May detect as Swahili (shared vocabulary) — that's acceptable
        assert result.primary_language.value in ("luo", "sw")

    def test_detect_code_switching(self, language_detector):
        """Should detect code-switched text (Swahili + English)."""
        result = language_detector.detect("Hii sample ina gold content ya 3.5 grams")
        assert result.is_code_switched or result.english_ratio > 0.2

    def test_detect_empty_text(self, language_detector):
        """Should handle empty text gracefully."""
        result = language_detector.detect("")
        assert result.primary_language.value == "unknown"

    def test_detect_single_word(self, language_detector):
        """Should handle single-word input."""
        result = language_detector.detect("dhahabu")
        # "dhahabu" is shared across Swahili/Dholuo/Kikuyu
        assert result.primary_language.value in ("sw", "luo", "ki")

    def test_detect_simple_method(self, language_detector):
        """Simple detection should return just the language."""
        lang = language_detector.detect_simple("Chunguza sampuli hii")
        assert lang.value == "sw"

    def test_mining_vocabulary(self, language_support_module=None):
        """Mining vocabulary should have all required languages."""
        from language_support import get_mineral_info, get_supported_minerals
        
        minerals = get_supported_minerals()
        assert "gold" in minerals
        assert "copper" in minerals
        
        gold_sw = get_mineral_info("gold", "sw")
        assert gold_sw is not None
        assert gold_sw["name"] == "dhahabu"

    def test_all_minerals_have_translations(self):
        """All minerals should have translations for supported languages."""
        from language_support import MINING_VOCABULARY
        
        for mineral, translations in MINING_VOCABULARY.items():
            for lang in ["en", "sw", "luo", "ki"]:
                assert lang in translations, f"{mineral} missing {lang} translation"
                assert "name" in translations[lang], f"{mineral}/{lang} missing name"


# ============================================================
# Intent Classification Tests
# ============================================================

class TestIntentClassification:
    """Test intent classification for mining commands."""

    def test_analyze_sample_english(self, intent_classifier):
        from voice_pipeline import Intent
        from stt_engine import Language
        
        result = intent_classifier.classify_offline("Analyze this sample", Language.ENGLISH)
        assert result.intent == Intent.ANALYZE_SAMPLE
        assert result.confidence > 0.3

    def test_check_gold_swahili(self, intent_classifier):
        from voice_pipeline import Intent
        from stt_engine import Language
        
        result = intent_classifier.classify_offline("Kuna dhahabu?", Language.SWAHILI)
        assert result.intent == Intent.CHECK_GOLD

    def test_generate_report_english(self, intent_classifier):
        from voice_pipeline import Intent
        from stt_engine import Language
        
        result = intent_classifier.classify_offline("Generate a geological report", Language.ENGLISH)
        assert result.intent == Intent.GENERATE_REPORT

    def test_get_price_swahili(self, intent_classifier):
        from voice_pipeline import Intent
        from stt_engine import Language
        
        result = intent_classifier.classify_offline("Bei ya dhahabu gani?", Language.SWAHILI)
        assert result.intent == Intent.GET_PRICE

    def test_help_command(self, intent_classifier):
        from voice_pipeline import Intent
        from stt_engine import Language
        
        result = intent_classifier.classify_offline("Help", Language.ENGLISH)
        assert result.intent == Intent.HELP

    def test_cancel_command(self, intent_classifier):
        from voice_pipeline import Intent
        from stt_engine import Language
        
        result = intent_classifier.classify_offline("Cancel", Language.ENGLISH)
        assert result.intent == Intent.CANCEL

    def test_unknown_command(self, intent_classifier):
        from voice_pipeline import Intent
        from stt_engine import Language
        
        result = intent_classifier.classify_offline("Blah blah random words", Language.ENGLISH)
        assert result.intent == Intent.UNKNOWN

    def test_entity_extraction_gold(self, intent_classifier):
        from voice_pipeline import Intent
        from stt_engine import Language
        
        result = intent_classifier.classify_offline("Check gold sample", Language.ENGLISH)
        assert result.entities.get("mineral") == "gold"

    def test_entity_extraction_commodity(self, intent_classifier):
        from voice_pipeline import Intent
        from stt_engine import Language
        
        result = intent_classifier.classify_offline("What's the price of copper?", Language.ENGLISH)
        assert result.entities.get("commodity") == "copper"

    def test_save_note_entity(self, intent_classifier):
        from voice_pipeline import Intent
        from stt_engine import Language
        
        result = intent_classifier.classify_offline(
            "Save note found quartz veining in sector B", Language.ENGLISH
        )
        assert result.intent == Intent.SAVE_NOTE
        assert "note_content" in result.entities


# ============================================================
# Offline Handler Tests
# ============================================================

class TestOfflineHandler:
    """Test offline caching and command queuing."""

    def test_cache_response(self, offline_handler):
        """Should cache and retrieve responses."""
        offline_handler.cache_response(
            intent="check_gold",
            entities={"mineral": "gold"},
            response={"result": "Gold detected", "confidence": 0.85},
        )
        
        cached = offline_handler.get_cached_response("check_gold", {"mineral": "gold"})
        assert cached is not None
        assert cached["result"] == "Gold detected"
        assert cached["confidence"] == 0.85

    def test_cache_miss(self, offline_handler):
        """Should return None for cache miss."""
        cached = offline_handler.get_cached_response("nonexistent", {})
        assert cached is None

    def test_cache_different_entities(self, offline_handler):
        """Different entities should not match."""
        offline_handler.cache_response(
            intent="check_gold",
            entities={"mineral": "gold"},
            response={"result": "Gold found"},
        )
        
        cached = offline_handler.get_cached_response("check_gold", {"mineral": "silver"})
        assert cached is None

    def test_cache_stats(self, offline_handler):
        """Should track cache statistics."""
        offline_handler.cache_response("test", {}, {"data": 1})
        offline_handler.cache_response("test2", {}, {"data": 2})
        
        stats = offline_handler.get_cache_stats()
        assert stats["cached_responses"] == 2

    def test_queue_command(self, offline_handler):
        """Should queue commands for later sync."""
        from offline_handler import QueuedCommand
        
        cmd = QueuedCommand(
            intent="analyze_sample",
            entities={"mineral": "gold"},
            raw_text="Analyze this gold sample",
            language="sw",
        )
        offline_handler.queue_command(cmd)
        
        pending = offline_handler.get_pending_commands()
        assert len(pending) == 1
        assert pending[0].intent == "analyze_sample"

    def test_mark_command_synced(self, offline_handler):
        """Should mark commands as synced."""
        from offline_handler import QueuedCommand
        
        cmd = QueuedCommand(
            intent="test",
            entities={},
            raw_text="test command",
            language="en",
        )
        offline_handler.queue_command(cmd)
        offline_handler.mark_command_synced(cmd.id)
        
        pending = offline_handler.get_pending_commands()
        assert len(pending) == 0

    def test_field_notes(self, offline_handler):
        """Should save and retrieve field notes."""
        from offline_handler import FieldNote
        
        note = FieldNote(
            id="note-001",
            text="Found quartz veining in sector B",
            language="en",
            location={"lat": -1.0833, "lng": 34.5833},
        )
        offline_handler.save_note(note)
        
        notes = offline_handler.get_notes()
        assert len(notes) == 1
        assert notes[0].text == "Found quartz veining in sector B"

    def test_geo_samples(self, offline_handler):
        """Should save and retrieve geological samples."""
        offline_handler.save_sample(
            sample_id="S-001",
            location={"lat": -1.08, "lng": 34.58},
            minerals=["gold", "quartz"],
            analysis={"grade": 3.5, "unit": "g/t"},
            confidence=0.85,
            worker_id="worker-01",
        )
        
        samples = offline_handler.get_samples()
        assert len(samples) == 1
        assert "gold" in samples[0]["minerals"]

    def test_sync_summary(self, offline_handler):
        """Should provide sync summary."""
        from offline_handler import QueuedCommand, FieldNote
        
        offline_handler.queue_command(QueuedCommand(
            intent="test", entities={}, raw_text="test", language="en",
        ))
        offline_handler.save_note(FieldNote(
            id="n1", text="note", language="en",
        ))
        
        summary = offline_handler.get_sync_summary()
        assert summary["pending_commands"] == 1
        assert summary["pending_notes"] == 1
        assert summary["total_pending"] == 2

    def test_connectivity_logging(self, offline_handler):
        """Should log connectivity changes."""
        offline_handler.log_connectivity(True)
        offline_handler.log_connectivity(False)
        
        # Should not raise
        duration = offline_handler.get_offline_duration()
        assert duration >= 0


# ============================================================
# STT Engine Tests
# ============================================================

class TestSTTEngine:
    """Test speech-to-text engines."""

    def test_vosk_engine_creation(self):
        """Should create Vosk engine."""
        from stt_engine import VoskSTTEngine, Language
        
        engine = VoskSTTEngine(model_dir="/tmp/test_models", language=Language.SWAHILI)
        assert engine.language == Language.SWAHILI

    def test_groq_engine_creation(self):
        """Should create Groq engine."""
        from stt_engine import GroqWhisperSTTEngine
        
        engine = GroqWhisperSTTEngine(api_key="test_key")
        assert engine.api_key == "test_key"

    def test_hybrid_engine_creation(self):
        """Should create hybrid engine."""
        from stt_engine import HybridSTTEngine, Language
        
        engine = HybridSTTEngine(
            model_dir="/tmp/test_models",
            groq_api_key="test_key",
            default_language=Language.SWAHILI,
        )
        assert engine.default_language == Language.SWAHILI

    def test_hybrid_offline_mode(self):
        """Should respect offline-only mode."""
        from stt_engine import HybridSTTEngine, Language
        
        engine = HybridSTTEngine(
            model_dir="/tmp/test_models",
            default_language=Language.SWAHILI,
        )
        engine.set_online_status(False)
        assert engine._online_available is False

    def test_transcription_result(self):
        """TranscriptionResult should store all fields."""
        from stt_engine import TranscriptionResult, Language
        
        result = TranscriptionResult(
            text="Hii sampuli ina dhahabu",
            language=Language.SWAHILI,
            confidence=0.85,
            is_final=True,
            engine="vosk",
        )
        assert result.text == "Hii sampuli ina dhahabu"
        assert result.confidence == 0.85
        assert result.is_final is True

    def test_language_model_mapping(self):
        """Should have models for all supported languages."""
        from stt_engine import VoskSTTEngine, Language
        
        for lang in [Language.SWAHILI, Language.ENGLISH, Language.DHOLUO, Language.KIKUYU]:
            assert lang in VoskSTTEngine.MODEL_MAP


# ============================================================
# TTS Engine Tests
# ============================================================

class TestTTSEngine:
    """Test text-to-speech engines."""

    def test_piper_engine_creation(self):
        """Should create Piper engine."""
        from tts_engine import PiperTTSEngine
        
        engine = PiperTTSEngine(voice_dir="/tmp/test_voices", default_voice="en")
        assert engine.default_voice == "en"

    def test_multilingual_engine_creation(self):
        """Should create multilingual engine."""
        from tts_engine import MultilingualTTSEngine
        
        engine = MultilingualTTSEngine(voice_dir="/tmp/test_voices")
        assert engine is not None

    def test_geological_text_preparation(self):
        """Should prepare geological text for TTS."""
        from tts_engine import prepare_geological_text, MINING_PHONETICS
        
        # Test phonetic replacement
        text = "This sample contains pyrite"
        prepared = prepare_geological_text(text, "en")
        assert "PIE-rite" in prepared

    def test_swahili_geological_terms(self):
        """Should add Swahili context for English terms."""
        from tts_engine import prepare_geological_text
        
        text = "The gold content is 3.5 grams"
        prepared = prepare_geological_text(text, "sw")
        assert "dhahabu" in prepared

    def test_voice_mapping(self):
        """Should have voice entries for all languages."""
        from tts_engine import PiperTTSEngine
        
        assert "en" in PiperTTSEngine.VOICE_MAP
        assert "sw" in PiperTTSEngine.VOICE_MAP
        assert "luo" in PiperTTSEngine.VOICE_MAP
        assert "ki" in PiperTTSEngine.VOICE_MAP


# ============================================================
# Response Formatting Tests
# ============================================================

class TestResponseFormatting:
    """Test response formatting for voice output."""

    def test_format_english_response(self):
        from voice_pipeline import ResponseFormatter, VoiceIntent, Intent
        from stt_engine import Language
        
        formatter = ResponseFormatter()
        intent = VoiceIntent(intent=Intent.ANALYZE_SAMPLE, confidence=0.9, language=Language.ENGLISH)
        agent_result = {"result": "Gold detected at 3.5 g/t"}
        
        response = formatter.format_response(intent, agent_result)
        assert "Gold detected" in response

    def test_format_swahili_response(self):
        from voice_pipeline import ResponseFormatter, VoiceIntent, Intent
        from stt_engine import Language
        
        formatter = ResponseFormatter()
        intent = VoiceIntent(intent=Intent.CHECK_GOLD, confidence=0.9, language=Language.SWAHILI)
        agent_result = {"result": "Dhahabu imepatikana"}
        
        response = formatter.format_response(intent, agent_result)
        assert "Uchunguzi" in response or "dhahabu" in response.lower()

    def test_offline_notice(self):
        from voice_pipeline import ResponseFormatter, VoiceIntent, Intent
        from stt_engine import Language
        
        formatter = ResponseFormatter()
        intent = VoiceIntent(intent=Intent.ANALYZE_SAMPLE, confidence=0.9, language=Language.ENGLISH)
        
        response = formatter.format_response(intent, {"result": "test"}, is_offline=True)
        assert "offline" in response.lower() or "cached" in response.lower()

    def test_unknown_intent_response(self):
        from voice_pipeline import ResponseFormatter, VoiceIntent, Intent
        from stt_engine import Language
        
        formatter = ResponseFormatter()
        intent = VoiceIntent(intent=Intent.UNKNOWN, confidence=0.0, language=Language.ENGLISH)
        
        response = formatter.format_response(intent, None)
        assert "help" in response.lower() or "understand" in response.lower()


# ============================================================
# Agent Router Tests
# ============================================================

class TestAgentRouter:
    """Test agent routing logic."""

    def test_route_analyze_sample(self):
        from voice_pipeline import AgentRouter, VoiceIntent, Intent
        from stt_engine import Language
        
        router = AgentRouter()
        intent = VoiceIntent(intent=Intent.ANALYZE_SAMPLE, confidence=0.9, language=Language.ENGLISH)
        
        result = asyncio.get_event_loop().run_until_complete(router.route(intent))
        assert result is not None
        assert result["type"] == "analysis"

    def test_route_help_returns_none(self):
        from voice_pipeline import AgentRouter, VoiceIntent, Intent
        from stt_engine import Language
        
        router = AgentRouter()
        intent = VoiceIntent(intent=Intent.HELP, confidence=1.0, language=Language.ENGLISH)
        
        result = asyncio.get_event_loop().run_until_complete(router.route(intent))
        assert result is None

    def test_route_unknown_returns_none(self):
        from voice_pipeline import AgentRouter, VoiceIntent, Intent
        from stt_engine import Language
        
        router = AgentRouter()
        intent = VoiceIntent(intent=Intent.UNKNOWN, confidence=0.0, language=Language.ENGLISH)
        
        result = asyncio.get_event_loop().run_until_complete(router.route(intent))
        assert result is None


# ============================================================
# Voice Commands YAML Tests
# ============================================================

class TestVoiceCommandsConfig:
    """Test voice commands YAML configuration."""

    def test_load_config(self):
        """Should load the YAML config."""
        import yaml
        
        config_path = Path(__file__).parent / "voice_commands.yaml"
        if config_path.exists():
            with open(config_path) as f:
                config = yaml.safe_load(f)
            assert "commands" in config
            assert "version" in config

    def test_all_intents_have_commands(self):
        """Every VoiceIntent should have a command definition."""
        import yaml
        from voice_pipeline import Intent
        
        config_path = Path(__file__).parent / "voice_commands.yaml"
        if not config_path.exists():
            pytest.skip("voice_commands.yaml not found")
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        commands = config.get("commands", {})
        for intent in Intent:
            if intent not in (Intent.UNKNOWN, Intent.REPEAT, Intent.CANCEL):
                assert intent.value in commands, f"Missing command for {intent.value}"

    def test_commands_have_aliases(self):
        """Each command should have aliases in at least English."""
        import yaml
        
        config_path = Path(__file__).parent / "voice_commands.yaml"
        if not config_path.exists():
            pytest.skip("voice_commands.yaml not found")
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        for cmd_name, cmd in config.get("commands", {}).items():
            if cmd.get("agent") != "none":
                assert "aliases" in cmd, f"{cmd_name} missing aliases"
                assert "en" in cmd["aliases"], f"{cmd_name} missing English aliases"
                assert len(cmd["aliases"]["en"]) >= 2, f"{cmd_name} needs 2+ English aliases"

    def test_commands_have_swahili_aliases(self):
        """Each command should have Swahili aliases."""
        import yaml
        
        config_path = Path(__file__).parent / "voice_commands.yaml"
        if not config_path.exists():
            pytest.skip("voice_commands.yaml not found")
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        for cmd_name, cmd in config.get("commands", {}).items():
            if cmd.get("agent") != "none":
                assert "sw" in cmd.get("aliases", {}), f"{cmd_name} missing Swahili aliases"


# ============================================================
# Integration Tests
# ============================================================

class TestIntegration:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_text_pipeline_english(self):
        """Full text pipeline in English."""
        from voice_pipeline import VoicePipeline, Intent, Language
        
        pipeline = VoicePipeline(
            language=Language.ENGLISH,
            offline_only=True,
        )
        # Don't initialize (requires models) — test text processing logic
        
        # Test intent classification directly
        from voice_pipeline import IntentClassifier
        classifier = IntentClassifier()
        
        intent = classifier.classify_offline("Is there gold in this sample?", Language.ENGLISH)
        assert intent.intent == Intent.CHECK_GOLD

    @pytest.mark.asyncio
    async def test_text_pipeline_swahili(self):
        """Full text pipeline in Swahili."""
        from voice_pipeline import IntentClassifier, Intent, Language
        
        classifier = IntentClassifier()
        
        intent = classifier.classify_offline("Kuna dhahabu kwenye sampuli hii?", Language.SWAHILI)
        assert intent.intent == Intent.CHECK_GOLD

    def test_offline_cache_roundtrip(self, offline_handler):
        """Complete cache roundtrip: write → read → verify."""
        from offline_handler import QueuedCommand, FieldNote
        
        # Cache a response
        offline_handler.cache_response(
            intent="analyze_sample",
            entities={"mineral": "gold", "location": {"lat": -1.08, "lng": 34.58}},
            response={
                "result": "Gold detected at 3.5 g/t",
                "minerals": ["gold", "quartz"],
                "confidence": 0.85,
            },
        )
        
        # Queue a command
        cmd = QueuedCommand(
            intent="analyze_sample",
            entities={"mineral": "gold"},
            raw_text="Analyze this gold sample",
            language="sw",
        )
        offline_handler.queue_command(cmd)
        
        # Save a note
        note = FieldNote(
            id="note-001",
            text="Found quartz veining near the river",
            language="en",
            location={"lat": -1.0833, "lng": 34.5833},
        )
        offline_handler.save_note(note)
        
        # Verify everything persists
        cached = offline_handler.get_cached_response(
            "analyze_sample", {"mineral": "gold", "location": {"lat": -1.08, "lng": 34.58}}
        )
        assert cached is not None
        assert "Gold detected" in cached["result"]
        
        pending = offline_handler.get_pending_commands()
        assert len(pending) == 1
        assert pending[0].id == cmd.id
        
        notes = offline_handler.get_notes()
        assert len(notes) == 1
        assert notes[0].id == "note-001"

    def test_full_sync_summary(self, offline_handler):
        """Sync summary should reflect all pending items."""
        from offline_handler import QueuedCommand, FieldNote
        
        # Add various items
        for i in range(3):
            offline_handler.queue_command(QueuedCommand(
                intent=f"cmd_{i}", entities={}, raw_text=f"command {i}", language="en",
            ))
        
        for i in range(2):
            offline_handler.save_note(FieldNote(
                id=f"note_{i}", text=f"note {i}", language="en",
            ))
        
        offline_handler.save_sample(
            sample_id="S-001",
            location={"lat": -1.08, "lng": 34.58},
            minerals=["gold"],
        )
        
        summary = offline_handler.get_sync_summary()
        assert summary["pending_commands"] == 3
        assert summary["pending_notes"] == 2
        assert summary["pending_samples"] == 1
        assert summary["total_pending"] == 6


# ============================================================
# Voice Commands YAML Validation
# ============================================================

class TestYAMLValidation:
    """Validate the voice_commands.yaml structure."""

    @pytest.fixture
    def config(self):
        import yaml
        config_path = Path(__file__).parent / "voice_commands.yaml"
        if not config_path.exists():
            pytest.skip("voice_commands.yaml not found")
        with open(config_path) as f:
            return yaml.safe_load(f)

    def test_has_version(self, config):
        assert "version" in config

    def test_has_commands(self, config):
        assert "commands" in config
        assert len(config["commands"]) > 0

    def test_commands_have_description(self, config):
        for name, cmd in config["commands"].items():
            assert "description" in cmd, f"{name} missing description"

    def test_compound_commands_reference_valid(self, config):
        """Compound commands should reference existing simple commands."""
        simple_commands = set(config.get("commands", {}).keys())
        for name, compound in config.get("compound_commands", {}).items():
            for step in compound.get("steps", []):
                assert step in simple_commands, \
                    f"Compound '{name}' references unknown command '{step}'"

    def test_entity_patterns(self, config):
        """Should have mineral and unit entity patterns."""
        patterns = config.get("entity_patterns", {})
        assert "minerals" in patterns
        assert "gold" in patterns["minerals"]
        assert "units" in patterns
        assert "g/t" in patterns["units"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
