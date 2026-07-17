# Uptime Robot Configuration

## Monitors to Create

### 1. Backend API
- **URL:** `https://api.afrimine.ai/health`
- **Type:** HTTP(s)
- **Interval:** 5 minutes
- **Keyword:** `"status":"healthy"`
- **Alert contacts:** Your email + phone

### 2. AI Engine
- **URL:** `https://api.afrimine.ai/ai/health`
- **Type:** HTTP(s)
- **Interval:** 5 minutes
- **Keyword:** `"status":"healthy"`
- **Alert contacts:** Your email + phone

### 3. Frontend (Cloudflare Pages)
- **URL:** `https://afrimine.ai`
- **Type:** HTTP(s)
- **Interval:** 5 minutes
- **Keyword:** `AfriMine`
- **Alert contacts:** Your email

### 4. Database (Supabase)
- **URL:** `https://your-project.supabase.co/rest/v1/`
- **Type:** HTTP(s)
- **Interval:** 10 minutes
- **Expected status:** 200 or 401 (both mean DB is up)

## Alert Thresholds

### Critical (Immediate Alert — Email + SMS + Telegram)
| Metric | Threshold | Window | Action |
|--------|-----------|--------|--------|
| Service Down | HTTP 5xx or timeout | 2 consecutive checks (10 min) | Page on-call |
| Health Check Fail | Non-200 response | 2 consecutive checks (10 min) | Page on-call |
| Response Time | > 10 seconds | 3 consecutive checks (15 min) | Page on-call |
| SSL Certificate | Expiring in < 7 days | Daily check | Page on-call |
| Database Connection | Connection refused/timeout | 1 check | Page on-call |

### Warning (Email + Telegram)
| Metric | Threshold | Window | Action |
|--------|-----------|--------|--------|
| Response Time | > 5 seconds | 3 consecutive checks (15 min) | Email team |
| Error Rate | > 5% of requests | 15 min window | Email team |
| CPU Usage | > 80% | 10 min average | Email team |
| Memory Usage | > 85% | 10 min average | Email team |
| Disk Usage | > 90% | Hourly check | Email team |
| SSL Certificate | Expiring in < 30 days | Daily check | Email team |

### Info (Dashboard Only — No Alert)
| Metric | Threshold | Window |
|--------|-----------|--------|
| Response Time | > 2 seconds | 5 min average |
| Request Volume | Spike > 200% baseline | 1 hour |
| Cache Hit Rate | < 70% | 1 hour |
| Backup Age | > 24 hours | Daily check |

## Sentry Alert Rules

Configure in Sentry → Alerts:

### Error Alerts
1. **New Issue Detected** → Email immediately (first occurrence of new error)
2. **High Error Volume** → >10 errors in 1 hour → Slack/Telegram webhook
3. **Error Spike** → Error rate >2x baseline in 15 min → Email + Slack
4. **Regression** → Resolved issue re-opens → Email immediately

### Performance Alerts
1. **Slow Transaction** → p95 latency >5s → Email
2. **Database Slow Query** → Query time >2s → Email
3. **AI Inference Timeout** → Gemini call >30s → Email
4. **Memory Leak** → Memory growth >50MB/hour → Email

### Uptime Alerts
1. **Health Check Failure** → 2 consecutive failures → Page on-call
2. **Deploy Failure** → CI/CD pipeline failure → Email team

## UptimeRobot API Configuration

```bash
# Set your API key
UPTIMEROBOT_API_KEY="your-api-key"

# Create Backend monitor with alert thresholds
curl -X POST "https://api.uptimerobot.com/v2/newMonitor" \
  -H "Content-Type: application/json" \
  -H "Cache-Control: no-cache" \
  -d "{
    \"api_key\": \"$UPTIMEROBOT_API_KEY\",
    \"friendly_name\": \"AfriMine Backend API\",
    \"url\": \"https://api.afrimine.ai/health\",
    \"type\": 2,
    \"interval\": 300,
    \"keyword_type\": 1,
    \"keyword_value\": \"healthy\",
    \"timeout\": 10
  }"

# Create AI Engine monitor
curl -X POST "https://api.uptimerobot.com/v2/newMonitor" \
  -H "Content-Type: application/json" \
  -d "{
    \"api_key\": \"$UPTIMEROBOT_API_KEY\",
    \"friendly_name\": \"AfriMine AI Engine\",
    \"url\": \"https://api.afrimine.ai/ai/health\",
    \"type\": 2,
    \"interval\": 300,
    \"keyword_type\": 1,
    \"keyword_value\": \"healthy\",
    \"timeout\": 15
  }"

# Create Frontend monitor
curl -X POST "https://api.uptimerobot.com/v2/newMonitor" \
  -H "Content-Type: application/json" \
  -d "{
    \"api_key\": \"$UPTIMEROBOT_API_KEY\",
    \"friendly_name\": \"AfriMine Frontend\",
    \"url\": \"https://afrimine.ai\",
    \"type\": 2,
    \"interval\": 300,
    \"timeout\": 10
  }"
```

## Alert Channels

1. **Email:** Primary notification (all levels)
2. **Telegram Bot:** For instant critical alerts
   - Create bot via @BotFather
   - Add to UptimeRobot webhook alerts
3. **Slack/Discord webhook:** Team notifications (warning + critical)

## Response Playbook

### Service Down (Critical)
1. Check Render dashboard for service status
2. Check Sentry for recent errors
3. Review deploy log (`.deploy.log`) for recent changes
4. If caused by recent deploy: `scripts/deploy.sh rollback <target>`
5. If infrastructure issue: check Render status page
6. If persistent: escalate to manual investigation

### High Response Time (Warning)
1. Check if AI engine is under heavy load
2. Verify database connection pool isn't exhausted
3. Check Redis connectivity
4. Review nginx access logs for traffic spikes

### Error Rate Spike (Warning)
1. Check Sentry for new error patterns
2. Review recent code changes
3. Check external API status (Gemini, Supabase)
4. Verify environment variables haven't changed
