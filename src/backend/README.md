# AfriMine AI — Go Backend Architecture

## Canonical Implementation

The backend uses a single, consolidated implementation:

- **`main.go`** — Entry point, router setup, graceful shutdown
- **`handlers/`** — HTTP handlers (auth, samples, analysis, reports, market)
- **`middleware/`** — JWT auth, rate limiting, role-based access
- **`a2a/`** — A2A JSON-RPC 2.0 client for Python bridge communication
- **`models/`** — Request/response types and domain models

### Removed (dead code)
The `internal/api/` directory contained a divergent implementation using `slog` logger,
different handler signatures, and different API paths. It was never wired into `main.go`
and has been removed to avoid confusion.

### Key Design Decisions
- Uses `zap` structured logger (not `slog`)
- Uses Chi router with standard middleware stack
- A2A bridge at `http://localhost:8000` by default
- JWT auth via Supabase tokens
