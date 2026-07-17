# AfriMine AI — DevOps Review Report

**Date:** 2026-07-18  
**Reviewer:** DevOps Fix Engineer  
**Status:** All 10 issues resolved

---

## Summary

| # | Issue | Severity | Status | Files Changed |
|---|-------|----------|--------|---------------|
| 1 | Hardcoded secrets in config | 🔴 Critical | ✅ Fixed | `config/development.yaml`, `.env.example`, `main.go` |
| 2 | Docker: missing labels | 🟡 Medium | ✅ Fixed | `docker/backend.Dockerfile`, `docker/ai-engine.Dockerfile` |
| 3 | SQL race condition in migrations | 🟡 Medium | ✅ Fixed | `supabase/migrations/001_initial_schema.sql` |
| 4 | CORS not restricted in nginx | 🔴 Critical | ✅ Fixed | `docker/nginx/nginx.conf` |
| 5 | Incomplete RLS policies | 🔴 Critical | ✅ Fixed | `supabase/migrations/001_initial_schema.sql` |
| 6 | Health check config incomplete | 🟡 Medium | ✅ Fixed | `render.yaml` |
| 7 | No error handling / rollback in deploy | 🔴 Critical | ✅ Fixed | `scripts/deploy.sh` |
| 8 | Rate limiting incomplete | 🟡 Medium | ✅ Fixed | `docker/nginx/nginx.conf` |
| 9 | Env var handling insecure | 🟡 Medium | ✅ Fixed | `scripts/deploy.sh`, `scripts/setup.sh`, `main.go`, `postgres.go` |
| 10 | No monitoring alert thresholds | 🟡 Medium | ✅ Fixed | `monitoring/uptimerobot-config.md` |

---

## Detailed Fixes

### 1. Hardcoded Secrets Removed

**Problem:** `config/development.yaml` contained hardcoded database credentials (`afrimine:afrimine_dev_pass`). `main.go` had default credentials (`postgres:postgres`). OTP debug code was logged and returned in API response.

**Fix:**
- `config/development.yaml`: Changed `url:` to `${DATABASE_URL}` (env var reference)
- `main.go`: Added `DatabaseURL` field, removed default password from `DBPassword`, changed `DBSSLMode` default from `disable` to `require`
- `postgres.go`: Added `URL` field to Config struct, prefer full `DATABASE_URL` over individual fields
- `.env.example`: Added security notes, changed JWT_SECRET placeholder to `CHANGE_ME_GENERATE_WITH_openssl_rand_base64_48`
- `handlers.go`: Verified OTP debug code already removed (was `"debug_code": code`)

### 2. Docker OCI Labels Added

**Problem:** Dockerfiles lacked OCI image labels for traceability.

**Fix:**
- Both `backend.Dockerfile` and `ai-engine.Dockerfile` now include:
  - `org.opencontainers.image.title`
  - `org.opencontainers.image.description`
  - `org.opencontainers.image.version` (build arg)
  - `org.opencontainers.image.created` (build arg)
  - `org.opencontainers.image.revision` (build arg)
  - `org.opencontainers.image.source`
  - `org.opencontainers.image.vendor`
  - `org.opencontainers.image.licenses`
- Added `ARG VERSION`, `ARG BUILD_DATE`, `ARG VCS_REF` build arguments
- AI Engine: Added `mkdir -p /app/cache /app/models && chown` for write permissions

### 3. SQL Race Condition Fixed

**Problem:** `generate_sample_code()` used `SELECT MAX(...)` with string parsing, which has a race condition on concurrent inserts — two inserts could generate the same code.

**Fix:**
- Replaced `SELECT COALESCE(MAX(...))` with a PostgreSQL `SEQUENCE`
- `CREATE SEQUENCE IF NOT EXISTS sample_code_seq START 1`
- `SELECT nextval('sample_code_seq') INTO next_num`
- Sequences are atomic and guarantee uniqueness under concurrency

### 4. CORS Restricted in Nginx

**Problem:** No CORS headers were set in nginx.conf. Any origin could make API requests.

**Fix:**
- Added `map $http_origin $cors_origin` block with explicit whitelist:
  - `https://afrimine.ai`
  - `https://www.afrimine.ai`
  - `https://afrimine.pages.dev`
- All other origins get empty string (no CORS header)
- Added `Access-Control-Allow-Origin`, `Allow-Methods`, `Allow-Headers`, `Allow-Credentials`, `Max-Age` headers
- Added `OPTIONS` preflight handling with `return 204`
- Added `Vary: Origin` header for proper caching
- Added `Content-Security-Policy` header
- Added `ssl_prefer_server_ciphers on`, `ssl_session_cache`, `ssl_session_timeout`

### 5. RLS Policies Expanded

**Problem:** Missing DELETE policies on most tables. `sync_queue` used overly broad `FOR ALL`. `analyses` had no UPDATE/DELETE policies. No admin management policies.

**Fix:**
- **Users**: Added INSERT policy, DELETE policy, admin ALL policy
- **Mine Sites**: Added DELETE policy, admin ALL policy
- **Samples**: Added DELETE policy, admin ALL policy
- **Analyses**: Added UPDATE policy (service role), admin ALL policy, user SELECT via user_id
- **Reports**: Added UPDATE policy, DELETE policy, admin ALL policy
- **Market Prices**: Added UPDATE policy, DELETE policy (service role)
- **Sync Queue**: Replaced `FOR ALL` with individual SELECT, INSERT, UPDATE, DELETE policies
- All UPDATE policies now include `WITH CHECK` clause for write validation

### 6. Health Check Config Enhanced

**Problem:** `render.yaml` had basic `healthCheckPath` but no documentation of health check behavior.

**Fix:**
- Added comments explaining Render's health check behavior:
  - Non-2xx responses mark service unhealthy
  - 30s response timeout (Render default)
  - 3 consecutive failures trigger restart
- Added `autoDeploy: true` to both web services
- Added documentation for AI Engine's longer start period

### 7. Deploy Script Error Handling + Rollback

**Problem:** `deploy.sh` used `set -euo pipefail` but had no rollback, no version tracking, no failure recovery, and used unsafe `source` for env loading.

**Fix:**
- **Safe env loading**: `load_env()` function validates key format (`^[A-Z_][A-Z0-9_]*$`), strips quotes, warns on world-readable files
- **Version tracking**: `track_deploy()` logs target, status, version, timestamp to `.deploy.log`
- **Rollback**: `rollback()` function provides platform-specific instructions (Render dashboard, Cloudflare Pages, Supabase)
- **Failure handling**: Each deploy function calls `rollback` on failure before exiting
- **Post-deploy validation**: `validate_deploy()` checks both backend and AI engine health
- **Signal handling**: `trap` for INT/TERM signals
- **New `rollback` target**: `scripts/deploy.sh rollback <target>`
- **Git version**: Captures `git rev-parse --short HEAD` for tracking

### 8. Rate Limiting Enhanced

**Problem:** Rate limiting existed but lacked connection limits, custom error pages, and proper 429 responses.

**Fix:**
- Added `limit_conn_zone $binary_remote_addr zone=conn_limit:10m`
- Added `limit_conn conn_limit 50` to limit concurrent connections per IP
- Added custom 429 error page handler:
  ```
  error_page 429 = @rate_limited;
  location @rate_limited {
      default_type application/json;
      return 429 '{"success":false,"error":"Rate limit exceeded."}';
  }
  ```
- Added default server block that returns 444 (drop unknown hosts)

### 9. Environment Variable Handling Fixed

**Problem:** `deploy.sh` used `source "$ENV_FILE"` which executes arbitrary shell code. `main.go` had hardcoded default credentials. No env validation.

**Fix:**
- `deploy.sh`: New `load_env()` function parses KEY=VALUE safely, validates key format, strips quotes, warns on insecure permissions
- `main.go`: Prefer `DATABASE_URL` env var, removed `postgres:postgres` defaults, changed SSL default to `require`
- `postgres.go`: Added `URL` field, prefer full connection string
- `setup.sh`: Added `chmod 600 .env`, added `validate_env()` function that checks for placeholder values
- `.env.example`: Added security notes and strong placeholder for JWT_SECRET

### 10. Monitoring Alert Thresholds Added

**Problem:** `uptimerobot-config.md` had monitor setup but no alert thresholds or response playbook.

**Fix:**
- Added **Critical** thresholds (immediate page):
  - Service down: 2 consecutive checks (10 min)
  - Response time > 10s: 3 consecutive checks
  - SSL expiring < 7 days
- Added **Warning** thresholds (email + Telegram):
  - Response time > 5s, error rate > 5%, CPU > 80%, memory > 85%, disk > 90%
- Added **Info** thresholds (dashboard only):
  - Response time > 2s, request volume spikes, cache hit rate < 70%
- Added **Sentry alert rules**: new issues, error spikes, regressions, slow transactions, AI timeouts
- Added **Response Playbook**: step-by-step for service down, high latency, error spikes

---

## Additional Fixes Applied

- **supabase/config.toml**: Changed `enable_confirmations = false` to `true` (email confirmation should always be required)
- **nginx.conf**: Added `Content-Security-Policy` header with appropriate directives
- **nginx.conf**: Added SSL session caching and cipher preferences

---

## Files Modified

1. `config/development.yaml` — Removed hardcoded DB credentials
2. `docker/backend.Dockerfile` — Added OCI labels, build args
3. `docker/ai-engine.Dockerfile` — Added OCI labels, build args, cache dir permissions
4. `docker/nginx/nginx.conf` — CORS, rate limiting, security headers, 429 handler
5. `supabase/migrations/001_initial_schema.sql` — RLS policies, sequence-based sample codes
6. `supabase/config.toml` — Email confirmation enabled
7. `render.yaml` — Health check documentation, autoDeploy
8. `scripts/deploy.sh` — Error handling, rollback, safe env loading, version tracking
9. `scripts/setup.sh` — Env validation, secure permissions
10. `src/backend/main.go` — DATABASE_URL support, removed default credentials
11. `src/backend/internal/database/postgres.go` — DATABASE_URL support
12. `.env.example` — Security notes, strong placeholders
13. `monitoring/uptimerobot-config.md` — Alert thresholds, response playbook
