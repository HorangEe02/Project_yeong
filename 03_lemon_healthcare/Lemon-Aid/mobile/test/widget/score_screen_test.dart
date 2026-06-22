import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:lemon_aid_mobile/app_controller.dart';
import 'package:lemon_aid_mobile/core/api/api_client.dart';
import 'package:lemon_aid_mobile/features/ai_coaching/ai_coaching_repository.dart';
import 'package:lemon_aid_mobile/features/analysis_trend/analysis_trend_repository.dart';
import 'package:lemon_aid_mobile/features/consent/consent_models.dart';
import 'package:lemon_aid_mobile/features/dashboard/dashboard_models.dart';
import 'package:lemon_aid_mobile/features/dashboard/home_models.dart';
import 'package:lemon_aid_mobile/features/nutrition/kdri_models.dart';
import 'package:lemon_aid_mobile/features/supplements/comprehensive_analysis_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_models.dart';
import 'package:lemon_aid_mobile/features/records/food_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_repository.dart';
import 'package:lemon_aid_mobile/screens/score_screen.dart';
import 'package:lemon_aid_mobile/widgets/common/medical_disclaimer.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FakeClient extends http.BaseClient {
  _FakeClient(this.handler);

  final Future<http.StreamedResponse> Function(http.Request request) handler;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    return handler(request as http.Request);
  }
}

http.StreamedResponse _jsonResponse(Map<String, dynamic> body, int status) {
  return http.StreamedResponse(
    Stream<List<int>>.value(utf8.encode(jsonEncode(body))),
    status,
    headers: const <String, String>{'content-type': 'application/json'},
  );
}

Map<String, dynamic> _coachingResponse() {
  return <String, dynamic>{
    'status': 'ok',
    'approval_status': 'not_required',
    'requires_user_approval': false,
    'message': '오늘 단백질이 조금 부족했어요.',
    'findings': <Map<String, dynamic>>[],
    'recommendations': <Map<String, dynamic>>[
      <String, dynamic>{
        'category': 'meal',
        'title': '저녁에 단백질 반찬 추가하기',
        'rationale': '오늘 단백질 섭취가 적었어요.',
        'priority': 1,
      },
    ],
    'actions': <Map<String, dynamic>>[],
    'safety_warnings': <String>[],
  };
}

AiCoachingRepository _coachingRepository({
  Future<http.StreamedResponse> Function(http.Request request)? handler,
}) {
  return AiCoachingRepository(
    apiClient: ApiClient(
      baseUrl: 'https://api.example.com/api/v1',
      httpClient: _FakeClient(
        handler ??
            (http.Request request) async =>
                _jsonResponse(_coachingResponse(), 200),
      ),
    ),
  );
}

Map<String, dynamic> _trendResponse(int days) {
  return <String, dynamic>{
    'results': List<Map<String, dynamic>>.generate(days, (int i) {
      final DateTime day = DateTime(2026, 6, 28).subtract(Duration(days: i));
      final String month = day.month.toString().padLeft(2, '0');
      final String date = day.day.toString().padLeft(2, '0');
      return <String, dynamic>{
        'id': '00000000-0000-0000-0000-${i.toString().padLeft(12, '0')}',
        'analysis_type': 'daily_health_score',
        'algorithm_version': 'daily-health-score-v1.0.0',
        'kdris_source_manifest_version': null,
        'created_at': '2026-06-28T00:00:00Z',
        'score': 60 + (i % 30),
        'measured_date': '${day.year}-$month-$date',
        'label': const <String>['good', 'moderate', 'warning'][i % 3],
      };
    }),
    'limit': 28,
    'offset': 0,
  };
}

AnalysisTrendRepository _trendRepository({int days = 28}) {
  return AnalysisTrendRepository(
    apiClient: ApiClient(
      baseUrl: 'https://api.example.com/api/v1',
      httpClient: _FakeClient(
        (http.Request request) async =>
            _jsonResponse(_trendResponse(days), 200),
      ),
    ),
  );
}

Future<AppController> _readyController() async {
  final AppController controller = AppController(
    repository: _ScoreRepository(scoreReady: true),
  );
  await controller.bootstrap();
  return controller;
}

Future<AppController> _notReadyController() async {
  final AppController controller = AppController(
    repository: _ScoreRepository(scoreReady: false),
  );
  await controller.bootstrap();
  return controller;
}

Future<void> _pump(
  WidgetTester tester, {
  required AppController controller,
  required AiCoachingRepository coaching,
  AnalysisTrendRepository? trend,
  DateTime Function()? now,
}) async {
  // 화면이 길어 기본 뷰포트(800×600)에서는 ListView가 하단 카드(추이/CTA)를
  // 지연 빌드로 생략한다 — 전체가 빌드되도록 세로를 충분히 키운다.
  tester.view.physicalSize = const Size(800, 2600);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(
    MaterialApp(
      home: ScoreScreen(
        controller: controller,
        coachingRepository: coaching,
        trendRepository: trend,
        now: now,
      ),
    ),
  );
  await tester.pumpAndSettle();
}

// 날짜 칩 → 데이트 피커에서 일자를 고른다 (기본 MaterialLocalizations = 영문 OK).
Future<void> _pickPastDay(
  WidgetTester tester,
  String chipLabel,
  String day,
) async {
  await tester.tap(find.text(chipLabel));
  await tester.pumpAndSettle();
  await tester.tap(find.text(day));
  await tester.pumpAndSettle();
  await tester.tap(find.text('OK'));
  await tester.pumpAndSettle();
}

// 화면 전체 금칙어·신뢰도 % 가드 (가이드 06 ⑦). 표준 면책 문장은 '진단'을
// 부정 맥락으로 포함하므로 정확 일치 화이트리스트로 제외한다
// (챗 면책 가드와 동일 규칙). 문구 단일 출처는 공용 위젯의 상수를 직접 참조해
// 위젯과 가드가 절대 어긋나지 않도록 한다.
void _expectNoForbiddenCopy(WidgetTester tester) {
  const String summaryDisclaimer = MedicalDisclaimer.summaryDisclaimerText;
  final Iterable<Text> texts = tester.widgetList<Text>(find.byType(Text));
  expect(texts, isNotEmpty);
  for (final Text text in texts) {
    final String data = text.data ?? '';
    if (data == summaryDisclaimer) {
      continue;
    }
    for (final String term in const <String>['진단', '처방', '치료', '효능']) {
      expect(data.contains(term), isFalse, reason: '금칙어 "$term" in "$data"');
    }
    expect(data.contains('%'), isFalse, reason: '% in "$data"');
  }
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues(<String, Object>{});
  });
  testWidgets('ready score renders ring, grade chip and lemon bot CTA', (
    WidgetTester tester,
  ) async {
    final AppController controller = await _readyController();
    await _pump(
      tester,
      controller: controller,
      coaching: _coachingRepository(),
    );

    expect(find.text('오늘의 분석'), findsOneWidget);
    expect(find.text('오늘의 종합 분석'), findsOneWidget);
    expect(find.text('78'), findsOneWidget);
    expect(find.text('좋아요'), findsOneWidget);
    expect(find.text('오늘 활동량이 좋아요.'), findsOneWidget);
    expect(find.text('레몬봇에게 물어보기'), findsOneWidget);
    // 잠금 추이 placeholder.
    expect(find.text('기록이 쌓이면 추이를 보여드려요'), findsOneWidget);
  });

  testWidgets('not_ready score shows record guidance and 촬영하기 CTA', (
    WidgetTester tester,
  ) async {
    final AppController controller = await _notReadyController();
    await _pump(
      tester,
      controller: controller,
      coaching: _coachingRepository(),
    );

    expect(find.text('기록을 추가하면 점수를 보여드려요.'), findsOneWidget);
    expect(find.text('촬영하기'), findsOneWidget);
    expect(find.text('좋아요'), findsNothing);
  });

  testWidgets('renders the daily-coaching checklist items', (
    WidgetTester tester,
  ) async {
    final AppController controller = await _readyController();
    await _pump(
      tester,
      controller: controller,
      coaching: _coachingRepository(),
    );

    expect(find.text('오늘 챙기면 좋은 1가지'), findsOneWidget);
    expect(find.text('저녁에 단백질 반찬 추가하기'), findsOneWidget);
  });

  testWidgets('checklist failure shows a retry affordance', (
    WidgetTester tester,
  ) async {
    final AppController controller = await _readyController();
    await _pump(
      tester,
      controller: controller,
      coaching: _coachingRepository(
        handler: (http.Request request) async =>
            _jsonResponse(<String, dynamic>{'detail': 'boom'}, 500),
      ),
    );

    expect(find.text('실천 리스트를 불러오지 못했어요'), findsOneWidget);
    expect(find.text('다시 시도'), findsOneWidget);
    // 화면 전체는 점수 카드를 유지한다.
    expect(find.text('오늘의 종합 분석'), findsOneWidget);
    expect(find.text('78'), findsOneWidget);
  });

  testWidgets('add-practice CTA appends a custom checklist item', (
    WidgetTester tester,
  ) async {
    final AppController controller = await _readyController();
    await _pump(
      tester,
      controller: controller,
      coaching: _coachingRepository(),
    );

    // figma 800:23 — 실천 리스트 카드 하단 풀폭 CTA.
    expect(find.text('오늘 실천 추가하기'), findsOneWidget);
    await tester.tap(find.text('오늘 실천 추가하기'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).last, '물 한 잔 더 마시기');
    await tester.tap(find.text('추가'));
    await tester.pumpAndSettle();

    expect(find.text('물 한 잔 더 마시기'), findsOneWidget);
    expect(find.text('내가 추가한 실천'), findsOneWidget);
    // 기존 코칭 1건 + 직접 추가 1건.
    expect(find.text('오늘 챙기면 좋은 2가지'), findsOneWidget);
  });

  testWidgets('trend card renders the 28-day chart when history is enough', (
    WidgetTester tester,
  ) async {
    final AppController controller = await _readyController();
    await _pump(
      tester,
      controller: controller,
      coaching: _coachingRepository(),
      trend: _trendRepository(),
    );

    expect(find.text('지난 4주 추이'), findsOneWidget);
    expect(find.text('기록이 쌓이면 추이를 보여드려요'), findsNothing);
    expect(find.text('점수는 기록 당시 기준이에요'), findsOneWidget);
    // 주차 보조 라벨 + 카드 하단 레몬봇 CTA (가이드 10 ③-P2 6 —
    // 종합 분석 카드 CTA 와 합쳐 2개).
    expect(find.text('1주'), findsOneWidget);
    expect(find.text('4주'), findsOneWidget);
    expect(find.text('레몬봇에게 물어보기'), findsNWidgets(2));
    expect(
      find.byWidgetPredicate(
        (Widget widget) =>
            widget is CustomPaint &&
            widget.painter.runtimeType.toString() == '_TrendChartPainter',
      ),
      findsOneWidget,
    );
  });

  testWidgets('trend card stays locked with fewer than 7 days of history', (
    WidgetTester tester,
  ) async {
    final AppController controller = await _readyController();
    await _pump(
      tester,
      controller: controller,
      coaching: _coachingRepository(),
      trend: _trendRepository(days: 3),
    );

    expect(find.text('기록이 쌓이면 추이를 보여드려요'), findsOneWidget);
    expect(find.text('점수는 기록 당시 기준이에요'), findsNothing);
  });

  testWidgets('safety warnings from the server render verbatim', (
    WidgetTester tester,
  ) async {
    final AppController controller = await _readyController();
    await _pump(
      tester,
      controller: controller,
      coaching: _coachingRepository(
        handler: (http.Request request) async =>
            _jsonResponse(<String, dynamic>{
              ..._coachingResponse(),
              'safety_warnings': <String>['영양제와 약을 함께 드시는 경우 전문가와 상담해 주세요.'],
            }, 200),
      ),
    );

    // 서버 문구 그대로 — 프론트 가공 금지 (가이드 06 §4.2-4).
    expect(find.text('영양제와 약을 함께 드시는 경우 전문가와 상담해 주세요.'), findsOneWidget);
  });

  testWidgets('checked practice restores from storage and persists on toggle', (
    WidgetTester tester,
  ) async {
    // 제목 기반 키 — 항목 순서가 바뀌어도 체크가 유지된다 (가이드 06 §4.2).
    SharedPreferences.setMockInitialValues(<String, Object>{
      'coaching_checked:2026-06-28': <String>['coach:저녁에 단백질 반찬 추가하기'],
    });
    final AppController controller = await _readyController();
    await _pump(
      tester,
      controller: controller,
      coaching: _coachingRepository(),
      now: () => DateTime(2026, 6, 28, 10),
    );

    final Text restored = tester.widget<Text>(find.text('저녁에 단백질 반찬 추가하기'));
    expect(restored.style?.decoration, TextDecoration.lineThrough);

    // 토글 해제가 저장소에 반영된다.
    await tester.tap(find.text('저녁에 단백질 반찬 추가하기'));
    await tester.pumpAndSettle();
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    expect(prefs.getStringList('coaching_checked:2026-06-28'), isEmpty);
  });

  testWidgets('past day shows history snapshot with read-only checks', (
    WidgetTester tester,
  ) async {
    final AppController controller = await _readyController();
    await _pump(
      tester,
      controller: controller,
      coaching: _coachingRepository(),
      trend: _trendRepository(),
      now: () => DateTime(2026, 6, 28, 10),
    );

    await _pickPastDay(tester, '6월 28일 (일)', '27');

    // 이력 스냅샷 — fixture 의 2026-06-27 점수(61) + measured_date 기준 캡션.
    expect(find.text('61'), findsOneWidget);
    expect(find.text('기록 당시 기준이에요'), findsWidgets);
    // 이력 캡션이 노출된 화면도 금칙어·% 가드를 통과한다 (가이드 ⑦-5).
    _expectNoForbiddenCopy(tester);
    // 과거 보기 상태에서만 '오늘' 복귀 칩, 추가 CTA 는 숨김 (가이드 06 §4.3).
    expect(find.text('오늘'), findsOneWidget);
    expect(find.text('오늘 실천 추가하기'), findsNothing);

    // 읽기 전용 — 탭해도 체크되지 않고 저장소에도 쓰지 않는다.
    await tester.tap(find.text('저녁에 단백질 반찬 추가하기'));
    await tester.pumpAndSettle();
    final Text row = tester.widget<Text>(find.text('저녁에 단백질 반찬 추가하기'));
    expect(row.style?.decoration, isNot(TextDecoration.lineThrough));
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    expect(
      prefs.getStringList('coaching_checked:2026-06-27') ?? const <String>[],
      isEmpty,
    );

    // '오늘' 칩으로 복귀하면 오늘 화면(추가 CTA 포함)으로 돌아온다.
    await tester.tap(find.text('오늘'));
    await tester.pumpAndSettle();
    expect(find.text('6월 28일 (일)'), findsOneWidget);
    expect(find.text('오늘 실천 추가하기'), findsOneWidget);
  });

  testWidgets('past day without history shows safe preparation hint', (
    WidgetTester tester,
  ) async {
    final AppController controller = await _readyController();
    await _pump(
      tester,
      controller: controller,
      coaching: _coachingRepository(),
      trend: _trendRepository(days: 3),
      now: () => DateTime(2026, 6, 28, 10),
    );

    await _pickPastDay(tester, '6월 28일 (일)', '25');

    expect(find.text('지난 날짜의 점수는 준비 중이에요. 실천 기록만 보여드려요.'), findsOneWidget);

    // 과거 보기 화면 전체 — 금칙어·신뢰도 % 가드 (가이드 06 ⑦ 신규 문구 2종 포함).
    _expectNoForbiddenCopy(tester);
  });

  testWidgets('trend card copy avoids forbidden medical terms and percent', (
    WidgetTester tester,
  ) async {
    final AppController controller = await _readyController();
    await _pump(
      tester,
      controller: controller,
      coaching: _coachingRepository(),
      trend: _trendRepository(),
    );

    final Finder trendCard = find
        .ancestor(of: find.text('지난 4주 추이'), matching: find.byType(Container))
        .first;
    final Iterable<Text> texts = tester.widgetList<Text>(
      find.descendant(of: trendCard, matching: find.byType(Text)),
    );
    expect(texts, isNotEmpty);
    for (final Text text in texts) {
      final String data = text.data ?? '';
      // 의료법 금칙어 가드 (가이드 06 ④).
      for (final String term in const <String>['진단', '처방', '치료', '효능']) {
        expect(data.contains(term), isFalse, reason: '금칙어 "$term" in "$data"');
      }
      // 신뢰도 % 미노출 가드 — 점수 숫자는 허용, % 기호는 어떤 형태로도 금지.
      expect(data.contains('%'), isFalse, reason: '% in "$data"');
    }
  });
}

class _ScoreRepository implements LemonAidRepository {
  _ScoreRepository({required this.scoreReady});

  final bool scoreReady;

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
  Future<DashboardSummary> fetchDashboardSummary({int days = 30}) async {
    return DashboardSummary(
      asOf: DateTime.utc(2026, 6, 1),
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
      healthScore: scoreReady
          ? const DashboardHealthScore(
              status: HealthScoreStatus.ready,
              score: 78,
              labelText: '좋아요',
              message: '오늘 활동량이 좋아요.',
            )
          : const DashboardHealthScore(status: HealthScoreStatus.notReady),
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
  Future<SupplementImpactPreviewResponse>
  fetchLatestSupplementRecommendation() {
    throw UnimplementedError();
  }

  ConsentStatus _consent(String consentType) {
    return ConsentStatus(
      consentType: consentType,
      policyVersion: 'test',
      title: consentType,
      required: true,
      granted: true,
      occurredAt: DateTime.utc(2026, 6, 1),
      revokedAt: null,
    );
  }

  @override
  Future<SupplementAnalysisPreview> analyzeSupplementImage(
    String imagePath, {
    String ocrProvider = 'configured',
  }) {
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
  Future<SupplementAnalysisSession> createSupplementAnalysisSession() {
    throw UnimplementedError();
  }

  @override
  Future<SupplementMultiImageAnalysisPreview> finalizeSupplementAnalysisSession(
    String analysisGroupId,
  ) {
    throw UnimplementedError();
  }

  @override
  Future<ConsentAction> grantConsent(String consentType) {
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
}
