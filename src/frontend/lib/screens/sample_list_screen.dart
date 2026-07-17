import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../providers/sample_provider.dart';
import '../utils/constants.dart';
import '../widgets/sample_card.dart';
import '../widgets/loading_overlay.dart';
import '../widgets/offline_banner.dart';

class SampleListScreen extends StatefulWidget {
  const SampleListScreen({super.key});

  @override
  State<SampleListScreen> createState() => _SampleListScreenState();
}

class _SampleListScreenState extends State<SampleListScreen> {
  final _searchController = TextEditingController();
  String _searchQuery = '';

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final samples = context.watch<SampleProvider>();

    final filtered = samples.filteredSamples.where((s) {
      if (_searchQuery.isEmpty) return true;
      final query = _searchQuery.toLowerCase();
      return (s.mineralType?.toLowerCase().contains(query) ?? false) ||
          (s.notes?.toLowerCase().contains(query) ?? false) ||
          s.status.toLowerCase().contains(query);
    }).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('My Samples'),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(60),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            child: TextField(
              controller: _searchController,
              onChanged: (v) => setState(() => _searchQuery = v),
              decoration: InputDecoration(
                hintText: 'Search samples...',
                prefixIcon: const Icon(Icons.search, size: 20),
                suffixIcon: _searchQuery.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear, size: 18),
                        onPressed: () {
                          _searchController.clear();
                          setState(() => _searchQuery = '');
                        },
                      )
                    : null,
                filled: true,
                fillColor: Colors.white,
                contentPadding: const EdgeInsets.symmetric(vertical: 0, horizontal: 16),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
          ),
        ),
      ),
      body: OfflineBanner(
        child: LoadingOverlay(
          isLoading: samples.isLoading,
          message: 'Loading samples...',
          child: Column(
          children: [
            // Filter tabs
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: [
                  _buildFilterChip('All', 'all', samples.totalCount),
                  const SizedBox(width: 8),
                  _buildFilterChip('Pending', 'pending', samples.pendingCount),
                  const SizedBox(width: 8),
                  _buildFilterChip('Analyzed', 'analyzed', samples.analyzedCount),
                  const SizedBox(width: 8),
                  _buildFilterChip('Verified', 'verified', samples.verifiedCount),
                ],
              ),
            ),

            // Error state
            if (samples.error != null)
              Container(
                margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.error.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.error_outline, color: AppColors.error, size: 18),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        samples.error!,
                        style: AppTextStyles.bodySmall.copyWith(color: AppColors.error),
                      ),
                    ),
                    TextButton(
                      onPressed: () => samples.loadSamples(),
                      child: const Text('Retry'),
                    ),
                  ],
                ),
              ),

            // Sample list
            Expanded(
              child: filtered.isEmpty
                  ? EmptyState(
                      icon: Icons.science_outlined,
                      title: 'No samples yet',
                      description: 'Capture your first mineral sample to get started.',
                      actionLabel: 'Capture Sample',
                      onAction: () => context.push('/capture'),
                    )
                  : RefreshIndicator(
                      onRefresh: () => samples.loadSamples(),
                      child: ListView.builder(
                        padding: const EdgeInsets.only(bottom: 80),
                        itemCount: filtered.length,
                        itemBuilder: (context, index) {
                          final sample = filtered[index];
                          return Dismissible(
                            key: Key(sample.id),
                            direction: DismissDirection.endToStart,
                            background: Container(
                              alignment: Alignment.centerRight,
                              padding: const EdgeInsets.only(right: 20),
                              color: AppColors.error,
                              child: const Icon(Icons.delete, color: Colors.white),
                            ),
                            confirmDismiss: (direction) async {
                              return await showDialog<bool>(
                                context: context,
                                builder: (ctx) => AlertDialog(
                                  title: const Text('Delete Sample'),
                                  content: const Text('Are you sure you want to delete this sample?'),
                                  actions: [
                                    TextButton(
                                      onPressed: () => Navigator.pop(ctx, false),
                                      child: const Text('Cancel'),
                                    ),
                                    TextButton(
                                      onPressed: () => Navigator.pop(ctx, true),
                                      style: TextButton.styleFrom(foregroundColor: AppColors.error),
                                      child: const Text('Delete'),
                                    ),
                                  ],
                                ),
                              );
                            },
                            onDismissed: (_) => samples.deleteSample(sample.id),
                            child: SampleCard(
                              sample: sample,
                              onTap: () {
                                samples.selectSample(sample);
                                context.push('/samples/${sample.id}');
                              },
                            ),
                          );
                        },
                      ),
                    ),
            ),
          ],
        ),
      ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/capture'),
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.camera_alt),
        label: const Text('New Sample'),
      ),
    );
  }

  Widget _buildFilterChip(String label, String status, int count) {
    final isSelected = context.watch<SampleProvider>().filterStatus == status;
    return FilterChip(
      selected: isSelected,
      label: Text('$label ($count)'),
      onSelected: (_) => context.read<SampleProvider>().setFilter(status),
      selectedColor: AppColors.primary.withOpacity(0.2),
      checkmarkColor: AppColors.primary,
      labelStyle: TextStyle(
        color: isSelected ? AppColors.primary : AppColors.textSecondary,
        fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
        fontSize: 12,
      ),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
    );
  }
}
