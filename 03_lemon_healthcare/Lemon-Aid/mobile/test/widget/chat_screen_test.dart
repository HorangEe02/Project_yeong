import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/app_controller.dart';
import 'package:lemon_aid_mobile/core/api/api_client.dart';
import 'package:lemon_aid_mobile/features/chat/chat_models.dart';
import 'package:lemon_aid_mobile/features/chat/chat_repository.dart';
import 'package:lemon_aid_mobile/features/consent/consent_models.dart';
import 'package:lemon_aid_mobile/features/dashboard/dashboard_models.dart';
import 'package:lemon_aid_mobile/features/dashboard/home_models.dart';
import 'package:lemon_aid_mobile/features/nutrition/kdri_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_models.dart';
import 'package:lemon_aid_mobile/features/records/food_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_repository.dart';
import 'package:lemon_aid_mobile/features/supplements/comprehensive_analysis_models.dart';
import 'package:lemon_aid_mobile/screens/chat_screen.dart';

const List<String> _bannedTerms = <String>['진단', '처방', '치료', '효능'];

/// Fake chat repository returning a queue of canned responses.
class _FakeChatRepository extends ChatRepository {
  _FakeChatRepository(this._responses)
    : super(apiClient: ApiClient(baseUrl: 'https://example.test/api/v1'));

  final List<ChatbotResponse> _responses;
  int _index = 0;

  @override
  Future<ChatbotResponse> sendMessage({
    required String message,
    required List<ChatTurn> conversation,
    Map<String, dynamic>? analysisRunApproval,
  }) async {
    final ChatbotResponse response =
        _responses[_index.clamp(0, _responses.length - 1)];
    _index += 1;
    return response;
  }
}

ChatbotResponse _approvedTodayResponse() {
  return ChatbotResponse.fromJson(<String, dynamic>{
    'request_id': 'r-approved',
    'message': '오늘 기록을 바탕으로 정리했어요.',
    'provider': 'sglang',
    'used_tools': <String>['app_health_analysis'],
    'answerability': 'answerable',
    'today_analysis': <String, dynamic>{
      'status': 'ready_for_analysis',
      'score': 76,
      'score_name': '오늘 현재 분석 점수',
      'strengths': <String>['food_records_available'],
      'priority_adjustments': <String>['sodium_high'],
      'recommended_foods': <String>['grilled fish'],
      'checklist_actions': <String>['check soup and sauce intake'],
      'missing_records': <String>[],
      'stale': false,
    },
    'checklist_candidates': <Map<String, dynamic>>[
      <String, dynamic>{
        'candidate_id': 'checklist-candidate-v1-1',
        'kind': 'today_practice',
        'title': '국물·소스 섭취 확인하기',
        'source': 'today_analysis',
        'approval_state': 'approval_required',
        'side_effect': 'none',
        'deferred_action': 'add_today_practice',
      },
    ],
    'ctas': <String>['ask_about_this_result'],
    'approval_preview': <String, dynamic>{
      'schema_version': 'approval-preview-v1',
      'approval_state': 'approved',
      'analysis_kind': 'today_analysis',
      'side_effects': <String>['analysis_result_persisted'],
    },
  });
}

ChatbotResponse _approvedPendingResponse() {
  return ChatbotResponse.fromJson(<String, dynamic>{
    'request_id': 'r-pending',
    'message': '아직 기록이 더 필요해요.',
    'provider': 'sglang',
    'used_tools': <String>['app_health_analysis'],
    'answerability': 'answerable',
    'today_analysis': <String, dynamic>{
      'status': 'analysis_pending',
      'score': null,
      'score_name': '오늘 현재 분석 점수',
      'missing_records': <String>['food_records'],
    },
    'approval_preview': <String, dynamic>{
      'approval_state': 'approved',
      'analysis_kind': 'today_analysis',
      'side_effects': <String>['analysis_result_persisted'],
    },
  });
}

ChatbotResponse _plainAnswerResponse() {
  return ChatbotResponse.fromJson(<String, dynamic>{
    'request_id': 'r-plain',
    'message': '비타민 D는 햇빛으로도 만들어져요.',
    'provider': 'sglang',
    'used_tools': <String>['chatbot_agent'],
    'answerability': 'answerable',
    // Snapshot blocks ride along on every response but must not render here.
    'today_analysis': <String, dynamic>{
      'status': 'ready_for_analysis',
      'score': 80,
      'score_name': '오늘 현재 분석 점수',
    },
    'approval_preview': <String, dynamic>{
      'approval_state': 'not_required',
      'side_effects': <String>[],
    },
  });
}

ChatbotResponse _wikiSourcesResponse() {
  return ChatbotResponse.fromJson(<String, dynamic>{
    'request_id': 'r-wiki',
    'message': '아스코르브산은 식사로도 충분히 얻을 수 있어요.',
    'provider': 'gemma_wiki_rag',
    'used_tools': <String>['llm_wiki_rag'],
    'answerability': 'answered_from_wiki',
    'source_families': <String>['lemon_wiki'],
    'sources': <Map<String, dynamic>>[
      // Backend sends `source_title` (heading); the "1.2 " section number is
      // stripped for the chip and the raw `source_id` path is never shown.
      <String, dynamic>{
        'source_id':
            'raw/references/2026-06-05-chronic-hepatitis-bc-cancer-research.md',
        'source_title': '1.2 비타민 C',
        'source_family': 'lemon_wiki',
        'review_status': 'reference',
      },
      // A heading containing '/' must be kept (not mistaken for a file path).
      <String, dynamic>{
        'source_id': 'raw/references/2026-06-05-copd-intake-research.md',
        'source_title': '비타민C (Vitamin C / ascorbic acid)',
        'source_family': 'lemon_wiki',
        'review_status': 'reference',
      },
      // A very long heading must ellipsize within the chip, never overflow.
      <String, dynamic>{
        'source_id': 'wiki/concepts/water-soluble-vitamin-supplements.md',
        'source_title':
            '수용성 비타민 보충제와 만성 질환 관리에 관한 아주 길고 긴 참고 섹션 제목 예시이며 '
            '추가 설명 텍스트가 계속 이어져서 한 줄을 훌쩍 넘기는 경우를 검증하기 위한 문자열입니다',
        'source_family': 'lemon_wiki',
        'review_status': 'reference',
      },
    ],
    'approval_preview': <String, dynamic>{
      'approval_state': 'not_required',
      'side_effects': <String>[],
    },
  });
}

void main() {
  testWidgets('consumes supplement explanation draft as chat messages', (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      repository: _ChatDraftRepository(),
    );

    await controller.registerSupplement(_registrationRequest());
    expect(controller.queueSupplementExplanationForChat(), isTrue);
    expect(
      controller.pendingChatExplanationDraft?.userPrompt,
      contains('Vitamin D 성분과 함유량'),
    );
    expect(
      controller.pendingChatExplanationDraft?.assistantMessage,
      contains('라벨에서 사용자가 확인한 성분 기준'),
    );

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(home: ChatScreen(controller: controller)),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('성분과 함유량'), findsOneWidget);
    expect(find.textContaining('Vitamin D: 25 mcg'), findsOneWidget);
    expect(find.textContaining('내 정보 기준 확인'), findsOneWidget);
    expect(find.textContaining('성분: Vitamin D 25 mcg'), findsOneWidget);
    expect(controller.pendingChatExplanationDraft, isNull);
  });

  testWidgets(
    'renders the inline analysis card after an approved+persisted response',
    (WidgetTester tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: ChatScreen(
              repository: _FakeChatRepository(<ChatbotResponse>[
                _approvedTodayResponse(),
              ]),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), '오늘 분석해줘');
      await tester.testTextInput.receiveAction(TextInputAction.send);
      await tester.pumpAndSettle();

      // Card chrome + score + grade chip (no percent) + disclaimer.
      expect(find.text('분석 결과 정리'), findsOneWidget);
      expect(find.text('76'), findsOneWidget);
      expect(find.text('좋음'), findsOneWidget);
      expect(find.text('잘하고 있어요'), findsOneWidget);
      expect(find.text('이런 점을 살펴보면 좋아요'), findsOneWidget);
      expect(find.text('건강 참고용이며 의료 행위를 대신하지 않아요.'), findsOneWidget);
      // Checklist candidate is shown (display-only).
      expect(find.text('국물·소스 섭취 확인하기'), findsOneWidget);
      expect(find.text('오늘 실천에 추가해볼까요?'), findsOneWidget);

      _expectNoBannedTermsOrPercent(tester);
    },
  );

  testWidgets(
    'shows a record-completion notice instead of a score when pending',
    (WidgetTester tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            home: ChatScreen(
              repository: _FakeChatRepository(<ChatbotResponse>[
                _approvedPendingResponse(),
              ]),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField), '오늘 분석해줘');
      await tester.testTextInput.receiveAction(TextInputAction.send);
      await tester.pumpAndSettle();

      expect(find.text('분석 결과 정리'), findsOneWidget);
      expect(find.text('기록을 조금 더 채우면 분석해드릴게요.'), findsOneWidget);
      expect(find.textContaining('식사 기록'), findsOneWidget);
      // No fabricated score: the grade chips must be absent.
      expect(find.text('좋음'), findsNothing);
      expect(find.text('보통'), findsNothing);
      expect(find.text('확인 필요'), findsNothing);

      _expectNoBannedTermsOrPercent(tester);
    },
  );

  testWidgets('does not render the analysis card for an ordinary chat answer', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          home: ChatScreen(
            repository: _FakeChatRepository(<ChatbotResponse>[
              _plainAnswerResponse(),
            ]),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), '비타민 D 알려줘');
    await tester.testTextInput.receiveAction(TextInputAction.send);
    await tester.pumpAndSettle();

    expect(find.text('비타민 D는 햇빛으로도 만들어져요.'), findsOneWidget);
    // Snapshot rides along but the card stays hidden on non-approval turns.
    expect(find.text('분석 결과 정리'), findsNothing);
    expect(find.text('80'), findsNothing);
  });

  testWidgets('standing compliance disclaimer is always visible above input', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          home: ChatScreen(
            repository: _FakeChatRepository(<ChatbotResponse>[]),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // figma S-11 773:23 — 입력창 위 상시 면책 (컴플라이언스 §14).
    expect(find.text(_allowedStandingDisclaimer), findsOneWidget);
  });

  testWidgets('renders wiki source chips cleanly without RenderFlex overflow', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          home: ChatScreen(
            repository: _FakeChatRepository(<ChatbotResponse>[
              _wikiSourcesResponse(),
            ]),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), '비타민 C 먹어도 돼?');
    await tester.testTextInput.receiveAction(TextInputAction.send);
    await tester.pumpAndSettle();

    // The original bug: a long source row overflowed to the right. The chip now
    // clamps + ellipsizes, so no layout overflow exception is thrown.
    expect(tester.takeException(), isNull);
    // Heading shows with the "1.2 " section number stripped.
    expect(find.text('비타민 C'), findsOneWidget);
    // A heading containing '/' is preserved, not treated as a path.
    expect(find.text('비타민C (Vitamin C / ascorbic acid)'), findsOneWidget);
    // The raw file path must never surface as a chip label.
    expect(find.textContaining('raw/references/'), findsNothing);
    expect(find.text('근거'), findsOneWidget);
  });
}

// 컴플라이언스 표준 면책은 금칙어를 부정형으로 포함하므로(상시 면책 라인),
// 정확히 이 문장일 때만 스캔에서 제외한다 — 부분 일치 허용 금지.
const String _allowedStandingDisclaimer = '레몬봇 안내는 일반 참고용이에요. 진단을 대신하지 않아요.';

void _expectNoBannedTermsOrPercent(WidgetTester tester) {
  final Iterable<Text> texts = tester.widgetList<Text>(find.byType(Text));
  for (final Text widget in texts) {
    final String value = widget.data ?? '';
    if (value == _allowedStandingDisclaimer) {
      continue;
    }
    for (final String banned in _bannedTerms) {
      expect(
        value.contains(banned),
        isFalse,
        reason: 'banned term "$banned" surfaced in "$value"',
      );
    }
    expect(
      value.contains('%'),
      isFalse,
      reason: 'percent must not be exposed in "$value"',
    );
  }
}

UserSupplementCreate _registrationRequest() {
  return const UserSupplementCreate(
    analysisId: 'analysis-1',
    displayName: 'Vitamin D',
    manufacturer: 'Lemon Lab',
    ingredients: <UserSupplementIngredientInput>[
      UserSupplementIngredientInput(
        displayName: 'Vitamin D',
        nutrientCode: 'vitamin_d',
        amount: 25,
        unit: 'mcg',
        confidence: 0.92,
        source: 'ocr_llm_preview',
      ),
    ],
    serving: SupplementServing(amount: 1, unit: 'capsule', dailyServings: 1),
    intakeSchedule: SupplementIntakeSchedule(
      frequency: 'daily',
      timeOfDay: <String>['morning'],
    ),
  );
}

class _ChatDraftRepository implements LemonAidRepository {
  @override
  Future<UserSupplementResponse> registerSupplement(
    UserSupplementCreate request,
  ) async {
    return UserSupplementResponse(
      id: 'supplement-1',
      displayName: request.displayName,
      manufacturer: request.manufacturer,
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
      asOf: DateTime.utc(2026, 6, 1),
      nutrition: const DashboardNutritionSummary(
        dataStatus: 'not_ready',
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
        registeredCount: 1,
        requiresReviewCount: 0,
      ),
      disclaimers: const <String>[],
      algorithmVersion: 'test',
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
  Future<SupplementImpactPreviewResponse>
  fetchLatestSupplementRecommendation() {
    throw UnimplementedError();
  }

  @override
  Future<SupplementMultiImageAnalysisPreview> finalizeSupplementAnalysisSession(
    String analysisGroupId,
  ) {
    throw UnimplementedError();
  }

  @override
  Future<ConsentState> fetchConsents() {
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
  Future<SupplementRecommendationExplainResponse> explainSupplementAnalysis(
    String analysisId, {
    bool useLocalLlm = false,
  }) {
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
  Future<SupplementImpactPreviewResponse> previewSupplementImpact(
    SupplementImpactPreviewRequest request,
  ) {
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
  Future<KdriLookupResult> lookupKdris({
    required int age,
    required String sex,
    String pregnancyStatus = 'none',
  }) {
    throw UnimplementedError();
  }
}
