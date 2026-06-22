import 'dart:async';

import 'package:camera/camera.dart' as camera;
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// Loads the camera list reported by the active Flutter camera implementation.
typedef CameraListLoader = Future<List<camera.CameraDescription>> Function();

/// Coarse camera readiness state for the supplement label capture flow.
enum CameraReadinessKind {
  /// The app is checking the active runtime.
  probing,

  /// At least one camera is available for direct capture.
  ready,

  /// The runtime reported no usable cameras.
  unavailable,

  /// Camera access is blocked by runtime permissions or restrictions.
  permissionDenied,

  /// Camera status could not be determined.
  error,
}

/// Sanitized camera capability snapshot shown to operators during live smoke.
class CameraReadinessSnapshot {
  /// Creates a camera readiness snapshot.
  ///
  /// Args:
  ///   kind: Coarse camera status.
  ///   platform: Flutter target platform being evaluated.
  ///   cameraCount: Number of cameras reported by the plugin.
  ///   errorCode: Sanitized plugin/platform error code, if any.
  const CameraReadinessSnapshot({
    required this.kind,
    required this.platform,
    required this.cameraCount,
    this.errorCode,
  });

  /// Coarse camera status.
  final CameraReadinessKind kind;

  /// Flutter target platform being evaluated.
  final TargetPlatform platform;

  /// Number of cameras reported by the plugin.
  final int cameraCount;

  /// Sanitized plugin/platform error code, if any.
  final String? errorCode;

  /// Snapshot used while a probe is running.
  ///
  /// Args:
  ///   platform: Flutter target platform being evaluated.
  ///
  /// Returns:
  ///   Probe-in-progress snapshot.
  factory CameraReadinessSnapshot.probing({required TargetPlatform platform}) {
    return CameraReadinessSnapshot(
      kind: CameraReadinessKind.probing,
      platform: platform,
      cameraCount: 0,
    );
  }

  /// Creates a snapshot from the list returned by `availableCameras`.
  ///
  /// Args:
  ///   platform: Flutter target platform being evaluated.
  ///   cameras: Cameras reported by the active plugin implementation.
  ///
  /// Returns:
  ///   Ready when at least one camera is present, otherwise unavailable.
  factory CameraReadinessSnapshot.fromCameras({
    required TargetPlatform platform,
    required List<camera.CameraDescription> cameras,
  }) {
    return CameraReadinessSnapshot(
      kind: cameras.isEmpty
          ? CameraReadinessKind.unavailable
          : CameraReadinessKind.ready,
      platform: platform,
      cameraCount: cameras.length,
    );
  }

  /// Creates a sanitized snapshot from a plugin/platform exception.
  ///
  /// Args:
  ///   platform: Flutter target platform being evaluated.
  ///   error: Exception thrown by the camera plugin or platform channel.
  ///
  /// Returns:
  ///   Permission, unavailable, or generic error status without raw payloads.
  factory CameraReadinessSnapshot.fromError({
    required TargetPlatform platform,
    required Object error,
  }) {
    final String? code = _errorCode(error);
    final CameraReadinessKind kind = switch (code) {
      'CameraAccessDenied' ||
      'CameraAccessDeniedWithoutPrompt' ||
      'CameraAccessRestricted' => CameraReadinessKind.permissionDenied,
      'NoCameraAvailable' => CameraReadinessKind.unavailable,
      _ => CameraReadinessKind.error,
    };
    return CameraReadinessSnapshot(
      kind: kind,
      platform: platform,
      cameraCount: 0,
      errorCode: code,
    );
  }

  /// Whether direct camera capture should be enabled.
  bool get canOpenCamera => kind == CameraReadinessKind.ready;

  /// Whether gallery fallback is the expected test path for this runtime.
  bool get preferGalleryFallback {
    return kind == CameraReadinessKind.unavailable ||
        kind == CameraReadinessKind.permissionDenied ||
        kind == CameraReadinessKind.error;
  }

  /// User-safe short platform label.
  String get platformLabel {
    return switch (platform) {
      TargetPlatform.iOS => 'iOS',
      TargetPlatform.android => 'Android',
      TargetPlatform.macOS => 'macOS',
      TargetPlatform.windows => 'Windows',
      TargetPlatform.linux => 'Linux',
      TargetPlatform.fuchsia => 'Fuchsia',
    };
  }

  /// User-safe title for the capture surface.
  String get title {
    return switch (kind) {
      CameraReadinessKind.probing => '카메라 연결 확인 중',
      CameraReadinessKind.ready => '$platformLabel 카메라 연결됨',
      CameraReadinessKind.unavailable => '$platformLabel 카메라 없음',
      CameraReadinessKind.permissionDenied => '카메라 권한 필요',
      CameraReadinessKind.error => '카메라 상태 확인 필요',
    };
  }

  /// User-safe platform-specific guidance.
  String get guidance {
    return switch (kind) {
      CameraReadinessKind.probing => '현재 실행 환경에서 직접 촬영 가능 여부를 확인하고 있어요.',
      CameraReadinessKind.ready => _readyGuidance,
      CameraReadinessKind.unavailable => _unavailableGuidance,
      CameraReadinessKind.permissionDenied =>
        '시스템 설정에서 카메라 권한을 허용한 뒤 다시 확인해주세요.',
      CameraReadinessKind.error => _errorGuidance,
    };
  }

  String get _readyGuidance {
    return switch (platform) {
      TargetPlatform.android =>
        'Android Studio Emulator 또는 실제 Android 기기에서 직접 촬영 후 OCR endpoint로 분석할 수 있어요.',
      TargetPlatform.iOS =>
        '실제 iPhone/iPad 카메라 또는 카메라가 보고된 런타임에서 직접 촬영 후 OCR endpoint로 분석할 수 있어요.',
      _ => '직접 촬영 후 OCR endpoint로 분석할 수 있어요.',
    };
  }

  String get _unavailableGuidance {
    return switch (platform) {
      TargetPlatform.iOS =>
        'iOS Simulator는 이 앱 런타임에서 카메라를 보고하지 않았어요. 갤러리 이미지로 같은 OCR endpoint를 테스트하거나 실제 iPhone에서 직접 촬영하세요.',
      TargetPlatform.android =>
        'Android Studio AVD의 Camera를 Virtual scene 또는 webcam으로 설정한 뒤 다시 확인하세요. 지금은 갤러리 이미지로 같은 OCR endpoint를 테스트할 수 있어요.',
      _ => '갤러리 이미지로 같은 OCR endpoint를 테스트하거나 카메라가 있는 기기에서 실행하세요.',
    };
  }

  String get _errorGuidance {
    final String suffix = errorCode == null ? '' : ' ($errorCode)';
    return '플러그인 또는 플랫폼 채널이 카메라 상태를 확인하지 못했어요$suffix. 갤러리 fallback은 계속 사용할 수 있어요.';
  }

  static String? _errorCode(Object error) {
    if (error is camera.CameraException) {
      return error.code;
    }
    if (error is PlatformException) {
      return error.code;
    }
    if (error is MissingPluginException) {
      return 'MissingPlugin';
    }
    return null;
  }

  /// Creates a bounded fallback when the platform camera probe hangs.
  ///
  /// Args:
  ///   platform: Flutter target platform being evaluated.
  ///
  /// Returns:
  ///   Android is allowed to try direct capture because the emulator camera
  ///   controller can still initialize after a slow list probe. Other platforms
  ///   fall back to gallery-first behavior.
  factory CameraReadinessSnapshot.fromProbeTimeout({
    required TargetPlatform platform,
  }) {
    return CameraReadinessSnapshot(
      kind: platform == TargetPlatform.android
          ? CameraReadinessKind.ready
          : CameraReadinessKind.error,
      platform: platform,
      cameraCount: 0,
      errorCode: 'CameraProbeTimeout',
    );
  }
}

/// Probes camera availability without exposing image data or provider payloads.
class CameraReadinessProbe {
  /// Creates a camera readiness probe.
  ///
  /// Args:
  ///   loader: Injectable camera list loader for unit tests.
  ///   platform: Injectable platform for deterministic tests.
  const CameraReadinessProbe({
    CameraListLoader? loader,
    TargetPlatform? platform,
    Duration timeout = const Duration(seconds: 4),
  }) : _loader = loader ?? camera.availableCameras,
       _timeout = timeout,
       _platform = platform;

  final CameraListLoader _loader;
  final Duration _timeout;
  final TargetPlatform? _platform;

  /// Checks camera availability for the current Flutter runtime.
  ///
  /// Returns:
  ///   Sanitized camera readiness snapshot.
  Future<CameraReadinessSnapshot> check() async {
    final TargetPlatform platform = _platform ?? defaultTargetPlatform;
    try {
      final List<camera.CameraDescription> cameras = await _loader().timeout(
        _timeout,
      );
      return CameraReadinessSnapshot.fromCameras(
        platform: platform,
        cameras: cameras,
      );
    } on TimeoutException {
      return CameraReadinessSnapshot.fromProbeTimeout(platform: platform);
    } catch (error) {
      return CameraReadinessSnapshot.fromError(
        platform: platform,
        error: error,
      );
    }
  }
}
