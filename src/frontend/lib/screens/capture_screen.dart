import 'dart:io';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:camera/camera.dart';
import '../providers/auth_provider.dart';
import '../providers/sample_provider.dart';
import '../services/camera_service.dart';
import '../services/location_service.dart';
import '../utils/constants.dart';

class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key});

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  final CameraService _cameraService = CameraService();
  final LocationService _locationService = LocationService();
  final _notesController = TextEditingController();

  CameraController? _controller;
  File? _capturedImage;
  double? _latitude;
  double? _longitude;
  double? _accuracy;
  bool _isCapturing = false;
  bool _isLocationLoading = true;
  Map<String, dynamic> _fieldTests = {};

  // Field test controllers
  final _phController = TextEditingController();
  final _colorController = TextEditingController();
  final _hardnessController = TextEditingController();
  final _streakController = TextEditingController();

  String? _locationError;

  @override
  void initState() {
    super.initState();
    _initCamera();
    _getCurrentLocation();
  }

  Future<void> _initCamera() async {
    try {
      await _cameraService.initializeCameras();
      _controller = await _cameraService.initController();
    } catch (e) {
      // Camera init failed - UI will show placeholder
    }
    if (mounted) setState(() {});
  }

  Future<void> _getCurrentLocation() async {
    setState(() {
      _isLocationLoading = true;
      _locationError = null;
    });
    try {
      final position = await _locationService.getCurrentLocation();
      if (position != null) {
        _latitude = position.latitude;
        _longitude = position.longitude;
        _accuracy = position.accuracy;
      } else {
        _locationError = 'Location unavailable';
      }
    } catch (e) {
      _locationError = 'Location permission denied';
    }
    if (mounted) setState(() => _isLocationLoading = false);
  }

  Future<void> _takePicture() async {
    setState(() => _isCapturing = true);
    final file = await _cameraService.takePicture();
    if (file != null) {
      setState(() => _capturedImage = file);
    }
    setState(() => _isCapturing = false);
  }

  Future<void> _pickFromGallery() async {
    final file = await _cameraService.pickFromGallery();
    if (file != null) {
      setState(() => _capturedImage = file);
    }
  }

  void _retake() {
    setState(() => _capturedImage = null);
  }

  Future<void> _submit() async {
    if (_capturedImage == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please capture a photo first'), backgroundColor: AppColors.error),
      );
      return;
    }

    _collectFieldTests();

    final auth = context.read<AuthProvider>();
    final samples = context.read<SampleProvider>();

    final sample = await samples.createSample(
      userId: auth.userId ?? 'local',
      imageFile: _capturedImage,
      notes: _notesController.text.trim().isNotEmpty ? _notesController.text.trim() : null,
      fieldTests: _fieldTests.isNotEmpty ? _fieldTests : null,
    );

    if (sample != null && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(sample.isAnalyzed
              ? 'Sample analyzed: ${sample.mineralType}'
              : 'Sample saved. Pending analysis.'),
          backgroundColor: sample.isAnalyzed ? AppColors.success : AppColors.info,
          duration: const Duration(seconds: 3),
        ),
      );
      context.pop();
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(samples.error ?? 'Failed to save sample'),
          backgroundColor: AppColors.error,
        ),
      );
    }
  }

  void _collectFieldTests() {
    _fieldTests = {};
    if (_phController.text.isNotEmpty) {
      _fieldTests['ph'] = double.tryParse(_phController.text);
    }
    if (_colorController.text.isNotEmpty) {
      _fieldTests['color'] = _colorController.text.trim();
    }
    if (_hardnessController.text.isNotEmpty) {
      _fieldTests['hardness'] = double.tryParse(_hardnessController.text);
    }
    if (_streakController.text.isNotEmpty) {
      _fieldTests['streak_color'] = _streakController.text.trim();
    }
  }

  @override
  void dispose() {
    _cameraService.dispose();
    _notesController.dispose();
    _phController.dispose();
    _colorController.dispose();
    _hardnessController.dispose();
    _streakController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black54,
        foregroundColor: Colors.white,
        title: const Text('Capture Sample'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.pop(),
        ),
      ),
      body: _capturedImage != null ? _buildPreview() : _buildCamera(),
    );
  }

  Widget _buildCamera() {
    return Column(
      children: [
        // Camera Preview
        Expanded(
          child: _controller != null && _controller!.value.isInitialized
              ? Stack(
                  children: [
                    CameraPreview(_controller!),
                    // AI Overlay
                    CustomPaint(
                      painter: _AIMarkerPainter(),
                      child: Container(),
                    ),
                    // Corner markers
                    Positioned(
                      top: 20,
                      left: 20,
                      child: _cornerMarker(Alignment.topLeft),
                    ),
                    Positioned(
                      top: 20,
                      right: 20,
                      child: _cornerMarker(Alignment.topRight),
                    ),
                    Positioned(
                      bottom: 20,
                      left: 20,
                      child: _cornerMarker(Alignment.bottomLeft),
                    ),
                    Positioned(
                      bottom: 20,
                      right: 20,
                      child: _cornerMarker(Alignment.bottomRight),
                    ),
                    // GPS indicator
                    Positioned(
                      top: 16,
                      left: 0,
                      right: 0,
                      child: Center(
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            color: Colors.black54,
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              if (_isLocationLoading)
                                const SizedBox(
                                  width: 12,
                                  height: 12,
                                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                                )
                              else
                                Icon(
                                  _latitude != null ? Icons.gps_fixed : Icons.gps_off,
                                  size: 14,
                                  color: _latitude != null ? AppColors.success : AppColors.error,
                                ),
                              const SizedBox(width: 6),
                              Text(
                                _locationError ??
                                    (_latitude != null
                                        ? '${_latitude!.toStringAsFixed(5)}, ${_longitude!.toStringAsFixed(5)}'
                                        : 'Getting GPS...'),
                                style: TextStyle(
                                  color: _locationError != null ? AppColors.warning : Colors.white,
                                  fontSize: 12,
                                ),
                              ),
                              if (_accuracy != null) ...[
                                const SizedBox(width: 4),
                                Text(
                                  '±${_accuracy!.toStringAsFixed(0)}m',
                                  style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 10),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ),
                    ),
                  ],
                )
              : const Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      CircularProgressIndicator(color: AppColors.accent),
                      SizedBox(height: 16),
                      Text('Initializing camera...', style: TextStyle(color: Colors.white)),
                    ],
                  ),
                ),
        ),

        // Controls
        Container(
          padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 32),
          color: Colors.black,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              // Gallery
              IconButton(
                onPressed: _pickFromGallery,
                icon: const Icon(Icons.photo_library, color: Colors.white, size: 28),
                tooltip: 'Gallery',
              ),
              // Capture button
              GestureDetector(
                onTap: _isCapturing ? null : _takePicture,
                child: Container(
                  width: 72,
                  height: 72,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.white, width: 4),
                  ),
                  child: Container(
                    margin: const EdgeInsets.all(4),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: _isCapturing ? Colors.grey : Colors.white,
                    ),
                  ),
                ),
              ),
              // Flash toggle
              IconButton(
                onPressed: () => _cameraService.toggleFlash(),
                icon: const Icon(Icons.flash_auto, color: Colors.white, size: 28),
                tooltip: 'Flash',
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildPreview() {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Image Preview
          Stack(
            children: [
              Image.file(
                _capturedImage!,
                height: 300,
                width: double.infinity,
                fit: BoxFit.cover,
              ),
              Positioned(
                bottom: 8,
                right: 8,
                child: TextButton.icon(
                  onPressed: _retake,
                  icon: const Icon(Icons.refresh, color: Colors.white, size: 18),
                  label: const Text('Retake', style: TextStyle(color: Colors.white)),
                  style: TextButton.styleFrom(
                    backgroundColor: Colors.black54,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                ),
              ),
            ],
          ),

          // Location info
          if (_latitude != null)
            Container(
              padding: const EdgeInsets.all(12),
              color: AppColors.primary.withOpacity(0.1),
              child: Row(
                children: [
                  const Icon(Icons.location_on, size: 18, color: AppColors.primary),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'GPS: ${_latitude!.toStringAsFixed(6)}, ${_longitude!.toStringAsFixed(6)} (±${_accuracy?.toStringAsFixed(0) ?? '?'}m)',
                      style: AppTextStyles.bodySmall.copyWith(color: AppColors.primary),
                    ),
                  ),
                ],
              ),
            ),

          // Field Tests Section
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Field Tests (Optional)', style: AppTextStyles.heading3),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: _buildFieldInput('pH Level', _phController, TextInputType.number),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _buildFieldInput('Hardness', _hardnessController, TextInputType.number),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: _buildFieldInput('Color', _colorController, TextInputType.text),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _buildFieldInput('Streak Color', _streakController, TextInputType.text),
                    ),
                  ],
                ),
                const SizedBox(height: 16),

                // Notes
                TextField(
                  controller: _notesController,
                  maxLines: 3,
                  decoration: InputDecoration(
                    labelText: 'Notes',
                    hintText: 'Add observations about the sample...',
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(color: AppColors.primary, width: 2),
                    ),
                  ),
                ),
                const SizedBox(height: 24),

                // Submit button
                Consumer<SampleProvider>(
                  builder: (context, samples, _) {
                    return SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: samples.isLoading ? null : _submit,
                        icon: samples.isLoading
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                              )
                            : const Icon(Icons.upload),
                        label: Text(
                          samples.isLoading ? 'Analyzing...' : 'Submit Sample',
                          style: const TextStyle(fontSize: 16, fontFamily: 'Poppins'),
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.primary,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                      ),
                    );
                  },
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFieldInput(String label, TextEditingController controller, TextInputType type) {
    return TextField(
      controller: controller,
      keyboardType: type,
      decoration: InputDecoration(
        labelText: label,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        isDense: true,
      ),
    );
  }

  Widget _cornerMarker(Alignment alignment) {
    return Container(
      width: 24,
      height: 24,
      decoration: BoxDecoration(
        border: Border(
          top: alignment.y < 0 ? const BorderSide(color: AppColors.accent, width: 3) : BorderSide.none,
          bottom: alignment.y > 0 ? const BorderSide(color: AppColors.accent, width: 3) : BorderSide.none,
          left: alignment.x < 0 ? const BorderSide(color: AppColors.accent, width: 3) : BorderSide.none,
          right: alignment.x > 0 ? const BorderSide(color: AppColors.accent, width: 3) : BorderSide.none,
        ),
      ),
    );
  }
}

class _AIMarkerPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppColors.accent.withOpacity(0.3)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;

    // Center crosshair
    final cx = size.width / 2;
    final cy = size.height / 2;
    canvas.drawLine(Offset(cx - 20, cy), Offset(cx + 20, cy), paint);
    canvas.drawLine(Offset(cx, cy - 20), Offset(cx, cy + 20), paint);

    // Center circle
    canvas.drawCircle(Offset(cx, cy), 30, paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
