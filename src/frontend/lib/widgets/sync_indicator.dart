import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/offline_service.dart';

/// Connectivity status provider.
final connectivityProvider = StreamProvider<ConnectivityResult>((ref) {
  return Connectivity().onConnectivityChanged.map((results) {
    return results.isNotEmpty ? results.first : ConnectivityResult.none;
  });
});

/// Whether the device is currently online.
final isOnlineProvider = Provider<bool>((ref) {
  final connectivity = ref.watch(connectivityProvider);
  return connectivity.whenData((result) => result != ConnectivityResult.none).value ?? false;
});

/// Pending sync count provider.
final pendingSyncCountProvider = FutureProvider<int>((ref) async {
  final offlineService = ref.watch(offlineServiceProvider);
  return offlineService.getPendingSyncCount();
});

/// Compact sync status indicator widget.
///
/// Shows:
/// - Green dot = online, all synced
/// - Yellow dot = online, items pending sync
/// - Red dot = offline
/// - Tap to trigger manual sync
class SyncIndicator extends ConsumerWidget {
  final VoidCallback? onSyncTap;
  final bool showLabel;

  const SyncIndicator({
    super.key,
    this.onSyncTap,
    this.showLabel = true,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOnline = ref.watch(isOnlineProvider);
    final pendingAsync = ref.watch(pendingSyncCountProvider);

    final pendingCount = pendingAsync.valueOrNull ?? 0;
    final hasPending = pendingCount > 0;

    Color dotColor;
    String label;
    IconData icon;

    if (!isOnline) {
      dotColor = Colors.red;
      label = 'Offline';
      icon = Icons.cloud_off;
    } else if (hasPending) {
      dotColor = Colors.orange;
      label = '$pendingCount pending';
      icon = Icons.cloud_sync;
    } else {
      dotColor = Colors.green;
      label = 'Synced';
      icon = Icons.cloud_done;
    }

    return GestureDetector(
      onTap: onSyncTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: dotColor.withOpacity(0.1),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: dotColor.withOpacity(0.3)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Animated dot
            _AnimatedDot(color: dotColor),
            const SizedBox(width: 6),
            Icon(icon, size: 16, color: dotColor),
            if (showLabel) ...[
              const SizedBox(width: 4),
              Text(
                label,
                style: TextStyle(
                  color: dotColor,
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Animated pulsing dot.
class _AnimatedDot extends StatefulWidget {
  final Color color;

  const _AnimatedDot({required this.color});

  @override
  State<_AnimatedDot> createState() => _AnimatedDotState();
}

class _AnimatedDotState extends State<_AnimatedDot>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    );
    _animation = Tween<double>(begin: 0.5, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeInOut),
    );
    _controller.repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _animation,
      builder: (context, child) {
        return Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: widget.color.withOpacity(_animation.value),
            boxShadow: [
              BoxShadow(
                color: widget.color.withOpacity(_animation.value * 0.4),
                blurRadius: 4,
                spreadRadius: 1,
              ),
            ],
          ),
        );
      },
    );
  }
}

/// Full-width sync status bar (for dashboard).
class SyncStatusBar extends ConsumerWidget {
  final VoidCallback? onSyncTap;

  const SyncStatusBar({super.key, this.onSyncTap});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOnline = ref.watch(isOnlineProvider);
    final pendingAsync = ref.watch(pendingSyncCountProvider);

    return pendingAsync.when(
      loading: () => const SizedBox.shrink(),
      error: (_, __) => const SizedBox.shrink(),
      data: (pendingCount) {
        if (isOnline && pendingCount == 0) return const SizedBox.shrink();

        final color = !isOnline ? Colors.red : Colors.orange;

        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          decoration: BoxDecoration(
            color: color.withOpacity(0.1),
            border: Border(
              bottom: BorderSide(color: color.withOpacity(0.3)),
            ),
          ),
          child: Row(
            children: [
              Icon(
                isOnline ? Icons.cloud_sync : Icons.cloud_off,
                size: 20,
                color: color,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  !isOnline
                      ? 'You are offline. Data will sync when connected.'
                      : '$pendingCount item${pendingCount != 1 ? 's' : ''} waiting to sync.',
                  style: TextStyle(color: color, fontSize: 13),
                ),
              ),
              if (isOnline && pendingCount > 0)
                TextButton(
                  onPressed: onSyncTap,
                  child: Text('Sync Now', style: TextStyle(color: color)),
                ),
            ],
          ),
        );
      },
    );
  }
}
