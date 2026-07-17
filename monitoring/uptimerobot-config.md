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

## Setup via API (Automated)

```bash
# Set your API key
UPTIMEROBOT_API_KEY="your-api-key"

# Create Backend monitor
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
    \"keyword_value\": \"healthy\"
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
    \"keyword_value\": \"healthy\"
  }"

# Create Frontend monitor
curl -X POST "https://api.uptimerobot.com/v2/newMonitor" \
  -H "Content-Type: application/json" \
  -d "{
    \"api_key\": \"$UPTIMEROBOT_API_KEY\",
    \"friendly_name\": \"AfriMine Frontend\",
    \"url\": \"https://afrimine.ai\",
    \"type\": 2,
    \"interval\": 300
  }"
```

## Alert Channels

1. **Email:** Primary notification
2. **Telegram Bot:** For instant alerts (optional)
   - Create bot via @BotFather
   - Add to UptimeRobot webhook alerts
3. **Slack/Discord webhook:** Team notifications (optional)
