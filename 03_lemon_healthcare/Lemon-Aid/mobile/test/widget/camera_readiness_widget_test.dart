import 'dart:convert';
import 'dart:io';

import 'package:camera/camera.dart' as camera;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/app_controller.dart';
import 'package:lemon_aid_mobile/core/api/api_error.dart';
import 'package:lemon_aid_mobile/features/consent/consent_models.dart';
import 'package:lemon_aid_mobile/features/dashboard/dashboard_models.dart';
import 'package:lemon_aid_mobile/features/dashboard/home_models.dart';
import 'package:lemon_aid_mobile/features/supplements/camera_readiness.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_flow_screen.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_models.dart';
import 'package:lemon_aid_mobile/features/records/food_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_repository.dart';
import 'package:lemon_aid_mobile/features/nutrition/kdri_models.dart';
import 'package:lemon_aid_mobile/features/supplements/comprehensive_analysis_models.dart';
import 'package:image_picker/image_picker.dart';

void main() {
  testWidgets('iOS runtime with no cameras keeps gallery endpoint path open', (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      repository: _CameraWidgetRepository(),
    );
    addTearDown(controller.dispose);
    await controller.bootstrap();

    await tester.pumpWidget(
      MaterialApp(
        home: SupplementFlowScreen(
          controller: controller,
          cameraReadinessProbe: CameraReadinessProbe(
            platform: TargetPlatform.iOS,
            loader: () async => const <camera.CameraDescription>[],
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('iOS 카메라 없음'), findsOneWidget);
    expect(find.textContaining('갤러리 이미지'), findsAtLeastNWidgets(1));

    final IconButton shutter = _iconButtonByTooltip(tester, '촬영');
    final IconButton gallery = _iconButtonByTooltip(tester, '갤러리');
    expect(shutter.onPressed, isNull);
    expect(gallery.onPressed, isNotNull);
  });

  testWidgets('Android runtime with camera enables direct capture control', (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      repository: _CameraWidgetRepository(),
    );
    addTearDown(controller.dispose);
    await controller.bootstrap();

    await tester.pumpWidget(
      MaterialApp(
        home: SupplementFlowScreen(
          controller: controller,
          cameraReadinessProbe: CameraReadinessProbe(
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
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Android 카메라 연결됨'), findsOneWidget);
    final IconButton shutter = _iconButtonByTooltip(tester, '촬영');
    expect(shutter.onPressed, isNotNull);
  });

  testWidgets('analysis endpoint errors remain visible on camera tab', (
    WidgetTester tester,
  ) async {
    final File image = _writeTinyPng();
    addTearDown(() {
      if (image.existsSync()) {
        image.deleteSync();
      }
    });
    final AppController controller = AppController(
      repository: _CameraWidgetRepository(
        analyzeError: const ApiError(
          statusCode: 403,
          code: 'consent_required',
          message: 'Consent is required.',
          requiredConsents: <String>['ocr_image_processing'],
        ),
      ),
    );
    addTearDown(controller.dispose);
    await controller.bootstrap();

    await tester.pumpWidget(
      MaterialApp(
        home: SupplementFlowScreen(
          controller: controller,
          imagePicker: _FakeImagePicker(image.path),
          cameraReadinessProbe: CameraReadinessProbe(
            platform: TargetPlatform.iOS,
            loader: () async => const <camera.CameraDescription>[],
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('갤러리'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('분석하기'));
    await tester.pumpAndSettle();

    expect(find.text('Request failed (403)'), findsOneWidget);
    expect(find.textContaining('Consent is required.'), findsOneWidget);
    expect(find.text('분석하기'), findsOneWidget);
  });

  testWidgets('default analysis issues a single configured OCR request', (
    WidgetTester tester,
  ) async {
    final File image = _writeTinyPng();
    addTearDown(() {
      if (image.existsSync()) {
        image.deleteSync();
      }
    });
    final _CameraWidgetRepository repository = _CameraWidgetRepository();
    final AppController controller = AppController(repository: repository);
    final _FakeImagePicker picker = _FakeImagePicker(image.path);
    addTearDown(controller.dispose);
    await controller.bootstrap();

    await tester.pumpWidget(
      MaterialApp(
        home: SupplementFlowScreen(
          controller: controller,
          imagePicker: picker,
          cameraReadinessProbe: CameraReadinessProbe(
            platform: TargetPlatform.android,
            loader: () async => const <camera.CameraDescription>[],
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('갤러리'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('분석하기'));
    await tester.pumpAndSettle();

    expect(repository.lastImagePath, image.path);
    // Default scan must reach the real flow with a SINGLE 'configured' request,
    // not a 4-provider fan-out (which tripped the backend rate limit on re-scan).
    expect(repository.ocrProviders, <String>['configured']);
    expect(picker.lastMaxWidth, 2400);
    expect(picker.lastImageQuality, 95);
    expect(find.text('Preview'), findsOneWidget);
  });

  testWidgets('gallery picker can upload several supplement images at once', (
    WidgetTester tester,
  ) async {
    final File imageA = _writeTinyPng();
    final File imageB = _writeTinyPng();
    final File imageC = _writeTinyPng();
    addTearDown(() {
      for (final File image in <File>[imageA, imageB, imageC]) {
        if (image.existsSync()) {
          image.deleteSync();
        }
      }
    });
    final _CameraWidgetRepository repository = _CameraWidgetRepository();
    final AppController controller = AppController(repository: repository);
    final _FakeImagePicker picker = _FakeImagePicker(
      imageA.path,
      multiPaths: <String>[imageA.path, imageB.path, imageC.path],
    );
    addTearDown(controller.dispose);
    await controller.bootstrap();

    await tester.pumpWidget(
      MaterialApp(
        home: SupplementFlowScreen(
          controller: controller,
          imagePicker: picker,
          cameraReadinessProbe: CameraReadinessProbe(
            platform: TargetPlatform.iOS,
            loader: () async => const <camera.CameraDescription>[],
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('갤러리'));
    await tester.pumpAndSettle();

    expect(picker.multiPickCount, 1);
    expect(picker.lastMultiLimit, 6);
    expect(picker.lastRequestFullMetadata, isFalse);
    expect(find.text('갤러리 사진 3장 선택됨'), findsOneWidget);
    expect(find.text('3장 분석하기'), findsOneWidget);

    await tester.tap(find.text('3장 분석하기'));
    await tester.pumpAndSettle();

    expect(repository.lastImageUploads, isNotNull);
    expect(repository.lastImageUploads, hasLength(3));
  });
}

IconButton _iconButtonByTooltip(WidgetTester tester, String tooltip) {
  return tester
      .widgetList<IconButton>(find.byType(IconButton))
      .singleWhere((IconButton button) => button.tooltip == tooltip);
}

class _FakeImagePicker extends ImagePicker {
  _FakeImagePicker(this.path, {List<String>? multiPaths})
    : multiPaths = multiPaths ?? <String>[path];

  final String path;
  final List<String> multiPaths;
  double? lastMaxWidth;
  int? lastImageQuality;
  bool? lastRequestFullMetadata;
  int? lastMultiLimit;
  int multiPickCount = 0;

  @override
  Future<XFile?> pickImage({
    required ImageSource source,
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
    CameraDevice preferredCameraDevice = CameraDevice.rear,
    bool requestFullMetadata = true,
  }) async {
    lastMaxWidth = maxWidth;
    lastImageQuality = imageQuality;
    lastRequestFullMetadata = requestFullMetadata;
    return XFile(path);
  }

  @override
  Future<List<XFile>> pickMultiImage({
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
    int? limit,
    bool requestFullMetadata = true,
  }) async {
    multiPickCount += 1;
    lastMaxWidth = maxWidth;
    lastImageQuality = imageQuality;
    lastRequestFullMetadata = requestFullMetadata;
    lastMultiLimit = limit;
    final Iterable<String> selectedPaths = limit == null
        ? multiPaths
        : multiPaths.take(limit);
    return selectedPaths
        .map((String path) => XFile(path))
        .toList(growable: false);
  }
}

class _CameraWidgetRepository implements LemonAidRepository {
  _CameraWidgetRepository({this.analyzeError});

  final ApiError? analyzeError;
  String? lastImagePath;
  List<SupplementImageUpload>? lastImageUploads;
  String? lastOcrProvider;
  final List<String> ocrProviders = <String>[];

  @override
  Future<SupplementAnalysisPreview> analyzeSupplementImage(
    String imagePath, {
    String ocrProvider = 'configured',
  }) async {
    lastImagePath = imagePath;
    lastOcrProvider = ocrProvider;
    ocrProviders.add(ocrProvider);
    final ApiError? error = analyzeError;
    if (error != null) {
      throw error;
    }
    return SupplementAnalysisPreview.fromJson(_previewResponse);
  }

  @override
  Future<MealImageAnalysisPreview> analyzeMealImage(
    String imagePath, {
    String mealType = 'unknown',
  }) {
    throw UnimplementedError();
  }

  @override
  Future<MealRecordResponse> confirmMealImagePreview(
    String mealId,
    MealConfirmationRequest request,
  ) {
    throw UnimplementedError();
  }

  @override
  Future<SupplementMultiImageAnalysisPreview> analyzeSupplementImagesOneShot(
    List<SupplementImageUpload> images, {
    String ocrProvider = 'configured',
    String mergeStrategy = 'single_product',
  }) => analyzeSupplementImages(images, ocrProvider: ocrProvider);

  @override
  Future<SupplementMultiImageAnalysisPreview> analyzeSupplementImages(
    List<SupplementImageUpload> images, {
    String ocrProvider = 'configured',
  }) async {
    lastImageUploads = images;
    lastOcrProvider = ocrProvider;
    ocrProviders.add(ocrProvider);
    return SupplementMultiImageAnalysisPreview(
      analysisGroupId: 'test-group',
      imageCount: images.length,
      previews: <SupplementAnalysisPreview>[
        SupplementAnalysisPreview.fromJson(_previewResponse),
      ],
      mergedPreview: SupplementAnalysisPreview.fromJson(_previewResponse),
      missingRequiredSections: const <String>[],
      actionRequired: 'review_required',
      pipelineMetadata: SupplementImagePipelineMetadata.intakeOnly,
      expiresAt: null,
    );
  }

  @override
  Future<SupplementAnalysisSession> createSupplementAnalysisSession() {
    throw UnimplementedError();
  }

  @override
  Future<SupplementMultiImageAnalysisPreview>
  uploadSupplementAnalysisSessionImage(
    String analysisGroupId,
    SupplementImageUpload image, {
    String ocrProvider = 'configured',
    String? clientRequestId,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<SupplementMultiImageAnalysisPreview> finalizeSupplementAnalysisSession(
    String analysisGroupId,
  ) {
    throw UnimplementedError();
  }

  @override
  Future<ComprehensiveDietAnalysis> analyzeComprehensive({
    required List<Map<String, Object?>> ingredients,
    Map<String, dynamic>? userProfile,
    String persona = 'B',
  }) async {
    return ComprehensiveDietAnalysis.empty;
  }

  @override
  Future<KdriLookupResult> lookupKdris({
    required int age,
    required String sex,
    String pregnancyStatus = 'none',
  }) async {
    return KdriLookupResult.empty;
  }

  @override
  Future<FoodCatalogList> searchFoods({
    String? q,
    String? cuisineCode,
    int limit = 50,
    int offset = 0,
  }) async {
    throw UnimplementedError();
  }

  @override
  Future<FoodCuisineList> fetchCuisines() async {
    throw UnimplementedError();
  }

  @override
  Future<List<SupplementCategory>> fetchSupplementCategories() async =>
      const <SupplementCategory>[];

  @override
  Future<void> deleteSupplement(String supplementId) async {
    throw UnimplementedError();
  }

  @override
  Future<void> deleteAnalysisResult(String resultId) async {
    throw UnimplementedError();
  }

  @override
  Future<MealRecordResponse> updateMealRecord(
    String mealId,
    MealConfirmationRequest request,
  ) async {
    throw UnimplementedError();
  }

  @override
  Future<void> deleteMealRecord(String mealId) async {
    throw UnimplementedError();
  }

  @override
  void close() {}

  @override
  Future<HomeMedicationsResult> fetchMedications() async {
    return HomeMedicationsResult.empty;
  }

  @override
  Future<HomeMedication> createMedication(MedicationCreateRequest request) {
    throw UnimplementedError();
  }

  @override
  Future<HomeMedication> deactivateMedication(String medicationId) {
    throw UnimplementedError();
  }

  @override
  Future<HomeMedication> reactivateMedication(String medicationId) {
    throw UnimplementedError();
  }

  @override
  Future<ConsentState> fetchConsents() async {
    return ConsentState(
      consents: <ConsentStatus>[
        _consent(AppController.ocrConsent),
        _consent(AppController.healthConsent),
      ],
    );
  }

  @override
  Future<ConsentAction> grantConsent(String consentType) async {
    return ConsentAction(
      consentType: consentType,
      policyVersion: 'test',
      granted: true,
      occurredAt: DateTime.utc(2026, 5, 25),
    );
  }

  @override
  Future<HomeMealsResult> fetchMeals({
    DateTime? from,
    DateTime? to,
    int limit = 50,
    int offset = 0,
  }) async {
    return HomeMealsResult.empty;
  }

  @override
  Future<HomeSupplementsResult> fetchSupplements({
    int limit = 50,
    int offset = 0,
  }) async {
    return HomeSupplementsResult.empty;
  }

  @override
  Future<DashboardSummary> fetchDashboardSummary({int days = 30}) async {
    return DashboardSummary(
      asOf: DateTime.utc(2026, 5, 25),
      nutrition: const DashboardNutritionSummary(
        dataStatus: 'ready',
        lowCount: 0,
        highCount: 0,
        datasetVersion: 'test',
      ),
      activity: const DashboardActivitySummary(
        dataStatus: 'not_ready',
        latestSteps: null,
        latestActivityScore: null,
      ),
      weight: const DashboardWeightSummary(
        dataStatus: 'not_ready',
        latestWeightKg: null,
        predictedWeightKg: null,
      ),
      supplements: const DashboardSupplementSummary(
        registeredCount: 0,
        requiresReviewCount: 0,
      ),
      disclaimers: const <String>[],
      algorithmVersion: 'test',
    );
  }

  @override
  Future<SupplementImpactPreviewResponse>
  fetchLatestSupplementRecommendation() {
    throw UnimplementedError();
  }

  @override
  Future<SupplementRecommendationExplainResponse>
  explainSupplementRecommendation(
    SupplementImpactPreviewResponse preview, {
    bool useLocalLlm = false,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<SupplementRecommendationExplainResponse> explainSupplementAnalysis(
    String analysisId, {
    bool useLocalLlm = false,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<SupplementAnalysisPreview> parseOcrText({
    required String analysisId,
    required SupplementOCRTextParseRequest request,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<SupplementImpactPreviewResponse> previewSupplementImpact(
    SupplementImpactPreviewRequest request,
  ) {
    throw UnimplementedError();
  }

  @override
  Future<UserSupplementResponse> registerSupplement(
    UserSupplementCreate request,
  ) {
    throw UnimplementedError();
  }

  ConsentStatus _consent(String consentType) {
    return ConsentStatus(
      consentType: consentType,
      policyVersion: 'test',
      title: consentType,
      required: true,
      granted: true,
      occurredAt: DateTime.utc(2026, 5, 25),
      revokedAt: null,
    );
  }
}

final Map<String, Object?> _previewResponse = <String, Object?>{
  'analysis_id': '00000000-0000-0000-0000-000000000010',
  'status': 'requires_confirmation',
  'parsed_product': <String, Object?>{},
  'ingredient_candidates': <Object?>[],
  'layout_available': false,
  'layout_fallback_reason': 'test',
  'label_sections': <Object?>[],
  'pipeline_metadata': <String, Object?>{
    'intake_completed': true,
    'vision_roi_used': false,
    'ocr_provider': 'paddleocr_local',
    'llm_parser_used': false,
    'raw_image_stored': false,
    'raw_ocr_text_stored': false,
  },
  'low_confidence_fields': <Object?>[],
  'warnings': <Object?>[],
  'algorithm_version': 'test',
  'source_manifest_version': null,
  'expires_at': '2026-05-25T00:00:00Z',
};

File _writeTinyPng() {
  final Directory directory = Directory.systemTemp.createTempSync(
    'lemon-aid-camera-widget-test-',
  );
  final File file = File('${directory.path}/label.png');
  addTearDown(() {
    if (directory.existsSync()) {
      directory.deleteSync(recursive: true);
    }
  });
  file.writeAsBytesSync(
    base64Decode(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=',
    ),
  );
  return file;
}
