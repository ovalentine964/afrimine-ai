/// AfriMine AI — App Configuration
///
/// All values are injected at compile time via `--dart-define`.
/// This keeps secrets out of source code and allows per-environment builds.
///
/// Usage:
///   flutter run --dart-define=API_URL=http://192.168.1.100:8080
///   flutter build apk --dart-define=API_URL=https://api.afrimine.com
///
class AppConfig {
  AppConfig._();

  // ── API ──────────────────────────────────────────────────────────────

  /// Backend API base URL.
  /// Default: http://localhost:8080 (local dev).
  /// Production builds pass --dart-define=API_URL=https://api.afrimine.com
  static const String apiUrl = String.fromEnvironment(
    'API_URL',
    defaultValue: 'http://localhost:8080',
  );

  /// Supabase project URL (for direct auth if needed).
  static const String supabaseUrl = String.fromEnvironment(
    'SUPABASE_URL',
    defaultValue: '',
  );

  /// Supabase anonymous key.
  static const String supabaseAnonKey = String.fromEnvironment(
    'SUPABASE_ANON_KEY',
    defaultValue: '',
  );

  // ── NVIDIA / On-device Inference ─────────────────────────────────────

  /// NVIDIA API key for on-device model inference (if used).
  /// NEVER hardcode — pass via --dart-define or CI secrets.
  static const String nvidiaApiKey = String.fromEnvironment(
    'NVIDIA_API_KEY',
    defaultValue: '',
  );

  /// NVIDIA inference endpoint.
  static const String nvidiaEndpoint = String.fromEnvironment(
    'NVIDIA_ENDPOINT',
    defaultValue: 'https://integrate.api.nvidia.com/v1',
  );

  // ── Feature Flags ────────────────────────────────────────────────────

  /// Enable offline-first mode (always true for field use).
  static const bool offlineModeEnabled = bool.fromEnvironment(
    'OFFLINE_MODE',
    defaultValue: true,
  );

  /// Enable voice input/output (requires microphone permission).
  static const bool voiceEnabled = bool.fromEnvironment(
    'VOICE_ENABLED',
    defaultValue: true,
  );

  /// Enable on-device mineral identification model.
  static const bool onDeviceInferenceEnabled = bool.fromEnvironment(
    'ON_DEVICE_INFERENCE',
    defaultValue: false,
  );

  /// Enable map features (requires location permission).
  static const bool mapsEnabled = bool.fromEnvironment(
    'MAPS_ENABLED',
    defaultValue: true,
  );

  /// Enable analytics collection (opt-in for privacy).
  static const bool analyticsEnabled = bool.fromEnvironment(
    'ANALYTICS_ENABLED',
    defaultValue: false,
  );

  // ── App Metadata ─────────────────────────────────────────────────────

  static const String appName = 'AfriMine AI';
  static const String appVersion = '1.0.0';
  static const int appBuildNumber = 1;

  /// Minimum sync interval to conserve data on limited plans.
  static const Duration syncInterval = Duration(minutes: 15);

  /// Max photo size before compression (bytes). Target: ~500KB.
  static const int maxPhotoSizeBytes = 512 * 1024;

  /// JPEG quality for photo compression (1-100).
  static const int photoCompressionQuality = 75;

  // ── Debug Helpers ────────────────────────────────────────────────────

  /// Whether we're running in debug mode (compile-time constant).
  static const bool isDebug = bool.fromEnvironment('dart.tool.dartdoc')
      ? false
      : true; // Will be false in release builds

  /// Dump config to map (for settings screen, never log secrets).
  static Map<String, dynamic> toMap() => {
        'apiUrl': apiUrl,
        'supabaseUrl': supabaseUrl.isNotEmpty ? '(set)' : '(not set)',
        'nvidiaApiKey': nvidiaApiKey.isNotEmpty ? '(set)' : '(not set)',
        'offlineModeEnabled': offlineModeEnabled,
        'voiceEnabled': voiceEnabled,
        'onDeviceInferenceEnabled': onDeviceInferenceEnabled,
        'mapsEnabled': mapsEnabled,
        'analyticsEnabled': analyticsEnabled,
        'appVersion': appVersion,
      };
}
