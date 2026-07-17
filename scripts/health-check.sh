#!/usr/bin/env bash
# AfriMine AI — Health Check Script
# Used by monitoring and CI/CD
set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"
TIMEOUT=10

echo "AfriMine AI Health Check"
echo "========================"
echo ""

check_endpoint() {
    local name="$1"
    local url="$2"
    local start_time
    start_time=$(date +%s%N)

    local response
    local http_code

    response=$(curl -sf --max-time "$TIMEOUT" -w "\n%{http_code}" "$url" 2>/dev/null) || {
        echo "❌ $name — UNREACHABLE ($url)"
        return 1
    }

    http_code=$(echo "$response" | tail -1)
    local body
    body=$(echo "$response" | head -n -1)

    local end_time
    end_time=$(date +%s%N)
    local duration_ms=$(( (end_time - start_time) / 1000000 ))

    if [ "$http_code" = "200" ]; then
        echo "✅ $name — OK (${duration_ms}ms)"
        echo "   $body"
        return 0
    else
        echo "❌ $name — HTTP $http_code (${duration_ms}ms)"
        echo "   $body"
        return 1
    fi
}

FAILURES=0

check_endpoint "Backend API"   "${BASE_URL}/health"           || ((FAILURES++))
check_endpoint "AI Engine"     "${BASE_URL}/ai/health"        || ((FAILURES++))

echo ""
if [ "$FAILURES" -eq 0 ]; then
    echo "All services healthy ✅"
    exit 0
else
    echo "$FAILURES service(s) unhealthy ❌"
    exit 1
fi
