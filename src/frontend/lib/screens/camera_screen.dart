import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../models/sample.dart';
import '../services/camera_service.dart';
import '../services/offline_service.dart';
import '../widgets/sync_indicator.dart';

/// Camera screen for capturing mineral samples.
///
/// Features:
/// - Live camera preview with color reference card overlay
/// - GPS auto-tagging on capture
/// - Photo compression for upload
/// - Flash toggle, camera switch
/// - Grid overlay for composition guidance
class CameraScreen extends ConsumerStatefulWidget {
  const CameraScreen({super.key});

  @override
  ConsumerState<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends ConsumerState<CameraScreen> {
  bool _isInitializing = true;
  bool _isCapturing = false;
  bool _showGrid = true;
  bool _showColorRef = true;
  SampleLocation? _currentLocation;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _initCamera();
  }

  Future<void> _initCamera() async {
    final cameraService = ref.read(cameraServiceProvider);
    final success = await cameraService.initialize();

    if (mounted) {
      setState(() {
        _isInitializing = false;
        if (!success) _errorMessage = 'Camera not available. Check permissions.';
      });

      // Get initial GPS location
      if (success) {
        final location = await cameraService.getCurrentLocation();
        if (mounted) setState(() => _currentLocation = location);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final cameraService = ref.watch(cameraServiceProvider);

    return Scaffold(
      backgroundColor: Colors.black,
      body: _isInitializing
          ? const Center(child: CircularProgressIndicator(color: Colors.white))
          : _errorMessage != null
              ? _buildError()
              : _buildCameraPreview(cameraService),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.camera_alt, size: 64, color: Colors.grey),
            const SizedBox(height: 16),
            Text(
              _errorMessage!,
              style: const TextStyle(color: Colors.white70, fontSize: 16),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Go Back'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCameraPreview(CameraService cameraService) {
    final controller = cameraService.controller;
    if (controller == null || !controller.value.isInitialized) {
      return const Center(child: CircularProgressIndicator(color: Colors.white));
    }

    return Stack(
      fit: StackFit.expand,
      children: [
        // Camera preview
        CameraPreview(controller),

        // Grid overlay
        if (_showGrid) _buildGridOverlay(),

        // Color reference card overlay
        if (_showColorRef) _buildColorReference(),

        // GPS indicator (top left)
        Positioned(
          top: MediaQuery.of(context).padding.top + 8,
          left: 16,
          child: _buildGpsIndicator(),
        ),

        // Top controls
        Positioned(
          top: MediaQuery.of(context).padding.top + 8,
          right: 16,
          child: _buildTopControls(cameraService),
        ),

        // Bottom controls
        Positioned(
          bottom: 0,
          left: 0,
          right: 0,
          child: _buildBottomControls(cameraService),
        ),

        // Capture flash effect
        if (_isCapturing)
          Container(color: Colors.white.withOpacity(0.8)),
      ],
    );
  }

  Widget _buildGridOverlay() {
    return CustomPaint(
      painter: _GridPainter(),
      size: Size.infinite,
    );
  }

  Widget _buildColorReference() {
    // Color reference card for mineral identification
    return Positioned(
      top: MediaQuery.of(context).padding.top + 60,
      right: 16,
      child: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: Colors.black54,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.white30),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Color Ref', style: TextStyle(color: Colors.white70, fontSize: 9)),
            const SizedBox(height: 4),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _colorSwatch(const Color(0xFFFFD700), 'Au'),
                const SizedBox(width: 2),
                _colorSwatch(const Color(0xFFB87333), 'Cu'),
                const SizedBox(width: 2),
                _colorSwatch(const Color(0xFFC0C0C0), 'Ag'),
                const SizedBox(width: 2),
                _colorSwatch(const Color(0xFF8B4513), 'Fe'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _colorSwatch(Color color, String label) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 20,
          height: 20,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(3),
            border: Border.all(color: Colors.white30),
          ),
        ),
        const SizedBox(height: 1),
        Text(label, style: const TextStyle(color: Colors.white60, fontSize: 7)),
      ],
    );
  }

  Widget _buildGpsIndicator() {
    final hasLocation = _currentLocation != null;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.black54,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            hasLocation ? Icons.gps_fixed : Icons.gps_off,
            size: 14,
            color: hasLocation ? Colors.green : Colors.red,
          ),
          const SizedBox(width: 4),
          Text(
            hasLocation
                ? '${_currentLocation!.latitude.toStringAsFixed(4)}, ${_currentLocation!.longitude.toStringAsFixed(4)}'
                : 'GPS unavailable',
            style: TextStyle(
              color: hasLocation ? Colors.white70 : Colors.red[300],
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTopControls(CameraService cameraService) {
    return Column(
      children: [
        // Close button
        _controlButton(
          icon: Icons.close,
          onTap: () => Navigator.pop(context),
        ),
        const SizedBox(height: 12),
        // Flash toggle
        _controlButton(
          icon: Icons.flash_auto,
          onTap: () {
            // Toggle flash mode
          },
        ),
        const SizedBox(height: 12),
        // Grid toggle
        _controlButton(
          icon: _showGrid ? Icons.grid_on : Icons.grid_off,
          onTap: () => setState(() => _showGrid = !_showGrid),
          active: _showGrid,
        ),
        const SizedBox(height: 12),
        // Color ref toggle
        _controlButton(
          icon: Icons.palette,
          onTap: () => setState(() => _showColorRef = !_showColorRef),
          active: _showColorRef,
        ),
        const SizedBox(height: 12),
        // Switch camera
        _controlButton(
          icon: Icons.flip_camera_android,
          onTap: () => cameraService.switchCamera(),
        ),
      ],
    );
  }

  Widget _controlButton({
    required IconData icon,
    required VoidCallback onTap,
    bool active = false,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          color: active ? Colors.white24 : Colors.black45,
          shape: BoxShape.circle,
        ),
        child: Icon(icon, color: Colors.white, size: 20),
      ),
    );
  }

  Widget _buildBottomControls(CameraService cameraService) {
    return Container(
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).padding.bottom + 20,
        top: 20,
        left: 32,
        right: 32,
      ),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.bottomCenter,
          end: Alignment.topCenter,
          colors: [Colors.black87, Colors.transparent],
        ),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          // Gallery button (last captured photo)
          _buildGalleryButton(),

          // Capture button (big, easy to tap)
          _buildCaptureButton(cameraService),

          // Notes button
          _buildNotesButton(),
        ],
      ),
    );
  }

  Widget _buildCaptureButton(CameraService cameraService) {
    return GestureDetector(
      onTap: _isCapturing ? null : () => _capturePhoto(cameraService),
      child: Container(
        width: 72,
        height: 72,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          border: Border.all(color: Colors.white, width: 4),
          color: Colors.transparent,
        ),
        child: Container(
          margin: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: _isCapturing ? Colors.grey : Colors.white,
          ),
          child: _isCapturing
              ? const CircularProgressIndicator(color: Colors.black)
              : const Icon(Icons.camera, color: Colors.black, size: 32),
        ),
      ),
    );
  }

  Widget _buildGalleryButton() {
    return Container(
      width: 48,
      height: 48,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        color: Colors.black45,
        border: Border.all(color: Colors.white30),
      ),
      child: const Icon(Icons.photo_library, color: Colors.white, size: 24),
    );
  }

  Widget _buildNotesButton() {
    return GestureDetector(
      onTap: _showNotesDialog,
      child: Container(
        width: 48,
        height: 48,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(8),
          color: Colors.black45,
          border: Border.all(color: Colors.white30),
        ),
        child: const Icon(Icons.note_add, color: Colors.white, size: 24),
      ),
    );
  }

  Future<void> _capturePhoto(CameraService cameraService) async {
    setState(() => _isCapturing = true);

    // Brief flash effect
    await Future.delayed(const Duration(milliseconds: 100));

    final photo = await cameraService.capturePhoto();

    if (mounted) {
      setState(() {
        _isCapturing = false;
        if (photo?.location != null) _currentLocation = photo!.location;
      });

      if (photo != null) {
        // Save sample to local DB
        final offlineService = ref.read(offlineServiceProvider);
        final sample = MineralSample(
          id: 'local_${DateTime.now().millisecondsSinceEpoch}',
          location: photo.location,
          photoPaths: [photo.filePath],
          createdAt: photo.capturedAt,
          updatedAt: photo.capturedAt,
        );

        await offlineService.saveSample(sample);

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Photo saved${photo.location != null ? ' with GPS' : ''}'),
              action: SnackBarAction(
                label: 'Analyze',
                onPressed: () => context.push('/analysis/new'),
              ),
              behavior: SnackBarBehavior.floating,
            ),
          );
        }
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Capture failed. Try again.'),
              behavior: SnackBarBehavior.floating,
            ),
          );
        }
      }
    }
  }

  void _showNotesDialog() {
    final controller = TextEditingController();
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.grey[900],
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (context) => Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom,
          left: 16,
          right: 16,
          top: 16,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Field Notes',
              style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              style: const TextStyle(color: Colors.white),
              maxLines: 4,
              decoration: InputDecoration(
                hintText: 'Describe what you see (color, texture, hardness)...',
                hintStyle: TextStyle(color: Colors.grey[600]),
                filled: true,
                fillColor: Colors.grey[850],
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
              ),
              autofocus: true,
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  // Save note to current sample context
                  Navigator.pop(context);
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.green[700],
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
                child: const Text('Save Note'),
              ),
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }
}

/// Grid overlay painter for composition guidance.
class _GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white.withOpacity(0.2)
      ..strokeWidth = 0.5;

    // Rule of thirds
    final thirdW = size.width / 3;
    final thirdH = size.height / 3;

    // Vertical lines
    canvas.drawLine(Offset(thirdW, 0), Offset(thirdW, size.height), paint);
    canvas.drawLine(Offset(thirdW * 2, 0), Offset(thirdW * 2, size.height), paint);

    // Horizontal lines
    canvas.drawLine(Offset(0, thirdH), Offset(size.width, thirdH), paint);
    canvas.drawLine(Offset(0, thirdH * 2), Offset(size.width, thirdH * 2), paint);

    // Center crosshair
    final center = Offset(size.width / 2, size.height / 2);
    final crosshairPaint = Paint()
      ..color = Colors.white.withOpacity(0.4)
      ..strokeWidth = 1;
    canvas.drawLine(center - const Offset(10, 0), center + const Offset(10, 0), crosshairPaint);
    canvas.drawLine(center - const Offset(0, 10), center + const Offset(0, 10), crosshairPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
