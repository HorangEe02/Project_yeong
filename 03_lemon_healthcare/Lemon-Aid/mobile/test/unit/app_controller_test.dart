import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/app_controller.dart';
import 'package:lemon_aid_mobile/core/api/api_error.dart';
import 'package:lemon_aid_mobile/features/consent/consent_models.dart';
import 'package:lemon_aid_mobile/features/dashboard/dashboard_models.dart';
import 'package:lemon_aid_mobile/features/dashboard/home_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_models.dart';
import 'package:lemon_aid_mobile/features/records/food_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_repository.dart';
import 'package:lemon_aid_mobile/features/nutrition/kdri_models.dart';
import 'package:lemon_aid_mobile/features/supplements/comprehensive_analysis_models.dart';

void main() {
  test(
    'registration can automatically refresh impact and local explanation',
    () async {
      final _AutoInsightRepository repository = _AutoInsightRepository();
      final AppController controller = AppController(repository: repository);

      await controller.registerSupplement(
        _registrationRequest(),
        refreshImpact: true,
        explainWithLocalLlm: true,
      );

      expect(repository.registerCalls, 1);
      expect(repository.impactCalls, 1);
      expect(repository.explainCalls, 1);
      expect(repository.lastExplainUsedLocalLlm, isTrue);
      expect(controller.lastRegisteredSupplement?.displayName, 'Vitamin D');
      expect(controller.analysisPreview, isNull);
      expect(controller.multiImageAnalysisPreview, isNull);
      expect(
        controller.supplementImpactPreview?.safeUserMessage,
        'Impact ready.',
      );
      expect(controller.supplementExplanation?.llmUsed, isTrue);
      expect(controller.apiError, isNull);

      final bool queued = controller.queueSupplementExplanationForChat();
      final ChatExplanationDraft draft =
          controller.pendingChatExplanationDraft!;
      expect(queued, isTrue);
      expect(draft.assistantMessage, contains('출처'));
      expect(draft.assistantMessage, contains('vitamin-d.md'));
    },
  );

  test(
    'registration keeps saved supplement when post-registration explanation fails',
    () async {
      final _AutoInsightRepository repository = _AutoInsightRepository(
        failExplanation: true,
      );
      final AppController controller = AppController(repository: repository);

      await controller.registerSupplement(
        _registrationRequest(),
        refreshImpact: true,
        explainWithLocalLlm: true,
      );

      expect(controller.lastRegisteredSupplement?.displayName, 'Vitamin D');
      expect(
        controller.supplementImpactPreview?.safeUserMessage,
        'Impact ready.',
      );
      expect(controller.supplementExplanation, isNull);
      expect(controller.apiError?.message, 'explanation unavailable');
      expect(controller.notice, contains('explanation needs retry'));
    },
  );

  test(
    'queues registered supplement details for chat when impact fails',
    () async {
      final _AutoInsightRepository repository = _AutoInsightRepository(
        failImpact: true,
      );
      final AppController controller = AppController(repository: repository);

      await controller.registerSupplement(
        _registrationRequest(),
        refreshImpact: true,
        explainWithLocalLlm: true,
      );

      expect(controller.lastRegisteredSupplement?.displayName, 'Vitamin D');
      expect(controller.supplementImpactPreview, isNull);
      expect(controller.apiError?.message, 'impact unavailable');

      final bool queued = controller.queueSupplementExplanationForChat();
      final ChatExplanationDraft draft =
          controller.pendingChatExplanationDraft!;

      expect(queued, isTrue);
      expect(draft.userPrompt, contains('Vitamin D'));
      expect(draft.assistantMessage, contains('성분: Vitamin D 25 mcg'));
      expect(draft.assistantMessage, contains('영향도 계산은 아직 완료되지 않았어요'));

      controller.markChatExplanationDraftDelivered(draft.id);

      expect(controller.pendingChatExplanationDraft, isNull);
    },
  );

  test('queues bilingual ingredient names for chat explanations', () async {
    final _AutoInsightRepository repository = _AutoInsightRepository(
      failImpact: true,
    );
    final AppController controller = AppController(repository: repository);

    await controller.registerSupplement(
      _registrationRequest(
        ingredientDisplayName: '비타민 D',
        ingredientOriginalName: 'Vitamin D',
      ),
      refreshImpact: true,
      explainWithLocalLlm: true,
    );

    final bool queued = controller.queueSupplementExplanationForChat();
    final ChatExplanationDraft draft = controller.pendingChatExplanationDraft!;

    expect(queued, isTrue);
    expect(draft.assistantMessage, contains('성분: 비타민 D (Vitamin D) 25 mcg'));
    expect(draft.assistantMessage, contains('· 비타민 D (Vitamin D): 25 mcg'));
  });

  test('finalizeAnalysisSession stores merged preview for review', () async {
    final _AutoInsightRepository repository = _AutoInsightRepository();
    final AppController controller = AppController(repository: repository);

    await controller.finalizeAnalysisSession('multi-test');

    expect(repository.finalizeCalls, 1);
    expect(repository.lastFinalizeGroupId, 'multi-test');
    expect(controller.multiImageAnalysisPreview?.analysisGroupId, 'multi-test');
    expect(
      controller.analysisPreview?.analysisId,
      '00000000-0000-0000-0000-000000000001',
    );
    expect(
      controller.notice,
      'Supplement image batch was finalized for review.',
    );
    expect(controller.apiError, isNull);
  });

  test('explainSupplementAnalysis uses current preview id', () async {
    final _AutoInsightRepository repository = _AutoInsightRepository();
    final AppController controller = AppController(repository: repository);

    await controller.analyzeImage('/tmp/supplement-label.png');
    await controller.explainSupplementAnalysis(useLocalLlm: true);

    expect(repository.analysisExplainCalls, 1);
    expect(
      repository.lastAnalysisExplainId,
      '00000000-0000-0000-0000-000000000001',
    );
    expect(repository.lastAnalysisExplainUsedLocalLlm, isTrue);
    expect(controller.supplementExplanation?.llmUsed, isTrue);
    expect(controller.notice, 'Analysis explanation is ready.');
  });

  test(
    'new background supplement analysis clears stale preview immediately',
    () async {
      final _AutoInsightRepository repository = _AutoInsightRepository(
        analysisDelay: const Duration(milliseconds: 20),
      );
      final AppController controller = AppController(repository: repository);

      await controller.analyzeImage('/tmp/old-label.png');
      expect(controller.analysisPreview, isNotNull);

      await controller.startSupplementImageAnalysis('/tmp/new-label.png');

      expect(controller.analysisPreview, isNull);
      expect(controller.lastRegisteredSupplement, isNull);
      expect(controller.analysisJob.isRunning, isTrue);
      expect(controller.notice, '분석을 하고 있어요.');

      await Future<void>.delayed(const Duration(milliseconds: 40));

      expect(controller.analysisPreview, isNotNull);
      expect(controller.analysisJob.phase, AnalysisJobPhase.completed);
    },
  );

  test('analyzeMealImage stores food detection preview', () async {
    final _AutoInsightRepository repository = _AutoInsightRepository();
    final AppController controller = AppController(repository: repository);

    await controller.analyzeMealImage('/tmp/meal.png', mealType: 'lunch');

    expect(repository.lastMealImagePath, '/tmp/meal.png');
    expect(repository.lastMealType, 'lunch');
    expect(
      controller.mealAnalysisPreview?.foodCandidates.single.displayName,
      '비빔밥',
    );
    expect(controller.analysisPreview, isNull);
    expect(controller.notice, 'Meal image preview is ready for review.');
  });

  test('startSupplementImageAnalysis completes in background', () async {
    final _AutoInsightRepository repository = _AutoInsightRepository(
      analysisDelay: const Duration(milliseconds: 20),
    );
    final AppController controller = AppController(repository: repository);

    await controller.startSupplementImageAnalysis('/tmp/supplement-label.png');

    expect(controller.analysisJob.isRunning, isTrue);
    expect(controller.analysisPreview, isNull);

    await Future<void>.delayed(const Duration(milliseconds: 40));

    expect(controller.analysisJob.phase, AnalysisJobPhase.completed);
    expect(controller.hasUnreadAnalysisCompletion, isTrue);
    expect(
      controller.completedAnalysisRoute,
      '/shell/home/analysis-result?mode=supplement',
    );
    expect(controller.notice, '분석이 완료 되었어요.');
    expect(controller.analysisPreview?.analysisId, isNotEmpty);
    // Default analysis must issue a SINGLE 'configured' OCR request, not a
    // 4-provider fan-out: one scan otherwise fired 4 parallel /analyze calls and
    // tripped the backend per-caller rate limit (burst 6) on re-scan.
    expect(repository.ocrProviders, <String>['configured']);

    controller.markAnalysisCompletionRead();

    expect(controller.hasUnreadAnalysisCompletion, isFalse);
  });

  test(
    'analyzeImage issues a single configured OCR request by default',
    () async {
      final _AutoInsightRepository repository = _AutoInsightRepository();
      final AppController controller = AppController(repository: repository);

      await controller.analyzeImage('/tmp/supplement-label.png');

      expect(repository.ocrProviders, <String>['configured']);
      expect(controller.analysisPreview, isNotNull);
      expect(controller.apiError, isNull);
    },
  );

  test(
    'analyzeImage compareOcrProviders fans out the diagnostic providers',
    () async {
      final _AutoInsightRepository repository = _AutoInsightRepository();
      final AppController controller = AppController(repository: repository);

      await controller.analyzeImage(
        '/tmp/supplement-label.png',
        compareOcrProviders: true,
      );

      expect(
        repository.ocrProviders,
        containsAll(<String>[
          'configured',
          'paddleocr',
          'clova',
          'google_vision',
        ]),
      );
      expect(repository.ocrProviders.length, 4);
    },
  );

  test(
    'analyzeImage surfaces the rate-limit error instead of an empty result',
    () async {
      final _AutoInsightRepository repository = _AutoInsightRepository(
        rateLimitedOcrProviders: <String>{'configured'},
      );
      final AppController controller = AppController(repository: repository);

      await controller.analyzeImage('/tmp/supplement-label.png');

      expect(controller.analysisPreview, isNull);
      expect(controller.apiError?.statusCode, 429);
      expect(controller.apiError?.code, 'rate_limited');
    },
  );

  test(
    'compareOcrProviders prefers a rate-limit error over an empty preview',
    () async {
      final _AutoInsightRepository repository = _AutoInsightRepository(
        rateLimitedOcrProviders: <String>{'clova'},
        emptyPreviewOcrProviders: <String>{
          'configured',
          'paddleocr',
          'google_vision',
        },
      );
      final AppController controller = AppController(repository: repository);

      await controller.analyzeImage(
        '/tmp/supplement-label.png',
        compareOcrProviders: true,
      );

      expect(controller.analysisPreview, isNull);
      expect(controller.apiError?.statusCode, 429);
      expect(controller.apiError?.code, 'rate_limited');
    },
  );

  test(
    'compareOcrProviders keeps a usable preview even when one provider is rate-limited',
    () async {
      final _AutoInsightRepository repository = _AutoInsightRepository(
        rateLimitedOcrProviders: <String>{'clova'},
      );
      final AppController controller = AppController(repository: repository);

      await controller.analyzeImage(
        '/tmp/supplement-label.png',
        compareOcrProviders: true,
      );

      expect(controller.analysisPreview, isNotNull);
      expect(controller.apiError, isNull);
    },
  );

  test('confirmMealImagePreview stores user-confirmed meal', () async {
    final _AutoInsightRepository repository = _AutoInsightRepository();
    final AppController controller = AppController(repository: repository);

    await controller.analyzeMealImage('/tmp/meal.png', mealType: 'lunch');
    await controller.confirmMealImagePreview(
      const MealConfirmationRequest(
        analysisId: '00000000-0000-0000-0000-000000000101',
        mealType: 'lunch',
        foodItems: <MealFoodItemInput>[
          MealFoodItemInput(
            displayName: '비빔밥',
            kcal: 520,
            confidence: 0.88,
            source: 'vision',
          ),
        ],
      ),
    );

    expect(repository.confirmMealCalls, 1);
    expect(
      repository.lastConfirmedMealId,
      '00000000-0000-0000-0000-000000000201',
    );
    expect(
      repository.lastMealConfirmationRequest?.foodItems.single.displayName,
      '비빔밥',
    );
    expect(controller.mealAnalysisPreview, isNull);
    expect(controller.lastRegisteredMeal?.foodItems.single.displayName, '비빔밥');
    expect(controller.notice, 'Meal record saved and dashboard refreshed.');
  });

  test('registerSupplement blocks when health consent is missing', () async {
    final _AutoInsightRepository repository = _AutoInsightRepository()
      ..consents = <String, bool>{
        AppController.ocrConsent: true,
        AppController.healthConsent: false,
      };
    final AppController controller = AppController(repository: repository);
    await controller.bootstrap();

    await controller.registerSupplement(_registrationRequest());

    expect(controller.consentRequired, isTrue);
    expect(controller.apiError?.statusCode, 403);
    expect(repository.registerCalls, 0);
    expect(controller.lastRegisteredSupplement, isNull);
  });

  test('registerSupplement proceeds after health consent is present', () async {
    final _AutoInsightRepository repository = _AutoInsightRepository()
      ..consents = <String, bool>{
        AppController.ocrConsent: true,
        AppController.healthConsent: true,
      };
    final AppController controller = AppController(repository: repository);
    await controller.bootstrap();

    await controller.registerSupplement(_registrationRequest());

    expect(controller.consentRequired, isFalse);
    expect(repository.registerCalls, 1);
    expect(controller.lastRegisteredSupplement?.displayName, 'Vitamin D');
  });

  test('bootstrap loads medications into the home medications block', () async {
    final _AutoInsightRepository repository =
        _AutoInsightRepository(
            medications: const HomeMedicationsResult(
              items: <HomeMedication>[
                HomeMedication(id: 'med-1', displayName: '아모디핀'),
              ],
            ),
          )
          ..consents = <String, bool>{
            AppController.ocrConsent: true,
            AppController.healthConsent: true,
          };
    final AppController controller = AppController(repository: repository);
    await controller.bootstrap();

    expect(repository.fetchMedicationsCalls, 1);
    expect(controller.homeMedicationsFailed, isFalse);
    expect(controller.homeMedications.activeItems.single.displayName, '아모디핀');
  });

  test(
    'a failing medications block does not pollute other home blocks',
    () async {
      final _AutoInsightRepository repository =
          _AutoInsightRepository(failMedications: true)
            ..consents = <String, bool>{
              AppController.ocrConsent: true,
              AppController.healthConsent: true,
            };
      final AppController controller = AppController(repository: repository);
      await controller.bootstrap();

      // meals/supplements 블록은 이 fake 에서 정상 — medications 실패가
      // 그들을 오염시키지 않음을 확인 (impact 는 이 fake 에서 미구현).
      expect(controller.homeMedicationsFailed, isTrue);
      expect(controller.homeMealsFailed, isFalse);
      expect(controller.homeSupplementsFailed, isFalse);
      expect(controller.homeMedications.items, isEmpty);
    },
  );

  test(
    'addMedication creates the row and reloads the medications block',
    () async {
      final _AutoInsightRepository repository =
          _AutoInsightRepository(
              medications: const HomeMedicationsResult(
                items: <HomeMedication>[
                  HomeMedication(id: 'med-1', displayName: '아모디핀'),
                ],
              ),
            )
            ..consents = <String, bool>{
              AppController.ocrConsent: true,
              AppController.healthConsent: true,
            };
      final AppController controller = AppController(repository: repository);
      await controller.bootstrap();
      final int loadsAfterBootstrap = repository.fetchMedicationsCalls;

      final bool created = await controller.addMedication(
        const MedicationCreateRequest(
          displayName: '아모디핀',
          medicationClass: 'calcium_channel_blocker',
          conditionTags: <String>['hypertension'],
        ),
      );

      expect(created, isTrue);
      expect(repository.createMedicationCalls, 1);
      expect(repository.lastCreateRequest?.displayName, '아모디핀');
      // 추가 후 medications 블록만 다시 로드 (전체 대시보드 새로고침 아님).
      expect(repository.fetchMedicationsCalls, loadsAfterBootstrap + 1);
      expect(controller.notice, '약을 추가했어요.');
      expect(controller.apiError, isNull);
    },
  );

  test(
    'addMedication surfaces an api error and keeps the list when it fails',
    () async {
      final _FailingCreateRepository repository = _FailingCreateRepository()
        ..consents = <String, bool>{
          AppController.ocrConsent: true,
          AppController.healthConsent: true,
        };
      final AppController controller = AppController(repository: repository);
      await controller.bootstrap();

      final bool created = await controller.addMedication(
        const MedicationCreateRequest(displayName: '아모디핀'),
      );

      expect(created, isFalse);
      expect(controller.apiError?.statusCode, 422);
    },
  );

  test(
    'deactivateMedication then reactivateMedication supports undo',
    () async {
      final _AutoInsightRepository repository =
          _AutoInsightRepository(
              medications: const HomeMedicationsResult(
                items: <HomeMedication>[
                  HomeMedication(id: 'med-1', displayName: '아모디핀'),
                ],
              ),
            )
            ..consents = <String, bool>{
              AppController.ocrConsent: true,
              AppController.healthConsent: true,
            };
      final AppController controller = AppController(repository: repository);
      await controller.bootstrap();

      final bool deactivated = await controller.deactivateMedication('med-1');
      final bool reactivated = await controller.reactivateMedication('med-1');

      expect(deactivated, isTrue);
      expect(reactivated, isTrue);
      expect(repository.deactivateMedicationCalls, 1);
      expect(repository.lastDeactivatedId, 'med-1');
      expect(repository.reactivateMedicationCalls, 1);
      expect(repository.lastReactivatedId, 'med-1');
    },
  );
}

class _FailingCreateRepository extends _AutoInsightRepository {
  @override
  Future<HomeMedication> createMedication(
    MedicationCreateRequest request,
  ) async {
    throw const ApiError(statusCode: 422, message: '입력을 확인해주세요.');
  }
}

UserSupplementCreate _registrationRequest({
  String ingredientDisplayName = 'Vitamin D',
  String? ingredientOriginalName,
}) {
  return UserSupplementCreate(
    analysisId: 'analysis-1',
    displayName: 'Vitamin D',
    manufacturer: 'Lemon Lab',
    ingredients: <UserSupplementIngredientInput>[
      UserSupplementIngredientInput(
        displayName: ingredientDisplayName,
        originalName: ingredientOriginalName,
        nutrientCode: 'vitamin_d',
        amount: 25,
        unit: 'mcg',
        confidence: 0.92,
        source: 'ocr_llm_preview',
      ),
    ],
    serving: const SupplementServing(
      amount: 1,
      unit: 'capsule',
      dailyServings: 1,
    ),
    intakeSchedule: const SupplementIntakeSchedule(
      frequency: 'daily',
      timeOfDay: <String>['morning'],
    ),
  );
}

class _AutoInsightRepository implements LemonAidRepository {
  _AutoInsightRepository({
    this.failExplanation = false,
    this.failImpact = false,
    this.failMedications = false,
    this.analysisDelay = Duration.zero,
    this.medications = HomeMedicationsResult.empty,
    this.rateLimitedOcrProviders = const <String>{},
    this.emptyPreviewOcrProviders = const <String>{},
  });

  final bool failExplanation;
  final bool failImpact;
  final bool failMedications;
  final Duration analysisDelay;
  final HomeMedicationsResult medications;

  /// OCR providers that respond with a backend rate-limit (HTTP 429) error.
  final Set<String> rateLimitedOcrProviders;

  /// OCR providers that respond with a structurally empty (unusable) preview.
  final Set<String> emptyPreviewOcrProviders;
  Map<String, bool> consents = const <String, bool>{};
  int registerCalls = 0;
  int impactCalls = 0;
  int explainCalls = 0;
  int analysisExplainCalls = 0;
  int finalizeCalls = 0;
  int confirmMealCalls = 0;
  int fetchMedicationsCalls = 0;
  int createMedicationCalls = 0;
  int deactivateMedicationCalls = 0;
  int reactivateMedicationCalls = 0;
  MedicationCreateRequest? lastCreateRequest;
  String? lastDeactivatedId;
  String? lastReactivatedId;
  bool? lastExplainUsedLocalLlm;
  bool? lastAnalysisExplainUsedLocalLlm;
  String? lastAnalysisExplainId;
  String? lastFinalizeGroupId;
  String? lastMealImagePath;
  String? lastMealType;
  String? lastConfirmedMealId;
  MealConfirmationRequest? lastMealConfirmationRequest;
  final List<String> ocrProviders = <String>[];

  @override
  Future<UserSupplementResponse> registerSupplement(
    UserSupplementCreate request,
  ) async {
    registerCalls += 1;
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
  Future<HomeMedicationsResult> fetchMedications() async {
    fetchMedicationsCalls += 1;
    if (failMedications) {
      throw const ApiError(statusCode: 503, message: 'medications unavailable');
    }
    return medications;
  }

  @override
  Future<HomeMedication> createMedication(
    MedicationCreateRequest request,
  ) async {
    createMedicationCalls += 1;
    lastCreateRequest = request;
    return HomeMedication(id: 'med-new', displayName: request.displayName);
  }

  @override
  Future<HomeMedication> deactivateMedication(String medicationId) async {
    deactivateMedicationCalls += 1;
    lastDeactivatedId = medicationId;
    return HomeMedication(
      id: medicationId,
      displayName: '아모디핀',
      isActive: false,
    );
  }

  @override
  Future<HomeMedication> reactivateMedication(String medicationId) async {
    reactivateMedicationCalls += 1;
    lastReactivatedId = medicationId;
    return HomeMedication(id: medicationId, displayName: '아모디핀');
  }

  @override
  Future<DashboardSummary> fetchDashboardSummary({int days = 30}) async {
    return DashboardSummary(
      asOf: DateTime.utc(2026, 5, 28),
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
        registeredCount: 1,
        requiresReviewCount: 0,
      ),
      disclaimers: const <String>[],
      algorithmVersion: 'test',
    );
  }

  @override
  Future<SupplementImpactPreviewResponse> previewSupplementImpact(
    SupplementImpactPreviewRequest request,
  ) async {
    impactCalls += 1;
    if (failImpact) {
      throw const ApiError(statusCode: 503, message: 'impact unavailable');
    }
    return _impactPreview();
  }

  @override
  Future<SupplementRecommendationExplainResponse>
  explainSupplementRecommendation(
    SupplementImpactPreviewResponse preview, {
    bool useLocalLlm = false,
  }) async {
    explainCalls += 1;
    lastExplainUsedLocalLlm = useLocalLlm;
    if (failExplanation) {
      throw const ApiError(statusCode: 503, message: 'explanation unavailable');
    }
    return const SupplementRecommendationExplainResponse(
      safeUserMessage: 'Local explanation ready.',
      explanationBullets: <String>['Review duplicate supplement sources.'],
      clinicalDisclaimer: 'Reference information only.',
      blockedTermsDetected: <String>[],
      llmUsed: true,
      sourceCitations: <SupplementExplanationSourceCitation>[
        SupplementExplanationSourceCitation(
          title: '비타민 D',
          sourcePath: 'vitamin-d.md',
          heading: '확인 필요',
          excerpt: '비타민 D는 개인 상태와 함께 확인합니다.',
          score: 9,
        ),
      ],
      warnings: <String>[],
    );
  }

  @override
  Future<SupplementAnalysisPreview> analyzeSupplementImage(
    String imagePath, {
    String ocrProvider = 'configured',
  }) async {
    if (analysisDelay > Duration.zero) {
      await Future<void>.delayed(analysisDelay);
    }
    ocrProviders.add(ocrProvider);
    if (rateLimitedOcrProviders.contains(ocrProvider)) {
      throw const ApiError(
        statusCode: 429,
        message: 'Rate limit exceeded. Please retry after a short delay.',
        code: 'rate_limited',
      );
    }
    if (emptyPreviewOcrProviders.contains(ocrProvider)) {
      return SupplementAnalysisPreview.fromJson(_emptyPreviewJson);
    }
    return SupplementAnalysisPreview.fromJson(
      _multiPreviewJson['merged_preview']! as Map<String, Object?>,
    );
  }

  @override
  Future<MealImageAnalysisPreview> analyzeMealImage(
    String imagePath, {
    String mealType = 'unknown',
  }) async {
    lastMealImagePath = imagePath;
    lastMealType = mealType;
    return MealImageAnalysisPreview.fromJson(_mealPreviewJson);
  }

  @override
  Future<MealRecordResponse> confirmMealImagePreview(
    String mealId,
    MealConfirmationRequest request,
  ) async {
    confirmMealCalls += 1;
    lastConfirmedMealId = mealId;
    lastMealConfirmationRequest = request;
    return MealRecordResponse.fromJson(_mealRecordJson);
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
  Future<SupplementMultiImageAnalysisPreview> finalizeSupplementAnalysisSession(
    String analysisGroupId,
  ) async {
    finalizeCalls += 1;
    lastFinalizeGroupId = analysisGroupId;
    return SupplementMultiImageAnalysisPreview.fromJson(_multiPreviewJson);
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
  Future<ConsentState> fetchConsents() async {
    return ConsentState(
      consents: <ConsentStatus>[
        for (final MapEntry<String, bool> entry in consents.entries)
          ConsentStatus(
            consentType: entry.key,
            policyVersion: 'v1',
            title: entry.key,
            required: true,
            granted: entry.value,
            occurredAt: null,
            revokedAt: null,
          ),
      ],
    );
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
  Future<SupplementImpactPreviewResponse>
  fetchLatestSupplementRecommendation() {
    throw UnimplementedError();
  }

  @override
  Future<SupplementRecommendationExplainResponse> explainSupplementAnalysis(
    String analysisId, {
    bool useLocalLlm = false,
  }) async {
    analysisExplainCalls += 1;
    lastAnalysisExplainId = analysisId;
    lastAnalysisExplainUsedLocalLlm = useLocalLlm;
    return const SupplementRecommendationExplainResponse(
      safeUserMessage: 'Analysis explanation ready.',
      explanationBullets: <String>['Review extracted label fields.'],
      clinicalDisclaimer: 'Reference information only.',
      blockedTermsDetected: <String>[],
      llmUsed: true,
      sourceCitations: <SupplementExplanationSourceCitation>[
        SupplementExplanationSourceCitation(
          title: '성분표 확인',
          sourcePath: 'supplement-label.md',
          heading: '라벨',
          excerpt: '성분표는 사용자가 저장 전에 확인합니다.',
          score: 5,
        ),
      ],
      warnings: <String>[],
    );
  }
}

SupplementImpactPreviewResponse _impactPreview() {
  return const SupplementImpactPreviewResponse(
    calculationVersion: 'supplement-impact-v1.0.0',
    referenceVersion: '2025',
    sourceManifestVersion: null,
    dataStatus: 'partial',
    currentSupplementContributions: <SupplementContributionAggregate>[],
    deficiencySupportCandidates: <SupplementNutritionInsight>[],
    excessOrDuplicateRisks: <SupplementNutritionInsight>[],
    missingProfileFields: <String>[],
    safeUserMessage: 'Impact ready.',
    clinicalDisclaimer: 'Reference information only.',
    warnings: <String>[],
    requiresUserConfirmation: true,
  );
}

final Map<String, Object?> _multiPreviewJson = <String, Object?>{
  'analysis_group_id': 'multi-test',
  'image_count': 2,
  'previews': <Object?>[
    <String, Object?>{
      'analysis_id': '00000000-0000-0000-0000-000000000001',
      'status': 'requires_confirmation',
      'parsed_product': <String, Object?>{'product_name': 'Vitamin D'},
      'ingredient_candidates': <Object?>[],
      'algorithm_version': 'test',
      'source_manifest_version': null,
      'expires_at': '2026-05-28T00:00:00Z',
    },
  ],
  'merged_preview': <String, Object?>{
    'analysis_id': '00000000-0000-0000-0000-000000000001',
    'status': 'requires_confirmation',
    'parsed_product': <String, Object?>{'product_name': 'Vitamin D'},
    'ingredient_candidates': <Object?>[],
    'image_role': 'mixed',
    'multi_image_group_id': 'multi-test',
    'algorithm_version': 'test',
    'source_manifest_version': null,
    'expires_at': '2026-05-28T00:00:00Z',
  },
  'missing_required_sections': <String>[],
  'action_required': 'review_required',
  'pipeline_metadata': <String, Object?>{
    'intake_completed': true,
    'image_count': 2,
    'image_role': 'mixed',
    'raw_image_stored': false,
    'raw_ocr_text_stored': false,
  },
  'expires_at': '2026-05-28T00:00:00Z',
};

/// A structurally empty (unusable) supplement preview: no product name, no
/// ingredient candidates, no label sections — the shape a provider returns when
/// OCR ran but produced nothing the parser could structure.
final Map<String, Object?> _emptyPreviewJson = <String, Object?>{
  'analysis_id': '00000000-0000-0000-0000-000000000009',
  'status': 'requires_confirmation',
  'parsed_product': <String, Object?>{'product_name': null},
  'ingredient_candidates': <Object?>[],
  'label_sections': <Object?>[],
  'algorithm_version': 'test',
  'source_manifest_version': null,
  'expires_at': '2026-05-28T00:00:00Z',
};

final Map<String, Object?> _mealPreviewJson = <String, Object?>{
  'analysis_id': '00000000-0000-0000-0000-000000000101',
  'meal_id': '00000000-0000-0000-0000-000000000201',
  'status': 'requires_confirmation',
  'meal_type': 'lunch',
  'eaten_at': '2026-05-28T03:00:00Z',
  'food_candidates': <Object?>[
    <String, Object?>{
      'display_name': '비빔밥',
      'portion_amount': null,
      'portion_unit': null,
      'kcal': null,
      'carb_g': null,
      'protein_g': null,
      'fat_g': null,
      'sodium_mg': null,
      'confidence': 0.88,
      'source': 'vision',
    },
  ],
  'nutrition_estimate_summary': <String, Object?>{
    'status': 'detected_review_required',
    'items': <Object?>[],
    'totals': <String, Object?>{},
    'detector_used': true,
  },
  'warning_codes': <String>['food_detection_review_required'],
  'pipeline_metadata': <String, Object?>{
    'intake_completed': true,
    'detector_model': 'food_yolo_local:best.pt',
    'classifier_model': null,
    'detector_used': true,
    'classifier_used': false,
    'raw_image_stored': false,
    'raw_provider_payload_stored': false,
    'requires_manual_entry': false,
  },
  'algorithm_version': 'food-image-preview-v1.0.0',
  'created_at': '2026-05-28T03:00:01Z',
};

final Map<String, Object?> _mealRecordJson = <String, Object?>{
  'id': '00000000-0000-0000-0000-000000000201',
  'status': 'confirmed',
  'meal_type': 'lunch',
  'eaten_at': '2026-05-28T03:00:00Z',
  'food_items': <Object?>[
    <String, Object?>{
      'id': '00000000-0000-0000-0000-000000000301',
      'display_name': '비빔밥',
      'portion_amount': null,
      'portion_unit': null,
      'kcal': 520,
      'carb_g': null,
      'protein_g': null,
      'fat_g': null,
      'sodium_mg': null,
      'confidence': 0.88,
      'source': 'vision',
    },
  ],
  'nutrition_summary': <String, Object?>{
    'status': 'user_confirmed',
    'items_count': 1,
    'totals': <String, Object?>{'kcal': 520},
  },
  'confirmed_at': '2026-05-28T03:05:00Z',
  'created_at': '2026-05-28T03:00:01Z',
};
