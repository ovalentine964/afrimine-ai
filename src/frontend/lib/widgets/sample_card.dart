import 'dart:io';
import 'package:flutter/material.dart';
import '../models/sample_model.dart';
import '../utils/constants.dart';
import '../utils/helpers.dart';

class SampleCard extends StatelessWidget {
  final SampleModel sample;
  final VoidCallback? onTap;
  final VoidCallback? onDelete;

  const SampleCard({
    super.key,
    required this.sample,
    this.onTap,
    this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              // Thumbnail
              _buildThumbnail(),
              const SizedBox(width: 12),
              // Info
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            sample.mineralType ?? 'Unknown Mineral',
                            style: AppTextStyles.heading3.copyWith(fontSize: 15),
                          ),
                        ),
                        _buildStatusChip(),
                      ],
                    ),
                    const SizedBox(height: 4),
                    if (sample.confidence != null)
                      Text(
                        '${(sample.confidence! * 100).toStringAsFixed(1)}% confidence',
                        style: AppTextStyles.bodySmall,
                      ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Icon(Icons.access_time, size: 14, color: AppColors.textSecondary),
                        const SizedBox(width: 4),
                        Text(
                          Helpers.relativeTime(sample.createdAt),
                          style: AppTextStyles.caption,
                        ),
                        if (sample.hasLocation) ...[
                          const SizedBox(width: 12),
                          Icon(Icons.location_on, size: 14, color: AppColors.textSecondary),
                          const SizedBox(width: 4),
                          Text(
                            '${sample.latitude!.toStringAsFixed(4)}, ${sample.longitude!.toStringAsFixed(4)}',
                            style: AppTextStyles.caption,
                          ),
                        ],
                      ],
                    ),
                    if (sample.gradeEstimate != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        'Grade: ${sample.gradeEstimate!.toStringAsFixed(2)} g/t',
                        style: AppTextStyles.bodySmall.copyWith(
                          color: AppColors.primary,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              // Sync indicator
              if (!sample.synced)
                Padding(
                  padding: const EdgeInsets.only(left: 8),
                  child: Icon(Icons.cloud_off, size: 16, color: AppColors.warning),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildThumbnail() {
    return Container(
      width: 60,
      height: 60,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(10),
        color: AppColors.surface,
      ),
      clipBehavior: Clip.antiAlias,
      child: sample.imagePath != null
          ? Image.file(
              File(sample.imagePath!),
              fit: BoxFit.cover,
              errorBuilder: (_, __, ___) => _buildPlaceholder(),
            )
          : _buildPlaceholder(),
    );
  }

  Widget _buildPlaceholder() {
    return Container(
      color: AppColors.primary.withOpacity(0.1),
      child: Center(
        child: Icon(Icons.landscape, color: AppColors.primary, size: 28),
      ),
    );
  }

  Widget _buildStatusChip() {
    Color color;
    switch (sample.status) {
      case AppConstants.statusVerified:
        color = AppColors.verified;
        break;
      case AppConstants.statusAnalyzed:
        color = AppColors.analyzed;
        break;
      default:
        color = AppColors.pending;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        Helpers.statusLabel(sample.status),
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w600,
          color: color,
        ),
      ),
    );
  }
}
