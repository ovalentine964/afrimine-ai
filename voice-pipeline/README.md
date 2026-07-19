# AfriMine AI — Voice Pipeline

**Zero-cost, offline-first voice interface for African mining communities.**

Field workers speak in Swahili, Dholuo, Kikuyu, or English → the system understands, routes to geological AI agents, and speaks back — all on a $50 Android phone with no internet.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Flutter Mobile App                           │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Mic Input │→│ STT Engine   │→│ Pipeline  │→│ TTS Output │  │
│  └──────────┘  └──────────────┘  └──────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
                         │                    │
                         ▼                    ▼
              ┌──────────────────┐  ┌──────────────────┐
              │  Vosk (offline)  │  │  Piper TTS       │
              │  50MB model      │  │  (offline, CPU)  │
              └──────────────────┘  └──────────────────┘
                         │
                         ▼ (when online)
              ┌──────────────────┐
              │  Groq Whisper    │
              │  (cloud backup)  │
              └──────────────────┘
                         │
                         ▼
              ┌──────────────────────────────────────┐
              │         Voice Pipeline Core           │
              │  ┌────────────┐  ┌────────────────┐  │
              │  │ Intent     │→│ Agent Router    │  │
              │  │ Recognizer │  │ (LangGraph)    │  │
              │  └────────────┘  └────────────────┘  │
              └──────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────────────────────┐
              │     LangGraph Agent System            │
              │  ┌──────────┐ ┌──────────────────┐   │
              │  │ Sampling │ │ Mineral Analysis │   │
              │  │ Agent    │ │ Agent            │   │
              │  └──────────┘ └──────────────────┘   │
              │  ┌──────────┐ ┌──────────────────┐   │
              │  │ Geology  │ │ Market Price     │   │
              │  │ Agent    │ │ Agent            │   │
              │  └──────────┘ └──────────────────┘   │
              │  ┌──────────┐ ┌──────────────────┐   │
              │  │ Report   │ │ Compliance       │   │
              │  │ Agent    │ │ Agent            │   │
              │  └──────────┘ └──────────────────┘   │
              └──────────────────────────────────────┘
```

## Design Principles

| Principle | Implementation |
|-----------|---------------|
| **$0 cost** | Vosk (offline STT) + Piper (offline TTS) + Groq free tier (backup) + Gemini free tier (reasoning) |
| **Offline-first** | All core STT/TTS works without internet. Online features are enhancement, not requirement |
| **2GB RAM** | Vosk model: 50MB. Piper model: ~50MB. Total pipeline: <200MB resident |
| **African languages** | Swahili, Dholuo, Kikuyu, English — with mining vocabulary |
| **LangGraph integration** | Voice intents map to agent graph nodes for geological workflows |

## Components

| File | Purpose |
|------|---------|
| `stt_engine.py` | Speech-to-text: Vosk (offline) + Groq Whisper (online fallback) |
| `tts_engine.py` | Text-to-speech: Piper TTS (offline, CPU-only) |
| `voice_pipeline.py` | Full pipeline: STT → Intent → Agent Routing → TTS |
| `language_support.py` | African language detection, translation, mining vocabulary |
| `offline_handler.py` | Offline-first: cache responses, queue for sync |
| `flutter_integration.dart` | Flutter/Dart mobile app voice interface |
| `voice_commands.yaml` | Voice command definitions for mineral analysis workflows |
| `test_pipeline.py` | Test suite |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Download Vosk model (Swahili/English)
wget https://alphacephei.com/vosk/models/vosk-model-small-sw-0.3.zip
unzip vosk-model-small-sw-0.3.zip

# 3. Download Piper TTS voice
pip install piper-tts
python -m piper.download_voices en_US-lessac-medium

# 4. Run the pipeline
python voice_pipeline.py --language sw --mode offline

# 5. Run tests
python -m pytest test_pipeline.py -v
```

## Voice Commands (Mining Workflows)

```yaml
# Example commands field workers can speak:
"Angalia sampuli hii"          # "Check this sample" (Swahili)
"Je, kuna dhahabu?"           # "Is there gold?" (Swahili)
"Picha ya ramani"             # "Show the map" (Swahili)
"Tafadhali ripoti"            # "Generate report" (Swahili)
"What minerals are here?"     # English
"Bado iko offline?"           # "Is it still offline?" (Swahili)
```

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 2GB | 4GB |
| Storage | 500MB | 1GB |
| CPU | ARM Cortex-A53 | ARM Cortex-A76+ |
| Android | 8.0+ | 10+ |
| Microphone | Built-in | External (field noise) |

## Integration with LangGraph Agents

The voice pipeline maps spoken intents to agent graph nodes:

```
"Analyze this sample" → mineral_analysis_agent → geological_report
"What's gold worth?"  → market_price_agent → price_update
"Generate report"     → report_agent → pdf_report
"Check compliance"    → compliance_agent → compliance_check
```

See `voice_commands.yaml` for full command definitions.

## Offline Sync Strategy

When connectivity returns:
1. Queued voice commands are sent to cloud agents for enhanced analysis
2. Results are cached locally for future offline use
3. Geological reports sync to Supabase
4. Market prices update from latest API data

## License

Apache 2.0 — Same as AfriMine AI project.
