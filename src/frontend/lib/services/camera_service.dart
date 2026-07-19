import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:camera/camera.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:image/image.dart' as img;
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';

import '../models/sample.dart';

final cameraServiceProvider = Provider<CameraService>((ref) {
  final service = CameraService();
  ref.onDispose(() => service.dispose());
  return service;
});

/// Camera service with GPS auto-tagging and photo compression.
///
/// Optimized for budget Android phones:
/// - Uses rear camera by default (mineral photos)
/// - Compresses photos to ~500KB for upload
/// - Auto-captures GPS location with each photo
/// - Supports color reference card overlay
class CameraService {
  CameraController? _controller;
  List<CameraDescription> _cameras = [];
  bool _isInitialized = false;

  // ===========================================================================
  // INITIALIZATION
  // ===========================================================================

  /// Initialize cameras. Call once at app startup.
  Future<bool> initialize() async {
    try {
      // Request camera permission
      final status = await Permission.camera.request();
      if (!status.isGranted) return false;

      _cameras = await availableCameras();
      if (_cameras.isEmpty) return false;

      // Prefer rear camera for mineral photos
      final rearCamera = _cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => _cameras.first,
      );

      _controller = CameraController(
        rearCamera,
        ResolutionPreset.medium, // Good enough for analysis, small file size
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.jpeg,
      );

      await _controller!.initialize();
      _isInitialized = true;
      return true;
    } catch (e) {
      _isInitialized = false;
      return false;
    }
  }

  /// Get the camera controller (for preview).
  CameraController? get controller => _controller;

  bool get isInitialized => _isInitialized;

  /// Switch between front and rear camera.
  Future<void> switchCamera() async {
    if (_cameras.length < 2) return;

    final currentLens = _controller?.description.lensDirection;
    final newCamera = _cameras.firstWhere(
      (c) => c.lensDirection != currentLens,
      orElse: () => _cameras.first,
    );

    await _controller?.dispose();
    _controller = CameraController(
      newCamera,
      ResolutionPreset.medium,
      enableAudio: false,
      imageFormatGroup: ImageFormatGroup.jpeg,
    );
    await _controller!.initialize();
  }

  // ===========================================================================
  // CAPTURE
  // ===========================================================================

  /// Capture a photo with GPS tagging.
  ///
  /// Returns a [CapturedPhoto] with the file path, GPS coordinates,
  /// and metadata. The photo is compressed for upload.
  Future<CapturedPhoto?> capturePhoto() async {
    if (!_isInitialized || _controller == null) return null;

    try {
      // Capture
      final xfile = await _controller!.takePicture();

      // Get GPS location simultaneously
      final location = await getCurrentLocation();

      // Compress photo
      final compressedPath = await compressPhoto(xfile.path);

      return CapturedPhoto(
        filePath: compressedPath ?? xfile.path,
        location: location,
        capturedAt: DateTime.now(),
        originalPath: xfile.path,
      );
    } catch (e) {
      return null;
    }
  }

  /// Compress a photo to reduce file size for upload.
  ///
  /// Target: ~500KB, max dimension 1920px.
  Future<String?> compressPhoto(String inputPath, {int maxWidth = 1920, int quality = 80}) async {
    try {
      final file = File(inputPath);
      if (!await file.exists()) return null;

      final bytes = await file.readAsBytes();
      final image = img.decodeImage(bytes);
      if (image == null) return null;

      // Resize if too large
      img.Image resized;
      if (image.width > maxWidth || image.height > maxWidth) {
        resized = img.copyResize(
          image,
          width: image.width > image.height ? maxWidth : null,
          height: image.height > image.width ? maxWidth : null,
          interpolation: img.Interpolation.linear,
        );
      } else {
        resized = image;
      }

      // Encode as JPEG with compression
      final compressed = img.encodeJpg(resized, quality: quality);

      // Save to app documents directory
      final dir = await getApplicationDocumentsDirectory();
      final photosDir = Directory(p.join(dir.path, 'photos'));
      if (!await photosDir.exists()) {
        await photosDir.create(recursive: true);
      }

      final filename = 'afrimine_${DateTime.now().millisecondsSinceEpoch}.jpg';
      final outputPath = p.join(photosDir.path, filename);
      await File(outputPath).writeAsBytes(compressed);

      return outputPath;
    } catch (e) {
      return null;
    }
  }

  // ===========================================================================
  // GPS
  // ===========================================================================

  /// Get the current GPS location.
  Future<SampleLocation?> getCurrentLocation() async {
    try {
      // Check permission
      LocationPermission permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
        if (permission == LocationPermission.denied) return null;
      }
      if (permission == LocationPermission.deniedForever) return null;

      // Check if location service is enabled
      final serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) return null;

      // Get position with reasonable accuracy for field work
      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 10),
      );

      return SampleLocation(
        latitude: position.latitude,
        longitude: position.longitude,
        elevation: position.altitude,
        accuracy: position.accuracy,
      );
    } catch (e) {
      // Fallback: try last known position
      try {
        final lastPosition = await Geolocator.getLastKnownPosition();
        if (lastPosition != null) {
          return SampleLocation(
            latitude: lastPosition.latitude,
            longitude: lastPosition.longitude,
            elevation: lastPosition.altitude,
            accuracy: lastPosition.accuracy,
          );
        }
      } catch (_) {}
      return null;
    }
  }

  /// Stream of location updates (for live tracking during field work).
  Stream<SampleLocation> getLocationStream() {
    return Geolocator.getPositionStream(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 10, // Update every 10 meters
      ),
    ).map((position) => SampleLocation(
      latitude: position.latitude,
      longitude: position.longitude,
      elevation: position.altitude,
      accuracy: position.accuracy,
    ));
  }

  // ===========================================================================
  // FILE MANAGEMENT
  // ===========================================================================

  /// Get all captured photos in the app's documents directory.
  Future<List<String>> getCapturedPhotos() async {
    final dir = await getApplicationDocumentsDirectory();
    final photosDir = Directory(p.join(dir.path, 'photos'));
    if (!await photosDir.exists()) return [];

    final files = await photosDir
        .list()
        .where((f) => f.path.endsWith('.jpg') || f.path.endsWith('.jpeg'))
        .toList();

    return files.map((f) => f.path).toList()..sort((a, b) => b.compareTo(a));
  }

  /// Delete a captured photo.
  Future<void> deletePhoto(String path) async {
    final file = File(path);
    if (await file.exists()) {
      await file.delete();
    }
  }

  /// Get total size of captured photos in MB.
  Future<double> getPhotosSizeMB() async {
    final photos = await getCapturedPhotos();
    int totalBytes = 0;
    for (final path in photos) {
      final file = File(path);
      if (await file.exists()) {
        totalBytes += await file.length();
      }
    }
    return totalBytes / (1024 * 1024);
  }

  // ===========================================================================
  // DISPOSE
  // ===========================================================================

  void dispose() {
    _controller?.dispose();
    _controller = null;
    _isInitialized = false;
  }
}

/// A captured photo with metadata.
class CapturedPhoto {
  final String filePath;
  final SampleLocation? location;
  final DateTime capturedAt;
  final String? originalPath;

  const CapturedPhoto({
    required this.filePath,
    this.location,
    required this.capturedAt,
    this.originalPath,
  });
}
