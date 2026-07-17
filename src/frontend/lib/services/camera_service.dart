import 'dart:io';
import 'package:camera/camera.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as path;
import '../utils/constants.dart';

class CameraService {
  static CameraService? _instance;
  final ImagePicker _picker = ImagePicker();
  List<CameraDescription> _cameras = [];
  CameraController? _controller;

  CameraService._();

  factory CameraService() {
    _instance ??= CameraService._();
    return _instance!;
  }

  List<CameraDescription> get cameras => _cameras;
  CameraController? get controller => _controller;
  bool get isInitialized => _controller?.value.isInitialized ?? false;

  Future<void> initializeCameras() async {
    try {
      _cameras = await availableCameras();
    } catch (e) {
      _cameras = [];
    }
  }

  Future<CameraController?> initController({int cameraIndex = 0}) async {
    if (_cameras.isEmpty) await initializeCameras();
    if (_cameras.isEmpty) return null;

    await _controller?.dispose();
    final idx = cameraIndex.clamp(0, _cameras.length - 1);
    _controller = CameraController(
      _cameras[idx],
      ResolutionPreset.high,
      enableAudio: false,
      imageFormatGroup: ImageFormatGroup.jpeg,
    );

    try {
      await _controller!.initialize();
      return _controller!;
    } catch (e) {
      return null;
    }
  }

  Future<File?> takePicture() async {
    if (!isInitialized) return null;

    try {
      final xFile = await _controller!.takePicture();
      final appDir = await getApplicationDocumentsDirectory();
      final samplesDir = Directory(path.join(appDir.path, 'samples'));
      if (!await samplesDir.exists()) {
        await samplesDir.create(recursive: true);
      }

      final fileName = 'sample_${DateTime.now().millisecondsSinceEpoch}.jpg';
      final savedPath = path.join(samplesDir.path, fileName);
      final savedFile = await File(xFile.path).copy(savedPath);
      return savedFile;
    } catch (e) {
      return null;
    }
  }

  Future<File?> pickFromGallery() async {
    try {
      final xFile = await _picker.pickImage(
        source: ImageSource.gallery,
        maxWidth: AppConstants.maxImageWidth.toDouble(),
        imageQuality: (AppConstants.imageQuality * 100).toInt(),
      );

      if (xFile == null) return null;

      final appDir = await getApplicationDocumentsDirectory();
      final samplesDir = Directory(path.join(appDir.path, 'samples'));
      if (!await samplesDir.exists()) {
        await samplesDir.create(recursive: true);
      }

      final fileName = 'sample_${DateTime.now().millisecondsSinceEpoch}.jpg';
      final savedPath = path.join(samplesDir.path, fileName);
      final savedFile = await File(xFile.path).copy(savedPath);
      return savedFile;
    } catch (e) {
      return null;
    }
  }

  Future<void> toggleFlash() async {
    if (!isInitialized) return;
    final mode = _controller!.value.flashMode;
    if (mode == FlashMode.off) {
      await _controller!.setFlashMode(FlashMode.torch);
    } else {
      await _controller!.setFlashMode(FlashMode.off);
    }
  }

  Future<void> switchCamera() async {
    if (_cameras.length < 2) return;
    final currentIdx = _cameras.indexOf(_controller!.description);
    final nextIdx = (currentIdx + 1) % _cameras.length;
    await initController(cameraIndex: nextIdx);
  }

  void dispose() {
    _controller?.dispose();
    _controller = null;
  }
}
