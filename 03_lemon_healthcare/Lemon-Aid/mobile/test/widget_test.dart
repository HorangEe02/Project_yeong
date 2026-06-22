import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/app.dart';
import 'package:lemon_aid_mobile/app_controller.dart';
import 'package:lemon_aid_mobile/core/storage/local_prefs.dart';
import 'package:lemon_aid_mobile/features/consent/consent_models.dart';
import 'package:lemon_aid_mobile/features/dashboard/dashboard_models.dart';
import 'package:lemon_aid_mobile/features/dashboard/home_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_models.dart';
import 'package:lemon_aid_mobile/features/records/food_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_repository.dart';
import 'package:lemon_aid_mobile/features/nutrition/kdri_models.dart';
import 'package:lemon_aid_mobile/features/supplements/comprehensive_analysis_models.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('renders source dashboard shell with backend session wiring', (
    WidgetTester tester,
  ) async {
    await _pumpReadyShell(tester);

    expect(find.text('레몬'), findsOneWidget);
    expect(find.text('에이드'), findsOneWidget);
    // 점수 ready → label_text 칩('좋아요')과 점수 코멘트가 보인다.
    expect(find.text('좋아요'), findsOneWidget);
    expect(find.text('오늘의 분석'), findsOneWidget);
    expect(find.text('홈'), findsOneWidget);
    expect(find.text('챗'), findsOneWidget);
    expect(find.text('분석'), findsOneWidget);
    expect(find.text('설정'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.add_rounded).last);
    await tester.pumpAndSettle();
    // Figma 팔레트 라벨 — 짧게 (영양제 / 식단 / 복약)
    expect(find.text('영양제'), findsOneWidget);
    expect(find.text('식단'), findsOneWidget);
    await tester.tapAt(const Offset(20, 20));
    await tester.pumpAndSettle();

    await tester.drag(find.byType(Scrollable).first, const Offset(0, -500));
    await tester.pumpAndSettle();
    // 정적 '최근 분석' 섹션을 실데이터 '식단 관리' 섹션으로 교체.
    expect(find.text('식단 관리'), findsOneWidget);
  });

  testWidgets('quick action supplement label opens supplement camera mode', (
    WidgetTester tester,
  ) async {
    await _pumpReadyShell(tester);

    await tester.tap(find.byIcon(Icons.add_rounded).last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('영양제'));
    await tester.pump(const Duration(seconds: 1));

    expect(find.text('성분표를 테두리 안에 맞춰주세요'), findsOneWidget);
  });

  testWidgets('quick action meal label opens meal camera mode', (
    WidgetTester tester,
  ) async {
    await _pumpReadyShell(tester);

    await tester.tap(find.byIcon(Icons.add_rounded).last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('식단'));
    await tester.pump(const Duration(seconds: 1));

    expect(find.text('음식이 테두리 안에 들어오게 맞춰주세요'), findsOneWidget);
  });

  testWidgets('settings tab renders account consent and OCR test sections', (
    WidgetTester tester,
  ) async {
    await _pumpReadyShell(tester);

    await tester.tap(find.text('설정'));
    await tester.pumpAndSettle();

    expect(find.text('내 건강'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('필수 동의 상태'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('필수 동의 상태'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('OCR 테스트'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('OCR 테스트'), findsOneWidget);
    expect(find.text('갤러리 입력'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('API access'),
      -300,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('API access'), findsOneWidget);
  });
}

Future<void> _pumpReadyShell(WidgetTester tester) async {
  // 첫 실행 온보딩이 끼어들지 않도록 본 적이 있는 상태로 시드한다(스플래시 분기).
  SharedPreferences.setMockInitialValues(<String, Object>{});
  await (await LocalPrefs.create()).setOnboardingSeen();
  await tester.pumpWidget(LemonAidApp(repository: _FakeRepository()));
  await tester.pump();
  expect(
    find.byWidgetPredicate((Widget widget) {
      final Object? image = widget is Image ? widget.image : null;
      return image is AssetImage &&
          image.assetName == 'assets/mascot/gold-poster.png';
    }),
    findsOneWidget,
  );

  await tester.pump(const Duration(seconds: 6));
  await tester.pumpAndSettle();
}

class _FakeRepository implements LemonAidRepository {
  @override
  Future<SupplementAnalysisPreview> analyzeSupplementImage(
    String imagePath, {
    String ocrProvider = 'configured',
  }) {
    throw UnimplementedError();
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
  }) {
    throw UnimplementedError();
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
      asOf: DateTime.utc(2026, 5, 15),
      nutrition: const DashboardNutritionSummary(
        dataStatus: 'ready',
        lowCount: 1,
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
        registeredCount: 2,
        requiresReviewCount: 0,
      ),
      disclaimers: const <String>['Review OCR output before saving.'],
      algorithmVersion: 'test',
      healthScore: const DashboardHealthScore(
        status: HealthScoreStatus.ready,
        score: 78,
        labelText: '좋아요',
        message: '오늘 활동량이 좋아요.',
      ),
    );
  }

  @override
  Future<ConsentAction> grantConsent(String consentType) async {
    return ConsentAction(
      consentType: consentType,
      policyVersion: 'test',
      granted: true,
      occurredAt: DateTime.utc(2026, 5, 15),
    );
  }

  @override
  Future<SupplementAnalysisPreview> parseOcrText({
    required String analysisId,
    required SupplementOCRTextParseRequest request,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<UserSupplementResponse> registerSupplement(
    UserSupplementCreate request,
  ) {
    throw UnimplementedError();
  }

  @override
  Future<SupplementImpactPreviewResponse> previewSupplementImpact(
    SupplementImpactPreviewRequest request,
  ) {
    throw UnimplementedError();
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

  ConsentStatus _consent(String consentType) {
    return ConsentStatus(
      consentType: consentType,
      policyVersion: 'test',
      title: consentType,
      required: true,
      granted: true,
      occurredAt: DateTime.utc(2026, 5, 15),
      revokedAt: null,
    );
  }
}
