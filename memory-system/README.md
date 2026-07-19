# AfriMine AI — Layered Memory Architecture

## Overview

The memory system is the critical foundation for AfriMine AI's 6-agent mineral detection pipeline. It provides persistent, searchable, and consolidating memory across all agents, enabling the system to learn from past analyses, retrieve similar geological contexts, and maintain state across sessions.

**Cost: $0** (Supabase free tier + open-source libraries)

---

## Memory Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LAYERED MEMORY ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ LAYER 1: SHORT-TERM MEMORY (Session State)                   │   │
│  │ • LangGraph checkpointer (Supabase)                          │   │
│  │ • Agent conversation context                                  │   │
│  │ • Current analysis pipeline state                             │   │
│  │ • TTL: Session lifetime (auto-cleanup after 24h)              │   │
│  │ • Storage: Supabase table `agent_sessions`                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                    [consolidation]                                   │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ LAYER 2: EPISODIC MEMORY (Analysis History)                  │   │
│  │ • Records of every completed mineral analysis                 │   │
│  │ • Input parameters, agent outputs, final report               │   │
│  │ • Enables "find similar analyses" queries                     │   │
│  │ • Storage: Supabase table `analysis_history`                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                    [embedding + indexing]                             │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ LAYER 3: SEMANTIC MEMORY (Knowledge & Embeddings)            │   │
│  │ • Geological knowledge base (deposit models, pathfinders)     │   │
│  │ • Vector embeddings for similarity search                     │   │
│  │ • Mineral pattern discovery across analyses                   │   │
│  │ • Storage: Supabase tables `geological_knowledge`,            │   │
│  │           `mineral_patterns` + pgvector                       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                    [pattern extraction]                               │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ LAYER 4: PROCEDURAL MEMORY (Learned Workflows)               │   │
│  │ • Successful analysis workflows (agent step sequences)        │   │
│  │ • Decision trees that led to accurate results                 │   │
│  │ • Error recovery patterns                                     │   │
│  │ • Storage: Supabase table `learned_workflows`                 │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ LAYER 5: LONG-TERM MEMORY (Persistent Facts)                 │   │
│  │ • User preferences, geological region facts                   │   │
│  │ • Calibration data, model performance history                 │   │
│  │ • Cross-session agent learnings                               │   │
│  │ • Storage: Supabase table `agent_long_term_memory`            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Flutter App (Offline-First)                   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  Local SQLite Cache                           │   │
│  │  • Cached analyses (last 50)                                  │   │
│  │  • Cached knowledge snippets                                  │   │
│  │  • Pending sync queue                                         │   │
│  │  • Offline vector search (HNSW-lite)                          │   │
│  └────────────────────────────┬─────────────────────────────────┘   │
└───────────────────────────────┼──────────────────────────────────────┘
                                │ Delta Sync (when online)
┌───────────────────────────────▼──────────────────────────────────────┐
│                    Go Backend (API Layer)                             │
│  /v1/memory/* endpoints · Sync conflict resolution                  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│                 Python Memory Manager                                 │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────┐ ┌────────────┐ │
│  │ Supabase    │ │ Vector       │ │ Episodic      │ │ Knowledge  │ │
│  │ Checkpointer│ │ Store        │ │ Memory        │ │ Graph      │ │
│  │ (short-term)│ │ (semantic)   │ │ (history)     │ │ (semantic) │ │
│  └──────┬──────┘ └──────┬───────┘ └───────┬───────┘ └─────┬──────┘ │
│         │               │                 │               │         │
│  ┌──────▼───────────────▼─────────────────▼───────────────▼──────┐  │
│  │              Memory Consolidation Engine                       │  │
│  │  • Short-term → Episodic (after analysis completes)           │  │
│  │  • Episodic → Semantic (batch, nightly)                       │  │
│  │  • Pattern discovery (weekly)                                 │  │
│  │  • Workflow learning (after successful analyses)              │  │
│  └───────────────────────────────────────────────────────────────┘  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│                    Supabase (PostgreSQL + pgvector)                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ │
│  │agent_sessions│ │analysis_     │ │geological_   │ │learned_    │ │
│  │(short-term)  │ │history       │ │knowledge     │ │workflows   │ │
│  │              │ │(episodic)    │ │(semantic)    │ │(procedural)│ │
│  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │
│  │mineral_      │ │agent_long_   │ │checkpoints   │                │
│  │patterns      │ │term_memory   │ │(LangGraph)   │                │
│  └──────────────┘ └──────────────┘ └──────────────┘                │
│                                                                      │
│  Extensions: pgvector · pg_trgm · PostGIS (optional)                │
│  Free Tier: 500MB database · 1GB storage                            │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Files

| File | Purpose |
|------|---------|
| `README.md` | This file — architecture overview |
| `requirements.txt` | Python dependencies |
| `memory_schema.sql` | Complete Supabase SQL schema |
| `memory_manager.py` | Unified memory manager class |
| `supabase_checkpointer.py` | LangGraph checkpointer with Supabase |
| `vector_store.py` | Geological vector embeddings store |
| `episodic_memory.py` | Past analysis retrieval |
| `knowledge_graph.py` | Geological knowledge graph |
| `memory_consolidation.py` | Background consolidation jobs |
| `flutter_memory_cache.dart` | Offline memory cache for Flutter |
| `migrations/` | SQL migration files |

---

## Supabase Free Tier Budget

| Resource | Budget | Usage Estimate |
|----------|--------|----------------|
| Database | 500 MB | ~200 MB (schemas + data) |
| Storage | 1 GB | ~500 MB (satellite images) |
| Auth | 50K MAU | MVP: <1K users |
| Edge Functions | 500K invocations | ~50K/month |
| Realtime | 200 concurrent | <50 concurrent |
| Bandwidth | 5 GB | ~2 GB/month |

---

## Agent Concurrency Model

All 6 agents share the same Supabase database. Concurrency is managed via:

1. **Row-level locking** — `SELECT ... FOR UPDATE` on active sessions
2. **Optimistic concurrency** — version columns with `UPDATE ... WHERE version = $1`
3. **Session isolation** — each pipeline run gets a unique `session_id`
4. **Agent-specific writes** — each agent writes to its own output column in the shared state

```
Agent                    Writes To
─────────────────────    ─────────────────────────
Sampling Agent    →      state['sampling_result']
Analysis Agent    →      state['analysis_result']
Geology Agent     →      state['geology_result']
Market Agent      →      state['market_result']
Report Agent      →      state['report_result']
Compliance Agent  →      state['compliance_result']
```

No two agents write to the same key. Read conflicts are impossible (append-only results).

---

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Enable pgvector in Supabase
# Run in Supabase SQL Editor:
CREATE EXTENSION IF NOT EXISTS vector;

# 3. Run schema
psql $SUPABASE_URL -f memory_schema.sql

# 4. Run migrations (in order)
psql $SUPABASE_URL -f migrations/001_initial_schema.sql
psql $SUPABASE_URL -f migrations/002_pgvector_setup.sql
psql $SUPABASE_URL -f migrations/003_indexes_and_rls.sql

# 5. Set environment variables
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="your-anon-key"
export GOOGLE_API_KEY="your-gemini-key"

# 6. Initialize memory manager
python -c "from memory_manager import MemoryManager; mm = MemoryManager(); print('Memory system ready')"
```

---

## Key Design Decisions

1. **Supabase over Redis** — Free tier, persistent, SQL-queryable, pgvector for embeddings
2. **pgvector over Pinecone** — Zero cost, same database, no external service
3. **LangGraph checkpointer** — Native integration with our graph-based agent pipeline
4. **Offline-first** — Flutter SQLite cache with delta sync, not real-time subscriptions
5. **Consolidation as background job** — Not blocking the analysis pipeline
6. **Version columns** — Optimistic concurrency, no distributed locks needed
7. **Embedding dimension 384** — all-MiniLM-L6-v2 (small, fast, free, good enough for geological text)
