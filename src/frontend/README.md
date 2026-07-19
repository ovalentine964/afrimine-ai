# AfriMine AI — Flutter Frontend

Mobile app for field workers to analyze minerals in African mining communities.

## Architecture

- **State Management:** Riverpod (flutter_riverpod)
- **Routing:** go_router
- **Offline-first:** SQLite (sqflite) with sync queue
- **Voice:** Vosk STT (offline) + Flutter TTS (Piper wrapper)
- **Camera:** camera package with GPS auto-tagging (geolocator)
- **Maps:** MapLibre GL (offline-capable)
- **HTTP:** Dio with offline queue and retry

## Directory Structure

```
lib/
├── main.dart              # App entry, Riverpod scope, routing, theme
├── models/
│   ├── sample.dart        # MineralSample, SampleLocation, XrfReadings
│   └── analysis.dart      # Analysis, agent results, streaming updates
├── screens/
│   ├── home_screen.dart   # Dashboard: recent analyses, quick actions
│   ├── camera_screen.dart # Camera capture with GPS + color reference
│   ├── analysis_screen.dart # View analysis results + streaming progress
│   ├── reports_screen.dart  # List/filter/view generated reports
│   ├── map_screen.dart    # MapLibre map with sample pins
│   ├── voice_screen.dart  # Push-to-talk voice interface
│   └── settings_screen.dart # API keys, sync, language, offline mode
├── services/
│   ├── api_service.dart   # HTTP client → Go backend (Dio, auth, offline queue)
│   ├── offline_service.dart # SQLite offline storage + sync queue
│   ├── camera_service.dart  # Camera + GPS + photo compression
│   └── voice_service.dart   # Vosk STT + Flutter TTS integration
└── widgets/
    ├── mineral_card.dart    # Reusable mineral result card
    └── sync_indicator.dart  # Online/offline sync status indicator
```

## Key Design Decisions

1. **Offline-first:** All data cached in SQLite. Sync queue handles uploads when online.
2. **Budget phones:** Photo compression (medium resolution, ~500KB target), minimal animations.
3. **Field workers:** Large touch targets, push-to-talk voice, GPS auto-tagging.
4. **6-agent pipeline:** Results from Sampling → Analysis → Geology ∥ Market → Report → Compliance.
5. **Voice in Dholuo/Swahili:** Vosk for offline STT, Flutter TTS for speech output.

## Building

```bash
# Install dependencies
flutter pub get

# Run on Android device
flutter run

# Build APK
flutter build apk --release
```

## Environment

Set API endpoint in Settings screen or via environment:
- `API_BASE_URL` — Go backend URL (default: https://api.afrimine.com)
- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_ANON_KEY` — Supabase anonymous key
