import 'package:dio/dio.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import '../models/sample_model.dart';
import '../models/market_price_model.dart';
import '../utils/constants.dart';

class ApiService {
  static ApiService? _instance;
  late final Dio _dio;
  final Connectivity _connectivity = Connectivity();

  ApiService._() {
    _dio = Dio(BaseOptions(
      baseUrl: AppConstants.apiBaseUrl,
      connectTimeout: const Duration(seconds: 30),
      receiveTimeout: const Duration(seconds: 30),
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    ));

    _dio.interceptors.add(LogInterceptor(
      requestBody: true,
      responseBody: true,
      logPrint: (obj) => print('[API] $obj'),
    ));

    _dio.interceptors.add(InterceptorsWrapper(
      onError: (error, handler) {
        if (error.type == DioExceptionType.connectionTimeout ||
            error.type == DioExceptionType.receiveTimeout) {
          handler.next(error.copyWith(
            error: 'Connection timeout. Please check your internet.',
          ));
        } else if (error.type == DioExceptionType.connectionError) {
          handler.next(error.copyWith(
            error: 'No internet connection.',
          ));
        } else {
          handler.next(error);
        }
      },
    ));
  }

  factory ApiService() {
    _instance ??= ApiService._();
    return _instance!;
  }

  Future<bool> get isConnected async {
    final result = await _connectivity.checkConnectivity();
    return !result.contains(ConnectivityResult.none);
  }

  // ========== AI CLASSIFICATION ==========

  Future<Map<String, dynamic>> classifySample({
    required String imagePath,
    double? latitude,
    double? longitude,
    Map<String, dynamic>? fieldTests,
  }) async {
    if (!await isConnected) {
      throw ApiException('No internet connection. Sample saved offline.', 0);
    }

    try {
      final formData = FormData.fromMap({
        'image': await MultipartFile.fromFile(imagePath),
        if (latitude != null) 'latitude': latitude,
        if (longitude != null) 'longitude': longitude,
        if (fieldTests != null) 'field_tests': fieldTests,
      });

      final response = await _dio.post('/classify', data: formData);
      return response.data as Map<String, dynamic>;
    } on DioException catch (e) {
      throw ApiException(_getErrorMessage(e), e.response?.statusCode ?? 0);
    }
  }

  // ========== MARKET PRICES ==========

  Future<List<MarketPriceModel>> getMarketPrices() async {
    if (!await isConnected) {
      return MarketPriceModel.getMockPrices();
    }

    try {
      final response = await _dio.get('/market-prices');
      final data = response.data as List;
      return data.map((json) => MarketPriceModel.fromJson(json as Map<String, dynamic>)).toList();
    } on DioException catch (_) {
      // Return mock data on error
      return MarketPriceModel.getMockPrices();
    }
  }

  // ========== SAMPLES SYNC ==========

  Future<SampleModel> syncSample(SampleModel sample) async {
    if (!await isConnected) {
      throw ApiException('No internet connection', 0);
    }

    try {
      final response = await _dio.post('/samples', data: sample.toJson());
      return SampleModel.fromJson(response.data as Map<String, dynamic>);
    } on DioException catch (e) {
      throw ApiException(_getErrorMessage(e), e.response?.statusCode ?? 0);
    }
  }

  Future<void> updateSampleOnServer(SampleModel sample) async {
    if (!await isConnected) {
      throw ApiException('No internet connection', 0);
    }

    try {
      await _dio.put('/samples/${sample.id}', data: sample.toJson());
    } on DioException catch (e) {
      throw ApiException(_getErrorMessage(e), e.response?.statusCode ?? 0);
    }
  }

  Future<void> deleteSampleFromServer(String sampleId) async {
    if (!await isConnected) {
      throw ApiException('No internet connection', 0);
    }

    try {
      await _dio.delete('/samples/$sampleId');
    } on DioException catch (e) {
      throw ApiException(_getErrorMessage(e), e.response?.statusCode ?? 0);
    }
  }

  // ========== REPORTS ==========

  Future<List<int>> generateReport({
    required String reportType,
    required String userId,
    DateTime? startDate,
    DateTime? endDate,
  }) async {
    if (!await isConnected) {
      throw ApiException('No internet connection', 0);
    }

    try {
      final response = await _dio.post(
        '/reports/generate',
        data: {
          'report_type': reportType,
          'user_id': userId,
          'start_date': startDate?.toIso8601String(),
          'end_date': endDate?.toIso8601String(),
        },
        options: Options(responseType: ResponseType.bytes),
      );
      return response.data as List<int>;
    } on DioException catch (e) {
      throw ApiException(_getErrorMessage(e), e.response?.statusCode ?? 0);
    }
  }

  // ========== USER ==========

  Future<Map<String, dynamic>> getUserProfile(String userId) async {
    try {
      final response = await _dio.get('/users/$userId');
      return response.data as Map<String, dynamic>;
    } on DioException catch (e) {
      throw ApiException(_getErrorMessage(e), e.response?.statusCode ?? 0);
    }
  }

  Future<void> updateUserProfile(String userId, Map<String, dynamic> data) async {
    try {
      await _dio.put('/users/$userId', data: data);
    } on DioException catch (e) {
      throw ApiException(_getErrorMessage(e), e.response?.statusCode ?? 0);
    }
  }

  String _getErrorMessage(DioException error) {
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.receiveTimeout:
        return 'Connection timeout. Please try again.';
      case DioExceptionType.connectionError:
        return 'No internet connection.';
      case DioExceptionType.badResponse:
        final statusCode = error.response?.statusCode;
        if (statusCode == 401) return 'Authentication expired. Please login again.';
        if (statusCode == 403) return 'Access denied.';
        if (statusCode == 404) return 'Resource not found.';
        if (statusCode == 500) return 'Server error. Please try again later.';
        return error.response?.data?['message'] ?? 'Unknown error occurred.';
      default:
        return error.message ?? 'An unexpected error occurred.';
    }
  }
}

class ApiException implements Exception {
  final String message;
  final int statusCode;

  ApiException(this.message, this.statusCode);

  @override
  String toString() => message;
}
