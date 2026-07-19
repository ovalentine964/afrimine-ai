#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────
# AfriMine AI — Android APK Build Script
#
# Builds optimized APKs for field deployment on low-end Android devices.
# Targets arm64-v8a (modern) and armeabi-v7a (older phones).
#
# Usage:
#   ./scripts/build-apk.sh                    # Release build
#   ./scripts/build-apk.sh --debug            # Debug build
#   ./scripts/build-apk.sh --api-url URL      # Custom API URL
#
# Output:
#   build/app/outputs/flutter-apk/app-arm64-v8a-release.apk
#   build/app/outputs/flutter-apk/app-armeabi-v7a-release.apk
# ─────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/src/frontend"
OUTPUT_DIR=""

# ── Defaults ─────────────────────────────────────────────────────────────
BUILD_MODE="release"
API_URL="https://api.afrimine.com"
SPLIT_PER_ABI=true

# ── Parse args ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --debug)
            BUILD_MODE="debug"
            SPLIT_PER_ABI=false
            shift
            ;;
        --api-url)
            API_URL="$2"
            shift 2
            ;;
        --no-split)
            SPLIT_PER_ABI=false
            shift
            ;;
        --help)
            echo "Usage: $0 [--debug] [--api-url URL] [--no-split]"
            echo ""
            echo "Options:"
            echo "  --debug       Build debug APK (no minification)"
            echo "  --api-url URL Set API backend URL (default: https://api.afrimine.com)"
            echo "  --no-split    Build single fat APK instead of per-ABI splits"
            echo ""
            echo "Output:"
            echo "  build/app/outputs/flutter-apk/app-arm64-v8a-release.apk"
            echo "  build/app/outputs/flutter-apk/app-armeabi-v7a-release.apk"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ── Pre-flight checks ───────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════╗"
echo "║          AfriMine AI — APK Builder                  ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Build mode:  $BUILD_MODE"
echo "  API URL:     $API_URL"
echo "  Split/ABI:   $SPLIT_PER_ABI"
echo ""

# Check Flutter
if ! command -v flutter &> /dev/null; then
    echo "❌ Flutter not found. Install from https://flutter.dev"
    exit 1
fi

echo "Flutter version:"
flutter --version
echo ""

# ── Navigate to frontend ────────────────────────────────────────────────
cd "$FRONTEND_DIR"

# ── Clean previous builds ───────────────────────────────────────────────
echo "🧹 Cleaning previous builds..."
flutter clean
echo ""

# ── Get dependencies ────────────────────────────────────────────────────
echo "📦 Getting dependencies..."
flutter pub get
echo ""

# ── Build APK ───────────────────────────────────────────────────────────
BUILD_ARGS=(
    "build" "apk"
    "--$BUILD_MODE"
    "--dart-define=API_URL=$API_URL"
)

if [[ "$SPLIT_PER_ABI" == "true" ]]; then
    BUILD_ARGS+=("--split-per-abi")
fi

echo "🔨 Building APK..."
echo "   Command: flutter ${BUILD_ARGS[*]}"
echo ""
flutter "${BUILD_ARGS[@]}"

# ── Report output ───────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║                 ✅ Build Complete!                   ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

APK_DIR="build/app/outputs/flutter-apk"
if [[ -d "$APK_DIR" ]]; then
    echo "📱 APK files:"
    ls -lh "$APK_DIR"/*.apk 2>/dev/null || echo "   (no APK files found)"
    echo ""
    echo "📂 Location: $(pwd)/$APK_DIR"

    # Calculate sizes
    for apk in "$APK_DIR"/*.apk; do
        if [[ -f "$apk" ]]; then
            SIZE=$(du -h "$apk" | cut -f1)
            BASENAME=$(basename "$apk")
            echo "   $BASENAME — $SIZE"
        fi
    done
else
    echo "⚠️  APK output directory not found at $APK_DIR"
fi

echo ""
echo "💡 To install on a connected device:"
echo "   flutter install"
echo ""
echo "💡 To distribute:"
echo "   Upload APKs to your distribution channel or share directly."
