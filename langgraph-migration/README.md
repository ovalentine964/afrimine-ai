# AfriMine AI — LangGraph Migration

**Migrating from CrewAI to LangGraph 1.0 for production-grade multi-agent orchestration.**

## Why LangGraph?

| Feature | CrewAI (before) | LangGraph (after) |
|---------|-----------------|-------------------|
| Orchestration | Sequential only | Graph-based: parallel, conditional, loops |
| State management | Basic | Durable checkpointing (Supabase) |
| Crash recovery | None | Resume from last checkpoint |
| Parallel execution | Not supported | Native fan-out/fan-in |
| Production score | 7.8/10 | 9.2/10 (#1 ranked) |
| Production users | Prototyping teams | Klarna, Replit, Elastic, LinkedIn, Uber |

## Architecture

```
START → Sampling → Analysis → Router ──┬→ Geology ──┬→ Report → Compliance → END
                                       │            │        ↑
                                       └→ Market ───┘        │
                                                └── REFINE ──┘
```

- **Parallel branches**: Geology + Market run concurrently after Analysis
- **Conditional routing**: Based on mineral type and confidence
- **Refinement loop**: Report can loop back through Analysis up to 3 times
- **Checkpointing**: Every node boundary saved to Supabase for crash recovery

## Quick Start

### 1. Install dependencies

```bash
cd afrimine-ai/langgraph-migration
pip install -r requirements.txt
```

### 2. Set environment variables

```bash
# .env file
GOOGLE_API_KEY=your-gemini-api-key
DATABASE_URL=postgresql://postgres:password@db.xxxxx.supabase.co:5432/postgres?sslmode=require

# Or individual Supabase vars
SUPABASE_DB_HOST=db.xxxxx.supabase.co
SUPABASE_DB_PASSWORD=your-password
```

### 3. Run a test analysis

```bash
python graph.py
```

### 4. Start the A2A bridge (for Go backend)

```bash
python a2a_bridge.py
# Runs on http://localhost:8000
```

### 5. Test with curl

```bash
curl -X POST http://localhost:8000/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-001",
    "method": "tasks/send",
    "params": {
      "id": "analysis-001",
      "message": {
        "role": "user",
        "parts": [{
          "type": "data",
          "data": {
            "location": {
              "lat": -1.05,
              "lon": 34.55,
              "region": "Nyatike",
              "county": "Migori",
              "area_hectares": 10
            },
            "sample_data": {
              "sample_id": "NYT-001",
              "xrf_readings": {"Au": 5.2, "As": 120.5, "Cu": 45},
              "notes": "Quartz vein with sulfide staining"
            }
          }
        }]
      }
    }
  }'
```

## File Structure

```
langgraph-migration/
├── requirements.txt          # All Python dependencies
├── state_schema.py           # AfriMineState TypedDict (shared state)
├── graph.py                  # StateGraph with 6 agent nodes
├── checkpointer.py           # Supabase PostgreSQL checkpointer
├── a2a_bridge.py             # A2A protocol bridge (FastAPI)
├── mcp_servers.py            # MCP tool definitions for all agents
├── README.md                 # This file
└── agents/
    ├── __init__.py           # Agent exports
    ├── sampling_agent.py     # GPS waypoints, field routes
    ├── analysis_agent.py     # Mineral classification (Gemini vision)
    ├── geology_agent.py      # Geological context, deposit models
    ├── market_agent.py       # Gold/copper prices, deposit valuation
    ├── report_agent.py       # Investor PDF generation
    └── compliance_agent.py   # Kenya Mining Act 2016 checks
```

## Migration from CrewAI

### What changes

| CrewAI concept | LangGraph equivalent |
|---------------|---------------------|
| `Crew` | `StateGraph` |
| `Agent` | Node function (async) |
| `Task` | Agent's state read/write |
| `@task` decorator | `graph.add_node("name", fn)` |
| Sequential execution | `graph.add_edge("a", "b")` |
| Hierarchical execution | `graph.add_conditional_edges(...)` |
| (no equivalent) | Parallel fan-out with `Send` API |
| (no equivalent) | Checkpointing to Supabase |
| Crew kickoff | `graph.ainvoke(state, config)` |

### What stays the same

- All 6 agents keep their same responsibilities
- Gemini 2.5 Flash remains the primary LLM
- Supabase remains the database
- The Go backend still calls into Python agents (now via A2A protocol)
- Flutter app is unchanged

### Key differences in code

**CrewAI (before):**
```python
from crewai import Agent, Task, Crew

sampling = Agent(role="Sampling Agent", goal="...", llm=gemini)
task = Task(description="...", agent=sampling)
crew = Crew(agents=[sampling, ...], tasks=[task, ...])
result = crew.kickoff()
```

**LangGraph (after):**
```python
from langgraph.graph import StateGraph

graph = StateGraph(AfriMineState)
graph.add_node("sampling", sampling_agent)
graph.add_edge(START, "sampling")
# ... add all nodes and edges
app = graph.compile(checkpointer=checkpointer)
result = await app.ainvoke(initial_state, config)
```

## Integration with Go Backend

The Go backend communicates with Python agents via the **A2A protocol** (JSON-RPC 2.0 over HTTP):

```
Go Backend ──POST /a2a──→ FastAPI (a2a_bridge.py) ──→ LangGraph agents
```

### Go client example

```go
// In your Go backend
type A2ARequest struct {
    JSONRPC string      `json:"jsonrpc"`
    ID      string      `json:"id"`
    Method  string      `json:"method"`
    Params  A2AParams   `json:"params"`
}

type A2AParams struct {
    ID      string         `json:"id"`
    Message A2AMessage     `json:"message"`
}

// POST to http://localhost:8000/a2a
```

## MCP Tools

Each agent has associated MCP tools (defined in `mcp_servers.py`):

| Agent | Tools |
|-------|-------|
| Sampling | `gps_waypoint_generator`, `route_optimizer` |
| Analysis | `xrf_analyzer` |
| Geology | `deposit_model_lookup`, `band_ratio_calculator` |
| Market | `cut_off_calculator`, `deposit_valuator` |
| Compliance | `license_checker`, `royalty_calculator` |

## Production Deployment

### Environment setup

```bash
# Supabase checkpointer (production)
DATABASE_URL=postgresql://postgres:password@db.xxxxx.supabase.co:5432/postgres?sslmode=require

# Gemini API
GOOGLE_API_KEY=your-key

# LangSmith observability (free: 5K traces/month)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-key
```

### Start the A2A bridge

```bash
uvicorn a2a_bridge:app --host 0.0.0.0 --port 8000 --workers 4
```

### Health check

```bash
curl http://localhost:8000/health
```

## Cost

| Component | Cost |
|-----------|------|
| LangGraph | $0 (MIT license) |
| Gemini 2.5 Flash | $0 (free: 1,500 req/day) |
| Supabase | $0 (free: 500MB PostgreSQL) |
| LangSmith | $0 (free: 5K traces/month) |
| A2A bridge hosting | $0 (runs on existing server) |
| **Total** | **$0/month** |

## Next Steps

- [ ] Set up Supabase project and run checkpointer migrations
- [ ] Port CrewAI agent prompts to LangGraph node functions
- [ ] Implement A2A bridge and test with Go backend
- [ ] Add LangSmith tracing for observability
- [ ] Test offline mode with local models (Ollama)
- [ ] Deploy A2A bridge to production
- [ ] Update Flutter app to use new API endpoints
