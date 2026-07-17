# AfriMine AI — Go Backend Dockerfile
# Multi-stage build for minimal production image

# ===== BUILD STAGE =====
FROM golang:1.22-alpine AS builder

RUN apk add --no-cache git ca-certificates tzdata

WORKDIR /app

# Cache dependencies
COPY src/backend/go.mod src/backend/go.sum* ./
RUN go mod download

# Copy source and build
COPY src/backend/ .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w -X main.version=$(cat VERSION 2>/dev/null || echo dev)" \
    -o /app/server ./cmd/server

# ===== RUNTIME STAGE =====
FROM alpine:3.19

RUN apk add --no-cache ca-certificates tzdata curl

# Non-root user
RUN addgroup -g 1001 -S afrimine && \
    adduser -u 1001 -S afrimine -G afrimine

WORKDIR /app

COPY --from=builder /app/server .
COPY --from=builder /app/migrations ./migrations

USER afrimine

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["./server"]
