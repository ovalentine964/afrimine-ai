import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/voice_service.dart';
import '../widgets/sync_indicator.dart';

/// Voice interface screen for hands-free mineral analysis.
///
/// Features:
/// - Big push-to-talk button (easy to tap with gloves)
/// - Live transcription display
/// - Response text with TTS playback
/// - Language selector (Swahili, Dholuo, English)
/// - Offline/online indicator
/// - Voice command history
class VoiceScreen extends ConsumerStatefulWidget {
  const VoiceScreen({super.key});

  @override
  ConsumerState<VoiceScreen> createState() => _VoiceScreenState();
}

class _VoiceScreenState extends ConsumerState<VoiceScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;
  final List<VoiceResult> _history = [];
  final TextEditingController _textController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1000),
      vsync: this,
    );
    _pulseAnimation = Tween<double>(begin: 1.0, end: 1.15).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _textController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final voiceService = ref.watch(voiceServiceProvider);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Voice Assistant'),
        actions: [
          // Language selector
          _buildLanguageSelector(voiceService),
        ],
      ),
      body: Column(
        children: [
          // Status bar
          _buildStatusBar(voiceService, theme),

          // Transcription area
          Expanded(
            child: _buildTranscriptionArea(voiceService, theme),
          ),

          // History
          if (_history.isNotEmpty) _buildHistory(theme),

          // Controls
          _buildControls(voiceService, theme),
        ],
      ),
    );
  }

  Widget _buildLanguageSelector(VoiceService voiceService) {
    return PopupMenuButton<VoiceLanguage>(
      icon: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            voiceService.language.displayName,
            style: const TextStyle(fontSize: 14),
          ),
          const Icon(Icons.arrow_drop_down, size: 20),
        ],
      ),
      onSelected: (lang) => voiceService.setLanguage(lang),
      itemBuilder: (context) => VoiceLanguage.values.map((lang) {
        return PopupMenuItem(
          value: lang,
          child: Row(
            children: [
              if (lang == voiceService.language)
                const Icon(Icons.check, color: Colors.green, size: 18)
              else
                const SizedBox(width: 18),
              const SizedBox(width: 8),
              Text(lang.displayName),
            ],
          ),
        );
      }).toList(),
    );
  }

  Widget _buildStatusBar(VoiceService voiceService, ThemeData theme) {
    return StreamBuilder<VoiceState>(
      stream: voiceService.stateStream,
      initialData: voiceService.state,
      builder: (context, snapshot) {
        final state = snapshot.data ?? VoiceState.idle;
        final isOnline = true; // TODO: Get from connectivity service

        Color color;
        String text;
        IconData icon;

        switch (state) {
          case VoiceState.idle:
            color = Colors.grey;
            text = 'Ready — tap microphone to speak';
            icon = Icons.mic_off;
            break;
          case VoiceState.listening:
            color = Colors.green;
            text = 'Listening...';
            icon = Icons.mic;
            break;
          case VoiceState.processing:
            color = Colors.orange;
            text = 'Processing...';
            icon = Icons.sync;
            break;
          case VoiceState.speaking:
            color = Colors.blue;
            text = 'Speaking...';
            icon = Icons.volume_up;
            break;
          case VoiceState.error:
            color = Colors.red;
            text = 'Error — tap to retry';
            icon = Icons.error;
            break;
        }

        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          color: color.withOpacity(0.08),
          child: Row(
            children: [
              Icon(icon, color: color, size: 18),
              const SizedBox(width: 8),
              Text(text, style: TextStyle(color: color, fontSize: 13)),
              const Spacer(),
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: isOnline ? Colors.green : Colors.red,
                ),
              ),
              const SizedBox(width: 4),
              Text(
                isOnline ? 'Online' : 'Offline',
                style: TextStyle(
                  color: isOnline ? Colors.green : Colors.red,
                  fontSize: 11,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildTranscriptionArea(VoiceService voiceService, ThemeData theme) {
    return StreamBuilder<String>(
      stream: voiceService.transcriptionStream,
      initialData: voiceService.transcription,
      builder: (context, snapshot) {
        final transcription = snapshot.data ?? '';

        return Container(
          margin: const EdgeInsets.all(16),
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: Colors.grey.withOpacity(0.05),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: Colors.grey.withOpacity(0.2)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                voiceService.state == VoiceState.listening
                    ? 'Listening...'
                    : voiceService.state == VoiceState.processing
                        ? 'Processing...'
                        : 'Your voice:',
                style: TextStyle(
                  color: Colors.grey[500],
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 8),
              Expanded(
                child: SingleChildScrollView(
                  child: Text(
                    transcription.isEmpty
                        ? 'Tap the microphone and speak your command.\n\n'
                            'Try: "Analyze this sample" or "What minerals are here?"'
                        : transcription,
                    style: TextStyle(
                      color: transcription.isEmpty ? Colors.grey[400] : Colors.black87,
                      fontSize: transcription.isEmpty ? 14 : 18,
                      height: 1.5,
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildHistory(ThemeData theme) {
    final last = _history.last;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.blue.withOpacity(0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.blue.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                last.isOffline ? Icons.cloud_off : Icons.cloud,
                color: last.isOffline ? Colors.orange : Colors.blue,
                size: 14,
              ),
              const SizedBox(width: 4),
              Text(
                last.isOffline ? 'Offline Response' : 'AI Response',
                style: TextStyle(
                  color: last.isOffline ? Colors.orange : Colors.blue,
                  fontSize: 11,
                  fontWeight: FontWeight.w500,
                ),
              ),
              if (last.confidence != null) ...[
                const Spacer(),
                Text(
                  '${(last.confidence! * 100).round()}%',
                  style: TextStyle(color: Colors.grey[500], fontSize: 11),
                ),
              ],
            ],
          ),
          const SizedBox(height: 6),
          Text(
            last.responseText,
            style: const TextStyle(fontSize: 14),
          ),
        ],
      ),
    );
  }

  Widget _buildControls(VoiceService voiceService, ThemeData theme) {
    return Container(
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).padding.bottom + 20,
        top: 20,
        left: 32,
        right: 32,
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          // Cancel button
          if (voiceService.state != VoiceState.idle)
            _controlCircleButton(
              icon: Icons.close,
              color: Colors.red,
              onTap: () => voiceService.cancel(),
            ),

          // Push-to-talk button
          GestureDetector(
            onTapDown: (_) => _startListening(voiceService),
            onTapUp: (_) => _stopListening(voiceService),
            onTapCancel: () => voiceService.cancel(),
            child: AnimatedBuilder(
              animation: _pulseAnimation,
              builder: (context, child) {
                final isListening = voiceService.state == VoiceState.listening;
                return Transform.scale(
                  scale: isListening ? _pulseAnimation.value : 1.0,
                  child: Container(
                    width: 88,
                    height: 88,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: isListening
                          ? Colors.red
                          : voiceService.state == VoiceState.processing
                              ? Colors.orange
                              : Colors.green[700],
                      boxShadow: [
                        BoxShadow(
                          color: (isListening ? Colors.red : Colors.green)
                              .withOpacity(0.4),
                          blurRadius: 24,
                          spreadRadius: 6,
                        ),
                      ],
                    ),
                    child: Icon(
                      isListening
                          ? Icons.mic
                          : voiceService.state == VoiceState.processing
                              ? Icons.hourglass_top
                              : Icons.mic_none,
                      color: Colors.white,
                      size: 40,
                    ),
                  ),
                );
              },
            ),
          ),

          // Text input button
          _controlCircleButton(
            icon: Icons.keyboard,
            color: Colors.grey,
            onTap: _showTextInput,
          ),
        ],
      ),
    );
  }

  Widget _controlCircleButton({
    required IconData icon,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 48,
        height: 48,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: color.withOpacity(0.1),
        ),
        child: Icon(icon, color: color, size: 24),
      ),
    );
  }

  Future<void> _startListening(VoiceService voiceService) async {
    final success = await voiceService.startListening();
    if (success) {
      _pulseController.repeat(reverse: true);
    }
  }

  Future<void> _stopListening(VoiceService voiceService) async {
    _pulseController.stop();
    _pulseController.value = 0;

    final result = await voiceService.stopListening();
    if (result != null && mounted) {
      setState(() => _history.add(result));
    }
  }

  void _showTextInput() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (context) => Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom,
          left: 16,
          right: 16,
          top: 16,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Type your command',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _textController,
              decoration: InputDecoration(
                hintText: 'e.g., "Analyze this gold sample"',
                filled: true,
                fillColor: Colors.grey[100],
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
              ),
              autofocus: true,
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () async {
                  final text = _textController.text.trim();
                  if (text.isNotEmpty) {
                    Navigator.pop(context);
                    final voiceService = ref.read(voiceServiceProvider);
                    final result = await voiceService.processTextCommand(text);
                    if (mounted) {
                      setState(() => _history.add(result));
                    }
                    _textController.clear();
                  }
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.green[700],
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                child: const Text('Send'),
              ),
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }
}
