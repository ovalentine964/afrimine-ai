# AfriMine AI — Go Backend Dockerfile
# Multi-stage build for minimal production image

# ===== BUILD STAGE =====
FROM golang:1.22-alpine AS builder

ARG VERSION=dev
ARG BUILD_DATE
ARG VCS_REF

RUN apk add --no-cache git ca-certificates tzdata

WORKDIR /app

# Cache dependencies
COPY src/backend/go.mod src/backend/go.sum* ./
RUN go mod download

# Copy source and build
COPY src/backend/ .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w -X main.version=${VERSION}" \
    -o /app/server ./cmd/server

# ===== RUNTIME STAGE =====
FROM alpine:3.19

ARG VERSION=dev
ARG BUILD_DATE
ARG VCS_REF

LABEL org.opencontainers.image.title="afrimine-backend" \
      org.opencontainers.image.description="AfriMine AI Go Backend API" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="https://github.com/ovalentine964/afrimine-ai" \
      org.opencontainers.image.vendor="AfriMine AI" \
      org.opencontainers.image.licenses="MIT"

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
