import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/analysis.dart';
import '../services/offline_service.dart';
import '../widgets/mineral_card.dart';

/// Reports screen — list and view generated analysis reports.
///
/// Features:
/// - List of all analyses with status badges
/// - Filter by mineral type, status, date
/// - Pull-to-refresh from server
/// - Tap to view full report
class ReportsScreen extends ConsumerStatefulWidget {
  const ReportsScreen({super.key});

  @override
  ConsumerState<ReportsScreen> createState() => _ReportsScreenState();
}

class _ReportsScreenState extends ConsumerState<ReportsScreen> {
  AnalysisStatus? _statusFilter;
  String? _mineralFilter;
  bool _isRefreshing = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Reports'),
        actions: [
          IconButton(
            icon: const Icon(Icons.filter_list),
            onPressed: _showFilterSheet,
          ),
        ],
      ),
      body: Column(
        children: [
          // Filter chips
          if (_statusFilter != null || _mineralFilter != null)
            _buildActiveFilters(theme),

          // Reports list
          Expanded(
            child: _buildReportsList(theme),
          ),
        ],
      ),
    );
  }

  Widget _buildActiveFilters(ThemeData theme) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      color: Colors.grey.withOpacity(0.05),
      child: Row(
        children: [
          if (_statusFilter != null)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: Chip(
                label: Text(_statusFilter!.name),
                onDeleted: () => setState(() => _statusFilter = null),
                visualDensity: VisualDensity.compact,
              ),
            ),
          if (_mineralFilter != null)
            Chip(
              label: Text(_mineralFilter!),
              onDeleted: () => setState(() => _mineralFilter = null),
              visualDensity: VisualDensity.compact,
            ),
          const Spacer(),
          TextButton(
            onPressed: () => setState(() {
              _statusFilter = null;
              _mineralFilter = null;
            }),
            child: const Text('Clear All'),
          ),
        ],
      ),
    );
  }

  Widget _buildReportsList(ThemeData theme) {
    final offlineService = ref.watch(offlineServiceProvider);

    return FutureBuilder<List<Analysis>>(
      future: offlineService.getCachedAnalyses(limit: 100),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }

        var analyses = snapshot.data ?? [];

        // Apply filters
        if (_statusFilter != null) {
          analyses = analyses.where((a) => a.status == _statusFilter).toList();
        }
        if (_mineralFilter != null) {
          analyses = analyses.where((a) {
            final minerals = a.analysisResult?.detectedMinerals ?? [];
            return minerals.any((m) => m.toLowerCase() == _mineralFilter!.toLowerCase());
          }).toList();
        }

        if (analyses.isEmpty) {
          return _buildEmptyState(theme);
        }

        return RefreshIndicator(
          onRefresh: _refreshFromServer,
          child: ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: analyses.length,
            itemBuilder: (context, index) {
              final analysis = analyses[index];
              return Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _ReportListItem(
                  analysis: analysis,
                  onTap: () => context.push('/analysis/${analysis.id}'),
                  onShare: () => _shareReport(analysis),
                  onViewPdf: analysis.reportUrl != null
                      ? () => _openReport(analysis.reportUrl!)
                      : null,
                ),
              );
            },
          ),
        );
      },
    );
  }

  Widget _buildEmptyState(ThemeData theme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.assessment, size: 64, color: Colors.grey[400]),
            const SizedBox(height: 16),
            Text(
              'No reports yet',
              style: theme.textTheme.titleMedium?.copyWith(color: Colors.grey[600]),
            ),
            const SizedBox(height: 8),
            Text(
              'Analyze mineral samples to generate reports',
              style: theme.textTheme.bodyMedium?.copyWith(color: Colors.grey[500]),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  void _showFilterSheet() {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (context) => Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Filter Reports', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
            const SizedBox(height: 16),

            const Text('Status', style: TextStyle(fontWeight: FontWeight.w500)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: AnalysisStatus.values.map((status) {
                final isSelected = _statusFilter == status;
                return FilterChip(
                  label: Text(status.name),
                  selected: isSelected,
                  onSelected: (selected) {
                    setState(() => _statusFilter = selected ? status : null);
                    Navigator.pop(context);
                  },
                );
              }).toList(),
            ),

            const SizedBox(height: 16),
            const Text('Common Minerals', style: TextStyle(fontWeight: FontWeight.w500)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: ['Gold', 'Copper', 'Silver', 'Iron', 'Titanium'].map((mineral) {
                final isSelected = _mineralFilter?.toLowerCase() == mineral.toLowerCase();
                return FilterChip(
                  label: Text(mineral),
                  selected: isSelected,
                  onSelected: (selected) {
                    setState(() => _mineralFilter = selected ? mineral : null);
                    Navigator.pop(context);
                  },
                );
              }).toList(),
            ),

            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }

  Future<void> _refreshFromServer() async {
    setState(() => _isRefreshing = true);
    // TODO: Fetch from API and update local cache
    await Future.delayed(const Duration(seconds: 1));
    if (mounted) setState(() => _isRefreshing = false);
  }

  void _shareReport(Analysis analysis) {
    // TODO: Implement share via share_plus
  }

  Future<void> _openReport(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }
}

/// Individual report list item with actions.
class _ReportListItem extends StatelessWidget {
  final Analysis analysis;
  final VoidCallback onTap;
  final VoidCallback? onShare;
  final VoidCallback? onViewPdf;

  const _ReportListItem({
    required this.analysis,
    required this.onTap,
    this.onShare,
    this.onViewPdf,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final minerals = analysis.analysisResult?.detectedMinerals ?? [];
    final dominant = analysis.analysisResult?.dominantMineral ??
        (minerals.isNotEmpty ? minerals.first : 'Unknown');

    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Row(
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: _mineralColor(dominant).withOpacity(0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Center(child: Text(_mineralEmoji(dominant), style: const TextStyle(fontSize: 20))),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          analysis.displayTitle,
                          style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600),
                        ),
                        Text(
                          _formatDate(analysis.createdAt),
                          style: theme.textTheme.bodySmall?.copyWith(color: Colors.grey[600]),
                        ),
                      ],
                    ),
                  ),
                  _buildStatusBadge(),
                ],
              ),

              const SizedBox(height: 12),

              // Stats row
              Row(
                children: [
                  _miniStat(Icons.science, '${minerals.length} minerals'),
                  const SizedBox(width: 16),
                  if (analysis.confidenceScore != null)
                    _miniStat(Icons.speed, analysis.confidencePercent),
                  const SizedBox(width: 16),
                  if (analysis.estimatedValueUsd != null)
                    _miniStat(Icons.attach_money, analysis.formattedValue),
                ],
              ),

              // Actions
              if (onShare != null || onViewPdf != null) ...[
                const Divider(height: 24),
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    if (onViewPdf != null)
                      TextButton.icon(
                        onPressed: onViewPdf,
                        icon: const Icon(Icons.picture_as_pdf, size: 16),
                        label: const Text('PDF'),
                      ),
                    if (onShare != null)
                      TextButton.icon(
                        onPressed: onShare,
                        icon: const Icon(Icons.share, size: 16),
                        label: const Text('Share'),
                      ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatusBadge() {
    Color color;
    switch (analysis.status) {
      case AnalysisStatus.pending:
        color = Colors.grey;
        break;
      case AnalysisStatus.running:
        color = Colors.blue;
        break;
      case AnalysisStatus.completed:
        color = Colors.green;
        break;
      case AnalysisStatus.failed:
        color = Colors.red;
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Text(
        analysis.status.name,
        style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w500),
      ),
    );
  }

  Widget _miniStat(IconData icon, String value) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: Colors.grey[600]),
        const SizedBox(width: 4),
        Text(value, style: TextStyle(fontSize: 12, color: Colors.grey[600])),
      ],
    );
  }

  Color _mineralColor(String mineral) {
    switch (mineral.toLowerCase()) {
      case 'gold':
        return const Color(0xFFFFD700);
      case 'copper':
        return const Color(0xFFB87333);
      case 'silver':
        return const Color(0xFFC0C0C0);
      default:
        return const Color(0xFF6B7280);
    }
  }

  String _mineralEmoji(String mineral) {
    switch (mineral.toLowerCase()) {
      case 'gold':
        return '🪙';
      case 'copper':
        return '🟤';
      case 'silver':
        return '⚪';
      default:
        return '⛏️';
    }
  }

  String _formatDate(DateTime dt) {
    return '${dt.day}/${dt.month}/${dt.year} ${dt.hour}:${dt.minute.toString().padLeft(2, '0')}';
  }
}
