# Uptime Monitoring — AfriMine AI

## Overview

Uptime Robot provides HTTP/HTTPS monitoring with 5-minute check intervals.

**Free tier:** 50 monitors, 5-min intervals, 5 status pages, email/SMS alerts.

---

## 1. Monitors to Create

### Core Services

| # | Monitor Name | URL | Type | Expected |
|---|-------------|-----|------|----------|
| 1 | Frontend (Production) | `https://afrimine.com` | HTTP(s) | 200 |
| 2 | API Health (Production) | `https://api.afrimine.com/health` | HTTP(s) | 200, contains `ok` |
| 3 | A2A Health (Production) | `https://api.afrimine.com/a2a/health` | HTTP(s) | 200, contains `ok` |
| 4 | Frontend (Staging) | `https://staging.afrimine.com` | HTTP(s) | 200 |
| 5 | API Health (Staging) | `https://staging-api.afrimine.com/health` | HTTP(s) | 200 |

### External Dependencies

| # | Monitor Name | URL | Type | Expected |
|---|-------------|-----|------|----------|
| 6 | Supabase Status | `https://status.supabase.com` | HTTP(s) | 200 |
| 7 | Gemini API | `https://generativelanguage.googleapis.com/` | Keyword | 200 |
| 8 | Cloudflare Status | `https://www.cloudflarestatus.com` | HTTP(s) | 200 |

### Endpoint Deep Checks

| # | Monitor Name | URL | Method | Expected |
|---|-------------|-----|--------|----------|
| 9 | API Auth Check | `https://api.afrimine.com/v1/analyses` | POST | 401 (not 500) |
| 10 | Agent Pipeline | `https://api.afrimine.com/a2a/.well-known/agent.json` | GET | 200, valid JSON |

---

## 2. Setup Steps

### 2.1 Create Account

1. Go to [uptimerobot.com](https://uptimerobot.com)
2. Sign up with team email
3. Create alert contacts:
   - Email: `devops@afrimine.com`
   - Slack webhook (optional): `#alerts` channel

### 2.2 Create Monitors

For each monitor above:

1. **Add New Monitor** → HTTP(s)
2. Enter URL
3. Set monitoring interval: 5 minutes
4. Set alert contacts
5. For keyword monitors: add "expected string" check

### 2.3 Status Page

1. Create public status page: `status.afrimine.com`
2. Add all production monitors (1-3, 6-10)
3. Customize with AfriMine logo and colors
4. Set CNAME: `status.afrimine.com` → `stats.uptimerobot.com`

---

## 3. Alert Configuration

### Alert Thresholds

| Alert Type | Trigger | Channels |
|-----------|---------|----------|
| **Down** | 2+ consecutive failures (10 min) | Email + Slack |
| **Up** | Service recovered | Email |
| **Slow** | Response >5s for 3+ checks | Email |
| **SSL** | Certificate expires in <7 days | Email |

### Escalation (Manual)

Since we're on the free tier, escalation is manual:

1. **P0 (Production down):** Team gets email → check Sentry → check Railway logs → rollback if needed
2. **P1 (Staging down):** Team gets email → fix before next production deploy
3. **P2 (Slow response):** Weekly review of slow alerts

---

## 4. Integration with CI/CD

Add post-deploy health verification in GitHub Actions:

```yaml
# Already implemented in deploy-production.yml:
# - Frontend health check
# - API health check
# - A2A health check
# - Smoke test analysis endpoint
```

---

## 5. Downtime Runbook

### When Monitor Reports Down

1. **Check Sentry** — any new errors? Spike in existing errors?
2. **Check Railway logs** — `railway logs --service <name>`
3. **Check Supabase status** — `status.supabase.com`
4. **Check Cloudflare** — `cloudflarestatus.com`

### If Go API is Down

```bash
# Check Railway service status
railway status

# View recent logs
railway logs --service go-api --tail 100

# Restart service
railway service restart --service go-api

# If persistent, rollback to previous deploy
railway rollback --service go-api
```

### If Python Agents are Down

```bash
# Check Railway
railway status
railway logs --service langgraph --tail 100

# Common causes:
# - Gemini API rate limit → check GOOGLE_API_KEY quota
# - Memory exceeded → check if embedding generation caused OOM
# - Supabase connection pool exhausted → check connection count

# Restart
railway service restart --service langgraph
```

### If Frontend is Down

```bash
# Check Cloudflare Pages status
wrangler pages deployment list --project-name=afrimine-web

# Redeploy from last known good
wrangler pages deployment create --project-name=afrimine-web --branch=main
```

---

## 6. Cost & Limits

| Metric | Free Tier | Usage (Expected) | Headroom |
|--------|----------|-----------------|----------|
| Monitors | 50 | 10 | 40 free |
| Check interval | 5 min | 5 min | — |
| Status pages | 5 | 1 | 4 free |
| SMS alerts | 20/month | 0 (use email) | 20 free |
| Logs retention | 30 days | — | — |

**Upgrade ($7/mo):** 1-min intervals, 80 monitors, SMS to more numbers. Not needed for MVP.
