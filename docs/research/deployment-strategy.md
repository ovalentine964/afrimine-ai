# AfriMine AI — Zero-Budget Production Deployment Strategy

> **Cost to start: $0** · **Designed for: Rural Kenya (poor internet, power issues)**
> **Stack: Flutter + Go + Python + PostgreSQL + NVIDIA NIM**

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Free Hosting — Recommended Stack](#2-free-hosting--recommended-stack)
3. [Database Hosting](#3-database-hosting)
4. [CI/CD Pipeline](#4-cicd-pipeline)
5. [Domain, DNS & SSL](#5-domain-dns--ssl)
6. [Monitoring & Observability](#6-monitoring--observability)
7. [Africa-Specific Deployment](#7-africa-specific-deployment)
8. [Offline-First Strategy](#8-offline-first-strategy)
9. [Step-by-Step Deployment Commands](#9-step-by-step-deployment-commands)
10. [Production Hardening Checklist](#10-production-hardening-checklist)
11. [Scaling Path](#11-scaling-path)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    USERS (Rural Kenya)                       │
│          Flutter Mobile App / Flutter Web (PWA)              │
│                   ↓ Low bandwidth                            │
├─────────────────────────────────────────────────────────────┤
│              CLOUDFLARE FREE CDN + DNS                       │
│          (Edge caching, DDoS protection, SSL)                │
│       African edge: Nairobi, Mombasa, Johannesburg           │
├──────────┬────────────────┬────────────────┬────────────────┤
│ RENDER   │  RENDER        │   RENDER       │  NVIDIA NIM    │
│ Go API   │  Python AI     │  WebSocket     │  (Cloud API)   │
│ (Free)   │  (Free)        │  Service       │  Free credits  │
├──────────┴────────────────┴────────────────┴────────────────┤
│              SUPABASE (Free PostgreSQL)                      │
│           500 MB · Auth · Storage · Realtime                 │
└─────────────────────────────────────────────────────────────┘
```

### Why This Stack?

| Component | Choice | Why |
|-----------|--------|-----|
| Frontend | Flutter Web (PWA) on Cloudflare Pages | Free CDN, edge in Africa, offline-capable |
| Backend API | Go on Render.com | Free tier, auto-deploy from GitHub |
| AI Service | Python on Render.com | Free tier, connects to NVIDIA NIM |
| Database | Supabase | Free 500MB PostgreSQL + Auth + Storage + Realtime |
| CDN/DNS | Cloudflare | Free, Africa edge locations |
| CI/CD | GitHub Actions | Free 2000 min/month |
| Monitoring | Uptime Robot + Sentry | Free tiers |

---

## 2. Free Hosting — Recommended Stack

### 2.1 PRIMARY: Render.com (Backend Services)

**Free Tier (as of 2025):**
- ✅ 750 hours/month of web services (enough for 1 service 24/7)
- ✅ Free PostgreSQL (90 days, then needs renewal)
- ✅ Auto-deploy from GitHub
- ✅ Custom domains with free SSL
- ⚠️ Cold starts: 15 min inactivity spin-down (mitigated below)
- ⚠️ 512 MB RAM per service

**Strategy:** Use Render for Go API + Python AI service. Mitigate cold starts with a free cron ping.

### 2.2 SECONDARY: Oracle Cloud Free Tier (Best Always-Free VM)

**Always Free (no time limit):**
- ✅ 2x AMD VMs (1/8 OCPU, 1 GB RAM each)
- ✅ **4x ARM Ampere A1 cores + 24 GB RAM** (always free!)
- ✅ 200 GB block storage
- ✅ 10 TB outbound/month
- ⚠️ ARM availability varies by region (try Johannesburg)

**Strategy:** Use ARM instance for self-hosted Go + Python services if Render cold starts become unacceptable. This is the **most powerful free option** available.

### 2.3 Cloudflare Pages + Workers (Frontend)

**Free Tier:**
- ✅ Unlimited sites, requests, bandwidth
- ✅ 500 builds/month
- ✅ Workers: 100K requests/day
- ✅ African edge locations (Nairobi, Johannesburg)
- ✅ Automatic SSL
- ✅ Great for Flutter Web PWA

### 2.4 TIER COMPARISON

| Platform | Compute | Database | Cold Start | Africa Edge | Always Free |
|----------|---------|----------|------------|-------------|-------------|
| Render.com | 750h/mo | ❌ (use Supabase) | 15 min | ❌ | ✅ (with renewal) |
| Oracle ARM | 4 cores/24GB | Self-host | None | ⚠️ Joburg | ✅ Forever |
| Railway.app | $5 credit/mo | ❌ | None | ❌ | ✅ (limited) |
| Fly.io | 3 shared VMs | ❌ | None | ⚠️ Limited | ✅ |
| Vercel | Serverless only | ❌ | ~1s | ❌ | ✅ |
| AWS Free Tier | t2.micro 750h | RDS 750h | None | ❌ (Cape Town $) | 12 months |

### RECOMMENDED COMBINATION

```
Frontend  → Cloudflare Pages (free, Africa CDN)
Backend   → Render.com (free, auto-deploy)
Database  → Supabase (free, PostgreSQL)
AI Worker → Render.com (free) or Oracle ARM (free forever)
```

---

## 3. Database Hosting

### 3.1 PRIMARY: Supabase (Recommended)

**Free Tier:**
- ✅ 500 MB PostgreSQL storage
- ✅ 50,000 monthly active users (Auth)
- ✅ 1 GB file storage
- ✅ 2 GB bandwidth
- ✅ Realtime subscriptions
- ✅ Row Level Security (RLS)
- ✅ Auto-backups (7 days)
- ⚠️ 2 concurrent connections (use PgBouncer)
- ⚠️ No point-in-time recovery on free tier

**Setup:**

```bash
# 1. Create project at supabase.com
# 2. Get connection string from Settings > Database
# 3. Use pooled connection for your Go backend:

DATABASE_URL="postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres"

# Direct connection (for migrations only):
DIRECT_URL="postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres"
```

### 3.2 BACKUP: Neon (Serverless PostgreSQL)

**Free Tier:**
- ✅ 512 MB storage
- ✅ Autoscaling to 0 (pay nothing when idle)
- ✅ Branching (great for dev/staging)
- ⚠️ Compute hours limit

### 3.3 Schema Design for Supabase Free Tier

```sql
-- Optimize for 500 MB limit
-- Use UUID primary keys (good for distributed systems)
-- Add indexes only where needed

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For text search

-- Users table (leverages Supabase Auth)
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    phone TEXT UNIQUE,
    location POINT, -- GPS coordinates for mine sites
    role TEXT DEFAULT 'worker' CHECK (role IN ('admin', 'manager', 'worker')),
    preferred_language TEXT DEFAULT 'sw', -- Swahili default
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Mining sites
CREATE TABLE mine_sites (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    location POINT NOT NULL,
    region TEXT NOT NULL,
    minerals TEXT[], -- Array of mineral types
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'rehabilitation')),
    created_by UUID REFERENCES profiles(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Safety reports (AI-analyzed)
CREATE TABLE safety_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    site_id UUID REFERENCES mine_sites(id) ON DELETE CASCADE,
    reporter_id UUID REFERENCES profiles(id),
    report_type TEXT NOT NULL CHECK (report_type IN ('hazard', 'incident', 'inspection', 'near_miss')),
    description TEXT NOT NULL,
    image_urls TEXT[], -- Supabase Storage URLs
    ai_risk_score FLOAT, -- 0.0 to 1.0 from NVIDIA NIM
    ai_analysis JSONB, -- Full AI analysis result
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'investigating', 'resolved', 'closed')),
    severity TEXT CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    location POINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

-- AI predictions cache (to reduce NVIDIA NIM API calls)
CREATE TABLE ai_predictions_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    input_hash TEXT UNIQUE NOT NULL, -- SHA256 of normalized input
    prediction_type TEXT NOT NULL,
    result JSONB NOT NULL,
    model_version TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ -- Cache expiration
);

-- Offline sync queue
CREATE TABLE sync_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES profiles(id),
    table_name TEXT NOT NULL,
    record_id UUID NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    payload JSONB NOT NULL,
    synced BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    synced_at TIMESTAMPTZ
);

-- Indexes (minimal for free tier)
CREATE INDEX idx_safety_reports_site ON safety_reports(site_id);
CREATE INDEX idx_safety_reports_status ON safety_reports(status);
CREATE INDEX idx_safety_reports_created ON safety_reports(created_at DESC);
CREATE INDEX idx_sync_queue_unsynced ON sync_queue(synced) WHERE synced = FALSE;
CREATE INDEX idx_profiles_phone ON profiles(phone);

-- Enable Row Level Security
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE safety_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE mine_sites ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can view own profile" ON profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON profiles
    FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can view reports for their sites" ON safety_reports
    FOR SELECT USING (
        site_id IN (
            SELECT id FROM mine_sites WHERE created_by = auth.uid()
        )
        OR reporter_id = auth.uid()
    );

CREATE POLICY "Users can create reports" ON safety_reports
    FOR INSERT WITH CHECK (reporter_id = auth.uid());

-- Auto-update timestamps
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

---

## 4. CI/CD Pipeline

### 4.1 GitHub Actions (Free: 2000 minutes/month)

```yaml
# .github/workflows/deploy.yml
name: Deploy AfriMine AI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  # ─── TEST ───
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: afrimine_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports: ['5432:5432']
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      # ── Go Backend Tests ──
      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.22'

      - name: Go dependencies
        working-directory: ./backend
        run: go mod download

      - name: Go tests
        working-directory: ./backend
        env:
          DATABASE_URL: postgres://test:test@localhost:5432/afrimine_test?sslmode=disable
        run: go test -v -race -coverprofile=coverage.out ./...

      # ── Python AI Tests ──
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Python dependencies
        working-directory: ./ai
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-asyncio

      - name: Python tests
        working-directory: ./ai
        env:
          DATABASE_URL: postgres://test:test@localhost:5432/afrimine_test
        run: pytest -v

      # ── Flutter Tests ──
      - name: Set up Flutter
        uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.22.x'
          channel: stable

      - name: Flutter dependencies
        working-directory: ./frontend
        run: flutter pub get

      - name: Flutter analyze
        working-directory: ./frontend
        run: flutter analyze

      - name: Flutter tests
        working-directory: ./frontend
        run: flutter test

  # ─── DEPLOY BACKEND ───
  deploy-backend:
    needs: test
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      # Render auto-deploys on push to main
      # Just trigger a manual deploy via API
      - name: Trigger Render Deploy
        run: |
          curl -X POST "${{ secrets.RENDER_DEPLOY_HOOK_URL }}"

  # ─── DEPLOY FRONTEND ───
  deploy-frontend:
    needs: test
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Flutter
        uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.22.x'
          channel: stable

      - name: Build Flutter Web
        working-directory: ./frontend
        run: |
          flutter build web --release --web-renderer canvaskit \
            --dart-define=API_URL=${{ secrets.API_URL }} \
            --dart-define=SUPABASE_URL=${{ secrets.SUPABASE_URL }} \
            --dart-define=SUPABASE_ANON_KEY=${{ secrets.SUPABASE_ANON_KEY }}

      - name: Deploy to Cloudflare Pages
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          command: pages deploy frontend/build/web --project-name=afrimine

  # ─── BUILD DOCKER IMAGES ───
  build-images:
    needs: test
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    strategy:
      matrix:
        service: [backend, ai]

    steps:
      - uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: ./${{ matrix.service }}
          push: true
          tags: |
            ghcr.io/${{ github.repository }}/${{ matrix.service }}:latest
            ghcr.io/${{ github.repository }}/${{ matrix.service }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### 4.2 Alternative: Gitea + Woodpecker CI (Self-Hosted, Fully Free)

For when you want zero dependency on GitHub:

```yaml
# docker-compose.yml (run on Oracle ARM)
version: '3.8'

services:
  gitea:
    image: gitea/gitea:latest
    container_name: gitea
    environment:
      - USER_UID=1000
      - USER_GID=1000
      - GITEA__database__DB_TYPE=sqlite3
    volumes:
      - gitea_data:/data
      - /etc/timezone:/etc/timezone:ro
    ports:
      - "3000:3000"
      - "2222:22"
    restart: unless-stopped

  woodpecker-server:
    image: woodpeckerci/woodpecker-server:latest
    container_name: woodpecker-server
    environment:
      - WOODPECKER_OPEN=true
      - WOODPECKER_HOST=https://ci.yourdomain.com
      - WOODPECKER_AGENT_SECRET=${WOODPECKER_AGENT_SECRET}
      - WOODPECKER_GITEA=true
      - WOODPECKER_GITEA_URL=http://gitea:3000
      - WOODPECKER_GITEA_CLIENT=${GITEA_OAUTH_CLIENT}
      - WOODPECKER_GITEA_SECRET=${GITEA_OAUTH_SECRET}
    volumes:
      - woodpecker_data:/var/lib/woodpecker
    ports:
      - "8000:8000"
    restart: unless-stopped

  woodpecker-agent:
    image: woodpeckerci/woodpecker-agent:latest
    container_name: woodpecker-agent
    environment:
      - WOODPECKER_SERVER=woodpecker-server:9000
      - WOODPECKER_AGENT_SECRET=${WOODPECKER_AGENT_SECRET}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    restart: unless-stopped
    depends_on:
      - woodpecker-server

volumes:
  gitea_data:
  woodpecker_data:
```

---

## 5. Domain, DNS & SSL

### 5.1 Free Domain Options

| Option | Cost | Duration | Notes |
|--------|------|----------|-------|
| `.tk`, `.ml`, `.ga`, `.cf`, `.gq` | Free | 1 year (renewable) | From Freenom — **unreliable, often down** |
| GitHub Pages subdomain | Free | Forever | `username.github.io` |
| Cloudflare Pages subdomain | Free | Forever | `project.pages.dev` |
| Render subdomain | Free | Forever | `service.onrender.com` |
| Supabase subdomain | Free | Forever | `project.supabase.co` |

**RECOMMENDATION:** Start with Cloudflare Pages (`afrimine.pages.dev`) and Render (`afrimine-api.onrender.com`). When budget allows, buy a `.co.ke` domain (~$10/year).

### 5.2 Cloudflare Free DNS Setup

```
# DNS Records for afrimine.pages.dev

Type    Name              Content                        Proxy
A       afrimine          192.0.2.1 (CF Pages IP)       ✅ Proxied
CNAME   api               afrimine-api.onrender.com      ✅ Proxied
CNAME   ai                afrimine-ai.onrender.com       ✅ Proxied
CNAME   www               afrimine.pages.dev             ✅ Proxied

# Cloudflare Page Rules (free: 3 rules)
# 1. Cache everything for static assets
# 2. Always use HTTPS
# 3. Browser Cache TTL: 1 month for /assets/*
```

### 5.3 SSL — Automatic with Cloudflare + Render

- **Cloudflare Pages:** Auto SSL via Cloudflare
- **Render.com:** Auto SSL via Let's Encrypt
- **Between Render ↔ Supabase:** TLS by default
- **Total cost: $0**

---

## 6. Monitoring & Observability

### 6.1 Uptime Monitoring — Uptime Robot (Free)

**Free Tier:** 50 monitors, 5-minute intervals, 1 status page

```
# Set up monitors for:
# 1. https://afrimine.pages.dev (frontend)
# 2. https://afrimine-api.onrender.com/health (Go API)
# 3. https://afrimine-ai.onrender.com/health (Python AI)
# 4. Supabase database (via health endpoint)

# Alert channels (all free):
# - Email
# - Telegram bot
# - Slack webhook
```

**Keep-alive ping to prevent Render cold starts:**

```bash
# Cron job on Uptime Robot (or any free cron service)
# Ping every 10 minutes to prevent 15-min spin-down
# URL: https://afrimine-api.onrender.com/health
# Method: GET
# Interval: 5 minutes
```

### 6.2 Error Tracking — Sentry (Free)

**Free Tier:** 5,000 errors/month, 1 user, 30-day retention

```go
// Go backend - sentry setup
import (
    "github.com/getsentry/sentry-go"
    "time"
)

func initSentry() {
    sentry.Init(sentry.ClientOptions{
        Dsn:              os.Getenv("SENTRY_DSN"),
        Environment:      os.Getenv("APP_ENV"), // "production" or "development"
        TracesSampleRate: 0.2, // 20% of transactions
        BeforeSend: func(event *sentry.Event, hint *sentry.EventHint) *sentry.Event {
            // Strip PII from events
            event.User = sentry.User{}
            return event
        },
    })
    defer sentry.Flush(2 * time.Second)
}
```

```python
# Python AI service - sentry setup
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    environment=os.environ.get("APP_ENV", "production"),
    traces_sample_rate=0.2,
    integrations=[FastApiIntegration()],
    before_send=lambda event, hint: strip_pii(event),
)
```

### 6.3 Performance Monitoring — Grafana Cloud (Free)

**Free Tier:** 10K metrics, 50 GB logs, 50 GB traces

```yaml
# docker-compose.monitoring.yml (for local dev or Oracle ARM)
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
    ports:
      - "3001:3000"
    restart: unless-stopped

volumes:
  prometheus_data:
  grafana_data:
```

---

## 7. Africa-Specific Deployment

### 7.1 Cloud Regions with Africa Presence

| Provider | Region | Latency from Nairobi | Cost |
|----------|--------|---------------------|------|
| **Cloudflare Edge** | Nairobi, Mombasa, Joburg | ~5ms | **Free** |
| AWS | Cape Town (af-south-1) | ~40ms | Paid |
| Azure | South Africa North | ~45ms | Paid |
| Google Cloud | No Africa region | N/A | N/A |
| Oracle Cloud | Johannesburg | ~35ms | **Free (ARM)** |

**Strategy:** Cloudflare edge handles static content and CDN. Backend services on Render (US/EU, ~150ms) are acceptable for API calls. Use Supabase's closest region.

### 7.2 Network Optimization for Poor Connectivity

```go
// backend/middleware/compression.go
package middleware

import (
    "compress/gzip"
    "net/http"
    "strings"
)

func GzipMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        if !strings.Contains(r.Header.Get("Accept-Encoding"), "gzip") {
            next.ServeHTTP(w, r)
            return
        }
        w.Header().Set("Content-Encoding", "gzip")
        w.Header().Set("Content-Type", "application/json")
        gz := gzip.NewWriter(w)
        defer gz.Close()
        gz.Reset(w)
        next.ServeHTTP(gzipResponseWriter{ResponseWriter: w, Writer: gz}, r)
    })
}

// Aggressive caching for static data
func CacheMiddleware(duration string) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            w.Header().Set("Cache-Control", "public, max-age="+duration)
            w.Header().Set("CDN-Cache-Control", "max-age="+duration)
            next.ServeHTTP(w, r)
        })
    }
}
```

```python
# ai/main.py - Efficient responses for low bandwidth
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
import orjson  # Faster JSON serialization

app = FastAPI()
app.add_middleware(GZipMiddleware, minimum_size=500)

@app.post("/api/analyze")
async def analyze_safety_report(report: ReportInput):
    # Return minimal response, fetch details on demand
    result = await nvidia_nim_analyze(report)
    return {
        "id": result.id,
        "risk_score": result.risk_score,
        "severity": result.severity,
        # Don't return full analysis unless requested
        "summary": result.summary[:200],  # Truncate for mobile
    }
```

### 7.3 Mobile Data Optimization

```dart
// frontend/lib/services/api_service.dart
// Adaptive quality based on connection

import 'package:connectivity_plus/connectivity_plus.dart';

class AdaptiveApiService {
  Future<ConnectionQuality> getConnectionQuality() async {
    final connectivity = await Connectivity().checkConnectivity();
    
    switch (connectivity) {
      case ConnectivityResult.wifi:
        return ConnectionQuality.high;
      case ConnectivityResult.mobile:
        // Check actual speed with a small download
        final stopwatch = Stopwatch()..start();
        try {
          await http.get(Uri.parse('https://afrimine.pages.dev/ping.txt'));
          stopwatch.stop();
          if (stopwatch.elapsedMilliseconds < 500) {
            return ConnectionQuality.medium;
          }
        } catch (_) {}
        return ConnectionQuality.low;
      default:
        return ConnectionQuality.offline;
    }
  }

  Future<Map<String, dynamic>> fetchWithAdaptiveQuality(String endpoint) async {
    final quality = await getConnectionQuality();
    
    switch (quality) {
      case ConnectionQuality.high:
        return _fetchFull(endpoint);
      case ConnectionQuality.medium:
        return _fetchCompressed(endpoint);
      case ConnectionQuality.low:
        return _fetchMinimal(endpoint);  // Text only, no images
      case ConnectionQuality.offline:
        return _fetchFromCache(endpoint);
    }
  }
}
```

---

## 8. Offline-First Strategy

### 8.1 Architecture

```
┌─────────────────────────────────────────────┐
│              Flutter App (PWA)               │
│  ┌─────────────┐  ┌──────────────────────┐  │
│  │ Hive/SQLite │  │  Supabase Flutter    │  │
│  │ Local DB    │  │  (with offline mode) │  │
│  └──────┬──────┘  └──────────┬───────────┘  │
│         │                    │               │
│         └────────┬───────────┘               │
│                  │                           │
│         ┌────────▼────────┐                  │
│         │  Sync Manager   │                  │
│         │  (conflict      │                  │
│         │   resolution)   │                  │
│         └────────┬────────┘                  │
│                  │                           │
└──────────────────┼───────────────────────────┘
                   │ When online
         ┌─────────▼─────────┐
         │  Backend API      │
         │  (Go on Render)   │
         └───────────────────┘
```

### 8.2 Flutter Offline Implementation

```dart
// frontend/lib/services/offline_manager.dart
import 'package:hive_flutter/hive_flutter.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'dart:convert';

class OfflineManager {
  static const String _syncQueueBox = 'sync_queue';
  static const String _cacheBox = 'data_cache';
  late Box<Map> _syncQueue;
  late Box<String> _cache;

  Future<void> initialize() async {
    await Hive.initFlutter();
    _syncQueue = await Hive.openBox<Map>(_syncQueueBox);
    _cache = await Hive.openBox<String>(_cacheBox);
    
    // Listen for connectivity changes
    Connectivity().onConnectivityChanged.listen((result) {
      if (result != ConnectivityResult.none) {
        _processSyncQueue();
      }
    });
  }

  /// Save data locally and queue for sync
  Future<void> saveOfflineFirst({
    required String table,
    required String recordId,
    required Map<String, dynamic> data,
    required String operation, // INSERT, UPDATE, DELETE
  }) async {
    // 1. Save to local cache immediately
    await _cache.put('${table}_$recordId', jsonEncode(data));
    
    // 2. Add to sync queue
    await _syncQueue.add({
      'table': table,
      'record_id': recordId,
      'operation': operation,
      'data': data,
      'timestamp': DateTime.now().toIso8601String(),
      'retry_count': 0,
    });
    
    // 3. Try to sync immediately if online
    final connectivity = await Connectivity().checkConnectivity();
    if (connectivity != ConnectivityResult.none) {
      await _processSyncQueue();
    }
  }

  /// Process queued sync operations
  Future<void> _processSyncQueue() async {
    final pending = _syncQueue.values.toList();
    
    for (int i = 0; i < pending.length; i++) {
      final item = Map<String, dynamic>.from(pending[i]);
      
      try {
        final response = await http.post(
          Uri.parse('$API_URL/api/sync'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(item),
        );
        
        if (response.statusCode == 200) {
          await _syncQueue.deleteAt(i);
        } else if (response.statusCode == 409) {
          // Conflict — use server version
          await _resolveConflict(item, jsonDecode(response.body));
          await _syncQueue.deleteAt(i);
        }
      } catch (e) {
        // Update retry count
        item['retry_count'] = (item['retry_count'] ?? 0) + 1;
        if (item['retry_count'] > 5) {
          // Move to dead letter queue for manual review
          await _handleDeadLetter(item);
          await _syncQueue.deleteAt(i);
        } else {
          await _syncQueue.putAt(i, item);
        }
      }
    }
  }

  /// Conflict resolution: last-write-wins with server priority
  Future<void> _resolveConflict(
    Map<String, dynamic> local,
    Map<String, dynamic> server,
  ) async {
    final localTime = DateTime.parse(local['timestamp']);
    final serverTime = DateTime.parse(server['updated_at']);
    
    if (serverTime.isAfter(localTime)) {
      // Server is newer — update local cache
      await _cache.put(
        '${local['table']}_${local['record_id']}',
        jsonEncode(server),
      );
    } else {
      // Local is newer — force update on server
      await http.put(
        Uri.parse('$API_URL/api/${local['table']}/${local['record_id']}'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({...local['data'], 'force': true}),
      );
    }
  }

  /// Get data from cache or server
  Future<Map<String, dynamic>?> getData(String table, String id) async {
    // Try cache first
    final cached = _cache.get('${table}_$id');
    if (cached != null) {
      return jsonDecode(cached);
    }
    
    // Try server
    try {
      final response = await http.get(
        Uri.parse('$API_URL/api/$table/$id'),
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        await _cache.put('${table}_$id', response.body);
        return data;
      }
    } catch (_) {
      // Offline — return null
    }
    return null;
  }

  /// Clear old cache entries (keep last 30 days)
  Future<void> cleanupCache() async {
    final cutoff = DateTime.now().subtract(Duration(days: 30));
    for (final key in _cache.keys) {
      // Implementation depends on cache structure
    }
  }
}
```

### 8.3 AI Offline Fallback

```python
# ai/offline_model.py
# Lightweight model for on-device inference when offline

import onnxruntime as ort
import numpy as np

class OfflineRiskPredictor:
    """Tiny ONNX model that runs on mobile devices.
    Provides basic risk assessment when NVIDIA NIM is unreachable."""
    
    def __init__(self, model_path: str = "models/risk_lite.onnx"):
        self.session = ort.InferenceSession(model_path)
    
    def predict(self, features: dict) -> dict:
        """
        Input: Basic safety report features
        Output: Risk score and category
        """
        # Preprocess features into model input
        input_data = self._preprocess(features)
        
        # Run inference
        result = self.session.run(None, {"input": input_data})
        
        return {
            "risk_score": float(result[0][0]),
            "category": self._get_category(float(result[0][0])),
            "model": "offline_lite_v1",
            "confidence": float(result[1][0]),  # Lower than NIM
            "note": "Offline prediction — connect for full AI analysis"
        }
    
    def _preprocess(self, features: dict) -> np.ndarray:
        # Convert text to basic features
        text = features.get("description", "")
        word_count = len(text.split())
        has_hazard_words = any(w in text.lower() for w in [
            "danger", "hazard", "collapse", "flood", "gas", "explosion"
        ])
        return np.array([[
            word_count,
            int(has_hazard_words),
            features.get("nearby_incidents_30d", 0),
            features.get("workers_present", 0),
        ]], dtype=np.float32)
```

---

## 9. Step-by-Step Deployment Commands

### 9.1 Phase 1: Database (Supabase) — 10 minutes

```bash
# 1. Go to supabase.com and create account
# 2. Create new project:
#    - Name: afrimine-prod
#    - Region: East Asia (closest to Africa available)
#    - Database password: [generate strong password]
# 3. Wait ~2 minutes for provisioning
# 4. Go to SQL Editor and run the schema from Section 3.3
# 5. Get connection strings:
#    Settings > Database > Connection string > URI
#    Save both pooled (port 6543) and direct (port 5432)
# 6. Enable Auth:
#    Authentication > Providers > Enable Email/Phone
# 7. Create Storage bucket:
#    Storage > Create bucket > "safety-images" (public)
```

### 9.2 Phase 2: Backend (Render.com) — 15 minutes

```bash
# Prerequisites: GitHub repo with your Go backend

# 1. Go to render.com and connect GitHub
# 2. Create Web Service:
#    - Name: afrimine-api
#    - Runtime: Docker
#    - Region: Frankfurt (closest to Africa)
#    - Branch: main
#    - Instance Type: Free

# 3. Set environment variables:
#    DATABASE_URL=postgresql://postgres.[ref]:[pass]@aws-0-[region].pooler.supabase.com:6543/postgres
#    DIRECT_URL=postgresql://postgres.[ref]:[pass]@aws-0-[region].pooler.supabase.com:5432/postgres
#    SUPABASE_URL=https://[ref].supabase.co
#    SUPABASE_ANON_KEY=[your-key]
#    NVIDIA_NIM_API_KEY=[your-key]
#    SENTRY_DSN=[your-dsn]
#    APP_ENV=production
#    GIN_MODE=release
#    PORT=8080

# 4. Create render.yaml in repo root:
```

```yaml
# render.yaml
services:
  - type: web
    name: afrimine-api
    runtime: docker
    dockerfilePath: ./backend/Dockerfile
    region: frankfurt
    plan: free
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: DIRECT_URL
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: NVIDIA_NIM_API_KEY
        sync: false
      - key: GIN_MODE
        value: release
    healthCheckPath: /health
    autoDeploy: true

  - type: web
    name: afrimine-ai
    runtime: docker
    dockerfilePath: ./ai/Dockerfile
    region: frankfurt
    plan: free
    envVars:
      - key: DATABASE_URL
        sync: false
      - key: NVIDIA_NIM_API_KEY
        sync: false
    healthCheckPath: /health
    autoDeploy: true
```

```dockerfile
# backend/Dockerfile
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /server ./cmd/server

FROM alpine:3.19
RUN apk --no-cache add ca-certificates tzdata
WORKDIR /app
COPY --from=builder /server .
COPY --from=builder /app/migrations ./migrations
EXPOSE 8080
CMD ["./server"]
```

```dockerfile
# ai/Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

### 9.3 Phase 3: Frontend (Cloudflare Pages) — 10 minutes

```bash
# Option A: Direct upload (fastest)
# 1. Build locally
cd frontend
flutter build web --release --web-renderer canvaskit

# 2. Go to dash.cloudflare.com > Pages > Create project
# 3. Upload build/web folder directly

# Option B: Git integration (recommended)
# 1. Go to dash.cloudflare.com > Pages > Create project
# 2. Connect GitHub repo
# 3. Set build settings:
#    - Framework: None
#    - Build command: cd frontend && flutter build web --release
#    - Build output: frontend/build/web
# 4. Set environment variables:
#    - API_URL: https://afrimine-api.onrender.com
#    - SUPABASE_URL: https://[ref].supabase.co
#    - SUPABASE_ANON_KEY: [your-key]
```

### 9.4 Phase 4: Domain & DNS — 5 minutes

```bash
# If using free subdomain (recommended to start):
# Frontend: https://afrimine.pages.dev
# API:      https://afrimine-api.onrender.com

# If you buy a domain ($10/year for .co.ke):
# 1. Add domain to Cloudflare
# 2. Update nameservers at registrar
# 3. Add DNS records:

# In Cloudflare DNS:
# Type  Name  Content                        Proxy
# A     @     [Cloudflare Pages IP]          ✅
# CNAME api   afrimine-api.onrender.com       ✅
# CNAME ai    afrimine-ai.onrender.com        ✅

# In Cloudflare SSL/TLS:
# - Mode: Full (strict)
# - Always Use HTTPS: On
# - Minimum TLS Version: 1.2
```

### 9.5 Phase 5: Monitoring — 5 minutes

```bash
# Uptime Robot
# 1. Create account at uptimerobot.com
# 2. Add monitors:
#    - https://afrimine.pages.dev (HTTP, every 5 min)
#    - https://afrimine-api.onrender.com/health (HTTP, every 5 min)
#    - https://afrimine-ai.onrender.com/health (HTTP, every 5 min)
# 3. Add alert contacts:
#    - Email
#    - Telegram: Create bot via @BotFather, get token

# Sentry
# 1. Create project at sentry.io (free tier)
# 2. Copy DSN to environment variables
# 3. Errors auto-capture in both Go and Python

# Cold start prevention
# Set up a cron service to ping your Render endpoints:
# - Use cron-job.org (free) or Uptime Robot's built-in monitoring
# - Ping every 10 minutes: GET https://afrimine-api.onrender.com/health
```

### 9.6 Phase 6: NVIDIA NIM Integration — 5 minutes

```bash
# 1. Sign up at build.nvidia.com
# 2. Get API key (free credits for startups)
# 3. Set in environment variables

# Python AI service integration:
```

```python
# ai/services/nvidia_nim.py
import httpx
import os
from functools import lru_cache

NVIDIA_NIM_BASE = "https://integrate.api.nvidia.com/v1"
NVIDIA_API_KEY = os.environ["NVIDIA_NIM_API_KEY"]

class NIMClient:
    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=NVIDIA_NIM_BASE,
            headers={"Authorization": f"Bearer {NVIDIA_API_KEY}"},
            timeout=30.0,
        )
    
    async def analyze_safety(self, report_text: str, images: list[str] = None) -> dict:
        """Use NIM for safety analysis with vision + language models."""
        
        messages = [
            {
                "role": "system",
                "content": """You are a mining safety AI for African mines. 
                Analyze safety reports and provide:
                1. Risk score (0-100)
                2. Severity (low/medium/high/critical)
                3. Key hazards identified
                4. Recommended actions
                5. Regulatory compliance notes (Kenya Mining Act)
                
                Respond in JSON format."""
            },
            {
                "role": "user",
                "content": report_text
            }
        ]
        
        # Use NIM's meta/llama-3.1-8b-instruct (free tier)
        response = await self.client.post("/chat/completions", json={
            "model": "meta/llama-3.1-8b-instruct",
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 500,
            "response_format": {"type": "json_object"},
        })
        
        return response.json()["choices"][0]["message"]["content"]
    
    async def analyze_image(self, image_url: str) -> dict:
        """Use NIM vision model for image analysis."""
        
        response = await self.client.post("/chat/completions", json={
            "model": "meta/llama-3.2-11b-vision-instruct",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this mining site image for safety hazards. Identify: 1) Equipment issues 2) Environmental risks 3) Worker safety concerns 4) Structural problems. Respond in JSON."},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ],
            "max_tokens": 500,
        })
        
        return response.json()["choices"][0]["message"]["content"]
```

---

## 10. Production Hardening Checklist

### 10.1 Security

```bash
# ✅ Environment Variables (never commit secrets)
echo "*.env" >> .gitignore
echo "*.env.local" >> .gitignore

# ✅ Rate Limiting (Go backend)
# Using golang.org/x/time/rate
```

```go
// backend/middleware/ratelimit.go
package middleware

import (
    "net/http"
    "sync"
    "time"
    "golang.org/x/time/rate"
)

type RateLimiter struct {
    visitors map[string]*rate.Limiter
    mu       sync.RWMutex
    rate     rate.Limit
    burst    int
}

func NewRateLimiter(rps float64, burst int) *RateLimiter {
    return &RateLimiter{
        visitors: make(map[string]*rate.Limiter),
        rate:     rate.Limit(rps),
        burst:    burst,
    }
}

func (rl *RateLimiter) GetLimiter(ip string) *rate.Limiter {
    rl.mu.Lock()
    defer rl.mu.Unlock()
    
    limiter, exists := rl.visitors[ip]
    if !exists {
        limiter = rate.NewLimiter(rl.rate, rl.burst)
        rl.visitors[ip] = limiter
        
        // Cleanup old entries every 3 minutes
        go func() {
            time.Sleep(3 * time.Minute)
            rl.mu.Lock()
            delete(rl.visitors, ip)
            rl.mu.Unlock()
        }()
    }
    return limiter
}

// 10 requests/second per IP, burst of 20
var limiter = NewRateLimiter(10, 20)

func RateLimitMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        ip := r.RemoteAddr
        if !limiter.GetLimiter(ip).Allow() {
            http.Error(w, "Rate limit exceeded", http.StatusTooManyRequests)
            return
        }
        next.ServeHTTP(w, r)
    })
}
```

```bash
# ✅ CORS Configuration (Go backend)
```

```go
// backend/middleware/cors.go
func CORSMiddleware(allowedOrigins []string) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            origin := r.Header.Get("Origin")
            
            for _, allowed := range allowedOrigins {
                if origin == allowed {
                    w.Header().Set("Access-Control-Allow-Origin", origin)
                    break
                }
            }
            
            w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
            w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
            w.Header().Set("Access-Control-Max-Age", "86400")
            
            if r.Method == "OPTIONS" {
                w.WriteHeader(http.StatusOK)
                return
            }
            
            next.ServeHTTP(w, r)
        })
    }
}
```

### 10.2 Database Migrations

```bash
# Using golang-migrate (works with Supabase)
# Install: go install -tags 'postgres' github.com/golang-migrate/migrate/v4/cmd/migrate@latest

# Create migration
migrate create -ext sql -dir backend/migrations -seq create_profiles_table

# Apply migrations (use DIRECT_URL, not pooled)
migrate -path backend/migrations \
  -database "$DIRECT_URL" \
  up

# Rollback if needed
migrate -path backend/migrations \
  -database "$DIRECT_URL" \
  down 1
```

### 10.3 Health Checks

```go
// backend/handlers/health.go
func HealthHandler(db *sql.DB) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
        defer cancel()
        
        // Check database
        dbErr := db.PingContext(ctx)
        
        // Check NVIDIA NIM (cached, don't call every time)
        nimStatus := checkNIMCache()
        
        status := "healthy"
        httpCode := http.StatusOK
        
        if dbErr != nil {
            status = "degraded"
            httpCode = http.StatusServiceUnavailable
        }
        
        json.NewEncoder(w).Encode(map[string]interface{}{
            "status":    status,
            "database":  dbErr == nil,
            "nim":       nimStatus,
            "timestamp": time.Now().UTC(),
            "version":   os.Getenv("APP_VERSION"),
        })
    }
}
```

---

## 11. Scaling Path

### When Free Tier Isn't Enough

```
Phase 1: $0/month (Now)
├── Render.com Free (750h/mo)
├── Supabase Free (500MB)
├── Cloudflare Pages (unlimited)
└── GitHub Actions Free (2000 min)

Phase 2: ~$7/month (100+ users)
├── Render.com Starter ($7/mo per service) — no cold starts
├── Supabase Free (still enough)
├── Cloudflare Pages (still free)
└── Buy .co.ke domain ($10/year)

Phase 3: ~$25/month (1000+ users)
├── Oracle ARM Free (keep for AI service)
├── Render.com Starter ($7/mo × 2)
├── Supabase Pro ($25/mo) — 8GB, daily backups
├── Cloudflare Pro ($20/mo) — WAF, image optimization
└── Or: Migrate to Oracle ARM entirely ($0)

Phase 4: ~$100/month (10K+ users)
├── AWS/GCP with startup credits (apply!)
├── Kubernetes on Oracle ARM (free)
├── Dedicated PostgreSQL
└── CDN with Africa PoPs
```

### Startup Credits (Apply!)

| Provider | Credits | How to Get |
|----------|---------|------------|
| AWS Activate | $1,000-$100,000 | aws.amazon.com/activate |
| Google for Startups | $1,000-$200,000 | cloud.google.com/startup |
| Microsoft for Startups | $150,000 | microsoft.com/startups |
| NVIDIA Inception | NIM credits + support | nvidia.com/en-us/startups |
| DigitalOcean Hatch | $1,000-$100,000 | do.co/startups |
| Cloudflare Workers Launch | Free paid plan | cloudflare.com/launch |

---

## Quick Start Summary

```bash
# MINUTES 0-10: Database
# → Create Supabase project
# → Run SQL schema
# → Get connection strings

# MINUTES 10-25: Backend
# → Push code to GitHub
# → Create Render web service (free)
# → Set environment variables
# → Auto-deploys on push

# MINUTES 25-35: Frontend
# → Create Cloudflare Pages project
# → Connect GitHub or upload build
# → Set environment variables

# MINUTES 35-40: Monitoring
# → Create Uptime Robot monitors
# → Create Sentry project
# → Set up keep-alive pings

# MINUTES 40-45: AI Service
# → Create second Render service
# → Set NVIDIA NIM API key
# → Deploy

# TOTAL: 45 minutes to production on $0
```

---

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Render cold starts (15 min) | Slow first request | Uptime Robot keep-alive pings every 5 min |
| Supabase 500MB limit | Storage full | Archive old data, compress images, use Supabase Storage |
| Supabase 2 connection limit | Connection exhaustion | Use PgBouncer (built-in), connection pooling in Go |
| Poor rural connectivity | Users can't access | Offline-first with sync queue |
| Power outages | Data loss | Auto-save to local storage, sync when online |
| NVIDIA NIM rate limits | AI features blocked | Cache predictions, offline fallback model |
| Free tier changes | Service disruption | Multi-cloud strategy, Oracle ARM as backup |

---

**Total monthly cost: $0**  
**Time to production: 45 minutes**  
**Ready for: 100+ concurrent users**  
**Africa-optimized: Yes** (CDN edge, offline-first, low bandwidth)
