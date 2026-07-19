"""
AfriMine AI — Text-to-Speech Engine

Uses Piper TTS for offline, CPU-only speech synthesis.
Designed for field workers on cheap Android phones (2GB RAM).

Supported voices:
- en_US-lessac-medium (English)
- sw_CD-medium (Swahili — when available from WAXAL/Piper community)
- Custom Dholuo/Kikuyu voices (fine-tuned from WAXAL TTS data)

Latency: ~200-500ms on ARM Cortex-A53 (budget phone)
"""

import os
import io
import logging
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Union

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TTSResult:
    """Result from text-to-speech synthesis."""
    audio_bytes: bytes
    sample_rate: int
    duration_seconds: float
    voice: str
    engine: str


class PiperTTSEngine:
    """
    Offline text-to-speech using Piper TTS.
    
    Piper is a fast, local neural TTS engine that runs on CPU.
    Voice models are ~50MB each and produce natural-sounding speech.
    
    Architecture: text → phonemes → mel spectrogram → waveform (ONNX Runtime)
    """

    # Default voice paths (relative to Piper voice directory)
    VOICE_MAP = {
        "en": "en_US-lessac-medium",
        "sw": "sw_CD-medium",       # Swahili (community model)
        "luo": "luo_KE-medium",     # Dholuo (custom fine-tuned)
        "ki": "ki_KE-medium",       # Kikuyu (custom fine-tuned)
    }

    def __init__(self, voice_dir: str = "models/piper", default_voice: str = "en"):
        self.voice_dir = Path(voice_dir)
        self.default_voice = default_voice
        self._loaded_voice = None
        self._piper_model = None

    def _get_voice_path(self, voice_key: str) -> Optional[Path]:
        """Get path to voice model files."""
        voice_name = self.VOICE_MAP.get(voice_key, voice_key)
        onnx_path = self.voice_dir / f"{voice_name}.onnx"
        json_path = self.voice_dir / f"{voice_name}.onnx.json"
        
        if onnx_path.exists() and json_path.exists():
            return onnx_path
        
        # Try without subdirectory
        alt_path = Path(voice_name)
        if alt_path.exists():
            return alt_path
            
        return None

    def load_voice(self, voice_key: Optional[str] = None) -> bool:
        """Load a Piper TTS voice model."""
        key = voice_key or self.default_voice
        
        if self._loaded_voice == key and self._piper_model is not None:
            return True

        voice_path = self._get_voice_path(key)
        if not voice_path:
            logger.warning(f"Voice '{key}' not found at {self.voice_dir}. "
                          f"Download with: python -m piper.download_voices {self.VOICE_MAP.get(key, key)}")
            # Fall back to English
            if key != "en":
                logger.info("Falling back to English voice")
                return self.load_voice("en")
            return False

        try:
            from piper import PiperVoice
            self._piper_model = PiperVoice.load(str(voice_path))
            self._loaded_voice = key
            logger.info(f"Loaded Piper voice: {key}")
            return True
        except ImportError:
            logger.error("piper-tts not installed. Run: pip install piper-tts")
            return False
        except Exception as e:
            logger.error(f"Failed to load Piper voice: {e}")
            return False

    def synthesize(self, text: str, voice_key: Optional[str] = None) -> TTSResult:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to speak
            voice_key: Voice to use (defaults to self.default_voice)
            
        Returns:
            TTSResult with audio bytes (WAV format)
        """
        if not self.load_voice(voice_key):
            raise RuntimeError("No TTS voice available")

        try:
            # Piper synthesis
            wav_io = io.BytesIO()
            self._piper_model.synthesize(text, wav_io)
            wav_bytes = wav_io.getvalue()
            
            # Calculate duration from WAV header
            sample_rate = self._piper_model.config.sample_rate
            # WAV header is 44 bytes, 16-bit samples = 2 bytes each
            audio_data_bytes = len(wav_bytes) - 44
            duration = audio_data_bytes / (sample_rate * 2) if audio_data_bytes > 0 else 0.0

            return TTSResult(
                audio_bytes=wav_bytes,
                sample_rate=sample_rate,
                duration_seconds=duration,
                voice=self._loaded_voice or self.default_voice,
                engine="piper",
            )
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            raise

    def synthesize_to_file(self, text: str, output_path: str,
                           voice_key: Optional[str] = None) -> str:
        """Synthesize speech and save to WAV file."""
        result = self.synthesize(text, voice_key)
        with open(output_path, "wb") as f:
            f.write(result.audio_bytes)
        logger.info(f"Audio saved to {output_path}")
        return output_path

    def play(self, text: str, voice_key: Optional[str] = None):
        """Synthesize and play speech through speakers."""
        result = self.synthesize(text, voice_key)
        self._play_audio(result)

    def _play_audio(self, result: TTSResult):
        """Play audio bytes through system speakers."""
        try:
            import sounddevice as sd
            import wave
            
            # Parse WAV bytes
            with io.BytesIO(result.audio_bytes) as wav_io:
                with wave.open(wav_io, "rb") as wf:
                    audio_data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
                    sd.play(audio_data, samplerate=wf.getsampwidth() * wf.getframerate())
                    sd.wait()
        except ImportError:
            logger.warning("sounddevice not installed. Cannot play audio.")
        except Exception as e:
            logger.error(f"Audio playback failed: {e}")


class MultilingualTTSEngine:
    """
    TTS engine with automatic language detection and voice switching.
    
    Handles code-switching (mixing English technical terms with local language)
    common in mining communities.
    """

    def __init__(self, voice_dir: str = "models/piper"):
        self.piper = PiperTTSEngine(voice_dir=voice_dir)
        self._voice_cache = {}

    def synthesize(self, text: str, language: str = "en") -> TTSResult:
        """
        Synthesize with automatic voice selection.
        
        For code-switched text (English + Swahili), uses the primary language voice.
        Technical terms are kept as-is — Piper handles them phonetically.
        """
        voice_key = language if language in PiperTTSEngine.VOICE_MAP else "en"
        return self.piper.synthesize(text, voice_key)

    def speak_response(self, text: str, language: str = "en"):
        """Convenience: synthesize and play immediately."""
        self.piper.play(text, language if language in PiperTTSEngine.VOICE_MAP else "en")


# === Geology-Specific TTS Helpers ===

# Mining terminology pronunciation guide
# Maps technical terms to phonetic approximations for better TTS output
MINING_PHONETICS = {
    "pyrite": "PIE-rite",
    "chalcopyrite": "cal-co-PIE-rite", 
    "galena": "ga-LEE-na",
    "magnetite": "MAG-ne-tite",
    "hematite": "HEM-a-tite",
    "cassiterite": "cass-IT-er-ite",
    "coltan": "COL-tan",
    "kimberlite": "KIM-ber-lite",
    "alluvial": "a-LOO-vee-al",
    "XRF": "X-R-F",
    "ppm": "parts per million",
    "g/t": "grams per tonne",
}

# Swahili geological terms
GEOLOGY_TERMS_SW = {
    "gold": "dhahabu",
    "silver": "fedha",
    "copper": "shaba",
    "iron": "chuma",
    "diamond": "almasi",
    "mineral": "madini",
    "rock": "jiwe",
    "soil": "udongo",
    "sample": "sampuli",
    "mine": "mgodi",
    "dig": "chimba",
    "value": "thamani",
}


def prepare_geological_text(text: str, language: str = "en") -> str:
    """
    Prepare geological text for TTS by handling technical terms.
    
    For English: uses phonetic guide for tricky mineral names
    For Swahili: translates key technical terms
    """
    if language == "sw":
        # For Swahili output, keep English technical terms but add Swahili context
        for eng, swa in GEOLOGY_TERMS_SW.items():
            text = text.replace(f" {eng} ", f" {eng} ({swa}) ")
    
    # Apply phonetic guides for hard-to-pronounce terms
    for term, phonetic in MINING_PHONETICS.items():
        text = text.replace(term, phonetic)
    
    return text


# === Convenience Functions ===

def create_tts_engine(
    default_language: str = "sw",
    voice_dir: str = "models/piper",
) -> MultilingualTTSEngine:
    """Create the default TTS engine for AfriMine."""
    return MultilingualTTSEngine(voice_dir=voice_dir)


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)
    
    engine = create_tts_engine(default_language="en")
    
    test_texts = [
        ("This rock sample contains gold at 3.5 grams per tonne.", "en"),
        ("Sampuli hii ina dhahabu gramu 3.5 kwa tani.", "sw"),
        ("The mineral is pyrite, also known as fool's gold.", "en"),
    ]
    
    for text, lang in test_texts:
        prepared = prepare_geological_text(text, lang)
        print(f"[{lang}] Speaking: {prepared}")
        try:
            engine.speak_response(prepared, lang)
        except Exception as e:
            print(f"  (Audio skipped: {e})")
