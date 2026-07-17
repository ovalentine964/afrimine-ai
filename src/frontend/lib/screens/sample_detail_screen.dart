import 'dart:io';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import '../models/sample_model.dart';
import '../providers/sample_provider.dart';
import '../utils/constants.dart';
import '../utils/helpers.dart';
import '../widgets/offline_banner.dart';

class SampleDetailScreen extends StatelessWidget {
  final String sampleId;

  const SampleDetailScreen({super.key, required this.sampleId});

  @override
  Widget build(BuildContext context) {
    final samples = context.watch<SampleProvider>();
    final sample = samples.samples.where((s) => s.id == sampleId).firstOrNull ??
        samples.selectedSample;

    if (sample == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Sample Details')),
        body: const Center(child: Text('Sample not found')),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Sample Details'),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.edit),
            onPressed: () => _showEditDialog(context, sample),
          ),
          IconButton(
            icon: const Icon(Icons.delete),
            onPressed: () => _confirmDelete(context, sample),
          ),
        ],
      ),
      body: OfflineBanner(
        child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Image
            _buildImageSection(sample),

            // Status bar
            _buildStatusBar(sample),

            // AI Classification
            _buildClassificationSection(sample),

            // Location Map
            if (sample.hasLocation) _buildLocationSection(sample),

            // Field Tests
            if (sample.fieldTests != null && sample.fieldTests!.isNotEmpty)
              _buildFieldTestsSection(sample),

            // Notes
            if (sample.notes != null && sample.notes!.isNotEmpty)
              _buildNotesSection(sample),

            // Metadata
            _buildMetadataSection(sample),

            const SizedBox(height: 24),
          ],
        ),
      ),
      ),
    );
  }

  Widget _buildImageSection(SampleModel sample) {
    return Container(
      height: 280,
      color: Colors.black,
      child: sample.imagePath != null
          ? Image.file(
              File(sample.imagePath!),
              fit: BoxFit.contain,
              errorBuilder: (_, __, ___) => _imagePlaceholder(),
            )
          : sample.imageUrl != null
              ? Image.network(
                  sample.imageUrl!,
                  fit: BoxFit.contain,
                  errorBuilder: (_, __, ___) => _imagePlaceholder(),
                )
              : _imagePlaceholder(),
    );
  }

  Widget _imagePlaceholder() {
    return Container(
      color: AppColors.surface,
      child: const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.image_not_supported, size: 48, color: AppColors.textSecondary),
            SizedBox(height: 8),
            Text('No image available', style: AppTextStyles.bodySmall),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusBar(SampleModel sample) {
    Color statusColor;
    IconData statusIcon;
    switch (sample.status) {
      case AppConstants.statusVerified:
        statusColor = AppColors.verified;
        statusIcon = Icons.verified;
        break;
      case AppConstants.statusAnalyzed:
        statusColor = AppColors.analyzed;
        statusIcon = Icons.analytics;
        break;
      default:
        statusColor = AppColors.pending;
        statusIcon = Icons.hourglass_empty;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      color: statusColor.withOpacity(0.1),
      child: Row(
        children: [
          Icon(statusIcon, color: statusColor, size: 20),
          const SizedBox(width: 8),
          Text(
            Helpers.statusLabel(sample.status),
            style: TextStyle(
              color: statusColor,
              fontWeight: FontWeight.w600,
              
            ),
          ),
          const Spacer(),
          if (!sample.synced)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: AppColors.warning.withOpacity(0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.cloud_off, size: 14, color: AppColors.warning),
                  SizedBox(width: 4),
                  Text('Not synced', style: TextStyle(fontSize: 11, color: AppColors.warning)),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildClassificationSection(SampleModel sample) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Card(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        elevation: 2,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppColors.primary.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.auto_awesome, color: AppColors.primary, size: 20),
                  ),
                  const SizedBox(width: 10),
                  const Text('AI Classification', style: AppTextStyles.heading3),
                ],
              ),
              const Divider(height: 24),
              _buildInfoRow('Mineral Type', sample.mineralType ?? 'Pending analysis'),
              if (sample.confidence != null)
                _buildInfoRow('Confidence', '${(sample.confidence! * 100).toStringAsFixed(1)}%'),
              if (sample.gradeEstimate != null)
                _buildInfoRow('Grade Estimate', '${sample.gradeEstimate!.toStringAsFixed(2)} g/t'),

              // Confidence bar
              if (sample.confidence != null) ...[
                const SizedBox(height: 12),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: sample.confidence,
                    backgroundColor: AppColors.surface,
                    valueColor: AlwaysStoppedAnimation<Color>(
                      sample.confidence! > 0.7
                          ? AppColors.success
                          : sample.confidence! > 0.4
                              ? AppColors.warning
                              : AppColors.error,
                    ),
                    minHeight: 8,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  sample.confidence! > 0.7
                      ? 'High confidence'
                      : sample.confidence! > 0.4
                          ? 'Medium confidence'
                          : 'Low confidence — consider field verification',
                  style: AppTextStyles.caption,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLocationSection(SampleModel sample) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Card(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        elevation: 2,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppColors.info.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.location_on, color: AppColors.info, size: 20),
                  ),
                  const SizedBox(width: 10),
                  const Text('Location', style: AppTextStyles.heading3),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(
                Helpers.formatCoordinate(sample.latitude!, sample.longitude!),
                style: AppTextStyles.body,
              ),
            ),
            if (sample.accuracy != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
                child: Text(
                  'Accuracy: ±${sample.accuracy!.toStringAsFixed(0)} meters',
                  style: AppTextStyles.caption,
                ),
              ),
            // Mini map
            ClipRRect(
              borderRadius: const BorderRadius.vertical(bottom: Radius.circular(14)),
              child: SizedBox(
                height: 200,
                child: FlutterMap(
                  options: MapOptions(
                    initialCenter: LatLng(sample.latitude!, sample.longitude!),
                    initialZoom: 15,
                    interactionOptions: const InteractionOptions(
                      flags: InteractiveFlag.pinchZoom | InteractiveFlag.drag,
                    ),
                  ),
                  children: [
                    TileLayer(
                      urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                      userAgentPackageName: 'com.afrimine.ai',
                    ),
                    MarkerLayer(
                      markers: [
                        Marker(
                          point: LatLng(sample.latitude!, sample.longitude!),
                          width: 40,
                          height: 40,
                          child: Container(
                            decoration: BoxDecoration(
                              color: AppColors.primary,
                              shape: BoxShape.circle,
                              border: Border.all(color: Colors.white, width: 3),
                              boxShadow: [
                                BoxShadow(
                                  color: AppColors.primary.withOpacity(0.4),
                                  blurRadius: 8,
                                  spreadRadius: 2,
                                ),
                              ],
                            ),
                            child: const Icon(Icons.location_on, color: Colors.white, size: 20),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFieldTestsSection(SampleModel sample) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Card(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        elevation: 2,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppColors.warning.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.science, color: AppColors.warning, size: 20),
                  ),
                  const SizedBox(width: 10),
                  const Text('Field Test Results', style: AppTextStyles.heading3),
                ],
              ),
              const Divider(height: 24),
              ...sample.fieldTests!.entries.map((e) =>
                  _buildInfoRow(_formatFieldName(e.key), '${e.value}')),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildNotesSection(SampleModel sample) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Card(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        elevation: 2,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Notes', style: AppTextStyles.heading3),
              const SizedBox(height: 8),
              Text(sample.notes!, style: AppTextStyles.body),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMetadataSection(SampleModel sample) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Card(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        elevation: 1,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Details', style: AppTextStyles.heading3),
              const Divider(height: 24),
              _buildInfoRow('Sample ID', sample.id.substring(0, 8)),
              _buildInfoRow('Created', Helpers.formatDateTime(sample.createdAt)),
              _buildInfoRow('Updated', Helpers.formatDateTime(sample.updatedAt)),
              _buildInfoRow('Sync Status', sample.synced ? 'Synced ✓' : 'Not synced'),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(label, style: AppTextStyles.bodySmall),
          ),
          Expanded(
            child: Text(value, style: AppTextStyles.body.copyWith(fontWeight: FontWeight.w500)),
          ),
        ],
      ),
    );
  }

  String _formatFieldName(String key) {
    return key
        .replaceAll('_', ' ')
        .split(' ')
        .map((w) => w[0].toUpperCase() + w.substring(1))
        .join(' ');
  }

  void _showEditDialog(BuildContext context, SampleModel sample) {
    final notesController = TextEditingController(text: sample.notes);

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => Padding(
        padding: EdgeInsets.fromLTRB(24, 24, 24, MediaQuery.of(ctx).viewInsets.bottom + 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text('Edit Sample', style: AppTextStyles.heading2),
            const SizedBox(height: 16),
            TextField(
              controller: notesController,
              maxLines: 4,
              decoration: InputDecoration(
                labelText: 'Notes',
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () {
                context.read<SampleProvider>().updateSample(
                      sample.copyWith(notes: notesController.text.trim()),
                    );
                Navigator.pop(ctx);
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: const Text('Save Changes'),
            ),
          ],
        ),
      ),
    );
  }

  void _confirmDelete(BuildContext context, SampleModel sample) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Sample'),
        content: const Text('Are you sure? This action cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              context.read<SampleProvider>().deleteSample(sample.id);
              Navigator.pop(ctx);
              context.pop();
            },
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }
}
