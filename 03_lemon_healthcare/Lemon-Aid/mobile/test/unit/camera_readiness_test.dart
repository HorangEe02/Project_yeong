import 'package:camera/camera.dart' as camera;
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/supplements/camera_readiness.dart';

void main() {
  test('reports Android emulator or device camera as ready', () async {
    final CameraReadinessProbe probe = CameraReadinessProbe(
      platform: TargetPlatform.android,
      loader: () async {
        return const <camera.CameraDescription>[
          camera.CameraDescription(
            name: '0',
            lensDirection: camera.CameraLensDirection.back,
            sensorOrientation: 90,
          ),
        ];
      },
    );

    final CameraReadinessSnapshot snapshot = await probe.check();

    expect(snapshot.kind, CameraReadinessKind.ready);
    expect(snapshot.canOpenCamera, isTrue);
    expect(snapshot.cameraCount, 1);
    expect(snapshot.guidance, contains('OCR endpoint'));
  });

  test('uses gallery fallback guidance when iOS reports no cameras', () async {
    final CameraReadinessProbe probe = CameraReadinessProbe(
      platform: TargetPlatform.iOS,
      loader: () async => const <camera.CameraDescription>[],
    );

    final CameraReadinessSnapshot snapshot = await probe.check();

    expect(snapshot.kind, CameraReadinessKind.unavailable);
    expect(snapshot.canOpenCamera, isFalse);
    expect(snapshot.preferGalleryFallback, isTrue);
    expect(snapshot.guidance, contains('갤러리 이미지'));
  });

  test('maps camera permission errors without leaking raw details', () async {
    final CameraReadinessProbe probe = CameraReadinessProbe(
      platform: TargetPlatform.iOS,
      loader: () async {
        throw camera.CameraException(
          'CameraAccessDeniedWithoutPrompt',
          'raw permission detail',
        );
      },
    );

    final CameraReadinessSnapshot snapshot = await probe.check();

    expect(snapshot.kind, CameraReadinessKind.permissionDenied);
    expect(snapshot.errorCode, 'CameraAccessDeniedWithoutPrompt');
    expect(snapshot.guidance, isNot(contains('raw permission detail')));
  });

  test('maps missing plugin in widget tests to sanitized error', () async {
    final CameraReadinessProbe probe = CameraReadinessProbe(
      platform: TargetPlatform.android,
      loader: () async {
        throw MissingPluginException('camera channel unavailable');
      },
    );

    final CameraReadinessSnapshot snapshot = await probe.check();

    expect(snapshot.kind, CameraReadinessKind.error);
    expect(snapshot.errorCode, 'MissingPlugin');
    expect(snapshot.guidance, contains('MissingPlugin'));
    expect(snapshot.guidance, isNot(contains('camera channel unavailable')));
  });

  test(
    'allows Android direct capture attempt when camera probe times out',
    () async {
      final CameraReadinessProbe probe = CameraReadinessProbe(
        platform: TargetPlatform.android,
        timeout: const Duration(milliseconds: 1),
        loader: () async {
          await Future<void>.delayed(const Duration(milliseconds: 50));
          return const <camera.CameraDescription>[];
        },
      );

      final CameraReadinessSnapshot snapshot = await probe.check();

      expect(snapshot.kind, CameraReadinessKind.ready);
      expect(snapshot.canOpenCamera, isTrue);
      expect(snapshot.errorCode, 'CameraProbeTimeout');
    },
  );

  test(
    'uses gallery fallback when non-Android camera probe times out',
    () async {
      final CameraReadinessProbe probe = CameraReadinessProbe(
        platform: TargetPlatform.iOS,
        timeout: const Duration(milliseconds: 1),
        loader: () async {
          await Future<void>.delayed(const Duration(milliseconds: 50));
          return const <camera.CameraDescription>[];
        },
      );

      final CameraReadinessSnapshot snapshot = await probe.check();

      expect(snapshot.kind, CameraReadinessKind.error);
      expect(snapshot.canOpenCamera, isFalse);
      expect(snapshot.preferGalleryFallback, isTrue);
      expect(snapshot.errorCode, 'CameraProbeTimeout');
    },
  );
}
