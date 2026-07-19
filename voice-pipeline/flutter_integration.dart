/// AfriMine AI — Flutter Voice Interface
///
/// Dart/Flutter code for the mobile app voice interface.
/// Integrates with the Python voice pipeline via platform channels.
///
/// Architecture:
/// - Microphone capture via `record` package
/// - STT via `vosk_flutter` (offline) or API call (online)
/// - TTS via `flutter_tts` (offline Piper wrapper) or `audioplayers`
/// - State management via Riverpod
///
/// Designed for: Android 8+, 2GB RAM, cheap phones
library afrimine_voice;

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:connectivity_plus/connectivity_plus.dart';

// ============================================================
// Voice Pipeline State
// ============================================================

/// Pipeline operating mode
enum PipelineMode { offline, online }

/// Voice pipeline states
enum PipelineState {
  idle,
  listening,
  processing,
  speaking,
  error,
}

/// Supported languages
enum AfriLanguage {
  swahili('sw', 'Kiswahili'),
  dholuo('luo', 'Dholuo'),
  kikuyu('ki', 'Gikuyu'),
  english('en', 'English');

  const AfriLanguage(this.code, this.displayName);
  final String code;
  final String displayName;
}

/// Voice intent classification
enum VoiceIntent {
  analyzeSample,
  checkGold,
  checkMineral,
  generateReport,
  getPrice,
  showMap,
  checkCompliance,
  saveNote,
  syncData,
  help,
  status,
  repeat,
  cancel,
  unknown,
}

/// Pipeline response
class VoiceResponse {
  final String text;
  final VoiceIntent intent;
  final double confidence;
  final Map<String, dynamic>? agentResult;
  final bool isOffline;
  final Uint8List? audioBytes;

  const VoiceResponse({
    required this.text,
    required this.intent,
    this.confidence = 0.0,
    this.agentResult,
    this.isOffline = false,
    this.audioBytes,
  });

  factory VoiceResponse.fromJson(Map<String, dynamic> json) {
    return VoiceResponse(
      text: json['text'] as String? ?? '',
      intent: VoiceIntent.values.firstWhere(
        (e) => e.name == json['intent'],
        orElse: () => VoiceIntent.unknown,
      ),
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      agentResult: json['agent_result'] as Map<String, dynamic>?,
      isOffline: json['is_offline'] as bool? ?? false,
      audioBytes: json['audio_bytes'] != null
          ? base64Decode(json['audio_bytes'] as String)
          : null,
    );
  }
}

// ============================================================
// Platform Channel Bridge to Python Pipeline
// ============================================================

/// Bridge to the Python voice pipeline running in a background service.
///
/// On Android, the Python pipeline runs as a foreground service
/// communicating via MethodChannel.
class VoicePipelineBridge {
  static const _channel = MethodChannel('afrimine/voice_pipeline');
  static const _eventChannel = EventChannel('afrimine/voice_events');

  /// Initialize the Python pipeline
  static Future<bool> initialize({
    AfriLanguage language = AfriLanguage.swahili,
    PipelineMode mode = PipelineMode.offline,
  }) async {
    try {
      final result = await _channel.invokeMethod<bool>('initialize', {
        'language': language.code,
        'mode': mode.name,
      });
      return result ?? false;
    } on PlatformException catch (e) {
      debugPrint('Pipeline init failed: ${e.message}');
      return false;
    }
  }

  /// Process text input (bypass STT)
  static Future<VoiceResponse?> processText(String text, {
    AfriLanguage language = AfriLanguage.swahili,
  }) async {
    try {
      final result = await _channel.invokeMethod<Map>('process_text', {
        'text': text,
        'language': language.code,
      });
      if (result != null) {
        return VoiceResponse.fromJson(Map<String, dynamic>.from(result));
      }
    } on PlatformException catch (e) {
      debugPrint('Process text failed: ${e.message}');
    }
    return null;
  }

  /// Process voice (listen → transcribe → respond)
  static Future<VoiceResponse?> processVoice({
    AfriLanguage language = AfriLanguage.swahili,
  }) async {
    try {
      final result = await _channel.invokeMethod<Map>('process_voice', {
        'language': language.code,
      });
      if (result != null) {
        return VoiceResponse.fromJson(Map<String, dynamic>.from(result));
      }
    } on PlatformException catch (e) {
      debugPrint('Process voice failed: ${e.message}');
    }
    return null;
  }

  /// Stream of voice pipeline events (partial transcriptions, status)
  static Stream<Map<String, dynamic>> get eventStream {
    return _eventChannel
        .receiveBroadcastStream()
        .map((event) => Map<String, dynamic>.from(event as Map));
  }

  /// Set online/offline status
  static Future<void> setOnlineStatus(bool isOnline) async {
    await _channel.invokeMethod('set_online_status', {
      'is_online': isOnline,
    });
  }
}

// ============================================================
// Audio Recording Service
// ============================================================

/// Handles microphone recording for voice input.
/// Uses the `record` package for cross-platform audio capture.
class AudioRecordingService {
  final AudioRecorder _recorder = AudioRecorder();
  bool _isRecording = false;
  String? _currentPath;

  /// Request microphone permission
  Future<bool> requestPermission() async {
    final status = await Permission.microphone.request();
    return status.isGranted;
  }

  /// Start recording audio
  Future<String?> startRecording() async {
    if (_isRecording) return null;

    final hasPermission = await requestPermission();
    if (!hasPermission) {
      debugPrint('Microphone permission denied');
      return null;
    }

    try {
      final dir = await getTemporaryDirectory();
      _currentPath = '${dir.path}/voice_input_${DateTime.now().millisecondsSinceEpoch}.wav';

      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.wav,
          sampleRate: 16000,
          numChannels: 1,
          bitRate: 256000,
        ),
        path: _currentPath!,
      );

      _isRecording = true;
      debugPrint('Recording started: $_currentPath');
      return _currentPath;
    } catch (e) {
      debugPrint('Recording failed: $e');
      return null;
    }
  }

  /// Stop recording and return the file path
  Future<String?> stopRecording() async {
    if (!_isRecording) return null;

    try {
      final path = await _recorder.stop();
      _isRecording = false;
      debugPrint('Recording stopped: $path');
      return path;
    } catch (e) {
      debugPrint('Stop recording failed: $e');
      return null;
    }
  }

  /// Check if currently recording
  bool get isRecording => _isRecording;

  /// Dispose resources
  void dispose() {
    _recorder.dispose();
  }
}

// ============================================================
// TTS Service
// ============================================================

/// Text-to-speech service using local audio playback.
/// Plays WAV files generated by Piper TTS.
class TTSService {
  final AudioPlayer _player = AudioPlayer();
  bool _isSpeaking = false;

  /// Play audio bytes (WAV format)
  Future<void> playAudio(Uint8List audioBytes) async {
    try {
      _isSpeaking = true;

      // Write to temp file
      final dir = await getTemporaryDirectory();
      final file = File('${dir.path}/tts_output.wav');
      await file.writeAsBytes(audioBytes);

      // Play
      await _player.play(DeviceFileSource(file.path));
      await _player.onPlayerComplete.first;

      _isSpeaking = false;
    } catch (e) {
      _isSpeaking = false;
      debugPrint('TTS playback failed: $e');
    }
  }

  /// Play audio from file path
  Future<void> playFile(String path) async {
    try {
      _isSpeaking = true;
      await _player.play(DeviceFileSource(path));
      await _player.onPlayerComplete.first;
      _isSpeaking = false;
    } catch (e) {
      _isSpeaking = false;
      debugPrint('TTS file playback failed: $e');
    }
  }

  /// Stop speaking
  Future<void> stop() async {
    await _player.stop();
    _isSpeaking = false;
  }

  bool get isSpeaking => _isSpeaking;

  void dispose() {
    _player.dispose();
  }
}

// ============================================================
// Connectivity Monitor
// ============================================================

/// Monitors network connectivity for offline/online transitions.
class ConnectivityService {
  final Connectivity _connectivity = Connectivity();
  final StreamController<bool> _statusController = StreamController<bool>.broadcast();

  bool _isOnline = false;
  StreamSubscription? _subscription;

  ConnectivityService() {
    _subscription = _connectivity.onConnectivityChanged.listen(_onConnectivityChanged);
    _checkInitial();
  }

  bool get isOnline => _isOnline;
  Stream<bool> get statusStream => _statusController.stream;

  Future<void> _checkInitial() async {
    final result = await _connectivity.checkConnectivity();
    _updateStatus(result);
  }

  void _onConnectivityChanged(List<ConnectivityResult> results) {
    _updateStatus(results);
  }

  void _updateStatus(List<ConnectivityResult> results) {
    final wasOnline = _isOnline;
    _isOnline = results.any((r) => r != ConnectivityResult.none);

    if (wasOnline != _isOnline) {
      _statusController.add(_isOnline);
      debugPrint('Connectivity: ${_isOnline ? "ONLINE" : "OFFLINE"}');
    }
  }

  void dispose() {
    _subscription?.cancel();
    _statusController.close();
  }
}

// ============================================================
// Riverpod Providers
// ============================================================

/// Current pipeline state
final pipelineStateProvider = StateProvider<PipelineState>(
  (ref) => PipelineState.idle,
);

/// Selected language
final languageProvider = StateProvider<AfriLanguage>(
  (ref) => AfriLanguage.swahili,
);

/// Pipeline mode (offline/online)
final pipelineModeProvider = StateProvider<PipelineMode>(
  (ref) => PipelineMode.offline,
);

/// Connectivity status
final connectivityProvider = StreamProvider<bool>(
  (ref) => ConnectivityService().statusStream,
);

/// Voice response history
final voiceHistoryProvider = StateNotifierProvider<VoiceHistoryNotifier, List<VoiceResponse>>(
  (ref) => VoiceHistoryNotifier(),
);

class VoiceHistoryNotifier extends StateNotifier<List<VoiceResponse>> {
  VoiceHistoryNotifier() : super([]);

  void addResponse(VoiceResponse response) {
    state = [...state, response];
  }

  void clear() {
    state = [];
  }
}

/// Current transcription text
final transcriptionProvider = StateProvider<String>((ref) => '');

// ============================================================
// Voice Pipeline Controller
// ============================================================

/// Main controller that orchestrates the voice pipeline.
class VoicePipelineController {
  final AudioRecordingService _recording = AudioRecordingService();
  final TTSService _tts = TTSService();
  final ConnectivityService _connectivity = ConnectivityService();
  final WidgetRef _ref;

  VoicePipelineController(this._ref) {
    // Update pipeline mode when connectivity changes
    _connectivity.statusStream.listen((isOnline) {
      _ref.read(pipelineModeProvider.notifier).state =
          isOnline ? PipelineMode.online : PipelineMode.offline;
      VoicePipelineBridge.setOnlineStatus(isOnline);
    });
  }

  /// Initialize the pipeline
  Future<bool> initialize() async {
    final language = _ref.read(languageProvider);
    final mode = _ref.read(pipelineModeProvider);

    final success = await VoicePipelineBridge.initialize(
      language: language,
      mode: mode,
    );

    if (!success) {
      _ref.read(pipelineStateProvider.notifier).state = PipelineState.error;
    }

    return success;
  }

  /// Start voice interaction (press-to-talk)
  Future<void> startVoiceInput() async {
    final state = _ref.read(pipelineStateProvider);
    if (state == PipelineState.listening || state == PipelineState.processing) {
      return;
    }

    _ref.read(pipelineStateProvider.notifier).state = PipelineState.listening;
    _ref.read(transcriptionProvider.notifier).state = '';

    // Start recording
    await _recording.startRecording();

    // Listen for partial transcriptions
    VoicePipelineBridge.eventStream.listen((event) {
      if (event['type'] == 'partial_transcription') {
        _ref.read(transcriptionProvider.notifier).state =
            event['text'] as String? ?? '';
      }
    });
  }

  /// Stop voice input and process
  Future<void> stopVoiceInput() async {
    final state = _ref.read(pipelineStateProvider);
    if (state != PipelineState.listening) return;

    _ref.read(pipelineStateProvider.notifier).state = PipelineState.processing;

    // Stop recording
    final audioPath = await _recording.stopRecording();
    if (audioPath == null) {
      _ref.read(pipelineStateProvider.notifier).state = PipelineState.error;
      return;
    }

    // Process through pipeline
    final language = _ref.read(languageProvider);
    final response = await VoicePipelineBridge.processVoice(language: language);

    if (response != null) {
      _ref.read(voiceHistoryProvider.notifier).addResponse(response);
      _ref.read(transcriptionProvider.notifier).state = response.text;

      // Speak response
      if (response.audioBytes != null) {
        _ref.read(pipelineStateProvider.notifier).state = PipelineState.speaking;
        await _tts.playAudio(response.audioBytes!);
      }
    }

    _ref.read(pipelineStateProvider.notifier).state = PipelineState.idle;
  }

  /// Process text input (keyboard)
  Future<void> processTextInput(String text) async {
    if (text.trim().isEmpty) return;

    _ref.read(pipelineStateProvider.notifier).state = PipelineState.processing;

    final language = _ref.read(languageProvider);
    final response = await VoicePipelineBridge.processText(text, language: language);

    if (response != null) {
      _ref.read(voiceHistoryProvider.notifier).addResponse(response);

      if (response.audioBytes != null) {
        _ref.read(pipelineStateProvider.notifier).state = PipelineState.speaking;
        await _tts.playAudio(response.audioBytes!);
      }
    }

    _ref.read(pipelineStateProvider.notifier).state = PipelineState.idle;
  }

  /// Cancel current operation
  Future<void> cancel() async {
    await _recording.stopRecording();
    await _tts.stop();
    _ref.read(pipelineStateProvider.notifier).state = PipelineState.idle;
  }

  /// Dispose resources
  void dispose() {
    _recording.dispose();
    _tts.dispose();
    _connectivity.dispose();
  }
}

// ============================================================
// Voice UI Widget
// ============================================================

/// Main voice interface widget for the AfriMine app.
///
/// Shows:
/// - Push-to-talk button (big, easy to tap with gloves)
/// - Live transcription text
/// - Response text + audio playback
/// - Language selector
/// - Offline/online indicator
class VoiceInterfaceWidget extends ConsumerStatefulWidget {
  const VoiceInterfaceWidget({super.key});

  @override
  ConsumerState<VoiceInterfaceWidget> createState() => _VoiceInterfaceState();
}

class _VoiceInterfaceState extends ConsumerState<VoiceInterfaceWidget>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;
  VoicePipelineController? _controller;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1000),
      vsync: this,
    );
    _pulseAnimation = Tween<double>(begin: 1.0, end: 1.2).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pipelineState = ref.watch(pipelineStateProvider);
    final transcription = ref.watch(transcriptionProvider);
    final history = ref.watch(voiceHistoryProvider);
    final isOnline = ref.watch(connectivityProvider).valueOrNull ?? false;
    final language = ref.watch(languageProvider);

    // Animate pulse when listening
    if (pipelineState == PipelineState.listening) {
      _pulseController.repeat(reverse: true);
    } else {
      _pulseController.stop();
      _pulseController.value = 0;
    }

    return Container(
      decoration: BoxDecoration(
        color: Colors.grey[900],
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Status bar
          _buildStatusBar(isOnline, language, pipelineState),

          // Transcription area
          _buildTranscriptionArea(transcription, pipelineState),

          // Response history
          if (history.isNotEmpty) _buildResponseHistory(history),

          // Control buttons
          _buildControls(pipelineState),

          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Widget _buildStatusBar(bool isOnline, AfriLanguage language, PipelineState state) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          // Online/offline indicator
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: isOnline ? Colors.green : Colors.red,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            isOnline ? 'Online' : 'Offline',
            style: TextStyle(
              color: isOnline ? Colors.green : Colors.red,
              fontSize: 12,
            ),
          ),
          const Spacer(),
          // Language selector
          DropdownButton<AfriLanguage>(
            value: language,
            dropdownColor: Colors.grey[800],
            style: const TextStyle(color: Colors.white, fontSize: 12),
            underline: const SizedBox(),
            items: AfriLanguage.values.map((lang) {
              return DropdownMenuItem(
                value: lang,
                child: Text(lang.displayName),
              );
            }).toList(),
            onChanged: (lang) {
              if (lang != null) {
                ref.read(languageProvider.notifier).state = lang;
              }
            },
          ),
          const SizedBox(width: 8),
          // Pipeline state indicator
          _buildStateIndicator(state),
        ],
      ),
    );
  }

  Widget _buildStateIndicator(PipelineState state) {
    IconData icon;
    Color color;
    switch (state) {
      case PipelineState.idle:
        icon = Icons.mic_off;
        color = Colors.grey;
        break;
      case PipelineState.listening:
        icon = Icons.mic;
        color = Colors.green;
        break;
      case PipelineState.processing:
        icon = Icons.sync;
        color = Colors.orange;
        break;
      case PipelineState.speaking:
        icon = Icons.volume_up;
        color = Colors.blue;
        break;
      case PipelineState.error:
        icon = Icons.error;
        color = Colors.red;
        break;
    }
    return Icon(icon, color: color, size: 20);
  }

  Widget _buildTranscriptionArea(String transcription, PipelineState state) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.grey[850],
        borderRadius: BorderRadius.circular(12),
      ),
      constraints: const BoxConstraints(minHeight: 80),
      width: double.infinity,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            state == PipelineState.listening ? 'Listening...' :
            state == PipelineState.processing ? 'Processing...' :
            'Your voice:',
            style: TextStyle(
              color: Colors.grey[500],
              fontSize: 11,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            transcription.isEmpty ? 'Tap the microphone to start' : transcription,
            style: TextStyle(
              color: transcription.isEmpty ? Colors.grey[600] : Colors.white,
              fontSize: 16,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildResponseHistory(List<VoiceResponse> history) {
    final lastResponse = history.last;
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.blue[900]?.withOpacity(0.3),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.blue[800]!, width: 0.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                lastResponse.isOffline ? Icons.cloud_off : Icons.cloud,
                color: lastResponse.isOffline ? Colors.orange : Colors.blue,
                size: 14,
              ),
              const SizedBox(width: 4),
              Text(
                lastResponse.isOffline ? 'Offline Response' : 'AI Response',
                style: TextStyle(
                  color: Colors.blue[300],
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const Spacer(),
              Text(
                '${(lastResponse.confidence * 100).round()}%',
                style: TextStyle(
                  color: Colors.grey[500],
                  fontSize: 11,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            lastResponse.text,
            style: const TextStyle(color: Colors.white, fontSize: 14),
          ),
        ],
      ),
    );
  }

  Widget _buildControls(PipelineState state) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          // Cancel button
          if (state != PipelineState.idle)
            IconButton(
              onPressed: () => _controller?.cancel(),
              icon: const Icon(Icons.close, color: Colors.red),
              iconSize: 32,
            ),

          // Main push-to-talk button
          GestureDetector(
            onTapDown: (_) => _controller?.startVoiceInput(),
            onTapUp: (_) => _controller?.stopVoiceInput(),
            onTapCancel: () => _controller?.cancel(),
            child: AnimatedBuilder(
              animation: _pulseAnimation,
              builder: (context, child) {
                return Transform.scale(
                  scale: state == PipelineState.listening ? _pulseAnimation.value : 1.0,
                  child: Container(
                    width: 80,
                    height: 80,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: state == PipelineState.listening
                          ? Colors.red
                          : state == PipelineState.processing
                              ? Colors.orange
                              : Colors.green,
                      boxShadow: [
                        BoxShadow(
                          color: (state == PipelineState.listening
                                  ? Colors.red
                                  : Colors.green)
                              .withOpacity(0.4),
                          blurRadius: 20,
                          spreadRadius: 5,
                        ),
                      ],
                    ),
                    child: Icon(
                      state == PipelineState.listening
                          ? Icons.mic
                          : state == PipelineState.processing
                              ? Icons.hourglass_top
                              : Icons.mic_none,
                      color: Colors.white,
                      size: 36,
                    ),
                  ),
                );
              },
            ),
          ),

          // Text input button
          IconButton(
            onPressed: () => _showTextInput(context),
            icon: const Icon(Icons.keyboard, color: Colors.grey),
            iconSize: 32,
          ),
        ],
      ),
    );
  }

  void _showTextInput(BuildContext context) {
    final textController = TextEditingController();
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.grey[900],
      builder: (context) => Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: textController,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: 'Type your command...',
                hintStyle: TextStyle(color: Colors.grey[600]),
                filled: true,
                fillColor: Colors.grey[850],
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
              ),
              autofocus: true,
            ),
            const SizedBox(height: 12),
            ElevatedButton(
              onPressed: () {
                final text = textController.text.trim();
                if (text.isNotEmpty) {
                  _controller?.processTextInput(text);
                  Navigator.pop(context);
                }
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.green,
                minimumSize: const Size(double.infinity, 48),
              ),
              child: const Text('Send'),
            ),
          ],
        ),
      ),
    );
  }
}

// ============================================================
// Example Usage in Main App
// ============================================================

/// Example: How to integrate VoiceInterfaceWidget in your app
///
/// ```dart
/// class AfriMineApp extends StatelessWidget {
///   @override
///   Widget build(BuildContext context) {
///     return ProviderScope(
///       child: MaterialApp(
///         home: Scaffold(
///           body: Column(
///             children: [
///               // Main app content (map, samples, etc.)
///               Expanded(child: MapView()),
///               
///               // Voice interface at bottom
///               const VoiceInterfaceWidget(),
///             ],
///           ),
///         ),
///       ),
///     );
///   }
/// }
/// ```
///
/// For the Android platform channel implementation, create:
/// android/app/src/main/kotlin/com/afrimine/VoicePipelinePlugin.kt
///
/// This plugin spawns the Python pipeline as a background service
/// and communicates via MethodChannel/EventChannel.
