import 'dart:async';
import 'package:connectivity_plus/connectivity_plus.dart';
import '../models/sample_model.dart';
import '../models/sync_item_model.dart';
import '../utils/constants.dart';
import '../utils/helpers.dart';
import 'database_service.dart';
import 'api_service.dart';

class SyncService {
  static SyncService? _instance;
  final DatabaseService _db = DatabaseService();
  final ApiService _api = ApiService();
  final Connectivity _connectivity = Connectivity();
  StreamSubscription<List<ConnectivityResult>>? _connectivitySub;
  Timer? _periodicTimer;
  bool _isSyncing = false;
  DateTime? _lastSyncTime;

  SyncService._();

  factory SyncService() {
    _instance ??= SyncService._();
    return _instance!;
  }

  DateTime? get lastSyncTime => _lastSyncTime;
  bool get isSyncing => _isSyncing;

  void initialize() {
    // Listen for connectivity changes
    _connectivitySub = _connectivity.onConnectivityChanged.listen((results) {
      final isConnected = !results.contains(ConnectivityResult.none);
      if (isConnected) {
        syncAll();
      }
    });

    // Periodic sync
    _periodicTimer = Timer.periodic(
      Duration(minutes: AppConstants.syncIntervalMinutes),
      (_) => syncAll(),
    );
  }

  void dispose() {
    _connectivitySub?.cancel();
    _periodicTimer?.cancel();
  }

  Future<SyncResult> syncAll() async {
    if (_isSyncing) return SyncResult.alreadySyncing();

    final isConnected = await _api.isConnected;
    if (!isConnected) return SyncResult.noConnection();

    _isSyncing = true;
    int synced = 0;
    int failed = 0;
    final List<String> errors = [];

    try {
      // Get pending sync items
      final items = await _db.getPendingSyncItems();

      for (final item in items) {
        if (!item.canRetry) {
          // Remove items that exceeded retry limit
          await _db.removeFromSyncQueue(item.id);
          continue;
        }

        try {
          await _processSyncItem(item);
          await _db.removeFromSyncQueue(item.id);
          synced++;
        } catch (e) {
          failed++;
          errors.add('${item.entityType}/${item.entityId}: $e');
          final newRetryCount = item.retryCount + 1;
          await _db.updateSyncItem(item.copyWith(
            retryCount: newRetryCount,
            lastError: e.toString(),
          ));
          // Exponential backoff: wait before retrying next item
          if (newRetryCount < AppConstants.maxRetryAttempts) {
            final backoffMs = _calculateBackoff(newRetryCount);
            await Future.delayed(Duration(milliseconds: backoffMs));
          }
        }
      }

      // Sync unsynced samples directly
      final unsyncedSamples = await _db.getUnsyncedSamples();
      for (final sample in unsyncedSamples) {
        try {
          final syncedSample = await _api.syncSample(sample);
          await _db.updateSample(syncedSample.copyWith(synced: true));
          synced++;
        } catch (e) {
          failed++;
          errors.add('Sample ${sample.id}: $e');
        }
      }

      _lastSyncTime = DateTime.now();

      return SyncResult(
        success: failed == 0,
        syncedCount: synced,
        failedCount: failed,
        errors: errors,
      );
    } catch (e) {
      return SyncResult(
        success: false,
        syncedCount: synced,
        failedCount: failed,
        errors: [...errors, e.toString()],
      );
    } finally {
      _isSyncing = false;
    }
  }

  /// Calculate exponential backoff delay in milliseconds
  /// Base delay: 1 second, doubles with each retry attempt
  int _calculateBackoff(int retryCount) {
    const baseDelayMs = 1000;
    const maxDelayMs = 30000; // 30 seconds max
    final delay = baseDelayMs * (1 << (retryCount - 1)); // 2^(retryCount-1)
    return delay.clamp(baseDelayMs, maxDelayMs);
  }

  Future<void> _processSyncItem(SyncItemModel item) async {
    switch (item.entityType) {
      case 'sample':
        await _syncSampleItem(item);
        break;
      case 'user':
        await _syncUserItem(item);
        break;
      default:
        throw Exception('Unknown entity type: ${item.entityType}');
    }
  }

  Future<void> _syncSampleItem(SyncItemModel item) async {
    final sample = await _db.getSample(item.entityId);
    if (sample == null) {
      await _db.removeFromSyncQueue(item.id);
      return;
    }

    switch (item.action) {
      case 'create':
      case 'update':
        final syncedSample = await _api.syncSample(sample);
        await _db.updateSample(syncedSample.copyWith(synced: true));
        break;
      case 'delete':
        await _api.deleteSampleFromServer(item.entityId);
        break;
    }
  }

  Future<void> _syncUserItem(SyncItemModel item) async {
    if (item.data != null) {
      await _api.updateUserProfile(item.entityId, item.data!);
    }
  }

  Future<void> queueSyncItem({
    required String entityType,
    required String entityId,
    required String action,
    Map<String, dynamic>? data,
  }) async {
    final item = SyncItemModel(
      id: Helpers.generateId(),
      entityType: entityType,
      entityId: entityId,
      action: action,
      data: data,
      createdAt: DateTime.now(),
    );
    await _db.addToSyncQueue(item);
  }

  Future<int> getPendingCount() async {
    return await _db.getPendingSyncCount();
  }
}

class SyncResult {
  final bool success;
  final int syncedCount;
  final int failedCount;
  final List<String> errors;

  SyncResult({
    required this.success,
    this.syncedCount = 0,
    this.failedCount = 0,
    this.errors = const [],
  });

  factory SyncResult.alreadySyncing() => SyncResult(
        success: true,
        errors: ['Sync already in progress'],
      );

  factory SyncResult.noConnection() => SyncResult(
        success: false,
        errors: ['No internet connection'],
      );

  String get summary {
    if (success && syncedCount == 0) return 'Everything up to date';
    if (success) return 'Synced $syncedCount items';
    if (syncedCount > 0) return 'Synced $syncedCount, failed $failedCount';
    return 'Sync failed: ${errors.first}';
  }
}
