import 'package:flutter/material.dart';

import '../models/analysis.dart';

/// Reusable card displaying a mineral analysis result.
///
/// Shows:
/// - Mineral name with confidence badge
/// - Grade estimate
/// - Estimated value
/// - Status indicator
/// - Tap to view full analysis
class MineralCard extends StatelessWidget {
  final Analysis analysis;
  final VoidCallback? onTap;
  final bool compact;

  const MineralCard({
    super.key,
    required this.analysis,
    this.onTap,
    this.compact = false,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final minerals = analysis.analysisResult?.detectedMinerals ?? [];
    final dominant = analysis.analysisResult?.dominantMineral ??
        (minerals.isNotEmpty ? minerals.first : 'Unknown');

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                _mineralColor(dominant).withOpacity(0.08),
                theme.cardColor,
              ],
            ),
          ),
          child: compact ? _buildCompact(theme, dominant) : _buildFull(theme, dominant, minerals),
        ),
      ),
    );
  }

  Widget _buildCompact(ThemeData theme, String dominant) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: Row(
        children: [
          _buildMineralIcon(dominant, 36),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  dominant,
                  style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  analysis.confidencePercent,
                  style: theme.textTheme.bodySmall?.copyWith(color: Colors.grey[600]),
                ),
              ],
            ),
          ),
          _buildStatusChip(theme),
        ],
      ),
    );
  }

  Widget _buildFull(ThemeData theme, String dominant, List<String> minerals) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header row
          Row(
            children: [
              _buildMineralIcon(dominant, 44),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      dominant,
                      style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
                    ),
                    if (analysis.analysisResult?.rockType != null)
                      Text(
                        analysis.analysisResult!.rockType!,
                        style: theme.textTheme.bodySmall?.copyWith(color: Colors.grey[600]),
                      ),
                  ],
                ),
              ),
              _buildStatusChip(theme),
            ],
          ),

          const SizedBox(height: 12),

          // Confidence bar
          _buildConfidenceBar(theme),

          const SizedBox(height: 12),

          // Info row
          Row(
            children: [
              _buildInfoChip(
                icon: Icons.science,
                label: '${minerals.length} mineral${minerals.length != 1 ? 's' : ''}',
                color: Colors.blue,
              ),
              const SizedBox(width: 8),
              if (analysis.estimatedGrade != null)
                _buildInfoChip(
                  icon: Icons.trending_up,
                  label: '${analysis.estimatedGrade!.toStringAsFixed(1)} ${analysis.gradeUnit ?? 'ppm'}',
                  color: Colors.orange,
                ),
              const SizedBox(width: 8),
              if (analysis.estimatedValueUsd != null)
                _buildInfoChip(
                  icon: Icons.attach_money,
                  label: analysis.formattedValue,
                  color: Colors.green,
                ),
            ],
          ),

          // Detected minerals chips
          if (minerals.length > 1) ...[
            const SizedBox(height: 8),
            Wrap(
              spacing: 4,
              runSpacing: 4,
              children: minerals.take(5).map((m) {
                return Chip(
                  label: Text(m, style: const TextStyle(fontSize: 11)),
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  visualDensity: VisualDensity.compact,
                  padding: EdgeInsets.zero,
                  labelPadding: const EdgeInsets.symmetric(horizontal: 6),
                );
              }).toList(),
            ),
          ],

          // Timestamp
          const SizedBox(height: 8),
          Row(
            children: [
              Icon(Icons.access_time, size: 14, color: Colors.grey[500]),
              const SizedBox(width: 4),
              Text(
                _formatTimestamp(analysis.createdAt),
                style: theme.textTheme.bodySmall?.copyWith(color: Colors.grey[500]),
              ),
              const Spacer(),
              if (analysis.pipelineDurationMs != null)
                Text(
                  '⏱ ${analysis.durationText}',
                  style: theme.textTheme.bodySmall?.copyWith(color: Colors.grey[500]),
                ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMineralIcon(String mineral, double size) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: _mineralColor(mineral).withOpacity(0.15),
        borderRadius: BorderRadius.circular(size * 0.25),
      ),
      child: Center(
        child: Text(
          _mineralEmoji(mineral),
          style: TextStyle(fontSize: size * 0.5),
        ),
      ),
    );
  }

  Widget _buildConfidenceBar(ThemeData theme) {
    final score = analysis.confidenceScore ?? 0.0;
    final color = score >= 0.8
        ? Colors.green
        : score >= 0.6
            ? Colors.orange
            : Colors.red;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('Confidence', style: theme.textTheme.bodySmall),
            Text(
              analysis.confidencePercent,
              style: theme.textTheme.bodySmall?.copyWith(
                fontWeight: FontWeight.w600,
                color: color,
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: score,
            backgroundColor: Colors.grey[200],
            valueColor: AlwaysStoppedAnimation(color),
            minHeight: 6,
          ),
        ),
      ],
    );
  }

  Widget _buildStatusChip(ThemeData theme) {
    Color color;
    String label;
    IconData icon;

    switch (analysis.status) {
      case AnalysisStatus.pending:
        color = Colors.grey;
        label = 'Pending';
        icon = Icons.schedule;
        break;
      case AnalysisStatus.running:
        color = Colors.blue;
        label = 'Running';
        icon = Icons.sync;
        break;
      case AnalysisStatus.completed:
        color = Colors.green;
        label = 'Done';
        icon = Icons.check_circle;
        break;
      case AnalysisStatus.failed:
        color = Colors.red;
        label = 'Failed';
        icon = Icons.error;
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }

  Widget _buildInfoChip({
    required IconData icon,
    required String label,
    required Color color,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(color: color, fontSize: 12)),
        ],
      ),
    );
  }

  Color _mineralColor(String mineral) {
    switch (mineral.toLowerCase()) {
      case 'gold':
      case 'au':
        return const Color(0xFFFFD700);
      case 'copper':
      case 'cu':
        return const Color(0xFFB87333);
      case 'silver':
      case 'ag':
        return const Color(0xFFC0C0C0);
      case 'iron':
      case 'fe':
        return const Color(0xFF8B4513);
      case 'titanium':
      case 'ti':
        return const Color(0xFF708090);
      case 'zinc':
      case 'zn':
        return const Color(0xFF4682B4);
      case 'lead':
      case 'pb':
        return const Color(0xFF696969);
      default:
        return const Color(0xFF6B7280);
    }
  }

  String _mineralEmoji(String mineral) {
    switch (mineral.toLowerCase()) {
      case 'gold':
      case 'au':
        return '🪙';
      case 'copper':
      case 'cu':
        return '🟤';
      case 'silver':
      case 'ag':
        return '⚪';
      case 'iron':
      case 'fe':
        return '🔴';
      case 'titanium':
      case 'ti':
        return '⚫';
      default:
        return '⛏️';
    }
  }

  String _formatTimestamp(DateTime dt) {
    final now = DateTime.now();
    final diff = now.difference(dt);

    if (diff.inMinutes < 1) return 'Just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${dt.day}/${dt.month}/${dt.year}';
  }
}
