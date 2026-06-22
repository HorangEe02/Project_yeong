// screens/camera_screen.dart — 영양제·식단 인앱 라이브 프리뷰
//
// 디자인 (Pillyze/토스 톤, LADS v2):
//   - 풀스크린 검정 BG (탭바 숨김 — MainShell 에서 처리)
//   - 카메라 라이브 프리뷰 (가이드 프레임 안)
//   - 4 모서리 강조 + 안내 텍스트
//   - 하단: 모드 토글 (영양제/식단) + 큰 셔터 + 갤러리
//   - 촬영 → 인앱 미리보기 → 분석하기 / 다시 촬영
//
// camera 패키지: 라이브 프리뷰 + takePicture()
// image_picker 는 갤러리 진입용으로만 사용
//
// 권한 (AndroidManifest / iOS Info.plist) 박혀있어야 함 — 이미 박혔음

import 'dart:async';
import 'dart:io';
import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../core/storage/local_prefs.dart';
import '../features/supplements/image_quality_probe.dart';
import '../features/supplements/supplement_models.dart';
import '../utils/design_tokens_v2.dart';
import '../utils/device_env.dart';
import '../widgets/common/capture_guide_modal.dart';

enum _CaptureMode { supplement, meal }

// 카메라 초기화 오류 분류 (figma 912:23 권한 / 912:69 초기화 실패).
// 권한 거부면 설정·갤러리 안내, 그 외는 재시도·갤러리 안내로 가른다.
enum _CameraErrorKind { permissionDenied, initFailed }

class _CapturedSupplementImage {
  const _CapturedSupplementImage({required this.file, required this.role});

  final File file;
  final String role;

  SupplementImageUpload toUpload() {
    return SupplementImageUpload(path: file.path, role: role);
  }
}

const bool _enableEmulatorLiveCamera = bool.fromEnvironment(
  'LEMON_ENABLE_EMULATOR_LIVE_CAMERA',
);
const String _debugSupplementImagePathFromEnv = String.fromEnvironment(
  'LEMON_DEBUG_SUPPLEMENT_IMAGE_PATH',
);
const String _macCameraBridgeUrlFromEnv = String.fromEnvironment(
  'LEMON_MAC_CAMERA_BRIDGE_URL',
);
const Duration _macCameraPreviewPollInterval = Duration(milliseconds: 180);
const int _maxSupplementGalleryImages = 6;

@visibleForTesting
bool shouldUseCameraPickerFallback({
  required bool isEmulator,
  required TargetPlatform platform,
  required bool enableEmulatorLiveCamera,
  required bool hasMacCameraBridge,
  bool? override,
}) {
  if (override != null) {
    return override;
  }
  if (!isEmulator || enableEmulatorLiveCamera) {
    return false;
  }
  if ((platform == TargetPlatform.iOS || platform == TargetPlatform.android) &&
      hasMacCameraBridge) {
    return false;
  }
  return true;
}

// ═══════════════════════════════════════════
// 카메라 화면 UI 톤 — LADS Flat 2.0 + Soft UI.
// 검정 배경 위라 surface/그림자 톤을 별도로 통일.
// ═══════════════════════════════════════════
class _CamTone {
  // 떠있는 컨트롤(버튼·칩) 공통 표면색 — 반투명 검정 + 미세 보더
  static final Color surface = Colors.black.withValues(alpha: 0.42);
  static final Color surfaceStrong = Colors.black.withValues(alpha: 0.55);
  static final Color border = Colors.white.withValues(alpha: 0.14);
  // Soft UI — 떠있는 요소의 부드러운 그림자
  static final List<BoxShadow> softShadow = [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.30),
      blurRadius: 14,
      offset: const Offset(0, 4),
    ),
  ];
}

class CameraScreen extends StatefulWidget {
  /// Creates the source-UI camera screen wired to the real OCR endpoint.
  ///
  /// Args:
  ///   onAnalyzeSupplementImage: Called with the captured or selected image
  ///     path when the user taps the analysis CTA in supplement mode.
  ///   onClose: Optional callback used by the app shell to return home.
  const CameraScreen({
    required this.onAnalyzeSupplementImage,
    this.onAnalyzeSupplementImages,
    this.onAnalyzeMealImage,
    this.initialMode = 'supplement',
    this.initialImageRole = 'unknown',
    this.imagePicker,
    this.useCameraPickerFallback,
    this.debugSupplementImagePath,
    this.macCameraBridgeUrl,
    this.macCameraPreviewFrameOverride,
    this.macCameraCaptureOverride,
    this.isEmulatorOverride,
    this.localPrefs,
    this.showCaptureGuide,
    this.onClose,
    super.key,
  });

  /// Initial capture mode selected from the quick action palette.
  final String initialMode;

  /// Initial supplement image role selected from analysis-result retake actions.
  final String initialImageRole;

  /// Optional image picker override used by widget tests.
  final ImagePicker? imagePicker;

  /// Optional camera picker fallback override used by widget tests.
  final bool? useCameraPickerFallback;

  /// Optional debug-only local image path used when Android Photo Picker stalls.
  final String? debugSupplementImagePath;

  /// Optional debug-only localhost bridge for taking iOS Simulator photos with
  /// the host Mac camera.
  final String? macCameraBridgeUrl;

  /// Optional Mac camera preview-frame override used by widget tests.
  final Future<Uint8List> Function()? macCameraPreviewFrameOverride;

  /// Optional Mac camera capture override used by widget tests.
  final Future<File> Function()? macCameraCaptureOverride;

  /// Optional emulator/simulator classification override used by widget tests.
  final bool? isEmulatorOverride;

  /// Local persistence used for the capture-guide "다시 보지 않기" flag.
  ///
  /// When null the guide modal is skipped (e.g. consent gate not yet ready).
  final LocalPrefs? localPrefs;

  /// Optional override forcing the capture guide modal on/off in widget tests.
  ///
  /// When null the modal visibility is decided by [localPrefs] per mode.
  final bool? showCaptureGuide;

  /// Sends a supplement image to the backend OCR analysis endpoint.
  final Future<void> Function(String imagePath, {required String ocrProvider})
  onAnalyzeSupplementImage;

  /// Sends multiple supplement label images to the backend batch endpoint.
  final Future<void> Function(
    List<SupplementImageUpload> images, {
    required String ocrProvider,
    required bool sameSupplementBatch,
  })?
  onAnalyzeSupplementImages;

  /// Sends a meal image to the backend food analysis endpoint.
  final Future<void> Function(String imagePath)? onAnalyzeMealImage;

  /// Closes the camera screen.
  final VoidCallback? onClose;

  @override
  State<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends State<CameraScreen>
    with WidgetsBindingObserver {
  late _CaptureMode _mode;
  File? _captured;
  final List<_CapturedSupplementImage> _captures = <_CapturedSupplementImage>[];
  bool _picking = false;
  late String _imageRole;
  bool _sameSupplementBatch = true;
  bool _lostDataChecked = false;

  // ─── 카메라 컨트롤러 ───
  CameraController? _controller;
  List<CameraDescription>? _cameras;
  bool _initializing = true;
  String? _initError;
  // 초기화 실패 분류(권한/일반). 권한 거부면 설정 안내 CTA를 노출한다.
  _CameraErrorKind _initErrorKind = _CameraErrorKind.initFailed;
  // 카메라 방향 — 영양제 라벨 촬영은 후면을 우선한다.
  CameraLensDirection _lens = CameraLensDirection.back;
  // 에뮬 여부 — 카메라 영상 정렬 보정용
  bool _isEmulator = false;
  Timer? _macPreviewTimer;
  bool _macPreviewFetching = false;
  Uint8List? _macPreviewFrame;
  int? _macPreviewFrameId;
  String? _macPreviewError;

  // 이번 세션에서 가이드 모달을 이미 띄운 모드(중복 표출 방지).
  final Set<_CaptureMode> _guideShownThisSession = <_CaptureMode>{};

  @override
  void initState() {
    super.initState();
    _mode = widget.initialMode == 'meal'
        ? _CaptureMode.meal
        : _CaptureMode.supplement;
    _imageRole = _normalizeInitialImageRole(widget.initialImageRole);
    WidgetsBinding.instance.addObserver(this);
    _isEmulator = widget.isEmulatorOverride ?? DeviceEnv.isEmulatorSync;
    _startCameraAfterDeviceProbe();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _recoverLostGalleryPick();
      _maybeShowCaptureGuide(_mode);
    });
  }

  // figma 920:23 — 모드별 첫 진입 1회 촬영 가이드 모달.
  // '다시 보지 않기'는 LocalPrefs 로 모드별 즉시 영속(가이드 ④-3 정합).
  String _modeKey(_CaptureMode mode) =>
      mode == _CaptureMode.meal ? 'meal' : 'supplement';

  Future<void> _maybeShowCaptureGuide(_CaptureMode mode) async {
    if (!mounted || _captured != null) return;
    if (_guideShownThisSession.contains(mode)) return;
    final LocalPrefs? prefs = widget.localPrefs;
    final bool forced = widget.showCaptureGuide ?? false;
    // 영속 '다시 보지 않기' 또는 prefs 미주입이면(테스트 강제 제외) 건너뛴다.
    if (!forced) {
      if (prefs == null) return;
      if (prefs.captureGuideDismissed(_modeKey(mode))) return;
    }
    _guideShownThisSession.add(mode);
    final bool isMeal = mode == _CaptureMode.meal;
    final CaptureGuideResult? result = await showCaptureGuideModal(
      context,
      isMeal: isMeal,
    );
    if (result != null && result.dismissedForever) {
      await prefs?.setCaptureGuideDismissed(_modeKey(mode), true);
    }
  }

  @override
  void didUpdateWidget(covariant CameraScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.initialMode != widget.initialMode && _captured == null) {
      _mode = widget.initialMode == 'meal'
          ? _CaptureMode.meal
          : _CaptureMode.supplement;
    }
    if (oldWidget.initialImageRole != widget.initialImageRole &&
        _captured == null &&
        _captures.isEmpty) {
      _imageRole = _normalizeInitialImageRole(widget.initialImageRole);
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _disposeCamera();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused ||
        state == AppLifecycleState.hidden) {
      _disposeCamera();
      if (mounted) {
        setState(() {
          _initializing = false;
          _initError = null;
        });
      }
    } else if (state == AppLifecycleState.resumed) {
      if (mounted && _captured == null) {
        _initCamera();
      }
    }
  }

  bool _initInFlight = false;

  bool get _canUseCameraPickerFallback => shouldUseCameraPickerFallback(
    isEmulator: _isEmulator,
    platform: defaultTargetPlatform,
    enableEmulatorLiveCamera: _enableEmulatorLiveCamera,
    hasMacCameraBridge: _canUseMacCameraBridge,
    override: widget.useCameraPickerFallback,
  );

  String get _debugSupplementImagePath =>
      (widget.debugSupplementImagePath ?? _debugSupplementImagePathFromEnv)
          .trim();

  bool get _canLoadDebugSupplementImage =>
      !kReleaseMode &&
      _mode == _CaptureMode.supplement &&
      _debugSupplementImagePath.isNotEmpty;

  int get _supplementBatchCount =>
      _captures.length + (_captured == null ? 0 : 1);

  int get _remainingSupplementSlots =>
      _maxSupplementGalleryImages - _supplementBatchCount;

  // figma 912:46 미리보기 품질 체크 2종(가이드 ④-4 · ⑥): 업로드 전 소프트 안내.
  // 경로별 결과를 캐시한다(같은 사진 재계산 방지). null = 계산 전/진행 중.
  String? _qualityProbedPath;
  ImageQualityProbeResult? _qualityProbeResult;

  /// 현재 미리보기 이미지의 품질을 비동기로 계산한다(소프트 안내 — 차단 아님).
  ///
  /// 결과가 준비되면 [setState] 로 갱신한다. 디코드 실패 시 조용히 무시한다.
  Future<void> _ensureQualityProbe(File file) async {
    if (_qualityProbedPath == file.path) return;
    _qualityProbedPath = file.path;
    _qualityProbeResult = null;
    try {
      final ImageLumaGrid? grid = await _decodeLumaGrid(file);
      if (!mounted || _qualityProbedPath != file.path || grid == null) return;
      setState(() => _qualityProbeResult = probeImageQuality(grid));
    } on Object {
      // 과한 이미지 분석 금지 — 실패하면 안내를 띄우지 않는다.
    }
  }

  /// 이미지 파일을 [kProbeGridSize] 정사각 휘도 격자로 다운샘플 디코드한다.
  Future<ImageLumaGrid?> _decodeLumaGrid(File file) async {
    final Uint8List bytes = await file.readAsBytes();
    if (bytes.isEmpty) return null;
    final ui.Codec codec = await ui.instantiateImageCodec(
      bytes,
      targetWidth: kProbeGridSize,
      targetHeight: kProbeGridSize,
    );
    final ui.FrameInfo frame = await codec.getNextFrame();
    final ui.Image image = frame.image;
    final ByteData? data = await image.toByteData(
      format: ui.ImageByteFormat.rawRgba,
    );
    image.dispose();
    if (data == null) return null;
    final Uint8List rgba = data.buffer.asUint8List();
    final int width = image.width;
    final int height = image.height;
    final List<int> luma = List<int>.filled(width * height, 0);
    for (int i = 0; i < width * height; i++) {
      final int base = i * 4;
      luma[i] = lumaFromRgb(rgba[base], rgba[base + 1], rgba[base + 2]);
    }
    return ImageLumaGrid(width: width, height: height, luma: luma);
  }

  String get _macCameraBridgeUrl {
    final String configured =
        (widget.macCameraBridgeUrl ?? _macCameraBridgeUrlFromEnv)
            .trim()
            .replaceFirst(RegExp(r'/+$'), '');
    if (configured.isNotEmpty || kReleaseMode || !_isEmulator) {
      return configured;
    }
    return switch (defaultTargetPlatform) {
      TargetPlatform.iOS => 'http://127.0.0.1:8755',
      TargetPlatform.android => 'http://10.0.2.2:8755',
      _ => '',
    };
  }

  bool get _supportsMacCameraBridge =>
      defaultTargetPlatform == TargetPlatform.iOS ||
      defaultTargetPlatform == TargetPlatform.android;

  bool get _canUseMacCameraBridge =>
      !kReleaseMode &&
      _isEmulator &&
      _supportsMacCameraBridge &&
      _macCameraBridgeUrl.isNotEmpty;

  String get _cameraFallbackMessage {
    if (_canUseMacCameraBridge) {
      return 'Mac 카메라 live preview를 연결 중이에요.\nbridge를 켜면 화면이 바로 표시돼요.';
    }
    if (defaultTargetPlatform == TargetPlatform.iOS && _isEmulator) {
      return 'iOS Simulator는 기기 카메라를 직접 보고하지 않을 수 있어요.\nMac camera bridge를 켜거나 갤러리로 OCR을 테스트해주세요.';
    }
    if (defaultTargetPlatform == TargetPlatform.android && _isEmulator) {
      return 'Android Emulator는 Mac 카메라 bridge로 live preview를 볼 수 있어요.\n8755 포트의 bridge를 켜거나 갤러리로 OCR을 테스트해주세요.';
    }
    return '에뮬레이터 live preview는 실행 옵션으로 켜요.\n셔터를 누르면 카메라 앱 촬영으로 열려요.';
  }

  Future<void> _startCameraAfterDeviceProbe() async {
    final bool isEmulator =
        widget.isEmulatorOverride ?? await DeviceEnv.isEmulator;
    if (!mounted) return;
    if (_isEmulator != isEmulator) {
      setState(() => _isEmulator = isEmulator);
    }
    await _initCamera();
  }

  Future<void> _initCamera() async {
    // 동시 진입 방지
    if (_initInFlight) return;
    _initInFlight = true;
    // 이미 살아있으면 스킵
    if (_controller != null && _controller!.value.isInitialized) {
      _initInFlight = false;
      if (mounted && _initializing) {
        setState(() => _initializing = false);
      }
      return;
    }
    if (mounted) {
      setState(() {
        _initializing = true;
        _initError = null;
        _initErrorKind = _CameraErrorKind.initFailed;
      });
    }
    try {
      if (_canUseMacCameraBridge) {
        _startMacCameraPreviewLoop();
        if (mounted) {
          setState(() {
            _initError = null;
            _initializing = false;
          });
        }
        return;
      }
      if (_canUseCameraPickerFallback) {
        if (mounted) {
          setState(() {
            _initError = _cameraFallbackMessage;
            _initializing = false;
          });
        }
        return;
      }
      _cameras ??= await availableCameras();
      if (_cameras == null || _cameras!.isEmpty) {
        if (mounted) {
          setState(() {
            _initError = defaultTargetPlatform == TargetPlatform.iOS
                ? 'iOS Simulator가 카메라를 보고하지 않았어요.\nMac camera bridge를 켜거나 갤러리로 OCR을 테스트해주세요.'
                : '연결된 카메라가 없어요';
            _initializing = false;
          });
        }
        return;
      }
      final cam = _selectCamera(_cameras!);
      final resolution = _isEmulator
          ? ResolutionPreset.low
          : ResolutionPreset.high;
      final controller = CameraController(
        cam,
        resolution,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.jpeg,
      );
      await controller.initialize().timeout(const Duration(seconds: 8));
      if (!mounted) {
        await controller.dispose();
        return;
      }
      setState(() {
        _controller = controller;
        _lens = cam.lensDirection;
        _initializing = false;
        _initError = null;
      });
    } on TimeoutException {
      if (mounted) {
        setState(() {
          _initError = '카메라 응답이 지연되고 있어요.\n갤러리로 OCR을 테스트해주세요.';
          _initializing = false;
        });
      }
    } catch (e) {
      if (mounted) {
        final bool denied = _isPermissionDeniedError(e);
        setState(() {
          _initError = denied
              ? '카메라 권한이 꺼져 있어요.\n설정에서 권한을 켜거나 갤러리로 진행해주세요.'
              : '카메라를 열 수 없어요.\n다시 시도하거나 갤러리로 진행해주세요.';
          _initErrorKind = denied
              ? _CameraErrorKind.permissionDenied
              : _CameraErrorKind.initFailed;
          _initializing = false;
        });
      }
    } finally {
      _initInFlight = false;
    }
  }

  /// 예외가 카메라 권한 거부(설정에서 켜야 하는)인지 판별한다.
  bool _isPermissionDeniedError(Object error) {
    if (error is CameraException) {
      const Set<String> deniedCodes = <String>{
        'CameraAccessDenied',
        'CameraAccessDeniedWithoutPrompt',
        'CameraAccessRestricted',
        'AudioAccessDenied',
        'AudioAccessDeniedWithoutPrompt',
      };
      return deniedCodes.contains(error.code);
    }
    return false;
  }

  Future<void> _disposeCamera() async {
    _stopMacCameraPreviewLoop();
    final c = _controller;
    _controller = null;
    await c?.dispose();
  }

  CameraDescription _selectCamera(List<CameraDescription> cameras) {
    final CameraLensDirection preferredLens = _lens;
    return cameras.firstWhere(
      (CameraDescription c) => c.lensDirection == preferredLens,
      orElse: () => cameras.firstWhere(
        (CameraDescription c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      ),
    );
  }

  Future<void> _shutter() async {
    final c = _controller;
    if (_picking) return;
    if (c == null || !c.value.isInitialized) {
      if (_canUseMacCameraBridge) {
        await _captureFromMacCameraBridge();
        return;
      }
      if (_canUseCameraPickerFallback) {
        await _pickFromCameraApp();
      }
      return;
    }
    setState(() => _picking = true);
    HapticFeedback.mediumImpact();
    try {
      final XFile shot = await c.takePicture();
      if (mounted) {
        setState(() => _captured = File(shot.path));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('촬영을 못 했어요 · ${e.toString()}'),
            backgroundColor: AppColor.danger,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  // 카메라 전후면 토글
  Future<void> _toggleLens() async {
    if (_canUseMacCameraBridge) return;
    HapticFeedback.selectionClick();
    final next = _lens == CameraLensDirection.back
        ? CameraLensDirection.front
        : CameraLensDirection.back;
    // 기존 컨트롤러 정리 후 재초기화
    await _disposeCamera();
    if (!mounted) return;
    setState(() {
      _lens = next;
      _initializing = true;
      _initError = null;
    });
    await _initCamera();
  }

  Future<void> _pickFromGallery() async {
    if (_mode == _CaptureMode.supplement) {
      await _pickSupplementImagesFromGallery();
      return;
    }
    await _pickImageFromPicker(
      source: ImageSource.gallery,
      errorMessage: '갤러리 이미지를 불러오지 못했어요. 다른 사진을 선택해주세요.',
    );
  }

  Future<void> _pickFromCameraApp() async {
    await _pickImageFromPicker(
      source: ImageSource.camera,
      errorMessage: '카메라 앱 촬영 이미지를 불러오지 못했어요. 갤러리로 테스트해주세요.',
    );
  }

  Future<void> _captureFromMacCameraBridge() async {
    if (_picking || !_canUseMacCameraBridge) return;
    setState(() => _picking = true);
    HapticFeedback.mediumImpact();
    final Uint8List? previewFrame = _macPreviewFrame;
    if (previewFrame != null && previewFrame.isNotEmpty) {
      try {
        final File captured = _writeCapturedBytes(
          previewFrame,
          extension: '.jpg',
        );
        if (mounted) {
          setState(() => _captured = captured);
        }
        return;
      } catch (_) {
        // Fall through to the bridge capture endpoint if the cached frame
        // cannot be materialized.
      } finally {
        if (mounted) setState(() => _picking = false);
      }
    }
    final Future<File> Function()? captureOverride =
        widget.macCameraCaptureOverride;
    if (captureOverride != null) {
      try {
        final File captured = await captureOverride();
        if (!captured.existsSync() || captured.lengthSync() == 0) {
          throw const FormatException('empty mac camera capture override');
        }
        if (mounted) {
          setState(() => _captured = captured);
        }
      } catch (_) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Mac 카메라 촬영에 실패했어요. bridge 실행 상태와 카메라 권한을 확인해주세요.'),
              backgroundColor: AppColor.danger,
            ),
          );
        }
      } finally {
        if (mounted) setState(() => _picking = false);
      }
      return;
    }
    final HttpClient client = HttpClient()
      ..connectionTimeout = const Duration(seconds: 3);
    try {
      final Uri captureUri = Uri.parse('$_macCameraBridgeUrl/capture');
      final HttpClientRequest request = await client
          .getUrl(captureUri)
          .timeout(const Duration(seconds: 3));
      request.headers.set(
        HttpHeaders.acceptHeader,
        'image/jpeg,image/png;q=0.9',
      );
      final HttpClientResponse response = await request.close().timeout(
        const Duration(seconds: 12),
      );
      final ContentType? contentType = response.headers.contentType;
      final Uint8List bytes = await consolidateHttpClientResponseBytes(
        response,
      );
      if (response.statusCode != HttpStatus.ok || bytes.isEmpty) {
        throw const FormatException('empty mac camera capture');
      }
      final File captured = _writeCapturedBytes(
        bytes,
        extension: _extensionForContentType(contentType),
      );
      if (mounted) {
        setState(() => _captured = captured);
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Mac 카메라 촬영에 실패했어요. bridge 실행 상태와 카메라 권한을 확인해주세요.'),
            backgroundColor: AppColor.danger,
          ),
        );
      }
    } finally {
      client.close(force: true);
      if (mounted) setState(() => _picking = false);
    }
  }

  Future<void> _loadDebugSupplementImage() async {
    if (_picking || !_canLoadDebugSupplementImage) return;
    setState(() => _picking = true);
    HapticFeedback.lightImpact();
    try {
      final File sourceFile = File(_debugSupplementImagePath);
      if (!sourceFile.existsSync() || sourceFile.lengthSync() == 0) {
        throw const FormatException('debug image unavailable');
      }
      final File cached = await _copyPickedImageToCache(
        XFile(
          sourceFile.path,
          name: sourceFile.uri.pathSegments.isNotEmpty
              ? sourceFile.uri.pathSegments.last
              : 'debug-supplement.jpg',
        ),
      );
      if (mounted) {
        setState(() => _captured = cached);
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('디버그 샘플 이미지를 불러오지 못했어요. 경로와 권한을 확인해주세요.'),
            backgroundColor: AppColor.danger,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  Future<void> _pickSupplementImagesFromGallery() async {
    if (_picking) return;
    final int remainingSlots = _maxSupplementGalleryImages - _captures.length;
    if (remainingSlots <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('영양제 라벨 사진은 최대 6장까지 선택할 수 있어요.'),
          backgroundColor: AppColor.ink,
        ),
      );
      return;
    }
    setState(() => _picking = true);
    HapticFeedback.lightImpact();
    bool truncatedSelection = false;
    final String currentImageRole = _imageRole;
    try {
      final picker = widget.imagePicker ?? ImagePicker();
      final List<XFile> files = await picker.pickMultiImage(
        maxWidth: 2400,
        imageQuality: 95,
        limit: remainingSlots,
        requestFullMetadata: false,
      );
      if (files.isEmpty || !mounted) return;
      final List<XFile> selectedFiles = files.length > remainingSlots
          ? files.take(remainingSlots).toList(growable: false)
          : files;
      truncatedSelection = files.length > selectedFiles.length;
      final List<File> cachedFiles = await _copyPickedImagesToCache(
        selectedFiles,
      );
      if (cachedFiles.isEmpty || !mounted) return;
      _setSupplementGallerySelection(cachedFiles, currentImageRole);
      if (truncatedSelection && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('한 번에 분석할 수 있는 사진은 최대 6장이라 나머지는 제외했어요.'),
            backgroundColor: AppColor.ink,
          ),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('갤러리 이미지를 불러오지 못했어요. 다른 사진을 선택해주세요.'),
            backgroundColor: AppColor.danger,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  Future<void> _pickImageFromPicker({
    required ImageSource source,
    required String errorMessage,
  }) async {
    if (_picking) return;
    setState(() => _picking = true);
    HapticFeedback.lightImpact();
    try {
      final picker = widget.imagePicker ?? ImagePicker();
      final XFile? file = await picker.pickImage(
        source: source,
        maxWidth: 2400,
        imageQuality: 95,
        preferredCameraDevice: CameraDevice.rear,
        requestFullMetadata: false,
      );
      if (file != null && mounted) {
        final File cached = await _copyPickedImageToCache(file);
        if (mounted) {
          setState(() => _captured = cached);
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(errorMessage),
            backgroundColor: AppColor.danger,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  Future<void> _recoverLostGalleryPick() async {
    if (_lostDataChecked) return;
    _lostDataChecked = true;
    if (defaultTargetPlatform != TargetPlatform.android) {
      return;
    }
    try {
      final LostDataResponse response =
          await (widget.imagePicker ?? ImagePicker()).retrieveLostData();
      final List<XFile>? files = response.files;
      final List<XFile> recoveredFiles = files != null && files.isNotEmpty
          ? files
          : response.file == null
          ? const <XFile>[]
          : <XFile>[response.file!];
      if (!mounted || response.isEmpty || recoveredFiles.isEmpty) return;
      if (_mode == _CaptureMode.supplement) {
        final int remainingSlots =
            _maxSupplementGalleryImages - _captures.length;
        if (remainingSlots <= 0) return;
        final List<File> cachedFiles = await _copyPickedImagesToCache(
          recoveredFiles.take(remainingSlots),
        );
        if (mounted && _captured == null && cachedFiles.isNotEmpty) {
          _setSupplementGallerySelection(cachedFiles, _imageRole);
        }
        return;
      }
      final File cached = await _copyPickedImageToCache(recoveredFiles.first);
      if (mounted && _captured == null) {
        setState(() => _captured = cached);
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('이전 갤러리 선택을 복구하지 못했어요. 다시 선택해주세요.'),
            backgroundColor: AppColor.ink,
          ),
        );
      }
    }
  }

  Future<List<File>> _copyPickedImagesToCache(Iterable<XFile> files) async {
    final List<File> cachedFiles = <File>[];
    for (final XFile file in files) {
      cachedFiles.add(await _copyPickedImageToCache(file));
    }
    return cachedFiles;
  }

  void _setSupplementGallerySelection(
    List<File> cachedFiles,
    String currentImageRole,
  ) {
    if (cachedFiles.isEmpty || !mounted) return;
    setState(() {
      for (final File file in cachedFiles.take(cachedFiles.length - 1)) {
        _captures.add(
          _CapturedSupplementImage(file: file, role: _nextImageRole()),
        );
      }
      _captured = cachedFiles.last;
      _imageRole = currentImageRole;
    });
  }

  Future<File> _copyPickedImageToCache(XFile file) async {
    Uint8List? bytes;
    if (file.path.isNotEmpty) {
      final File sourceFile = File(file.path);
      if (sourceFile.existsSync() && sourceFile.lengthSync() > 0) {
        bytes = sourceFile.readAsBytesSync();
      }
    }
    bytes ??= await file.readAsBytes();
    if (bytes.isEmpty) {
      throw const FormatException('empty image');
    }
    final String extension = _imageExtension(file.name).isNotEmpty
        ? _imageExtension(file.name)
        : _imageExtension(file.path);
    final String safeExtension = extension.isEmpty ? '.jpg' : extension;
    final String outputPath =
        '${Directory.systemTemp.path}/lemon_aid_ocr_${DateTime.now().microsecondsSinceEpoch}$safeExtension';
    final File output = File(outputPath);
    output.writeAsBytesSync(bytes, flush: true);
    final int copiedLength = output.lengthSync();
    if (copiedLength == 0) {
      throw const FormatException('empty copied image');
    }
    return output;
  }

  File _writeCapturedBytes(Uint8List bytes, {required String extension}) {
    final String outputPath =
        '${Directory.systemTemp.path}/lemon_aid_ocr_${DateTime.now().microsecondsSinceEpoch}$extension';
    final File output = File(outputPath);
    output.writeAsBytesSync(bytes, flush: true);
    if (output.lengthSync() == 0) {
      throw const FormatException('empty captured image');
    }
    return output;
  }

  void _startMacCameraPreviewLoop() {
    if (_macPreviewTimer != null || !_canUseMacCameraBridge) return;
    _macPreviewError = null;
    _scheduleMacCameraPreviewFetch(Duration.zero);
  }

  void _stopMacCameraPreviewLoop() {
    _macPreviewTimer?.cancel();
    _macPreviewTimer = null;
    _macPreviewFetching = false;
  }

  void _scheduleMacCameraPreviewFetch(Duration delay) {
    _macPreviewTimer?.cancel();
    _macPreviewTimer = Timer(delay, () {
      _macPreviewTimer = null;
      if (!_canUseMacCameraBridge || _captured != null) return;
      unawaited(_fetchMacCameraPreviewFrame());
    });
  }

  Future<void> _fetchMacCameraPreviewFrame() async {
    if (_macPreviewFetching || !_canUseMacCameraBridge || _captured != null) {
      return;
    }
    _macPreviewFetching = true;
    bool shouldContinuePreview = false;
    try {
      final Future<Uint8List> Function()? previewOverride =
          widget.macCameraPreviewFrameOverride;
      final Uint8List bytes;
      int? nextFrameId;
      if (previewOverride != null) {
        bytes = await previewOverride();
      } else {
        final HttpClient client = HttpClient()
          ..connectionTimeout = const Duration(seconds: 2);
        try {
          final Map<String, String> query = <String, String>{
            't': DateTime.now().microsecondsSinceEpoch.toString(),
            if (_macPreviewFrameId != null)
              'after': _macPreviewFrameId.toString(),
          };
          final Uri frameUri = Uri.parse(
            '$_macCameraBridgeUrl/frame.jpg',
          ).replace(queryParameters: query);
          final HttpClientRequest request = await client
              .getUrl(frameUri)
              .timeout(const Duration(seconds: 2));
          request.headers.set(HttpHeaders.acceptHeader, 'image/jpeg');
          request.headers.set(HttpHeaders.cacheControlHeader, 'no-cache');
          final HttpClientResponse response = await request.close().timeout(
            const Duration(seconds: 5),
          );
          bytes = await consolidateHttpClientResponseBytes(response);
          nextFrameId = int.tryParse(
            response.headers.value('x-lemon-frame-id') ?? '',
          );
          if (response.statusCode != HttpStatus.ok || bytes.isEmpty) {
            throw const FormatException('empty mac camera preview');
          }
        } finally {
          client.close(force: true);
        }
      }
      if (!mounted || bytes.isEmpty) return;
      setState(() {
        _macPreviewFrame = bytes;
        _macPreviewFrameId = nextFrameId ?? _macPreviewFrameId;
        _macPreviewError = null;
      });
      shouldContinuePreview = true;
    } catch (error) {
      if (mounted) {
        setState(() {
          _macPreviewFrameId = null;
          _macPreviewError = _macCameraPreviewErrorMessage(error);
        });
      }
      shouldContinuePreview = true;
    } finally {
      _macPreviewFetching = false;
      if (mounted &&
          shouldContinuePreview &&
          _canUseMacCameraBridge &&
          _captured == null) {
        _scheduleMacCameraPreviewFetch(_macCameraPreviewPollInterval);
      }
    }
  }

  String _macCameraPreviewErrorMessage(Object error) {
    if (error is SocketException) {
      return 'Mac camera bridge에 연결할 수 없어요.\n8755 포트의 bridge 실행 상태를 확인해주세요.';
    }
    if (error is TimeoutException) {
      return 'Mac 카메라 프리뷰 응답이 지연되고 있어요.\nbridge와 카메라 권한을 확인해주세요.';
    }
    return 'Mac 카메라 프리뷰 연결 중이에요.\n성분표가 보이도록 카메라를 준비해주세요.';
  }

  String _extensionForContentType(ContentType? contentType) {
    return switch (contentType?.mimeType.toLowerCase()) {
      'image/png' => '.png',
      'image/webp' => '.webp',
      _ => '.jpg',
    };
  }

  String _imageExtension(String value) {
    final String lower = value.toLowerCase();
    for (final String extension in <String>[
      '.jpg',
      '.jpeg',
      '.png',
      '.webp',
      '.heic',
    ]) {
      if (lower.endsWith(extension)) {
        return extension == '.jpeg' ? '.jpg' : extension;
      }
    }
    return '';
  }

  void _retake() {
    HapticFeedback.selectionClick();
    setState(() => _captured = null);
    if (_canUseMacCameraBridge) {
      _startMacCameraPreviewLoop();
    }
  }

  void _addCurrentToBatch() {
    final File? captured = _captured;
    if (captured == null || _mode != _CaptureMode.supplement) return;
    if (_captures.length >= _maxSupplementGalleryImages - 1) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('영양제 라벨 사진은 최대 6장까지 분석할 수 있어요.'),
          backgroundColor: AppColor.ink,
        ),
      );
      return;
    }
    HapticFeedback.selectionClick();
    setState(() {
      _captures.add(_CapturedSupplementImage(file: captured, role: _imageRole));
      _captured = null;
      _imageRole = _nextImageRole();
    });
    if (_canUseMacCameraBridge) {
      _startMacCameraPreviewLoop();
    }
  }

  Future<void> _addGalleryImagesToBatch() async {
    final File? captured = _captured;
    if (captured == null || _mode != _CaptureMode.supplement || _picking) {
      return;
    }
    final int remainingSlots = _remainingSupplementSlots;
    if (remainingSlots <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('영양제 라벨 사진은 최대 6장까지 분석할 수 있어요.'),
          backgroundColor: AppColor.ink,
        ),
      );
      return;
    }
    setState(() => _picking = true);
    HapticFeedback.lightImpact();
    bool truncatedSelection = false;
    try {
      final picker = widget.imagePicker ?? ImagePicker();
      final List<XFile> files = await picker.pickMultiImage(
        maxWidth: 2400,
        imageQuality: 95,
        limit: remainingSlots,
        requestFullMetadata: false,
      );
      if (files.isEmpty || !mounted) return;
      final List<XFile> selectedFiles = files.length > remainingSlots
          ? files.take(remainingSlots).toList(growable: false)
          : files;
      truncatedSelection = files.length > selectedFiles.length;
      final List<File> cachedFiles = await _copyPickedImagesToCache(
        selectedFiles,
      );
      if (cachedFiles.isEmpty || !mounted) return;
      setState(() {
        for (final File file in cachedFiles) {
          _captures.add(
            _CapturedSupplementImage(file: file, role: _nextImageRole()),
          );
        }
      });
      if (truncatedSelection && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('한 번에 분석할 수 있는 사진은 최대 6장이라 나머지는 제외했어요.'),
            backgroundColor: AppColor.ink,
          ),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('갤러리 이미지를 불러오지 못했어요. 다른 사진을 선택해주세요.'),
            backgroundColor: AppColor.danger,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  void _removeBatchImage(int index) {
    if (index < 0 || index >= _captures.length) return;
    HapticFeedback.selectionClick();
    setState(() {
      _captures.removeAt(index);
      if (_captured == null) {
        _imageRole = _nextImageRole();
      }
    });
  }

  String _nextImageRole() {
    return 'unknown';
  }

  List<SupplementImageUpload> _analysisUploads(File current) {
    return <SupplementImageUpload>[
      for (final _CapturedSupplementImage image in _captures) image.toUpload(),
      SupplementImageUpload(path: current.path, role: _imageRole),
    ];
  }

  Future<void> _analyze() async {
    final File? captured = _captured;
    if (captured == null || _picking) return;
    if (!await captured.exists() || await captured.length() == 0) {
      if (mounted) {
        // Clear the stale preview so the user returns to the capture view
        // instead of being stuck on a missing/empty image.
        setState(() => _captured = null);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('선택한 이미지 파일이 비어 있어요. 다시 촬영하거나 선택해주세요.'),
            backgroundColor: AppColor.danger,
          ),
        );
      }
      return;
    }
    if (!mounted) return;
    HapticFeedback.mediumImpact();
    if (_mode == _CaptureMode.meal) {
      final Future<void> Function(String imagePath)? analyzer =
          widget.onAnalyzeMealImage;
      if (analyzer == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('식단 분석 연결을 확인해주세요. 갤러리 사진은 유지됩니다.'),
            backgroundColor: AppColor.ink,
          ),
        );
        return;
      }
      setState(() => _picking = true);
      try {
        await analyzer(captured.path);
      } finally {
        if (mounted) setState(() => _picking = false);
      }
      return;
    }
    setState(() => _picking = true);
    try {
      final List<SupplementImageUpload> uploads = _analysisUploads(captured);
      final bool shouldUseRoleAwareUpload =
          widget.onAnalyzeSupplementImages != null &&
          (uploads.length > 1 ||
              (_imageRole != 'unknown' && _imageRole != 'front_label'));
      if (shouldUseRoleAwareUpload) {
        await widget.onAnalyzeSupplementImages!(
          uploads,
          ocrProvider: 'configured',
          sameSupplementBatch: _sameSupplementBatch,
        );
      } else {
        await widget.onAnalyzeSupplementImage(
          captured.path,
          ocrProvider: 'configured',
        );
      }
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    // 화면 재진입 시 컨트롤러 죽어있으면 다시 켜기
    if (_captured == null &&
        !_canUseMacCameraBridge &&
        !_initializing &&
        _initError == null &&
        (_controller == null || !_controller!.value.isInitialized)) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _initCamera();
      });
    }
    // 시스템 바 스타일 명시 — 카메라 화면은 검정 풀스크린.
    // (안드로이드 에뮬이 카메라 인디케이터를 테두리로 잘못 그리는 현상 완화)
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.light,
        statusBarBrightness: Brightness.dark,
        systemNavigationBarColor: Colors.black,
        systemNavigationBarIconBrightness: Brightness.light,
        systemNavigationBarContrastEnforced: false,
      ),
      child: Scaffold(
        backgroundColor: Colors.black,
        // 풀스크린 — body 가 화면 끝까지. SafeArea 는 컨트롤 위젯 안에서 처리.
        // 촬영 ↔ 미리보기 전환은 페이드 + 미세 스케일 (토스 톤 — "딱" 안 바뀜)
        body: AnimatedSwitcher(
          duration: const Duration(milliseconds: 320),
          switchInCurve: Curves.easeOutQuart,
          switchOutCurve: Curves.easeInQuart,
          transitionBuilder: (child, anim) {
            return FadeTransition(
              opacity: anim,
              child: ScaleTransition(
                scale: Tween<double>(begin: 1.03, end: 1.0).animate(anim),
                child: child,
              ),
            );
          },
          child: _captured == null
              ? KeyedSubtree(
                  key: const ValueKey('capture'),
                  child: _buildCapture(),
                )
              : KeyedSubtree(
                  key: const ValueKey('preview'),
                  child: _buildPreview(),
                ),
        ),
      ),
    );
  }

  // ─── 촬영 화면 (가이드 프레임 안에 라이브 프리뷰) ───
  Widget _buildCapture() {
    return Stack(
      fit: StackFit.expand,
      children: [
        _FullScreenPreview(
          controller: _controller,
          initializing: _initializing,
          error: _initError,
          errorKind: _initErrorKind,
          onRetry: _initCamera,
          onGallery: _pickFromGallery,
          isFront: _lens == CameraLensDirection.front,
          isEmulator: _isEmulator,
          macPreviewFrame: _macPreviewFrame,
          macPreviewActive: _canUseMacCameraBridge,
          macPreviewMessage: _macPreviewError ?? _cameraFallbackMessage,
        ),
        _GuideOverlay(mode: _mode),
        Positioned(
          top: 0,
          left: 0,
          right: 0,
          child: SafeArea(
            bottom: false,
            child: _TopBar(
              mode: _mode,
              onClose:
                  widget.onClose ??
                  () => context.canPop()
                      ? context.pop()
                      : context.go('/shell/home'),
              onFlip: _canUseMacCameraBridge ? null : _toggleLens,
              isFront: _lens == CameraLensDirection.front,
            ),
          ),
        ),
        Positioned(
          left: 0,
          right: 0,
          bottom: 0,
          child: SafeArea(
            top: false,
            child: _BottomControls(
              mode: _mode,
              onModeChange: (m) {
                HapticFeedback.selectionClick();
                setState(() => _mode = m);
                _maybeShowCaptureGuide(m);
              },
              onShutter: _shutter,
              onGallery: _pickFromGallery,
              onDebugSupplementImage: _canLoadDebugSupplementImage
                  ? _loadDebugSupplementImage
                  : null,
              loading: _picking,
              enabled:
                  _controller?.value.isInitialized == true ||
                  _canUseMacCameraBridge ||
                  _canUseCameraPickerFallback,
              // 영양제 모드에만 묶음 의도 토글. 식단 모드는 null.
              supplementBatchStrip: _mode == _CaptureMode.supplement
                  ? _SupplementBatchIntentToggle(
                      sameSupplementBatch: _sameSupplementBatch,
                      onChanged: (bool value) {
                        HapticFeedback.selectionClick();
                        setState(() => _sameSupplementBatch = value);
                      },
                    )
                  : null,
            ),
          ),
        ),
      ],
    );
  }

  // ─── 미리보기 (촬영 후) ───
  Widget _buildPreview() {
    final File? captured = _captured;
    if (captured != null) {
      // 업로드 전 품질 휴리스틱을 비동기로 계산(소프트 안내 — 차단 아님).
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _ensureQualityProbe(captured);
      });
    }
    return SafeArea(
      child: Column(
        children: [
          _TopBar(
            mode: _mode,
            title: '미리보기',
            onClose: _retake,
            closeIcon: Icons.arrow_back_rounded,
          ),
          const SizedBox(height: AppSpace.md),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpace.page),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(AppRadius.lg),
                child: Image.file(
                  _captured!,
                  fit: BoxFit.cover,
                  width: double.infinity,
                  errorBuilder: (context, error, stackTrace) {
                    return Container(
                      color: AppColor.ink,
                      alignment: Alignment.center,
                      padding: const EdgeInsets.all(AppSpace.lg),
                      child: const Text(
                        '이미지 미리보기를 열 수 없어요.\n다시 촬영하거나 다른 사진을 선택해주세요.',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          height: 1.45,
                        ),
                      ),
                    );
                  },
                ),
              ),
            ),
          ),
          const SizedBox(height: AppSpace.md),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpace.page),
            child: _PreviewQualityChecks(result: _qualityProbeResult),
          ),
          if (_mode == _CaptureMode.supplement) ...[
            const SizedBox(height: AppSpace.md),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpace.page),
              child: _SupplementBatchIntentToggle(
                sameSupplementBatch: _sameSupplementBatch,
                onChanged: (bool value) {
                  HapticFeedback.selectionClick();
                  setState(() => _sameSupplementBatch = value);
                },
              ),
            ),
            const SizedBox(height: AppSpace.sm),
            _SupplementBatchStrip(
              captures: _captures,
              onRemove: _removeBatchImage,
            ),
            const SizedBox(height: AppSpace.sm),
            const _AutoAnalysisBadge(),
          ],
          const SizedBox(height: AppSpace.md),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpace.page),
            child: _mode == _CaptureMode.supplement
                ? Column(
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: _GhostButton(
                              label: '다시 촬영',
                              icon: Icons.refresh_rounded,
                              onTap: _retake,
                            ),
                          ),
                          const SizedBox(width: AppSpace.sm),
                          Expanded(
                            child: _GhostButton(
                              label: '계속 촬영',
                              icon: Icons.add_a_photo_rounded,
                              onTap: _addCurrentToBatch,
                            ),
                          ),
                          const SizedBox(width: AppSpace.sm),
                          Expanded(
                            child: _GhostButton(
                              label: '여러 장 추가',
                              icon: Icons.add_photo_alternate_rounded,
                              onTap: _addGalleryImagesToBatch,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpace.sm),
                      _PrimaryButton(
                        key: const ValueKey('supplement-preview-analyze'),
                        label: _picking
                            ? '분석 중'
                            : _captures.isEmpty
                            ? '분석하기'
                            : '${_captures.length + 1}장 분석',
                        onTap: _analyze,
                      ),
                    ],
                  )
                : Row(
                    children: [
                      Expanded(
                        child: _GhostButton(
                          label: '다시 촬영',
                          icon: Icons.refresh_rounded,
                          onTap: _retake,
                        ),
                      ),
                      const SizedBox(width: AppSpace.sm),
                      Expanded(
                        flex: 2,
                        child: _PrimaryButton(
                          key: const ValueKey('supplement-preview-analyze'),
                          label: _picking ? '분석 중' : '분석하기',
                          onTap: _analyze,
                        ),
                      ),
                    ],
                  ),
          ),
          const SizedBox(height: AppSpace.md),
        ],
      ),
    );
  }
}

String _normalizeInitialImageRole(String value) {
  const Set<String> allowedRoles = <String>{
    'unknown',
    'front_label',
    'supplement_facts',
    'intake_method',
    'precautions',
  };
  final String normalized = value.trim();
  return allowedRoles.contains(normalized) ? normalized : 'unknown';
}

class _SupplementBatchStrip extends StatelessWidget {
  const _SupplementBatchStrip({required this.captures, required this.onRemove});

  final List<_CapturedSupplementImage> captures;
  final ValueChanged<int> onRemove;

  @override
  Widget build(BuildContext context) {
    final int totalCount = captures.length + 1;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpace.page),
      child: SizedBox(
        height: 74,
        child: Row(
          children: [
            _BatchCountBadge(count: totalCount),
            const SizedBox(width: AppSpace.sm),
            Expanded(
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: captures.length + 1,
                separatorBuilder: (context, index) =>
                    const SizedBox(width: AppSpace.sm),
                itemBuilder: (context, index) {
                  if (index == captures.length) {
                    return _BatchImageChip(
                      label: '현재 사진',
                      selected: true,
                      onRemove: null,
                    );
                  }
                  final _CapturedSupplementImage image = captures[index];
                  return _BatchImageChip(
                    label: '추가 사진 ${index + 1}',
                    file: image.file,
                    selected: false,
                    onRemove: () => onRemove(index),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BatchCountBadge extends StatelessWidget {
  const _BatchCountBadge({required this.count});

  final int count;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 62,
      height: 62,
      decoration: BoxDecoration(
        color: _CamTone.surfaceStrong,
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(color: _CamTone.border),
      ),
      alignment: Alignment.center,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.collections_rounded, color: AppColor.brand, size: 18),
          const SizedBox(height: 3),
          Text(
            '$count장',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 13,
              fontWeight: FontWeight.w800,
              letterSpacing: 0,
            ),
          ),
        ],
      ),
    );
  }
}

class _BatchImageChip extends StatelessWidget {
  const _BatchImageChip({
    required this.label,
    required this.selected,
    this.file,
    this.onRemove,
  });

  final String label;
  final bool selected;
  final File? file;
  final VoidCallback? onRemove;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 96,
      height: 62,
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: selected
              ? AppColor.brand.withValues(alpha: 0.18)
              : _CamTone.surface,
          borderRadius: BorderRadius.circular(AppRadius.md),
          border: Border.all(
            color: selected ? AppColor.brand : _CamTone.border,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Stack(
          children: [
            if (file != null)
              Positioned.fill(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(AppRadius.md),
                  child: Image.file(file!, fit: BoxFit.cover),
                ),
              ),
            Positioned.fill(
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: Colors.black.withValues(
                    alpha: file == null ? 0.0 : 0.42,
                  ),
                  borderRadius: BorderRadius.circular(AppRadius.md),
                ),
              ),
            ),
            Align(
              alignment: Alignment.center,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 6),
                child: Text(
                  label,
                  maxLines: 2,
                  textAlign: TextAlign.center,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0,
                  ),
                ),
              ),
            ),
            if (onRemove != null)
              Positioned(
                top: 3,
                right: 3,
                child: GestureDetector(
                  onTap: onRemove,
                  child: Container(
                    width: 22,
                    height: 22,
                    decoration: BoxDecoration(
                      color: Colors.black.withValues(alpha: 0.62),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.close_rounded,
                      color: Colors.white,
                      size: 15,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _AutoAnalysisBadge extends StatelessWidget {
  const _AutoAnalysisBadge();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpace.page),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpace.md,
          vertical: AppSpace.sm,
        ),
        decoration: BoxDecoration(
          color: _CamTone.surfaceStrong,
          borderRadius: BorderRadius.circular(AppRadius.full),
          border: Border.all(color: _CamTone.border),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: <Widget>[
            Icon(Icons.auto_awesome_rounded, color: AppColor.brand, size: 18),
            const SizedBox(width: AppSpace.xs),
            const Text(
              '자동 분석',
              style: TextStyle(
                color: Colors.white,
                fontSize: 13,
                fontWeight: FontWeight.w900,
                letterSpacing: 0,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 미리보기 품질 체크 2종 (figma 912:46) — 소프트 안내(차단 아님)
// ═══════════════════════════════════════════
class _PreviewQualityChecks extends StatelessWidget {
  const _PreviewQualityChecks({required this.result});

  /// 품질 휴리스틱 결과. null 이면 계산 중(확인 중 표시).
  final ImageQualityProbeResult? result;

  @override
  Widget build(BuildContext context) {
    final ImageQualityProbeResult? r = result;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpace.md,
        vertical: AppSpace.sm + 2,
      ),
      decoration: BoxDecoration(
        color: _CamTone.surfaceStrong,
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(color: _CamTone.border),
      ),
      child: Column(
        children: <Widget>[
          _PreviewQualityRow(
            label: '선명도',
            okText: '또렷해요',
            failText: '흐릿해요 · 다시 찍기를 권해요',
            passed: r?.sharpness.passed,
          ),
          const SizedBox(height: 6),
          _PreviewQualityRow(
            label: '밝기',
            okText: '적당해요',
            failText: '어두워요 · 다시 찍기를 권해요',
            passed: r?.brightness.passed,
          ),
        ],
      ),
    );
  }
}

class _PreviewQualityRow extends StatelessWidget {
  const _PreviewQualityRow({
    required this.label,
    required this.okText,
    required this.failText,
    required this.passed,
  });

  final String label;
  final String okText;
  final String failText;

  /// null = 확인 중, true = 통과, false = 미달.
  final bool? passed;

  @override
  Widget build(BuildContext context) {
    final bool checking = passed == null;
    final bool ok = passed == true;
    final IconData icon = checking
        ? Icons.hourglass_empty_rounded
        : ok
        ? Icons.check_circle_rounded
        : Icons.warning_amber_rounded;
    final Color tone = checking
        ? Colors.white.withValues(alpha: 0.6)
        : ok
        ? AppColor.success
        : AppColor.warning;
    final String message = checking
        ? '확인 중이에요'
        : ok
        ? okText
        : failText;
    return Row(
      children: <Widget>[
        Icon(icon, size: 18, color: tone),
        const SizedBox(width: AppSpace.sm),
        SizedBox(
          width: 52,
          child: Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 13,
              fontWeight: FontWeight.w800,
              letterSpacing: 0,
            ),
          ),
        ),
        Expanded(
          child: Text(
            message,
            style: TextStyle(
              color: tone,
              fontSize: 13,
              fontWeight: FontWeight.w700,
              letterSpacing: 0,
            ),
          ),
        ),
      ],
    );
  }
}

// ═══════════════════════════════════════════
// 상단 바
// ═══════════════════════════════════════════
class _TopBar extends StatelessWidget {
  final _CaptureMode mode;
  final VoidCallback onClose;
  final String? title;
  final IconData closeIcon;
  final VoidCallback? onFlip;
  final bool isFront;
  const _TopBar({
    required this.mode,
    required this.onClose,
    this.title,
    this.closeIcon = Icons.close_rounded,
    this.onFlip,
    this.isFront = false,
  });

  @override
  Widget build(BuildContext context) {
    final modeLabel = mode == _CaptureMode.supplement ? '영양제' : '식단';
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpace.page,
        AppSpace.md,
        AppSpace.page,
        0,
      ),
      child: Row(
        children: [
          _RoundIcon(icon: closeIcon, onTap: onClose),
          const Spacer(),
          // 제목 — 모드 바뀔 때 부드럽게 전환
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 220),
            child: Text(
              title ?? '$modeLabel 촬영',
              key: ValueKey(title ?? modeLabel),
              style: const TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.w700,
                letterSpacing: 0,
              ),
            ),
          ),
          const Spacer(),
          // 우측: 카메라 전환 버튼 (회전 아이콘 고정)
          if (onFlip != null)
            _RoundIcon(icon: Icons.cameraswitch_rounded, onTap: onFlip!)
          else
            const SizedBox(width: 44, height: 44),
        ],
      ),
    );
  }
}

// 상단 원형 아이콘 버튼 — 글래스 톤 + press 피드백 (LADS / 애플 카메라 톤)
class _RoundIcon extends StatefulWidget {
  final IconData icon;
  final VoidCallback onTap;
  const _RoundIcon({required this.icon, required this.onTap});

  @override
  State<_RoundIcon> createState() => _RoundIconState();
}

class _RoundIconState extends State<_RoundIcon> {
  bool _pressed = false;

  void _set(bool v) {
    if (_pressed != v) setState(() => _pressed = v);
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        HapticFeedback.lightImpact();
        widget.onTap();
      },
      onTapDown: (_) => _set(true),
      onTapUp: (_) => _set(false),
      onTapCancel: () => _set(false),
      child: AnimatedScale(
        scale: _pressed ? 0.90 : 1.0,
        duration: const Duration(milliseconds: 150),
        curve: Curves.easeOutCubic,
        child: Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: _CamTone.surface,
            shape: BoxShape.circle,
            border: Border.all(color: _CamTone.border, width: 1),
            boxShadow: _CamTone.softShadow,
          ),
          alignment: Alignment.center,
          child: Icon(widget.icon, color: Colors.white, size: 21),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 풀스크린 라이브 프리뷰
//   - 화면 전체에 카메라 영상을 cover 로 깐다
//   - 비율 계산 없이 FittedBox 정중앙 cover
// ═══════════════════════════════════════════
class _FullScreenPreview extends StatelessWidget {
  final CameraController? controller;
  final bool initializing;
  final String? error;
  final _CameraErrorKind errorKind;
  final VoidCallback? onRetry;
  final VoidCallback? onGallery;
  final bool isFront;
  final bool isEmulator;
  final Uint8List? macPreviewFrame;
  final bool macPreviewActive;
  final String? macPreviewMessage;
  const _FullScreenPreview({
    required this.controller,
    required this.initializing,
    required this.error,
    this.errorKind = _CameraErrorKind.initFailed,
    this.onRetry,
    this.onGallery,
    this.isFront = false,
    this.isEmulator = false,
    this.macPreviewFrame,
    this.macPreviewActive = false,
    this.macPreviewMessage,
  });

  @override
  Widget build(BuildContext context) {
    if (macPreviewActive) {
      final Uint8List? frame = macPreviewFrame;
      if (frame == null) {
        return Container(
          color: Colors.black,
          alignment: Alignment.center,
          child: _SpinnerWithLabel(
            label: macPreviewMessage ?? 'Mac 카메라 프리뷰 연결 중이에요',
          ),
        );
      }
      return ClipRect(
        child: SizedBox.expand(
          child: Image.memory(
            frame,
            fit: BoxFit.cover,
            filterQuality: FilterQuality.low,
            gaplessPlayback: true,
            semanticLabel: 'Mac 카메라 실시간 프리뷰',
            errorBuilder: (context, error, stackTrace) {
              return Container(
                color: Colors.black,
                alignment: Alignment.center,
                child: _SpinnerWithLabel(
                  label: macPreviewMessage ?? 'Mac 카메라 프리뷰 연결 중이에요',
                ),
              );
            },
          ),
        ),
      );
    }
    if (initializing) {
      return Container(
        color: Colors.black,
        alignment: Alignment.center,
        child: _SpinnerWithLabel(label: '카메라를 켜는 중이에요'),
      );
    }
    if (error != null) {
      return Container(
        color: Colors.black,
        alignment: Alignment.center,
        child: _ErrorBox(
          message: error!,
          kind: errorKind,
          onRetry: onRetry,
          onGallery: onGallery,
        ),
      );
    }
    final c = controller;
    if (c == null || !c.value.isInitialized) {
      return Container(
        color: Colors.black,
        alignment: Alignment.center,
        child: _SpinnerWithLabel(label: '카메라를 켜는 중이에요'),
      );
    }
    final size = c.value.previewSize;
    if (size == null) {
      // previewSize 아직 안 옴 — 잠깐 로딩 표시 (검정 무한 방지)
      return Container(
        color: Colors.black,
        alignment: Alignment.center,
        child: _SpinnerWithLabel(label: '카메라 준비 중이에요'),
      );
    }
    // 풀스크린 cover — 안드로이드 previewSize 는 가로 좌표계라 세로 화면 그릴 때 swap.
    // FittedBox(cover, center) 가 정중앙 기준으로 양쪽 똑같이 자름.
    //
    // 검정 → 카메라 영상 전환을 페이드 인 (토스 톤 — "딱" 안 켜짐).
    return ClipRect(
      child: TweenAnimationBuilder<double>(
        tween: Tween(begin: 0.0, end: 1.0),
        duration: const Duration(milliseconds: 350),
        curve: Curves.easeOutQuart,
        builder: (ctx, v, child) => Opacity(opacity: v, child: child),
        child: SizedBox.expand(
          child: FittedBox(
            fit: BoxFit.cover,
            alignment: Alignment.center,
            child: SizedBox(
              width: size.height,
              height: size.width,
              child: isFront && !isEmulator
                  ? Transform(
                      alignment: Alignment.center,
                      transform: Matrix4.identity()
                        ..scaleByDouble(-1.0, 1.0, 1.0, 1.0),
                      child: CameraPreview(c),
                    )
                  : CameraPreview(c),
            ),
          ),
        ),
      ),
    );
  }
}

class _GuideOverlay extends StatelessWidget {
  final _CaptureMode mode;
  const _GuideOverlay({required this.mode});

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: LayoutBuilder(
        builder: (context, constraints) {
          final size = Size(constraints.maxWidth, constraints.maxHeight);
          // 둥근 박스(마스크·흰 외곽) = 영양제 크기로 고정
          final outerRect = _guideRect(size, _CaptureMode.supplement);
          // 노란 코너 = 둥근 박스 '안쪽'에 여백 두고 배치 (실제 촬영 영역).
          //   - 영양제: 박스에서 패딩만큼 균등 축소 (세로 직사각)
          //   - 식단:   그 안에 들어가는 최대 정사각 (가운데 정렬)
          final innerTarget = _innerRect(outerRect, mode);

          return Stack(
            children: [
              // ① 마스크 — 영양제 크기 고정
              Positioned.fill(
                child: CustomPaint(
                  painter: _GuideMaskPainter(
                    guideRect: outerRect,
                    radius: AppRadius.lg,
                  ),
                ),
              ),
              // ② 흰 외곽 둥근 박스 — 영양제 크기 고정
              Positioned.fromRect(
                rect: outerRect,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(AppRadius.lg),
                    border: Border.all(
                      color: Colors.white.withValues(alpha: 0.34),
                      width: 1,
                    ),
                  ),
                ),
              ),
              // ③ 노란 코너 — 모드별 rect 로 부드럽게 변형
              TweenAnimationBuilder<Rect?>(
                tween: RectTween(end: innerTarget),
                duration: const Duration(milliseconds: 320),
                curve: Curves.easeOutQuart,
                builder: (context, rect, _) {
                  final r = rect ?? innerTarget;
                  return Positioned.fromRect(
                    rect: r,
                    child: Stack(
                      children: const [
                        Positioned(
                          top: 0,
                          left: 0,
                          child: _Corner(corner: _CornerType.tl),
                        ),
                        Positioned(
                          top: 0,
                          right: 0,
                          child: _Corner(corner: _CornerType.tr),
                        ),
                        Positioned(
                          bottom: 0,
                          left: 0,
                          child: _Corner(corner: _CornerType.bl),
                        ),
                        Positioned(
                          bottom: 0,
                          right: 0,
                          child: _Corner(corner: _CornerType.br),
                        ),
                      ],
                    ),
                  );
                },
              ),
              // 안내 문구는 _buildCapture 에서 하단 컨트롤 바로 위에 별도 배치
              // (여기 두면 프레임/컨트롤과 겹침)
            ],
          );
        },
      ),
    );
  }

  // 가이드 사각 계산.
  //   - 둥근 외곽 박스: 항상 supplement 모드로 호출 → 영양제 크기 고정
  //   - 노란 코너: 현재 mode 로 호출 → 모드별 비율
  // 위치·여백·최대 크기는 동일. aspect(비율) 만 모드별로 다름.
  Rect _guideRect(Size size, _CaptureMode forMode) {
    final aspect = forMode == _CaptureMode.supplement ? 0.72 : 1.0;
    final topReserved = math.min(112.0, size.height * 0.18);
    final bottomReserved = math.min(212.0, size.height * 0.28);
    final usableHeight = math.max(
      220.0,
      size.height - topReserved - bottomReserved,
    );
    final maxWidth = math.max(
      1.0,
      math.min(size.width - (AppSpace.page * 2), 420.0),
    );
    // 영양제 기준 최대 높이로 통일
    final maxHeight = math.min(usableHeight, 520.0);

    var width = math.min(maxWidth, maxHeight * aspect);
    var height = width / aspect;
    if (height > maxHeight) {
      height = maxHeight;
      width = height * aspect;
    }

    return Rect.fromCenter(
      // 프레임 전체를 10px 위로
      center: Offset(size.width / 2, topReserved + usableHeight / 2 - 10),
      width: width,
      height: height,
    );
  }

  // 노란 코너 사각 — 둥근 외곽 박스(outer) 안쪽 영역.
  //   - 영양제: outer 에서 패딩만큼 균등 축소
  //   - 식단:   그 축소된 영역 안에 들어가는 최대 정사각 (중앙 정렬)
  Rect _innerRect(Rect outer, _CaptureMode forMode) {
    const pad = 24.0; // 둥근 박스 ↔ 노란 코너 사이 여백
    final inset = outer.deflate(pad);
    if (forMode == _CaptureMode.supplement) {
      return inset; // 세로 직사각 그대로
    }
    // 식단 — inset 안에 들어가는 최대 정사각
    final side = math.min(inset.width, inset.height);
    return Rect.fromCenter(center: inset.center, width: side, height: side);
  }
}

class _GuideMaskPainter extends CustomPainter {
  final Rect guideRect;
  final double radius;
  const _GuideMaskPainter({required this.guideRect, required this.radius});

  @override
  void paint(Canvas canvas, Size size) {
    final hole = RRect.fromRectAndRadius(guideRect, Radius.circular(radius));
    final paint = Paint()..color = Colors.black.withValues(alpha: 0.48);
    final outer = Path()..addRect(Offset.zero & size);
    final inner = Path()..addRRect(hole);
    final mask = Path.combine(PathOperation.difference, outer, inner);
    canvas.drawPath(mask, paint);
  }

  @override
  bool shouldRepaint(_GuideMaskPainter oldDelegate) {
    return oldDelegate.guideRect != guideRect || oldDelegate.radius != radius;
  }
}

class _SpinnerWithLabel extends StatelessWidget {
  final String label;
  const _SpinnerWithLabel({required this.label});
  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          width: 28,
          height: 28,
          child: CircularProgressIndicator(
            strokeWidth: 2.6,
            valueColor: AlwaysStoppedAnimation<Color>(AppColor.brand),
          ),
        ),
        const SizedBox(height: AppSpace.md),
        Text(
          label,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.72),
            fontSize: 13,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

class _ErrorBox extends StatelessWidget {
  final String message;
  final _CameraErrorKind kind;
  final VoidCallback? onRetry;
  final VoidCallback? onGallery;
  const _ErrorBox({
    required this.message,
    this.kind = _CameraErrorKind.initFailed,
    this.onRetry,
    this.onGallery,
  });

  @override
  Widget build(BuildContext context) {
    // figma 912:23 권한 / 912:69 초기화 실패 — StatusStateView 변형 톤.
    final bool denied = kind == _CameraErrorKind.permissionDenied;
    final String title = denied ? '권한이 필요해요' : '카메라를 열 수 없어요';
    return Padding(
      padding: const EdgeInsets.all(AppSpace.lg),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(
            denied ? Icons.lock_outline_rounded : Icons.no_photography_rounded,
            color: Colors.white.withValues(alpha: 0.4),
            size: 48,
          ),
          const SizedBox(height: AppSpace.md),
          Text(
            title,
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 17,
              fontWeight: FontWeight.w900,
              height: 1.3,
              letterSpacing: 0,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            message,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.72),
              fontSize: 13,
              fontWeight: FontWeight.w600,
              height: 1.5,
            ),
          ),
          const SizedBox(height: AppSpace.lg),
          if (onRetry != null)
            SizedBox(
              width: double.infinity,
              child: _PrimaryButton(
                key: const ValueKey<String>('camera-error-retry'),
                label: denied ? '권한 다시 확인' : '다시 시도',
                onTap: onRetry!,
              ),
            ),
          if (onGallery != null) ...<Widget>[
            const SizedBox(height: AppSpace.sm),
            GestureDetector(
              key: const ValueKey<String>('camera-error-gallery'),
              onTap: onGallery,
              behavior: HitTestBehavior.opaque,
              child: Container(
                width: double.infinity,
                height: 48,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: _CamTone.surfaceStrong,
                  borderRadius: BorderRadius.circular(AppRadius.md),
                  border: Border.all(color: _CamTone.border),
                ),
                child: const Text(
                  '갤러리로 진행',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0,
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// 안내 문구 칩 — 가이드 프레임 바깥 아래 (LADS 톤)
class _HintChip extends StatelessWidget {
  final IconData icon;
  final String text;
  const _HintChip({super.key, required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Container(
      // 화면 가로폭 가득 — 토글 버튼과 같은 폭. 텍스트는 가운데.
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpace.lg,
        vertical: AppSpace.sm + 3,
      ),
      decoration: BoxDecoration(
        color: _CamTone.surfaceStrong,
        borderRadius: BorderRadius.circular(AppRadius.full),
        border: Border.all(color: _CamTone.border, width: 1),
        boxShadow: _CamTone.softShadow,
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: AppColor.brand, size: 16),
          const SizedBox(width: 7),
          Flexible(
            child: Text(
              text,
              maxLines: 1,
              textAlign: TextAlign.center,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 13.5,
                fontWeight: FontWeight.w700,
                letterSpacing: 0,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

enum _CornerType { tl, tr, bl, br }

class _Corner extends StatelessWidget {
  final _CornerType corner;
  const _Corner({required this.corner});

  @override
  Widget build(BuildContext context) {
    const len = 30.0;
    const thick = 3.5;
    final color = AppColor.brand;
    const radius = Radius.circular(6);
    BorderSide side(bool show) =>
        show ? BorderSide(color: color, width: thick) : BorderSide.none;
    Border border;
    BorderRadius br;
    switch (corner) {
      case _CornerType.tl:
        border = Border(top: side(true), left: side(true));
        br = const BorderRadius.only(topLeft: radius);
        break;
      case _CornerType.tr:
        border = Border(top: side(true), right: side(true));
        br = const BorderRadius.only(topRight: radius);
        break;
      case _CornerType.bl:
        border = Border(bottom: side(true), left: side(true));
        br = const BorderRadius.only(bottomLeft: radius);
        break;
      case _CornerType.br:
        border = Border(bottom: side(true), right: side(true));
        br = const BorderRadius.only(bottomRight: radius);
        break;
    }
    return Container(
      width: len,
      height: len,
      decoration: BoxDecoration(border: border, borderRadius: br),
    );
  }
}

// ═══════════════════════════════════════════
// 하단 컨트롤 — 모드 토글 + 셔터 + 갤러리
// ═══════════════════════════════════════════
class _BottomControls extends StatelessWidget {
  final _CaptureMode mode;
  final ValueChanged<_CaptureMode> onModeChange;
  final VoidCallback onShutter;
  final VoidCallback onGallery;
  final VoidCallback? onDebugSupplementImage;
  final bool loading;
  final bool enabled;
  final Widget? supplementBatchStrip;

  const _BottomControls({
    required this.mode,
    required this.onModeChange,
    required this.onShutter,
    required this.onGallery,
    this.onDebugSupplementImage,
    required this.loading,
    required this.enabled,
    this.supplementBatchStrip,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(
        AppSpace.page,
        AppSpace.xl, // 칩 위 여백 — 그라데 때문에 좁아보여 한 단계 키움
        AppSpace.page,
        AppSpace.lg,
      ),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Colors.black.withValues(alpha: 0.0),
            Colors.black.withValues(alpha: 0.78),
          ],
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // 영양제 묶음 의도 토글 (영양제 모드).
          if (supplementBatchStrip != null) ...[
            supplementBatchStrip!,
            const SizedBox(height: AppSpace.md),
          ],
          // 안내 칩 — 모드 토글 위. 가이드 프레임/컨트롤과 안 겹침.
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 240),
            switchInCurve: Curves.easeOutQuart,
            transitionBuilder: (child, anim) => FadeTransition(
              opacity: anim,
              child: SlideTransition(
                position: Tween<Offset>(
                  begin: const Offset(0, 0.25),
                  end: Offset.zero,
                ).animate(anim),
                child: child,
              ),
            ),
            child: _HintChip(
              key: ValueKey(mode),
              icon: mode == _CaptureMode.supplement
                  ? Icons.description_rounded
                  : Icons.restaurant_rounded,
              text: mode == _CaptureMode.supplement
                  ? '성분표를 테두리 안에 맞춰주세요'
                  : '음식이 테두리 안에 들어오게 맞춰주세요',
            ),
          ),
          const SizedBox(height: AppSpace.lg),
          _ModeSegment(mode: mode, onChange: onModeChange),
          if (onDebugSupplementImage != null) ...[
            const SizedBox(height: AppSpace.md),
            _DebugSampleButton(onTap: onDebugSupplementImage!),
          ],
          const SizedBox(height: AppSpace.xl),
          // 셔터 정중앙 · 갤러리 좌측 끝 · 우측 균형 빈자리
          // Stack 으로 셔터를 화면 정중앙에 고정, 갤러리는 좌측에.
          SizedBox(
            height: 72,
            child: Stack(
              alignment: Alignment.center,
              children: [
                // 정중앙 — 셔터
                _ShutterButton(
                  onTap: enabled ? onShutter : () {},
                  loading: loading,
                  enabled: enabled,
                ),
                // 좌측 끝 — 갤러리 (가이드 프레임 좌측선과 정렬)
                Align(
                  alignment: Alignment.centerLeft,
                  child: _GalleryButton(onTap: onGallery),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _DebugSampleButton extends StatelessWidget {
  const _DebugSampleButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: '디버그 샘플 이미지',
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: Container(
          height: 42,
          padding: const EdgeInsets.symmetric(horizontal: AppSpace.md),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.10),
            borderRadius: BorderRadius.circular(AppRadius.full),
            border: Border.all(color: _CamTone.border, width: 1),
          ),
          child: const Row(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.science_rounded, color: Colors.white, size: 18),
              SizedBox(width: AppSpace.xs),
              Text(
                '디버그 샘플',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// 영양제 다중 사진 묶음 의도 — 기본은 "한 영양제" 병합.
// ═══════════════════════════════════════════
class _SupplementBatchIntentToggle extends StatelessWidget {
  const _SupplementBatchIntentToggle({
    required this.sameSupplementBatch,
    required this.onChanged,
  });

  final bool sameSupplementBatch;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: _CamTone.surface,
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(color: _CamTone.border),
        boxShadow: _CamTone.softShadow,
      ),
      child: Row(
        children: <Widget>[
          Expanded(
            child: _BatchIntentChip(
              key: const ValueKey<String>('supplement-batch-same'),
              label: '한 영양제 묶음',
              selected: sameSupplementBatch,
              onTap: () => onChanged(true),
            ),
          ),
          const SizedBox(width: 4),
          Expanded(
            child: _BatchIntentChip(
              key: const ValueKey<String>('supplement-batch-separate'),
              label: '서로 다른 영양제',
              selected: !sameSupplementBatch,
              onTap: () => onChanged(false),
            ),
          ),
        ],
      ),
    );
  }
}

class _BatchIntentChip extends StatelessWidget {
  const _BatchIntentChip({
    super.key,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 160),
        height: 38,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: selected ? AppColor.brand : Colors.transparent,
          borderRadius: BorderRadius.circular(AppRadius.sm),
        ),
        child: Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
            color: selected ? AppColor.ink : Colors.white,
            fontSize: 13,
            fontWeight: FontWeight.w900,
            letterSpacing: 0,
          ),
        ),
      ),
    );
  }
}

// 모드 토글 — 노란 알약이 슥 미끄러지는 슬라이딩 인디케이터 (토스 톤)
class _ModeSegment extends StatelessWidget {
  final _CaptureMode mode;
  final ValueChanged<_CaptureMode> onChange;
  const _ModeSegment({required this.mode, required this.onChange});

  @override
  Widget build(BuildContext context) {
    final isSupplement = mode == _CaptureMode.supplement;
    // maxWidth 제약 제거 — 좌우 끝까지 늘려서 가이드 프레임 폭과 정렬.
    // (_BottomControls 의 좌우 page 패딩 = 가이드 프레임 여백과 동일)
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: _CamTone.surfaceStrong,
        borderRadius: BorderRadius.circular(AppRadius.full),
        border: Border.all(color: _CamTone.border, width: 1),
        boxShadow: _CamTone.softShadow,
      ),
      child: LayoutBuilder(
        builder: (ctx, box) {
          final pillW = box.maxWidth / 2;
          return SizedBox(
            height: 48,
            child: Stack(
              children: [
                // 슬라이딩 노란 알약 — 선택에 따라 좌/우로 미끄러짐
                AnimatedAlign(
                  duration: const Duration(milliseconds: 260),
                  curve: Curves.easeOutQuart,
                  alignment: isSupplement
                      ? Alignment.centerLeft
                      : Alignment.centerRight,
                  child: Container(
                    width: pillW,
                    height: 48,
                    decoration: BoxDecoration(
                      color: AppColor.brand,
                      borderRadius: BorderRadius.circular(AppRadius.full),
                    ),
                  ),
                ),
                // 글자 2개 — 알약 위에 고정, 색만 부드럽게 전환
                Row(
                  children: [
                    _modeLabel(
                      '영양제',
                      isSupplement,
                      () => onChange(_CaptureMode.supplement),
                    ),
                    _modeLabel(
                      '식단',
                      !isSupplement,
                      () => onChange(_CaptureMode.meal),
                    ),
                  ],
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _modeLabel(String text, bool active, VoidCallback onTap) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: SizedBox(
          height: 48,
          child: Center(
            child: AnimatedDefaultTextStyle(
              duration: const Duration(milliseconds: 260),
              curve: Curves.easeOutQuart,
              style: TextStyle(
                color: active
                    ? AppColor.ink
                    : Colors.white.withValues(alpha: 0.65),
                fontSize: 17,
                fontWeight: active ? FontWeight.w800 : FontWeight.w600,
              ),
              child: Text(text),
            ),
          ),
        ),
      ),
    );
  }
}

// 셔터 — 누를 때 scale down (토스/애플 press 피드백)
class _ShutterButton extends StatefulWidget {
  final VoidCallback onTap;
  final bool loading;
  final bool enabled;
  const _ShutterButton({
    required this.onTap,
    required this.loading,
    required this.enabled,
  });

  @override
  State<_ShutterButton> createState() => _ShutterButtonState();
}

class _ShutterButtonState extends State<_ShutterButton> {
  bool _pressed = false;

  void _setPressed(bool v) {
    if (_pressed != v) setState(() => _pressed = v);
  }

  @override
  Widget build(BuildContext context) {
    final opacity = widget.enabled ? 1.0 : 0.4;
    return Semantics(
      button: true,
      label: '사진 촬영',
      child: Opacity(
        opacity: opacity,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: widget.loading ? null : widget.onTap,
          onTapDown: (_) => _setPressed(true),
          onTapUp: (_) => _setPressed(false),
          onTapCancel: () => _setPressed(false),
          child: AnimatedScale(
            // 누를 때 0.92 로 줄었다 복귀 — press 피드백
            scale: _pressed ? 0.92 : 1.0,
            duration: const Duration(milliseconds: 150),
            curve: Curves.easeOutCubic,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white, width: 4),
              ),
              child: Padding(
                padding: const EdgeInsets.all(4),
                child: Container(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [AppColor.brandTint, AppColor.brand],
                    ),
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: AppColor.brand.withValues(alpha: 0.35),
                        blurRadius: 18,
                        offset: const Offset(0, 6),
                      ),
                    ],
                  ),
                  // 로딩 스피너 페이드 인/아웃
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 200),
                    child: widget.loading
                        ? const Center(
                            key: ValueKey('spin'),
                            child: SizedBox(
                              width: 24,
                              height: 24,
                              child: CircularProgressIndicator(
                                strokeWidth: 2.6,
                                valueColor: AlwaysStoppedAnimation<Color>(
                                  AppColor.ink,
                                ),
                              ),
                            ),
                          )
                        : const SizedBox.shrink(key: ValueKey('idle')),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// 갤러리 버튼 — 글래스 톤 + press 피드백 (LADS / 토스 톤)
class _GalleryButton extends StatefulWidget {
  final VoidCallback onTap;
  const _GalleryButton({required this.onTap});

  @override
  State<_GalleryButton> createState() => _GalleryButtonState();
}

class _GalleryButtonState extends State<_GalleryButton> {
  bool _pressed = false;

  void _set(bool v) {
    if (_pressed != v) setState(() => _pressed = v);
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: '갤러리에서 여러 장 선택',
      child: GestureDetector(
        onTap: () {
          HapticFeedback.lightImpact();
          widget.onTap();
        },
        onTapDown: (_) => _set(true),
        onTapUp: (_) => _set(false),
        onTapCancel: () => _set(false),
        child: AnimatedScale(
          scale: _pressed ? 0.92 : 1.0,
          duration: const Duration(milliseconds: 150),
          curve: Curves.easeOutCubic,
          child: Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: _CamTone.surface,
              borderRadius: BorderRadius.circular(AppRadius.md),
              border: Border.all(color: _CamTone.border, width: 1),
              boxShadow: _CamTone.softShadow,
            ),
            alignment: Alignment.center,
            child: const Icon(
              Icons.photo_library_rounded,
              color: Colors.white,
              size: 23,
            ),
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════
// CTA 버튼 (미리보기 화면용)
// ═══════════════════════════════════════════
class _PrimaryButton extends StatelessWidget {
  final String label;
  final VoidCallback onTap;
  const _PrimaryButton({required this.label, required this.onTap, super.key});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 56,
      child: TextButton(
        onPressed: onTap,
        style: TextButton.styleFrom(
          padding: EdgeInsets.zero,
          foregroundColor: AppColor.ink,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppRadius.md),
          ),
        ),
        child: Ink(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [AppColor.brandTint, AppColor.brand],
            ),
            borderRadius: BorderRadius.circular(AppRadius.md),
            boxShadow: [
              BoxShadow(
                color: AppColor.brand.withValues(alpha: 0.40),
                blurRadius: 16,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          child: Center(
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: Text(
                label,
                maxLines: 1,
                style: const TextStyle(
                  color: AppColor.ink,
                  fontSize: 17,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _GhostButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final VoidCallback onTap;
  const _GhostButton({
    required this.label,
    required this.icon,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        height: 56,
        decoration: BoxDecoration(
          color: _CamTone.surface,
          borderRadius: BorderRadius.circular(AppRadius.md),
          border: Border.all(color: _CamTone.border, width: 1),
        ),
        alignment: Alignment.center,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: Colors.white, size: 18),
            const SizedBox(width: AppSpace.xs),
            Flexible(
              child: FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(
                  label,
                  maxLines: 1,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
