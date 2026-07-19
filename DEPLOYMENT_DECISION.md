# AfriMine AI — Deployment Decision

**Date:** July 19, 2026
**Status:** DECIDED
**Decision:** Cloudflare Pages + Workers (frontend + API edge) + Railway (Python LangGraph)

---

## 1. The Problem

ARCHITECTURE_V3.md §6.1 lists 4 deployment options for the Python LangGraph service but commits to none:
- Railway free tier
- Fly.io free tier
- Supabase Edge Functions
- Cloudflare Workers

This ambiguity blocks engineering. Developers don't know where to deploy, which affects latency, cold starts, cost, and CI/CD.

---

## 2. Decision

### Frontend + Edge API: Cloudflare Pages + Workers (ADR-011, unchanged)

| Component | Deployment | Why |
|-----------|-----------|-----|
| **Flutter Web** | Cloudflare Pages | Auto-deploy from GitHub, free SSL, Africa edge CDN (Johannesburg, Nairobi, Lagos PoPs) |
| **API Proxy** | Cloudflare Workers | Rate limiting, CORS, edge caching, WAF bot protection |
| **DNS + SSL** | Cloudflare | Free, automatic, DDoS protection |

### Python LangGraph Service: Railway

| Component | Deployment | Why |
|-----------|-----------|-----|
| **LangGraph Orchestrator** | Railway ($5/mo hobby plan) | Persistent process, no cold starts, PostgreSQL addon compatible |
| **A2A Bridge** | Same Railway service | FastAPI runs alongside LangGraph in same container |

---

## 3. Why Railway Over Alternatives

### Comparison Matrix

| Criterion | Railway | Fly.io | Supabase Edge Functions | Cloudflare Workers |
|----------|---------|--------|------------------------|-------------------|
| **Python support** | ✅ Native | ✅ Native | ⚠️ Limited (Deno-based, Python beta) | ⚠️ Python workers in beta |
| **Persistent process** | ✅ Yes (always-on) | ✅ Yes | ❌ No (serverless, 50ms CPU limit) | ❌ No (30s max) |
| **Cold starts** | ✅ None (persistent) | ⚠️ ~2-5s (scale to zero) | ❌ ~1-3s per invocation | ❌ ~50ms (fast but stateless) |
| **LangGraph compatibility** | ✅ Full (long-running graphs) | ✅ Full | ❌ Graph may exceed timeout | ❌ Graph may exceed timeout |
| **PostgreSQL addon** | ✅ Built-in | ❌ Need external | ✅ (Supabase itself) | ❌ Need external |
| **Free tier** | ⚠️ $5/mo hobby (500 hrs) | ⚠️ Free but limited (3 shared VMs) | ✅ Free (500K invocations) | ✅ Free (100K req/day) |
| **Africa latency** | ⚠️ US/EU regions (~150-300ms) | ⚠️ US/EU (~150-300ms) | ✅ Edge (low) | ✅ Edge (low) |
| **CI/CD** | ✅ GitHub auto-deploy | ✅ GitHub auto-deploy | ✅ Supabase CLI | ✅ Wrangler CLI |
| **Scaling** | ✅ Horizontal (paid) | ✅ Horizontal | ✅ Automatic | ✅ Automatic |
| **Setup complexity** | Low | Medium | Medium | Medium |

### Why NOT Each Alternative

**Supabase Edge Functions:**
- ❌ 50ms CPU time limit — LangGraph agent pipeline can take 30-60 seconds
- ❌ Serverless — no persistent connections to MCP servers
- ❌ Python support is beta and limited
- ❌ Cannot run long-running graph executions

**Cloudflare Workers:**
- ❌ 30 second execution limit — insufficient for full 6-agent pipeline
- ❌ Python runtime is in beta
- ❌ Cannot maintain persistent state between agent calls
- ✅ Perfect for API proxy (stateless request routing) — which is what we use it for

**Fly.io:**
- ⚠️ Scale-to-zero causes cold starts (2-5s) — field workers notice
- ⚠️ Free tier is limited (3 shared-cpu-1x VMs, 256MB RAM each)
- ⚠️ More complex configuration than Railway
- ✅ Good option if Railway doesn't work out

### Why Railway Wins

1. **No cold starts:** LangGraph runs as a persistent process. Field workers in Nyatike with 3G connections can't afford 3-5s cold starts.
2. **Full Python support:** Long-running agent pipelines (30-60s) work without timeout issues.
3. **Simple deployment:** `railway up` from CLI or GitHub auto-deploy. No Dockerfile required for basic Python apps.
4. **$5/month:** Cheaper than a coffee. The hobby plan includes 500 execution hours/month — enough for MVP.
5. **PostgreSQL addon:** Can use Railway's PostgreSQL or connect to Supabase (we use Supabase).

---

## 4. Architecture After Decision

```
┌─────────────────────────────────────────────────────────────────┐
│                        DEPLOYMENT MAP                            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ CLOUDFLARE (Free Tier)                                    │   │
│  │                                                           │   │
│  │  Pages: Flutter Web build                                 │   │
│  │    └── Auto-deploy from GitHub main branch                │   │
│  │    └── Africa CDN: JNB, NBO, LOS PoPs                    │   │
│  │                                                           │   │
│  │  Workers: API proxy                                       │   │
│  │    └── Rate limiting (100 req/min per user)               │   │
│  │    └── CORS headers                                       │   │
│  │    └── Request routing to Railway backend                 │   │
│  │    └── Edge caching for static responses                  │   │
│  │                                                           │   │
│  │  DNS: afrimine.com → Cloudflare nameservers              │   │
│  │  SSL: Automatic (Universal SSL)                           │   │
│  │  WAF: Bot protection, DDoS mitigation                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│                           │ HTTPS                                │
│                           ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ RAILWAY ($5/mo Hobby Plan)                                │   │
│  │                                                           │   │
│  │  Single service: Go Backend + Python LangGraph            │   │
│  │    ├── Go Chi Router (API endpoints)                      │   │
│  │    ├── A2A Bridge (FastAPI, port 8000)                    │   │
│  │    ├── LangGraph Orchestrator (6 agents)                  │   │
│  │    ├── MCP Servers (12 servers)                           │   │
│  │    └── Health check endpoint                              │   │
│  │                                                           │   │
│  │  Region: US-East (closest to Supabase)                    │   │
│  │  RAM: 512MB (hobby) → 8GB (pro)                          │   │
│  │  CPU: 1 vCPU (hobby) → 8 vCPU (pro)                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│                           │ PostgreSQL connection                 │
│                           ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ SUPABASE (Free Tier → Pro $25/mo)                         │   │
│  │                                                           │   │
│  │  PostgreSQL: Database, pgvector, RLS, checkpoints         │   │
│  │  Auth: Phone OTP, JWT                                     │   │
│  │  Storage: Photos, reports, satellite tiles                │   │
│  │  Realtime: Live analysis progress                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ EDGE (Physical Hardware)                                  │   │
│  │                                                           │   │
│  │  Jetson Orin Nano: Field kit AI                           │   │
│  │  Android Phone: Flutter app + offline cache               │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Step-by-Step Deployment Guide

### 5.1 Prerequisites

```bash
# Install Railway CLI
npm install -g @railway/cli

# Install Wrangler (Cloudflare Workers CLI)
npm install -g wrangler

# Login to both
railway login
wrangler login
```

### 5.2 Deploy Python LangGraph Service to Railway

```bash
# 1. Create Railway project
cd afrimine-ai/langgraph-migration
railway init afrimine-langgraph

# 2. Set environment variables
railway variables set SUPABASE_URL="https://xxx.supabase.co"
railway variables set SUPABASE_SERVICE_KEY="eyJ..."
railway variables set SUPABASE_DB_HOST="db.xxx.supabase.co"
railway variables set SUPABASE_DB_PASSWORD="..."
railway variables set GOOGLE_API_KEY="..."
railway variables set GROQ_API_KEY="..."
railway variables set MISTRAL_API_KEY="..."
railway variables set LANGSMITH_API_KEY="..."
railway variables set SENTRY_DSN="..."

# 3. Create Procfile (if not exists)
echo "web: uvicorn a2a_bridge:app --host 0.0.0.0 --port \$PORT" > Procfile

# 4. Deploy
railway up

# 5. Get the public URL
railway domain
# → https://afrimine-langgraph-production-xxxx.up.railway.app
```

### 5.3 Deploy Flutter Web to Cloudflare Pages

```bash
# 1. Build Flutter web
cd afrimine-ai/flutter_app
flutter build web --release

# 2. Deploy via Wrangler
wrangler pages project create afrimine-web --production-branch main
wrangler pages deploy build/web --project-name afrimine-web

# 3. Set custom domain (in Cloudflare Dashboard)
# afrimine.com → Pages → Custom domains → Add
```

### 5.4 Deploy API Proxy to Cloudflare Workers

```javascript
// wrangler.toml
name = "afrimine-api"
main = "src/index.js"
compatibility_date = "2026-07-19"

[vars]
RAILWAY_URL = "https://afrimine-langgraph-production-xxxx.up.railway.app"
```

```javascript
// src/index.js
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // CORS headers
    const corsHeaders = {
      'Access-Control-Allow-Origin': 'https://afrimine.com',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    // Rate limiting (simple in-memory, use Durable Objects for production)
    // ... rate limiting logic ...

    // Proxy to Railway
    const targetUrl = env.RAILWAY_URL + url.pathname + url.search;
    const response = await fetch(targetUrl, {
      method: request.method,
      headers: request.headers,
      body: request.body,
    });

    // Add CORS headers to response
    const newResponse = new Response(response.body, response);
    Object.entries(corsHeaders).forEach(([key, value]) => {
      newResponse.headers.set(key, value);
    });

    return newResponse;
  },
};
```

```bash
# Deploy worker
wrangler deploy
```

### 5.5 DNS + SSL Configuration

```
# Cloudflare DNS Records
afrimine.com          → A     → Cloudflare proxy (automatic)
www.afrimine.com      → CNAME → afrimine.com
api.afrimine.com      → CNAME → afrimine-langgraph-production-xxxx.up.railway.app
```

**SSL:** Cloudflare Universal SSL (free, automatic). Mode: "Full (Strict)" — encrypts end-to-end.

### 5.6 CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.x'
      - run: flutter build web --release
      - uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          command: pages deploy build/web --project-name afrimine-web

  deploy-backend:
    runs-on: ubuntu-latest
    # Railway auto-deploys from GitHub — no explicit step needed
    # But we can add health check
    steps:
      - name: Wait for Railway deployment
        run: sleep 60
      - name: Health check
        run: curl -f https://api.afrimine.com/health || exit 1
```

---

## 6. Latency Analysis

| Path | Hop | Latency | Total |
|------|-----|---------|-------|
| Field worker (Kenya) → Cloudflare CDN | Edge (Nairobi PoP) | ~10ms | 10ms |
| Cloudflare Worker → Railway | US-East | ~150ms | 160ms |
| Railway → Supabase | US-East (same region) | ~5ms | 165ms |
| Railway → Gemini API | Google (global) | ~50ms | 215ms |
| **Total: First byte** | | | **~215ms** |
| Agent pipeline (6 agents) | LLM calls | ~30-60s | 30-60s |
| **Total: Full analysis** | | | **~30-60s** |

**Note:** The 215ms overhead is for the initial request. The 30-60s pipeline time dominates. Streaming via SSE means the field worker sees progress updates in real-time.

---

## 7. Scaling Path

| Stage | Railway Plan | Cost | Capacity |
|-------|-------------|------|----------|
| **MVP** | Hobby | $5/mo | 500 hrs, 512MB RAM |
| **Growth** | Pro | $20/mo | Unlimited, 8GB RAM, 8 vCPU |
| **Scale** | Pro + replicas | $40-80/mo | Multiple instances behind load balancer |
| **Enterprise** | Dedicated | Custom | Dedicated compute, SLA |

**When to upgrade from Hobby to Pro:**
- Consistent >500 execution hours/month
- Memory usage >400MB (6 agents + embeddings)
- Need >1 vCPU for parallel agent execution

---

## 8. Rollback Plan

If Railway doesn't work:

1. **Immediate fallback:** Deploy Python service to Fly.io (similar capabilities)
2. **Quick migration:** `fly launch` → `fly deploy` (similar CLI workflow)
3. **Alternative:** Render.com (similar pricing, auto-deploy from GitHub)

No data migration needed — Supabase is the data layer, not Railway.
