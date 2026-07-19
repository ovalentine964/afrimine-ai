import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;
import 'package:permission_handler/permission_handler.dart';

import '../services/api_service.dart';

final voiceServiceProvider = Provider<VoiceService>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  final service = VoiceService(apiService: apiService);
  ref.onDispose(() => service.dispose());
  return service;
});

/// Supported languages for voice interaction.
enum VoiceLanguage {
  english('en', 'English'),
  swahili('sw', 'Kiswahili'),
  dholuo('luo', 'Dholuo'),
  kikuyu('ki', 'Gikuyu');

  const VoiceLanguage(this.code, this.displayName);
  final String code;
  final String displayName;
}

/// State of the voice pipeline.
enum VoiceState {
  idle,
  listening,
  processing,
  speaking,
  error,
}

/// A voice interaction result.
class VoiceResult {
  final String transcribedText;
  final String responseText;
  final VoiceLanguage language;
  final bool isOffline;
  final double? confidence;

  const VoiceResult({
    required this.transcribedText,
    required this.responseText,
    required this.language,
    this.isOffline = false,
    this.confidence,
  });

  /// Backward-compatible getters for screens that reference shorter names.
  String get text => responseText;
  String get transcription => transcribedText;
}

/// Voice service integrating Vosk STT + Piper TTS.
///
/// Pipeline:
/// 1. Record audio via `record` package
/// 2. Transcribe via Vosk (offline) or Groq Whisper (online)
/// 3. Send text to backend for LLM processing
/// 4. Speak response via Flutter TTS (wraps Piper)
///
/// Designed for field workers: big push-to-talk button,
/// works offline with Vosk models, supports Dholuo/Swahili.
class VoiceService {
  final ApiService apiService;

  final AudioRecorder _recorder = AudioRecorder();
  final FlutterTts _tts = FlutterTts();

  VoiceState _state = VoiceState.idle;
  VoiceLanguage _language = VoiceLanguage.swahili;
  String _transcription = '';
  String? _currentRecordingPath;

  final _stateController = StreamController<VoiceState>.broadcast();
  final _transcriptionController = StreamController<String>.broadcast();

  VoiceService({required this.apiService}) {
    _initTts();
  }

  // ===========================================================================
  // INITIALIZATION
  // ===========================================================================

  Future<void> _initTts() async {
    await _tts.setLanguage(_language.code);
    await _tts.setSpeechRate(0.8); // Slightly slower for clarity
    await _tts.setVolume(1.0);
    await _tts.setPitch(1.0);

    _tts.setCompletionHandler(() {
      _updateState(VoiceState.idle);
    });

    _tts.setErrorHandler((msg) {
      _updateState(VoiceState.error);
    });
  }

  // ===========================================================================
  // STATE
  // ===========================================================================

  VoiceState get state => _state;
  String get transcription => _transcription;
  VoiceLanguage get language => _language;

  Stream<VoiceState> get stateStream => _stateController.stream;
  Stream<String> get transcriptionStream => _transcriptionController.stream;

  void _updateState(VoiceState newState) {
    _state = newState;
    _stateController.add(newState);
  }

  void _updateTranscription(String text) {
    _transcription = text;
    _transcriptionController.add(text);
  }

  // ===========================================================================
  // LANGUAGE
  // ===========================================================================

  Future<void> setLanguage(VoiceLanguage language) async {
    _language = language;
    await _tts.setLanguage(language.code);
  }

  // ===========================================================================
  // RECORDING (Push-to-Talk)
  // ===========================================================================

  /// Start recording voice input.
  Future<bool> startListening() async {
    if (_state == VoiceState.listening || _state == VoiceState.processing) {
      return false;
    }

    // Request microphone permission
    final status = await Permission.microphone.request();
    if (!status.isGranted) return false;

    try {
      final dir = await getTemporaryDirectory();
      _currentRecordingPath = p.join(
        dir.path,
        'voice_${DateTime.now().millisecondsSinceEpoch}.wav',
      );

      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.wav,
          sampleRate: 16000,
          numChannels: 1,
          bitRate: 256000,
        ),
        path: _currentRecordingPath!,
      );

      _updateState(VoiceState.listening);
      _updateTranscription('');
      return true;
    } catch (e) {
      _updateState(VoiceState.error);
      return false;
    }
  }

  /// Stop recording and process the voice input.
  Future<VoiceResult?> stopListening() async {
    if (_state != VoiceState.listening) return null;

    try {
      await _recorder.stop();
      _updateState(VoiceState.processing);

      if (_currentRecordingPath == null) {
        _updateState(VoiceState.error);
        return null;
      }

      // Step 1: Transcribe (STT)
      final transcribed = await _transcribe(_currentRecordingPath!);
      _updateTranscription(transcribed ?? '');

      if (transcribed == null || transcribed.isEmpty) {
        _updateState(VoiceState.idle);
        return VoiceResult(
          transcribedText: '',
          responseText: 'Sorry, I could not understand. Please try again.',
          language: _language,
          isOffline: true,
        );
      }

      // Step 2: Process via backend
      final response = await _processCommand(transcribed);

      // Step 3: Speak response (TTS)
      if (response != null && response.isNotEmpty) {
        _updateState(VoiceState.speaking);
        await _speak(response);
      } else {
        _updateState(VoiceState.idle);
      }

      return VoiceResult(
        transcribedText: transcribed,
        responseText: response ?? 'No response from server.',
        language: _language,
        isOffline: false,
      );
    } catch (e) {
      _updateState(VoiceState.error);
      return null;
    }
  }

  /// Cancel current recording.
  Future<void> cancel() async {
    await _recorder.stop();
    await _tts.stop();
    _updateState(VoiceState.idle);
    _updateTranscription('');
  }

  // ===========================================================================
  // STT (Speech-to-Text)
  // ===========================================================================

  /// Transcribe audio file to text.
  ///
  /// Uses Groq Whisper API when online, falls back to Vosk offline.
  Future<String?> _transcribe(String audioPath) async {
    try {
      // Try online first (Groq Whisper — better accuracy)
      if (await apiService.checkHealth()) {
        // TODO: Implement Groq Whisper upload
        // For now, fall through to offline
      }

      // Offline: use Vosk via platform channel
      // This would connect to a Vosk model loaded on the device
      // For MVP, we'll use a simple platform channel approach
      return null; // Placeholder — requires native Android integration
    } catch (e) {
      return null;
    }
  }

  // ===========================================================================
  // LLM PROCESSING
  // ===========================================================================

  /// Send transcribed text to backend for processing.
  Future<String?> _processCommand(String text) async {
    try {
      // TODO: Send to Go backend /v1/voice/process endpoint
      // For now, return a placeholder
      return 'I heard: $text. Processing your request...';
    } catch (e) {
      return 'Sorry, I could not process your request. Please try again.';
    }
  }

  // ===========================================================================
  // TTS (Text-to-Speech)
  // ===========================================================================

  /// Speak text aloud using Flutter TTS (wraps Piper on Android).
  Future<void> _speak(String text) async {
    await _tts.speak(text);
  }

  /// Speak text directly (public API for other screens).
  Future<void> speak(String text) async {
    _updateState(VoiceState.speaking);
    await _tts.speak(text);
  }

  /// Stop speaking.
  Future<void> stopSpeaking() async {
    await _tts.stop();
    _updateState(VoiceState.idle);
  }

  // ===========================================================================
  // VOICE COMMANDS
  // ===========================================================================

  /// Process a text command (bypass STT, for keyboard input).
  Future<VoiceResult> processTextCommand(String text) async {
    _updateState(VoiceState.processing);

    final response = await _processCommand(text);

    if (response != null) {
      _updateState(VoiceState.speaking);
      await _speak(response);
    } else {
      _updateState(VoiceState.idle);
    }

    return VoiceResult(
      transcribedText: text,
      responseText: response ?? 'No response.',
      language: _language,
    );
  }

  // ===========================================================================
  // DISPOSE
  // ===========================================================================

  void dispose() {
    _recorder.dispose();
    _tts.stop();
    _stateController.close();
    _transcriptionController.close();
  }
}
