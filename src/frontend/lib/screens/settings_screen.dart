import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../services/api_service.dart';
import '../services/offline_service.dart';
import '../services/voice_service.dart';
import '../widgets/sync_indicator.dart';

/// Settings screen for API keys, sync, language, and offline mode.
class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final _storage = const FlutterSecureStorage();
  bool _offlineMode = false;
  VoiceLanguage _selectedLanguage = VoiceLanguage.swahili;
  bool _autoSync = true;
  bool _compressPhotos = true;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    final offlineService = ref.read(offlineServiceProvider);
    final offlineMode = await offlineService.getSetting('offline_mode');
    final language = await offlineService.getSetting('language');
    final autoSync = await offlineService.getSetting('auto_sync');
    final compressPhotos = await offlineService.getSetting('compress_photos');

    if (mounted) {
      setState(() {
        _offlineMode = offlineMode == 'true';
        _selectedLanguage = VoiceLanguage.values.firstWhere(
          (l) => l.code == language,
          orElse: () => VoiceLanguage.swahili,
        );
        _autoSync = autoSync != 'false';
        _compressPhotos = compressPhotos != 'false';
      });
    }
  }

  Future<void> _saveSetting(String key, String value) async {
    final offlineService = ref.read(offlineServiceProvider);
    await offlineService.saveSetting(key, value);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isOnline = ref.watch(isOnlineProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        children: [
          // Account section
          _buildSectionHeader(theme, 'Account'),
          _buildAccountTile(theme),

          const Divider(),

          // Sync section
          _buildSectionHeader(theme, 'Sync & Connectivity'),
          _buildSyncSection(theme, isOnline),

          const Divider(),

          // Voice section
          _buildSectionHeader(theme, 'Voice & Language'),
          _buildVoiceSection(theme),

          const Divider(),

          // Camera section
          _buildSectionHeader(theme, 'Camera'),
          _buildCameraSection(theme),

          const Divider(),

          // Offline mode
          _buildSectionHeader(theme, 'Offline Mode'),
          _buildOfflineSection(theme),

          const Divider(),

          // API Keys
          _buildSectionHeader(theme, 'API Configuration'),
          _buildApiSection(theme),

          const Divider(),

          // About
          _buildSectionHeader(theme, 'About'),
          _buildAboutSection(theme),

          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(ThemeData theme, String title) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Text(
        title,
        style: theme.textTheme.titleSmall?.copyWith(
          color: Colors.green[700],
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _buildAccountTile(ThemeData theme) {
    final apiService = ref.watch(apiServiceProvider);

    return ListTile(
      leading: CircleAvatar(
        backgroundColor: Colors.green[100],
        child: Icon(Icons.person, color: Colors.green[700]),
      ),
      title: Text(apiService.isAuthenticated ? 'Logged in' : 'Not logged in'),
      subtitle: Text(apiService.isAuthenticated ? 'Tap to manage account' : 'Tap to sign in'),
      trailing: const Icon(Icons.chevron_right),
      onTap: () {
        if (apiService.isAuthenticated) {
          _showLogoutDialog(apiService);
        } else {
          _showLoginDialog(apiService);
        }
      },
    );
  }

  Widget _buildSyncSection(ThemeData theme, bool isOnline) {
    return Column(
      children: [
        // Sync status
        ListTile(
          leading: Icon(
            isOnline ? Icons.cloud_done : Icons.cloud_off,
            color: isOnline ? Colors.green : Colors.red,
          ),
          title: Text(isOnline ? 'Connected' : 'Offline'),
          subtitle: Text(isOnline ? 'Data will sync automatically' : 'Changes saved locally'),
          trailing: SyncIndicator(showLabel: false),
        ),

        // Auto-sync toggle
        SwitchListTile(
          secondary: const Icon(Icons.sync),
          title: const Text('Auto Sync'),
          subtitle: const Text('Sync data when connected'),
          value: _autoSync,
          onChanged: (value) {
            setState(() => _autoSync = value);
            _saveSetting('auto_sync', value.toString());
          },
        ),

        // Manual sync
        ListTile(
          leading: const Icon(Icons.refresh),
          title: const Text('Sync Now'),
          subtitle: const Text('Upload pending changes'),
          trailing: const Icon(Icons.chevron_right),
          onTap: isOnline ? () => _triggerSync() : null,
        ),
      ],
    );
  }

  Widget _buildVoiceSection(ThemeData theme) {
    return Column(
      children: [
        // Language selector
        ListTile(
          leading: const Icon(Icons.language),
          title: const Text('Voice Language'),
          subtitle: Text(_selectedLanguage.displayName),
          trailing: const Icon(Icons.chevron_right),
          onTap: _showLanguagePicker,
        ),

        // Voice test
        ListTile(
          leading: const Icon(Icons.volume_up),
          title: const Text('Test Voice'),
          subtitle: const Text('Preview TTS output'),
          trailing: const Icon(Icons.play_arrow),
          onTap: () async {
            final voiceService = ref.read(voiceServiceProvider);
            await voiceService.speak('Habari! Karibu AfriMine AI.');
          },
        ),
      ],
    );
  }

  Widget _buildCameraSection(ThemeData theme) {
    return Column(
      children: [
        SwitchListTile(
          secondary: const Icon(Icons.compress),
          title: const Text('Compress Photos'),
          subtitle: const Text('Reduce photo size for faster upload'),
          value: _compressPhotos,
          onChanged: (value) {
            setState(() => _compressPhotos = value);
            _saveSetting('compress_photos', value.toString());
          },
        ),
      ],
    );
  }

  Widget _buildOfflineSection(ThemeData theme) {
    return Column(
      children: [
        SwitchListTile(
          secondary: const Icon(Icons.airplanemode_active),
          title: const Text('Force Offline Mode'),
          subtitle: const Text('Use only local data, no network requests'),
          value: _offlineMode,
          onChanged: (value) {
            setState(() => _offlineMode = value);
            _saveSetting('offline_mode', value.toString());
          },
        ),

        // Storage info
        FutureBuilder<Map<String, int>>(
          future: ref.read(offlineServiceProvider).getSyncStats(),
          builder: (context, snapshot) {
            final stats = snapshot.data ?? {};
            return ListTile(
              leading: const Icon(Icons.storage),
              title: const Text('Local Storage'),
              subtitle: Text(
                '${stats['unsynced_samples'] ?? 0} unsynced samples, '
                '${stats['pending_sync'] ?? 0} items in queue',
              ),
            );
          },
        ),
      ],
    );
  }

  Widget _buildApiSection(ThemeData theme) {
    return Column(
      children: [
        ListTile(
          leading: const Icon(Icons.key),
          title: const Text('API Endpoint'),
          subtitle: const Text('https://api.afrimine.com'),
          trailing: const Icon(Icons.edit),
          onTap: _showApiEndpointDialog,
        ),
        ListTile(
          leading: const Icon(Icons.storage),
          title: const Text('Supabase URL'),
          subtitle: const Text('Configure database connection'),
          trailing: const Icon(Icons.edit),
          onTap: _showSupabaseDialog,
        ),
      ],
    );
  }

  Widget _buildAboutSection(ThemeData theme) {
    return Column(
      children: [
        const ListTile(
          leading: Icon(Icons.info_outline),
          title: Text('AfriMine AI'),
          subtitle: Text('Version 1.0.0 — Field mineral analysis'),
        ),
        ListTile(
          leading: const Icon(Icons.description),
          title: const Text('Open Source Licenses'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => showLicensePage(context: context),
        ),
      ],
    );
  }

  void _showLanguagePicker() {
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
            const Text('Select Language', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
            const SizedBox(height: 16),
            ...VoiceLanguage.values.map((lang) {
              return RadioListTile<VoiceLanguage>(
                title: Text(lang.displayName),
                subtitle: Text(lang.code),
                value: lang,
                groupValue: _selectedLanguage,
                onChanged: (value) {
                  if (value != null) {
                    setState(() => _selectedLanguage = value);
                    _saveSetting('language', value.code);
                    ref.read(voiceServiceProvider).setLanguage(value);
                    Navigator.pop(context);
                  }
                },
              );
            }),
          ],
        ),
      ),
    );
  }

  void _showLoginDialog(ApiService apiService) {
    final phoneController = TextEditingController();
    final otpController = TextEditingController();
    bool otpSent = false;

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Sign In'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: phoneController,
                decoration: const InputDecoration(
                  labelText: 'Phone Number',
                  hintText: '+254...',
                  prefixIcon: Icon(Icons.phone),
                ),
                keyboardType: TextInputType.phone,
              ),
              if (otpSent) ...[
                const SizedBox(height: 16),
                TextField(
                  controller: otpController,
                  decoration: const InputDecoration(
                    labelText: 'OTP Code',
                    hintText: '123456',
                    prefixIcon: Icon(Icons.lock),
                  ),
                  keyboardType: TextInputType.number,
                ),
              ],
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () async {
                if (!otpSent) {
                  final success = await apiService.requestOtp(phoneController.text);
                  if (success) setDialogState(() => otpSent = true);
                } else {
                  final success = await apiService.verifyOtp(
                    phoneController.text,
                    otpController.text,
                  );
                  if (success && mounted) {
                    Navigator.pop(context);
                    setState(() {});
                  }
                }
              },
              child: Text(otpSent ? 'Verify' : 'Send OTP'),
            ),
          ],
        ),
      ),
    );
  }

  void _showLogoutDialog(ApiService apiService) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Sign Out?'),
        content: const Text('This will clear your saved session.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              await apiService.logout();
              if (mounted) {
                Navigator.pop(context);
                setState(() {});
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Sign Out'),
          ),
        ],
      ),
    );
  }

  void _showApiEndpointDialog() {
    final controller = TextEditingController(
      text: ref.read(apiConfigProvider).baseUrl,
    );

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('API Endpoint'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(
            hintText: 'https://api.afrimine.com',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              ref.read(apiConfigProvider.notifier).state = ApiConfig(
                baseUrl: controller.text,
              );
              Navigator.pop(context);
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  void _showSupabaseDialog() {
    final urlController = TextEditingController();
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Supabase Configuration'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: urlController,
              decoration: const InputDecoration(
                labelText: 'Supabase URL',
                hintText: 'https://xxx.supabase.co',
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'API key is stored securely on device.',
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  Future<void> _triggerSync() async {
    final apiService = ref.read(apiServiceProvider);
    final result = await apiService.syncPendingData();
    if (mounted) {
      ref.invalidate(pendingSyncCountProvider);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Synced: ${result['uploaded']} uploaded, ${result['failed']} failed'),
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }
}
