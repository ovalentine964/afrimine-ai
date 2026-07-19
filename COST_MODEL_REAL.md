# AfriMine AI — Honest Cost Model

**Date:** July 19, 2026
**Purpose:** Transparent cost projections that account for agent multiplication, hardware, and real growth triggers
**Supersedes:** The $0/month claim in ARCHITECTURE_V3.md §9

---

## TL;DR

| Tier | Monthly Cost | When You Hit It |
|------|-------------|-----------------|
| **MVP** | **$0** | Months 1-4, <10 users, <10 analyses/day |
| **Growth** | **$50-100/mo** | Month 5-8, 10-100 users, 10-50 analyses/day |
| **Scale** | **$500-2,000/mo** | Month 9+, 100+ users, 50+ analyses/day |

**One-time hardware costs (NOT $0):**
- NVIDIA Jetson Orin Nano: **$249-499** (field kit)
- Budget Android phone for field workers: **$50-150** (if not already owned)

**The $0 claim is real for MVP, but misleading if presented as the production cost.**

---

## 1. The Agent Multiplication Problem

Each mineral analysis triggers **6 agents**, each making LLM calls. The architecture counts "analyses/day" but free tier limits are in "requests/day."

| Analyses/Day | Agent Calls/Day | Gemini Free Tier (1,500 req/day) |
|-------------|----------------|--------------------------------|
| 10 | 60 | ✅ Fine (4% utilization) |
| 50 | 300 | ✅ Fine (20% utilization) |
| 100 | 600 | ✅ Fine (40% utilization) |
| 250 | 1,500 | ⚠️ **At the limit** |
| 500 | 3,000 | ❌ **2x over limit** |

**Reality:** At ~250 analyses/day, you exhaust the Gemini free tier. This happens faster than the architecture suggests because each analysis ≠ one request.

---

## 2. MVP Tier — $0/month (Months 1-4)

### What's Actually Free

| Service | Free Limit | What Uses It | ~MVP Usage | % of Limit |
|---------|------------|-------------|------------|-----------|
| **Gemini 2.5 Flash** | 1,500 req/day | 6 agent calls per analysis | ~60 req/day (10 analyses) | 4% |
| **Supabase DB** | 500MB | All tables + embeddings | ~50MB | 10% |
| **Supabase Storage** | 1GB | Photos, reports, satellite tiles | ~200MB | 20% |
| **Supabase Auth** | 50K MAU | User authentication | ~10 MAU | 0.02% |
| **Supabase Realtime** | 200 concurrent | Live analysis updates | ~5 concurrent | 2.5% |
| **Cloudflare Pages** | Unlimited | Flutter web frontend | ~1GB bandwidth | — |
| **Cloudflare Workers** | 100K req/day | API proxy | ~1K req/day | 1% |
| **GitHub Actions** | 2,000 min/month (public) | CI/CD | ~200 min | 10% |
| **LangSmith** | 5K traces/month | Agent observability | ~300 traces (10 analyses × ~30 traces) | 6% |
| **Sentry** | 5K errors/month | Error tracking | ~100 errors | 2% |
| **Google Earth Engine** | Free (non-commercial) | Satellite imagery | ~30 tiles/month | — |
| **Groq Whisper** | 2K RPD | Voice STT | ~50 RPD | 2.5% |

### What Triggers Overflow (When $0 Ends)

| Trigger | When | What Happens |
|---------|------|-------------|
| Gemini >1,500 req/day | ~250 analyses/day | LLM calls fail → fallback to Mistral/Groq |
| Supabase DB >500MB | ~50K analyses with embeddings | Database reads fail → need Pro ($25/mo) |
| Supabase Storage >1GB | ~10 analyses with satellite tiles (100MB each) | Uploads fail → need Pro ($25/mo) |
| LangSmith >5K traces | ~167 analyses/month (5.5/day) | Tracing stops → sample or upgrade |
| Satellite tiles | 10 tiles × 100MB = 1GB | Storage full on first day of satellite use |

### Honest Assessment

**$0 is realistic for:**
- Development and testing (1-5 developers)
- Pilot with <10 field workers
- <10 analyses per day
- No satellite tile storage (text-only analyses)

**$0 is NOT realistic for:**
- Any satellite imagery work (100MB tiles fill 1GB storage immediately)
- More than ~5 analyses/day with LangSmith tracing
- Production use with real users

---

## 3. Growth Tier — $50-100/month (Months 5-8)

### Required Upgrades

| Service | Upgrade | Cost | Why |
|---------|---------|------|-----|
| **Supabase Pro** | 8GB DB, 100GB storage | **$25/mo** | Embeddings + satellite tiles exceed free tier |
| **Gemini Paid** | Pay-as-you-go (~$0.075/1M input tokens) | **$10-30/mo** | When >250 analyses/day |
| **LangSmith Plus** | 10K traces/month | **$0-29/mo** | If tracing is critical |
| **Domain** | afrimine.com | **$12/year** ($1/mo) | Professional presence |

### Cost Breakdown at 50 Analyses/Day

```
Per-analysis cost:
  6 LLM calls × ~2,000 tokens each = 12,000 tokens/analysis
  Gemini input:  $0.075 / 1M tokens × 12,000 = $0.0009/analysis
  Gemini output: $0.30 / 1M tokens × 3,000  = $0.0009/analysis
  Total LLM: ~$0.002/analysis

Monthly at 50 analyses/day:
  LLM: 50 × 30 × $0.002 = $3.00
  Supabase Pro: $25.00
  Storage (satellite): ~$5.00
  Total: ~$33/month
```

### Fallback Chain Cost

If Gemini free tier is exhausted:
- **Mistral Free:** 1B tokens/month → ~83K analyses worth → **$0**
- **Groq Free:** 1K RPD (Llama) + 2K RPD (Whisper) → **$0**
- **Claude Free:** Limited → **$0**

**The fallback chain can keep costs at $0 longer, but with degraded quality.**

---

## 4. Scale Tier — $500-2,000/month (Month 9+)

### Required Infrastructure

| Service | Upgrade | Cost | Why |
|---------|---------|------|-----|
| **Supabase Team** | 100GB DB, 1TB storage, priority support | **$125/mo** | Production database needs |
| **Gemini Pro** | Higher rate limits, better models | **$50-200/mo** | 500+ analyses/day |
| **Dedicated Python Host** | Railway/Fly.io production plan | **$20-50/mo** | LangGraph needs dedicated compute |
| **LangSmith Plus** | 100K traces | **$29-99/mo** | Production observability |
| **Cloudflare Pro** | WAF, advanced caching | **$20/mo** | Production security |
| **Monitoring** | Better Uptime, PagerDuty | **$0-50/mo** | On-call alerting |

### Cost at 500 Analyses/Day

```
Per-analysis cost (Gemini paid):
  6 LLM calls × ~2,000 tokens = 12,000 tokens
  Input:  $1.25 / 1M tokens × 12,000 = $0.015
  Output: $5.00 / 1M tokens × 3,000  = $0.015
  Total LLM: ~$0.03/analysis

Monthly at 500 analyses/day:
  LLM: 500 × 30 × $0.03 = $450
  Supabase Team: $125
  Compute (Python): $30
  Storage: $20
  Monitoring: $30
  Total: ~$655/month
```

### Cost at 5,000 Analyses/Day

```
Monthly at 5,000 analyses/day:
  LLM: 5,000 × 30 × $0.03 = $4,500  ← This is the bottleneck
  Supabase Team: $125
  Compute: $100
  Storage: $50
  Monitoring: $50
  Total: ~$4,825/month
```

**At this scale, LLM costs dominate.** Options:
1. Use cheaper models (Groq Llama 4 Scout: $0.05/1M tokens → 100x cheaper)
2. Cache common analyses (reduce LLM calls by 50%)
3. Use local models on Jetson for routine classifications

---

## 5. Hardware Costs (NOT $0)

| Hardware | Cost | Purpose | When Needed |
|----------|------|---------|-------------|
| **NVIDIA Jetson Orin Nano** | $249-499 | Field kit: Gemma 4 E2B, Kokoro TTS, offline AI | Phase 4+ |
| **Budget Android Phone** | $50-150 | Field worker device (if not owned) | Phase 1+ |
| **Jetson Orin NX** (upgrade) | $599-999 | More capable field kit | Phase 6 |
| **Jetson T2000** (future) | TBD (~$1,500?) | Thor-based edge AI | When available |

**Total hardware budget for 5 field workers:**
- 5 × Android phones: $250-750 (or use existing phones → $0)
- 1 × Jetson Orin Nano: $249-499
- **Total: $249-1,249 one-time**

---

## 6. Per-Analysis Cost Breakdown

### What Happens in One Analysis

| Step | Service | Tokens/Time | Cost |
|------|---------|-------------|------|
| 1. Sampling Agent | Gemini Flash | ~1,500 tokens | $0.0003 |
| 2. Analysis Agent | Gemini Flash (vision) | ~3,000 tokens + image | $0.001 |
| 3. Geology Agent | Gemini Flash + RAG | ~2,500 tokens | $0.0005 |
| 4. Market Agent | API call (no LLM) | — | $0.000 |
| 5. Report Agent | Gemini Flash | ~4,000 tokens | $0.001 |
| 6. Compliance Agent | Gemini Flash | ~1,500 tokens | $0.0003 |
| **Total LLM** | | **~12,500 tokens** | **~$0.003** |
| Embedding generation | all-MiniLM-L6-v2 (local) | CPU time | $0.000 |
| Storage (Supabase) | PostgreSQL + pgvector | ~5KB | ~$0.000 |
| Storage (satellite tile) | Supabase Storage | ~100MB | ~$0.001 |
| LangSmith trace | 6+ spans | — | $0.000 (free tier) |
| **Total per analysis** | | | **~$0.004** |

### Cost per Analysis at Scale

| Scale | Analyses/Month | Monthly LLM Cost | Cost/Analysis |
|-------|---------------|-----------------|---------------|
| MVP (free) | 300 | $0 (free tier) | $0.00 |
| Growth (paid) | 1,500 | $4.50 | $0.003 |
| Scale | 15,000 | $450 | $0.030 |
| Enterprise | 150,000 | $4,500 | $0.030 |

---

## 7. Free Tier Monitoring Checklist

Track these metrics to know when $0 is ending:

| Metric | Free Limit | Warning Threshold | Action |
|--------|-----------|-------------------|--------|
| Gemini requests/day | 1,500 | 1,200 (80%) | Enable Mistral fallback |
| Supabase DB size | 500MB | 400MB (80%) | Archive old sessions |
| Supabase Storage | 1GB | 800MB (80%) | Compress/delete old tiles |
| LangSmith traces/month | 5,000 | 4,000 (80%) | Enable 50% sampling |
| Sentry errors/month | 5,000 | 4,000 (80%) | Filter low-severity |
| Supabase Auth MAU | 50,000 | 40,000 (80%) | — (unlikely to hit) |
| Cloudflare Workers req/day | 100,000 | 80,000 (80%) | Cache more aggressively |

**Recommendation:** Set up alerts at 80% of each limit. The moment you hit 80% on Gemini or Supabase, start the upgrade conversation.

---

## 8. Cost Optimization Strategies

### Keep Costs Low

1. **Cache aggressively:** Geological knowledge, deposit models, and common analyses don't change. Cache LLM responses.
2. **Use the right model:** Market Agent uses NO LLM. Compliance Agent can use rule engine + LLM only for edge cases.
3. **Compress satellite tiles:** 100MB GeoTIFF → 10MB compressed PNG for storage.
4. **Prune embeddings:** Delete embeddings for failed/low-quality analyses.
5. **Sample LangSmith:** Only trace 20% of successful analyses, 100% of failures.
6. **Batch embeddings:** Generate embeddings in batches, not one-at-a-time.

### When to Invest

| Investment | Cost | ROI |
|-----------|------|-----|
| Supabase Pro ($25/mo) | Low | Unblocks satellite tiles + more users |
| Gemini paid ($10-30/mo) | Low | Removes rate limit anxiety |
| Jetson Orin Nano ($249) | Medium | Enables offline AI, reduces cloud LLM costs |
| Dedicated Python host ($20/mo) | Low | Eliminates cold starts, improves latency |

---

## Summary

| What the Architecture Says | Reality |
|---------------------------|---------|
| "$0/month" | ✅ True for MVP (1-4 months, <10 users) |
| "Free tier sustains $0" | ⚠️ Only if you skip satellite tiles and limit tracing |
| "Scaling cost: $25-100" | ✅ Reasonable for Growth tier |
| "Hardware: not mentioned" | ❌ Jetson costs $249-499, phones $50-150 |
| "1 analysis = 1 request" | ❌ 1 analysis = 6+ LLM requests |
| "Free forever" | ❌ $0 ends at ~250 analyses/day or 10 satellite tiles |

**Be honest with your team:** $0 gets you to MVP. Growth costs real money. Plan for it.
