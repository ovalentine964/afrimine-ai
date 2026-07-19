import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../models/analysis.dart';
import '../services/api_service.dart';
import '../services/offline_service.dart';

/// Screen showing analysis results.
///
/// Two modes:
/// 1. New analysis — shows streaming progress as agents work
/// 2. View existing — shows completed results with all agent outputs
class AnalysisScreen extends ConsumerStatefulWidget {
  final String analysisId;

  const AnalysisScreen({super.key, required this.analysisId});

  @override
  ConsumerState<AnalysisScreen> createState() => _AnalysisScreenState();
}

class _AnalysisScreenState extends ConsumerState<AnalysisScreen> {
  Analysis? _analysis;
  bool _isLoading = true;
  String? _error;
  List<AnalysisUpdate> _updates = [];
  StreamSubscription<AnalysisUpdate>? _streamSub;

  @override
  void initState() {
    super.initState();
    _loadAnalysis();
  }

  @override
  void dispose() {
    _streamSub?.cancel();
    super.dispose();
  }

  Future<void> _loadAnalysis() async {
    final offlineService = ref.read(offlineServiceProvider);

    if (widget.analysisId == 'new') {
      // New analysis — create from latest sample
      setState(() {
        _isLoading = false;
        _analysis = null;
      });
      return;
    }

    // Load existing analysis
    final analysis = await offlineService.getCachedAnalysis(widget.analysisId);

    if (mounted) {
      setState(() {
        _analysis = analysis;
        _isLoading = false;
      });

      // If running, stream progress
      if (analysis?.status == AnalysisStatus.running) {
        _startStreaming(analysis!.id);
      }
    }
  }

  void _startStreaming(String analysisId) {
    final apiService = ref.read(apiServiceProvider);
    _streamSub = apiService.streamAnalysisProgress(analysisId).listen(
      (update) {
        if (mounted) {
          setState(() => _updates.add(update));
        }
      },
      onDone: () {
        // Reload analysis when stream completes
        _loadAnalysis();
      },
      onError: (_) {
        _loadAnalysis();
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(_analysis?.displayTitle ?? 'Analysis'),
        actions: [
          if (_analysis?.status == AnalysisStatus.completed)
            IconButton(
              icon: const Icon(Icons.share),
              onPressed: _shareAnalysis,
            ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError(theme)
              : widget.analysisId == 'new'
                  ? _buildNewAnalysis(theme)
                  : _analysis != null
                      ? _buildAnalysisResult(theme)
                      : _buildNotFound(theme),
    );
  }

  Widget _buildError(ThemeData theme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 64, color: Colors.red),
            const SizedBox(height: 16),
            Text(_error!, textAlign: TextAlign.center),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: _loadAnalysis,
              child: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNotFound(ThemeData theme) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.search_off, size: 64, color: Colors.grey[400]),
          const SizedBox(height: 16),
          Text('Analysis not found', style: theme.textTheme.titleMedium),
        ],
      ),
    );
  }

  Widget _buildNewAnalysis(ThemeData theme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.science, size: 64, color: Colors.blue),
            const SizedBox(height: 16),
            Text(
              'Start New Analysis',
              style: theme.textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            Text(
              'Capture a mineral sample first, then analyze it.',
              style: theme.textTheme.bodyMedium?.copyWith(color: Colors.grey[600]),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () => context.push('/camera'),
              icon: const Icon(Icons.camera_alt),
              label: const Text('Capture Sample'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.green[700],
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAnalysisResult(ThemeData theme) {
    final analysis = _analysis!;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Status header
          _buildStatusHeader(theme, analysis),

          // Agent progress (if running)
          if (analysis.status == AnalysisStatus.running) ...[
            const SizedBox(height: 16),
            _buildAgentProgress(theme),
          ],

          const SizedBox(height: 16),

          // Mineral identification
          if (analysis.analysisResult != null) ...[
            _buildSectionTitle(theme, 'Mineral Identification'),
            _buildMineralSection(theme, analysis.analysisResult!),
          ],

          // Geological context
          if (analysis.geologyResult != null) ...[
            const SizedBox(height: 16),
            _buildSectionTitle(theme, 'Geological Context'),
            _buildGeologySection(theme, analysis.geologyResult!),
          ],

          // Market valuation
          if (analysis.marketResult != null) ...[
            const SizedBox(height: 16),
            _buildSectionTitle(theme, 'Market Valuation'),
            _buildMarketSection(theme, analysis.marketResult!),
          ],

          // Compliance
          if (analysis.complianceResult != null) ...[
            const SizedBox(height: 16),
            _buildSectionTitle(theme, 'Compliance Status'),
            _buildComplianceSection(theme, analysis.complianceResult!),
          ],

          const SizedBox(height: 24),

          // Action buttons
          _buildActionButtons(theme, analysis),

          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildStatusHeader(ThemeData theme, Analysis analysis) {
    Color color;
    IconData icon;
    String text;

    switch (analysis.status) {
      case AnalysisStatus.pending:
        color = Colors.grey;
        icon = Icons.schedule;
        text = 'Waiting to start...';
        break;
      case AnalysisStatus.running:
        color = Colors.blue;
        icon = Icons.sync;
        text = 'Analysis in progress...';
        break;
      case AnalysisStatus.completed:
        color = Colors.green;
        icon = Icons.check_circle;
        text = 'Analysis complete';
        break;
      case AnalysisStatus.failed:
        color = Colors.red;
        icon = Icons.error;
        text = 'Analysis failed';
        break;
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 28),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(text, style: TextStyle(color: color, fontWeight: FontWeight.w600)),
                if (analysis.pipelineDurationMs != null)
                  Text(
                    'Completed in ${analysis.durationText}',
                    style: theme.textTheme.bodySmall?.copyWith(color: color.withOpacity(0.8)),
                  ),
              ],
            ),
          ),
          if (analysis.confidenceScore != null)
            _buildConfidenceBadge(analysis.confidenceScore!),
        ],
      ),
    );
  }

  Widget _buildConfidenceBadge(double score) {
    final color = score >= 0.8
        ? Colors.green
        : score >= 0.6
            ? Colors.orange
            : Colors.red;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Text(
        '${(score * 100).round()}%',
        style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: 16),
      ),
    );
  }

  Widget _buildAgentProgress(ThemeData theme) {
    final agents = [
      _AgentInfo('Sampling', Icons.map, 0),
      _AgentInfo('Analysis', Icons.science, 1),
      _AgentInfo('Geology', Icons.landscape, 2),
      _AgentInfo('Market', Icons.trending_up, 3),
      _AgentInfo('Report', Icons.description, 4),
      _AgentInfo('Compliance', Icons.verified, 5),
    ];

    return Column(
      children: agents.map((agent) {
        final update = _updates.lastWhere(
          (u) => u.agent.toLowerCase() == agent.name.toLowerCase(),
          orElse: () => const AnalysisUpdate(agent: '', status: 'pending', progress: 0),
        );

        final isComplete = update.status == 'completed';
        final isRunning = update.status == 'working';
        final progress = isComplete ? 1.0 : update.progress;

        return Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Row(
            children: [
              Icon(
                isComplete
                    ? Icons.check_circle
                    : isRunning
                        ? Icons.sync
                        : Icons.radio_button_unchecked,
                color: isComplete
                    ? Colors.green
                    : isRunning
                        ? Colors.blue
                        : Colors.grey,
                size: 20,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(agent.name, style: theme.textTheme.bodySmall),
                    if (isRunning)
                      ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: progress,
                          minHeight: 4,
                          backgroundColor: Colors.grey[200],
                        ),
                      ),
                  ],
                ),
              ),
              if (update.message != null)
                Flexible(
                  child: Text(
                    update.message!,
                    style: theme.textTheme.bodySmall?.copyWith(color: Colors.grey[600]),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
            ],
          ),
        );
      }).toList(),
    );
  }

  Widget _buildSectionTitle(ThemeData theme, String title) {
    return Text(
      title,
      style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
    );
  }

  Widget _buildMineralSection(ThemeData theme, AnalysisResult result) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Dominant mineral
            if (result.dominantMineral != null)
              Text(
                result.dominantMineral!,
                style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700),
              ),
            if (result.rockType != null)
              Text(
                'Rock type: ${result.rockType}',
                style: theme.textTheme.bodyMedium?.copyWith(color: Colors.grey[600]),
              ),
            const SizedBox(height: 12),

            // Detected minerals
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: result.detectedMinerals.map((mineral) {
                return Chip(
                  avatar: const Icon(Icons.diamond, size: 16),
                  label: Text(mineral),
                );
              }).toList(),
            ),

            // Alteration
            if (result.alteration != null) ...[
              const SizedBox(height: 8),
              Text('Alteration: ${result.alteration}', style: theme.textTheme.bodyMedium),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildGeologySection(ThemeData theme, GeologyResult result) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (result.beltName != null)
              _infoRow('Belt', result.beltName!),
            if (result.formation != null)
              _infoRow('Formation', result.formation!),
            if (result.depositModel != null)
              _infoRow('Deposit Model', result.depositModel!),
            if (result.resourcePotential != null)
              _infoRow('Resource Potential', '${(result.resourcePotential! * 100).round()}%'),
            if (result.geologicalContext != null) ...[
              const SizedBox(height: 8),
              Text(result.geologicalContext!, style: theme.textTheme.bodyMedium),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildMarketSection(ThemeData theme, MarketResult result) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (result.estimatedValueUsd != null)
              _infoRow('Estimated Value', '\$${result.estimatedValueUsd!.toStringAsFixed(0)}'),
            if (result.cutOffGrade != null)
              _infoRow('Cut-off Grade', '${result.cutOffGrade!.toStringAsFixed(1)} ppm'),
            if (result.priceTrend != null)
              _infoRow('Price Trend', result.priceTrend!),
            if (result.royaltyRate != null)
              _infoRow('Royalty Rate', '${(result.royaltyRate! * 100).toStringAsFixed(1)}%'),
            if (result.commodityPrices.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('Commodity Prices:', style: theme.textTheme.bodySmall?.copyWith(fontWeight: FontWeight.w600)),
              ...result.commodityPrices.entries.map((e) {
                return _infoRow(e.key, '\$${e.value.toStringAsFixed(2)}/oz');
              }),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildComplianceSection(ThemeData theme, ComplianceResult result) {
    return Card(
      color: result.isCompliant ? Colors.green.withOpacity(0.05) : Colors.red.withOpacity(0.05),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  result.isCompliant ? Icons.check_circle : Icons.warning,
                  color: result.isCompliant ? Colors.green : Colors.red,
                ),
                const SizedBox(width: 8),
                Text(
                  result.isCompliant ? 'Compliant' : 'Compliance Issues Found',
                  style: TextStyle(
                    color: result.isCompliant ? Colors.green : Colors.red,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
            if (result.licenseType != null) _infoRow('License Type', result.licenseType!),
            if (result.eiaStatus != null) _infoRow('EIA Status', result.eiaStatus!),
            if (result.issues.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('Issues:', style: theme.textTheme.bodySmall?.copyWith(fontWeight: FontWeight.w600)),
              ...result.issues.map((issue) => Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('• ', style: TextStyle(color: Colors.red)),
                        Expanded(child: Text(issue, style: theme.textTheme.bodySmall)),
                      ],
                    ),
                  )),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildActionButtons(ThemeData theme, Analysis analysis) {
    return Row(
      children: [
        Expanded(
          child: OutlinedButton.icon(
            onPressed: () => context.push('/reports'),
            icon: const Icon(Icons.description),
            label: const Text('View Report'),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: ElevatedButton.icon(
            onPressed: () => context.push('/camera'),
            icon: const Icon(Icons.camera_alt),
            label: const Text('New Sample'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.green[700],
              foregroundColor: Colors.white,
            ),
          ),
        ),
      ],
    );
  }

  Widget _infoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 120,
            child: Text(label, style: const TextStyle(color: Colors.grey, fontSize: 13)),
          ),
          Expanded(child: Text(value, style: const TextStyle(fontWeight: FontWeight.w500))),
        ],
      ),
    );
  }

  void _shareAnalysis() {
    // TODO: Implement share via share_plus
  }
}

class _AgentInfo {
  final String name;
  final IconData icon;
  final int order;

  const _AgentInfo(this.name, this.icon, this.order);
}
