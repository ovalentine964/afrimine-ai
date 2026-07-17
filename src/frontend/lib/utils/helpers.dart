import 'dart:io';
import 'package:intl/intl.dart';
import 'package:uuid/uuid.dart';
import 'constants.dart';

class Helpers {
  static const _uuid = Uuid();

  static String generateId() => _uuid.v4();

  static String formatDate(DateTime date) => DateFormat('MMM dd, yyyy').format(date);
  static String formatDateTime(DateTime date) => DateFormat('MMM dd, yyyy HH:mm').format(date);
  static String formatTime(DateTime date) => DateFormat('HH:mm').format(date);
  static String formatCurrency(double amount, {String symbol = 'KES'}) {
    final formatter = NumberFormat('#,##0.00');
    return '$symbol ${formatter.format(amount)}';
  }

  static String formatWeight(double grams) {
    if (grams >= 1000) {
      return '${(grams / 1000).toStringAsFixed(2)} kg';
    }
    return '${grams.toStringAsFixed(1)} g';
  }

  static String statusLabel(String status) {
    switch (status) {
      case AppConstants.statusPending: return 'Pending Analysis';
      case AppConstants.statusAnalyzed: return 'Analyzed';
      case AppConstants.statusVerified: return 'Verified';
      default: return status;
    }
  }

  static String statusEmoji(String status) {
    switch (status) {
      case AppConstants.statusPending: return '⏳';
      case AppConstants.statusAnalyzed: return '🔬';
      case AppConstants.statusVerified: return '✅';
      default: return '❓';
    }
  }

  static String relativeTime(DateTime date) {
    final diff = DateTime.now().difference(date);
    if (diff.inMinutes < 1) return 'Just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return formatDate(date);
  }

  static double? parseDouble(dynamic value) {
    if (value == null) return null;
    if (value is double) return value;
    if (value is int) return value.toDouble();
    if (value is String) return double.tryParse(value);
    return null;
  }

  static int? parseInt(dynamic value) {
    if (value == null) return null;
    if (value is int) return value;
    if (value is String) return int.tryParse(value);
    return null;
  }

  static String truncateText(String text, int maxLength) {
    if (text.length <= maxLength) return text;
    return '${text.substring(0, maxLength)}...';
  }

  static String formatCoordinate(double lat, double lng) {
    final latDir = lat >= 0 ? 'N' : 'S';
    final lngDir = lng >= 0 ? 'E' : 'W';
    return '${lat.abs().toStringAsFixed(6)}°$latDir, ${lng.abs().toStringAsFixed(6)}°$lngDir';
  }

  static String formatFileSize(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  static Future<int> getFileSize(String path) async {
    final file = File(path);
    return await file.length();
  }

  static Map<String, dynamic> sampleToJson(dynamic sample) {
    return sample.toJson();
  }
}
