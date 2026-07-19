import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../models/analysis.dart';
import '../services/api_service.dart';
import '../services/offline_service.dart';
import '../widgets/mineral_card.dart';
import '../widgets/sync_indicator.dart';

/// Dashboard screen — first thing field workers see.
///
/// Shows:
/// - Recent analyses with quick-glance cards
/// - Quick action buttons (capture, voice, reports)
/// - Sync status banner
/// - Offline-capable (loads from SQLite cache)
class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isOnline = ref.watch(isOnlineProvider);

    return Scaffold(
      body: CustomScrollView(
        slivers: [
          // App bar
          SliverAppBar(
            expandedHeight: 120,
            floating: true,
            pinned: true,
            flexibleSpace: FlexibleSpaceBar(
              title: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('⛏️', style: TextStyle(fontSize: 20)),
                  const SizedBox(width: 8),
                  Text(
                    'AfriMine',
                    style: theme.textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
              background: Container(
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [Color(0xFF1B5E20), Color(0xFF2E7D32), Color(0xFF43A047)],
                  ),
                ),
              ),
            ),
            actions: [
              SyncIndicator(
                showLabel: false,
                onSyncTap: () => _triggerSync(context),
              ),
              const SizedBox(width: 8),
              IconButton(
                icon: const Icon(Icons.settings),
                onPressed: () => context.push('/settings'),
              ),
            ],
          ),

          // Sync status bar
          SliverToBoxAdapter(
            child: SyncStatusBar(
              onSyncTap: () => _triggerSync(context),
            ),
          ),

          // Quick actions
          SliverToBoxAdapter(
            child: _buildQuickActions(context, theme),
          ),

          // Recent analyses header
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 24, 16, 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Recent Analyses',
                    style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
                  ),
                  TextButton(
                    onPressed: () => context.push('/reports'),
                    child: const Text('View All'),
                  ),
                ],
              ),
            ),
          ),

          // Recent analyses list
          _buildRecentAnalyses(context),
        ],
      ),
    );
  }

  Widget _buildQuickActions(BuildContext context, ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Quick Actions',
            style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              _ActionButton(
                icon: Icons.camera_alt,
                label: 'Capture',
                color: Colors.blue,
                onTap: () => context.push('/camera'),
              ),
              const SizedBox(width: 12),
              _ActionButton(
                icon: Icons.mic,
                label: 'Voice',
                color: Colors.purple,
                onTap: () => context.push('/voice'),
              ),
              const SizedBox(width: 12),
              _ActionButton(
                icon: Icons.map,
                label: 'Map',
                color: Colors.teal,
                onTap: () => context.push('/map'),
              ),
              const SizedBox(width: 12),
              _ActionButton(
                icon: Icons.assessment,
                label: 'Reports',
                color: Colors.orange,
                onTap: () => context.push('/reports'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildRecentAnalyses(BuildContext context) {
    final offlineService = ref.watch(offlineServiceProvider);

    return FutureBuilder<List<Analysis>>(
      future: offlineService.getCachedAnalyses(limit: 10),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const SliverToBoxAdapter(
            child: Center(
              child: Padding(
                padding: EdgeInsets.all(32),
                child: CircularProgressIndicator(),
              ),
            ),
          );
        }

        final analyses = snapshot.data ?? [];

        if (analyses.isEmpty) {
          return SliverToBoxAdapter(
            child: _buildEmptyState(context),
          );
        }

        return SliverPadding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          sliver: SliverList(
            delegate: SliverChildBuilderDelegate(
              (context, index) {
                final analysis = analyses[index];
                return Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: MineralCard(
                    analysis: analysis,
                    onTap: () => context.push('/analysis/${analysis.id}'),
                  ),
                );
              },
              childCount: analyses.length,
            ),
          ),
        );
      },
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          children: [
            Icon(Icons.landscape, size: 64, color: Colors.grey[400]),
            const SizedBox(height: 16),
            Text(
              'No analyses yet',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(color: Colors.grey[600]),
            ),
            const SizedBox(height: 8),
            Text(
              'Capture a mineral sample to get started',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Colors.grey[500]),
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

  Future<void> _triggerSync(BuildContext context) async {
    final apiService = ref.read(apiServiceProvider);
    final offlineService = ref.read(offlineServiceProvider);

    final result = await apiService.syncPendingData();
    if (mounted) {
      ref.invalidate(pendingSyncCountProvider);

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Sync complete: ${result['uploaded']} uploaded, ${result['failed']} failed',
          ),
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }
}

/// Quick action button for the dashboard.
class _ActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  const _ActionButton({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Material(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Column(
              children: [
                Icon(icon, color: color, size: 28),
                const SizedBox(height: 6),
                Text(
                  label,
                  style: TextStyle(
                    color: color,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
