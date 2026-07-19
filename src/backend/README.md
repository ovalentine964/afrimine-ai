# AfriMine AI — Go Backend API

Production-ready Go backend that connects Flutter clients to LangGraph agents via the A2A protocol.

## Architecture

```
Flutter App → Chi Router (Go) → A2A Bridge (JSON-RPC 2.0) → LangGraph (Python)
                ↓
           Supabase (PostgreSQL + Auth + Storage)
```

## Structure

```
src/backend/
├── main.go                 # Entry point — Chi router, middleware, graceful shutdown
├── go.mod                  # Go module dependencies
├── handlers/
│   ├── auth.go             # Supabase Auth (phone OTP, JWT, role management)
│   ├── samples.go          # Mineral sample CRUD (photo upload, GPS tagging)
│   ├── analysis.go         # Trigger analysis, get results, SSE streaming
│   ├── reports.go          # Report generation, PDF download
│   └── market.go           # Commodity prices, deposit valuation
├── middleware/
│   ├── auth.go             # JWT validation, role-based access control
│   ├── cors.go             # CORS configuration for Flutter web
│   └── ratelimit.go        # Per-role rate limiting
├── a2a/
│   ├── client.go           # A2A protocol client (JSON-RPC 2.0 over HTTP)
│   └── agent_cards.go      # Agent card discovery (/.well-known/agent.json)
└── models/
    ├── sample.go           # MineralSample, Location, XRFReadings
    ├── analysis.go         # Analysis pipeline result models (all 6 agents)
    └── report.go           # Report types and generation models
```

## API Endpoints

### Public (no auth)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (includes A2A bridge status) |
| GET | `/version` | Build version info |
| POST | `/v1/auth/phone` | Request phone OTP |
| POST | `/v1/auth/verify` | Verify OTP, get JWT |

### Protected (JWT required)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/auth/me` | Current user profile |
| POST | `/v1/samples` | Create mineral sample |
| GET | `/v1/samples` | List samples (paginated) |
| GET | `/v1/samples/{id}` | Get sample detail |
| PUT | `/v1/samples/{id}` | Update sample |
| DELETE | `/v1/samples/{id}` | Delete sample |
| POST | `/v1/samples/{id}/photo` | Upload sample photo |
| POST | `/v1/analyses` | Trigger analysis pipeline |
| GET | `/v1/analyses` | List analyses (paginated) |
| GET | `/v1/analyses/{id}` | Get analysis results |
| GET | `/v1/analyses/{id}/stream` | SSE stream of pipeline progress |
| POST | `/v1/analyses/{id}/cancel` | Cancel running analysis |
| POST | `/v1/reports/generate` | Generate report |
| GET | `/v1/reports` | List reports |
| GET | `/v1/reports/{id}` | Get report detail |
| GET | `/v1/reports/{id}/download` | Download report PDF |
| GET | `/v1/market/prices` | Current commodity prices |
| GET | `/v1/market/prices/{commodity}` | Single commodity price |
| GET | `/v1/market/valuation/{analysisID}` | Deposit valuation |
| GET | `/v1/agents` | List A2A agent cards |
| GET | `/v1/agents/{id}` | Get specific agent card |

### Admin (admin role required)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/admin/health` | Detailed admin health check |
| PUT | `/v1/auth/role` | Update user role |

## Roles

| Role | Permissions |
|------|-------------|
| `field_worker` | Create samples, trigger analyses, view own reports |
| `geologist` | All field_worker + validate analyses, edit knowledge base |
| `investor` | View reports, view market data (read-only) |
| `admin` | Full access, manage users, system config |

## Environment Variables

```bash
# Required
SUPABASE_JWT_SECRET=your-jwt-secret
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
A2A_BRIDGE_URL=http://localhost:8000

# Optional
PORT=8080
APP_ENV=development          # development | production
A2A_TIMEOUT=120s             # Timeout for A2A pipeline calls
```

## Running

```bash
# Development
go run main.go

# Build
go build -o afrimine-backend .

# With ldflags (for version info)
go build -ldflags "-X main.version=1.0.0 -X main.commit=$(git rev-parse --short HEAD)" -o afrimine-backend .
```

## Rate Limits

| Role | Requests/Minute |
|------|----------------|
| field_worker | 30 |
| geologist | 60 |
| investor | 20 |
| admin | 120 |
| unauthenticated | 10 |

## Key Design Decisions

- **Chi Router**: Lightweight, idiomatic Go, middleware-friendly (vs. Gin/Echo)
- **A2A Protocol**: JSON-RPC 2.0 for Go ↔ Python communication (language-agnostic, debuggable)
- **Supabase Auth**: Phone OTP for field workers, JWT for all API calls
- **SSE Streaming**: Real-time pipeline progress updates to Flutter clients
- **Graceful Shutdown**: Handles SIGINT/SIGTERM, drains connections
- **Structured Logging**: Zap logger with request tracing via X-Request-ID
