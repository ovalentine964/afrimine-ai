# AfriMine AI — Mining Intelligence Platform

> **Democratizing mining intelligence for African communities.**
> AI-powered mineral detection, geological estimation, and operational decision-making — previously available only to major foreign mining corporations.

---

## The Problem

Chinese miners pay Kenyan families **1M KES (~$7,700)** for land containing **28M+ KES** in gold. That's a **28:1 extraction ratio** — they take 96.5% of the value while leaving the land destroyed.

**The root cause: Information asymmetry.** Foreign miners have geological survey data, portable XRF analyzers, and professional labs. Local families have none of that.

## The Solution

AfriMine AI gives mining communities the same technological capabilities as major foreign operations:

- 📷 **AI Mineral Detection** — Photograph a rock sample → get mineral ID, grade estimate, confidence score
- 🛰️ **Satellite Analysis** — Free Sentinel-2 imagery → alteration maps showing where gold/copper likely exists
- 📊 **Investor-Grade Reports** — One-click PDF reports that banks and investors take seriously
- 📱 **Works Offline** — Full functionality without internet. Syncs when connected.
- 🎙️ **Voice Interface** — Multilingual voice commands in Swahili, Dholuo, Kikuyu, and English
- ⚛️ **Quantum-Enhanced** — Quantum computing for geochemical classification and pit optimization

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐ │
│  │ Flutter App  │  │ Flutter Web │  │ OpenClaw Gateway            │ │
│  │ (Field)      │  │ (Investor)  │  │ (WhatsApp/Telegram)         │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────────────┘ │
└─────────┼────────────────┼─────────────────────┼────────────────────┘
          │                │                     │
┌─────────▼────────────────▼─────────────────────▼────────────────────┐
│                  API LAYER (Go + Chi Router)                         │
│  /v1/samples │ /v1/analysis │ /v1/reports │ /v1/auth │ /v1/market  │
└──────────────────────────┬───────────────────────────────────────────┘
                           │ A2A Protocol (JSON-RPC 2.0)
┌──────────────────────────▼───────────────────────────────────────────┐
│              AGENT ORCHESTRATION (LangGraph 1.0)                      │
│                                                                       │
│  ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐   │
│  │ Sampling  │───▶│ Analysis  │──┬─▶│ Geology   │──┐ │           │   │
│  │ Agent     │    │ Agent     │  │  │ Agent     │  │ │  Report   │   │
│  └───────────┘    └───────────┘  │  └───────────┘  ├▶│  Agent    │   │
│                                  │  ┌───────────┐  │ │           │   │
│                                  └─▶│ Market    │──┘ └─────┬─────┘   │
│                                     │ Agent     │         │          │
│                                     └───────────┘    ┌────▼─────┐   │
│                                                      │Compliance│   │
│                                                      │ Agent    │   │
│                                                      └──────────┘   │
│  LLM: Gemini 2.5 Flash │ Memory: Supabase pgvector (5 layers)      │
└──────────────────────────────────────────────────────────────────────┘
          │                    │                    │
┌─────────▼──────┐  ┌─────────▼──────┐  ┌─────────▼──────┐
│ Supabase       │  │ Google Earth   │  │ NVIDIA Jetson  │
│ PostgreSQL     │  │ Engine         │  │ (Edge AI)      │
│ + Auth + Store │  │ (Satellite)    │  │                │
└────────────────┘  └────────────────┘  └────────────────┘
```

---

## Tech Stack

| Layer | Technology | Cost |
|-------|-----------|------|
| **Frontend** | Flutter (Dart) — Android/iOS/Web | $0 |
| **Backend** | Go (Chi router) — single binary | $0 |
| **Agent Framework** | LangGraph 1.0 (replaced CrewAI) | $0 |
| **AI/LLM** | Google Gemini 2.5 Flash | $0 |
| **Database** | Supabase (PostgreSQL + Auth + Storage) | $0 |
| **Hosting** | Cloudflare Pages + Workers | $0 |
| **Satellite** | Google Earth Engine (Sentinel-2) | $0 |
| **Voice** | Vosk (STT) + Piper (TTS) — offline | $0 |
| **Quantum** | IBM Quantum + D-Wave | $0 |
| **Edge** | NVIDIA Jetson Orin Nano | $249 |
| **CI/CD** | GitHub Actions | $0 |
| **Monitoring** | Sentry + Uptime Robot | $0 |

**Total software cost: $0/month** | **Total hardware: $249** (one Jetson kit)

---

## Repository Structure

```
afrimine-ai/
├── src/
│   ├── agents/          # LangGraph agent pipeline (Python)
│   │   ├── agents/      # 6 specialized agents
│   │   ├── tools/       # MCP client
│   │   ├── security/    # Security middleware
│   │   └── memory/      # Supabase checkpointer
│   ├── backend/         # Go API server (Chi router)
│   │   ├── handlers/    # REST endpoints
│   │   ├── middleware/   # Auth, CORS, rate limiting
│   │   └── a2a/         # A2A protocol bridge
│   ├── frontend/        # Flutter mobile/web app
│   │   ├── lib/screens/ # 7 screens
│   │   ├── lib/services/# Offline, camera, voice, API
│   │   └── lib/widgets/ # Reusable components
│   └── satellite/       # Google Earth Engine analysis
├── docs/
│   ├── architecture/    # System architecture
│   └── research/        # Research documents
│       └── weekly/      # Weekly AI intelligence reports
├── security/            # Security hardening documentation
├── memory-system/       # Memory architecture (design docs)
├── voice-pipeline/      # Voice interface (design docs)
├── langgraph-migration/ # Migration code (reference)
├── scripts/             # Setup, deploy, backup scripts
├── monitoring/          # Sentry + Uptime Robot config
├── .github/workflows/   # CI/CD pipelines
├── ARCHITECTURE_V3.md   # Master architecture document
├── COST_MODEL_REAL.md   # Honest cost breakdown
├── DEPLOYMENT_DECISION.md # Deployment strategy
└── TESTING_STRATEGY.md  # Testing approach
```

---

## Quick Start

```bash
# Clone
git clone https://github.com/ovalentine964/afrimine-ai.git
cd afrimine-ai

# Setup Supabase
bash scripts/setup-supabase.sh

# Backend (Go)
cd src/backend
go mod download
go run main.go

# Agent Pipeline (Python)
cd src/agents
pip install -r requirements.txt
python main.py

# Frontend (Flutter)
cd src/frontend
flutter pub get
flutter run
```

---

## Key Documents

| Document | Description |
|----------|-------------|
| [ARCHITECTURE_V3.md](ARCHITECTURE_V3.md) | Master architecture (11 ADRs, all layers) |
| [COST_MODEL_REAL.md](COST_MODEL_REAL.md) | Honest cost breakdown by growth stage |
| [DEPLOYMENT_DECISION.md](DEPLOYMENT_DECISION.md) | Cloudflare + Railway deployment guide |
| [TESTING_STRATEGY.md](TESTING_STRATEGY.md) | Unit, integration, E2E, load testing |
| [Security Hardening](security/) | Threat model, agent security, audit logging |
| [Weekly AI Research](docs/research/weekly/) | AI intelligence reports (July 2026) |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License — see [LICENSE](LICENSE)

## Acknowledgments

Built for Valentine Cohusdex and the mining communities of Nyatike, Migori County, Kenya.

---

**AfriMine AI** — Know Your Ground. 💰🌍
