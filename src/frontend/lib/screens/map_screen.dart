import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';

import '../models/sample.dart';
import '../services/camera_service.dart';
import '../services/offline_service.dart';

/// Map screen showing sample locations and satellite overlays.
///
/// Uses MapLibre GL for offline-capable map rendering.
/// Shows:
/// - Sample location pins with mineral type icons
/// - Satellite imagery overlay (when online)
/// - Current GPS position
/// - Heatmap of sample density
class MapScreen extends ConsumerStatefulWidget {
  const MapScreen({super.key});

  @override
  ConsumerState<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends ConsumerState<MapScreen> {
  SampleLocation? _currentLocation;
  List<MineralSample> _samples = [];
  bool _showSatellite = false;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final cameraService = ref.read(cameraServiceProvider);
    final offlineService = ref.read(offlineServiceProvider);

    final location = await cameraService.getCurrentLocation();
    final samples = await offlineService.getCachedSamples(limit: 200);

    if (mounted) {
      setState(() {
        _currentLocation = location;
        _samples = samples.where((s) => s.location != null).toList();
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Sample Map'),
        actions: [
          // Satellite toggle
          IconButton(
            icon: Icon(_showSatellite ? Icons.map : Icons.satellite),
            onPressed: () => setState(() => _showSatellite = !_showSatellite),
            tooltip: _showSatellite ? 'Map view' : 'Satellite view',
          ),
          // My location
          IconButton(
            icon: const Icon(Icons.my_location),
            onPressed: _goToMyLocation,
            tooltip: 'My location',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _buildMap(),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _loadData,
        icon: const Icon(Icons.refresh),
        label: const Text('Refresh'),
        backgroundColor: Colors.green[700],
      ),
    );
  }

  Widget _buildMap() {
    // MapLibre GL would be used here for the actual map.
    // For now, build a placeholder that shows the data structure.
    return Stack(
      children: [
        // Map placeholder (replace with MapLibreMap widget)
        Container(
          color: _showSatellite ? Colors.grey[900] : const Color(0xFFE8E0D8),
          child: CustomPaint(
            painter: _MapPainter(
              samples: _samples,
              currentLocation: _currentLocation,
              isSatellite: _showSatellite,
            ),
            size: Size.infinite,
          ),
        ),

        // Sample count badge
        Positioned(
          top: 16,
          left: 16,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: Colors.black87,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.location_on, color: Colors.red, size: 16),
                const SizedBox(width: 4),
                Text(
                  '${_samples.length} samples',
                  style: const TextStyle(color: Colors.white, fontSize: 13),
                ),
              ],
            ),
          ),
        ),

        // Legend
        Positioned(
          bottom: 80,
          right: 16,
          child: _buildLegend(),
        ),

        // Sample list bottom sheet
        Positioned(
          bottom: 0,
          left: 0,
          right: 0,
          child: _buildSampleListSheet(),
        ),
      ],
    );
  }

  Widget _buildLegend() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.black87,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Legend', style: TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w600)),
          const SizedBox(height: 6),
          _legendItem(Colors.amber, 'Gold'),
          _legendItem(Colors.brown, 'Copper'),
          _legendItem(Colors.grey, 'Silver'),
          _legendItem(Colors.red, 'Iron'),
          _legendItem(Colors.blue, 'Other'),
          const SizedBox(height: 4),
          _legendItem(Colors.green, 'You', icon: Icons.my_location),
        ],
      ),
    );
  }

  Widget _legendItem(Color color, String label, {IconData? icon}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 3),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          icon != null
              ? Icon(icon, color: color, size: 12)
              : Container(
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(color: color, shape: BoxShape.circle),
                ),
          const SizedBox(width: 6),
          Text(label, style: const TextStyle(color: Colors.white70, fontSize: 10)),
        ],
      ),
    );
  }

  Widget _buildSampleListSheet() {
    return DraggableScrollableSheet(
      initialChildSize: 0.15,
      minChildSize: 0.1,
      maxChildSize: 0.5,
      builder: (context, scrollController) {
        return Container(
          decoration: const BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
            boxShadow: [BoxShadow(color: Colors.black26, blurRadius: 10)],
          ),
          child: Column(
            children: [
              // Drag handle
              Container(
                margin: const EdgeInsets.only(top: 8),
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey[300],
                  borderRadius: BorderRadius.circular(2),
                ),
              ),

              // Header
              Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    const Text(
                      'Samples in this area',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                    ),
                    const Spacer(),
                    Text(
                      '${_samples.length}',
                      style: TextStyle(color: Colors.grey[600], fontSize: 14),
                    ),
                  ],
                ),
              ),

              // List
              Expanded(
                child: ListView.builder(
                  controller: scrollController,
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  itemCount: _samples.length,
                  itemBuilder: (context, index) {
                    final sample = _samples[index];
                    return _SampleListTile(sample: sample);
                  },
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  void _goToMyLocation() {
    // TODO: Animate map camera to current location
    if (_currentLocation != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Location: ${_currentLocation!.latitude.toStringAsFixed(4)}, ${_currentLocation!.longitude.toStringAsFixed(4)}',
          ),
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }
}

/// Custom painter for the map placeholder.
class _MapPainter extends CustomPainter {
  final List<MineralSample> samples;
  final SampleLocation? currentLocation;
  final bool isSatellite;

  _MapPainter({
    required this.samples,
    this.currentLocation,
    required this.isSatellite,
  });

  @override
  void paint(Canvas canvas, Size size) {
    // Background
    final bgPaint = Paint()
      ..color = isSatellite ? const Color(0xFF2D3436) : const Color(0xFFE8E0D8);
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, size.height), bgPaint);

    // Grid lines (roads/paths)
    final gridPaint = Paint()
      ..color = isSatellite ? Colors.white12 : Colors.black12
      ..strokeWidth = 1;

    for (double x = 0; x < size.width; x += 60) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), gridPaint);
    }
    for (double y = 0; y < size.height; y += 60) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    // Sample pins
    if (samples.isNotEmpty) {
      // Distribute samples across the map area
      final random = samples.length;
      for (int i = 0; i < samples.length; i++) {
        final sample = samples[i];
        final x = 40.0 + (i * 73.0 % (size.width - 80));
        final y = 80.0 + (i * 137.0 % (size.height - 200));

        // Pin shadow
        final shadowPaint = Paint()
          ..color = Colors.black26
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 3);
        canvas.drawCircle(Offset(x + 2, y + 2), 8, shadowPaint);

        // Pin
        final pinPaint = Paint()
          ..color = _sampleColor(sample);
        canvas.drawCircle(Offset(x, y), 8, pinPaint);

        // Pin border
        final borderPaint = Paint()
          ..color = Colors.white
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2;
        canvas.drawCircle(Offset(x, y), 8, borderPaint);
      }
    }

    // Current location marker
    if (currentLocation != null) {
      final cx = size.width / 2;
      final cy = size.height / 2;

      // Accuracy circle
      final accuracyPaint = Paint()
        ..color = Colors.blue.withOpacity(0.15);
      canvas.drawCircle(Offset(cx, cy), 30, accuracyPaint);

      // Dot
      final dotPaint = Paint()..color = Colors.blue;
      canvas.drawCircle(Offset(cx, cy), 8, dotPaint);

      // Border
      final borderPaint = Paint()
        ..color = Colors.white
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3;
      canvas.drawCircle(Offset(cx, cy), 8, borderPaint);
    }

    // "Tap to open full map" text
    final textPainter = TextPainter(
      text: TextSpan(
        text: 'Install MapLibre GL for full map',
        style: TextStyle(color: Colors.grey[500], fontSize: 12),
      ),
      textDirection: TextDirection.ltr,
    );
    textPainter.layout();
    textPainter.paint(
      canvas,
      Offset(
        (size.width - textPainter.width) / 2,
        size.height - 40,
      ),
    );
  }

  Color _sampleColor(MineralSample sample) {
    // Color based on field notes or XRF data
    final notes = sample.fieldNotes?.toLowerCase() ?? '';
    if (notes.contains('gold') || notes.contains('au')) return Colors.amber;
    if (notes.contains('copper') || notes.contains('cu')) return Colors.brown;
    if (notes.contains('silver') || notes.contains('ag')) return Colors.grey;
    if (notes.contains('iron') || notes.contains('fe')) return Colors.red;
    return Colors.blue;
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}

/// List tile for a sample in the bottom sheet.
class _SampleListTile extends StatelessWidget {
  final MineralSample sample;

  const _SampleListTile({required this.sample});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      dense: true,
      leading: Container(
        width: 36,
        height: 36,
        decoration: BoxDecoration(
          color: Colors.green.withOpacity(0.1),
          borderRadius: BorderRadius.circular(8),
        ),
        child: const Icon(Icons.location_on, color: Colors.green, size: 20),
      ),
      title: Text(
        sample.displayName,
        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
      ),
      subtitle: Text(
        sample.location?.toString() ?? 'No GPS',
        style: TextStyle(fontSize: 12, color: Colors.grey[600]),
      ),
      trailing: sample.isSynced
          ? const Icon(Icons.cloud_done, color: Colors.green, size: 16)
          : const Icon(Icons.cloud_off, color: Colors.orange, size: 16),
    );
  }
}
