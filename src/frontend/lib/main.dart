import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'screens/home_screen.dart';
import 'screens/camera_screen.dart';
import 'screens/analysis_screen.dart';
import 'screens/reports_screen.dart';
import 'screens/map_screen.dart';
import 'screens/voice_screen.dart';
import 'screens/settings_screen.dart';
import 'services/offline_service.dart';
import 'services/api_service.dart';

// =============================================================================
// Entry Point
// =============================================================================

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize offline storage
  final offlineService = OfflineService();
  await offlineService.initialize();

  runApp(
    ProviderScope(
      overrides: [
        offlineServiceProvider.overrideWithValue(offlineService),
      ],
      child: const AfriMineApp(),
    ),
  );
}

// =============================================================================
// App Widget
// =============================================================================

class AfriMineApp extends ConsumerWidget {
  const AfriMineApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      title: 'AfriMine AI',
      debugShowCheckedModeBanner: false,

      // Theme — dark-friendly for outdoor use, green accent for mining
      theme: _buildLightTheme(),
      darkTheme: _buildDarkTheme(),
      themeMode: ThemeMode.system,

      // Routing
      routerConfig: router,
    );
  }
}

// =============================================================================
// Theme
// =============================================================================

ThemeData _buildLightTheme() {
  const primaryGreen = Color(0xFF2E7D32);
  const surfaceWhite = Color(0xFFFAFAFA);

  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    colorSchemeSeed: primaryGreen,
    scaffoldBackgroundColor: surfaceWhite,

    // AppBar
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.white,
      foregroundColor: Colors.black87,
      elevation: 0,
      scrolledUnderElevation: 1,
      centerTitle: false,
      titleTextStyle: TextStyle(
        color: Colors.black87,
        fontSize: 20,
        fontWeight: FontWeight.w600,
      ),
    ),

    // Cards
    cardTheme: CardTheme(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      clipBehavior: Clip.antiAlias,
    ),

    // Buttons
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
      ),
    ),

    // Input fields
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.grey[100],
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide.none,
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    ),

    // Bottom navigation
    bottomNavigationBarTheme: const BottomNavigationBarThemeData(
      selectedItemColor: primaryGreen,
      unselectedItemColor: Colors.grey,
    ),

    // Text
    fontFamily: 'Nunito',
  );
}

ThemeData _buildDarkTheme() {
  const primaryGreen = Color(0xFF43A047);
  const surfaceDark = Color(0xFF121212);
  const cardDark = Color(0xFF1E1E1E);

  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorSchemeSeed: primaryGreen,
    scaffoldBackgroundColor: surfaceDark,

    appBarTheme: const AppBarTheme(
      backgroundColor: cardDark,
      elevation: 0,
      scrolledUnderElevation: 1,
      centerTitle: false,
    ),

    cardTheme: CardTheme(
      color: cardDark,
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      clipBehavior: Clip.antiAlias,
    ),

    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
      ),
    ),

    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: const Color(0xFF2A2A2A),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide.none,
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    ),

    fontFamily: 'Nunito',
  );
}

// =============================================================================
// Routing
// =============================================================================

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/',
    debugLogDiagnostics: true,

    routes: [
      // Shell route with bottom navigation
      ShellRoute(
        builder: (context, state, child) {
          return ScaffoldWithNav(child: child);
        },
        routes: [
          GoRoute(
            path: '/',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: HomeScreen(),
            ),
          ),
          GoRoute(
            path: '/reports',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: ReportsScreen(),
            ),
          ),
          GoRoute(
            path: '/map',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: MapScreen(),
            ),
          ),
          GoRoute(
            path: '/settings',
            pageBuilder: (context, state) => const NoTransitionPage(
              child: SettingsScreen(),
            ),
          ),
        ],
      ),

      // Full-screen routes (no bottom nav)
      GoRoute(
        path: '/camera',
        builder: (context, state) => const CameraScreen(),
      ),
      GoRoute(
        path: '/voice',
        builder: (context, state) => const VoiceScreen(),
      ),
      GoRoute(
        path: '/analysis/:id',
        builder: (context, state) => AnalysisScreen(
          analysisId: state.pathParameters['id']!,
        ),
      ),
    ],

    // Error page
    errorBuilder: (context, state) => Scaffold(
      appBar: AppBar(title: const Text('Page Not Found')),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 64, color: Colors.grey),
            const SizedBox(height: 16),
            Text('Page not found: ${state.uri}'),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () => context.go('/'),
              child: const Text('Go Home'),
            ),
          ],
        ),
      ),
    ),
  );
});

// =============================================================================
// Shell with Bottom Navigation
// =============================================================================

class ScaffoldWithNav extends StatelessWidget {
  final Widget child;

  const ScaffoldWithNav({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: _calculateSelectedIndex(context),
        onDestinationSelected: (index) => _onItemTapped(index, context),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.assessment_outlined),
            selectedIcon: Icon(Icons.assessment),
            label: 'Reports',
          ),
          NavigationDestination(
            icon: Icon(Icons.map_outlined),
            selectedIcon: Icon(Icons.map),
            label: 'Map',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            selectedIcon: Icon(Icons.settings),
            label: 'Settings',
          ),
        ],
      ),
    );
  }

  int _calculateSelectedIndex(BuildContext context) {
    final location = GoRouterState.of(context).uri.path;
    if (location.startsWith('/reports')) return 1;
    if (location.startsWith('/map')) return 2;
    if (location.startsWith('/settings')) return 3;
    return 0;
  }

  void _onItemTapped(int index, BuildContext context) {
    switch (index) {
      case 0:
        context.go('/');
        break;
      case 1:
        context.go('/reports');
        break;
      case 2:
        context.go('/map');
        break;
      case 3:
        context.go('/settings');
        break;
    }
  }
}
