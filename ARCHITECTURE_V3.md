# AfriMine AI — Architecture Document v3.0

**Date:** July 19, 2026
**Status:** AUTHORITATIVE — Engineering Reference
**Supersedes:** FINAL_ARCHITECTURE.md (v2.0, July 18, 2026)
**Repository:** https://github.com/ovalentine964/afrimine-ai

---

## Table of Contents

1. [Architecture Decision Records](#1-architecture-decision-records)
2. [System Architecture v3.0](#2-system-architecture-v30)
3. [Agent Architecture](#3-agent-architecture)
4. [Data Architecture](#4-data-architecture)
5. [Integration Architecture](#5-integration-architecture)
6. [Deployment Architecture](#6-deployment-architecture)
7. [Security Architecture](#7-security-architecture)
8. [Migration Roadmap](#8-migration-roadmap)
9. [Cost Model](#9-cost-model)
10. [Technology Radar](#10-technology-radar)
11. [Horizontal Scaling Strategy](#11-horizontal-scaling-strategy)
12. [Offline Sync Conflict Resolution](#12-offline-sync-conflict-resolution)

### Companion Documents
- [COST_MODEL_REAL.md](./COST_MODEL_REAL.md) — Honest cost projections with hardware costs
- [DEPLOYMENT_DECISION.md](./DEPLOYMENT_DECISION.md) — Cloudflare + Railway deployment guide
- [TESTING_STRATEGY.md](./TESTING_STRATEGY.md) — Unit, integration, E2E, load, and security testing
- [security/agent-security-hardening.md](./security/agent-security-hardening.md) — LangGraph security model

---

## 1. Architecture Decision Records

### ADR-001: Multi-Agent Framework — CrewAI → LangGraph 1.0

| Field | Value |
|-------|-------|
| **Status** | ✅ Accepted |
| **Date** | July 19, 2026 |
| **Deciders** | Architecture Research Agent, validated by 15+ sources |

**Context:** AfriMine AI's 6-agent mineral detection pipeline (Sampling → Analysis → Geology → Market → Report → Compliance) was originally built on CrewAI. Research revealed CrewAI's limitations: no graph-based workflows (cannot model parallel branches), fragile sequential pipelines, production score of 7.8/10, and the fact that 80% of AI projects fail to reach production — with multi-agent coordination latency being a primary cause. The real workflow requires parallel fan-out (Geology ∥ Market), conditional routing (mineral type → different analysis paths), and iterative refinement loops (Report → re-analysis). CrewAI cannot model any of these natively.

**Decision:** Replace CrewAI with **LangGraph 1.0** (Alice Labs production score: 9.2/10, #1 ranked). LangGraph is production-proven at Klarna (85M+ users), Replit, Elastic, LinkedIn, and Uber. It models directed graphs natively with conditional edges, parallel fan-out/fan-in, checkpointing for crash recovery, and per-node state management. MIT licensed, self-hosted, zero cost.

**Alternatives Considered:**

| Framework | Score | Rejection Reason |
|-----------|-------|-----------------|
| Microsoft Agent Framework v1.13 | 7.05/10 | Azure-tethered, no Go support, enterprise overkill |
| Pydantic AI V2 | 5.20/10 | No multi-agent orchestration, no graph workflows |
| LangChain DeepAgents | 8.00/10 | Built on LangGraph — use as pattern, not framework |
| CrewAI v1.15.2 (current) | 7.20/10 | Cannot model parallel branches, no graph-based state machines |
| Omnigent, Mozilla Otari | N/A | Meta-harnesses/control planes, not orchestration frameworks |

**Consequences:**
- **Positive:** Graph-based workflows, checkpointing, parallel execution, production-proven, 60K+ GitHub stars, native Gemini integration, Supabase checkpointer
- **Negative:** No Go SDK (solved via A2A protocol bridge), 2-3 week learning curve for graph concepts, migration effort (~200 hours over 10 weeks)
- **Risk:** Medium — mitigated by parallel operation during migration and shadow-testing

**References:** [Alice Labs Framework Ranking](https://alicelabs.ai), [Langfuse Comparison](https://langfuse.com/blog/2025-03-19-ai-agent-comparison), [Framework Replacement Decision](./ai-week-research/07-framework-replacement.md)

---

### ADR-002: Primary LLM — Google Gemini 2.5 Flash

| Field | Value |
|-------|-------|
| **Status** | ✅ Accepted |
| **Date** | July 18, 2026 (unchanged from v2.0) |

**Context:** The platform requires a capable LLM for geological reasoning, mineral classification from images, and report generation — all at zero cost.

**Decision:** **Google Gemini 2.5 Flash** as primary LLM. Free tier via Google AI Studio (no billing required). Vision-capable (mineral photo analysis), 1,500 req/day free, hybrid reasoning with adjustable thinking budget.

**Alternatives Considered:**

| Model | Role | Free Tier | Rejection Reason |
|-------|------|-----------|-----------------|
| GPT-5.6 Luna | Potential primary | TBD | Monitor — could replace Gemini if free tier offered |
| Claude Sonnet 5 | Backup reasoning | Free plan (limited) | Default on Claude Free plan, use as backup |
| Mistral AI | Backup/fallback | 1B tokens/month free | Use as fallback when Gemini limits hit |
| Groq (Llama 4 Scout) | Speed layer | 1K RPD, 30K TPM | Use for real-time voice, not primary reasoning |
| Qwen3-32B (Groq) | Alternative reasoning | 60 RPM, 500K TPD | Test for geological Q&A |
| Kimi K3 | Open-weight frontier | API TBD | Evaluate for self-hosted sensitive reports |

**Consequences:**
- Generous free tier sustains $0/month architecture
- Vision capability enables direct mineral photo analysis
- Risk: Google could change free tier — mitigated by Mistral + Groq fallback chain

**LLM Fallback Chain:**
```
Gemini 2.5 Flash (primary, 95% accuracy)
  → Claude Sonnet 5 (free plan backup)
    → Mistral AI (1B tokens/month)
      → Groq Llama 4 Scout (speed fallback)
        → Groq Qwen3-32B (reasoning fallback)
          → Local Gemma 4 E2B (offline, on-device)
```

---

### ADR-003: Voice Pipeline Architecture — Chained Pipeline

| Field | Value |
|-------|-------|
| **Status** | ✅ Accepted |
| **Date** | July 19, 2026 |

**Context:** Field workers in Nyatike, Migori County primarily speak Dholuo and Swahili. They need voice-driven interfaces for mineral analysis in remote mining sites with intermittent connectivity. OpenAI GPT-Live set the UX bar for full-duplex voice, but is not free. Microsoft Paza provides ASR for 6 Kenyan languages. Google WAXAL provides 11,000+ hours of African speech data. sherpa-onnx enables offline STT in Flutter.

**Decision:** Implement a **chained (cascading) voice pipeline** — not native speech-to-speech. Architecture:

```
Voice Input → STT → Translation → LLM Reasoning → Translation → TTS → Voice Output
```

Each layer is independently swappable:

| Layer | Primary | Offline Fallback | Free Tier |
|-------|---------|-----------------|-----------|
| **STT** | Groq Whisper Large V3 (20 RPM, 2K RPD) | sherpa-onnx + Paza models (Dholuo/Swahili) | ✅ |
| **Translation** | Gemini 2.5 Flash | Local Gemma 4 E2B | ✅ |
| **Reasoning** | Gemini 2.5 Flash | Local Gemma 4 E2B / LFM2.5-1.2B | ✅ |
| **TTS** | Kokoro (82M params, on-device) | Piper TTS (offline) | ✅ |
| **Voice Output** | Fish Audio S2 (voice cloning) | Kokoro cross-lingual | ✅ |

**Alternatives Considered:**

| Approach | Rejection Reason |
|----------|-----------------|
| OpenAI GPT-Live (full-duplex) | Not free, API not yet available |
| OpenAI Realtime API (native S2S) | Black box, can't inspect/translate at each hop, not free |
| AssemblyAI Voice Agent API | Not free for African languages |
| AWS Nova Sonic | Not free, AWS dependency |

**Consequences:**
- Full offline capability (sherpa-onnx + Kokoro on device)
- Swahili/Dholuo support via Paza models + WAXAL dataset
- Each layer independently upgradeable
- Higher latency than native S2S (~500ms vs ~200ms) — acceptable for field use
- Voice cloning (Fish Audio S2) creates trusted community voice for reports

---

### ADR-004: Memory Architecture — 5-Layer System on Supabase

| Field | Value |
|-------|-------|
| **Status** | ✅ Accepted |
| **Date** | July 19, 2026 |

**Context:** The multi-agent system needs persistent memory across sessions, the ability to find similar past analyses, geological knowledge retrieval, learned workflow templates, and long-term facts. Research identified 5 memory layers as the industry standard (short-term, episodic, semantic, procedural, long-term).

**Decision:** Implement a **5-layer memory architecture** on Supabase PostgreSQL with pgvector:

| Layer | Purpose | Storage | TTL |
|-------|---------|---------|-----|
| **Short-term** | Session state, LangGraph checkpoints | `agent_sessions` + `checkpoints` | 24h auto-expire |
| **Episodic** | Analysis history, "find similar" queries | `analysis_history` + pgvector | Permanent |
| **Semantic** | Geological knowledge, vector embeddings | `geological_knowledge` + `mineral_patterns` | Permanent |
| **Procedural** | Learned workflows, successful patterns | `learned_workflows` | Permanent |
| **Long-term** | Persistent facts, calibration data | `agent_long_term_memory` | Configurable TTL |

**Key Design Decisions:**
- **Supabase over Redis:** Free tier, persistent, SQL-queryable, pgvector for embeddings
- **pgvector over Pinecone:** Zero cost, same database, no external service
- **Embedding dimension 384:** all-MiniLM-L6-v2 (small, fast, free, good enough for geological text)
- **IVFFlat index** for <100K rows; migrate to HNSW when scale demands
- **Optimistic concurrency** via version columns (no distributed locks)

**Alternatives Considered:**

| Option | Rejection Reason |
|--------|-----------------|
| Redis for short-term | Not free tier, external dependency |
| Pinecone for vectors | Not free, external service |
| ChromaDB | Extra infrastructure, Supabase pgvector covers the need |
| Single flat memory | No separation of concerns, poor retrieval quality |

---

### ADR-005: Edge Deployment — Jetson Orin Nano + Flutter Phone

| Field | Value |
|-------|-------|
| **Status** | ✅ Accepted (with upgrade path to T2000) |
| **Date** | July 19, 2026 |

**Context:** Mining sites in Nyatike have intermittent connectivity. Field workers need on-device AI for mineral classification, voice interaction, and offline data collection. NVIDIA Jetson Thor T2000 (400 FP4 TFLOPS, 16GB) was announced July 15, 2026 as an upgrade path. Gemma 4 E2B runs on 5GB RAM at 4-bit quantization. LFM2.5-1.2B-Thinking runs in 900MB.

**Decision:** Deploy on two edge tiers:

| Tier | Device | AI Models | Use Case |
|------|--------|-----------|----------|
| **Phone** | Budget Android (2-4GB RAM) | TFLite mineral classifier, sherpa-onnx STT, LFM2.5-1.2B reasoning | Field data collection, basic classification, voice input |
| **Field Kit** | NVIDIA Jetson Orin Nano (upgrade → T2000) | Gemma 4 E2B, Kokoro TTS, full geology agent | Advanced analysis, report generation, voice interaction |

**Offline Fallback Chain:**
```
Gemini API (best, 95% accuracy, requires internet)
  → Cached Gemini results (from last sync)
    → Jetson Orin Nano local inference (Gemma 4 E2B)
      → Phone TFLite model (70% accuracy)
        → Field test kits + manual entry
```

**Consequences:**
- Works offline for 3+ days (phone storage)
- Jetson T2000 upgrade path when pricing available
- Qualcomm NPU (60 TOPS) support for Android phones via QNN SDK
- Model quantization critical (INT8/INT4) for budget phones

---

### ADR-006: Communication Gateway — OpenClaw

| Field | Value |
|-------|-------|
| **Status** | ✅ Accepted |
| **Date** | July 19, 2026 |

**Context:** Mining community workers in Nyatike already use WhatsApp and Telegram. Building custom chat interfaces is expensive and unnecessary. OpenClaw is the fastest-growing open-source project in GitHub history (185K+ stars), now a 501(c)(3) foundation, MIT-licensed, with 24+ messaging platform integrations and 142 official plugins.

**Decision:** Use **OpenClaw** as the primary agent gateway for field worker communication. Workers interact with AfriMine AI through WhatsApp/Telegram — apps they already use.

**Capabilities Used:**
- WhatsApp/Telegram channel integration (field workers)
- Skill Workshop for reusable geological analysis skills
- Exec Auto-Mode for safe geological tool execution
- SkillSpector (NVIDIA) for skill security scanning
- Multi-model support (Gemini, Mistral, Groq)

**Consequences:**
- Zero custom frontend needed for basic field interaction
- 4.5M new "claws"/week = large community for support
- 501(c)(3) foundation ensures long-term viability
- Skills published to ClawHub gain community visibility

---

### ADR-007: Quantum Integration — IBM Quantum + D-Wave Free Tiers

| Field | Value |
|-------|-------|
| **Status** | ✅ Accepted (Phase 3) |
| **Date** | July 19, 2026 |

**Context:** Pit optimization, logistics routing, and resource allocation are combinatorial optimization problems suitable for quantum approaches. IBM Quantum offers free-tier access with Qiskit v2.3 (Store instruction, Executor primitive, NoiseLearnerV3). D-Wave Advantage2 (1,200+ qubits) is available via Leap free tier. ESA installed its first quantum computer for Earth observation research. QAOA improvements (Hamiltonian compression) reduce qubit requirements.

**Decision:** Integrate quantum computing in Phase 3 using free tiers:

| Provider | Use Case | Free Access |
|----------|----------|-------------|
| **IBM Quantum** | QAOA pit optimization, hybrid quantum-classical | Open Plan (free, limited QPU minutes) |
| **D-Wave Leap** | Quantum annealing for logistics/resource allocation | Free tier (monthly QPU minutes) |
| **PennyLane** | Quantum ML for mineral classification | Open-source, runs on IBM/D-Wave |

**Specific Applications:**
- **Pit optimization:** Lerchs-Grossmann → QUBO formulation → D-Wave annealing
- **Logistics routing:** Hybrid quantum tabu search (Springer 2026 paper)
- **Mineral classification:** Quantum Fisher information matrix for few-shot learning
- **Grade estimation:** Quantum-enhanced geostatistical modeling

**Consequences:**
- Free tier limits problem size (~100 variables on IBM, ~1200 on D-Wave)
- Hamiltonian compression reduces qubit count needed
- Phase 3 only — not on critical path for MVP
- Classroom Accounts available for university partnerships in Kenya

---

### ADR-008: Go ↔ Python Integration — A2A Protocol

| Field | Value |
|-------|-------|
| **Status** | ✅ Accepted |
| **Date** | July 19, 2026 |

**Context:** The backend is Go (Chi router), the AI/agent layer is Python (LangGraph). There is no LangGraph Go SDK. Google published a cross-language A2A protocol tutorial (June 22, 2026) showing Python agents collaborating with Go agents via JSON-RPC 2.0.

**Decision:** Use **A2A (Agent-to-Agent) protocol** for Go ↔ Python communication:

```
Go Backend ──A2A (JSON-RPC 2.0)──→ Python LangGraph Agents
     │                                      │
     └── Agent Cards at /.well-known/ ──────┘
```

Each agent exposes an Agent Card (JSON metadata) at `/.well-known/agent.json`. The Go backend discovers and invokes agents via JSON-RPC 2.0 over HTTP.

**Consequences:**
- Language-agnostic — any future service can invoke agents
- ~50-100ms overhead per agent call (acceptable)
- Industry-standard protocol (150+ organizations)
- Agent Cards enable future federation across mining regions

---

### ADR-009: Frontend — Flutter (Unchanged)

| Field | Value |
|-------|-------|
| **Status** | ✅ Accepted (unchanged from v2.0) |

**Decision:** Continue with **Flutter (Dart)** for Android/iOS/Web. One codebase, offline-first with SQLite, camera + GPS + voice integration.

---

### ADR-010: Database + Auth + Storage — Supabase (Unchanged)

| Field | Value |
|-------|-------|
| **Status** | ✅ Accepted (unchanged from v2.0) |

**Decision:** Continue with **Supabase** for PostgreSQL (500MB free), Auth (50K MAU), Storage (1GB), Realtime, Edge Functions, and now pgvector for embeddings.

---

### ADR-011: Hosting — Cloudflare Pages + Workers (Unchanged)

| Field | Value |
|-------|-------|
| **Status** | ✅ Accepted (unchanged from v2.0) |

**Decision:** Continue with **Cloudflare Pages + Workers** for frontend hosting and API edge deployment. Africa CDN, free SSL, free tier.

---

## 2. System Architecture v3.0

### 2.1 Complete System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                        │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Flutter App   │  │ Flutter Web  │  │ WhatsApp     │  │ Telegram     │   │
│  │ (Field)       │  │ (Investor)   │  │ (OpenClaw)   │  │ (OpenClaw)   │   │
│  │ Android/iOS   │  │ Browser      │  │ Voice/Text   │  │ Voice/Text   │   │
│  │               │  │              │  │              │  │              │   │
│  │ • Camera      │  │ • Reports    │  │ • Field Q&A  │  │ • Field Q&A  │   │
│  │ • GPS         │  │ • Dashboard  │  │ • Voice memos│  │ • Voice memos│   │
│  │ • Voice       │  │ • Invest     │  │ • Photo share│  │ • Photo share│   │
│  │ • Offline     │  │              │  │              │  │              │   │
│  │ • TFLite AI   │  │              │  │              │  │              │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                 │                 │             │
│         └─────────────────┼─────────────────┼─────────────────┘             │
└───────────────────────────┼─────────────────┼───────────────────────────────┘
                            │ HTTPS/WSS       │
┌───────────────────────────▼─────────────────▼───────────────────────────────┐
│                     OPENCLAW GATEWAY (Self-Hosted)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ WhatsApp     │  │ Telegram     │  │ Signal       │  │ Web Chat     │   │
│  │ Channel      │  │ Channel      │  │ Channel      │  │ Channel      │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ Skills: satellite-analysis · geology-report · market-lookup · voice │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │ HTTP API
┌───────────────────────────▼─────────────────────────────────────────────────┐
│                     CLOUDFLARE (Free Tier)                                  │
│  Pages (frontend) + Workers (API proxy) + CDN + DNS + SSL + WAF            │
└───────────────────────────┬─────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────────────┐
│                     GO BACKEND (Chi Router)                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ Auth     │ │ File     │ │ Job      │ │ Sync     │ │ A2A      │        │
│  │ Proxy    │ │ Upload   │ │ Queue    │ │ Engine   │ │ Gateway  │        │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────┬─────┘        │
└───────────────────────────┬────────────────────────────────┼───────────────┘
                            │                                │
              ┌─────────────┼────────────┐    A2A Protocol   │
              │             │            │    (JSON-RPC 2.0)  │
              ▼             ▼            ▼                    ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐
│ Supabase     │ │ Supabase     │ │ Google Earth │ │ PYTHON LANGGRAPH         │
│ PostgreSQL   │ │ Storage      │ │ Engine       │ │ ORCHESTRATOR             │
│ + pgvector   │ │ (images)     │ │ (satellite)  │ │                          │
│ + PostGIS    │ │              │ │              │ │ ┌──────────────────────┐  │
│              │ │              │ │              │ │ │ StateGraph           │  │
│ • Auth       │ │ • Photos     │ │ • Sentinel-2 │ │ │ (AfriMineState)      │  │
│ • Database   │ │ • Reports    │ │ • Band ratios│ │ │                      │  │
│ • Realtime   │ │ • Satellite  │ │ • NDVI       │ │ │ 6 Agents (see §3)    │  │
│ • RLS        │ │              │ │              │ │ │                      │  │
│ • Checkpoint │ │              │ │              │ │ │ Checkpointer:        │  │
│ • Memory (5L)│ │              │ │              │ │ │ Supabase PostgreSQL  │  │
│              │ │              │ │              │ │ │                      │  │
│              │ │              │ │              │ │ │ Memory: 5-Layer      │  │
│              │ │              │ │              │ │ │ (see §4)             │  │
│              │ │              │ │              │ │ └──────────────────────┘  │
│              │ │              │ │              │ │                          │
│              │ │              │ │              │ │ Tools: MCP Servers       │
│              │ │              │ │              │ │ • satellite-mcp          │
│              │ │              │ │              │ │ • geology-mcp            │
│              │ │              │ │              │ │ • market-mcp             │
│              │ │              │ │              │ │ • compliance-mcp         │
│              │ │              │ │              │ │ • report-mcp             │
│              │ │              │ │              │ │                          │
│              │ │              │ │              │ │ Observability:           │
│              │ │              │ │              │ │ LangSmith (5K traces/mo) │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                     EDGE DEPLOYMENT                                         │
│                                                                             │
│  ┌──────────────────────────┐  ┌──────────────────────────────────────────┐ │
│  │ NVIDIA Jetson Orin Nano  │  │ Budget Android Phone                     │ │
│  │ (Field Kit)              │  │ (Worker Device)                          │ │
│  │                          │  │                                          │ │
│  │ • Gemma 4 E2B (5GB)     │  │ • TFLite mineral classifier              │ │
│  │ • Kokoro TTS             │  │ • sherpa-onnx STT (Paza Dholuo)         │ │
│  │ • Ollama + Open WebUI    │  │ • LFM2.5-1.2B reasoning (<1GB)          │ │
│  │ • LangGraph (headless)   │  │ • SQLite offline cache                   │ │
│  │ • Full geology agent     │  │ • Flutter app                            │ │
│  │                          │  │                                          │ │
│  │ Upgrade path: T2000      │  │ Target: 2-4GB RAM                        │ │
│  └──────────────────────────┘  └──────────────────────────────────────────┘ │
│                                                                             │
│  Offline Duration: 3+ days (phone storage)                                  │
│  Sync Strategy: Delta sync with exponential backoff                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Layer Summary

| Layer | Technology | Responsibility |
|-------|-----------|----------------|
| **Client** | Flutter (Dart) + OpenClaw channels | User interface, offline cache, voice input, camera/GPS |
| **Gateway** | OpenClaw (self-hosted) | Multi-channel messaging, skill routing, agent invocation |
| **CDN/Edge** | Cloudflare Pages + Workers | Frontend hosting, API proxy, SSL, WAF, edge caching |
| **API** | Go (Chi router) | Auth proxy, file upload, job queue, sync engine, A2A gateway |
| **Agent Orchestration** | LangGraph 1.0 (Python) | 6-agent graph, state management, checkpointing, streaming |
| **AI/ML** | Gemini 2.5 Flash + local models | LLM reasoning, vision, voice processing |
| **Data** | Supabase (PostgreSQL + pgvector) | Database, auth, storage, realtime, vector search, memory |
| **Satellite** | Google Earth Engine | Sentinel-2 processing, NDVI, band ratios, alteration mapping |
| **Edge** | Jetson Orin Nano + Android phone | On-device inference, offline AI, voice processing |
| **Observability** | LangSmith + Sentry + Uptime Robot | Agent tracing, error tracking, uptime monitoring |

### 2.3 Voice Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     VOICE PIPELINE (Chained Architecture)                │
│                                                                         │
│  FIELD WORKER                                                           │
│  speaks Dholuo                                                          │
│       │                                                                 │
│       ▼                                                                 │
│  ┌──────────────┐                                                       │
│  │ STT Layer    │  Primary: Groq Whisper Large V3 (free, 20 RPM)       │
│  │              │  Offline: sherpa-onnx + Paza Dholuo model             │
│  └──────┬───────┘                                                       │
│         │ Dholuo text                                                   │
│         ▼                                                               │
│  ┌──────────────┐                                                       │
│  │ Translation  │  Gemini 2.5 Flash (Dholuo → English)                  │
│  │ (optional)   │  Offline: Gemma 4 E2B multilingual                    │
│  └──────┬───────┘                                                       │
│         │ English text                                                  │
│         ▼                                                               │
│  ┌──────────────┐                                                       │
│  │ LLM Reasoning│  Gemini 2.5 Flash (geological analysis)               │
│  │              │  Offline: Gemma 4 E2B / LFM2.5-1.2B                   │
│  └──────┬───────┘                                                       │
│         │ English response                                              │
│         ▼                                                               │
│  ┌──────────────┐                                                       │
│  │ Translation  │  Gemini 2.5 Flash (English → Dholuo)                  │
│  │ (optional)   │  Offline: Gemma 4 E2B multilingual                    │
│  └──────┬───────┘                                                       │
│         │ Dholuo text                                                   │
│         ▼                                                               │
│  ┌──────────────┐                                                       │
│  │ TTS Layer    │  Primary: Kokoro (82M params, on-device)              │
│  │              │  Enhanced: Fish Audio S2 (voice cloning)              │
│  │              │  Offline: Piper TTS                                    │
│  └──────┬───────┘                                                       │
│         │ Dholuo speech                                                 │
│         ▼                                                               │
│  FIELD WORKER                                                           │
│  hears response                                                         │
│                                                                         │
│  WAXAL Dataset: 11,000+ hours African speech (training data)            │
│  Paza Models: ASR for Swahili, Dholuo, Kalenjin, Kikuyu, Maasai, Somali│
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.4 Agent Pipeline Flow (LangGraph StateGraph)

```
                        ┌─────────┐
                        │  START  │
                        └────┬────┘
                             │
                        ┌────▼────┐
                        │SAMPLING │  Plans field routes, GPS waypoints
                        │ Agent   │  LLM: Gemini 2.5 Flash
                        └────┬────┘
                             │
                        ┌────▼────┐
                        │ANALYSIS │  Mineral classification from photos + XRF
                        │ Agent   │  LLM: Gemini 2.5 Flash (vision)
                        └────┬────┘
                             │
                   ┌─────────▼─────────┐
                   │  CONDITIONAL      │
                   │  ROUTER           │
                   │  (by mineral type)│
                   └──┬──────────┬─────┘
                      │          │
          ┌───────────▼──┐  ┌───▼───────────┐
          │   GEOLOGY    │  │    MARKET      │  ← PARALLEL FAN-OUT
          │   Agent      │  │    Agent       │
          │   LLM: Gemini│  │    LLM: None   │
          │   (RAG)      │  │    (API + calc)│
          └───────┬──────┘  └───────┬────────┘
                  │                  │
                  └────────┬─────────┘
                           │
                     ┌─────▼─────┐
                     │  MERGE    │  Barrier: waits for BOTH branches
                     │  Branches │  (prevents Report firing twice)
                     └─────┬─────┘
                           │
                     ┌─────▼─────┐
                     │  REPORT   │  Generates investor PDF
                     │  Agent    │  LLM: Gemini 2.5 Flash
                     └─────┬─────┘
                           │
                     ┌─────▼─────┐
                     │ needs     │──YES──┐
                     │ refine?   │       │
                     └─────┬─────┘       │
                           │ NO          │
                     ┌─────▼─────┐       │
                     │COMPLIANCE │       │
                     │ Agent     │       │
                     │ LLM: Gemini│      │
                     └─────┬─────┘       │
                           │             │
                     ┌─────▼─────┐       │
                     │ human     │──YES──┐│
                     │ review?   │       ││
                     └─────┬─────┘       ││
                           │ NO          ││
                      ┌────▼────┐        ││
                      │   END   │        ││
                      └─────────┘        ││
                                         ││
                           ┌─────────────┘│
                           │ REFINEMENT   │
                           │ LOOP (max 3) │
                           └──────────────┘
```

---

## 3. Agent Architecture

### 3.1 Agent Summary

| # | Agent | Role | Primary LLM | Parallel? | Checkpoint? |
|---|-------|------|-------------|-----------|-------------|
| 1 | Sampling | Field route planning | Gemini 2.5 Flash | No | Yes |
| 2 | Analysis | Mineral classification | Gemini 2.5 Flash (vision) | No | Yes |
| 3 | Geology | Geological interpretation | Gemini 2.5 Flash + RAG | **Yes** (with Market) | Yes |
| 4 | Market | Price data + valuation | None (API + calculation) | **Yes** (with Geology) | Yes |
| 5 | Report | Investor report generation | Gemini 2.5 Flash | No | Yes |
| 6 | Compliance | Regulatory validation | Gemini 2.5 Flash | No | Yes |

### 3.2 Sampling Agent

| Field | Value |
|-------|-------|
| **Role** | Plans field sampling routes and GPS waypoints for follow-up data collection |
| **Input** | `location` (GPS), `analysis_result` (from Analysis Agent), `satellite_imagery` |
| **Output** | `SamplingResult` — waypoints, field route, grid spacing, sampling strategy |
| **LLM** | Gemini 2.5 Flash (primary) |
| **Tools** | `satellite-mcp` (terrain analysis), `geology-mcp` (known deposits), GPS calculations |
| **Memory Access** | Reads: episodic (past sampling routes in region), semantic (geological knowledge) |
| **Security** | Scoped Supabase credentials (read: analysis_history, geological_knowledge; write: sampling_result) |
| **Error Handling** | Retry 3x with exponential backoff. If LLM fails, use cached sampling templates for region. |
| **MCP Servers** | `satellite-mcp`, `geology-mcp` |

### 3.3 Analysis Agent

| Field | Value |
|-------|-------|
| **Role** | Classifies minerals from photos + XRF data, estimates grades |
| **Input** | `sample_data` (photo URLs, XRF readings), `satellite_imagery` |
| **Output** | `AnalysisResult` — minerals, dominant mineral, confidence, rock type, alteration |
| **LLM** | Gemini 2.5 Flash with vision (primary), Groq Llama 4 Scout (speed fallback) |
| **Tools** | `mineral-classifier-mcp` (TFLite for pre-classification), `image-processor-mcp` |
| **Memory Access** | Reads: semantic (mineral patterns, deposit models), episodic (similar analyses) |
| **Security** | Scoped credentials (read: mineral_patterns, geological_knowledge; write: analysis_result) |
| **Error Handling** | Retry 3x. If vision fails, fall back to XRF-only analysis. If LLM fails, use TFLite on-device. |
| **MCP Servers** | `mineral-classifier-mcp`, `image-processor-mcp` |
| **Routing Output** | Sets `routing_decision` to `parallel_geo_market`, `market_only`, or `direct_report` |

### 3.4 Geology Agent

| Field | Value |
|-------|-------|
| **Role** | Interprets geological context — belt, formation, deposit model, pathfinder analysis |
| **Input** | `analysis_result`, `location`, `satellite_imagery` |
| **Output** | `GeologicalContext` — belt name, formation, deposit model, resource potential |
| **LLM** | Gemini 2.5 Flash (primary) with RAG from geological knowledge base |
| **Tools** | `geology-mcp` (knowledge retrieval), `satellite-mcp` (band ratios, alteration mapping), `geostats-mcp` (PyKrige/GSTools) |
| **Memory Access** | Reads: semantic (geological knowledge, deposit models), episodic (past geology interpretations). Writes: semantic (new geological observations) |
| **Security** | Scoped credentials (read: geological_knowledge, analysis_history; write: geology_result, geological_knowledge) |
| **Error Handling** | Retry 3x. If RAG fails, use cached geological models. If satellite fails, proceed with text-only analysis. |
| **MCP Servers** | `geology-mcp`, `satellite-mcp`, `geostats-mcp` |
| **Execution** | Runs in parallel with Market Agent |

### 3.5 Market Agent

| Field | Value |
|-------|-------|
| **Role** | Fetches commodity prices, calculates deposit value, determines cut-off grade |
| **Input** | `analysis_result` (mineral types, grades), `location` |
| **Output** | `MarketResult` — prices, deposit value, cut-off grade, trend, royalty |
| **LLM** | **None** — pure calculation (Python). No LLM needed for price lookups and math. |
| **Tools** | `market-mcp` (metals.live API, commodity feeds), `economics-mcp` (NPV, DCF calculations) |
| **Memory Access** | Reads: long-term (price history, calibration data), episodic (past valuations) |
| **Security** | Scoped credentials (read: agent_long_term_memory; write: market_result) |
| **Error Handling** | Retry 3x on API failure. If price API unavailable, use cached prices (max 24h old). |
| **MCP Servers** | `market-mcp`, `economics-mcp` |
| **Execution** | Runs in parallel with Geology Agent |

### 3.6 Report Agent

| Field | Value |
|-------|-------|
| **Role** | Generates investor-ready PDF reports, technical reports, regulatory filings |
| **Input** | `analysis_result`, `geology_result`, `market_result`, `compliance_result` |
| **Output** | `ReportResult` — HTML report, sections, executive summary, PDF URL |
| **LLM** | Gemini 2.5 Flash (primary), Claude Sonnet 5 (backup for complex reports) |
| **Tools** | `report-mcp` (PDF generation, template rendering), `storage-mcp` (Supabase upload) |
| **Memory Access** | Reads: episodic (past reports for style), procedural (learned report templates), semantic (geological knowledge for citations) |
| **Security** | Scoped credentials (read: all agent outputs, learned_workflows; write: report_result, Supabase storage) |
| **Error Handling** | Retry 3x. Set `needs_refinement=True` if quality below threshold (triggers refinement loop, max 3 iterations). |
| **MCP Servers** | `report-mcp`, `storage-mcp` |
| **Refinement Loop** | Can request re-analysis from Geology/Market agents (max 3 loops) |

### 3.7 Compliance Agent

| Field | Value |
|-------|-------|
| **Role** | Validates Kenya Mining Act 2016 requirements, license status, EIA, royalties |
| **Input** | `report_result`, `analysis_result`, `location`, `market_result` |
| **Output** | `ComplianceResult` — license type, EIA status, compliance issues, is_compliant |
| **LLM** | Gemini 2.5 Flash (primary) with DMN-style rule engine |
| **Tools** | `compliance-mcp` (Kenya Mining Act rules, license database), `regulatory-mcp` |
| **Memory Access** | Reads: semantic (regulatory rules), long-term (license status, compliance history) |
| **Security** | Scoped credentials (read: regulatory knowledge; write: compliance_result) |
| **Error Handling** | Retry 3x. If LLM fails, use rule engine fallback. Human-in-the-loop for blocking compliance issues. |
| **MCP Servers** | `compliance-mcp`, `regulatory-mcp` |
| **Human-in-the-Loop** | Flags blocking issues for geologist approval before finalizing |

---

## 4. Data Architecture

### 4.1 Database Schema (Supabase PostgreSQL)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SUPABASE PostgreSQL SCHEMA                              │
│                     Extensions: pgvector, pg_trgm                            │
│                     Free Tier: 500MB database, 1GB storage                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ CORE TABLES                                                         │   │
│  │                                                                      │   │
│  │  users (Supabase Auth managed)                                      │   │
│  │  ├── id UUID PK                                                     │   │
│  │  ├── email TEXT                                                     │   │
│  │  ├── phone TEXT                                                     │   │
│  │  ├── role ENUM('field_worker', 'geologist', 'investor', 'admin')   │   │
│  │  └── region TEXT                                                    │   │
│  │                                                                      │   │
│  │  mineral_samples                                                    │   │
│  │  ├── id UUID PK                                                    │   │
│  │  ├── user_id FK → users                                            │   │
│  │  ├── location JSONB {lat, lon, elevation, accuracy}                │   │
│  │  ├── photo_urls TEXT[]                                             │   │
│  │  ├── xrf_readings JSONB {element: ppm}                             │   │
│  │  ├── field_notes TEXT                                              │   │
│  │  ├── voice_note_url TEXT                                           │   │
│  │  ├── created_at TIMESTAMPTZ                                        │   │
│  │  └── synced BOOLEAN DEFAULT FALSE                                  │   │
│  │                                                                      │   │
│  │  analyses                                                           │   │
│  │  ├── id UUID PK (= analysis_id in AfriMineState)                   │   │
│  │  ├── user_id FK → users                                            │   │
│  │  ├── sample_ids UUID[] FK → mineral_samples                        │   │
│  │  ├── status ENUM('pending','running','completed','failed')         │   │
│  │  ├── agent_outputs JSONB (all 6 agent results)                     │   │
│  │  ├── detected_minerals TEXT[]                                      │   │
│  │  ├── estimated_grade NUMERIC                                       │   │
│  │  ├── confidence_score NUMERIC [0-1]                                │   │
│  │  ├── estimated_value_usd NUMERIC                                   │   │
│  │  ├── embedding vector(384)                                         │   │
│  │  ├── pipeline_duration_ms INTEGER                                  │   │
│  │  └── created_at TIMESTAMPTZ                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ MEMORY TABLES (5-Layer Architecture)                                │   │
│  │                                                                      │   │
│  │  agent_sessions (Layer 1: Short-term)                               │   │
│  │  ├── session_id TEXT PK                                             │   │
│  │  ├── pipeline_run_id TEXT                                          │   │
│  │  ├── user_id TEXT                                                  │   │
│  │  ├── status ENUM('active','paused','completed','failed','expired') │   │
│  │  ├── state JSONB (AfriMineState snapshot)                          │   │
│  │  ├── state_version INTEGER (optimistic concurrency)                │   │
│  │  ├── checkpoint_id TEXT                                            │   │
│  │  └── expires_at TIMESTAMPTZ (24h TTL)                              │   │
│  │                                                                      │   │
│  │  analysis_history (Layer 2: Episodic)                               │   │
│  │  ├── analysis_id TEXT PK                                           │   │
│  │  ├── location JSONB                                                │   │
│  │  ├── sampling/analysis/geology/market/report/compliance_output JSONB│  │
│  │  ├── embedding vector(384)                                         │   │
│  │  └── validation_status ENUM                                       │   │
│  │                                                                      │   │
│  │  geological_knowledge (Layer 3: Semantic)                           │   │
│  │  ├── knowledge_id TEXT PK                                          │   │
│  │  ├── category ENUM('deposit_model','pathfinder_element',...)       │   │
│  │  ├── content JSONB                                                 │   │
│  │  ├── related_minerals TEXT[]                                       │   │
│  │  ├── embedding vector(384)                                         │   │
│  │  └── usefulness_score NUMERIC                                      │   │
│  │                                                                      │   │
│  │  mineral_patterns (Layer 3b: Discovered Patterns)                   │   │
│  │  ├── pattern_id TEXT PK                                            │   │
│  │  ├── pattern_type ENUM('element_correlation','grade_distribution',.)│  │
│  │  ├── conditions JSONB                                              │   │
│  │  ├── confidence NUMERIC                                            │   │
│  │  └── applicable_regions TEXT[]                                     │   │
│  │                                                                      │   │
│  │  learned_workflows (Layer 4: Procedural)                            │   │
│  │  ├── workflow_id TEXT PK                                           │   │
│  │  ├── workflow_type ENUM('full_pipeline','analysis_template',...)   │   │
│  │  ├── graph_definition JSONB (LangGraph-compatible)                 │   │
│  │  ├── success_rate NUMERIC                                          │   │
│  │  └── applicable_minerals TEXT[]                                    │   │
│  │                                                                      │   │
│  │  agent_long_term_memory (Layer 5: Long-term)                        │   │
│  │  ├── namespace TEXT ('user:{id}', 'region:{name}', 'system')       │   │
│  │  ├── key TEXT                                                      │   │
│  │  ├── value JSONB                                                   │   │
│  │  └── UNIQUE(namespace, key)                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ LANGGRAPH TABLES                                                    │   │
│  │                                                                      │   │
│  │  checkpoints                                                        │   │
│  │  ├── (thread_id, checkpoint_ns, checkpoint_id) PK                  │   │
│  │  ├── checkpoint JSONB                                              │   │
│  │  └── parent_checkpoint TEXT                                        │   │
│  │                                                                      │   │
│  │  checkpoint_writes                                                  │   │
│  │  ├── (thread_id, checkpoint_ns, checkpoint_id, task_id, idx) PK    │   │
│  │  ├── channel TEXT                                                  │   │
│  │  └── value JSONB                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ SYNC TABLE                                                          │   │
│  │                                                                      │   │
│  │  sync_log                                                           │   │
│  │  ├── device_id TEXT                                                │   │
│  │  ├── entity_type ENUM('analysis','sample','knowledge')             │   │
│  │  ├── action ENUM('create','update','delete')                       │   │
│  │  ├── direction ENUM('upload','download')                           │   │
│  │  └── conflict BOOLEAN                                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Vector Store Design

| Store | Table | Dimension | Index | Use Case |
|-------|-------|-----------|-------|----------|
| Analysis embeddings | `analysis_history.embedding` | 384 | IVFFlat (lists=10) | "Find similar analyses" |
| Knowledge embeddings | `geological_knowledge.embedding` | 384 | IVFFlat (lists=10) | Semantic knowledge retrieval |
| Pattern embeddings | `mineral_patterns.embedding` | 384 | IVFFlat (lists=5) | Pattern similarity |

**Embedding Model:** `all-MiniLM-L6-v2` (384 dimensions, runs on CPU, free)

**When to upgrade indexes:**
- IVFFlat → HNSW when rows exceed 100K
- Add dedicated embedding service when query latency > 200ms

### 4.3 File Storage (Supabase Storage)

| Bucket | Content | Size Estimate | Retention |
|--------|---------|---------------|-----------|
| `sample-photos` | Mineral sample photos from field | ~500KB each | Permanent |
| `satellite-tiles` | Sentinel-2 GeoTIFF tiles | ~100MB each | 30 days |
| `reports` | Generated PDF reports | ~2MB each | Permanent |
| `voice-notes` | Field worker voice recordings | ~1MB each | 90 days |
| `model-weights` | TFLite models for offline use | ~50MB each | Current version |

### 4.4 Offline Sync Strategy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     OFFLINE SYNC ARCHITECTURE                            │
│                                                                         │
│  PHONE (SQLite)                         CLOUD (Supabase)                │
│  ┌──────────────────┐                  ┌──────────────────┐             │
│  │ Local Database    │                  │ PostgreSQL       │             │
│  │ • Samples         │◄──── Delta ────►│ • All data       │             │
│  │ • Photos          │      Sync        │ • AI results     │             │
│  │ • GPS points      │                  │ • Reports        │             │
│  │ • AI results      │                  │                  │             │
│  │ • Sync queue      │                  │                  │             │
│  │ • Knowledge cache │                  │                  │             │
│  └──────────────────┘                  └──────────────────┘             │
│                                                                         │
│  Sync Rules:                                                            │
│  1. Delta sync — only changed records (by updated_at timestamp)        │
│  2. Conflict detection: vector clocks (see §12)                        │
│  3. Conflict resolution: type-specific strategy                        │
│     - Geological data: manual merge (field worker UI)                  │
│     - Photos: keep both                                                │
│     - AI results: keep highest confidence                              │
│     - Notes: text diff merge                                           │
│  4. Retry: exponential backoff (1s, 2s, 4s, 8s, max 5min)             │
│  5. Dead letter queue: failed syncs after 10 retries                   │
│  6. Background sync: every 15 minutes when online                      │
│  7. Manual trigger: pull-to-refresh in Flutter app                     │
│                                                                         │
│  Offline Capability: 3+ days on phone storage                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.5 Data Sensitivity Classification

| Classification | Data | Storage | Access | Encryption |
|---------------|------|---------|--------|------------|
| **Critical** | GPS coordinates, mineral values, land ownership | Supabase (RLS) | User + service role only | AES-256 at rest, TLS in transit |
| **Sensitive** | XRF readings, geological reports, compliance data | Supabase (RLS) | User + agents (scoped) | AES-256 at rest, TLS in transit |
| **Internal** | Analysis history, patterns, workflows | Supabase (RLS) | Service role + read for agents | AES-256 at rest |
| **Public** | Geological knowledge base, deposit models | Supabase (RLS) | Public read, admin write | AES-256 at rest |

---

## 5. Integration Architecture

### 5.1 Go Backend ↔ LangGraph (A2A Protocol)

```
Go Backend (Chi Router)                 Python LangGraph
    │                                           │
    │  GET /.well-known/agent.json              │
    │  ─────────────────────────────────────────▶│  Agent Card Discovery
    │  ◀─────────────────────────────────────────│  (per-agent metadata)
    │                                           │
    │  POST /a2a/tasks/send                     │
    │  {                                        │
    │    "jsonrpc": "2.0",                      │
    │    "method": "tasks/send",                │
    │    "params": {                            │
    │      "id": "task-uuid",                   │
    │      "message": {                         │
    │        "role": "user",                    │
    │        "parts": [{                        │
    │          "type": "text",                  │
    │          "text": "Analyze sample..."      │
    │        }, {                               │
    │          "type": "file",                  │
    │          "mimeType": "image/jpeg",        │
    │          "data": "base64..."              │
    │        }]                                 │
    │      }                                    │
    │    }                                      │
    │  }                                        │
    │  ─────────────────────────────────────────▶│  Agent Pipeline Execution
    │                                           │
    │  SSE: task_status_update                  │
    │  ◀─────────────────────────────────────────│  Streaming Progress
    │  { "status": "working",                   │
    │    "agent": "analysis",                   │
    │    "progress": 0.4 }                      │
    │                                           │
    │  SSE: task_completed                      │
    │  ◀─────────────────────────────────────────│  Final Result
    │  { "status": "completed",                 │
    │    "result": { ... AfriMineState ... } }  │
```

**Agent Cards (per agent):**
```json
{
  "name": "afrimine-analysis-agent",
  "description": "Classifies minerals from photos and XRF data",
  "url": "http://localhost:8001/a2a",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": false
  },
  "skills": [
    {
      "id": "mineral-classification",
      "name": "Mineral Classification",
      "description": "Identifies minerals from rock sample photos"
    }
  ],
  "authentication": {
    "schemes": ["bearer"]
  }
}
```

### 5.2 Flutter App ↔ API Layer

```
Flutter App                      Go Backend (Chi Router)
    │                                    │
    │  POST /v1/auth/phone              │
    │  {phone: "+254..."}               │
    │  ─────────────────────────────────▶│  Supabase Auth (OTP)
    │  ◀─────────────────────────────────│  {session_token}
    │                                    │
    │  POST /v1/samples                  │
    │  {photo, gps, xrf, notes}         │
    │  ─────────────────────────────────▶│  Store in Supabase
    │  ◀─────────────────────────────────│  {sample_id}
    │                                    │
    │  POST /v1/analyses                 │
    │  {sample_ids: [...]}              │
    │  ─────────────────────────────────▶│  → A2A → LangGraph
    │                                    │
    │  GET /v1/analyses/{id}/stream     │
    │  ◀──── SSE ────────────────────────│  Streaming agent progress
    │                                    │
    │  GET /v1/analyses/{id}            │
    │  ─────────────────────────────────▶│  Final results + report URL
    │  ◀─────────────────────────────────│
    │                                    │
    │  POST /v1/sync                     │
    │  {delta: [...changes...]}          │
    │  ─────────────────────────────────▶│  Delta sync
    │  ◀─────────────────────────────────│  {conflicts: [], synced: n}
```

### 5.3 Satellite Integration (Google Earth Engine)

```
Analysis/Geology Agent
    │
    │  MCP: satellite-mcp
    │
    ▼
Google Earth Engine API (free)
    │
    ├── Sentinel-2 Surface Reflectance
    │   ├── Band 4 (Red) / Band 2 (Blue) → Alteration ratio
    │   ├── Band 11 (SWIR) / Band 12 (SWIR2) → Clay minerals
    │   ├── NDVI → Vegetation stress (indicator)
    │   └── Band composites → False color for visual inspection
    │
    ├── Digital Elevation Model (SRTM)
    │   ├── Slope → Access/safety assessment
    │   ├── Aspect → Weathering patterns
    │   └── Lineaments → Structural geology (Canny + Hough)
    │
    └── Output: GeoTIFF tiles → Supabase Storage
        Processing: NumPy + Rasterio (Python)
```

### 5.4 Market Data Feeds

| Source | Data | Frequency | Cost |
|--------|------|-----------|------|
| metals.live | Gold, copper, silver spot prices | Real-time | Free |
| Kitco | Precious metals | Daily | Free |
| LME | Base metals | Daily | Free |
| Supabase cache | Historical prices | Hourly update | Free |

### 5.5 SMS/Notification (Africa's Talking)

| Channel | Use Case | Volume | Cost |
|---------|----------|--------|------|
| SMS | OTP verification, analysis complete notification | ~1K/month | Free tier |
| Push | Real-time analysis progress, new reports | ~5K/month | Free (Firebase FCM) |
| WhatsApp | Report delivery, field Q&A | Unlimited | Free (OpenClaw) |

---

## 6. Deployment Architecture

### 6.1 Infrastructure Map

> **Deployment decision:** See [DEPLOYMENT_DECISION.md](./DEPLOYMENT_DECISION.md) for the full rationale.
> **TL;DR:** Cloudflare Pages + Workers (frontend + edge API) + Railway $5/mo (Python LangGraph).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     DEPLOYMENT ARCHITECTURE                                  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ CLOUDFLARE (Free Tier)                                              │   │
│  │                                                                      │   │
│  │  Pages: Flutter Web build (auto-deploy from GitHub main)            │   │
│  │  Workers: API proxy, rate limiting, CORS, edge caching              │   │
│  │  DNS: afrimine.com                                                  │   │
│  │  SSL: Automatic                                                     │   │
│  │  WAF: Bot protection                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ SUPABASE (Free Tier)                                                │   │
│  │                                                                      │   │
│  │  PostgreSQL: 500MB, pgvector, RLS, checkpoints                      │   │
│  │  Auth: Phone OTP, 50K MAU                                           │   │
│  │  Storage: 1GB, sample photos, reports, satellite tiles              │   │
│  │  Realtime: 200 concurrent connections                               │   │
│  │  Edge Functions: 500K invocations/month                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ GITHUB ACTIONS (Free for public repos)                              │   │
│  │                                                                      │   │
│  │  CI: Lint → Test → Build on every push                              │   │
│  │  CD: Auto-deploy Flutter Web to Cloudflare Pages                    │   │
│  │  CD: Auto-deploy Go backend (if using Cloudflare Workers)           │   │
│  │  Scheduled: Weekly dependency updates (Dependabot)                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ PYTHON LANGGRAPH SERVICE                                            │   │
│  │                                                                      │   │
│  │  Deployment: Railway ($5/mo) — see DEPLOYMENT_DECISION.md            │   │
│  │  Persistent process, no cold starts, GitHub auto-deploy              │   │
│  │  Checkpointer: Supabase PostgreSQL                                  │   │
│  │  Model: Gemini 2.5 Flash via Google AI Studio API                   │   │
│  │  Observability: LangSmith free tier (5K traces/month)               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ MONITORING (Free Tier)                                              │   │
│  │                                                                      │   │
│  │  Uptime Robot: 50 monitors, 5-min intervals                        │   │
│  │  Sentry: 5K errors/month, performance tracing                       │   │
│  │  LangSmith: 5K traces/month, agent execution visibility             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ EDGE (Physical Hardware)                                            │   │
│  │                                                                      │   │
│  │  NVIDIA Jetson Orin Nano (Field Kit)                                │   │
│  │  ├── Ubuntu 22.04, JetPack 7.2                                     │   │
│  │  ├── Ollama (Gemma 4 E2B quantized)                                │   │
│  │  ├── Kokoro TTS                                                    │   │
│  │  ├── LangGraph headless runtime                                     │   │
│  │  └── WiFi hotspot for phone connection                              │   │
│  │                                                                      │   │
│  │  Budget Android Phone (Worker Device)                               │   │
│  │  ├── Flutter app (APK sideloaded)                                   │   │
│  │  ├── TFLite mineral classifier                                      │   │
│  │  ├── sherpa-onnx STT (Paza Dholuo)                                 │   │
│  │  ├── SQLite offline cache                                           │   │
│  │  └── LFM2.5-1.2B (if 4GB+ RAM)                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 CI/CD Pipeline

```
Developer pushes to GitHub
    │
    ▼
GitHub Actions CI
    ├── Lint (Dart, Go, Python)
    ├── Unit Tests
    ├── Integration Tests
    └── Build
        ├── Flutter Web → Cloudflare Pages (auto-deploy)
        ├── Go binary → Cloudflare Workers / Railway
        └── Python → Railway / Fly.io
            │
            ▼
        Production
            ├── Health check (Uptime Robot)
            ├── Error tracking (Sentry)
            └── Agent tracing (LangSmith)
```

### 6.3 Environment Variables

| Variable | Service | Source |
|----------|---------|--------|
| `SUPABASE_URL` | All | Supabase Dashboard |
| `SUPABASE_ANON_KEY` | Flutter, Go | Supabase Dashboard |
| `SUPABASE_SERVICE_KEY` | Go, Python | Supabase Dashboard |
| `SUPABASE_DB_HOST` | Python (checkpointer) | Supabase → Settings → Database |
| `SUPABASE_DB_PASSWORD` | Python (checkpointer) | Supabase → Settings → Database |
| `GOOGLE_API_KEY` | Python (Gemini) | Google AI Studio |
| `GROQ_API_KEY` | Python (speed fallback) | Groq Console |
| `MISTRAL_API_KEY` | Python (backup) | Mistral Console |
| `LANGSMITH_API_KEY` | Python (observability) | LangSmith |
| `EARTH_ENGINE_KEY` | Python (satellite) | Google Earth Engine |
| `SENTRY_DSN` | All | Sentry |
| `CLOUDFLARE_API_TOKEN` | CI/CD | Cloudflare |

---

## 7. Security Architecture

### 7.1 Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     AUTHENTICATION FLOW                                   │
│                                                                         │
│  Field Worker                    Supabase Auth                          │
│  enters phone number             (Phone OTP)                            │
│       │                              │                                  │
│       │  POST /auth/phone            │                                  │
│       │  ────────────────────────────▶│                                 │
│       │                              │  Send OTP via Africa's Talking   │
│       │  ◀──── OTP sent ─────────────│                                 │
│       │                              │                                  │
│       │  enters OTP code             │                                  │
│       │  POST /auth/verify           │                                  │
│       │  ────────────────────────────▶│                                 │
│       │                              │  Verify OTP                      │
│       │  ◀──── JWT token ────────────│                                 │
│       │                              │                                  │
│       │  All subsequent requests:    │                                  │
│       │  Authorization: Bearer <JWT> │                                  │
│       │  ────────────────────────────▶│                                 │
│       │                              │  Verify JWT + RLS                │
│       │  ◀──── authorized ───────────│                                 │
│                                                                         │
│  Roles: field_worker, geologist, investor, admin                        │
│  MFA: Optional (for geologists and admins)                              │
│  Session: 24h expiry, refresh token rotation                            │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 Authorization (RBAC)

| Role | Can Do | Cannot Do |
|------|--------|-----------|
| **field_worker** | Create samples, trigger analyses, view own reports, use voice | View others' data, modify knowledge base, access admin |
| **geologist** | All field_worker actions + validate analyses, edit knowledge base, approve compliance | Access financial data, modify system config |
| **investor** | View reports, view analysis summaries, view market data | Create samples, trigger analyses, access raw data |
| **admin** | Full access, manage users, system config | — |

### 7.3 Agent Isolation Boundaries

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     AGENT ISOLATION MODEL                                │
│                                                                         │
│  Each of the 6 agents has:                                              │
│  1. Scoped Supabase credentials (not shared)                            │
│  2. Own MCP server connection                                           │
│  3. Own state key in AfriMineState (no write conflicts)                 │
│  4. Own rate limits (prevent runaway agents)                            │
│                                                                         │
│  Agent               Scoped Permissions                                 │
│  ────────────────    ─────────────────────────────────                  │
│  Sampling Agent      READ: analysis_history, geological_knowledge       │
│                      WRITE: state.sampling_result                       │
│                                                                         │
│  Analysis Agent      READ: mineral_patterns, geological_knowledge       │
│                      WRITE: state.analysis_result                       │
│                                                                         │
│  Geology Agent       READ: geological_knowledge, analysis_history       │
│                      WRITE: state.geology_result, geological_knowledge  │
│                                                                         │
│  Market Agent        READ: agent_long_term_memory                       │
│                      WRITE: state.market_result                         │
│                                                                         │
│  Report Agent        READ: all agent outputs, learned_workflows         │
│                      WRITE: state.report_result, Supabase storage       │
│                                                                         │
│  Compliance Agent    READ: geological_knowledge (regulatory rules)      │
│                      WRITE: state.compliance_result                     │
│                                                                         │
│  Blast Radius Containment:                                              │
│  - If Analysis Agent compromised → only analysis_result affected        │
│  - No agent can modify another agent's output                           │
│  - Report Agent reads others but cannot modify their outputs            │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.4 Data Protection

| Layer | Protection | Implementation |
|-------|-----------|----------------|
| **At rest** | AES-256 | Supabase default encryption, encrypted SQLite on phone |
| **In transit** | TLS 1.3 | Cloudflare SSL, HTTPS everywhere |
| **Database** | Row-Level Security | Supabase RLS policies per table |
| **API** | JWT verification | Every request verified, token rotation |
| **Agent credentials** | Scoped, isolated | Per-agent Supabase service keys |
| **Phone storage** | Encrypted SQLite | SQLCipher for offline cache |
| **Voice data** | Processed locally when possible | sherpa-onnx on-device STT |

### 7.5 Audit Logging

| Event | Logged To | Retention |
|-------|-----------|-----------|
| User login/logout | `auth.audit_log` (Supabase) | 90 days |
| Sample creation | `sync_log` + `mineral_samples.created_at` | Permanent |
| Analysis trigger | `agent_sessions` + LangSmith trace | Permanent |
| Agent execution | LangSmith traces (5K/month free) | 30 days |
| Report generation | `analysis_history` + Supabase storage | Permanent |
| Compliance check | `compliance_result` in analysis | Permanent |
| Data sync | `sync_log` | 90 days |
| Error/exception | Sentry | 30 days |

### 7.6 Kenya Mining Act 2016 Compliance

| Requirement | Implementation |
|-------------|----------------|
| **License tracking** | Compliance Agent checks license status against `geological_knowledge` (regulatory rules) |
| **EIA requirement** | Compliance Agent flags when Environmental Impact Assessment required |
| **Royalty calculation** | Market Agent calculates royalties per Kenya Mining Act rates |
| **Community agreement** | Compliance Agent flags when community agreement required |
| **Data retention** | Analysis records retained permanently per regulatory requirements |
| **Audit trail** | Full agent execution history in LangSmith + Supabase |

---

## 8. Migration Roadmap

### 8.1 Phase Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     MIGRATION ROADMAP                                        │
│                                                                             │
│  PHASE 0: FOUNDATION (Week 1-2)                    [CURRENT]               │
│  ├── LangGraph installation + state schema                                  │
│  ├── Supabase checkpointer setup                                            │
│  ├── Memory schema deployment                                               │
│  ├── Port Sampling Agent (first validation)                                 │
│  └── CI/CD pipeline update                                                  │
│                                                                             │
│  PHASE 1: AGENT MIGRATION (Week 3-4)                                       │
│  ├── Port Analysis Agent (Gemini vision)                                    │
│  ├── Port Geology Agent (RAG + knowledge base)                             │
│  ├── Port Market Agent (API + calculations)                                │
│  ├── Port Report Agent (PDF generation)                                    │
│  ├── Port Compliance Agent (rule engine)                                    │
│  └── Conditional routing (mineral type → analysis path)                    │
│                                                                             │
│  PHASE 2: ADVANCED PATTERNS (Week 5-6)                                     │
│  ├── Parallel fan-out (Geology ∥ Market)                                   │
│  ├── Iterative refinement loops (Report → re-analysis)                     │
│  ├── Human-in-the-loop (Compliance approvals)                              │
│  ├── MCP server exposure for all tools                                      │
│  └── A2A protocol bridge (Go ↔ Python)                                    │
│                                                                             │
│  PHASE 3: VOICE + OPENCLAW (Week 7-8)                                      │
│  ├── sherpa-onnx integration (offline STT)                                 │
│  ├── Paza model deployment (Dholuo/Swahili)                                │
│  ├── Kokoro TTS integration                                                │
│  ├── OpenClaw gateway setup (WhatsApp/Telegram)                            │
│  └── Voice pipeline end-to-end testing                                      │
│                                                                             │
│  PHASE 4: MEMORY + OFFLINE (Week 9-10)                                     │
│  ├── 5-layer memory deployment                                             │
│  ├── Vector embeddings (pgvector)                                           │
│  ├── Flutter offline sync                                                   │
│  ├── TFLite model deployment                                               │
│  └── End-to-end pipeline testing                                            │
│                                                                             │
│  PHASE 5: PRODUCTION HARDENING (Week 11-12)                                │
│  ├── LangSmith observability                                                │
│  ├── Error recovery + retry logic                                           │
│  ├── Security audit (VulnHunter)                                            │
│  ├── Load testing                                                           │
│  ├── Documentation + runbooks                                               │
│  └── Pilot deployment in Nyatike                                            │
│                                                                             │
│  PHASE 6: QUANTUM + SCALE (Month 4-6)                                      │
│  ├── IBM Quantum integration (pit optimization)                             │
│  ├── D-Wave Advantage2 (logistics)                                          │
│  ├── Jetson Orin Nano field kit deployment                                  │
│  ├── Tanzania/Ghana regulatory modules                                      │
│  └── Federated learning across mine sites                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Phase Dependencies

```
Phase 0 (Foundation)
    │
    ├──→ Phase 1 (Agent Migration)
    │        │
    │        ├──→ Phase 2 (Advanced Patterns)
    │        │        │
    │        │        └──→ Phase 5 (Production Hardening)
    │        │
    │        └──→ Phase 3 (Voice + OpenClaw) [can parallel with Phase 2]
    │
    └──→ Phase 4 (Memory + Offline) [can start after Phase 0]
             │
             └──→ Phase 5 (Production Hardening)
                      │
                      └──→ Phase 6 (Quantum + Scale)
```

### 8.3 Risk Mitigation per Phase

| Phase | Key Risk | Mitigation | Rollback |
|-------|----------|------------|----------|
| **0** | State schema doesn't match agent needs | Start with simplest agent (Sampling), iterate | Revert to CrewAI (both systems run in parallel) |
| **1** | Agent output quality degrades in LangGraph | Shadow-test against CrewAI outputs | Route single agent back to CrewAI |
| **2** | Parallel execution introduces race conditions | Optimistic concurrency via version columns | Fall back to sequential execution |
| **3** | Voice accuracy insufficient for Dholuo | Use English fallback, improve models iteratively | Text-only mode |
| **4** | Memory schema too large for free tier | Monitor with `get_memory_stats()`, prune old data | Reduce to 3-layer memory |
| **5** | Production issues in Nyatike | Gradual rollout, feature flags | Disable new features, revert to Phase 1 pipeline |
| **6** | Quantum hardware unavailable/errors | Classical fallback for all optimization | Remove quantum, keep classical |

### 8.4 Parallel Operation Strategy

During migration (Phase 0-2), both CrewAI and LangGraph systems run simultaneously:

```
Request → Go Backend
    │
    ├──→ CrewAI Pipeline (existing, stable)
    │        │
    │        └──→ Result A
    │
    └──→ LangGraph Pipeline (new, shadow mode)
             │
             └──→ Result B
    │
    ▼
Comparator: Compare Result A vs Result B
    │
    ├── Match → Log, increase LangGraph confidence
    └── Mismatch → Flag for review, keep CrewAI result
```

---

## 9. Cost Model

### 9.1 Monthly Breakdown — $0/month

| Service | Tier | Free Limit | Estimated Usage | Cost |
|---------|------|------------|-----------------|------|
| **Gemini 2.5 Flash** | Free (AI Studio) | 1,500 req/day | ~500 req/day | $0 |
| **Mistral AI** | Free | 1B tokens/month | ~100M tokens | $0 |
| **Groq** | Free | 1K RPD (Llama), 2K RPD (Whisper) | ~200 RPD | $0 |
| **Supabase** | Free | 500MB DB, 1GB storage, 50K MAU | ~200MB, ~500MB, ~1K MAU | $0 |
| **Cloudflare Pages** | Free | Unlimited bandwidth | ~10GB/month | $0 |
| **Cloudflare Workers** | Free | 100K req/day | ~10K req/day | $0 |
| **GitHub Actions** | Free (public) | 2,000 min/month | ~200 min/month | $0 |
| **LangSmith** | Free | 5K traces/month | ~2K traces | $0 |
| **Uptime Robot** | Free | 50 monitors | ~5 monitors | $0 |
| **Sentry** | Free | 5K errors/month | ~500 errors | $0 |
| **Google Earth Engine** | Free | Unlimited (non-commercial) | ~100 tiles/month | $0 |
| **Kaggle Notebooks** | Free | 30hrs/week GPU | ~10hrs/week | $0 |
| **IBM Quantum** | Open Plan | Limited QPU minutes | ~30 min/month | $0 |
| **D-Wave Leap** | Free | Monthly QPU minutes | ~10 min/month | $0 |
| **Africa's Talking** | Free trial | 10K SMS | ~1K SMS | $0 |
| **Firebase FCM** | Free | Unlimited push | ~5K push | $0 |
| **TOTAL** | | | | **$0** |

### 9.2 Free Tier Overflow Strategy

| Service | When Limit Hit | Overflow Strategy |
|---------|---------------|-------------------|
| Gemini 2.5 Flash | >1,500 req/day | Route to Mistral (1B tokens/month) |
| Mistral | >1B tokens/month | Route to Groq Llama 4 Scout |
| Groq | >1K RPD | Route to Groq Qwen3-32B (different model, separate limit) |
| Supabase DB | >500MB | Archive old sessions, compress embeddings |
| Supabase Storage | >1GB | Compress images, delete satellite tiles >30 days |
| LangSmith | >5K traces | Sample 50% of traces, keep errors only |
| Sentry | >5K errors | Filter low-severity errors |

### 9.3 Scaling Cost Projections

| Stage | Users | Analysis/Day | Monthly Cost | Notes |
|-------|-------|-------------|-------------|-------|
| **MVP** (Month 1-4) | <100 | <50 | **$0** | All free tiers |
| **Early Growth** (Month 5-8) | 100-1K | 50-500 | **$0-25** | May need Supabase Pro ($25) for DB |
| **Growth** (Month 9-12) | 1K-10K | 500-5K | **$25-100** | Supabase Pro + Gemini paid tier |
| **Scale** (Year 2+) | 10K+ | 5K+ | **$100-500** | Supabase Team + dedicated compute |

**Key insight:** The architecture is designed to stay at $0 for at least 4 months of active development and initial deployment. Scaling costs only kick in with real user growth.

> **⚠️ Important:** The $0/month claim is valid for MVP only. See [COST_MODEL_REAL.md](./COST_MODEL_REAL.md) for honest cost projections including hardware costs, agent multiplication factor, and production-scale pricing.

---

## 11. Horizontal Scaling Strategy

### 11.1 Stateless Agent Design

All LangGraph agent nodes are **stateless functions** — they receive state as input and return partial state as output. No agent holds in-memory state between invocations. This enables horizontal scaling:

```
┌─────────────────────────────────────────────────────────────┐
│                  HORIZONTAL SCALING MODEL                    │
│                                                              │
│  Load Balancer (Cloudflare Workers)                         │
│       │                                                      │
│       ├──→ LangGraph Instance 1 (Railway)                   │
│       │       └── Sampling → Analysis → Geology/Market       │
│       │              → Merge → Report → Compliance           │
│       │                                                      │
│       ├──→ LangGraph Instance 2 (Railway)                   │
│       │       └── Sampling → Analysis → Geology/Market       │
│       │              → Merge → Report → Compliance           │
│       │                                                      │
│       └──→ LangGraph Instance N (Railway)                   │
│               └── ...                                        │
│                                                              │n│  Shared State: Supabase PostgreSQL (checkpoints + memory)   │n│  No in-process state — all state in database                │n└─────────────────────────────────────────────────────────────┘
```

**Key properties:**
- Each analysis is a single `graph.ainvoke()` call with its own `thread_id`
- State is checkpointed to Supabase after every node boundary
- Any instance can resume any analysis from its last checkpoint
- No sticky sessions required — any instance handles any request

### 11.2 Supabase Connection Pooling

At scale, each LangGraph instance maintains a connection pool to Supabase:

```python
# Connection pool configuration
SUPABASE_POOL_CONFIG = {
    "min_connections": 2,       # Keep alive for low-traffic periods
    "max_connections": 10,      # Per instance (Supabase free: 60 concurrent)
    "connection_timeout": 30,   # Seconds to wait for available connection
    "idle_timeout": 300,        # Close idle connections after 5 min
}
```

**Scaling limits:**
- Supabase Free: 60 concurrent connections → 6 instances × 10 pool
- Supabase Pro: 200 concurrent connections → 20 instances × 10 pool
- Supabase Team: 400 concurrent connections → 40 instances × 10 pool

### 11.3 LLM Rate Limit Handling with Queuing

When Gemini rate limits are hit, requests queue for retry:

```python
# LLM call queue with exponential backoff
import asyncio
from collections import deque

class LLMQueue:
    """Queue LLM calls to handle rate limits gracefully."""

    def __init__(self, max_concurrent: int = 5):
        self._queue = deque()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._retry_after: float = 0

    async def call(self, llm_func, *args, **kwargs):
        """Queue an LLM call with retry on rate limit."""
        async with self._semaphore:
            for attempt in range(3):
                try:
                    return await llm_func(*args, **kwargs)
                except RateLimitError as e:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(f"Rate limited, waiting {wait}s (attempt {attempt+1})")
                    await asyncio.sleep(wait)

            # All retries exhausted — fall back to next model in chain
            return await self._fallback_call(*args, **kwargs)

    async def _fallback_call(self, *args, **kwargs):
        """Try fallback LLM (Mistral → Groq → Local)."""
        for model in ["mistral", "groq-llama", "groq-qwen", "local-gemma"]:
            try:
                return await call_model(model, *args, **kwargs)
            except Exception:
                continue
        raise RuntimeError("All LLM models exhausted")
```

### 11.4 Scaling Tiers

| Tier | Instances | Concurrent Analyses | LLM Strategy | Cost |
|------|----------|--------------------|--------------|----|
| **MVP** | 1 | 1-2 | Gemini free tier | $0 |
| **Growth** | 1-2 | 5-10 | Gemini free + Mistral fallback | $5-25 |
| **Scale** | 2-5 | 10-50 | Gemini paid + queue | $50-200 |
| **Enterprise** | 5-20 | 50-200 | Multi-model + caching | $200-2000 |

---

## 12. Offline Sync Conflict Resolution

### 12.1 Problem with Last-Write-Wins

The original design used "last-write-wins + audit log" for conflict resolution. This is **dangerous for geological data:**

- Two field workers analyze the same sample offline → one analysis silently overwrites the other
- Geological data has real financial implications (landowner negotiations, royalty calculations)
- Lost data means lost mineral discoveries

### 12.2 Vector Clock Conflict Detection

Replace last-write-wins with **vector clocks** for conflict detection:

```python
# sync/conflict_resolution.py
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class VectorClock:
    """Vector clock for distributed conflict detection."""
    clocks: Dict[str, int] = field(default_factory=dict)  # {device_id: counter}

    def increment(self, device_id: str):
        """Increment this device's clock on every write."""
        self.clocks[device_id] = self.clocks.get(device_id, 0) + 1

    def merge(self, other: 'VectorClock'):
        """Merge with another vector clock (take max of each)."""
        for device_id, counter in other.clocks.items():
            self.clocks[device_id] = max(self.clocks.get(device_id, 0), counter)

    def compare(self, other: 'VectorClock') -> str:
        """
        Compare two vector clocks.
        Returns: 'before', 'after', 'concurrent', or 'equal'
        """
        all_devices = set(self.clocks.keys()) | set(other.clocks.keys())
        self_greater = False
        other_greater = False

        for d in all_devices:
            s = self.clocks.get(d, 0)
            o = other.clocks.get(d, 0)
            if s > o:
                self_greater = True
            elif o > s:
                other_greater = True

        if self_greater and not other_greater:
            return "after"   # self supersedes other
        elif other_greater and not self_greater:
            return "before"  # other supersedes self
        elif not self_greater and not other_greater:
            return "equal"   # identical
        else:
            return "concurrent"  # CONFLICT — both modified independently
```

### 12.3 Conflict Resolution by Data Type

| Data Type | Conflict Strategy | Rationale |
|-----------|------------------|----------|
| **Geological analyses** | Manual merge | Two expert opinions may both be valid |
| **Sample photos** | Keep both | Photos don't conflict — add to collection |
| **XRF readings** | Latest wins + flag | Same sample, same device → latest is calibration |
| **Field notes** | Text merge (diff) | Append both, show diff to user |
| **GPS waypoints** | Keep both | Different routes may both be valid |
| **AI results** | Keep highest confidence | AI output can be compared objectively |
| **Report drafts** | Manual merge | Reports are documents — need human review |

### 12.4 Conflict Resolution UI for Field Workers

```
┌─────────────────────────────────────────────┐
│  ⚠️ SYNC CONFLICT DETECTED                   │
│                                              │
│  Sample: NYA-2026-042                        │
│  Conflict: Two analyses exist for this sample│
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ Analysis A (Kamau's phone)             │  │
│  │ • Gold: 5.2 ppm                        │  │
│  │ • Confidence: 85%                      │  │
│  │ • Time: Jul 18, 10:30 AM              │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ Analysis B (Wanjiku's phone)           │  │
│  │ • Gold: 4.8 ppm                        │  │
│  │ • Confidence: 78%                      │  │
│  │ • Time: Jul 18, 11:15 AM              │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  [Keep A]  [Keep B]  [Keep Both]  [Merge]   │
└─────────────────────────────────────────────┘
```

### 12.5 Sync Schema Update

```sql
-- Add vector clock to sync_log
ALTER TABLE sync_log ADD COLUMN vector_clock JSONB DEFAULT '{}';
ALTER TABLE sync_log ADD COLUMN conflict_details JSONB;
ALTER TABLE sync_log ADD COLUMN resolution_method TEXT
    CHECK (resolution_method IN ('auto_latest', 'auto_highest_confidence',
                                   'manual_keep_a', 'manual_keep_b',
                                   'manual_merge', 'manual_keep_both'));

-- Add vector clock to synced tables
ALTER TABLE mineral_samples ADD COLUMN vector_clock JSONB DEFAULT '{}';
ALTER TABLE analysis_history ADD COLUMN vector_clock JSONB DEFAULT '{}';
```

---

## 10. Technology Radar

### 10.1 ADOPT — Use Now

| Technology | Why | Status |
|-----------|-----|--------|
| **LangGraph 1.0** | Production-proven graph-based agent orchestration | ✅ Replacing CrewAI |
| **Gemini 2.5 Flash** | Free, vision-capable, primary LLM | ✅ In production |
| **Supabase** | Free PostgreSQL + Auth + Storage + pgvector | ✅ In production |
| **Flutter** | One codebase for Android/iOS/Web | ✅ In production |
| **Go (Chi)** | Single binary, edge-deployable backend | ✅ In production |
| **Cloudflare Pages + Workers** | Free hosting, Africa edge CDN | ✅ In production |
| **sherpa-onnx** | Offline STT for Flutter, supports Paza models | ✅ Integrating |
| **A2A Protocol** | Go ↔ Python agent communication | ✅ Implementing |
| **MCP** | Standardized tool interfaces for agents | ✅ Implementing |
| **pgvector** | Vector embeddings in Supabase (zero extra cost) | ✅ Deploying |
| **Groq** | Speed layer for voice (500+ tok/s, free) | ✅ In stack |

### 10.2 TRIAL — Pilot This Quarter

| Technology | Why | Risk |
|-----------|-----|------|
| **Microsoft Paza** | ASR for Dholuo/Swahili — our target languages | New (Feb 2026), limited benchmarks |
| **Google WAXAL** | 11K hours African speech training data | Large dataset, training effort needed |
| **Kokoro TTS** | 82M params, on-device TTS for spoken reports | Limited African language support |
| **Gemma 4 E2B** | On-device multimodal, 5GB RAM, Apache 2.0 | New (Apr 2026), limited geological benchmarks |
| **LFM2.5-1.2B** | On-device reasoning under 1GB | New (Jan 2026), limited domain testing |
| **OpenClaw** | Multi-channel gateway for field workers | Self-hosting required |
| **VoicERA** | Open-source voice AI stack for agriculture in Africa | India-focused, may need adaptation |
| **Fish Audio S2** | Voice cloning for community-trusted reports | Ethical considerations for voice cloning |
| **Kimi K3** | Open-weight frontier model, potential Gemini replacement | API pricing TBD |

### 10.3 ASSESS — Evaluate This Quarter

| Technology | Why | When to Adopt |
|-----------|-----|---------------|
| **GPT-5.6 Luna** | Cost-efficient reasoning, potential primary LLM | If free tier offered |
| **GPT-Live** | Full-duplex voice UX | When API available and affordable |
| **NVIDIA Jetson T2000** | Edge upgrade for field kits | When pricing available |
| **Qwen3-32B** | Open-weight reasoning on Groq free tier | After benchmarking geological tasks |
| **Claude Agent SDK** | Alternative to LangGraph if Anthropic offers better free tier | If LangGraph limitations emerge |
| **Ollama + Open WebUI** | Fully offline AI stack on Jetson | After Jetson deployment |
| **ESA Quantum Earth Observation** | Quantum-enhanced land classification | When code published |
| **Z.ai GLM 5.2** | Open-weight coding model | After benchmarking |
| **IRH Technology** | Competitor/partner for satellite mineral exploration | Partnership evaluation |

### 10.4 HOLD — Avoid for Now

| Technology | Why Not |
|-----------|---------|
| **OpenAI Realtime API** | Not free, black-box architecture |
| **AssemblyAI Voice Agent API** | Not free for African languages |
| **AWS Nova Sonic** | AWS dependency, not free |
| **Pinecone** | Paid vector DB, pgvector covers our needs |
| **Redis** | Extra infrastructure, Supabase covers session state |
| **Microsoft Agent Framework** | Azure-tethered, wrong ecosystem |
| **Pydantic AI V2** | No multi-agent orchestration |
| **Qiskit Code Assistant** | Discontinued (May 2026) |
| **Custom frontend for messaging** | OpenClaw eliminates this need |
| **Post-quantum cryptography** | Not urgent — monitor Supabase/Cloudflare adoption |

---

## Appendix A: File Inventory

### Action Swarm Deliverables

| File | Location | Purpose |
|------|----------|---------|
| `state_schema.py` | `langgraph-migration/` | AfriMineState TypedDict with all agent output schemas |
| `checkpointer.py` | `langgraph-migration/` | Supabase PostgreSQL checkpointer setup |
| `requirements.txt` | `langgraph-migration/` | Python dependencies for LangGraph |
| `agents/sampling_agent.py` | `langgraph-migration/agents/` | Sampling Agent implementation |
| `agents/analysis_agent.py` | `langgraph-migration/agents/` | Analysis Agent implementation |
| `agents/geology_agent.py` | `langgraph-migration/agents/` | Geology Agent implementation |
| `agents/market_agent.py` | `langgraph-migration/agents/` | Market Agent implementation |
| `agents/report_agent.py` | `langgraph-migration/agents/` | Report Agent implementation |
| `agents/compliance_agent.py` | `langgraph-migration/agents/` | Compliance Agent implementation |
| `memory_schema.sql` | `memory-system/` | Complete Supabase SQL schema (all 5 layers) |
| `memory_manager.py` | `memory-system/` | Unified memory manager class |
| `supabase_checkpointer.py` | `memory-system/` | LangGraph checkpointer with Supabase |
| `vector_store.py` | `memory-system/` | Geological vector embeddings store |
| `README.md` | `memory-system/` | Memory architecture documentation |

### Research Documents

| Document | Location | Key Finding |
|----------|----------|-------------|
| Voice & On-Device AI | `ai-week-research/01-*.md` | Paza (Dholuo ASR), WAXAL (speech data), sherpa-onnx |
| Voice & Reasoning LLMs | `ai-week-research/02-*.md` | GPT-5.6 Luna, GPT-Live, Gemini free tier confirmed |
| Multi-Agent Systems | `ai-week-research/03-*.md` | CrewAI v1.15.2, LangGraph 1.0, MCP+A2A universal |
| Quantum Computing | `ai-week-research/04-*.md` | ESA quantum, D-Wave Advantage2, QAOA improvements |
| AGI & Emerging | `ai-week-research/05-*.md` | Kimi K3, agent security crisis, Intuit lessons |
| OpenClaw & Open Source | `ai-week-research/06-*.md` | OpenClaw foundation, GEOAssist, mineral datasets |
| Framework Replacement | `ai-week-research/07-*.md` | LangGraph 1.0 decision, 10-week migration plan |

---

## Appendix B: Key Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Agent handoff latency | <2s per handoff | LangSmith traces |
| End-to-end pipeline latency | <60s for full analysis | Application logs |
| Pipeline success rate | >95% completion | LangSmith + Supabase |
| Checkpoint resume success | >99% | Automated tests |
| Mineral classification accuracy | >75% (MVP), >85% (Production) | Evaluation harness |
| Voice transcription accuracy | >80% Dholuo, >90% Swahili | Paza benchmarks |
| Offline availability | >99% uptime | Health checks |
| Cost per analysis | $0 | Billing monitoring |
| User-facing latency (voice) | <3s response time | End-to-end measurement |
| Memory retrieval time | <500ms for pgvector queries | Database benchmarks |
| Free tier utilization | <80% of any limit | Monitoring dashboards |

---

## Appendix C: Glossary

| Term | Definition |
|------|-----------|
| **A2A** | Agent-to-Agent Protocol — Google's standard for inter-agent communication |
| **ASM** | Artisanal and Small-scale Mining |
| **CrewAI** | Multi-agent framework (being replaced by LangGraph) |
| **Dholuo** | Primary language in Nyatike, Migori County, Kenya |
| **EIA** | Environmental Impact Assessment |
| **GEE** | Google Earth Engine |
| **LangGraph** | LangChain's graph-based agent orchestration framework |
| **MCP** | Model Context Protocol — standardized tool interfaces |
| **OpenClaw** | Open-source multi-channel AI agent gateway |
| **Paza** | Microsoft's ASR models for 6 Kenyan languages |
| **QUBO** | Quadratic Unconstrained Binary Optimization (quantum formulation) |
| **RLS** | Row-Level Security (Supabase/PostgreSQL) |
| **Sentinel-2** | ESA's Earth observation satellite (free data) |
| **sherpa-onnx** | Offline speech recognition for mobile/edge |
| **TFLite** | TensorFlow Lite (on-device ML inference) |
| **WAXAL** | Google's open speech dataset for 21 African languages |

---

**Document Status:** AUTHORITATIVE
**Next Review:** August 19, 2026
**Owner:** Valentine (AfriMine AI)
**Contributors:** Architecture Research Agent, Voice Research Swarm, Multi-Agent Research Swarm, Quantum Research Swarm, OpenClaw Research Swarm, LangGraph Migration Swarm, Memory System Swarm

---

*This document is the single source of truth for AfriMine AI's architecture. All engineering decisions should reference this document. When in doubt, check the ADRs.*
