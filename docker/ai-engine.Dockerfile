# AfriMine AI — Python AI Engine Dockerfile
# Multi-stage build for minimal production image

# ===== BUILD STAGE =====
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgdal-dev \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY src/ai-engine/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ===== RUNTIME STAGE =====
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal32 \
    gdal-bin \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -g 1001 afrimine && \
    useradd -u 1001 -g afrimine -m afrimine

WORKDIR /app

# Copy installed packages
COPY --from=builder /install /usr/local

# Copy application code
COPY src/ai-engine/ .

USER afrimine

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
