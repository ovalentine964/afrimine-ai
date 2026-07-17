# Health Check Endpoints Specification

## Backend API (`/health`)

**Endpoint:** `GET /health`
**Response (200):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": "2h30m15s",
  "timestamp": "2026-07-18T02:00:00Z",
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 12
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 2
    }
  }
}
```

**Response (503):**
```json
{
  "status": "unhealthy",
  "version": "1.0.0",
  "timestamp": "2026-07-18T02:00:00Z",
  "checks": {
    "database": {
      "status": "unhealthy",
      "error": "connection refused"
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 2
    }
  }
}
```

## AI Engine (`/health`)

**Endpoint:** `GET /health`
**Response (200):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "models": {
    "tflite": "loaded",
    "classifier": "ready"
  },
  "timestamp": "2026-07-18T02:00:00Z"
}
```

## Liveness vs Readiness

- `/health` — Full health check (checks dependencies)
- `/health/live` — Is the process alive? (always 200 if running)
- `/health/ready` — Can it serve traffic? (checks DB, Redis, models)

## Uptime Robot Integration

- **Monitor URL:** `https://api.afrimine.ai/health`
- **Check interval:** 5 minutes
- **Keyword monitor:** Look for `"status":"healthy"`
- **Alert threshold:** 2 consecutive failures
