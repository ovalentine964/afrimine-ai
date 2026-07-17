import 'package:flutter/material.dart';

class AppConstants {
  static const String appName = 'AfriMine AI';
  static const String appVersion = '1.0.0';
  static const String appDescription = 'Mineral Detection Platform for Kenyan Mining Families';

  // Supabase - configured via --dart-define at build time
  static const String supabaseUrl = String.fromEnvironment(
    'SUPABASE_URL',
    defaultValue: 'https://your-project.supabase.co',
  );
  static const String supabaseAnonKey = String.fromEnvironment(
    'SUPABASE_ANON_KEY',
    defaultValue: 'your-anon-key',
  );

  // API Endpoints
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://api.afrimine.ai/v1',
  );
  static const String aiEndpoint = '$apiBaseUrl/classify';
  static const String marketEndpoint = '$apiBaseUrl/market-prices';
  static const String reportsEndpoint = '$apiBaseUrl/reports';

  // Database
  static const String dbName = 'afrimine.db';
  static const int dbVersion = 1;

  // Map Defaults - Kenya center
  static const double defaultLat = -0.0236;
  static const double defaultLng = 37.9062;
  static const double defaultZoom = 7.0;
  static const double detailZoom = 14.0;

  // Sample Status
  static const String statusPending = 'pending';
  static const String statusAnalyzed = 'analyzed';
  static const String statusVerified = 'verified';

  // Mineral Types
  static const List<String> mineralTypes = [
    'Gold',
    'Copper',
    'Titanium',
    'Rare Earth',
    'Iron Ore',
    'Manganese',
    'Graphite',
    'Soda Ash',
    'Fluorspar',
    'Gypsum',
  ];

  // Supported Languages
  static const String langEnglish = 'en';
  static const String langSwahili = 'sw';

  // Sync
  static const int syncIntervalMinutes = 15;
  static const int maxRetryAttempts = 3;

  // Camera
  static const double imageQuality = 0.85;
  static const int maxImageWidth = 1920;
}

class AppColors {
  static const Color primary = Color(0xFF1B5E20);
  static const Color primaryLight = Color(0xFF4C8C4A);
  static const Color primaryDark = Color(0xFF003300);
  static const Color accent = Color(0xFFFFB300);
  static const Color accentLight = Color(0xFFFFE54C);
  static const Color gold = Color(0xFFFFD700);
  static const Color copper = Color(0xFFB87333);
  static const Color surface = Color(0xFFF5F5F5);
  static const Color cardBg = Colors.white;
  static const Color textPrimary = Color(0xFF212121);
  static const Color textSecondary = Color(0xFF757575);
  static const Color success = Color(0xFF4CAF50);
  static const Color warning = Color(0xFFFF9800);
  static const Color error = Color(0xFFF44336);
  static const Color info = Color(0xFF2196F3);
  static const Color pending = Color(0xFFFF9800);
  static const Color analyzed = Color(0xFF2196F3);
  static const Color verified = Color(0xFF4CAF50);
}

class AppTextStyles {
  static const TextStyle heading1 = TextStyle(
    fontSize: 28,
    fontWeight: FontWeight.bold,
    color: AppColors.textPrimary,
    
  );

  static const TextStyle heading2 = TextStyle(
    fontSize: 22,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
    
  );

  static const TextStyle heading3 = TextStyle(
    fontSize: 18,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
    
  );

  static const TextStyle body = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.normal,
    color: AppColors.textPrimary,
    
  );

  static const TextStyle bodySmall = TextStyle(
    fontSize: 12,
    fontWeight: FontWeight.normal,
    color: AppColors.textSecondary,
    
  );

  static const TextStyle button = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w600,
    
  );

  static const TextStyle caption = TextStyle(
    fontSize: 11,
    fontWeight: FontWeight.normal,
    color: AppColors.textSecondary,
    
  );
}
