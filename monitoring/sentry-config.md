# Sentry Setup — AfriMine AI

## Overview

Sentry provides error tracking, performance monitoring, and release health for all AfriMine AI services.

**Free tier:** 5K errors/month, 10K performance transactions, 1GB attachments.

---

## 1. Create Sentry Project

1. Go to [sentry.io](https://sentry.io) → Create organization `afrimine`
2. Create 3 projects:

| Project | Platform | DSN Name |
|---------|----------|----------|
| `afrimine-api` | Go | `SENTRY_DSN_GO` |
| `afrimine-agents` | Python | `SENTRY_DSN_PYTHON` |
| `afrimine-flutter` | Dart/Flutter | `SENTRY_DSN_FLUTTER` |

3. Copy DSN values — store in GitHub Secrets and Railway variables.

---

## 2. Go Backend Integration

```go
// cmd/api/main.go
import (
    "github.com/getsentry/sentry-go"
    sentryhttp "github.com/getsentry/sentry-go/http"
)

func main() {
    err := sentry.Init(sentry.ClientOptions{
        Dsn:              os.Getenv("SENTRY_DSN"),
        Environment:      os.Getenv("ENV"),  // "production", "staging"
        Release:          os.Getenv("VERSION"),  // git tag
        TracesSampleRate: 0.1,  // 10% of transactions
        BeforeSend: func(event *sentry.Event, hint *sentry.EventHint) *sentry.Event {
            // Strip sensitive data
            if event.Request != nil {
                event.Request.Headers["Authorization"] = "[REDACTED]"
            }
            return event
        },
    })
    if err != nil {
        log.Fatalf("sentry.Init: %s", err)
    }
    defer sentry.Flush(2 * time.Second)

    // Wrap HTTP handler
    sentryHandler := sentryhttp.New(sentryhttp.Options{
        Repanic:         true,
        WaitForDelivery: true,
    })

    r := chi.NewRouter()
    r.Use(sentryHandler.Handle)
    // ... rest of your routes
}
```

---

## 3. Python LangGraph Integration

```python
# a2a_bridge.py or config.py
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.asyncio import AsyncioIntegration

sentry_sdk.init(
    dsn=os.environ["SENTRY_DSN"],
    environment=os.environ.get("LANGGRAPH_ENV", "production"),
    release=os.environ.get("VERSION", "dev"),
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1,
    integrations=[
        LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        AsyncioIntegration(),
    ],
    before_send=strip_sensitive_data,
)

def strip_sensitive_data(event, hint):
    """Remove API keys and PII before sending to Sentry."""
    if "extra" in event:
        for key in list(event["extra"].keys()):
            if any(s in key.lower() for s in ["key", "token", "secret", "password"]):
                event["extra"][key] = "[REDACTED]"
    return event
```

---

## 4. Flutter Integration

```dart
// lib/main.dart
import 'package:sentry_flutter/sentry_flutter.dart';

Future<void> main() async {
  await SentryFlutter.init(
    (options) {
      options.dsn = const String.fromEnvironment('SENTRY_DSN_FLUTTER');
      options.environment = const String.fromEnvironment('ENV', defaultValue: 'production');
      options.tracesSampleRate = 0.1;
      options.attachScreenshot = true;
      options.screenshotQuality = SentryScreenshotQuality.low;
      // Don't send PII
      options.sendDefaultPii = false;
    },
    appRunner: () => runApp(const AfriMineApp()),
  );
}
```

---

## 5. Alert Rules

Configure in Sentry → Alerts → Create Alert Rule:

### Critical (PagerDuty/Slack)

| Trigger | Condition | Action |
|---------|-----------|--------|
| New error | First seen in production | Slack #alerts channel |
| Error spike | >10 errors in 5 min | Slack + email |
| Performance | p95 latency >5s | Slack #backend |

### Warning (Email)

| Trigger | Condition | Action |
|---------|-----------|--------|
| Error frequency | >50 errors/hour | Email team |
| Release health | <95% crash-free sessions | Email team |

---

## 6. Source Maps (Flutter Web)

```yaml
# .github/workflows/deploy-production.yml — add after flutter build
- name: Upload source maps to Sentry
  run: |
    npx @sentry/cli releases new ${{ needs.gate.outputs.tag }}
    npx @sentry/cli releases files ${{ needs.gate.outputs.tag }} \
      upload-smap build/web/main.dart.js.map \
      --url-prefix "~/main.dart.js"
    npx @sentry/cli releases finalize ${{ needs.gate.outputs.tag }}
  env:
    SENTRY_AUTH_TOKEN: ${{ secrets.SENTRY_AUTH_TOKEN }}
    SENTRY_ORG: afrimine
    SENTRY_PROJECT: afrimine-flutter
```

---

## 7. Breadcrumbs for Agent Pipeline

```python
# In each agent node, add breadcrumbs for debugging
import sentry_sdk

async def analysis_agent(state):
    sentry_sdk.add_breadcrumb(
        category="agent",
        message="Analysis agent started",
        level="info",
        data={"analysis_id": state.get("analysis_id"), "sample_count": len(state.get("sample_data", {}))}
    )
    # ... agent logic ...
    sentry_sdk.add_breadcrumb(
        category="agent",
        message="Analysis agent completed",
        level="info",
        data={"confidence": result.get("overall_confidence"), "minerals": result.get("detected_minerals")}
    )
    return result
```

---

## 8. Cost Monitoring

| Metric | Free Limit | When to Upgrade |
|--------|-----------|-----------------|
| Errors | 5K/month | >4K (80%) |
| Transactions | 10K/month | >8K (80%) |
| Attachments | 1GB | >800MB |
| Retention | 30 days | Need 90+ days |

**Upgrade path:** Team plan ($26/month) → 50K errors, 100K transactions, 90-day retention.

---

## 9. Environment Variables

Set in GitHub Secrets and Railway:

```
SENTRY_DSN=https://xxx@sentry.io/xxx        # Per-project DSN
SENTRY_AUTH_TOKEN=sntrys_xxx                  # For source map uploads
SENTRY_ORG=afrimine
SENTRY_PROJECT=afrimine-api                   # or afrimine-agents, afrimine-flutter
```
