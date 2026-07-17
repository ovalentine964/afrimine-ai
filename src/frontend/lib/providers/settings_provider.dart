import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../utils/constants.dart';

class SettingsProvider extends ChangeNotifier {
  Locale _locale = const Locale('en');
  bool _offlineMode = true;
  bool _autoSync = true;
  DateTime? _lastSyncTime;
  int _pendingSyncCount = 0;

  Locale get locale => _locale;
  bool get offlineMode => _offlineMode;
  bool get autoSync => _autoSync;
  DateTime? get lastSyncTime => _lastSyncTime;
  int get pendingSyncCount => _pendingSyncCount;
  String get languageCode => _locale.languageCode;

  Future<void> loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    final langCode = prefs.getString('language') ?? 'en';
    _locale = Locale(langCode);
    _offlineMode = prefs.getBool('offline_mode') ?? true;
    _autoSync = prefs.getBool('auto_sync') ?? true;
    final lastSyncMs = prefs.getInt('last_sync_time');
    if (lastSyncMs != null) {
      _lastSyncTime = DateTime.fromMillisecondsSinceEpoch(lastSyncMs);
    }
    notifyListeners();
  }

  Future<void> setLanguage(String languageCode) async {
    _locale = Locale(languageCode);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('language', languageCode);
    notifyListeners();
  }

  Future<void> setOfflineMode(bool value) async {
    _offlineMode = value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('offline_mode', value);
    notifyListeners();
  }

  Future<void> setAutoSync(bool value) async {
    _autoSync = value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('auto_sync', value);
    notifyListeners();
  }

  Future<void> updateLastSyncTime() async {
    _lastSyncTime = DateTime.now();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt('last_sync_time', _lastSyncTime!.millisecondsSinceEpoch);
    notifyListeners();
  }

  void updatePendingSyncCount(int count) {
    _pendingSyncCount = count;
    notifyListeners();
  }

  bool get isSwahili => _locale.languageCode == 'sw';
}
