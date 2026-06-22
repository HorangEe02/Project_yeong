import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';
import 'package:lemon_aid_mobile/core/storage/local_prefs.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_models.dart';
import 'package:lemon_aid_mobile/screens/camera_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  test('emulator Mac camera bridge bypasses picker-camera fallback', () {
    expect(
      shouldUseCameraPickerFallback(
        isEmulator: true,
        platform: TargetPlatform.iOS,
        enableEmulatorLiveCamera: false,
        hasMacCameraBridge: true,
      ),
      isFalse,
    );
    expect(
      shouldUseCameraPickerFallback(
        isEmulator: true,
        platform: TargetPlatform.android,
        enableEmulatorLiveCamera: false,
        hasMacCameraBridge: true,
      ),
      isFalse,
    );
    expect(
      shouldUseCameraPickerFallback(
        isEmulator: true,
        platform: TargetPlatform.android,
        enableEmulatorLiveCamera: false,
        hasMacCameraBridge: false,
      ),
      isTrue,
    );
  });

  testWidgets('iOS simulator Mac camera bridge opens OCR preview', (
    WidgetTester tester,
  ) async {
    await _usePhoneSurface(tester);
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
    try {
      final File source = _writeTinyPng();
      int previewRequests = 0;

      await tester.pumpWidget(
        MaterialApp(
          home: CameraScreen(
            isEmulatorOverride: true,
            macCameraBridgeUrl: 'http://127.0.0.1:8755',
            macCameraPreviewFrameOverride: () async {
              previewRequests += 1;
              return base64Decode(_testFrameJpegBase64);
            },
            macCameraCaptureOverride: () async => source,
            onAnalyzeSupplementImage:
                (String imagePath, {required String ocrProvider}) async {},
          ),
        ),
      );
      await tester.pump(const Duration(seconds: 1));

      expect(find.textContaining('Mac 카메라 bridge'), findsNothing);
      expect(find.byType(Image), findsOneWidget);
      final Image previewImage = tester.widget<Image>(find.byType(Image));
      expect(previewImage.gaplessPlayback, isTrue);
      expect(previewImage.filterQuality, FilterQuality.low);
      await tester.pump(const Duration(milliseconds: 350));
      expect(previewRequests, greaterThan(1));

      await tester.tap(find.bySemanticsLabel('사진 촬영'));
      await tester.pump();
      await tester.runAsync(() async {
        await Future<void>.delayed(const Duration(seconds: 1));
      });
      await tester.pumpAndSettle();

      expect(find.text('미리보기'), findsOneWidget);
      expect(find.text('분석하기'), findsOneWidget);
    } finally {
      debugDefaultTargetPlatformOverride = null;
    }
  });

  testWidgets('Mac camera bridge shutter works before first preview frame', (
    WidgetTester tester,
  ) async {
    await _usePhoneSurface(tester);
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
    try {
      final File source = _writeTinyPng();

      await tester.pumpWidget(
        MaterialApp(
          home: CameraScreen(
            isEmulatorOverride: true,
            macCameraBridgeUrl: 'http://127.0.0.1:8755',
            macCameraPreviewFrameOverride: () async {
              throw const SocketException('test bridge unavailable');
            },
            macCameraCaptureOverride: () async => source,
            onAnalyzeSupplementImage:
                (String imagePath, {required String ocrProvider}) async {},
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 250));

      expect(find.textContaining('8755 포트'), findsOneWidget);

      await tester.tap(find.bySemanticsLabel('사진 촬영'));
      await tester.pump();
      await tester.runAsync(() async {
        await Future<void>.delayed(const Duration(milliseconds: 250));
      });
      await tester.pumpAndSettle();

      expect(find.text('미리보기'), findsOneWidget);
      expect(find.text('분석하기'), findsOneWidget);
    } finally {
      debugDefaultTargetPlatformOverride = null;
    }
  });

  testWidgets('Android emulator Mac camera bridge opens live OCR preview', (
    WidgetTester tester,
  ) async {
    await _usePhoneSurface(tester);
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    try {
      final File source = _writeTinyPng();
      int previewRequests = 0;

      await tester.pumpWidget(
        MaterialApp(
          home: CameraScreen(
            isEmulatorOverride: true,
            macCameraPreviewFrameOverride: () async {
              previewRequests += 1;
              return base64Decode(_testFrameJpegBase64);
            },
            macCameraCaptureOverride: () async => source,
            onAnalyzeSupplementImage:
                (String imagePath, {required String ocrProvider}) async {},
          ),
        ),
      );
      await tester.pump(const Duration(seconds: 1));

      expect(find.textContaining('8755 포트'), findsNothing);
      expect(find.byType(Image), findsOneWidget);
      final Image previewImage = tester.widget<Image>(find.byType(Image));
      expect(previewImage.gaplessPlayback, isTrue);
      expect(previewImage.filterQuality, FilterQuality.low);
      await tester.pump(const Duration(milliseconds: 350));
      expect(previewRequests, greaterThan(1));

      await tester.tap(find.bySemanticsLabel('사진 촬영'));
      await tester.pump();
      await tester.runAsync(() async {
        await Future<void>.delayed(const Duration(seconds: 1));
      });
      await tester.pumpAndSettle();

      expect(find.text('미리보기'), findsOneWidget);
      expect(find.text('분석하기'), findsOneWidget);
    } finally {
      debugDefaultTargetPlatformOverride = null;
    }
  });

  testWidgets('gallery pick opens the OCR preview with safer picker options', (
    WidgetTester tester,
  ) async {
    await _usePhoneSurface(tester);
    final File source = _writeTinyPng();
    final _FakeImagePicker picker = _FakeImagePicker(source.path);

    await tester.pumpWidget(
      MaterialApp(
        home: CameraScreen(
          imagePicker: picker,
          onAnalyzeSupplementImage:
              (String imagePath, {required String ocrProvider}) async {},
        ),
      ),
    );
    await tester.pump(const Duration(seconds: 1));

    await tester.tap(find.byIcon(Icons.photo_library_rounded));
    await tester.pump();
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();

    expect(picker.multiPickCount, 1);
    expect(picker.lastMultiLimit, 6);
    expect(picker.lastMaxWidth, 2400);
    expect(picker.lastImageQuality, 95);
    expect(picker.lastRequestFullMetadata, isFalse);
    expect(find.text('갤러리 이미지를 불러오지 못했어요. 다른 사진을 선택해주세요.'), findsNothing);
    expect(find.text('미리보기'), findsOneWidget);
    expect(find.text('분석하기'), findsOneWidget);
  });

  testWidgets('supplement gallery can select several images at once', (
    WidgetTester tester,
  ) async {
    await _usePhoneSurface(tester);
    final File sourceA = _writeTinyPng();
    final File sourceB = _writeTinyPng();
    final File sourceC = _writeTinyPng();
    final _FakeImagePicker picker = _FakeImagePicker(
      sourceA.path,
      multiPaths: <String>[sourceA.path, sourceB.path, sourceC.path],
    );
    List<SupplementImageUpload>? uploadedImages;
    bool? sameBatchIntent;

    await tester.pumpWidget(
      MaterialApp(
        home: CameraScreen(
          imagePicker: picker,
          onAnalyzeSupplementImage:
              (String imagePath, {required String ocrProvider}) async {},
          onAnalyzeSupplementImages:
              (
                List<SupplementImageUpload> images, {
                required String ocrProvider,
                required bool sameSupplementBatch,
              }) async {
                uploadedImages = images;
                sameBatchIntent = sameSupplementBatch;
              },
        ),
      ),
    );
    await tester.pump(const Duration(seconds: 1));

    await tester.tap(find.byIcon(Icons.photo_library_rounded));
    await tester.pump();
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();

    expect(picker.multiPickCount, 1);
    expect(picker.lastMultiLimit, 6);
    expect(find.text('3장'), findsOneWidget);
    expect(find.text('추가 사진 1'), findsOneWidget);
    expect(find.text('추가 사진 2'), findsOneWidget);
    expect(find.text('현재 사진'), findsOneWidget);
    expect(find.text('3장 분석'), findsOneWidget);

    final Finder analyzeButton = find.byKey(
      const ValueKey('supplement-preview-analyze'),
    );
    await tester.ensureVisible(analyzeButton);
    await tester.pump();
    final TextButton textButton = tester.widget<TextButton>(
      find.descendant(of: analyzeButton, matching: find.byType(TextButton)),
    );
    await tester.runAsync(() async {
      textButton.onPressed!();
      await Future<void>.delayed(const Duration(milliseconds: 100));
    });
    await tester.pumpAndSettle();

    expect(uploadedImages, isNotNull);
    expect(uploadedImages, hasLength(3));
    expect(sameBatchIntent, isTrue);
  });

  testWidgets('Android lost multi-image selection restores supplement batch', (
    WidgetTester tester,
  ) async {
    await _usePhoneSurface(tester);
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    try {
      final File sourceA = _writeTinyPng();
      final File sourceB = _writeTinyPng();
      final File sourceC = _writeTinyPng();
      final _FakeImagePicker picker = _FakeImagePicker(
        sourceA.path,
        lostDataResponse: LostDataResponse(
          files: <XFile>[
            XFile(sourceA.path, name: 'lost-a.png', mimeType: 'image/png'),
            XFile(sourceB.path, name: 'lost-b.png', mimeType: 'image/png'),
            XFile(sourceC.path, name: 'lost-c.png', mimeType: 'image/png'),
          ],
        ),
      );
      List<SupplementImageUpload>? uploadedImages;

      await tester.pumpWidget(
        MaterialApp(
          home: CameraScreen(
            imagePicker: picker,
            onAnalyzeSupplementImage:
                (String imagePath, {required String ocrProvider}) async {},
            onAnalyzeSupplementImages:
                (
                  List<SupplementImageUpload> images, {
                  required String ocrProvider,
                  required bool sameSupplementBatch,
                }) async {
                  uploadedImages = images;
                },
          ),
        ),
      );
      await tester.pump();
      await tester.runAsync(() async {
        await Future<void>.delayed(const Duration(seconds: 1));
      });
      await tester.pumpAndSettle();

      expect(find.text('3장'), findsOneWidget);
      expect(find.text('추가 사진 1'), findsOneWidget);
      expect(find.text('추가 사진 2'), findsOneWidget);
      expect(find.text('현재 사진'), findsOneWidget);
      expect(find.text('3장 분석'), findsOneWidget);

      final Finder analyzeButton = find.byKey(
        const ValueKey('supplement-preview-analyze'),
      );
      await tester.ensureVisible(analyzeButton);
      await tester.pump();
      final TextButton textButton = tester.widget<TextButton>(
        find.descendant(of: analyzeButton, matching: find.byType(TextButton)),
      );
      await tester.runAsync(() async {
        textButton.onPressed!();
        await Future<void>.delayed(const Duration(milliseconds: 100));
      });
      await tester.pumpAndSettle();

      expect(uploadedImages, isNotNull);
      expect(uploadedImages, hasLength(3));
    } finally {
      debugDefaultTargetPlatformOverride = null;
    }
  });

  testWidgets('emulator camera fallback opens picker camera source', (
    WidgetTester tester,
  ) async {
    await _usePhoneSurface(tester);
    final File source = _writeTinyPng();
    final _FakeImagePicker picker = _FakeImagePicker(source.path);

    await tester.pumpWidget(
      MaterialApp(
        home: CameraScreen(
          imagePicker: picker,
          useCameraPickerFallback: true,
          onAnalyzeSupplementImage:
              (String imagePath, {required String ocrProvider}) async {},
        ),
      ),
    );
    await tester.pump(const Duration(seconds: 1));

    await tester.tap(find.bySemanticsLabel('사진 촬영'));
    await tester.pump();
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();

    expect(picker.lastSource, ImageSource.camera);
    expect(picker.lastMaxWidth, 2400);
    expect(picker.lastImageQuality, 95);
    expect(picker.lastRequestFullMetadata, isFalse);
    expect(find.text('미리보기'), findsOneWidget);
    expect(find.text('분석하기'), findsOneWidget);
  });

  testWidgets('debug supplement image path bypasses Android photo picker', (
    WidgetTester tester,
  ) async {
    await _usePhoneSurface(tester);
    final File source = _writeTinyPng();
    final _FakeImagePicker picker = _FakeImagePicker(source.path);

    await tester.pumpWidget(
      MaterialApp(
        home: CameraScreen(
          imagePicker: picker,
          debugSupplementImagePath: source.path,
          onAnalyzeSupplementImage:
              (String imagePath, {required String ocrProvider}) async {},
        ),
      ),
    );
    await tester.pump(const Duration(seconds: 1));

    await tester.tap(find.text('디버그 샘플'));
    await tester.pumpAndSettle();

    expect(picker.lastSource, isNull);
    expect(find.text('미리보기'), findsOneWidget);
    expect(find.text('분석하기'), findsOneWidget);
  });

  testWidgets(
    'gallery button still opens multi-select when debug sample exists',
    (WidgetTester tester) async {
      await _usePhoneSurface(tester);
      final File debugSource = _writeTinyPng();
      final File galleryA = _writeTinyPng();
      final File galleryB = _writeTinyPng();
      final _FakeImagePicker picker = _FakeImagePicker(
        galleryA.path,
        multiPaths: <String>[galleryA.path, galleryB.path],
      );

      await tester.pumpWidget(
        MaterialApp(
          home: CameraScreen(
            imagePicker: picker,
            debugSupplementImagePath: debugSource.path,
            onAnalyzeSupplementImage:
                (String imagePath, {required String ocrProvider}) async {},
          ),
        ),
      );
      await tester.pump(const Duration(seconds: 1));

      await tester.tap(find.bySemanticsLabel('갤러리에서 여러 장 선택'));
      await tester.pump();
      await tester.runAsync(() async {
        await Future<void>.delayed(const Duration(seconds: 1));
      });
      await tester.pumpAndSettle();

      expect(picker.multiPickCount, 1);
      expect(picker.lastSource, isNull);
      expect(picker.lastMultiLimit, 6);
      expect(find.text('2장'), findsOneWidget);
      expect(find.text('2장 분석'), findsOneWidget);
    },
  );

  testWidgets('supplement preview can add images into a batch', (
    WidgetTester tester,
  ) async {
    await _usePhoneSurface(tester);
    final File source = _writeTinyPng();
    final _FakeImagePicker picker = _FakeImagePicker(source.path);

    await tester.pumpWidget(
      MaterialApp(
        home: CameraScreen(
          imagePicker: picker,
          onAnalyzeSupplementImage:
              (String imagePath, {required String ocrProvider}) async {},
          onAnalyzeSupplementImages:
              (
                List<SupplementImageUpload> images, {
                required String ocrProvider,
                required bool sameSupplementBatch,
              }) async {},
        ),
      ),
    );
    await tester.pump(const Duration(seconds: 1));

    await tester.tap(find.byIcon(Icons.photo_library_rounded));
    await tester.pump();
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(seconds: 1));
    });
    await tester.pump(const Duration(milliseconds: 600));

    await tester.tap(
      find
          .ancestor(
            of: find.text('계속 촬영'),
            matching: find.byType(GestureDetector),
          )
          .last,
    );
    await tester.pumpAndSettle();
    expect(find.text('2장'), findsNothing);

    await tester.tap(find.byIcon(Icons.photo_library_rounded));
    await tester.pump();
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(seconds: 1));
    });
    await tester.pump(const Duration(milliseconds: 600));

    expect(find.text('2장'), findsOneWidget);
    expect(find.text('추가 사진 1'), findsOneWidget);
    expect(find.text('현재 사진'), findsOneWidget);
    expect(find.text('자동 분석'), findsOneWidget);
    expect(find.text('2장 분석'), findsOneWidget);
  });

  testWidgets('supplement preview can add several gallery images at once', (
    WidgetTester tester,
  ) async {
    await _usePhoneSurface(tester);
    final File current = _writeTinyPng();
    final File extraA = _writeTinyPng();
    final File extraB = _writeTinyPng();
    final _FakeImagePicker picker = _FakeImagePicker(
      current.path,
      multiPaths: <String>[extraA.path, extraB.path],
    );
    List<SupplementImageUpload>? uploadedImages;

    await tester.pumpWidget(
      MaterialApp(
        home: CameraScreen(
          imagePicker: picker,
          useCameraPickerFallback: true,
          onAnalyzeSupplementImage:
              (String imagePath, {required String ocrProvider}) async {},
          onAnalyzeSupplementImages:
              (
                List<SupplementImageUpload> images, {
                required String ocrProvider,
                required bool sameSupplementBatch,
              }) async {
                uploadedImages = images;
              },
        ),
      ),
    );
    await tester.pump(const Duration(seconds: 1));

    await tester.tap(find.bySemanticsLabel('사진 촬영'));
    await tester.pump();
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();

    await tester.tap(find.text('여러 장 추가'));
    await tester.pump();
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();

    expect(picker.multiPickCount, 1);
    expect(picker.lastMultiLimit, 5);
    expect(find.text('3장'), findsOneWidget);
    expect(find.text('추가 사진 1'), findsOneWidget);
    expect(find.text('추가 사진 2'), findsOneWidget);
    expect(find.text('현재 사진'), findsOneWidget);
    expect(find.text('3장 분석'), findsOneWidget);

    final Finder analyzeButton = find.byKey(
      const ValueKey('supplement-preview-analyze'),
    );
    await tester.ensureVisible(analyzeButton);
    await tester.pump();
    final TextButton textButton = tester.widget<TextButton>(
      find.descendant(of: analyzeButton, matching: find.byType(TextButton)),
    );
    await tester.runAsync(() async {
      textButton.onPressed!();
      await Future<void>.delayed(const Duration(milliseconds: 100));
    });
    await tester.pumpAndSettle();

    expect(uploadedImages, isNotNull);
    expect(uploadedImages, hasLength(3));
  });

  testWidgets('supplement facts retake uses role-aware upload for one image', (
    WidgetTester tester,
  ) async {
    await _usePhoneSurface(tester);
    final File source = _writeTinyPng();
    final _FakeImagePicker picker = _FakeImagePicker(source.path);
    String? singleImagePath;
    List<SupplementImageUpload>? uploadedImages;

    await tester.pumpWidget(
      MaterialApp(
        home: CameraScreen(
          initialImageRole: 'supplement_facts',
          imagePicker: picker,
          onAnalyzeSupplementImage:
              (String imagePath, {required String ocrProvider}) async {
                singleImagePath = imagePath;
              },
          onAnalyzeSupplementImages:
              (
                List<SupplementImageUpload> images, {
                required String ocrProvider,
                required bool sameSupplementBatch,
              }) async {
                uploadedImages = images;
              },
        ),
      ),
    );
    await tester.pump(const Duration(seconds: 1));

    await tester.tap(find.byIcon(Icons.photo_library_rounded));
    await tester.pump();
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();

    expect(find.text('자동 분석'), findsOneWidget);
    final Finder analyzeButton = find.byKey(
      const ValueKey('supplement-preview-analyze'),
    );
    await tester.ensureVisible(analyzeButton);
    await tester.pump();
    final TextButton textButton = tester.widget<TextButton>(
      find.descendant(of: analyzeButton, matching: find.byType(TextButton)),
    );
    await tester.runAsync(() async {
      textButton.onPressed!();
      await Future<void>.delayed(const Duration(milliseconds: 100));
    });
    await tester.pumpAndSettle();

    expect(singleImagePath, isNull);
    expect(uploadedImages, isNotNull);
    expect(uploadedImages, hasLength(1));
    expect(uploadedImages!.single.role, 'supplement_facts');
  });

  testWidgets('meal preview calls the real meal analysis callback', (
    WidgetTester tester,
  ) async {
    await _usePhoneSurface(tester);
    final File source = _writeTinyPng();
    final _FakeImagePicker picker = _FakeImagePicker(source.path);
    String? analyzedPath;
    String? supplementPath;

    await tester.pumpWidget(
      MaterialApp(
        home: CameraScreen(
          initialMode: 'meal',
          imagePicker: picker,
          onAnalyzeSupplementImage:
              (String imagePath, {required String ocrProvider}) async {
                supplementPath = imagePath;
              },
          onAnalyzeMealImage: (String imagePath) async {
            analyzedPath = imagePath;
          },
        ),
      ),
    );
    await tester.pump(const Duration(seconds: 1));

    await tester.tap(find.byIcon(Icons.photo_library_rounded));
    await tester.pump();
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();

    expect(find.text('사진 추가'), findsNothing);
    expect(find.text('분석하기'), findsOneWidget);
    final Finder analyzeButton = find.byKey(
      const ValueKey('supplement-preview-analyze'),
    );
    await tester.ensureVisible(analyzeButton);
    await tester.pump();
    final TextButton textButton = tester.widget<TextButton>(
      find.descendant(of: analyzeButton, matching: find.byType(TextButton)),
    );
    await tester.runAsync(() async {
      textButton.onPressed!();
      await Future<void>.delayed(const Duration(milliseconds: 100));
    });
    await tester.pumpAndSettle();

    expect(analyzedPath, isNotNull);
    expect(supplementPath, isNull);
    expect(find.textContaining('endpoint는 아직 연결 전'), findsNothing);
  });

  testWidgets('preview shows the two quality check rows (figma 912:46)', (
    WidgetTester tester,
  ) async {
    await _usePhoneSurface(tester);
    final File source = _writeTinyPng();
    final _FakeImagePicker picker = _FakeImagePicker(source.path);

    await tester.pumpWidget(
      MaterialApp(
        home: CameraScreen(
          imagePicker: picker,
          onAnalyzeSupplementImage:
              (String imagePath, {required String ocrProvider}) async {},
        ),
      ),
    );
    await tester.pump(const Duration(seconds: 1));

    await tester.tap(find.byIcon(Icons.photo_library_rounded));
    await tester.pump();
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(seconds: 1));
    });
    await tester.pumpAndSettle();

    expect(find.text('미리보기'), findsOneWidget);
    // 두 품질 체크 행(선명도/밝기)이 노출된다 — 소프트 안내(차단 아님).
    expect(find.text('선명도'), findsOneWidget);
    expect(find.text('밝기'), findsOneWidget);
    // 안내일 뿐 분석하기 버튼은 그대로 활성(차단 아님).
    expect(find.text('분석하기'), findsOneWidget);
  });

  testWidgets('capture guide modal shows once and persists 다시 보지 않기', (
    WidgetTester tester,
  ) async {
    await _usePhoneSurface(tester);
    SharedPreferences.setMockInitialValues(<String, Object>{});
    final LocalPrefs prefs = await LocalPrefs.create();

    await tester.pumpWidget(
      MaterialApp(
        home: CameraScreen(
          localPrefs: prefs,
          onAnalyzeSupplementImage:
              (String imagePath, {required String ocrProvider}) async {},
        ),
      ),
    );
    // 카메라 프리뷰 루프가 계속 돌아 pumpAndSettle 이 끝나지 않으므로
    // 명시 프레임으로 모달(post-frame 표출)을 띄운다.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    // figma 920:23 — 첫 진입 1회 가이드 모달.
    expect(find.text('영양제 촬영 팁'), findsOneWidget);
    expect(find.text('프레임 안에 담아 주세요'), findsOneWidget);

    // '다시 보지 않기' 체크 후 촬영 시작 → 모드별 즉시 영속.
    await tester.tap(find.text('다시 보지 않기'));
    await tester.pump();
    await tester.tap(find.text('촬영 시작'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.text('영양제 촬영 팁'), findsNothing);
    // '다시 보지 않기' 선택은 모드별로 즉시 영속된다.
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(milliseconds: 50));
    });
    expect(prefs.captureGuideDismissed('supplement'), isTrue);
  });

  testWidgets('capture guide modal is skipped when already dismissed', (
    WidgetTester tester,
  ) async {
    await _usePhoneSurface(tester);
    SharedPreferences.setMockInitialValues(<String, Object>{
      'capture.guide.dismissed.supplement': true,
    });
    final LocalPrefs prefs = await LocalPrefs.create();

    await tester.pumpWidget(
      MaterialApp(
        home: CameraScreen(
          localPrefs: prefs,
          onAnalyzeSupplementImage:
              (String imagePath, {required String ocrProvider}) async {},
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('영양제 촬영 팁'), findsNothing);
  });

  testWidgets(
    'supplement mode keeps the batch toggle but drops the slot strip',
    (WidgetTester tester) async {
      await _usePhoneSurface(tester);

      await tester.pumpWidget(
        MaterialApp(
          home: CameraScreen(
            onAnalyzeSupplementImage:
                (String imagePath, {required String ocrProvider}) async {},
          ),
        ),
      );
      await tester.pump(const Duration(seconds: 1));

      // 묶음 의도 토글은 유지된다.
      expect(find.text('한 영양제 묶음'), findsOneWidget);
      expect(find.text('서로 다른 영양제'), findsOneWidget);

      // 앞면/성분표 2슬롯 칩은 제거됐다(figma 947:23 슬롯 UI 삭제).
      expect(
        find.byKey(const ValueKey<String>('two-slot-front')),
        findsNothing,
      );
      expect(
        find.byKey(const ValueKey<String>('two-slot-facts')),
        findsNothing,
      );
    },
  );
}

Future<void> _usePhoneSurface(WidgetTester tester) async {
  await tester.binding.setSurfaceSize(const Size(390, 844));
  addTearDown(() => tester.binding.setSurfaceSize(null));
}

File _writeTinyPng() {
  final File file = File(
    '${Directory.systemTemp.path}/lemon_camera_test_${DateTime.now().microsecondsSinceEpoch}.png',
  );
  file.writeAsBytesSync(base64Decode(_tinyPngBase64));
  return file;
}

const String _tinyPngBase64 =
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=';

const String _testFrameJpegBase64 =
    '/9j/4AAQSkZJRgABAgAAAQABAAD//gAQTGF2YzYyLjExLjEwMAD/2wBDAAgEBAQEBAUFBQUFBQYGBgYGBgYGBgYGBgYHBwcICAgHBwcGBgcHCAgICAkJCQgICAgJCQoKCgwMCwsODg4RERT/xABLAAEBAAAAAAAAAAAAAAAAAAAACAEBAAAAAAAAAAAAAAAAAAAAABABAAAAAAAAAAAAAAAAAAAAABEBAAAAAAAAAAAAAAAAAAAAAP/AABEIAAIAAgMBIgACEQADEQD/2gAMAwEAAhEDEQA/AJ/AB//Z';

class _FakeImagePicker extends ImagePicker {
  _FakeImagePicker(
    this.path, {
    List<String>? multiPaths,
    LostDataResponse? lostDataResponse,
  }) : multiPaths = multiPaths ?? <String>[path],
       _lostDataResponse = lostDataResponse ?? LostDataResponse.empty();

  final String path;
  final List<String> multiPaths;
  final LostDataResponse _lostDataResponse;
  ImageSource? lastSource;
  double? lastMaxWidth;
  int? lastImageQuality;
  bool? lastRequestFullMetadata;
  int multiPickCount = 0;
  int? lastMultiLimit;

  @override
  Future<XFile?> pickImage({
    required ImageSource source,
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
    CameraDevice preferredCameraDevice = CameraDevice.rear,
    bool requestFullMetadata = true,
  }) {
    lastSource = source;
    lastMaxWidth = maxWidth;
    lastImageQuality = imageQuality;
    lastRequestFullMetadata = requestFullMetadata;
    return Future<XFile?>.value(_xfileFromPath(path));
  }

  @override
  Future<List<XFile>> pickMultiImage({
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
    int? limit,
    bool requestFullMetadata = true,
  }) {
    multiPickCount += 1;
    lastMaxWidth = maxWidth;
    lastImageQuality = imageQuality;
    lastRequestFullMetadata = requestFullMetadata;
    lastMultiLimit = limit;
    final Iterable<String> selectedPaths = limit == null
        ? multiPaths
        : multiPaths.take(limit);
    return Future<List<XFile>>.value(
      selectedPaths.map(_xfileFromPath).toList(growable: false),
    );
  }

  @override
  Future<LostDataResponse> retrieveLostData() {
    return Future<LostDataResponse>.value(_lostDataResponse);
  }

  XFile _xfileFromPath(String imagePath) {
    return XFile(imagePath, name: 'source.png', mimeType: 'image/png');
  }
}
