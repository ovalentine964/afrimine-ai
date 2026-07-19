"""
AfriMine AI — Speech-to-Text Engine

Two-tier STT strategy:
1. Vosk (offline, 50MB model, CPU-only) — primary for field use
2. Groq Whisper (online, free tier) — fallback for better accuracy

Supports: Swahili, Dholuo, Kikuyu, English
Designed for: 2GB RAM Android phones, noisy mining environments
"""

import os
import json
import queue
import logging
import tempfile
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


class Language(Enum):
    SWAHILI = "sw"
    DHOLUO = "luo"
    KIKUYU = "ki"
    ENGLISH = "en"


@dataclass
class TranscriptionResult:
    """Result from speech-to-text processing."""
    text: str
    language: Language
    confidence: float
    is_final: bool
    engine: str  # "vosk" or "groq_whisper"
    raw_tokens: list = field(default_factory=list)


class VoskSTTEngine:
    """
    Offline speech-to-text using Vosk.
    
    Models:
    - vosk-model-small-sw-0.3 (Swahili, 50MB)
    - vosk-model-small-en-0.15 (English, 40MB)
    - Custom Dholuo/Kikuyu models (fine-tuned on WAXAL/Paza data)
    
    Runs entirely on CPU. No internet required.
    """

    MODEL_MAP = {
        Language.SWAHILI: "vosk-model-small-sw-0.3",
        Language.ENGLISH: "vosk-model-small-en-0.15",
        Language.DHOLUO: "vosk-model-small-luo-0.1",   # Custom fine-tuned
        Language.KIKUYU: "vosk-model-small-ki-0.1",     # Custom fine-tuned
    }

    SAMPLE_RATE = 16000
    BUFFER_SIZE = 4000  # 250ms chunks at 16kHz

    def __init__(self, model_dir: str = "models/vosk", language: Language = Language.SWAHILI):
        self.model_dir = Path(model_dir)
        self.language = language
        self.model = None
        self.recognizer = None
        self._audio_queue: queue.Queue = queue.Queue()
        self._is_listening = False
        self._on_result_callback: Optional[Callable] = None

    def load_model(self, language: Optional[Language] = None) -> bool:
        """Load Vosk model for specified language."""
        lang = language or self.language
        model_name = self.MODEL_MAP.get(lang)
        if not model_name:
            logger.error(f"No Vosk model for language: {lang}")
            return False

        model_path = self.model_dir / model_name
        if not model_path.exists():
            logger.warning(f"Model not found at {model_path}. Using fallback English model.")
            model_path = self.model_dir / self.MODEL_MAP[Language.ENGLISH]
            if not model_path.exists():
                logger.error("No Vosk models found. Download models first.")
                return False

        try:
            from vosk import Model, KaldiRecognizer
            self.model = Model(str(model_path))
            self.recognizer = KaldiRecognizer(self.model, self.SAMPLE_RATE)
            self.recognizer.SetWords(True)
            logger.info(f"Loaded Vosk model: {model_name}")
            return True
        except ImportError:
            logger.error("vosk not installed. Run: pip install vosk")
            return False
        except Exception as e:
            logger.error(f"Failed to load Vosk model: {e}")
            return False

    def _audio_callback(self, indata, frames, time, status):
        """Callback for sounddevice audio stream."""
        if status:
            logger.warning(f"Audio status: {status}")
        self._audio_queue.put(bytes(indata))

    def listen_stream(self, on_result: Callable[[TranscriptionResult], None], 
                      timeout_seconds: float = 30.0) -> None:
        """
        Start streaming recognition. Calls on_result for each partial/final result.
        
        This is the primary interface for real-time voice interaction.
        """
        if not self.recognizer:
            if not self.load_model():
                raise RuntimeError("Vosk model not loaded")

        self._on_result_callback = on_result
        self._is_listening = True
        self.recognizer.Reset()

        try:
            with sd.RawInputStream(
                samplerate=self.SAMPLE_RATE,
                blocksize=self.BUFFER_SIZE,
                dtype="int16",
                channels=1,
                callback=self._audio_callback,
            ):
                logger.info("Listening... (speak now)")
                import time as time_module
                start = time_module.monotonic()

                while self._is_listening:
                    if time_module.monotonic() - start > timeout_seconds:
                        logger.info("Listening timeout reached")
                        break

                    data = self._audio_queue.get(timeout=1.0)
                    if self.recognizer.AcceptWaveform(data):
                        result = json.loads(self.recognizer.Result())
                        text = result.get("text", "").strip()
                        if text:
                            confidence = self._extract_confidence(result)
                            callback_result = TranscriptionResult(
                                text=text,
                                language=self.language,
                                confidence=confidence,
                                is_final=True,
                                engine="vosk",
                                raw_tokens=result.get("result", []),
                            )
                            on_result(callback_result)
                    else:
                        partial = json.loads(self.recognizer.PartialResult())
                        partial_text = partial.get("partial", "").strip()
                        if partial_text:
                            callback_result = TranscriptionResult(
                                text=partial_text,
                                language=self.language,
                                confidence=0.5,
                                is_final=False,
                                engine="vosk",
                            )
                            on_result(callback_result)

        except queue.Empty:
            logger.info("Audio queue empty, stopping")
        except Exception as e:
            logger.error(f"Streaming error: {e}")
        finally:
            self._is_listening = False

    def transcribe_file(self, audio_path: str, language: Optional[Language] = None) -> TranscriptionResult:
        """Transcribe an audio file (WAV, 16kHz, mono)."""
        if not self.recognizer:
            if not self.load_model(language):
                raise RuntimeError("Vosk model not loaded")

        import wave
        with wave.open(audio_path, "rb") as wf:
            if wf.getsampwidth() != 2 or wf.getnchannels() != 1:
                raise ValueError("Audio must be 16-bit mono WAV")
            
            self.recognizer.Reset()
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                self.recognizer.AcceptWaveform(data)

            final = json.loads(self.recognizer.FinalResult())
            return TranscriptionResult(
                text=final.get("text", ""),
                language=language or self.language,
                confidence=self._extract_confidence(final),
                is_final=True,
                engine="vosk",
                raw_tokens=final.get("result", []),
            )

    def stop(self):
        """Stop listening."""
        self._is_listening = False

    @staticmethod
    def _extract_confidence(result: dict) -> float:
        """Extract average confidence from Vosk result tokens."""
        tokens = result.get("result", [])
        if not tokens:
            return 0.0
        confidences = [t.get("conf", 0.0) for t in tokens]
        return sum(confidences) / len(confidences)


class GroqWhisperSTTEngine:
    """
    Online speech-to-text using Groq's Whisper Large V3.
    
    Free tier: 20 RPM, 2000 RPD
    Latency: ~1-2 seconds
    Accuracy: Excellent for accented English, good for Swahili
    
    Used as fallback when Vosk accuracy is insufficient.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.client = None

    def _ensure_client(self):
        if self.client is None:
            if not self.api_key:
                raise ValueError("GROQ_API_KEY not set. Get free key at console.groq.com")
            from groq import Groq
            self.client = Groq(api_key=self.api_key)

    def transcribe_file(self, audio_path: str, language: Optional[Language] = None) -> TranscriptionResult:
        """Transcribe audio file using Groq Whisper."""
        self._ensure_client()

        lang_map = {
            Language.SWAHILI: "sw",
            Language.DHOLUO: None,  # Not in Whisper's supported list
            Language.KIKUYU: None,
            Language.ENGLISH: "en",
        }

        with open(audio_path, "rb") as f:
            kwargs = {
                "model": "whisper-large-v3",
                "file": f,
                "response_format": "verbose_json",
            }
            lang_code = lang_map.get(language) if language else None
            if lang_code:
                kwargs["language"] = lang_code

            response = self.client.audio.transcriptions.create(**kwargs)

        return TranscriptionResult(
            text=response.text,
            language=language or Language.ENGLISH,
            confidence=getattr(response, "avg_logprob", 0.8) or 0.8,
            is_final=True,
            engine="groq_whisper",
        )

    def transcribe_bytes(self, audio_bytes: bytes, filename: str = "audio.wav",
                         language: Optional[Language] = None) -> TranscriptionResult:
        """Transcribe raw audio bytes using Groq Whisper."""
        self._ensure_client()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            return self.transcribe_file(tmp_path, language)
        finally:
            os.unlink(tmp_path)


class HybridSTTEngine:
    """
    Hybrid STT engine that tries offline first, falls back to online.
    
    Strategy:
    1. Always start with Vosk (offline, instant)
    2. If confidence < threshold AND online available → retry with Groq Whisper
    3. Return best result
    """

    CONFIDENCE_THRESHOLD = 0.6

    def __init__(self, model_dir: str = "models/vosk", groq_api_key: Optional[str] = None,
                 default_language: Language = Language.SWAHILI):
        self.vosk = VoskSTTEngine(model_dir=model_dir, language=default_language)
        self.groq = GroqWhisperSTTEngine(api_key=groq_api_key)
        self.default_language = default_language
        self._online_available = True

    def set_online_status(self, available: bool):
        """Update online availability (called by connectivity monitor)."""
        self._online_available = available
        logger.info(f"Online status: {'available' if available else 'offline'}")

    def transcribe_file(self, audio_path: str, language: Optional[Language] = None) -> TranscriptionResult:
        """
        Transcribe with automatic fallback.
        
        1. Try Vosk offline
        2. If low confidence + online → try Groq Whisper
        3. Return best result
        """
        lang = language or self.default_language

        # Always try offline first
        vosk_result = self.vosk.transcribe_file(audio_path, lang)

        if vosk_result.confidence >= self.CONFIDENCE_THRESHOLD:
            logger.info(f"Vosk result (high confidence): {vosk_result.text}")
            return vosk_result

        # Low confidence — try online if available
        if self._online_available:
            try:
                groq_result = self.groq.transcribe_file(audio_path, lang)
                logger.info(f"Groq Whisper result: {groq_result.text}")
                # Return Groq result if it has text, otherwise Vosk
                if groq_result.text.strip():
                    return groq_result
            except Exception as e:
                logger.warning(f"Groq Whisper failed: {e}")

        logger.info(f"Using Vosk result (low confidence): {vosk_result.text}")
        return vosk_result

    def load_model(self, language: Optional[Language] = None) -> bool:
        """Load offline model."""
        return self.vosk.load_model(language or self.default_language)

    def listen_stream(self, on_result: Callable[[TranscriptionResult], None],
                      timeout_seconds: float = 30.0) -> None:
        """Start streaming recognition (offline only)."""
        self.vosk.listen_stream(on_result, timeout_seconds)

    def stop(self):
        """Stop listening."""
        self.vosk.stop()


# === Convenience Functions ===

def create_stt_engine(
    default_language: Language = Language.SWAHILI,
    model_dir: str = "models/vosk",
    groq_api_key: Optional[str] = None,
    offline_only: bool = False,
) -> HybridSTTEngine:
    """
    Create the default STT engine for AfriMine.
    
    Args:
        default_language: Primary language for field workers
        model_dir: Path to Vosk models
        groq_api_key: Groq API key (reads from env if not provided)
        offline_only: If True, disable online fallback
    
    Returns:
        Configured HybridSTTEngine
    """
    engine = HybridSTTEngine(
        model_dir=model_dir,
        groq_api_key=groq_api_key,
        default_language=default_language,
    )
    if offline_only:
        engine.set_online_status(False)
    return engine


if __name__ == "__main__":
    # Quick test: listen for 10 seconds and print transcription
    logging.basicConfig(level=logging.INFO)
    
    engine = create_stt_engine(
        default_language=Language.SWAHILI,
        offline_only=True,
    )
    
    if engine.load_model():
        print("🎤 Listening for 10 seconds... Speak in Swahili or English!")
        
        def on_result(result: TranscriptionResult):
            marker = "✅" if result.is_final else "⏳"
            print(f"{marker} [{result.engine}] {result.text} (conf: {result.confidence:.2f})")
        
        engine.listen_stream(on_result, timeout_seconds=10.0)
        print("Done.")
    else:
        print("❌ Failed to load STT model. Download Vosk models first.")
        print("   wget https://alphacephei.com/vosk/models/vosk-model-small-sw-0.3.zip")
