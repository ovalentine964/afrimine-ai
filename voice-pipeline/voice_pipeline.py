"""
AfriMine AI — Voice Pipeline

Full voice interface: STT → Intent Recognition → Agent Routing → TTS

Orchestrates the complete voice interaction loop for field workers.
Integrates with LangGraph agent system for geological analysis workflows.

Architecture:
1. Listen (STT) → transcribe speech to text
2. Understand (Intent) → classify what the user wants
3. Route (Agent) → send to appropriate LangGraph agent
4. Speak (TTS) → read back the response

All offline-capable. Online features enhance but are not required.
"""

import os
import json
import logging
import asyncio
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List

import yaml

from stt_engine import (
    HybridSTTEngine, Language, TranscriptionResult,
    create_stt_engine,
)
from tts_engine import (
    MultilingualTTSEngine, TTSResult,
    create_tts_engine, prepare_geological_text,
)
from language_support import LanguageDetector, TranslationService
from offline_handler import OfflineHandler, QueuedCommand

logger = logging.getLogger(__name__)


# === Intent Classification ===

class Intent(Enum):
    """Voice command intents for mining workflows."""
    ANALYZE_SAMPLE = "analyze_sample"          # "Analyze this sample"
    CHECK_GOLD = "check_gold"                  # "Is there gold?"
    CHECK_MINERAL = "check_mineral"            # "What mineral is this?"
    GENERATE_REPORT = "generate_report"        # "Generate report"
    GET_PRICE = "get_price"                    # "What's gold worth?"
    SHOW_MAP = "show_map"                      # "Show the map"
    CHECK_COMPLIANCE = "check_compliance"      # "Check compliance"
    SAVE_NOTE = "save_note"                    # "Save this note"
    SYNC_DATA = "sync_data"                    # "Sync data"
    HELP = "help"                              # "Help" / "What can you do?"
    STATUS = "status"                          # "What's the status?"
    REPEAT = "repeat"                          # "Say that again"
    CANCEL = "cancel"                          # "Cancel" / "Never mind"
    UNKNOWN = "unknown"


@dataclass
class VoiceIntent:
    """Classified intent from voice input."""
    intent: Intent
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    language: Language = Language.ENGLISH


@dataclass
class PipelineResponse:
    """Response from the voice pipeline."""
    text: str                      # Text response
    audio: Optional[TTSResult]     # Audio response
    intent: VoiceIntent            # Classified intent
    agent_result: Optional[Dict] = None  # Result from LangGraph agent
    is_offline: bool = False       # Whether response was generated offline


class IntentClassifier:
    """
    Rule-based + LLM intent classifier.
    
    For offline mode: uses keyword matching (fast, no model needed)
    For online mode: uses Gemini/Groq for better accuracy
    
    Mining-specific intents with Swahili/Dholuo/Kikuyu support.
    """

    # Keyword patterns for each intent (multilingual)
    PATTERNS = {
        Intent.ANALYZE_SAMPLE: {
            "en": ["analyze", "analyse", "check sample", "test sample", "examine", "what is this"],
            "sw": ["chunguza", "angalia sampuli", "jaribu", "tathmini", "hii ni nini"],
            "luo": ["neyo", "nen sampul", "chunguza"],
            "ki": ["koruo", "andika sampuli", "githii"],
        },
        Intent.CHECK_GOLD: {
            "en": ["gold", "dhahabu", "is there gold", "gold here", "find gold"],
            "sw": ["dhahabu", "kuna dhahabu", "ni dhahabu", "pata dhahabu"],
            "luo": ["dhahabu", "en dhahabu"],
            "ki": ["dhahabu", "kuna dhahabu"],
        },
        Intent.CHECK_MINERAL: {
            "en": ["mineral", "what mineral", "which mineral", "identify", "type of rock"],
            "sw": ["madini", "madini gani", "aina ya madini", "jiwe gani"],
            "luo": ["madini", "madini ang'o"],
            "ki": ["madini", "madini iria"],
        },
        Intent.GENERATE_REPORT: {
            "en": ["report", "generate report", "create report", "make report", "pdf"],
            "sw": ["ripoti", "unda ripoti", "tengeneza ripoti", "andika ripoti"],
            "luo": ["ripoti", "weyo ripoti"],
            "ki": ["ripoti", "umbira ripoti"],
        },
        Intent.GET_PRICE: {
            "en": ["price", "worth", "value", "how much", "market", "cost"],
            "sw": ["bei", "thamani", "gharama", "soko", "thamani gani"],
            "luo": ["bei", "thamani"],
            "ki": ["bei", "giciirio", "thamani"],
        },
        Intent.SHOW_MAP: {
            "en": ["map", "show map", "satellite", "location", "where"],
            "sw": ["ramani", "onyesha ramani", "satellite", "mahali", "wapi"],
            "luo": ["map", "nyis map"],
            "ki": ["map", "onania map"],
        },
        Intent.CHECK_COMPLIANCE: {
            "en": ["compliance", "legal", "license", "permit", "regulation"],
            "sw": ["kufuata sheria", "leseni", "kibali", "kanuni"],
            "luo": ["compliance", "leseni"],
            "ki": ["compliance", "leseni"],
        },
        Intent.SAVE_NOTE: {
            "en": ["save", "note", "remember", "record", "write down"],
            "sw": ["hifadhi", "kumbuka", "andika", "rekodi"],
            "luo": ["save", "kata"],
            "ki": ["save", "andika"],
        },
        Intent.SYNC_DATA: {
            "en": ["sync", "upload", "send data", "update"],
            "sw": ["sawazisha", "tuma", "sasisha", "upload"],
            "luo": ["sync", "os"],
            "ki": ["sync", "tumira"],
        },
        Intent.HELP: {
            "en": ["help", "what can you do", "commands", "options"],
            "sw": ["msaada", "unaweza nini", "amri", "chaguzi"],
            "luo": ["kony", "inyalo ang'o"],
            "ki": ["help", "unguinia atia"],
        },
        Intent.STATUS: {
            "en": ["status", "connection", "online", "offline", "battery"],
            "sw": ["hali", "muunganisho", "mtandaoni", "nje ya mtandao"],
            "luo": ["status", "yudo"],
            "ki": ["status", "hali"],
        },
        Intent.REPEAT: {
            "en": ["repeat", "say again", "what did you say", "again"],
            "sw": ["rudia", "sema tena", "tena"],
            "luo": ["doki", "miwuok doki"],
            "ki": ["rora", "ugoka ugoka"],
        },
        Intent.CANCEL: {
            "en": ["cancel", "never mind", "stop", "forget it"],
            "sw": ["sitisha", "sahau", "acha", "hapana"],
            "luo": ["cancel", "wuogi"],
            "ki": ["cancel", "rega"],
        },
    }

    def __init__(self):
        self._llm_client = None

    def classify_offline(self, text: str, language: Language) -> VoiceIntent:
        """Classify intent using keyword matching (offline, fast)."""
        text_lower = text.lower().strip()
        lang_key = language.value

        best_intent = Intent.UNKNOWN
        best_score = 0.0

        for intent, patterns in self.PATTERNS.items():
            lang_patterns = patterns.get(lang_key, patterns.get("en", []))
            for pattern in lang_patterns:
                if pattern in text_lower:
                    # Score based on pattern length (longer = more specific)
                    score = len(pattern.split()) / max(len(text_lower.split()), 1)
                    if score > best_score:
                        best_score = score
                        best_intent = intent

        # Extract simple entities
        entities = self._extract_entities(text_lower, best_intent)

        return VoiceIntent(
            intent=best_intent,
            confidence=min(best_score + 0.3, 1.0),  # Boost for exact matches
            entities=entities,
            raw_text=text,
            language=language,
        )

    async def classify_online(self, text: str, language: Language) -> VoiceIntent:
        """Classify intent using LLM (online, more accurate)."""
        # TODO: Implement LLM-based classification using Gemini/Groq
        # For now, fall back to offline
        return self.classify_offline(text, language)

    def _extract_entities(self, text: str, intent: Intent) -> Dict[str, Any]:
        """Extract simple entities from text."""
        entities = {}

        if intent in (Intent.CHECK_MINERAL, Intent.CHECK_GOLD):
            # Try to find mineral names
            minerals = ["gold", "silver", "copper", "iron", "diamond", "coltan",
                       "dhahabu", "fedha", "shaba", "chuma", "almasi"]
            for mineral in minerals:
                if mineral in text:
                    entities["mineral"] = mineral
                    break

        if intent == Intent.GET_PRICE:
            # Try to find commodity
            commodities = ["gold", "silver", "copper", "coltan",
                          "dhahabu", "fedha", "shaba"]
            for commodity in commodities:
                if commodity in text:
                    entities["commodity"] = commodity
                    break

        if intent == Intent.SAVE_NOTE:
            # The rest of the text after "save/note" is the note content
            for trigger in ["save", "note", "hifadhi", "kumbuka"]:
                idx = text.find(trigger)
                if idx >= 0:
                    note_text = text[idx + len(trigger):].strip()
                    if note_text:
                        entities["note_content"] = note_text
                    break

        return entities


# === Agent Router ===

class AgentRouter:
    """
    Routes classified intents to LangGraph agent nodes.
    
    Maps voice intents to the 6-agent system:
    - Sampling Agent → analyze_sample
    - Analysis Agent → check_gold, check_mineral
    - Geology Agent → geological context
    - Market Agent → get_price
    - Report Agent → generate_report
    - Compliance Agent → check_compliance
    """

    # Intent → Agent mapping
    ROUTE_MAP = {
        Intent.ANALYZE_SAMPLE: "mineral_analysis_agent",
        Intent.CHECK_GOLD: "mineral_analysis_agent",
        Intent.CHECK_MINERAL: "mineral_analysis_agent",
        Intent.GENERATE_REPORT: "report_agent",
        Intent.GET_PRICE: "market_price_agent",
        Intent.SHOW_MAP: "geology_agent",
        Intent.CHECK_COMPLIANCE: "compliance_agent",
        Intent.SAVE_NOTE: "report_agent",
        Intent.SYNC_DATA: "report_agent",
    }

    def __init__(self, offline_handler: Optional[OfflineHandler] = None):
        self.offline_handler = offline_handler
        self._agent_clients = {}

    async def route(self, intent: VoiceIntent, context: Optional[Dict] = None) -> Optional[Dict]:
        """
        Route intent to appropriate agent.
        
        Returns agent result dict, or None if offline and not cached.
        """
        if intent.intent in (Intent.HELP, Intent.STATUS, Intent.REPEAT, 
                             Intent.CANCEL, Intent.UNKNOWN):
            return None  # Handled locally, no agent needed

        agent_name = self.ROUTE_MAP.get(intent.intent)
        if not agent_name:
            return None

        # Check offline cache first
        if self.offline_handler:
            cached = self.offline_handler.get_cached_response(intent.intent.value, 
                                                               intent.entities)
            if cached:
                logger.info(f"Offline cache hit for {intent.intent.value}")
                return cached

        # Try online agent call
        try:
            result = await self._call_agent(agent_name, intent, context)
            
            # Cache result for offline use
            if self.offline_handler and result:
                self.offline_handler.cache_response(intent.intent.value,
                                                     intent.entities, result)
            return result
        except Exception as e:
            logger.error(f"Agent call failed: {e}")
            
            # Queue for later sync if offline
            if self.offline_handler:
                self.offline_handler.queue_command(QueuedCommand(
                    intent=intent.intent.value,
                    entities=intent.entities,
                    raw_text=intent.raw_text,
                    language=intent.language.value,
                ))
            
            return None

    async def _call_agent(self, agent_name: str, intent: VoiceIntent,
                          context: Optional[Dict]) -> Optional[Dict]:
        """
        Call a LangGraph agent node.
        
        In production, this connects to the LangGraph agent graph.
        For MVP, returns mock responses.
        """
        # TODO: Replace with actual LangGraph agent calls
        # This is where the CrewAI/LangGraph integration happens
        
        mock_responses = {
            "mineral_analysis_agent": {
                "type": "analysis",
                "result": "Sample contains quartz veining with possible gold association. "
                         "Recommended: XRF analysis for confirmation.",
                "confidence": 0.75,
                "minerals_detected": ["quartz", "possible gold"],
                "recommendation": "Perform XRF test on sample",
            },
            "report_agent": {
                "type": "report",
                "result": "Geological report generated for current survey area.",
                "report_id": "RPT-2026-0719-001",
                "status": "completed",
            },
            "market_price_agent": {
                "type": "price",
                "result": "Current gold price: $2,450/oz (July 2026). Local estimate: 28M KES/acre.",
                "commodity": intent.entities.get("commodity", "gold"),
                "price_usd": 2450.0,
                "price_kes": 28000000,
            },
            "geology_agent": {
                "type": "map",
                "result": "Satellite analysis shows alluvial deposits in northern sector.",
                "coordinates": {"lat": -1.0833, "lng": 34.5833},
                "deposit_type": "alluvial",
            },
            "compliance_agent": {
                "type": "compliance",
                "result": "Mining license valid. Next renewal: December 2026.",
                "license_status": "valid",
                "renewal_date": "2026-12-15",
            },
        }
        
        return mock_responses.get(agent_name)


# === Response Formatter ===

class ResponseFormatter:
    """
    Formats agent results into natural language responses.
    
    Handles:
    - Language-appropriate responses
    - Code-switching (English technical + Swahili explanation)
    - Concise field-worker-friendly output
    """

    RESPONSE_TEMPLATES = {
        Intent.ANALYZE_SAMPLE: {
            "en": "Analysis complete. {result}",
            "sw": "Uchunguzi umekamilika. {result}",
        },
        Intent.CHECK_GOLD: {
            "en": "Gold analysis: {result}",
            "sw": "Uchunguzi wa dhahabu: {result}",
        },
        Intent.CHECK_MINERAL: {
            "en": "Mineral identification: {result}",
            "sw": "Utambuzi wa madini: {result}",
        },
        Intent.GENERATE_REPORT: {
            "en": "Report generated. {result}",
            "sw": "Ripoti imeundwa. {result}",
        },
        Intent.GET_PRICE: {
            "en": "Market price: {result}",
            "sw": "Bei ya soko: {result}",
        },
        Intent.SHOW_MAP: {
            "en": "Map analysis: {result}",
            "sw": "Uchambuzi wa ramani: {result}",
        },
        Intent.CHECK_COMPLIANCE: {
            "en": "Compliance status: {result}",
            "sw": "Hali ya kufuata sheria: {result}",
        },
        Intent.SAVE_NOTE: {
            "en": "Note saved successfully.",
            "sw": "Imehifadhiwa.",
        },
        Intent.SYNC_DATA: {
            "en": "Data sync complete.",
            "sw": "Usawazishaji umekamilika.",
        },
        Intent.HELP: {
            "en": "You can say: analyze sample, check gold, generate report, "
                  "get price, show map, or save note.",
            "sw": "Unaweza kusema: chunguza sampuli, angalia dhahabu, unda ripoti, "
                  "bei ya soko, onyesha ramani, au hifadhi kumbuka.",
        },
        Intent.STATUS: {
            "en": "System status: {status}",
            "sw": "Hali ya mfumo: {status}",
        },
        Intent.REPEAT: {
            "en": "{last_response}",
            "sw": "{last_response}",
        },
        Intent.CANCEL: {
            "en": "Cancelled.",
            "sw": "Imesitishwa.",
        },
        Intent.UNKNOWN: {
            "en": "I didn't understand. Say 'help' for available commands.",
            "sw": "Sijaelewa. Sema 'msaada' kwa amri zinazopatikana.",
        },
    }

    def format_response(self, intent: VoiceIntent, agent_result: Optional[Dict],
                        last_response: str = "", is_offline: bool = False) -> str:
        """Format a natural language response."""
        templates = self.RESPONSE_TEMPLATES.get(intent.intent, {})
        lang_key = intent.language.value
        template = templates.get(lang_key, templates.get("en", ""))

        # Build context for template
        context = {
            "result": agent_result.get("result", "") if agent_result else "",
            "status": "offline" if is_offline else "online",
            "last_response": last_response,
        }

        response = template.format(**context)

        # Add offline notice if applicable
        if is_offline and intent.intent in (Intent.ANALYZE_SAMPLE, Intent.CHECK_GOLD,
                                            Intent.CHECK_MINERAL, Intent.GENERATE_REPORT):
            offline_notice = {
                "en": " (Working offline — results are cached for sync.)",
                "sw": " (Inafanya nje ya mtandao — matokeo yamehifadhiwa.)",
            }
            response += offline_notice.get(lang_key, offline_notice["en"])

        return response


# === Main Pipeline ===

class VoicePipeline:
    """
    Complete voice interaction pipeline for AfriMine AI.
    
    Orchestrates: STT → Intent → Agent → Response → TTS
    
    Usage:
        pipeline = VoicePipeline()
        pipeline.initialize()
        response = await pipeline.process_voice()
    """

    def __init__(
        self,
        language: Language = Language.SWAHILI,
        model_dir: str = "models",
        voice_dir: str = "models/piper",
        groq_api_key: Optional[str] = None,
        offline_only: bool = False,
        config_path: str = "voice_commands.yaml",
    ):
        self.language = language
        self.model_dir = model_dir
        self.voice_dir = voice_dir
        self.offline_only = offline_only
        self.config_path = config_path

        # Components (initialized in initialize())
        self.stt: Optional[HybridSTTEngine] = None
        self.tts: Optional[MultilingualTTSEngine] = None
        self.intent_classifier: Optional[IntentClassifier] = None
        self.agent_router: Optional[AgentRouter] = None
        self.response_formatter: Optional[ResponseFormatter] = None
        self.language_detector: Optional[LanguageDetector] = None
        self.offline_handler: Optional[OfflineHandler] = None

        # State
        self._last_response = ""
        self._conversation_active = False
        self._config = {}

    def initialize(self) -> bool:
        """Initialize all pipeline components."""
        logger.info("Initializing AfriMine Voice Pipeline...")

        # Load config
        self._load_config()

        # Language detection
        self.language_detector = LanguageDetector()

        # Offline handler
        self.offline_handler = OfflineHandler(cache_dir=".afrimine/cache")

        # STT engine
        self.stt = create_stt_engine(
            default_language=self.language,
            model_dir=f"{self.model_dir}/vosk",
            groq_api_key=os.environ.get("GROQ_API_KEY"),
            offline_only=self.offline_only,
        )
        if not self.stt.load_model():
            logger.warning("STT model not loaded — voice input will not work")

        # TTS engine
        self.tts = create_tts_engine(
            default_language=self.language.value,
            voice_dir=self.voice_dir,
        )

        # Intent classifier
        self.intent_classifier = IntentClassifier()

        # Agent router
        self.agent_router = AgentRouter(offline_handler=self.offline_handler)

        # Response formatter
        self.response_formatter = ResponseFormatter()

        logger.info("Voice Pipeline initialized successfully")
        return True

    def _load_config(self):
        """Load voice commands configuration."""
        config_path = Path(self.config_path)
        if config_path.exists():
            with open(config_path) as f:
                self._config = yaml.safe_load(f)
            logger.info(f"Loaded config from {config_path}")

    async def process_voice(self) -> PipelineResponse:
        """
        Process a single voice interaction:
        1. Listen for speech
        2. Transcribe (STT)
        3. Classify intent
        4. Route to agent
        5. Format response
        6. Speak response (TTS)
        
        Returns PipelineResponse with all results.
        """
        # Step 1-2: Listen and transcribe
        logger.info("🎤 Listening for voice input...")
        transcription = await self._listen_and_transcribe()
        
        if not transcription or not transcription.text.strip():
            return PipelineResponse(
                text="I didn't hear anything. Please try again.",
                audio=None,
                intent=VoiceIntent(intent=Intent.UNKNOWN, confidence=0.0),
                is_offline=self.offline_only,
            )

        logger.info(f"📝 Transcribed: {transcription.text}")

        # Step 2.5: Detect language if auto
        detected_lang = self.language_detector.detect(transcription.text)
        if detected_lang:
            transcription.language = detected_lang

        # Step 3: Classify intent
        intent = self.intent_classifier.classify_offline(
            transcription.text, transcription.language
        )
        logger.info(f"🧠 Intent: {intent.intent.value} (confidence: {intent.confidence:.2f})")

        # Step 4: Route to agent
        agent_result = await self.agent_router.route(intent)

        # Step 5: Format response
        response_text = self.response_formatter.format_response(
            intent, agent_result,
            last_response=self._last_response,
            is_offline=self.offline_only,
        )
        self._last_response = response_text

        # Step 6: Speak response
        prepared_text = prepare_geological_text(response_text, intent.language.value)
        audio = None
        try:
            audio = self.tts.synthesize(prepared_text, intent.language.value)
        except Exception as e:
            logger.error(f"TTS failed: {e}")

        return PipelineResponse(
            text=response_text,
            audio=audio,
            intent=intent,
            agent_result=agent_result,
            is_offline=self.offline_only,
        )

    async def _listen_and_transcribe(self) -> Optional[TranscriptionResult]:
        """Listen for speech and transcribe."""
        loop = asyncio.get_event_loop()
        result_holder = {}

        def on_result(result: TranscriptionResult):
            if result.is_final:
                result_holder["result"] = result
                self.stt.stop()

        # Run STT in thread to avoid blocking
        try:
            await loop.run_in_executor(
                None,
                lambda: self.stt.listen_stream(on_result, timeout_seconds=15.0)
            )
        except Exception as e:
            logger.error(f"STT error: {e}")
            return None

        return result_holder.get("result")

    async def process_text(self, text: str, language: Optional[Language] = None) -> PipelineResponse:
        """
        Process text input directly (bypass STT).
        
        Useful for testing, or when text input is available (keyboard, API).
        """
        lang = language or self.language

        # Classify intent
        intent = self.intent_classifier.classify_offline(text, lang)

        # Route to agent
        agent_result = await self.agent_router.route(intent)

        # Format response
        response_text = self.response_formatter.format_response(
            intent, agent_result,
            last_response=self._last_response,
            is_offline=self.offline_only,
        )
        self._last_response = response_text

        # TTS
        prepared_text = prepare_geological_text(response_text, lang.value)
        audio = None
        try:
            audio = self.tts.synthesize(prepared_text, lang.value)
        except Exception as e:
            logger.error(f"TTS failed: {e}")

        return PipelineResponse(
            text=response_text,
            audio=audio,
            intent=intent,
            agent_result=agent_result,
            is_offline=self.offline_only,
        )

    def set_language(self, language: Language):
        """Change the active language."""
        self.language = language
        if self.stt:
            self.stt.vosk.language = language
        logger.info(f"Language set to {language.value}")

    def set_online_status(self, available: bool):
        """Update online/offline status."""
        if self.stt:
            self.stt.set_online_status(available)
        self.offline_only = not available
        logger.info(f"Online status: {'available' if available else 'offline'}")


# === CLI Entry Point ===

async def main():
    """CLI entry point for the voice pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="AfriMine AI Voice Pipeline")
    parser.add_argument("--language", "-l", default="sw",
                       choices=["sw", "luo", "ki", "en"],
                       help="Primary language (default: sw/Swahili)")
    parser.add_argument("--mode", "-m", default="offline",
                       choices=["offline", "online"],
                       help="Operation mode")
    parser.add_argument("--text", "-t", type=str,
                       help="Process text input instead of voice")
    parser.add_argument("--model-dir", default="models",
                       help="Directory containing STT/TTS models")
    parser.add_argument("--config", default="voice_commands.yaml",
                       help="Voice commands config file")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    lang_map = {"sw": Language.SWAHILI, "luo": Language.DHOLUO,
                "ki": Language.KIKUYU, "en": Language.ENGLISH}

    pipeline = VoicePipeline(
        language=lang_map[args.language],
        model_dir=args.model_dir,
        offline_only=(args.mode == "offline"),
        config_path=args.config,
    )

    if not pipeline.initialize():
        print("❌ Failed to initialize pipeline")
        return

    print(f"🎤 AfriMine Voice Pipeline — Language: {args.language}, Mode: {args.mode}")
    print("   Say 'help' for available commands, 'exit' to quit\n")

    if args.text:
        # Text mode
        result = await pipeline.process_text(args.text)
        print(f"📝 Input: {args.text}")
        print(f"🧠 Intent: {result.intent.intent.value}")
        print(f"💬 Response: {result.text}")
        if result.agent_result:
            print(f"📊 Agent: {json.dumps(result.agent_result, indent=2)}")
    else:
        # Voice mode
        while True:
            try:
                result = await pipeline.process_voice()
                print(f"🧠 Intent: {result.intent.intent.value}")
                print(f"💬 Response: {result.text}")
                
                if result.intent.intent == Intent.CANCEL:
                    print("Goodbye!")
                    break
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break


if __name__ == "__main__":
    asyncio.run(main())
