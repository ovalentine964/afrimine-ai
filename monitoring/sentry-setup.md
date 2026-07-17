# Sentry Error Tracking Setup

## 1. Create Sentry Project

1. Go to [sentry.io](https://sentry.io)
2. Create project → Select "Go" for backend, "Python" for AI engine
3. Copy the DSN

## 2. Go Backend Integration

Add to `go.mod`:
```
github.com/getsentry/sentry-go v0.27.0
```

Add to your server initialization:
```go
import sentry "github.com/getsentry/sentry-go"

func init() {
    sentry.Init(sentry.ClientOptions{
        Dsn:              os.Getenv("SENTRY_DSN"),
        Environment:      os.Getenv("APP_ENV"),
        TracesSampleRate: 0.1,
        BeforeSend: func(event *sentry.Event, hint *sentry.EventHint) *sentry.Event {
            // Don't send health check errors
            if event.Request != nil && event.Request.URL == "/health" {
                return nil
            }
            return event
        },
    })
}
```

Add middleware for panic recovery:
```go
func sentryMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        defer func() {
            if err := recover(); err != nil {
                sentry.CurrentHub().Recover(err)
                sentry.Flush(time.Second * 5)
                http.Error(w, "Internal Server Error", 500)
            }
        }()
        next.ServeHTTP(w, r)
    })
}
```

## 3. Python AI Engine Integration

Install:
```bash
pip install sentry-sdk[fastapi]
```

Add to `main.py`:
```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("APP_ENV", "development"),
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1,
    integrations=[FastApiIntegration()],
)
```

## 4. Flutter Frontend Integration

Add to `pubspec.yaml`:
```yaml
dependencies:
  sentry_flutter: ^8.0.0
```

Add to `main.dart`:
```dart
import 'package:sentry_flutter/sentry_flutter.dart';

Future<void> main() async {
  await SentryFlutter.init(
    (options) {
      options.dsn = const String.fromEnvironment('SENTRY_DSN');
      options.environment = const String.fromEnvironment('APP_ENV', defaultValue: 'development');
      options.tracesSampleRate = 0.1;
    },
    appRunner: () => runApp(const AfriMineApp()),
  );
}
```

## 5. GitHub Actions Integration

Add to deploy workflow for release tracking:
```yaml
- name: Create Sentry release
  uses: getsentry/action-release@v1
  env:
    SENTRY_AUTH_TOKEN: ${{ secrets.SENTRY_AUTH_TOKEN }}
    SENTRY_ORG: afrimine
    SENTRY_PROJECT: afrimine-backend
  with:
    environment: production
    version: ${{ github.sha }}
```

## 6. Alert Rules

Configure in Sentry → Alerts:
1. **New issue:** Email immediately
2. **High volume:** >10 errors in 1 hour → Slack
3. **Performance:** Transaction >5s → Email
