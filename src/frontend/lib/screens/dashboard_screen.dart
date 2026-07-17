import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../providers/auth_provider.dart';
import '../providers/sample_provider.dart';
import '../providers/market_provider.dart';
import '../providers/settings_provider.dart';
import '../utils/constants.dart';
import '../utils/helpers.dart';
import '../utils/localization.dart';
import '../widgets/stat_card.dart';
import '../widgets/sample_card.dart';
import '../widgets/quick_action_button.dart';
import '../widgets/offline_banner.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  void initState() {
    super.initState();
    _loadData();
  }

  void _loadData() {
    final auth = context.read<AuthProvider>();
    final samples = context.read<SampleProvider>();
    final market = context.read<MarketProvider>();

    if (auth.userId != null) {
      samples.loadSamples(userId: auth.userId);
    }
    market.loadPrices();
  }

  @override
  Widget build(BuildContext context) {
    final loc = AppLocalizations.of(context);
    final auth = context.watch<AuthProvider>();
    final samples = context.watch<SampleProvider>();
    final market = context.watch<MarketProvider>();

    return Scaffold(
      body: OfflineBanner(
        child: RefreshIndicator(
          onRefresh: () async => _loadData(),
          child: CustomScrollView(
          slivers: [
            // App Bar
            SliverAppBar(
              expandedHeight: 180,
              floating: false,
              pinned: true,
              flexibleSpace: FlexibleSpaceBar(
                background: Container(
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [AppColors.primaryDark, AppColors.primary],
                    ),
                  ),
                  child: SafeArea(
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisAlignment: MainAxisAlignment.end,
                        children: [
                          Text(
                            'Karibu, ${auth.user?.userMetadata?['name'] ?? 'Miner'} 👋',
                            style: const TextStyle(
                              fontSize: 22,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                              
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Your mining dashboard',
                            style: TextStyle(
                              fontSize: 14,
                              color: Colors.white.withOpacity(0.8),
                              
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
              actions: [
                IconButton(
                  icon: const Icon(Icons.settings, color: Colors.white),
                  onPressed: () => context.push('/settings'),
                ),
              ],
            ),

            // Error state
            if (samples.error != null)
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
                  child: Card(
                    color: AppColors.error.withOpacity(0.1),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Row(
                        children: [
                          const Icon(Icons.error_outline, color: AppColors.error, size: 20),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              samples.error!,
                              style: AppTextStyles.bodySmall.copyWith(color: AppColors.error),
                            ),
                          ),
                          TextButton(
                            onPressed: () => _loadData(),
                            child: const Text('Retry'),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),

            // Stats Grid
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                child: GridView.count(
                  crossAxisCount: 2,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  mainAxisSpacing: 12,
                  crossAxisSpacing: 12,
                  childAspectRatio: 1.3,
                  children: [
                    StatCard(
                      title: 'My Land',
                      value: '5.2 acres',
                      icon: Icons.landscape,
                      color: AppColors.primary,
                      onTap: () => context.push('/map'),
                    ),
                    StatCard(
                      title: 'Estimated Value',
                      value: Helpers.formatCurrency(260000),
                      icon: Icons.attach_money,
                      color: AppColors.accent,
                    ),
                    StatCard(
                      title: 'Total Samples',
                      value: '${samples.totalCount}',
                      icon: Icons.science,
                      subtitle: '${samples.pendingCount} pending',
                      onTap: () => context.push('/samples'),
                    ),
                    StatCard(
                      title: 'Analyzed',
                      value: '${samples.analyzedCount + samples.verifiedCount}',
                      icon: Icons.check_circle,
                      color: AppColors.success,
                    ),
                  ],
                ),
              ),
            ),

            // Quick Actions
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Quick Actions', style: AppTextStyles.heading3),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: QuickActionButton(
                            icon: Icons.camera_alt,
                            label: 'New Sample',
                            onTap: () => context.push('/capture'),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: QuickActionButton(
                            icon: Icons.map,
                            label: 'View Map',
                            color: AppColors.info,
                            onTap: () => context.push('/map'),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: QuickActionButton(
                            icon: Icons.attach_money,
                            label: 'Market Prices',
                            color: AppColors.accent,
                            onTap: () => context.push('/market'),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: QuickActionButton(
                            icon: Icons.description,
                            label: 'Reports',
                            color: AppColors.copper,
                            onTap: () => context.push('/reports'),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),

            // Market Snapshot
            if (market.goldPrice != null)
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('Market Snapshot', style: AppTextStyles.heading3),
                          TextButton(
                            onPressed: () => context.push('/market'),
                            child: const Text('View All'),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Expanded(
                            child: _buildMiniPriceCard(
                              'Gold',
                              market.goldPrice!.formattedPrice,
                              market.goldPrice!.formattedChange,
                              market.goldPrice!.isPositive,
                              AppColors.gold,
                            ),
                          ),
                          const SizedBox(width: 12),
                          if (market.copperPrice != null)
                            Expanded(
                              child: _buildMiniPriceCard(
                                'Copper',
                                market.copperPrice!.formattedPrice,
                                market.copperPrice!.formattedChange,
                                market.copperPrice!.isPositive,
                                AppColors.copper,
                              ),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),

            // Recent Samples
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('Recent Samples', style: AppTextStyles.heading3),
                    TextButton(
                      onPressed: () => context.push('/samples'),
                      child: const Text('View All'),
                    ),
                  ],
                ),
              ),
            ),

            if (samples.samples.isEmpty)
              const SliverToBoxAdapter(
                child: Padding(
                  padding: EdgeInsets.all(32),
                  child: Center(
                    child: Column(
                      children: [
                        Icon(Icons.science_outlined, size: 48, color: AppColors.textSecondary),
                        SizedBox(height: 12),
                        Text('No samples yet', style: AppTextStyles.body),
                        SizedBox(height: 4),
                        Text('Capture your first mineral sample', style: AppTextStyles.bodySmall),
                      ],
                    ),
                  ),
                ),
              )
            else
              SliverList(
                delegate: SliverChildBuilderDelegate(
                  (context, index) {
                    final sample = samples.samples[index];
                    return SampleCard(
                      sample: sample,
                      onTap: () {
                        samples.selectSample(sample);
                        context.push('/samples/${sample.id}');
                      },
                    );
                  },
                  childCount: samples.samples.length.clamp(0, 5),
                ),
              ),

            const SliverToBoxAdapter(child: SizedBox(height: 80)),
          ],
        ),
      ),
      ),
      bottomNavigationBar: _buildBottomNav(context, 0),
    );
  }

  Widget _buildMiniPriceCard(String name, String price, String change, bool isPositive, Color color) {
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(color: color, shape: BoxShape.circle),
                ),
                const SizedBox(width: 6),
                Text(name, style: AppTextStyles.bodySmall),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              price,
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
                color: color,
                
              ),
            ),
            const SizedBox(height: 4),
            Text(
              change,
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: isPositive ? AppColors.success : AppColors.error,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBottomNav(BuildContext context, int currentIndex) {
    return BottomNavigationBar(
      currentIndex: currentIndex,
      type: BottomNavigationBarType.fixed,
      selectedItemColor: AppColors.primary,
      unselectedItemColor: AppColors.textSecondary,
      selectedLabelStyle: const TextStyle( fontWeight: FontWeight.w500, fontSize: 11),
      unselectedLabelStyle: const TextStyle( fontSize: 11),
      onTap: (index) {
        switch (index) {
          case 0:
            context.go('/dashboard');
            break;
          case 1:
            context.push('/samples');
            break;
          case 2:
            context.push('/capture');
            break;
          case 3:
            context.push('/map');
            break;
          case 4:
            context.push('/settings');
            break;
        }
      },
      items: const [
        BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Home'),
        BottomNavigationBarItem(icon: Icon(Icons.science), label: 'Samples'),
        BottomNavigationBarItem(icon: Icon(Icons.add_circle, size: 32), label: 'Capture'),
        BottomNavigationBarItem(icon: Icon(Icons.map), label: 'Map'),
        BottomNavigationBarItem(icon: Icon(Icons.settings), label: 'Settings'),
      ],
    );
  }
}
