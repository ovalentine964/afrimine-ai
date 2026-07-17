import 'dart:io';
import 'package:flutter/material.dart';
import '../models/sample_model.dart';
import '../services/database_service.dart';
import '../services/api_service.dart';
import '../services/sync_service.dart';
import '../services/location_service.dart';
import '../utils/helpers.dart';

class SampleProvider extends ChangeNotifier {
  final DatabaseService _db = DatabaseService();
  final ApiService _api = ApiService();
  final SyncService _sync = SyncService();
  final LocationService _location = LocationService();

  List<SampleModel> _samples = [];
  SampleModel? _selectedSample;
  bool _isLoading = false;
  String? _error;
  String _filterStatus = 'all';

  List<SampleModel> get samples => _samples;
  SampleModel? get selectedSample => _selectedSample;
  bool get isLoading => _isLoading;
  String? get error => _error;
  String get filterStatus => _filterStatus;

  List<SampleModel> get filteredSamples {
    if (_filterStatus == 'all') return _samples;
    return _samples.where((s) => s.status == _filterStatus).toList();
  }

  int get totalCount => _samples.length;
  int get pendingCount => _samples.where((s) => s.isPending).length;
  int get analyzedCount => _samples.where((s) => s.isAnalyzed).length;
  int get verifiedCount => _samples.where((s) => s.isVerified).length;

  Future<void> loadSamples({String? userId}) async {
    _isLoading = true;
    notifyListeners();

    try {
      _samples = await _db.getAllSamples(userId: userId);
      _error = null;
    } catch (e) {
      _error = e.toString();
    }

    _isLoading = false;
    notifyListeners();
  }

  void setFilter(String status) {
    _filterStatus = status;
    notifyListeners();
  }

  void selectSample(SampleModel sample) {
    _selectedSample = sample;
    notifyListeners();
  }

  Future<SampleModel?> createSample({
    required String userId,
    File? imageFile,
    String? notes,
    Map<String, dynamic>? fieldTests,
  }) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      // Get current location
      final position = await _location.getCurrentLocation();

      final now = DateTime.now();
      final sample = SampleModel(
        id: Helpers.generateId(),
        userId: userId,
        imagePath: imageFile?.path,
        latitude: position?.latitude,
        longitude: position?.longitude,
        accuracy: position?.accuracy,
        status: 'pending',
        notes: notes,
        fieldTests: fieldTests,
        synced: false,
        createdAt: now,
        updatedAt: now,
      );

      // Save to local DB
      await _db.insertSample(sample);

      // Try to classify with AI
      if (imageFile != null) {
        try {
          final aiResult = await _api.classifySample(
            imagePath: imageFile.path,
            latitude: position?.latitude,
            longitude: position?.longitude,
            fieldTests: fieldTests,
          );

          final analyzedSample = sample.copyWith(
            mineralType: aiResult['mineral_type'] as String?,
            confidence: (aiResult['confidence'] as num?)?.toDouble(),
            gradeEstimate: (aiResult['grade_estimate'] as num?)?.toDouble(),
            status: 'analyzed',
            aiResults: aiResult,
            updatedAt: DateTime.now(),
          );

          await _db.updateSample(analyzedSample);
          _samples.insert(0, analyzedSample);
        } catch (e) {
          // AI classification failed, keep as pending
          // Queue for sync
          await _sync.queueSyncItem(
            entityType: 'sample',
            entityId: sample.id,
            action: 'create',
          );
          _samples.insert(0, sample);
        }
      } else {
        _samples.insert(0, sample);
      }

      _isLoading = false;
      notifyListeners();
      return _samples.first;
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
      return null;
    }
  }

  Future<void> updateSample(SampleModel sample) async {
    try {
      final updated = sample.copyWith(updatedAt: DateTime.now());
      await _db.updateSample(updated);

      final idx = _samples.indexWhere((s) => s.id == sample.id);
      if (idx >= 0) _samples[idx] = updated;

      if (_selectedSample?.id == sample.id) {
        _selectedSample = updated;
      }

      // Queue for sync
      await _sync.queueSyncItem(
        entityType: 'sample',
        entityId: sample.id,
        action: 'update',
      );

      notifyListeners();
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }

  Future<void> deleteSample(String id) async {
    try {
      await _db.deleteSample(id);
      _samples.removeWhere((s) => s.id == id);

      if (_selectedSample?.id == id) {
        _selectedSample = null;
      }

      await _sync.queueSyncItem(
        entityType: 'sample',
        entityId: id,
        action: 'delete',
      );

      notifyListeners();
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }

  Future<void> refreshSample(String id) async {
    final sample = await _db.getSample(id);
    if (sample != null) {
      final idx = _samples.indexWhere((s) => s.id == id);
      if (idx >= 0) _samples[idx] = sample;
      if (_selectedSample?.id == id) _selectedSample = sample;
      notifyListeners();
    }
  }
}
