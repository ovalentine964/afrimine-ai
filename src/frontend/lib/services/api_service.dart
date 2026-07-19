import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:logger/logger.dart';

import '../models/analysis.dart';
import '../models/sample.dart';
import 'offline_service.dart';

final _logger = Logger(printer: PrettyPrinter(methodCount: 0));

/// API configuration — set at startup from settings or env.
///
/// For local development, run with:
///   flutter run --dart-define=API_URL=http://localhost:8080
///
/// For production, defaults to the production API.
class ApiConfig {
  final String baseUrl;
  final String? supabaseUrl;
  final String? supabaseAnonKey;
  final Duration timeout;

  const ApiConfig({
    String? baseUrl,
    this.supabaseUrl,
    this.supabaseAnonKey,
    this.timeout = const Duration(seconds: 60),
  }) : baseUrl = baseUrl ?? _defaultBaseUrl;

  /// Read from --dart-define at compile time, fall back to production URL.
  static const String _defaultBaseUrl =
      String.fromEnvironment('API_URL', defaultValue: 'https://api.afrimine.com');
}

/// Riverpod providers for API service.
final apiConfigProvider = StateProvider<ApiConfig>((ref) => const ApiConfig());

final apiServiceProvider = Provider<ApiService>((ref) {
  final config = ref.watch(apiConfigProvider);
  final offlineService = ref.watch(offlineServiceProvider);
  return ApiService(config: config, offlineService: offlineService);
});

/// HTTP client for the AfriMine Go backend.
///
/// Features:
/// - Automatic JWT token management
/// - Offline queue for failed requests
/// - Retry with exponential backoff
/// - SSE streaming for analysis progress
class ApiService {
  final ApiConfig config;
  final OfflineService offlineService;
  late final Dio _dio;
  final _secureStorage = const FlutterSecureStorage();

  String? _accessToken;
  String? _refreshToken;

  ApiService({required this.config, required this.offlineService}) {
    _dio = Dio(BaseOptions(
      baseUrl: config.baseUrl,
      connectTimeout: config.timeout,
      receiveTimeout: config.timeout,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    ));

    // Interceptor: attach auth token
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        if (_accessToken != null) {
          options.headers['Authorization'] = 'Bearer $_accessToken';
        }
        _logger.d('→ ${options.method} ${options.path}');
        handler.next(options);
      },
      onResponse: (response, handler) {
        _logger.d('← ${response.statusCode} ${response.requestOptions.path}');
        handler.next(response);
      },
      onError: (error, handler) async {
        _logger.e('✗ ${error.requestOptions.path}: ${error.message}');

        // Handle 401 — try to refresh token
        if (error.response?.statusCode == 401 && _refreshToken != null) {
          try {
            await _refreshAuth();
            // Retry original request
            final response = await _dio.fetch(error.requestOptions);
            handler.resolve(response);
            return;
          } catch (e) {
            _logger.e('Token refresh failed: $e');
          }
        }

        handler.next(error);
      },
    ));
  }

  // ===========================================================================
  // AUTH
  // ===========================================================================

  /// Request OTP for phone authentication.
  Future<bool> requestOtp(String phoneNumber) async {
    try {
      final response = await _dio.post('/v1/auth/phone', data: {
        'phone': phoneNumber,
      });
      return response.statusCode == 200;
    } on DioException catch (e) {
      _logger.e('OTP request failed: ${e.message}');
      return false;
    }
  }

  /// Verify OTP and get tokens.
  Future<bool> verifyOtp(String phoneNumber, String otp) async {
    try {
      final response = await _dio.post('/v1/auth/verify', data: {
        'phone': phoneNumber,
        'otp': otp,
      });

      final data = response.data as Map<String, dynamic>;
      _accessToken = data['access_token'] as String?;
      _refreshToken = data['refresh_token'] as String?;

      // Persist tokens
      if (_accessToken != null) {
        await _secureStorage.write(key: 'access_token', value: _accessToken);
      }
      if (_refreshToken != null) {
        await _secureStorage.write(key: 'refresh_token', value: _refreshToken);
      }

      return _accessToken != null;
    } on DioException catch (e) {
      _logger.e('OTP verify failed: ${e.message}');
      return false;
    }
  }

  /// Load saved tokens from secure storage.
  Future<bool> loadSavedTokens() async {
    _accessToken = await _secureStorage.read(key: 'access_token');
    _refreshToken = await _secureStorage.read(key: 'refresh_token');
    return _accessToken != null;
  }

  /// Refresh the access token using the refresh token.
  Future<void> _refreshAuth() async {
    final response = await _dio.post('/v1/auth/refresh', data: {
      'refresh_token': _refreshToken,
    });
    final data = response.data as Map<String, dynamic>;
    _accessToken = data['access_token'] as String?;
    _refreshToken = data['refresh_token'] as String?;

    if (_accessToken != null) {
      await _secureStorage.write(key: 'access_token', value: _accessToken);
    }
    if (_refreshToken != null) {
      await _secureStorage.write(key: 'refresh_token', value: _refreshToken);
    }
  }

  /// Logout — clear tokens.
  Future<void> logout() async {
    _accessToken = null;
    _refreshToken = null;
    await _secureStorage.delete(key: 'access_token');
    await _secureStorage.delete(key: 'refresh_token');
  }

  bool get isAuthenticated => _accessToken != null;

  // ===========================================================================
  // SAMPLES
  // ===========================================================================

  /// Create a new mineral sample.
  Future<MineralSample?> createSample(MineralSample sample) async {
    try {
      final response = await _dio.post('/v1/samples', data: sample.toJson());
      return MineralSample.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      _logger.e('Create sample failed: ${e.message}');
      // Queue for offline sync
      await offlineService.enqueueSync('sample', sample.id, 'create', sample.toJson());
      return sample; // Return local copy
    }
  }

  /// Upload sample photo.
  Future<String?> uploadPhoto(String sampleId, String filePath) async {
    try {
      final formData = FormData.fromMap({
        'photo': await MultipartFile.fromFile(filePath),
      });
      final response = await _dio.post('/v1/samples/$sampleId/photos', data: formData);
      return response.data['photo_url'] as String?;
    } on DioException catch (e) {
      _logger.e('Photo upload failed: ${e.message}');
      return null;
    }
  }

  /// Get a specific sample.
  Future<MineralSample?> getSample(String sampleId) async {
    try {
      final response = await _dio.get('/v1/samples/$sampleId');
      return MineralSample.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      _logger.e('Get sample failed: ${e.message}');
      return null;
    }
  }

  /// Get recent samples.
  Future<List<MineralSample>> getSamples({int limit = 20, int offset = 0}) async {
    try {
      final response = await _dio.get('/v1/samples', queryParameters: {
        'limit': limit,
        'offset': offset,
      });
      final List<dynamic> data = response.data as List<dynamic>;
      return data.map((e) => MineralSample.fromJson(e as Map<String, dynamic>)).toList();
    } on DioException catch (e) {
      _logger.e('Get samples failed: ${e.message}');
      // Return cached samples
      return await offlineService.getCachedSamples(limit: limit);
    }
  }

  // ===========================================================================
  // ANALYSES
  // ===========================================================================

  /// Trigger a new analysis for given samples.
  Future<Analysis?> createAnalysis(List<String> sampleIds) async {
    try {
      final response = await _dio.post('/v1/analyses', data: {
        'sample_ids': sampleIds,
      });
      return Analysis.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      _logger.e('Create analysis failed: ${e.message}');
      return null;
    }
  }

  /// Get analysis details.
  Future<Analysis?> getAnalysis(String analysisId) async {
    try {
      final response = await _dio.get('/v1/analyses/$analysisId');
      return Analysis.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      _logger.e('Get analysis failed: ${e.message}');
      // Return cached analysis
      return await offlineService.getCachedAnalysis(analysisId);
    }
  }

  /// Get recent analyses.
  Future<List<Analysis>> getAnalyses({int limit = 20, int offset = 0}) async {
    try {
      final response = await _dio.get('/v1/analyses', queryParameters: {
        'limit': limit,
        'offset': offset,
      });
      final List<dynamic> data = response.data as List<dynamic>;
      return data.map((e) => Analysis.fromJson(e as Map<String, dynamic>)).toList();
    } on DioException catch (e) {
      _logger.e('Get analyses failed: ${e.message}');
      return await offlineService.getCachedAnalyses(limit: limit);
    }
  }

  /// Stream analysis progress via SSE.
  Stream<AnalysisUpdate> streamAnalysisProgress(String analysisId) async* {
    try {
      final response = await _dio.get<ResponseBody>(
        '/v1/analyses/$analysisId/stream',
        options: Options(responseType: ResponseType.stream),
      );

      String buffer = '';
      await for (final chunk in response.data!.stream) {
        buffer += utf8.decode(chunk);
        final lines = buffer.split('\n');
        buffer = lines.removeLast(); // Keep incomplete line

        for (final line in lines) {
          if (line.startsWith('data: ')) {
            final jsonStr = line.substring(6).trim();
            if (jsonStr.isEmpty || jsonStr == '[DONE]') continue;
            try {
              final json = jsonDecode(jsonStr) as Map<String, dynamic>;
              yield AnalysisUpdate.fromJson(json);
            } catch (e) {
              _logger.w('SSE parse error: $e');
            }
          }
        }
      }
    } on DioException catch (e) {
      _logger.e('SSE stream failed: ${e.message}');
    }
  }

  // ===========================================================================
  // REPORTS
  // ===========================================================================

  /// Get report URL for an analysis.
  Future<String?> getReportUrl(String analysisId) async {
    try {
      final response = await _dio.get('/v1/analyses/$analysisId/report');
      return response.data['url'] as String?;
    } on DioException catch (e) {
      _logger.e('Get report URL failed: ${e.message}');
      return null;
    }
  }

  // ===========================================================================
  // SYNC
  // ===========================================================================

  /// Sync pending offline data to server.
  Future<Map<String, int>> syncPendingData() async {
    final pending = await offlineService.getPendingSyncItems();
    int uploaded = 0;
    int failed = 0;

    for (final item in pending) {
      try {
        final entityType = item['entity_type'] as String;
        final action = item['action'] as String;
        final data = jsonDecode(item['data_json'] as String) as Map<String, dynamic>;

        if (entityType == 'sample' && action == 'create') {
          final response = await _dio.post('/v1/samples', data: data);
          if (response.statusCode == 200 || response.statusCode == 201) {
            await offlineService.removeSyncItem(item['id'] as int);
            uploaded++;
          } else {
            failed++;
          }
        } else if (entityType == 'analysis' && action == 'create') {
          // Analyses are triggered server-side, just mark as synced
          await offlineService.removeSyncItem(item['id'] as int);
          uploaded++;
        } else {
          failed++;
        }
      } catch (e) {
        _logger.e('Sync item failed: $e');
        await offlineService.incrementSyncRetry(item['id'] as int);
        failed++;
      }
    }

    return {'uploaded': uploaded, 'failed': failed};
  }

  // ===========================================================================
  // HEALTH
  // ===========================================================================

  /// Check if the API is reachable.
  Future<bool> checkHealth() async {
    try {
      final response = await _dio.get('/health',
          options: Options(receiveTimeout: const Duration(seconds: 5)));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}
