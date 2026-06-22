import 'dart:async';

import 'package:flutter/foundation.dart';

import 'core/api/api_error.dart';
import 'features/consent/consent_models.dart';
import 'features/dashboard/dashboard_models.dart';
import 'features/dashboard/home_models.dart';
import 'features/records/deferred_delete_queue.dart';
import 'features/supplements/comprehensive_analysis_models.dart';
import 'features/supplements/supplement_models.dart';
import 'features/supplements/supplement_repository.dart';

/// Lifecycle state for an image analysis job started from the camera flow.
enum AnalysisJobPhase {
  /// No image analysis is currently tracked.
  idle,

  /// The backend analysis is still running.
  running,

  /// The backend analysis completed and a result is available.
  completed,

  /// The backend analysis failed.
  failed,
}

/// User-facing state for long-running image analysis.
class AnalysisJobSnapshot {
  /// Creates a tracked analysis job snapshot.
  ///
  /// Args:
  ///   phase: Current analysis lifecycle phase.
  ///   mode: `supplement` or `meal`.
  ///   message: User-facing status text.
  ///   resultRoute: Route that can show the finished analysis result.
  ///   startedAt: Local start timestamp.
  ///   completedAt: Local completion timestamp.
  ///   notificationRead: Whether the completion notification was dismissed.
  const AnalysisJobSnapshot({
    required this.phase,
    this.mode,
    this.message,
    this.resultRoute,
    this.startedAt,
    this.completedAt,
    this.notificationRead = true,
  });

  /// Current analysis lifecycle phase.
  final AnalysisJobPhase phase;

  /// Analysis mode, such as `supplement` or `meal`.
  final String? mode;

  /// User-facing status text.
  final String? message;

  /// Route that can display the analysis result.
  final String? resultRoute;

  /// Local timestamp when the job started.
  final DateTime? startedAt;

  /// Local timestamp when the job completed.
  final DateTime? completedAt;

  /// Whether completion notification has already been consumed.
  final bool notificationRead;

  /// Empty state.
  const AnalysisJobSnapshot.idle()
    : this(phase: AnalysisJobPhase.idle, message: null);

  /// Creates a running job state.
  factory AnalysisJobSnapshot.running({required String mode}) {
    return AnalysisJobSnapshot(
      phase: AnalysisJobPhase.running,
      mode: mode,
      message: '분석을 하고 있어요.',
      resultRoute: '/shell/home/analysis-result?mode=$mode',
      startedAt: DateTime.now(),
      notificationRead: true,
    );
  }

  /// Whether this job is actively running.
  bool get isRunning => phase == AnalysisJobPhase.running;

  /// Whether this job completed and should show a result notification.
  bool get hasUnreadCompletion {
    return phase == AnalysisJobPhase.completed && !notificationRead;
  }

  /// Returns a copy marked as completed.
  AnalysisJobSnapshot completed({required String message}) {
    return AnalysisJobSnapshot(
      phase: AnalysisJobPhase.completed,
      mode: mode,
      message: message,
      resultRoute: resultRoute,
      startedAt: startedAt,
      completedAt: DateTime.now(),
      notificationRead: false,
    );
  }

  /// Returns a copy marked as failed.
  AnalysisJobSnapshot failed({required String message}) {
    return AnalysisJobSnapshot(
      phase: AnalysisJobPhase.failed,
      mode: mode,
      message: message,
      resultRoute: resultRoute,
      startedAt: startedAt,
      completedAt: DateTime.now(),
      notificationRead: true,
    );
  }

  /// Returns a copy with completion notification consumed.
  AnalysisJobSnapshot markNotificationRead() {
    return AnalysisJobSnapshot(
      phase: phase,
      mode: mode,
      message: message,
      resultRoute: resultRoute,
      startedAt: startedAt,
      completedAt: completedAt,
      notificationRead: true,
    );
  }
}

/// User-safe supplement context queued for the chat tab.
class ChatExplanationDraft {
  /// Creates a one-shot chat explanation draft.
  ///
  /// Args:
  ///   id: Monotonic local identifier used to consume the draft once.
  ///   title: Short supplement title shown in chat.
  ///   userPrompt: User-side prompt inserted into the chat transcript.
  ///   assistantMessage: LemonBot-side explanation inserted after the prompt.
  ///   createdAt: Local creation timestamp for traceability.
  const ChatExplanationDraft({
    required this.id,
    required this.title,
    required this.userPrompt,
    required this.assistantMessage,
    required this.createdAt,
  });

  /// Monotonic local identifier used to consume the draft once.
  final int id;

  /// Short supplement title shown in chat.
  final String title;

  /// User-side prompt inserted into the chat transcript.
  final String userPrompt;

  /// LemonBot-side explanation inserted after the prompt.
  final String assistantMessage;

  /// Local creation timestamp for traceability.
  final DateTime createdAt;
}

class _SupplementAnalysisAttempt {
  const _SupplementAnalysisAttempt({
    required this.provider,
    this.preview,
    this.multiPreview,
    this.error,
  });

  final String provider;
  final SupplementAnalysisPreview? preview;
  final SupplementMultiImageAnalysisPreview? multiPreview;
  final Object? error;

  bool get succeeded => preview != null;
}

class _SupplementAnalysisSelection {
  const _SupplementAnalysisSelection({
    required this.provider,
    required this.preview,
    this.multiPreview,
  });

  final String provider;
  final SupplementAnalysisPreview preview;
  final SupplementMultiImageAnalysisPreview? multiPreview;
}

/// Coordinates the minimal mobile demo flow.
class AppController extends ChangeNotifier {
  /// Creates an app controller.
  ///
  /// Args:
  ///   repository: Backend or fake repository implementation.
  AppController({required LemonAidRepository repository})
    : _repository = repository;

  static const String ocrConsent = 'ocr_image_processing';
  static const String healthConsent = 'sensitive_health_analysis';

  final LemonAidRepository _repository;

  /// Backend repository for read-only secondary lookups (e.g. KDRIs from the
  /// ingredient detail screen). Screens reuse this instead of re-resolving the
  /// provider so widget tests can drive the same fake repository.
  LemonAidRepository get repository => _repository;
  // 영양제 삭제용 지연 실행 큐(4초)+실행취소 — 백엔드 공백 3(restore 라우트 없음)
  // 대체. 미취소 시 commit 으로 DELETE /supplements/{id} 호출.
  final DeferredDeleteQueue _supplementDeleteQueue = DeferredDeleteQueue();

  bool _busy = false;
  ApiError? _apiError;
  String? _notice;
  ConsentState? _consentState;
  DashboardSummary? _dashboardSummary;
  DashboardHealthScore _healthScore = const DashboardHealthScore(
    status: HealthScoreStatus.notReady,
  );
  HomeMealsResult _recentMeals = HomeMealsResult.empty;
  HomeSupplementsResult _homeSupplements = HomeSupplementsResult.empty;
  HomeMedicationsResult _homeMedications = HomeMedicationsResult.empty;
  bool _homeDataLoading = false;
  bool _homeMealsFailed = false;
  bool _homeSupplementsFailed = false;
  bool _homeImpactFailed = false;
  bool _homeMedicationsFailed = false;
  SupplementAnalysisPreview? _analysisPreview;
  SupplementMultiImageAnalysisPreview? _multiImageAnalysisPreview;
  MealImageAnalysisPreview? _mealAnalysisPreview;
  // 분석 결과 화면에서 사용자가 첨부/촬영한 원본 이미지를 다시 보여주기 위한 로컬
  // 파일 경로. 분석 시작 시 채워지고 모드 전환·초기화 시 비운다(Figma: 결과에 원본
  // 이미지 노출). 백엔드는 원본 이미지를 보관/반환하지 않으므로 클라이언트가 보관한다.
  List<String> _supplementImagePaths = const <String>[];
  String? _mealImagePath;
  ComprehensiveDietAnalysis? _comprehensiveDietAnalysis;
  MealRecordResponse? _lastRegisteredMeal;
  UserSupplementResponse? _lastRegisteredSupplement;
  UserSupplementCreate? _lastRegisteredSupplementRequest;
  SupplementImpactPreviewResponse? _supplementImpactPreview;
  SupplementRecommendationExplainResponse? _supplementExplanation;
  ChatExplanationDraft? _pendingChatExplanationDraft;
  String? _lastRequestedOcrProvider;
  bool _lastSupplementBatchIsSingleProduct = true;
  AnalysisJobSnapshot _analysisJob = const AnalysisJobSnapshot.idle();
  int _analysisJobSerial = 0;
  int _chatDraftSerial = 0;
  bool _consentRequired = false;

  /// Default single OCR provider for normal scans. The backend resolves
  /// 'configured' to its primary provider, so one scan = one `/analyze` call.
  static const String _defaultOcrProvider = 'configured';

  /// Diagnostic-only provider set for side-by-side OCR comparison.
  ///
  /// NOT the default path: fanning these out per scan fired 4 parallel
  /// `/analyze` calls into the same per-caller bucket and tripped the backend
  /// rate limit (burst 6) on re-scan. Opt in via `compareOcrProviders: true`.
  static const List<String> _diagnosticOcrProviders = <String>[
    'configured',
    'paddleocr',
    'clova',
    'google_vision',
  ];

  /// Whether a network operation is in progress.
  bool get busy => _busy;

  /// Last API error, if any.
  ApiError? get apiError => _apiError;

  /// Last user-safe notice.
  String? get notice => _notice;

  /// Whether the last action was blocked because a required consent is missing.
  ///
  /// When true, the UI should route the user to the consent screen and let them
  /// grant the missing bucket (e.g. sensitive health analysis) before retrying.
  bool get consentRequired => _consentRequired;

  /// Current consent state.
  ConsentState? get consentState => _consentState;

  /// Current dashboard summary.
  DashboardSummary? get dashboardSummary => _dashboardSummary;

  /// Latest parsed daily health score block (not_ready when unavailable).
  DashboardHealthScore get healthScore => _healthScore;

  /// Recently loaded meals (last 7 days window for the home tab).
  HomeMealsResult get recentMeals => _recentMeals;

  /// Current-user registered supplements for the home tab.
  HomeSupplementsResult get homeSupplements => _homeSupplements;

  /// Current-user saved medications for the home tab (active and inactive).
  HomeMedicationsResult get homeMedications => _homeMedications;

  /// Whether the home blocks (meals/supplements/impact) are loading.
  bool get homeDataLoading => _homeDataLoading;

  /// Whether the meals block failed to load on the last attempt.
  bool get homeMealsFailed => _homeMealsFailed;

  /// Whether the supplements block failed to load on the last attempt.
  bool get homeSupplementsFailed => _homeSupplementsFailed;

  /// Whether the supplement interaction block failed to load on the last attempt.
  bool get homeImpactFailed => _homeImpactFailed;

  /// Whether the medications block failed to load on the last attempt.
  bool get homeMedicationsFailed => _homeMedicationsFailed;

  /// Meals eaten on [day] (client-side filter over the loaded window).
  List<HomeMeal> mealsForDay(DateTime day) {
    return _recentMeals.results
        .where((HomeMeal meal) {
          final DateTime? eatenAt = meal.eatenAt;
          if (eatenAt == null) return false;
          final DateTime local = eatenAt.toLocal();
          return local.year == day.year &&
              local.month == day.month &&
              local.day == day.day;
        })
        .toList(growable: false);
  }

  /// Whether any meal record exists for [day].
  bool hasMealRecord(DateTime day) => mealsForDay(day).isNotEmpty;

  /// Current supplement analysis preview.
  SupplementAnalysisPreview? get analysisPreview => _analysisPreview;

  /// Current multi-image supplement analysis preview, if the batch endpoint was used.
  SupplementMultiImageAnalysisPreview? get multiImageAnalysisPreview =>
      _multiImageAnalysisPreview;

  /// Current meal image analysis preview.
  MealImageAnalysisPreview? get mealAnalysisPreview => _mealAnalysisPreview;

  /// Local file paths of the supplement images the user attached/captured for the
  /// current analysis, so the result screen can re-show the original image.
  List<String> get supplementImagePaths => _supplementImagePaths;

  /// Local file path of the meal image the user attached/captured for the current
  /// analysis, so the result screen can re-show the original image.
  String? get mealImagePath => _mealImagePath;

  /// Latest comprehensive diet analysis (C-hybrid result surface), if loaded.
  ///
  /// Null when not requested or when the request failed; the result screen
  /// hides the score/insight area in that case and keeps showing base info.
  ComprehensiveDietAnalysis? get comprehensiveDietAnalysis =>
      _comprehensiveDietAnalysis;

  /// Most recently confirmed meal record.
  MealRecordResponse? get lastRegisteredMeal => _lastRegisteredMeal;

  /// Most recently registered supplement.
  UserSupplementResponse? get lastRegisteredSupplement =>
      _lastRegisteredSupplement;

  /// User-confirmed request that produced the most recently registered supplement.
  UserSupplementCreate? get lastRegisteredSupplementRequest =>
      _lastRegisteredSupplementRequest;

  /// Latest deterministic supplement impact preview.
  SupplementImpactPreviewResponse? get supplementImpactPreview =>
      _supplementImpactPreview;

  /// Latest safe supplement explanation.
  SupplementRecommendationExplainResponse? get supplementExplanation =>
      _supplementExplanation;

  /// One-shot supplement explanation draft waiting for the chat tab.
  ChatExplanationDraft? get pendingChatExplanationDraft =>
      _pendingChatExplanationDraft;

  /// Most recent mobile-selected OCR provider for smoke-test diagnostics.
  String? get lastRequestedOcrProvider => _lastRequestedOcrProvider;

  /// Whether the most recent multi-image supplement scan was one product.
  bool get lastSupplementBatchIsSingleProduct =>
      _lastSupplementBatchIsSingleProduct;

  /// Current long-running image analysis job, if any.
  AnalysisJobSnapshot get analysisJob => _analysisJob;

  /// Whether a completed analysis result has not been opened yet.
  bool get hasUnreadAnalysisCompletion => _analysisJob.hasUnreadCompletion;

  /// Result route for the latest completed analysis, if available.
  String? get completedAnalysisRoute {
    return _analysisJob.hasUnreadCompletion ? _analysisJob.resultRoute : null;
  }

  /// Whether the two P2 demo consents are granted.
  bool get hasMinimumConsents {
    final ConsentState? state = _consentState;
    return state != null &&
        state.isGranted(ocrConsent) &&
        state.isGranted(healthConsent);
  }

  /// Loads consent state and dashboard summary when possible.
  Future<void> bootstrap() async {
    await _run(() async {
      _consentState = await _repository.fetchConsents();
      if (hasMinimumConsents) {
        _dashboardSummary = await _repository.fetchDashboardSummary();
        _healthScore = _dashboardSummary!.healthScore;
        await _loadHomeData();
      }
    });
  }

  /// Grants the P2 minimum consents and refreshes the dashboard.
  Future<void> grantMinimumConsents() async {
    await _run(() async {
      await _repository.grantConsent(ocrConsent);
      await _repository.grantConsent(healthConsent);
      _consentState = await _repository.fetchConsents();
      _dashboardSummary = await _repository.fetchDashboardSummary();
      _notice = 'Required demo consents are active.';
    });
  }

  /// Grants the consent buckets selected in the consent gate, then refreshes.
  ///
  /// Used by the consent gate sheet: the user checks one or more consent rows
  /// (all required plus any optional) and the gate grants exactly those buckets.
  /// When the minimum consents are met afterward, the dashboard and home blocks
  /// are loaded so the shell is ready on entry.
  ///
  /// Args:
  ///   consentTypes: Backend consent bucket identifiers the user agreed to.
  Future<void> grantConsents(Iterable<String> consentTypes) async {
    await _run(() async {
      for (final String consentType in consentTypes) {
        await _repository.grantConsent(consentType);
      }
      _consentState = await _repository.fetchConsents();
      if (hasMinimumConsents) {
        _dashboardSummary = await _repository.fetchDashboardSummary();
        _healthScore = _dashboardSummary!.healthScore;
        await _loadHomeData();
      }
      _notice = '동의가 저장됐어요.';
    });
  }

  /// Refreshes the dashboard summary and home data blocks.
  Future<void> refreshDashboard() async {
    await _run(() async {
      _dashboardSummary = await _repository.fetchDashboardSummary();
      _healthScore = _dashboardSummary!.healthScore;
      await _loadHomeData();
      _notice = 'Dashboard refreshed.';
    });
  }

  /// Loads today's meals, supplements, and the interaction impact preview.
  ///
  /// Each block is independent: a single block failing does not fail the whole
  /// home load. Per-block failure flags drive empty/error states in the UI.
  Future<void> _loadHomeData() async {
    _homeDataLoading = true;
    _homeMealsFailed = false;
    _homeSupplementsFailed = false;
    _homeImpactFailed = false;
    _homeMedicationsFailed = false;
    notifyListeners();

    await Future.wait<void>(<Future<void>>[
      _refreshMealsBlockForHome(),
      _loadSupplementsBlock(),
      _loadImpactBlock(),
      _loadMedicationsBlock(),
    ]);

    _homeDataLoading = false;
    notifyListeners();
  }

  DateTime _homeMealsFrom(DateTime now) {
    return DateTime(
      now.year,
      now.month,
      now.day,
    ).subtract(const Duration(days: 6));
  }

  Future<void> _refreshMealsBlockForHome() async {
    _homeMealsFailed = false;
    await _loadMealsBlock(_homeMealsFrom(DateTime.now()));
  }

  Future<void> _loadMealsBlock(DateTime from) async {
    try {
      _recentMeals = await _repository.fetchMeals(from: from, limit: 100);
    } catch (_) {
      _homeMealsFailed = true;
    }
  }

  Future<void> _loadSupplementsBlock() async {
    try {
      _homeSupplements = await _repository.fetchSupplements(limit: 100);
    } catch (_) {
      _homeSupplementsFailed = true;
    }
  }

  Future<void> _loadImpactBlock() async {
    try {
      _supplementImpactPreview = await _repository
          .fetchLatestSupplementRecommendation();
    } catch (_) {
      _homeImpactFailed = true;
    }
  }

  Future<void> _loadMedicationsBlock() async {
    try {
      _homeMedications = await _repository.fetchMedications();
    } catch (_) {
      _homeMedicationsFailed = true;
    }
  }

  /// Reloads only the medications block (after add/deactivate/undo).
  ///
  /// Keeps the rest of the home untouched so a medication action does not
  /// trigger a full dashboard refresh.
  Future<void> _reloadMedicationsBlock() async {
    _homeMedicationsFailed = false;
    try {
      _homeMedications = await _repository.fetchMedications();
    } catch (_) {
      _homeMedicationsFailed = true;
    }
    notifyListeners();
  }

  /// Saves a user-confirmed medication and refreshes the home medication list.
  ///
  /// Returns true on success. On failure, [apiError] holds a user-safe message
  /// (422 validation, network, etc.) and the list is left unchanged.
  Future<bool> addMedication(MedicationCreateRequest request) async {
    bool created = false;
    await _run(() async {
      await _repository.createMedication(request);
      created = true;
      await _reloadMedicationsBlock();
      _notice = '약을 추가했어요.';
    });
    return created;
  }

  /// Deactivates a saved medication and refreshes the home medication list.
  ///
  /// Returns true on success so the caller can offer an undo action.
  Future<bool> deactivateMedication(String medicationId) async {
    bool done = false;
    await _run(() async {
      await _repository.deactivateMedication(medicationId);
      done = true;
      await _reloadMedicationsBlock();
      _notice = '약을 목록에서 비활성화했어요.';
    });
    return done;
  }

  /// Reactivates a saved medication (undo of a deactivation).
  Future<bool> reactivateMedication(String medicationId) async {
    bool done = false;
    await _run(() async {
      await _repository.reactivateMedication(medicationId);
      done = true;
      await _reloadMedicationsBlock();
      _notice = '약을 다시 활성화했어요.';
    });
    return done;
  }

  /// Optimistically removes a registered supplement from the home list and
  /// schedules the backend delete after a short undo window.
  ///
  /// The row is removed from [homeSupplements] immediately so the UI reflects
  /// the deletion at once. The actual `DELETE /supplements/{id}` is deferred by
  /// the undo window; [undoSupplementRemoval] cancels it and restores the row.
  /// Returns the removed [HomeSupplement] so the caller can offer undo, or null
  /// when the id is unknown.
  HomeSupplement? removeSupplementOptimistically(String supplementId) {
    final int index = _homeSupplements.results.indexWhere(
      (HomeSupplement item) => item.id == supplementId,
    );
    if (index < 0) return null;
    final HomeSupplement removed = _homeSupplements.results[index];
    final List<HomeSupplement> next = List<HomeSupplement>.of(
      _homeSupplements.results,
    )..removeAt(index);
    _homeSupplements = HomeSupplementsResult(
      results: next,
      limit: _homeSupplements.limit,
      offset: _homeSupplements.offset,
    );
    notifyListeners();
    _supplementDeleteQueue.schedule(supplementId, () async {
      await _repository.deleteSupplement(supplementId);
    });
    return removed;
  }

  /// Cancels a pending supplement deletion and restores the row (undo).
  void undoSupplementRemoval(HomeSupplement supplement) {
    final bool cancelled = _supplementDeleteQueue.undo(supplement.id);
    if (!cancelled) return;
    final bool present = _homeSupplements.results.any(
      (HomeSupplement item) => item.id == supplement.id,
    );
    if (present) return;
    _homeSupplements = HomeSupplementsResult(
      results: <HomeSupplement>[..._homeSupplements.results, supplement],
      limit: _homeSupplements.limit,
      offset: _homeSupplements.offset,
    );
    notifyListeners();
  }

  /// Uploads a supplement label image and stores the preview.
  ///
  /// Issues a single `ocrProvider` request by default. Set `compareOcrProviders`
  /// (dev/diagnostic only) to fan out across providers for side-by-side compare.
  Future<void> analyzeImage(
    String imagePath, {
    String ocrProvider = _defaultOcrProvider,
    bool compareOcrProviders = false,
  }) async {
    await _run(() async {
      final _SupplementAnalysisSelection selection =
          await _analyzeSupplementImageAutomatically(
            imagePath,
            ocrProvider: ocrProvider,
            compareOcrProviders: compareOcrProviders,
          );
      _lastRequestedOcrProvider = selection.provider;
      _lastSupplementBatchIsSingleProduct = true;
      _analysisPreview = selection.preview;
      _multiImageAnalysisPreview = null;
      _mealAnalysisPreview = null;
      _supplementImagePaths = <String>[imagePath];
      _mealImagePath = null;
      _lastRegisteredSupplement = null;
      _lastRegisteredSupplementRequest = null;
      _lastRegisteredMeal = null;
      _supplementImpactPreview = null;
      _supplementExplanation = null;
      _comprehensiveDietAnalysis = null;
      _pendingChatExplanationDraft = null;
      _notice = 'Supplement preview is ready for review.';
    });
  }

  /// Uploads a multi-image supplement label batch and stores its review preview.
  ///
  /// Issues a single `ocrProvider` request per call by default. Set
  /// `compareOcrProviders` (dev/diagnostic only) to fan out for compare.
  Future<void> analyzeImages(
    List<SupplementImageUpload> images, {
    String ocrProvider = _defaultOcrProvider,
    bool compareOcrProviders = false,
    bool sameSupplementBatch = true,
  }) async {
    await _run(() async {
      final _SupplementAnalysisSelection selection =
          await _analyzeSupplementImagesAutomatically(
            images,
            ocrProvider: ocrProvider,
            compareOcrProviders: compareOcrProviders,
            singleProduct: sameSupplementBatch,
          );
      _lastRequestedOcrProvider = selection.provider;
      _lastSupplementBatchIsSingleProduct = sameSupplementBatch;
      _multiImageAnalysisPreview = selection.multiPreview;
      _analysisPreview = selection.preview;
      _mealAnalysisPreview = null;
      _supplementImagePaths = images
          .map((SupplementImageUpload image) => image.path)
          .toList();
      _mealImagePath = null;
      _lastRegisteredSupplement = null;
      _lastRegisteredSupplementRequest = null;
      _lastRegisteredMeal = null;
      _supplementImpactPreview = null;
      _supplementExplanation = null;
      _comprehensiveDietAnalysis = null;
      _pendingChatExplanationDraft = null;
      _notice = 'Supplement image batch is ready for review.';
    });
  }

  /// Starts supplement image analysis and lets the UI navigate away immediately.
  Future<void> startSupplementImageAnalysis(
    String imagePath, {
    bool compareOcrProviders = false,
  }) async {
    if (_analysisJob.isRunning) {
      _apiError = const ApiError(
        statusCode: 0,
        message: '이미 분석이 진행 중입니다. 완료 후 다시 시도해주세요.',
      );
      notifyListeners();
      return;
    }
    final int serial = _beginAnalysisJob('supplement');
    unawaited(
      _finishSupplementImageAnalysis(
        serial,
        imagePath,
        compareOcrProviders: compareOcrProviders,
      ),
    );
  }

  /// Starts multi-image supplement analysis without blocking navigation.
  Future<void> startSupplementImageBatchAnalysis(
    List<SupplementImageUpload> images, {
    bool compareOcrProviders = false,
    bool sameSupplementBatch = true,
  }) async {
    if (_analysisJob.isRunning) {
      _apiError = const ApiError(
        statusCode: 0,
        message: '이미 분석이 진행 중입니다. 완료 후 다시 시도해주세요.',
      );
      notifyListeners();
      return;
    }
    final int serial = _beginAnalysisJob('supplement');
    unawaited(
      _finishSupplementImageBatchAnalysis(
        serial,
        images,
        compareOcrProviders: compareOcrProviders,
        sameSupplementBatch: sameSupplementBatch,
      ),
    );
  }

  /// Starts meal image analysis without blocking navigation.
  Future<void> startMealImageAnalysis(String imagePath) async {
    if (_analysisJob.isRunning) {
      _apiError = const ApiError(
        statusCode: 0,
        message: '이미 분석이 진행 중입니다. 완료 후 다시 시도해주세요.',
      );
      notifyListeners();
      return;
    }
    final int serial = _beginAnalysisJob('meal');
    unawaited(
      _finishMealImageAnalysis(
        serial,
        imagePath,
        mealType: _mealTypeForClock(DateTime.now()),
      ),
    );
  }

  /// Marks the current completion notification as read.
  void markAnalysisCompletionRead() {
    if (!_analysisJob.hasUnreadCompletion) return;
    _analysisJob = _analysisJob.markNotificationRead();
    notifyListeners();
  }

  /// Rebuilds the merged preview for the current multi-image analysis session.
  Future<void> finalizeAnalysisSession(String analysisGroupId) async {
    await _run(() async {
      _multiImageAnalysisPreview = await _repository
          .finalizeSupplementAnalysisSession(analysisGroupId);
      _analysisPreview = _multiImageAnalysisPreview?.primaryPreview;
      _mealAnalysisPreview = null;
      _lastRegisteredSupplement = null;
      _lastRegisteredSupplementRequest = null;
      _lastRegisteredMeal = null;
      _supplementImpactPreview = null;
      _supplementExplanation = null;
      _comprehensiveDietAnalysis = null;
      _pendingChatExplanationDraft = null;
      _notice = 'Supplement image batch was finalized for review.';
    });
  }

  /// Uploads a meal image and stores its review-only food detection preview.
  Future<void> analyzeMealImage(
    String imagePath, {
    String mealType = 'unknown',
  }) async {
    await _run(() async {
      final String resolvedMealType = mealType == 'unknown'
          ? _mealTypeForClock(DateTime.now())
          : mealType;
      _mealAnalysisPreview = await _repository.analyzeMealImage(
        imagePath,
        mealType: resolvedMealType,
      );
      _analysisPreview = null;
      _multiImageAnalysisPreview = null;
      _mealImagePath = imagePath;
      _supplementImagePaths = const <String>[];
      _lastRegisteredSupplement = null;
      _lastRegisteredSupplementRequest = null;
      _lastRegisteredMeal = null;
      _supplementImpactPreview = null;
      _supplementExplanation = null;
      _comprehensiveDietAnalysis = null;
      _pendingChatExplanationDraft = null;
      _notice = 'Meal image preview is ready for review.';
    });
    await _refreshComprehensiveDietAnalysis();
  }

  /// Best-effort comprehensive diet analysis for the current meal preview.
  ///
  /// Converts the meal nutrition totals into nutrient rows and asks the backend
  /// for the C-hybrid result. Failures are swallowed so the result screen keeps
  /// working with the base meal preview when the endpoint is unavailable.
  Future<void> _refreshComprehensiveDietAnalysis() async {
    final MealImageAnalysisPreview? preview = _mealAnalysisPreview;
    if (preview == null) return;
    final List<Map<String, Object?>> ingredients =
        _comprehensiveIngredientsFromMeal(preview);
    if (ingredients.isEmpty) return;
    try {
      final ComprehensiveDietAnalysis analysis = await _repository
          .analyzeComprehensive(ingredients: ingredients);
      _comprehensiveDietAnalysis = analysis;
      notifyListeners();
    } on ApiError {
      // Score area stays hidden; base meal info still renders.
    } on FormatException {
      // Score area stays hidden; base meal info still renders.
    } on UnimplementedError {
      // Repository without the endpoint (e.g. tests) keeps the base layout.
    }
  }

  /// Maps a meal preview's nutrition totals to comprehensive nutrient rows.
  List<Map<String, Object?>> _comprehensiveIngredientsFromMeal(
    MealImageAnalysisPreview preview,
  ) {
    final Object? totals = preview.nutritionEstimateSummary['totals'];
    final Map<String, Object?> totalsMap = totals is Map<String, Object?>
        ? totals
        : totals is Map<Object?, Object?>
        ? Map<String, Object?>.from(totals)
        : const <String, Object?>{};
    const List<List<String>> nutrientFields = <List<String>>[
      <String>['carb_g', 'carbohydrate_g', '탄수화물', 'g'],
      <String>['protein_g', 'protein_g', '단백질', 'g'],
      <String>['fat_g', 'fat_g', '지방', 'g'],
      <String>['sodium_mg', 'sodium_mg', '나트륨', 'mg'],
    ];
    final List<Map<String, Object?>> rows = <Map<String, Object?>>[];
    for (final List<String> field in nutrientFields) {
      final Object? raw = totalsMap[field[0]];
      final double? amount = raw is num ? raw.toDouble() : null;
      if (amount == null) continue;
      rows.add(
        ComprehensiveIngredientInput(
          displayName: field[2],
          nutrientCode: field[1],
          amount: amount,
          unit: field[3],
        ).toJson(),
      );
    }
    return rows;
  }

  /// Confirms the current meal image preview after user review.
  Future<void> confirmMealImagePreview(MealConfirmationRequest request) async {
    final MealImageAnalysisPreview? preview = _mealAnalysisPreview;
    if (preview == null) {
      _apiError = const ApiError(
        statusCode: 0,
        message: 'Analyze a meal image before confirming it.',
      );
      notifyListeners();
      return;
    }

    await _run(() async {
      _lastRegisteredMeal = await _repository.confirmMealImagePreview(
        preview.mealId,
        request,
      );
      _mealAnalysisPreview = null;
      _analysisPreview = null;
      _multiImageAnalysisPreview = null;
      _lastRegisteredSupplement = null;
      _lastRegisteredSupplementRequest = null;
      _supplementImpactPreview = null;
      _supplementExplanation = null;
      _comprehensiveDietAnalysis = null;
      _pendingChatExplanationDraft = null;
      _dashboardSummary = await _repository.fetchDashboardSummary();
      await _refreshMealsBlockForHome();
      _notice = 'Meal record saved and dashboard refreshed.';
    });
  }

  /// Updates a saved meal record and refreshes home meal state.
  Future<void> updateMealRecord(
    String mealId,
    MealConfirmationRequest request,
  ) async {
    await _run(() async {
      _lastRegisteredMeal = await _repository.updateMealRecord(mealId, request);
      _dashboardSummary = await _repository.fetchDashboardSummary();
      await _refreshMealsBlockForHome();
      _notice = '식단 기록이 수정됐어요.';
    });
  }

  /// Deletes a saved meal record and refreshes home meal state.
  Future<void> deleteMealRecord(String mealId) async {
    await _run(() async {
      await _repository.deleteMealRecord(mealId);
      _dashboardSummary = await _repository.fetchDashboardSummary();
      await _refreshMealsBlockForHome();
      _notice = '식단 기록이 삭제됐어요.';
    });
  }

  /// Parses user-reviewed OCR text for the current preview.
  Future<void> parseOcrText(String ocrText) async {
    final SupplementAnalysisPreview? preview = _analysisPreview;
    if (preview == null) {
      _apiError = const ApiError(
        statusCode: 0,
        message: 'Upload an image before submitting OCR text.',
      );
      notifyListeners();
      return;
    }

    await _run(() async {
      _analysisPreview = await _repository.parseOcrText(
        analysisId: preview.analysisId,
        request: SupplementOCRTextParseRequest(ocrText: ocrText),
      );
      _notice = 'OCR text was parsed. Confirm fields before registration.';
    });
  }

  /// Registers a user-confirmed supplement and optionally refreshes insights.
  Future<void> registerSupplement(
    UserSupplementCreate request, {
    bool refreshImpact = false,
    bool explainWithLocalLlm = false,
  }) async {
    _consentRequired = false;
    // Confirming a supplement persists sensitive health data, so the backend
    // requires SENSITIVE_HEALTH_ANALYSIS consent (analyze only needs OCR
    // consent). When consent state is already loaded and health consent is
    // known-missing, surface an actionable message instead of a silent 403.
    // When state is not loaded yet, proceed and let the 403 mapping below
    // route to consent re-entry.
    final ConsentState? consent = _consentState;
    if (consent != null && !consent.isGranted(healthConsent)) {
      _apiError = const ApiError(
        statusCode: 403,
        message: '영양제 저장에는 민감 건강정보 분석 동의가 필요해요. 동의 화면에서 동의한 뒤 다시 저장해주세요.',
      );
      _consentRequired = true;
      _notice = null;
      notifyListeners();
      return;
    }
    await _run(() async {
      _lastRegisteredSupplement = await _repository.registerSupplement(request);
      _lastRegisteredSupplementRequest = request;
      _analysisPreview = null;
      _multiImageAnalysisPreview = null;
      _mealAnalysisPreview = null;
      _lastRegisteredMeal = null;
      _supplementImpactPreview = null;
      _supplementExplanation = null;
      _comprehensiveDietAnalysis = null;
      _pendingChatExplanationDraft = null;
      _dashboardSummary = await _repository.fetchDashboardSummary();
      _homeSupplementsFailed = false;
      await _loadSupplementsBlock();
      _notice = 'Supplement registered and dashboard refreshed.';
      if (refreshImpact || explainWithLocalLlm) {
        await _refreshPostRegistrationInsights(
          explainWithLocalLlm: explainWithLocalLlm,
        );
      }
    });
    // Defensive mapping when local consent state was stale: a 403 from the
    // confirm endpoint is consent-driven, so route the user to consent re-entry.
    if (_apiError?.statusCode == 403) {
      _consentRequired = true;
      notifyListeners();
    }
  }

  /// Calculates current supplement impact after registration or refresh.
  Future<void> previewSupplementImpact({
    SupplementImpactPreviewRequest request =
        const SupplementImpactPreviewRequest(),
  }) async {
    await _run(() async {
      _supplementImpactPreview = await _repository.previewSupplementImpact(
        request,
      );
      _supplementExplanation = null;
      _notice = 'Supplement impact check is ready.';
    });
  }

  /// Fetches the latest deterministic supplement recommendation view.
  Future<void> refreshSupplementRecommendation() async {
    await _run(() async {
      _supplementImpactPreview = await _repository
          .fetchLatestSupplementRecommendation();
      _supplementExplanation = null;
      _notice = 'Supplement check refreshed.';
    });
  }

  /// Builds a safe deterministic explanation for the current impact preview.
  Future<void> explainSupplementRecommendation({
    bool useLocalLlm = false,
  }) async {
    final SupplementImpactPreviewResponse? preview = _supplementImpactPreview;
    if (preview == null) {
      _apiError = const ApiError(
        statusCode: 0,
        message:
            'Run a supplement impact check before requesting an explanation.',
      );
      notifyListeners();
      return;
    }

    await _run(() async {
      _supplementExplanation = await _repository
          .explainSupplementRecommendation(preview, useLocalLlm: useLocalLlm);
      _notice = 'Supplement check explanation is ready.';
    });
  }

  /// Builds a safe explanation for the current analysis preview before saving.
  Future<void> explainSupplementAnalysis({bool useLocalLlm = false}) async {
    final SupplementAnalysisPreview? preview = _analysisPreview;
    if (preview == null) {
      _apiError = const ApiError(
        statusCode: 0,
        message: 'Analyze an image before requesting an explanation.',
      );
      notifyListeners();
      return;
    }

    await _run(() async {
      _supplementExplanation = await _repository.explainSupplementAnalysis(
        preview.analysisId,
        useLocalLlm: useLocalLlm,
      );
      _notice = 'Analysis explanation is ready.';
    });
  }

  /// Queues the latest supplement context so the chat tab can explain it.
  ///
  /// Returns true when a draft was created. The draft intentionally contains
  /// only user-confirmed fields and safe summaries, not raw OCR text or
  /// provider payloads.
  bool queueSupplementExplanationForChat() {
    final ChatExplanationDraft? draft = _buildSupplementChatDraft();
    if (draft == null) {
      _apiError = const ApiError(
        statusCode: 0,
        message: '저장된 영양제 정보가 없어 챗으로 설명을 보낼 수 없어요.',
      );
      _notice = null;
      notifyListeners();
      return false;
    }
    _pendingChatExplanationDraft = draft;
    _apiError = null;
    _notice = '챗으로 영양제 정보를 보냈어요.';
    notifyListeners();
    return true;
  }

  /// Clears a chat explanation draft after the chat screen consumed it.
  void markChatExplanationDraftDelivered(int id) {
    if (_pendingChatExplanationDraft?.id != id) return;
    _pendingChatExplanationDraft = null;
    notifyListeners();
  }

  /// Clears the current preview without sending data to the backend.
  void clearSupplementFlow() {
    _analysisPreview = null;
    _multiImageAnalysisPreview = null;
    _mealAnalysisPreview = null;
    _lastRegisteredMeal = null;
    _lastRegisteredSupplement = null;
    _lastRegisteredSupplementRequest = null;
    _supplementImpactPreview = null;
    _supplementExplanation = null;
    _pendingChatExplanationDraft = null;
    _lastRequestedOcrProvider = null;
    _lastSupplementBatchIsSingleProduct = true;
    if (!_analysisJob.isRunning) {
      _analysisJob = const AnalysisJobSnapshot.idle();
    }
    _apiError = null;
    _notice = null;
    _consentRequired = false;
    notifyListeners();
  }

  /// Clears transient error and notice messages.
  void clearMessages() {
    _apiError = null;
    _notice = null;
    _consentRequired = false;
    notifyListeners();
  }

  Future<void> _run(Future<void> Function() task) async {
    _busy = true;
    _apiError = null;
    _notice = null;
    _consentRequired = false;
    notifyListeners();
    try {
      await task();
    } on ApiError catch (error) {
      _apiError = error;
    } on FormatException catch (error) {
      _apiError = ApiError(statusCode: 0, message: error.message);
    } catch (error) {
      _apiError = ApiError(statusCode: 0, message: error.toString());
    } finally {
      _busy = false;
      notifyListeners();
    }
  }

  int _beginAnalysisJob(String mode) {
    _analysisJobSerial += 1;
    _analysisPreview = null;
    _multiImageAnalysisPreview = null;
    _mealAnalysisPreview = null;
    _lastRegisteredSupplement = null;
    _lastRegisteredSupplementRequest = null;
    _lastRegisteredMeal = null;
    _supplementImpactPreview = null;
    _supplementExplanation = null;
    _pendingChatExplanationDraft = null;
    _lastSupplementBatchIsSingleProduct = true;
    _analysisJob = AnalysisJobSnapshot.running(mode: mode);
    _apiError = null;
    _notice = '분석을 하고 있어요.';
    notifyListeners();
    return _analysisJobSerial;
  }

  bool _isCurrentAnalysisJob(int serial) {
    return serial == _analysisJobSerial && _analysisJob.isRunning;
  }

  Future<void> _finishSupplementImageAnalysis(
    int serial,
    String imagePath, {
    bool compareOcrProviders = false,
  }) async {
    try {
      final _SupplementAnalysisSelection selection =
          await _analyzeSupplementImageAutomatically(
            imagePath,
            compareOcrProviders: compareOcrProviders,
          );
      if (!_isCurrentAnalysisJob(serial)) return;
      _lastRequestedOcrProvider = selection.provider;
      _lastSupplementBatchIsSingleProduct = true;
      _analysisPreview = selection.preview;
      _multiImageAnalysisPreview = null;
      _mealAnalysisPreview = null;
      _supplementImagePaths = <String>[imagePath];
      _mealImagePath = null;
      _lastRegisteredSupplement = null;
      _lastRegisteredSupplementRequest = null;
      _lastRegisteredMeal = null;
      _supplementImpactPreview = null;
      _supplementExplanation = null;
      _comprehensiveDietAnalysis = null;
      _pendingChatExplanationDraft = null;
      _apiError = null;
      _notice = '분석이 완료 되었어요.';
      _analysisJob = _analysisJob.completed(message: _notice!);
    } catch (error) {
      if (!_isCurrentAnalysisJob(serial)) return;
      _apiError = _apiErrorFromObject(error);
      _notice = '분석을 완료하지 못했어요.';
      _analysisJob = _analysisJob.failed(message: _notice!);
    } finally {
      notifyListeners();
    }
  }

  Future<void> _finishSupplementImageBatchAnalysis(
    int serial,
    List<SupplementImageUpload> images, {
    bool compareOcrProviders = false,
    bool sameSupplementBatch = true,
  }) async {
    try {
      final _SupplementAnalysisSelection selection =
          await _analyzeSupplementImagesAutomatically(
            images,
            compareOcrProviders: compareOcrProviders,
            singleProduct: sameSupplementBatch,
          );
      if (!_isCurrentAnalysisJob(serial)) return;
      _lastRequestedOcrProvider = selection.provider;
      _lastSupplementBatchIsSingleProduct = sameSupplementBatch;
      _multiImageAnalysisPreview = selection.multiPreview;
      _analysisPreview = selection.preview;
      _mealAnalysisPreview = null;
      _supplementImagePaths = images
          .map((SupplementImageUpload image) => image.path)
          .toList();
      _mealImagePath = null;
      _lastRegisteredSupplement = null;
      _lastRegisteredSupplementRequest = null;
      _lastRegisteredMeal = null;
      _supplementImpactPreview = null;
      _supplementExplanation = null;
      _comprehensiveDietAnalysis = null;
      _pendingChatExplanationDraft = null;
      _apiError = null;
      _notice = '분석이 완료 되었어요.';
      _analysisJob = _analysisJob.completed(message: _notice!);
    } catch (error) {
      if (!_isCurrentAnalysisJob(serial)) return;
      _apiError = _apiErrorFromObject(error);
      _notice = '분석을 완료하지 못했어요.';
      _analysisJob = _analysisJob.failed(message: _notice!);
    } finally {
      notifyListeners();
    }
  }

  String _mealTypeForClock(DateTime value) {
    final int hour = value.toLocal().hour;
    if (hour >= 5 && hour < 11) return 'breakfast';
    if (hour >= 11 && hour < 16) return 'lunch';
    if (hour >= 16 && hour < 21) return 'dinner';
    return 'snack';
  }

  Future<void> _finishMealImageAnalysis(
    int serial,
    String imagePath, {
    required String mealType,
  }) async {
    try {
      _mealAnalysisPreview = await _repository.analyzeMealImage(
        imagePath,
        mealType: mealType,
      );
      if (!_isCurrentAnalysisJob(serial)) return;
      _analysisPreview = null;
      _multiImageAnalysisPreview = null;
      _mealImagePath = imagePath;
      _supplementImagePaths = const <String>[];
      _lastRegisteredSupplement = null;
      _lastRegisteredSupplementRequest = null;
      _lastRegisteredMeal = null;
      _supplementImpactPreview = null;
      _supplementExplanation = null;
      _comprehensiveDietAnalysis = null;
      _pendingChatExplanationDraft = null;
      _apiError = null;
      _notice = '분석이 완료 되었어요.';
      _analysisJob = _analysisJob.completed(message: _notice!);
    } catch (error) {
      if (!_isCurrentAnalysisJob(serial)) return;
      _apiError = _apiErrorFromObject(error);
      _notice = '분석을 완료하지 못했어요.';
      _analysisJob = _analysisJob.failed(message: _notice!);
    } finally {
      notifyListeners();
    }
  }

  Future<_SupplementAnalysisSelection> _analyzeSupplementImageAutomatically(
    String imagePath, {
    String ocrProvider = _defaultOcrProvider,
    bool compareOcrProviders = false,
  }) async {
    final List<String> providers = compareOcrProviders
        ? _diagnosticOcrProviders
        : <String>[ocrProvider];
    final List<_SupplementAnalysisAttempt> attempts = await Future.wait(
      providers.map((String provider) async {
        try {
          final SupplementAnalysisPreview preview = await _repository
              .analyzeSupplementImage(imagePath, ocrProvider: provider);
          return _SupplementAnalysisAttempt(
            provider: provider,
            preview: preview,
          );
        } catch (error) {
          return _SupplementAnalysisAttempt(provider: provider, error: error);
        }
      }),
    );
    final _SupplementAnalysisAttempt attempt = _selectBestSupplementAttempt(
      attempts,
    );
    return _SupplementAnalysisSelection(
      provider: attempt.provider,
      preview: attempt.preview!,
    );
  }

  Future<_SupplementAnalysisSelection> _analyzeSupplementImagesAutomatically(
    List<SupplementImageUpload> images, {
    String ocrProvider = _defaultOcrProvider,
    bool compareOcrProviders = false,
    bool singleProduct = true,
  }) async {
    final List<String> providers = compareOcrProviders
        ? _diagnosticOcrProviders
        : <String>[ocrProvider];
    final List<_SupplementAnalysisAttempt> attempts = await Future.wait(
      providers.map((String provider) async {
        try {
          // Both modes use the single /analyze-multi request: single_product fuses
          // the images into one result; distinct_products keeps each image as its
          // own supplement so the result screen renders one tab per product.
          final SupplementMultiImageAnalysisPreview multiPreview =
              await _repository.analyzeSupplementImagesOneShot(
                images,
                ocrProvider: provider,
                mergeStrategy: singleProduct
                    ? 'single_product'
                    : 'distinct_products',
              );
          final SupplementAnalysisPreview? preview =
              multiPreview.primaryPreview;
          if (preview == null) {
            throw const FormatException(
              'Supplement analysis returned no preview.',
            );
          }
          return _SupplementAnalysisAttempt(
            provider: provider,
            preview: preview,
            multiPreview: multiPreview,
          );
        } catch (error) {
          return _SupplementAnalysisAttempt(provider: provider, error: error);
        }
      }),
    );
    final _SupplementAnalysisAttempt attempt = _selectBestSupplementAttempt(
      attempts,
    );
    return _SupplementAnalysisSelection(
      provider: attempt.provider,
      preview: attempt.preview!,
      multiPreview: attempt.multiPreview,
    );
  }

  _SupplementAnalysisAttempt _selectBestSupplementAttempt(
    List<_SupplementAnalysisAttempt> attempts,
  ) {
    final List<_SupplementAnalysisAttempt> successful = attempts
        .where((_SupplementAnalysisAttempt attempt) => attempt.succeeded)
        .toList(growable: false);
    // Surface a backend retryable-capacity error (HTTP 429 rate limit or HTTP 503
    // inference-pool saturation) ahead of an empty/unusable preview: such a scan
    // must tell the user to retry, not silently render the "can't read the label"
    // fallback as if analysis had run. The backend sheds excess concurrent scans
    // with 503 inference_capacity_exceeded to protect the single local model.
    final ApiError? retryable = attempts
        .map((_SupplementAnalysisAttempt attempt) => attempt.error)
        .whereType<ApiError>()
        .where(
          (ApiError error) =>
              error.statusCode == 429 ||
              error.statusCode == 503 ||
              error.code == 'rate_limited' ||
              error.code == 'inference_capacity_exceeded',
        )
        .firstOrNull;
    if (successful.isEmpty) {
      if (retryable != null) throw retryable;
      final Object? firstError = attempts
          .map((_SupplementAnalysisAttempt attempt) => attempt.error)
          .whereType<Object>()
          .firstOrNull;
      if (firstError != null) throw firstError;
      throw const FormatException('Supplement analysis returned no results.');
    }
    successful.sort((
      _SupplementAnalysisAttempt left,
      _SupplementAnalysisAttempt right,
    ) {
      final int scoreCompare = _scoreSupplementPreview(
        right.preview!,
      ).compareTo(_scoreSupplementPreview(left.preview!));
      if (scoreCompare != 0) return scoreCompare;
      return _providerPriority(
        left.provider,
      ).compareTo(_providerPriority(right.provider));
    });
    final _SupplementAnalysisAttempt best = successful.first;
    if (retryable != null && !_isUsableSupplementPreview(best.preview!)) {
      throw retryable;
    }
    return best;
  }

  /// Whether a preview carries any structured content worth showing the user.
  bool _isUsableSupplementPreview(SupplementAnalysisPreview preview) {
    return preview.ingredientCandidates.isNotEmpty ||
        preview.labelSections.isNotEmpty ||
        (preview.parsedProduct.productName?.trim().isNotEmpty ?? false);
  }

  int _providerPriority(String provider) {
    final int index = _diagnosticOcrProviders.indexOf(provider);
    return index < 0 ? _diagnosticOcrProviders.length : index;
  }

  int _scoreSupplementPreview(SupplementAnalysisPreview preview) {
    final SupplementImagePipelineMetadata pipeline = preview.pipelineMetadata;
    final Set<String> missingSections = <String>{
      ...preview.missingRequiredSections,
      ...pipeline.missingRequiredSections,
    };
    int score = 0;
    score += preview.ingredientCandidates.length * 1000;
    score += preview.labelSections.length * 120;
    score += preview.evidenceSpans.length * 30;
    score += pipeline.sectionCount * 80;
    score += pipeline.roiCount * 30;
    if (pipeline.ocrTextPresent) score += 150;
    if (pipeline.visionRoiUsed) score += 90;
    if (pipeline.llmParserUsed) score += 80;
    if (preview.parsedProduct.productName?.trim().isNotEmpty == true) {
      score += 120;
    }
    score += switch (pipeline.ocrConfidenceBucket) {
      'high' => 90,
      'medium' => 45,
      'low' => -30,
      _ => 0,
    };
    if (missingSections.contains('supplement_facts')) score -= 650;
    if (missingSections.contains('ingredients')) score -= 650;
    if (preview.actionRequired == 'additional_label_image_required') {
      score -= 450;
    } else if (preview.actionRequired == 'blocked') {
      score -= 900;
    } else if (preview.actionRequired == 'none') {
      score += 120;
    }
    final Set<String> retakeReasons =
        preview.imageQualityReport?.retakeReasons.toSet() ?? <String>{};
    if (retakeReasons.contains('cover_only')) score -= 500;
    if (retakeReasons.contains('partial_table')) score -= 350;
    return score;
  }

  ChatExplanationDraft? _buildSupplementChatDraft() {
    final UserSupplementResponse? registered = _lastRegisteredSupplement;
    final UserSupplementCreate? request = _lastRegisteredSupplementRequest;
    final SupplementAnalysisPreview? analysis = _analysisPreview;
    if (registered == null && request == null && analysis == null) {
      return null;
    }

    final String title = _firstNonEmpty(<String?>[
      registered?.displayName,
      request?.displayName,
      analysis?.parsedProduct.productName,
      '영양제',
    ])!;
    final List<String> contextLines = _supplementChatContextLines(
      request: request,
      analysis: analysis,
    );
    final String prompt =
        '$title 성분과 함유량을 다시 정리하고, 내 건강 정보 기준으로 섭취 주의점을 쉽게 설명해줘.';
    final List<String> answer = <String>[
      '전달받은 $title 정보를 기준으로 정리할게요.',
      '',
      '성분과 함유량',
      ..._supplementChatIngredientLines(request: request, analysis: analysis),
      '',
      '내 정보 기준 확인',
      ..._supplementChatImpactLines(),
      '',
      '주의사항',
      ..._supplementChatPrecautionLines(request: request, analysis: analysis),
      '',
      if (_supplementExplanation != null) ...<String>[
        _supplementExplanation!.safeUserMessage,
        for (final String bullet in _supplementExplanation!.explanationBullets)
          '· $bullet',
        ..._supplementChatSourceLines(_supplementExplanation!),
      ],
      for (final String line in contextLines) '· $line',
      '의료적 진단·처방이 아닌 건강관리 참고 정보예요. 복용 중인 약이나 질환이 있으면 의사·약사와 확인해주세요.',
    ];

    _chatDraftSerial += 1;
    return ChatExplanationDraft(
      id: _chatDraftSerial,
      title: title,
      userPrompt: prompt,
      assistantMessage: answer.join('\n'),
      createdAt: DateTime.now(),
    );
  }

  List<String> _supplementChatSourceLines(
    SupplementRecommendationExplainResponse explanation,
  ) {
    if (explanation.sourceCitations.isEmpty) {
      return const <String>[];
    }
    return <String>[
      '',
      '출처',
      for (final SupplementExplanationSourceCitation citation
          in explanation.sourceCitations.take(4))
        '· ${citation.title} (${citation.sourcePath})',
    ];
  }

  List<String> _supplementChatContextLines({
    required UserSupplementCreate? request,
    required SupplementAnalysisPreview? analysis,
  }) {
    final List<String> lines = <String>[];
    if (request != null) {
      if (request.manufacturer?.trim().isNotEmpty == true) {
        lines.add('제조사: ${request.manufacturer!.trim()}');
      }
      if (request.ingredients.isEmpty) {
        lines.add('성분: 등록된 성분 후보가 부족해 라벨 재촬영 또는 직접 입력이 필요해요.');
      } else {
        lines.add(
          '성분: ${request.ingredients.map(_formatConfirmedIngredient).join(', ')}',
        );
      }
      lines.add('섭취량: ${_formatServing(request.serving)}');
      final SupplementIntakeSchedule? schedule = request.intakeSchedule;
      if (schedule != null) {
        lines.add('섭취 방법: ${_formatIntakeSchedule(schedule)}');
      }
      if (request.precautionSnapshot.isEmpty) {
        lines.add('주의사항: 라벨에서 확인된 주의 문구가 부족해요.');
      } else {
        lines.add('주의사항: ${request.precautionSnapshot.take(3).join(' / ')}');
      }
      return lines;
    }

    if (analysis != null) {
      final String? productName = analysis.parsedProduct.productName;
      if (productName?.trim().isNotEmpty == true) {
        lines.add('제품명 후보: ${productName!.trim()}');
      }
      if (analysis.ingredientCandidates.isEmpty) {
        lines.add('성분: OCR 성분 후보가 비어 있어 더 선명한 성분표 사진이 필요해요.');
      } else {
        lines.add(
          '성분 후보: ${analysis.ingredientCandidates.map(_formatPreviewIngredient).join(', ')}',
        );
      }
      if (analysis.precautions.isEmpty) {
        lines.add('주의사항: 주의사항 영역이 비어 있어 추가 촬영이 필요해요.');
      } else {
        lines.add(
          '주의사항 후보: ${analysis.precautions.map((SupplementPreviewPrecaution item) => item.text).take(3).join(' / ')}',
        );
      }
    }
    return lines;
  }

  List<String> _supplementChatIngredientLines({
    required UserSupplementCreate? request,
    required SupplementAnalysisPreview? analysis,
  }) {
    final List<String> lines = <String>[];
    if (request != null) {
      for (final UserSupplementIngredientInput ingredient
          in request.ingredients.take(8)) {
        lines.add('· ${_formatConfirmedIngredientForChat(ingredient)}');
      }
      if (lines.isEmpty) {
        lines.add('· 저장된 성분이 부족해 라벨 재촬영 또는 직접 입력이 필요해요.');
      }
      return lines;
    }
    if (analysis != null) {
      for (final SupplementIngredientCandidate ingredient
          in analysis.ingredientCandidates.take(8)) {
        lines.add('· ${_formatPreviewIngredientForChat(ingredient)}');
      }
    }
    if (lines.isEmpty) {
      lines.add('· 성분 후보가 비어 있어 더 선명한 성분표 사진이 필요해요.');
    }
    return lines;
  }

  List<String> _supplementChatImpactLines() {
    final SupplementImpactPreviewResponse? preview = _supplementImpactPreview;
    if (preview == null) {
      return <String>[
        '· 건강 정보 DB와 연결한 영향도 계산은 아직 완료되지 않았어요.',
        '· 우선 라벨에서 사용자가 확인한 성분 기준으로 참고 설명만 제공합니다.',
      ];
    }
    final List<String> lines = <String>['· ${preview.safeUserMessage}'];
    if (preview.excessOrDuplicateRisks.isNotEmpty) {
      lines.add(
        '· 중복·상한 확인 필요: ${preview.excessOrDuplicateRisks.map(_formatInsightForChat).take(3).join(' / ')}',
      );
    } else {
      lines.add('· 현재 계산 결과에서 중복·상한 위험 신호는 표시되지 않았어요.');
    }
    if (preview.deficiencySupportCandidates.isNotEmpty) {
      lines.add(
        '· 부족 보완 후보: ${preview.deficiencySupportCandidates.map(_formatInsightForChat).take(3).join(' / ')}',
      );
    }
    if (preview.missingProfileFields.isNotEmpty) {
      lines.add(
        '· 개인화 보강 필요: ${preview.missingProfileFields.take(3).join(', ')}',
      );
    }
    return lines;
  }

  List<String> _supplementChatPrecautionLines({
    required UserSupplementCreate? request,
    required SupplementAnalysisPreview? analysis,
  }) {
    final List<String> precautions =
        request?.precautionSnapshot.isNotEmpty == true
        ? request!.precautionSnapshot
        : analysis?.precautions
                  .map((SupplementPreviewPrecaution item) => item.text)
                  .toList(growable: false) ??
              const <String>[];
    if (precautions.isEmpty) {
      return <String>['· 라벨에서 확인된 주의 문구가 부족해요. 주의사항 영역을 한 장 더 촬영해주세요.'];
    }
    return <String>[
      for (final String precaution in precautions.take(4))
        '· ${precaution.trim()}',
    ];
  }

  String _formatConfirmedIngredient(UserSupplementIngredientInput ingredient) {
    final List<String> parts = <String>[
      _formatBilingualConfirmedIngredientName(ingredient),
    ];
    if (ingredient.amount != null) {
      parts.add(_formatAmount(ingredient.amount!));
    }
    if (ingredient.unit?.trim().isNotEmpty == true) {
      parts.add(ingredient.unit!.trim());
    }
    return parts.join(' ');
  }

  String _formatConfirmedIngredientForChat(
    UserSupplementIngredientInput ingredient,
  ) {
    final String name = _formatBilingualConfirmedIngredientName(ingredient);
    final List<String> amountParts = <String>[];
    if (ingredient.amount != null) {
      amountParts.add(_formatAmount(ingredient.amount!));
    }
    if (ingredient.unit?.trim().isNotEmpty == true) {
      amountParts.add(ingredient.unit!.trim());
    }
    if (amountParts.isEmpty) return '$name: 함량 확인 필요';
    return '$name: ${amountParts.join(' ')}';
  }

  String _formatPreviewIngredientForChat(
    SupplementIngredientCandidate ingredient,
  ) {
    final String name = _formatBilingualIngredientName(ingredient);
    final List<String> amountParts = <String>[];
    if (ingredient.amount != null) {
      amountParts.add(_formatAmount(ingredient.amount!));
    }
    if (ingredient.unit?.trim().isNotEmpty == true) {
      amountParts.add(ingredient.unit!.trim());
    }
    if (amountParts.isEmpty) return '$name: 함량 확인 필요';
    return '$name: ${amountParts.join(' ')}';
  }

  String _formatInsightForChat(SupplementNutritionInsight insight) {
    final String name = insight.nutrientName?.trim().isNotEmpty == true
        ? insight.nutrientName!.trim()
        : insight.nutrientCode.trim();
    final List<String> amountParts = <String>[];
    if (insight.estimatedTotalAmount != null) {
      amountParts.add(_formatAmount(insight.estimatedTotalAmount!));
    } else if (insight.supplementDailyAmount != null) {
      amountParts.add(_formatAmount(insight.supplementDailyAmount!));
    }
    if (insight.referenceUnit?.trim().isNotEmpty == true) {
      amountParts.add(insight.referenceUnit!.trim());
    }
    final String amountText = amountParts.isEmpty
        ? ''
        : ' ${amountParts.join(' ')}';
    return '$name$amountText';
  }

  String _formatPreviewIngredient(SupplementIngredientCandidate ingredient) {
    final List<String> parts = <String>[
      _formatBilingualIngredientName(ingredient),
    ];
    if (ingredient.amount != null) {
      parts.add(_formatAmount(ingredient.amount!));
    }
    if (ingredient.unit?.trim().isNotEmpty == true) {
      parts.add(ingredient.unit!.trim());
    }
    return parts.join(' ');
  }

  String _formatBilingualIngredientName(
    SupplementIngredientCandidate ingredient,
  ) {
    final String displayName = ingredient.displayName.trim();
    final String? originalName = _firstNonEmpty(<String?>[
      ingredient.originalName,
    ]);
    if (originalName == null ||
        originalName.toLowerCase() == displayName.toLowerCase()) {
      return displayName;
    }
    return '$displayName ($originalName)';
  }

  String _formatBilingualConfirmedIngredientName(
    UserSupplementIngredientInput ingredient,
  ) {
    final String displayName = ingredient.displayName.trim();
    final String? originalName = _firstNonEmpty(<String?>[
      ingredient.originalName,
    ]);
    if (originalName == null ||
        originalName.toLowerCase() == displayName.toLowerCase()) {
      return displayName;
    }
    return '$displayName ($originalName)';
  }

  String _formatServing(SupplementServing serving) {
    final List<String> parts = <String>[];
    if (serving.amount != null) {
      parts.add(_formatAmount(serving.amount!));
    }
    if (serving.unit?.trim().isNotEmpty == true) {
      parts.add(serving.unit!.trim());
    }
    parts.add('하루 ${_formatAmount(serving.dailyServings)}회');
    return parts.join(' ');
  }

  String _formatIntakeSchedule(SupplementIntakeSchedule schedule) {
    final List<String> parts = <String>[schedule.frequency.trim()];
    if (schedule.timeOfDay.isNotEmpty) {
      parts.add(schedule.timeOfDay.join(', '));
    }
    if (schedule.withFood?.trim().isNotEmpty == true) {
      parts.add(schedule.withFood!.trim());
    }
    return parts.where((String value) => value.isNotEmpty).join(' · ');
  }

  String _formatAmount(double value) {
    if (value == value.roundToDouble()) {
      return value.toStringAsFixed(0);
    }
    return value.toStringAsFixed(2).replaceFirst(RegExp(r'0+$'), '');
  }

  String? _firstNonEmpty(Iterable<String?> values) {
    for (final String? value in values) {
      final String? normalized = value?.trim();
      if (normalized != null && normalized.isNotEmpty) {
        return normalized;
      }
    }
    return null;
  }

  ApiError _apiErrorFromObject(Object error) {
    if (error is ApiError) return error;
    if (error is FormatException) {
      return ApiError(statusCode: 0, message: error.message);
    }
    return ApiError(statusCode: 0, message: error.toString());
  }

  Future<void> _refreshPostRegistrationInsights({
    required bool explainWithLocalLlm,
  }) async {
    try {
      _supplementImpactPreview = await _repository.previewSupplementImpact(
        const SupplementImpactPreviewRequest(),
      );
      _notice = 'Supplement registered and impact check is ready.';
    } on ApiError catch (error) {
      _apiError = error;
      _notice = 'Supplement registered, but impact check needs retry.';
      return;
    } on FormatException catch (error) {
      _apiError = ApiError(statusCode: 0, message: error.message);
      _notice = 'Supplement registered, but impact check needs retry.';
      return;
    }

    if (!explainWithLocalLlm || _supplementImpactPreview == null) {
      return;
    }
    try {
      _supplementExplanation = await _repository
          .explainSupplementRecommendation(
            _supplementImpactPreview!,
            useLocalLlm: true,
          );
      _notice = 'Supplement registered and local explanation is ready.';
    } on ApiError catch (error) {
      _apiError = error;
      _notice =
          'Supplement registered and impact check is ready; explanation needs retry.';
    } on FormatException catch (error) {
      _apiError = ApiError(statusCode: 0, message: error.message);
      _notice =
          'Supplement registered and impact check is ready; explanation needs retry.';
    }
  }

  @override
  void dispose() {
    // 보류 중인 영양제 삭제는 즉시 commit 해 유실을 막는다(백엔드 공백 3 대체).
    _supplementDeleteQueue.flush();
    _repository.close();
    super.dispose();
  }
}
