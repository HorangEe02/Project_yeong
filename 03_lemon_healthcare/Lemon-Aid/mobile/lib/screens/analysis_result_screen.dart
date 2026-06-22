// screens/analysis_result_screen.dart — 17 Pro UIUX analysis result surface.

import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../app_controller.dart';
import '../core/api/api_error.dart';
import '../features/records/records_providers.dart';
import '../features/records/records_repository.dart';
import '../features/supplements/comprehensive_analysis_models.dart';
import '../features/supplements/supplement_models.dart';
import '../shared/widgets/low_confidence_banner.dart';
import '../utils/design_tokens_v2.dart';
import '../utils/mascot_poses.dart';
import '../shared/widgets/status_state_view.dart';
import '../widgets/common/app_modals.dart';
import '../widgets/common/confidence_grade_chip.dart';
import '../widgets/common/detection_overlay.dart';
import '../widgets/common/diet_result_cards.dart';
import '../widgets/common/food_candidate_list.dart';
import '../widgets/common/portion_sheet.dart';
import '../widgets/common/pressable.dart';
import 'food_search_screen.dart';
import 'ingredient_detail_screen.dart';

/// Source-style analysis result screen backed by the real Lemon-Aid endpoints.
class AnalysisResultScreen extends StatefulWidget {
  /// Creates the analysis result screen.
  ///
  /// Args:
  ///   mode: `supplement` or `meal`.
  ///   controller: Optional real app controller for OCR/YOLO/Ollama data.
  const AnalysisResultScreen({
    super.key,
    this.mode = 'supplement',
    this.controller,
  });

  /// Analysis mode selected by the camera UI.
  final String mode;

  /// Current backend-connected app state.
  final AppController? controller;

  @override
  State<AnalysisResultScreen> createState() => _AnalysisResultScreenState();
}

class _AnalysisResultScreenState extends State<AnalysisResultScreen> {
  final TextEditingController _productNameController = TextEditingController();
  final TextEditingController _manufacturerController = TextEditingController();
  final TextEditingController _ingredientNameController =
      TextEditingController();
  final TextEditingController _ingredientAmountController =
      TextEditingController();
  final TextEditingController _ingredientUnitController =
      TextEditingController();
  final TextEditingController _frequencyController = TextEditingController();
  final TextEditingController _intakeMethodTextController =
      TextEditingController();
  final TextEditingController _precautionsController = TextEditingController();
  final TextEditingController _timeOfDayController = TextEditingController();
  // 1일 복용량 — 섭취 기준 스테퍼 값. serving.daily_servings 와
  // intake_schedule.times_per_day 로 저장된다 (가이드 10 ③-P2 7).
  int _dailyServings = 1;
  final TextEditingController _mealNameController = TextEditingController();
  final TextEditingController _mealPortionAmountController =
      TextEditingController();
  final TextEditingController _mealPortionUnitController =
      TextEditingController();
  final TextEditingController _mealKcalController = TextEditingController();
  final TextEditingController _mealCarbController = TextEditingController();
  final TextEditingController _mealProteinController = TextEditingController();
  final TextEditingController _mealFatController = TextEditingController();
  final TextEditingController _mealSodiumController = TextEditingController();
  String? _seededAnalysisId;
  String? _seededMealAnalysisId;
  // 음식 후보 선택 본편(figma 852:23): 현재 선택된 후보 인덱스 + 섭취량(인분).
  // null 이면 미선택(저신뢰/0건 폴백 진입 또는 사용자가 아직 선택 안 함).
  int? _selectedMealCandidateIndex;
  double _mealPortionAmount = 1;
  // 직접 입력(음식 검색) 폴백으로 담은 카탈로그 항목 (source: 'database_match').
  // 카메라 분석 폴백에서만 채워지며 confirm payload food_items[] 로 합류한다.
  List<MealFoodItemInput> _databaseMatchedFoods = const <MealFoodItemInput>[];
  int _selectedSupplementPreviewIndex = 0;
  List<_IngredientReviewDraft> _ingredientDrafts =
      const <_IngredientReviewDraft>[];
  bool _seedingCorrectionFields = false;
  // 영양제 분류 드롭다운(figma 855:23, 가이드 10 ③-P2 7) — 카탈로그 옵션과
  // 사용자가 고른 category_key. 카탈로그는 진입 시 1회 로드, 실패 시 빈 목록
  // 유지(드롭다운 미노출 — 백엔드 카탈로그 부재 시 조용히 강하).
  List<SupplementCategory> _supplementCategories = const <SupplementCategory>[];
  String? _selectedCategoryKey;
  // 분류 자동 선택을 분석 건당 1회만 적용하기 위한 가드. 카탈로그 로드와 프리뷰
  // 표시 순서가 비결정적이라 build()에서 재시도하되, 한번 적용하면 사용자가 바꾼
  // 선택을 덮어쓰지 않는다.
  String? _categoryAutoSelectedAnalysisId;

  bool get _isMeal => widget.mode == 'meal';

  @override
  void initState() {
    super.initState();
    for (final TextEditingController controller in _primaryActionControllers) {
      controller.addListener(_handlePrimaryActionFieldChanged);
    }
    if (!_isMeal) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _loadSupplementCategories();
      });
    }
  }

  /// 영양제 분류 카탈로그를 불러온다. 실패는 화면 오류로 올리지 않는다 —
  /// 드롭다운만 숨기고 등록은 분류 없이 진행한다(가이드 10 ③-P2 7).
  Future<void> _loadSupplementCategories() async {
    final AppController? controller = widget.controller;
    if (controller == null) {
      return;
    }
    try {
      final List<SupplementCategory> categories = await controller.repository
          .fetchSupplementCategories();
      if (!mounted) {
        return;
      }
      setState(() => _supplementCategories = categories);
    } on Object {
      // 카탈로그 부재/일시 오류 — 분류 드롭다운 비노출 유지.
    }
  }

  @override
  void dispose() {
    for (final TextEditingController controller in _primaryActionControllers) {
      controller.removeListener(_handlePrimaryActionFieldChanged);
    }
    _productNameController.dispose();
    _manufacturerController.dispose();
    _ingredientNameController.dispose();
    _ingredientAmountController.dispose();
    _ingredientUnitController.dispose();
    _frequencyController.dispose();
    _intakeMethodTextController.dispose();
    _precautionsController.dispose();
    _timeOfDayController.dispose();
    _mealNameController.dispose();
    _mealPortionAmountController.dispose();
    _mealPortionUnitController.dispose();
    _mealKcalController.dispose();
    _mealCarbController.dispose();
    _mealProteinController.dispose();
    _mealFatController.dispose();
    _mealSodiumController.dispose();
    super.dispose();
  }

  List<TextEditingController> get _primaryActionControllers =>
      <TextEditingController>[
        _productNameController,
        _manufacturerController,
        _ingredientNameController,
        _ingredientAmountController,
        _ingredientUnitController,
        _frequencyController,
        _intakeMethodTextController,
        _precautionsController,
        _timeOfDayController,
        _mealNameController,
        _mealPortionAmountController,
        _mealPortionUnitController,
        _mealKcalController,
        _mealCarbController,
        _mealProteinController,
        _mealFatController,
        _mealSodiumController,
      ];

  void _handlePrimaryActionFieldChanged() {
    if (!mounted || _seedingCorrectionFields) return;
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final AppController? controller = widget.controller;
    final List<_SupplementReviewGroup> supplementGroups =
        _supplementReviewGroups(controller);
    final int activeSupplementPreviewIndex = _activeSupplementPreviewIndex(
      supplementGroups.length,
    );
    final SupplementAnalysisPreview? preview = supplementGroups.isEmpty
        ? null
        : supplementGroups[activeSupplementPreviewIndex].preview;
    final MealImageAnalysisPreview? mealPreview =
        controller?.mealAnalysisPreview;
    if (preview != null) {
      _seedCorrectionFields(preview);
      _maybeAutoSelectCategory(preview);
    }
    if (mealPreview != null) {
      _seedMealCorrectionFields(mealPreview);
    }
    final UserSupplementResponse? registered =
        controller?.lastRegisteredSupplement;
    final MealRecordResponse? registeredMeal = controller?.lastRegisteredMeal;
    final ApiError? error = controller?.apiError;
    final AnalysisJobSnapshot? analysisJob = controller?.analysisJob;
    if (analysisJob?.isRunning == true && analysisJob?.mode == widget.mode) {
      return _AnalysisInProgressScreen(isMeal: _isMeal);
    }
    return Scaffold(
      backgroundColor: AppColor.section,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: <Widget>[
            _ResultTopBar(isMeal: _isMeal),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(
                  AppSpace.page,
                  AppSpace.lg,
                  AppSpace.page,
                  AppSpace.xl + 88,
                ),
                children: <Widget>[
                  if (error != null) ...<Widget>[
                    _StatusBanner(error: error),
                    const SizedBox(height: AppSpace.md),
                  ],
                  ..._analyzedImageHeader(controller),
                  if (!_isMeal && supplementGroups.length > 1) ...<Widget>[
                    _SupplementPreviewTabs(
                      groups: supplementGroups,
                      selectedIndex: activeSupplementPreviewIndex,
                      onSelected: (int index) {
                        setState(() {
                          _selectedSupplementPreviewIndex = index;
                          _seededAnalysisId = null;
                        });
                      },
                    ),
                    const SizedBox(height: AppSpace.md),
                  ],
                  _SummaryCard(
                    isMeal: _isMeal,
                    preview: preview,
                    mealPreview: mealPreview,
                    registered: registered,
                    registeredMeal: registeredMeal,
                    busy: controller?.busy == true,
                    onTap: !_isMeal && preview != null
                        ? () => _showOcrTextTable(context, preview)
                        : null,
                  ),
                  const SizedBox(height: AppSpace.md),
                  if (_isMeal) ...<Widget>[
                    ..._dietComprehensiveCards(
                      controller?.comprehensiveDietAnalysis,
                      registeredMeal != null,
                    ),
                    ..._mealCards(mealPreview, registeredMeal),
                  ] else
                    ..._supplementCards(preview),
                  if (!_isMeal && preview != null) ...<Widget>[
                    if (_coreIngredientCandidates(
                      preview,
                    ).isNotEmpty) ...<Widget>[
                      const SizedBox(height: AppSpace.md),
                      _CoreIngredientCard(
                        ingredients: _coreIngredientCandidates(preview),
                      ),
                    ],
                    const SizedBox(height: AppSpace.md),
                    _AnalysisExplanationCard(
                      explanation: controller?.supplementExplanation,
                      busy: controller?.busy == true,
                      onExplain: controller == null
                          ? null
                          : () => _handleAnalysisExplanation(controller),
                    ),
                    if (controller?.supplementImpactPreview !=
                        null) ...<Widget>[
                      const SizedBox(height: AppSpace.md),
                      _ImpactPreviewCard(
                        preview: controller!.supplementImpactPreview!,
                        explanation: controller.supplementExplanation,
                      ),
                    ],
                  ],
                  const SizedBox(height: AppSpace.lg),
                  const _MedicalNote(),
                ],
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpace.page,
            AppSpace.sm,
            AppSpace.page,
            AppSpace.md,
          ),
          child: _SaveButton(
            label: _primaryLabel(preview, registered, registeredMeal),
            busy: controller?.busy == true,
            onTap: () => _handlePrimaryAction(context),
          ),
        ),
      ),
    );
  }

  /// Builds the figma C-hybrid diet result cards above the base meal cards.
  ///
  /// Returns an empty list when no comprehensive analysis is available so the
  /// screen falls back to the existing meal preview layout (never blank).
  List<Widget> _dietComprehensiveCards(
    ComprehensiveDietAnalysis? analysis,
    bool registered,
  ) {
    if (analysis == null || (!analysis.hasScore && !analysis.hasContent)) {
      return const <Widget>[];
    }
    final bool lowScoreConfidence =
        analysis.hasScore &&
        ConfidenceGrade.fromConfidence(
          analysis.dietScoreConfidence,
        ).isLowConfidence;
    return <Widget>[
      if (analysis.hasScore) ...<Widget>[
        DietScoreHeaderCard(
          score: analysis.dietScore!,
          headline: analysis.dietScoreLabel,
          message: analysis.dietScoreMessage,
          confidence: analysis.dietScoreConfidence,
        ),
        if (lowScoreConfidence) ...<Widget>[
          const SizedBox(height: AppSpace.sm),
          const LowConfidenceBanner(),
        ],
        const SizedBox(height: AppSpace.md),
      ],
      // 주의 성분 카드 최우선 배치 (figma C).
      if (analysis.cautionaryComponents.isNotEmpty) ...<Widget>[
        CautionaryComponentCard(components: analysis.cautionaryComponents),
        const SizedBox(height: AppSpace.md),
      ],
      if (analysis.deficientNutrients.isNotEmpty ||
          analysis.excessiveNutrients.isNotEmpty) ...<Widget>[
        NutrientInsightGrid(
          deficient: analysis.deficientNutrients,
          excessive: analysis.excessiveNutrients,
        ),
        const SizedBox(height: AppSpace.md),
      ],
      if (analysis.purposeTargets.isNotEmpty) ...<Widget>[
        PurposeTargetCard(targets: analysis.purposeTargets),
        const SizedBox(height: AppSpace.md),
      ],
    ];
  }

  List<Widget> _mealCards(
    MealImageAnalysisPreview? preview,
    MealRecordResponse? registeredMeal,
  ) {
    if (preview == null) {
      return <Widget>[
        _ResultCard(
          color: AppColor.brand,
          icon: Icons.workspace_premium_rounded,
          label: '분석 상태',
          value: registeredMeal?.status ?? '분석 전',
          desc: registeredMeal == null
              ? '식단 사진을 먼저 분석해주세요'
              : '${registeredMeal.foodItems.length}개 음식이 식단 기록으로 저장됐어요',
          big: true,
        ),
      ];
    }
    // 등록 완료 후에는 후보 선택 UI 대신 저장 결과만 보여준다.
    if (registeredMeal != null) {
      return <Widget>[
        _ResultCard(
          color: AppColor.brand,
          icon: Icons.workspace_premium_rounded,
          label: '식단 저장 완료',
          value: registeredMeal.status,
          desc: '${registeredMeal.foodItems.length}개 음식이 식단 기록으로 저장됐어요',
          big: true,
        ),
      ];
    }

    final FoodImagePipelineMetadata pipeline = preview.pipelineMetadata;
    final List<MealFoodCandidate> candidates = preview.foodCandidates;
    final double topConfidence = candidates.isEmpty
        ? 0
        : candidates
              .map((MealFoodCandidate c) => c.confidence)
              .reduce((double a, double b) => a > b ? a : b);
    // 폴백 진입 조건(가이드 ④-1·⑥): 후보 0건 / requires_manual_entry /
    // 최고 confidence < 0.6.
    final bool forceManualFallback =
        candidates.isEmpty ||
        pipeline.requiresManualEntry ||
        topConfidence < 0.6;

    final int? selectedIndex = _selectedMealCandidateIndex;
    final MealFoodCandidate? selectedCandidate =
        (selectedIndex != null &&
            selectedIndex >= 0 &&
            selectedIndex < candidates.length)
        ? candidates[selectedIndex]
        : null;

    return <Widget>[
      if (candidates.isNotEmpty) ...<Widget>[
        FoodCandidateList(
          candidates: candidates,
          selectedIndex: _selectedMealCandidateIndex,
          onSelect: (int index) => _selectMealCandidate(preview, index),
          portionAmount: _mealPortionAmount,
          onAdjustPortion: () => _adjustMealPortion(preview),
        ),
        const SizedBox(height: AppSpace.md),
      ],
      // 인라인 섭취량 토글 + 예상 영양소 카드 — 후보가 선택됐을 때만(figma 06 심화).
      if (selectedCandidate != null) ...<Widget>[
        _PortionSegment(
          selectedAmount: _mealPortionAmount,
          onSelected: (double amount) =>
              _selectMealPortionPreset(preview, amount),
        ),
        const SizedBox(height: AppSpace.md),
        _PredictedNutrientCard(
          candidate: selectedCandidate,
          portionAmount: _mealPortionAmount,
        ),
        const SizedBox(height: AppSpace.md),
      ],
      // 저신뢰(951:76): 등급 칩만, % 비노출 — LowConfidenceBanner.
      if (forceManualFallback) ...<Widget>[
        const LowConfidenceBanner(),
        const SizedBox(height: AppSpace.md),
      ],
      // 세부 수정(선택 후보에서 시드된 값 미세 조정).
      _MealReviewCorrectionCard(
        mealNameController: _mealNameController,
        portionAmountController: _mealPortionAmountController,
        portionUnitController: _mealPortionUnitController,
        kcalController: _mealKcalController,
        carbController: _mealCarbController,
        proteinController: _mealProteinController,
        fatController: _mealFatController,
        sodiumController: _mealSodiumController,
        requiresManualEntry: pipeline.requiresManualEntry,
      ),
      const SizedBox(height: AppSpace.md),
      // 직접 입력 검색 폴백(916:23) — 후보 0건/저신뢰일 때 강조 안내.
      if (forceManualFallback && _databaseMatchedFoods.isEmpty) ...<Widget>[
        StatusStateView(
          variant: StatusStateVariant.searchEmpty,
          query: candidates.isEmpty ? '' : candidates.first.displayName,
          onPrimary: () => _openFoodSearchFallback(context),
        ),
        const SizedBox(height: AppSpace.md),
      ],
      _DatabaseMatchFallbackCard(
        pickedFoods: _databaseMatchedFoods,
        onOpenSearch: () => _openFoodSearchFallback(context),
        onRemove: (MealFoodItemInput item) {
          setState(() {
            _databaseMatchedFoods = _databaseMatchedFoods
                .where((MealFoodItemInput input) => input != item)
                .toList(growable: false);
          });
        },
      ),
    ];
  }

  List<Widget> _supplementCards(SupplementAnalysisPreview? preview) {
    final SupplementImagePipelineMetadata? pipeline = preview?.pipelineMetadata;
    final List<String> missingSections = _missingRequiredSections(preview);
    return <Widget>[
      if (pipeline != null) ...<Widget>[
        _PipelineLedStrip(metadata: pipeline),
        const SizedBox(height: AppSpace.sm),
      ],
      // 검출 오버레이(figma 946:50) — detected_product_regions[] 좌표 스케일 렌더.
      if (preview != null &&
          preview.detectedProductRegions.isNotEmpty) ...<Widget>[
        DetectionPreviewCard(regions: preview.detectedProductRegions),
        const SizedBox(height: AppSpace.sm),
      ],
      _SupplementInfoCard(
        icon: Icons.medication_rounded,
        title: '영양제명',
        body: _productInfoBody(preview),
        missingMessage: missingSections.contains('product_name')
            ? '제품명이 보이게 한 장 더 촬영해주세요'
            : null,
        onEdit: preview == null ? null : () => _editProductInfo(context),
      ),
      const SizedBox(height: AppSpace.sm),
      // 분류 드롭다운(figma 855:23) — 카탈로그가 로드됐을 때만 노출한다.
      if (_supplementCategories.isNotEmpty) ...<Widget>[
        _CategoryDropdownCard(
          categories: _supplementCategories,
          selectedKey: _selectedCategoryKey,
          onChanged: (String? key) =>
              setState(() => _selectedCategoryKey = key),
        ),
        const SizedBox(height: AppSpace.sm),
      ],
      _SupplementInfoCard(
        icon: Icons.fact_check_rounded,
        title: '상세 성분 및 함량',
        trailingCount: _ingredientAmountRows(preview).isEmpty
            ? null
            : '성분 ${_ingredientAmountRows(preview).length}개',
        bodyWidget: _ingredientInfoTable(preview),
        missingMessage: missingSections.contains('supplement_facts')
            ? '성분표가 보이게 한 장 더 촬영해주세요'
            : null,
        onEdit: preview == null ? null : () => _editIngredientInfo(context),
      ),
      const SizedBox(height: AppSpace.sm),
      _SupplementInfoCard(
        icon: Icons.schedule_rounded,
        title: '섭취 방법',
        body: _intakeInfoBody(preview),
        missingMessage: missingSections.contains('intake_method')
            ? '사진을 더 찍어서 보강해주세요.'
            : null,
        onEdit: preview == null ? null : () => _editIntakeInfo(context),
      ),
      const SizedBox(height: AppSpace.sm),
      _SupplementInfoCard(
        icon: Icons.shield_rounded,
        title: '섭취 시 주의사항',
        body: _precautionInfoBody(preview),
        missingMessage: missingSections.contains('precautions')
            ? '사진을 더 찍어서 보강해주세요.'
            : null,
        onEdit: preview == null ? null : () => _editPrecautionsInfo(context),
      ),
    ];
  }

  List<_SupplementReviewGroup> _supplementReviewGroups(
    AppController? controller,
  ) {
    final SupplementMultiImageAnalysisPreview? multiPreview =
        controller?.multiImageAnalysisPreview;
    final List<SupplementAnalysisPreview> multiPreviews =
        multiPreview?.previews ?? const <SupplementAnalysisPreview>[];
    if (multiPreviews.length > 1) {
      final SupplementAnalysisPreview? mergedPreview =
          multiPreview?.mergedPreview;
      final bool mergeAsSingleSupplement =
          controller?.lastSupplementBatchIsSingleProduct ?? true;
      if (mergeAsSingleSupplement) {
        // The user photographed one product from several angles and wants to
        // review EACH photo's own extraction. Render one result per image
        // (gallery-driven) instead of collapsing the photos into a single merged
        // result, so selecting a photo also switches the shown analysis result.
        return <_SupplementReviewGroup>[
          for (int index = 0; index < multiPreviews.length; index++)
            _SupplementReviewGroup(
              label: _supplementPreviewLabel(multiPreviews[index], index),
              preview: multiPreviews[index],
              sourcePreviews: <SupplementAnalysisPreview>[multiPreviews[index]],
            ),
        ];
      }
      // distinct_products: the user explicitly chose separate supplements and the
      // backend confirms via result_mode — render exactly one tab per image and
      // skip the OCR-identity merge heuristics that would otherwise collapse
      // facts-only photos (no product name) back into a single result.
      if (multiPreview?.isDistinctProducts ?? false) {
        return <_SupplementReviewGroup>[
          for (int index = 0; index < multiPreviews.length; index++)
            _SupplementReviewGroup(
              label: _supplementPreviewLabel(multiPreviews[index], index),
              preview: multiPreviews[index],
              sourcePreviews: <SupplementAnalysisPreview>[multiPreviews[index]],
            ),
        ];
      }
      if (mergedPreview != null &&
          _shouldUseMergedSupplementPreview(mergedPreview, multiPreviews)) {
        return <_SupplementReviewGroup>[
          _SupplementReviewGroup(
            label: _supplementPreviewLabel(mergedPreview, 0),
            preview: mergedPreview,
            sourcePreviews: multiPreviews,
          ),
        ];
      }
      return _groupSupplementPreviews(multiPreviews);
    }
    final SupplementAnalysisPreview? singlePreview =
        controller?.analysisPreview;
    if (singlePreview == null) return const <_SupplementReviewGroup>[];
    return <_SupplementReviewGroup>[
      _SupplementReviewGroup(
        label: _supplementPreviewLabel(singlePreview, 0),
        preview: singlePreview,
        sourcePreviews: <SupplementAnalysisPreview>[singlePreview],
      ),
    ];
  }

  bool _shouldUseMergedSupplementPreview(
    SupplementAnalysisPreview mergedPreview,
    List<SupplementAnalysisPreview> sourcePreviews,
  ) {
    if (!mergedPreview.hasReviewContent) return false;
    final Set<String> distinctIdentities = sourcePreviews
        .map(_supplementIdentityKey)
        .whereType<String>()
        .toSet();
    if (distinctIdentities.length > 1) return false;
    final int bestSourceScore = sourcePreviews.fold<int>(
      0,
      (int best, SupplementAnalysisPreview preview) =>
          preview.reviewContentScore > best ? preview.reviewContentScore : best,
    );
    return mergedPreview.reviewContentScore >= bestSourceScore;
  }

  List<_SupplementReviewGroup> _groupSupplementPreviews(
    List<SupplementAnalysisPreview> previews,
  ) {
    final List<_MutableSupplementReviewGroup> groups =
        <_MutableSupplementReviewGroup>[];
    for (final SupplementAnalysisPreview preview in previews) {
      final String? identityKey = _supplementIdentityKey(preview);
      if (identityKey != null) {
        final _MutableSupplementReviewGroup? existing = groups
            .cast<_MutableSupplementReviewGroup?>()
            .firstWhere(
              (_MutableSupplementReviewGroup? group) =>
                  group?.identityKey == identityKey,
              orElse: () => null,
            );
        if (existing != null) {
          existing.previews.add(preview);
          continue;
        }
        groups.add(
          _MutableSupplementReviewGroup(
            identityKey: identityKey,
            previews: <SupplementAnalysisPreview>[preview],
          ),
        );
        continue;
      }

      final _MutableSupplementReviewGroup? previous = groups.isEmpty
          ? null
          : groups.last;
      if (previous != null &&
          _canAttachIdentitylessPreview(previous, preview)) {
        previous.previews.add(preview);
        continue;
      }
      groups.add(
        _MutableSupplementReviewGroup(
          identityKey: null,
          previews: <SupplementAnalysisPreview>[preview],
        ),
      );
    }

    return <_SupplementReviewGroup>[
      for (int index = 0; index < groups.length; index++)
        _buildSupplementReviewGroup(groups[index].previews, index),
    ];
  }

  _SupplementReviewGroup _buildSupplementReviewGroup(
    List<SupplementAnalysisPreview> previews,
    int index,
  ) {
    final SupplementAnalysisPreview preview = _mergeSupplementGroupPreview(
      previews,
    );
    return _SupplementReviewGroup(
      label: _supplementPreviewLabel(preview, index),
      preview: preview,
      sourcePreviews: previews,
    );
  }

  bool _canAttachIdentitylessPreview(
    _MutableSupplementReviewGroup previous,
    SupplementAnalysisPreview preview,
  ) {
    if (!_hasSupplementFactsEvidence(preview)) return false;
    final bool previousHasProductIdentity = previous.previews.any(
      (SupplementAnalysisPreview item) => _supplementIdentityKey(item) != null,
    );
    if (!previousHasProductIdentity) return false;
    return !previous.previews.any(_hasSupplementFactsEvidence);
  }

  SupplementAnalysisPreview _mergeSupplementGroupPreview(
    List<SupplementAnalysisPreview> previews,
  ) {
    if (previews.length == 1) return previews.first;
    final SupplementAnalysisPreview base = _representativePreview(previews);
    final SupplementParsedProduct parsedProduct = _mergedParsedProduct(
      previews,
      base,
    );
    final List<SupplementIngredientCandidate> ingredients = _mergedIngredients(
      previews,
    );
    final List<SupplementPreviewLabelSection> labelSections =
        _mergedLabelSections(previews);
    final List<SupplementPreviewPrecaution> precautions = _mergedPrecautions(
      previews,
    );
    final List<SupplementPreviewFunctionalClaim> functionalClaims =
        _mergedFunctionalClaims(previews);
    final List<SupplementPreviewEvidenceSpan> evidenceSpans =
        _mergedEvidenceSpans(previews);
    final SupplementPreviewIntakeMethod intakeMethod = _mergedIntakeMethod(
      previews,
      base,
    );
    final List<String> missingRequiredSections = _calculatedMissingSections(
      parsedProduct: parsedProduct,
      ingredients: ingredients,
      labelSections: labelSections,
      intakeMethod: intakeMethod,
      precautions: precautions,
    );
    return SupplementAnalysisPreview(
      analysisId: base.analysisId,
      status: base.status,
      parsedProduct: parsedProduct,
      ingredientCandidates: ingredients,
      layoutAvailable: previews.any(
        (SupplementAnalysisPreview preview) => preview.layoutAvailable,
      ),
      layoutFallbackReason: base.layoutFallbackReason,
      labelSections: labelSections,
      intakeMethod: intakeMethod,
      precautions: precautions,
      functionalClaims: functionalClaims,
      evidenceSpans: evidenceSpans,
      imageQualityReport: base.imageQualityReport,
      analysisScope: base.analysisScope,
      actionRequired: _mergedActionRequired(previews),
      detectedProductRegions: base.detectedProductRegions,
      selectedRegionId: base.selectedRegionId,
      missingRequiredSections: missingRequiredSections,
      imageRole: 'mixed',
      multiImageGroupId: base.multiImageGroupId,
      sourceType: base.sourceType,
      identityConflict: base.identityConflict,
      pipelineMetadata: _mergedPipelineMetadata(
        previews,
        missingRequiredSections,
        labelSections.length,
      ),
      lowConfidenceFields: _mergedStrings(
        previews.map(
          (SupplementAnalysisPreview preview) => preview.lowConfidenceFields,
        ),
      ),
      warnings: _mergedStrings(
        previews.map((SupplementAnalysisPreview preview) => preview.warnings),
      ),
      algorithmVersion: base.algorithmVersion,
      sourceManifestVersion: base.sourceManifestVersion,
      expiresAt: base.expiresAt,
    );
  }

  SupplementAnalysisPreview _representativePreview(
    List<SupplementAnalysisPreview> previews,
  ) {
    SupplementAnalysisPreview best = previews.first;
    int bestScore = _previewMergeScore(best);
    for (final SupplementAnalysisPreview preview in previews.skip(1)) {
      final int score = _previewMergeScore(preview);
      if (score > bestScore) {
        best = preview;
        bestScore = score;
      }
    }
    return best;
  }

  int _previewMergeScore(SupplementAnalysisPreview preview) {
    return preview.ingredientCandidates.length * 6 +
        preview.labelSections.length * 4 +
        preview.evidenceSpans.length +
        (_nonEmpty(preview.parsedProduct.productName) == null ? 0 : 5) +
        (_nonEmpty(preview.parsedProduct.manufacturer) == null ? 0 : 2) +
        (_nonEmpty(preview.intakeMethod.text) == null ? 0 : 3) +
        preview.precautions.length * 3;
  }

  SupplementParsedProduct _mergedParsedProduct(
    List<SupplementAnalysisPreview> previews,
    SupplementAnalysisPreview base,
  ) {
    return SupplementParsedProduct(
      productName:
          _firstNonEmpty(
            previews.map(
              (SupplementAnalysisPreview preview) =>
                  preview.parsedProduct.productName,
            ),
          ) ??
          base.parsedProduct.productName,
      manufacturer:
          _firstNonEmpty(
            previews.map(
              (SupplementAnalysisPreview preview) =>
                  preview.parsedProduct.manufacturer,
            ),
          ) ??
          base.parsedProduct.manufacturer,
      servingSize:
          _firstNonEmpty(
            previews.map(
              (SupplementAnalysisPreview preview) =>
                  preview.parsedProduct.servingSize,
            ),
          ) ??
          base.parsedProduct.servingSize,
      dailyServings:
          _firstDailyServings(previews) ?? base.parsedProduct.dailyServings,
    );
  }

  List<SupplementIngredientCandidate> _mergedIngredients(
    List<SupplementAnalysisPreview> previews,
  ) {
    final Set<String> seen = <String>{};
    final List<SupplementIngredientCandidate> merged =
        <SupplementIngredientCandidate>[];
    for (final SupplementAnalysisPreview preview in previews) {
      for (final SupplementIngredientCandidate ingredient
          in preview.ingredientCandidates) {
        final String key = _ingredientKey(ingredient);
        if (seen.add(key)) merged.add(ingredient);
      }
    }
    return merged;
  }

  List<SupplementPreviewLabelSection> _mergedLabelSections(
    List<SupplementAnalysisPreview> previews,
  ) {
    final Set<String> seen = <String>{};
    final List<SupplementPreviewLabelSection> merged =
        <SupplementPreviewLabelSection>[];
    for (final SupplementAnalysisPreview preview in previews) {
      for (final SupplementPreviewLabelSection section
          in preview.labelSections) {
        final String key = <String>[
          section.sectionType,
          section.headingText ?? '',
          section.textBundle ?? '',
        ].map(_normalizeKeyPart).join('|');
        if (seen.add(key)) merged.add(section);
      }
    }
    return merged;
  }

  List<SupplementPreviewPrecaution> _mergedPrecautions(
    List<SupplementAnalysisPreview> previews,
  ) {
    final Set<String> seen = <String>{};
    final List<SupplementPreviewPrecaution> merged =
        <SupplementPreviewPrecaution>[];
    for (final SupplementAnalysisPreview preview in previews) {
      for (final SupplementPreviewPrecaution precaution
          in preview.precautions) {
        final String key = _normalizeKeyPart(precaution.text);
        if (seen.add(key)) merged.add(precaution);
      }
    }
    return merged;
  }

  List<SupplementPreviewFunctionalClaim> _mergedFunctionalClaims(
    List<SupplementAnalysisPreview> previews,
  ) {
    final Set<String> seen = <String>{};
    final List<SupplementPreviewFunctionalClaim> merged =
        <SupplementPreviewFunctionalClaim>[];
    for (final SupplementAnalysisPreview preview in previews) {
      for (final SupplementPreviewFunctionalClaim claim
          in preview.functionalClaims) {
        final String key = _normalizeKeyPart(claim.text);
        if (seen.add(key)) merged.add(claim);
      }
    }
    return merged;
  }

  List<SupplementPreviewEvidenceSpan> _mergedEvidenceSpans(
    List<SupplementAnalysisPreview> previews,
  ) {
    final Set<String> seen = <String>{};
    final List<SupplementPreviewEvidenceSpan> merged =
        <SupplementPreviewEvidenceSpan>[];
    for (final SupplementAnalysisPreview preview in previews) {
      for (final SupplementPreviewEvidenceSpan span in preview.evidenceSpans) {
        final String key = span.spanId.isEmpty
            ? _normalizeKeyPart('${span.sectionType}|${span.textExcerpt}')
            : span.spanId;
        if (seen.add(key)) merged.add(span);
      }
    }
    return merged;
  }

  SupplementPreviewIntakeMethod _mergedIntakeMethod(
    List<SupplementAnalysisPreview> previews,
    SupplementAnalysisPreview base,
  ) {
    for (final SupplementAnalysisPreview preview in previews) {
      if (_nonEmpty(preview.intakeMethod.text) != null) {
        return preview.intakeMethod;
      }
    }
    return base.intakeMethod;
  }

  SupplementImagePipelineMetadata _mergedPipelineMetadata(
    List<SupplementAnalysisPreview> previews,
    List<String> missingRequiredSections,
    int sectionCount,
  ) {
    final SupplementImagePipelineMetadata base = _representativePreview(
      previews,
    ).pipelineMetadata;
    return SupplementImagePipelineMetadata(
      intakeCompleted: previews.every(
        (SupplementAnalysisPreview preview) =>
            preview.pipelineMetadata.intakeCompleted,
      ),
      imageCount: previews.length,
      imageRole: 'mixed',
      visionRoiUsed: previews.any(
        (SupplementAnalysisPreview preview) =>
            preview.pipelineMetadata.visionRoiUsed,
      ),
      ocrStatus: _mergedStageStatus(
        previews.map(
          (SupplementAnalysisPreview preview) =>
              preview.pipelineMetadata.ocrStatus,
        ),
      ),
      visionStatus: _mergedStageStatus(
        previews.map(
          (SupplementAnalysisPreview preview) =>
              preview.pipelineMetadata.visionStatus,
        ),
      ),
      llmStatus: _mergedStageStatus(
        previews.map(
          (SupplementAnalysisPreview preview) =>
              preview.pipelineMetadata.llmStatus,
        ),
      ),
      ocrProvider:
          _firstNonEmpty(
            previews.map(
              (SupplementAnalysisPreview preview) =>
                  preview.pipelineMetadata.ocrProvider,
            ),
          ) ??
          base.ocrProvider,
      ocrTextPresent: previews.any(
        (SupplementAnalysisPreview preview) =>
            preview.pipelineMetadata.ocrTextPresent,
      ),
      ocrConfidenceBucket: _mergedConfidenceBucket(
        previews.map(
          (SupplementAnalysisPreview preview) =>
              preview.pipelineMetadata.ocrConfidenceBucket,
        ),
      ),
      roiCount: previews.fold<int>(
        0,
        (int total, SupplementAnalysisPreview preview) =>
            total + preview.pipelineMetadata.roiCount,
      ),
      sectionCount: sectionCount,
      llmParserUsed: previews.any(
        (SupplementAnalysisPreview preview) =>
            preview.pipelineMetadata.llmParserUsed,
      ),
      parserContractVersion:
          _firstNonEmpty(
            previews.map(
              (SupplementAnalysisPreview preview) =>
                  preview.pipelineMetadata.parserContractVersion,
            ),
          ) ??
          base.parserContractVersion,
      missingRequiredSections: missingRequiredSections,
      rawImageStored: previews.any(
        (SupplementAnalysisPreview preview) =>
            preview.pipelineMetadata.rawImageStored,
      ),
      rawOcrTextStored: previews.any(
        (SupplementAnalysisPreview preview) =>
            preview.pipelineMetadata.rawOcrTextStored,
      ),
    );
  }

  List<String> _calculatedMissingSections({
    required SupplementParsedProduct parsedProduct,
    required List<SupplementIngredientCandidate> ingredients,
    required List<SupplementPreviewLabelSection> labelSections,
    required SupplementPreviewIntakeMethod intakeMethod,
    required List<SupplementPreviewPrecaution> precautions,
  }) {
    final Set<String> sectionTypes = labelSections
        .map((SupplementPreviewLabelSection section) => section.sectionType)
        .toSet();
    return <String>[
      if (_nonEmpty(parsedProduct.productName) == null) 'product_name',
      if (ingredients.isEmpty && !sectionTypes.contains('supplement_facts'))
        'supplement_facts',
      if (_nonEmpty(intakeMethod.text) == null &&
          !sectionTypes.contains('intake_method'))
        'intake_method',
      if (precautions.isEmpty && !sectionTypes.contains('precautions'))
        'precautions',
    ];
  }

  String _mergedActionRequired(List<SupplementAnalysisPreview> previews) {
    if (previews.any(
      (SupplementAnalysisPreview preview) =>
          preview.actionRequired == 'blocked',
    )) {
      return 'blocked';
    }
    if (previews.any(
      (SupplementAnalysisPreview preview) =>
          preview.actionRequired == 'additional_label_image_required',
    )) {
      return 'additional_label_image_required';
    }
    if (previews.any(
      (SupplementAnalysisPreview preview) =>
          preview.actionRequired == 'review_required',
    )) {
      return 'review_required';
    }
    return previews.first.actionRequired;
  }

  bool _hasSupplementFactsEvidence(SupplementAnalysisPreview preview) {
    if (preview.ingredientCandidates.isNotEmpty) return true;
    return preview.labelSections.any(
      (SupplementPreviewLabelSection section) =>
          section.sectionType == 'supplement_facts',
    );
  }

  String? _supplementIdentityKey(SupplementAnalysisPreview preview) {
    final String? productName = _nonEmpty(preview.parsedProduct.productName);
    final String? manufacturer = _nonEmpty(preview.parsedProduct.manufacturer);
    if (productName == null && manufacturer == null) return null;
    return <String>[
      ?manufacturer,
      ?productName,
    ].map(_normalizeKeyPart).join('|');
  }

  String _supplementPreviewLabel(SupplementAnalysisPreview preview, int index) {
    final String? productName =
        _nonEmpty(preview.parsedProduct.productName) ??
        _nonEmpty(
          preview.ingredientCandidates.isEmpty
              ? null
              : preview.ingredientCandidates.first.displayName,
        );
    return productName ?? '영양제 ${index + 1}';
  }

  String _ingredientKey(SupplementIngredientCandidate ingredient) {
    return <String>[
      ingredient.displayName,
      ingredient.amount?.toString() ?? '',
      ingredient.unit ?? '',
    ].map(_normalizeKeyPart).join('|');
  }

  String _mergedStageStatus(Iterable<String> statuses) {
    final Set<String> values = statuses.toSet();
    if (values.contains('success')) return 'success';
    if (values.contains('warning')) return 'warning';
    if (values.contains('failed')) return 'failed';
    return 'skipped';
  }

  String _mergedConfidenceBucket(Iterable<String> buckets) {
    final Set<String> values = buckets.toSet();
    if (values.contains('high')) return 'high';
    if (values.contains('medium')) return 'medium';
    if (values.contains('low')) return 'low';
    if (values.contains('unknown')) return 'unknown';
    return 'none';
  }

  List<String> _mergedStrings(Iterable<List<String>> values) {
    final Set<String> seen = <String>{};
    final List<String> merged = <String>[];
    for (final List<String> list in values) {
      for (final String value in list) {
        if (seen.add(value)) merged.add(value);
      }
    }
    return merged;
  }

  String? _firstNonEmpty(Iterable<String?> values) {
    for (final String? value in values) {
      final String? normalized = _nonEmpty(value);
      if (normalized != null) return normalized;
    }
    return null;
  }

  double? _firstDailyServings(List<SupplementAnalysisPreview> previews) {
    for (final SupplementAnalysisPreview preview in previews) {
      final double? dailyServings = preview.parsedProduct.dailyServings;
      if (dailyServings != null) return dailyServings;
    }
    return null;
  }

  String _normalizeKeyPart(String value) {
    return value.trim().toLowerCase().replaceAll(RegExp(r'\s+'), ' ');
  }

  int _activeSupplementPreviewIndex(int itemCount) {
    if (itemCount == 0) return 0;
    if (_selectedSupplementPreviewIndex < 0) return 0;
    if (_selectedSupplementPreviewIndex >= itemCount) {
      return itemCount - 1;
    }
    return _selectedSupplementPreviewIndex;
  }

  List<String> _missingRequiredSections(SupplementAnalysisPreview? preview) {
    final List<String> pipelineMissing =
        preview?.pipelineMetadata.missingRequiredSections ?? const <String>[];
    if (pipelineMissing.isNotEmpty) return pipelineMissing;
    return preview?.missingRequiredSections ?? const <String>[];
  }

  String _productInfoBody(SupplementAnalysisPreview? preview) {
    final String? productName =
        _nonEmpty(_productNameController.text) ??
        preview?.parsedProduct.productName;
    final String? manufacturer =
        _nonEmpty(_manufacturerController.text) ??
        preview?.parsedProduct.manufacturer;
    if (productName == null && manufacturer == null) {
      return '제품명을 확인할 수 없어요.';
    }
    if (manufacturer == null) return productName!;
    if (productName == null) return manufacturer;
    return '$productName\n$manufacturer';
  }

  /// 성분 관련 라벨 섹션 타입(OCR 인식 텍스트 폴백 판별/표시에 사용).
  static const Set<String> _ingredientTextSectionTypes = <String>{
    'supplement_facts',
    'ingredients',
    'ingredient_candidates',
  };

  /// 구조화 성분은 없지만 OCR이 읽어온 성분 관련 라벨 글자가 있는지 본다.
  ///
  /// 섹션 검출기가 아직 학습 전이라 구조화 성분이 비더라도, OCR 자체는 글자를
  /// 읽어낸 경우가 있다. 그때 막다른 안내 대신 읽어온 글자를 보여주기 위한 판별.
  bool _hasRecognizedIngredientText(SupplementAnalysisPreview preview) {
    final bool hasSectionText = preview.labelSections.any(
      (SupplementPreviewLabelSection section) =>
          _ingredientTextSectionTypes.contains(section.sectionType) &&
          _nonEmpty(section.textBundle) != null,
    );
    if (hasSectionText) return true;
    return preview.evidenceSpans.any(
      (SupplementPreviewEvidenceSpan span) =>
          _ingredientTextSectionTypes.contains(span.sectionType) &&
          _nonEmpty(span.textExcerpt) != null,
    );
  }

  /// 읽어온 라벨 글자(성분 섹션)를 framed 카드로 보여주고, 전체 인식 텍스트는
  /// 기존 `_showOcrTextTable` 다이얼로그로, 입력은 하단 CTA로 잇는다.
  Widget _recognizedLabelTextBlock(SupplementAnalysisPreview preview) {
    final List<Widget> cards = <Widget>[];
    for (final SupplementPreviewLabelSection section in preview.labelSections) {
      if (cards.length >= 2) break;
      if (!_ingredientTextSectionTypes.contains(section.sectionType)) continue;
      final String? text = _nonEmpty(section.textBundle);
      if (text == null) continue;
      if (cards.isNotEmpty) {
        cards.add(const SizedBox(height: AppSpace.sm));
      }
      cards.add(_recognizedTextCard(_recognizedSectionHeading(section), text));
    }
    if (cards.isEmpty) {
      for (final SupplementPreviewEvidenceSpan span in preview.evidenceSpans) {
        if (cards.length >= 2) break;
        if (!_ingredientTextSectionTypes.contains(span.sectionType)) continue;
        final String? text = _nonEmpty(span.textExcerpt);
        if (text == null) continue;
        if (cards.isNotEmpty) {
          cards.add(const SizedBox(height: AppSpace.sm));
        }
        cards.add(_recognizedTextCard(_sectionLabel(span.sectionType), text));
      }
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        const Text('읽어온 라벨 글자예요. 직접 확인하고 성분을 추가해주세요.', style: AppText.caption),
        const SizedBox(height: AppSpace.sm),
        ...cards,
        const SizedBox(height: AppSpace.sm),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: () => _showOcrTextTable(context, preview),
            icon: const Icon(Icons.unfold_more_rounded, size: 18),
            label: const Text('인식된 텍스트 전체 보기'),
          ),
        ),
      ],
    );
  }

  /// 인식 텍스트 카드 제목. headingText가 있으면 우선, 없으면 성분 하위타입을
  /// 구분해 두 카드가 같은 '성분표'로 겹치지 않게 한다(공유 _sectionLabel 불변).
  static String _recognizedSectionHeading(
    SupplementPreviewLabelSection section,
  ) {
    final String? heading = _nonEmpty(section.headingText);
    if (heading != null) return heading;
    return switch (section.sectionType) {
      'supplement_facts' => '성분표',
      'ingredients' => '성분 목록',
      'ingredient_candidates' => '성분 후보',
      _ => _sectionLabel(section.sectionType),
    };
  }

  static Widget _recognizedTextCard(String heading, String text) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(
        color: AppColor.sunken,
        borderRadius: BorderRadius.circular(AppRadius.sm),
        border: Border.all(color: AppColor.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            heading,
            style: AppText.caption.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: AppSpace.xs),
          Text(
            text,
            style: AppText.body,
            maxLines: 4,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  Widget _ingredientInfoTable(SupplementAnalysisPreview? preview) {
    final List<_IngredientAmountRowData> rows = _ingredientAmountRows(preview);
    if (rows.isEmpty) {
      if (preview != null && _hasRecognizedIngredientText(preview)) {
        return _recognizedLabelTextBlock(preview);
      }
      return const Text(
        '성분명과 함량을 확인할 수 없어요.',
        style: TextStyle(
          color: AppColor.ink,
          fontSize: 15,
          height: 1.45,
          fontWeight: FontWeight.w800,
          letterSpacing: 0,
        ),
      );
    }
    return _IngredientAmountTable(
      rows: rows,
      onSelectionChanged: _setIngredientDraftSelected,
      onAllSelectionChanged: _setAllIngredientDraftsSelected,
      onRowTap: _openIngredientDetail,
      onAddIngredient: () => _addIngredientDraft(context),
    );
  }

  /// 성분을 직접 추가한다 (figma 855:23 — 가이드 10 ③-P2 7).
  ///
  /// 라벨에 없거나 OCR이 놓친 성분을 수동 입력으로 보탠다. 백엔드에 성분
  /// 검색 라우트가 없어 검색 연계 없이 수동 입력만 받는다
  /// (UserSupplementIngredientInput 은 display_name 만 필수).
  Future<void> _addIngredientDraft(BuildContext context) async {
    final TextEditingController nameController = TextEditingController();
    final TextEditingController amountController = TextEditingController();
    final TextEditingController unitController = TextEditingController();
    try {
      final bool? confirmed = await _showEditDialog(
        context,
        title: '성분 직접 추가',
        fields: <Widget>[
          _ReviewTextField(
            controller: nameController,
            label: '성분명',
            hintText: '예: 비타민 C',
          ),
          const SizedBox(height: AppSpace.sm),
          Row(
            children: <Widget>[
              Expanded(
                child: _ReviewTextField(
                  controller: amountController,
                  label: '함량',
                  hintText: '예: 500',
                ),
              ),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: _ReviewTextField(
                  controller: unitController,
                  label: '단위',
                  hintText: '예: mg',
                ),
              ),
            ],
          ),
        ],
      );
      if (confirmed == true && mounted && context.mounted) {
        final String name = nameController.text.trim();
        if (name.isEmpty) {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(const SnackBar(content: Text('성분명을 입력해주세요.')));
          return;
        }
        setState(() {
          _ingredientDrafts = <_IngredientReviewDraft>[
            ..._ingredientDrafts,
            _IngredientReviewDraft(
              displayName: name,
              originalName: null,
              amountText: amountController.text.trim(),
              unit: unitController.text.trim(),
              selected: true,
              nutrientCode: null,
              confidence: 1,
              source: 'user_confirmed',
              dailyValuePercent: null,
            ),
          ];
          _syncPrimaryIngredientControllers();
        });
      }
    } finally {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        nameController.dispose();
        amountController.dispose();
        unitController.dispose();
      });
    }
  }

  /// 성분 상세 화면(figma 12-④)으로 진입한다(가이드 ④-4 — Navigator.push).
  ///
  /// 화면이 이미 보유한 comprehensive/explain 데이터를 파라미터로 넘긴다
  /// (상세 화면에서 재호출 최소화 — KDRIs 만 신규 호출).
  Future<void> _openIngredientDetail(
    SupplementIngredientCandidate candidate,
  ) async {
    final AppController? controller = widget.controller;
    if (controller == null) return;
    HapticFeedback.selectionClick();
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (BuildContext context) => IngredientDetailScreen(
          ingredient: candidate,
          repository: controller.repository,
          comprehensive: controller.comprehensiveDietAnalysis,
          explanation: controller.supplementExplanation,
        ),
      ),
    );
  }

  List<_IngredientAmountRowData> _ingredientAmountRows(
    SupplementAnalysisPreview? preview,
  ) {
    if (_ingredientDrafts.isNotEmpty) {
      return <_IngredientAmountRowData>[
        for (int index = 0; index < _ingredientDrafts.length; index++)
          _ingredientAmountRowFromDraft(_ingredientDrafts[index], index),
      ];
    }
    final List<SupplementIngredientCandidate> candidates =
        preview?.ingredientCandidates.take(5).toList(growable: false) ??
        const <SupplementIngredientCandidate>[];
    return candidates
        .map(_ingredientAmountRowFromCandidate)
        .toList(growable: false);
  }

  /// 핵심성분 배지 카드(상위 5개)에 쓸 성분 후보 목록.
  ///
  /// 충족 등급(영양성분기준치 기반)을 보여주는 카드라, 후보 중 하나라도
  /// dailyValuePercent 가 있을 때만 목록을 돌려준다(없으면 빈 목록 → 카드 미노출).
  /// 등급 데이터가 없을 땐 상세 성분표만으로 충분해 빈 카드를 만들지 않는다.
  List<SupplementIngredientCandidate> _coreIngredientCandidates(
    SupplementAnalysisPreview preview,
  ) {
    final List<SupplementIngredientCandidate> top = preview.ingredientCandidates
        .take(5)
        .toList(growable: false);
    final bool hasAdequacyData = top.any(
      (SupplementIngredientCandidate c) => c.dailyValuePercent != null,
    );
    return hasAdequacyData ? top : const <SupplementIngredientCandidate>[];
  }

  String _intakeInfoBody(SupplementAnalysisPreview? preview) {
    if (_missingRequiredSections(preview).contains('intake_method')) {
      return '해당 이미지에는 해당하는 내용이 없습니다';
    }
    final String? directText = _nonEmpty(_intakeMethodTextController.text);
    if (directText != null) return directText;
    final String? previewText = _nonEmpty(preview?.intakeMethod.text);
    if (previewText != null) return previewText;
    final List<String> parts = <String>[
      if (_nonEmpty(_frequencyController.text) != null)
        _nonEmpty(_frequencyController.text)!,
      if (_splitCsv(_timeOfDayController.text).isNotEmpty)
        _splitCsv(_timeOfDayController.text).join(', '),
    ];
    final String structured = parts
        .where((String value) => value.trim().isNotEmpty)
        .join(' · ');
    return structured.isEmpty ? '섭취 방법을 확인할 수 없어요.' : structured;
  }

  String _precautionInfoBody(SupplementAnalysisPreview? preview) {
    if (_missingRequiredSections(preview).contains('precautions')) {
      return '해당 이미지에는 해당하는 내용이 없습니다';
    }
    final List<String> confirmed = _confirmedPrecautions();
    if (confirmed.isNotEmpty) return confirmed.join('\n');
    final List<String> precautions =
        preview?.precautions
            .map((SupplementPreviewPrecaution item) => item.text)
            .toList() ??
        const <String>[];
    if (precautions.isEmpty) {
      return '주의사항을 확인할 수 없어요.';
    }
    return precautions.join('\n');
  }

  _IngredientAmountRowData _ingredientAmountRowFromCandidate(
    SupplementIngredientCandidate candidate,
  ) {
    final String name = _bilingualIngredientName(
      candidate.displayName,
      candidate.originalName,
    );
    return _IngredientAmountRowData(
      name: name,
      originalName: _visibleOriginalName(name, candidate.originalName),
      amount: _ingredientAmountText(candidate.amount, candidate.unit),
      candidate: candidate,
    );
  }

  _IngredientAmountRowData _ingredientAmountRowFromDraft(
    _IngredientReviewDraft draft,
    int index,
  ) {
    final String displayName = draft.displayName.isEmpty
        ? '성분명 확인 필요'
        : draft.displayName;
    final String name = _bilingualIngredientName(
      displayName,
      draft.originalName,
    );
    return _IngredientAmountRowData(
      draftIndex: index,
      selected: draft.selected,
      name: name,
      originalName: _visibleOriginalName(name, draft.originalName),
      amount: _ingredientAmountText(
        _parseOptionalDouble(draft.amountText),
        draft.unit,
      ),
      candidate: draft.displayName.isEmpty
          ? null
          : SupplementIngredientCandidate(
              displayName: draft.displayName,
              originalName: draft.originalName,
              nutrientCode: draft.nutrientCode,
              amount: _parseOptionalDouble(draft.amountText),
              unit: _nonEmpty(draft.unit),
              confidence: draft.confidence,
              source: draft.source,
              dailyValuePercent: draft.dailyValuePercent,
            ),
    );
  }

  static String? _visibleOriginalName(
    String displayName,
    String? originalName,
  ) {
    final String display = displayName.trim();
    final String? original = _nonEmpty(originalName);
    if (original == null) return null;
    if (display.isNotEmpty && original.toLowerCase() == display.toLowerCase()) {
      return null;
    }
    if (display.toLowerCase().contains(original.toLowerCase())) {
      return null;
    }
    return original;
  }

  static String _bilingualIngredientName(
    String displayName,
    String? originalName,
  ) {
    final String display = displayName.trim();
    final String? original = _nonEmpty(originalName);
    if (original == null) return display;
    if (display.isNotEmpty && original.toLowerCase() == display.toLowerCase()) {
      return display;
    }
    if (display.contains(original)) return display;
    return '$display ($original)';
  }

  String _ingredientAmountText(double? amount, String? unit) {
    // 함량 칸이 좁아 긴 문구는 줄바꿈된다 → 짧게(칼럼 한 줄에 맞춤).
    if (amount == null) return '함량 확인 필요';
    final String amountText = _formatEditableAmount(amount);
    final String? normalizedUnit = _nonEmpty(unit);
    if (normalizedUnit == null) return amountText;
    return '$amountText $normalizedUnit';
  }

  Future<void> _editProductInfo(BuildContext context) async {
    await _showEditDialog(
      context,
      title: '영양제명 수정',
      fields: <Widget>[
        _ReviewTextField(
          controller: _productNameController,
          label: '제품명',
          hintText: '예: 비타민 D',
        ),
        const SizedBox(height: AppSpace.sm),
        _ReviewTextField(
          controller: _manufacturerController,
          label: '제조사',
          hintText: '라벨에 있으면 입력',
        ),
      ],
    );
  }

  Future<void> _editIngredientInfo(BuildContext context) async {
    if (_ingredientDrafts.length <= 1) {
      final bool? confirmed = await _showEditDialog(
        context,
        title: '성분 및 함량 수정',
        fields: <Widget>[
          _ReviewTextField(
            controller: _ingredientNameController,
            label: '대표 성분',
            hintText: '예: Vitamin D',
          ),
          if (_ingredientDrafts.isNotEmpty &&
              _visibleOriginalName(
                    _ingredientDrafts.first.displayName,
                    _ingredientDrafts.first.originalName,
                  ) !=
                  null) ...<Widget>[
            const SizedBox(height: AppSpace.xs),
            _OriginalIngredientNameText(
              originalName: _ingredientDrafts.first.originalName!,
            ),
          ],
          const SizedBox(height: AppSpace.sm),
          Row(
            children: <Widget>[
              Expanded(
                child: _ReviewTextField(
                  controller: _ingredientAmountController,
                  label: '함량',
                  hintText: '25',
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                ),
              ),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: _ReviewTextField(
                  controller: _ingredientUnitController,
                  label: '단위',
                  hintText: 'mg, mcg, IU',
                ),
              ),
            ],
          ),
        ],
      );
      if (confirmed == true && mounted) {
        setState(_syncSingleIngredientDraftFromFields);
      }
      return;
    }

    final List<int> selectedIndexes = <int>[
      for (int index = 0; index < _ingredientDrafts.length; index++)
        if (_ingredientDrafts[index].selected) index,
    ];
    if (selectedIndexes.length == 1) {
      await _editSingleIngredientDraft(context, selectedIndexes.single);
      return;
    }

    List<_IngredientReviewDraft> drafts = _ingredientDrafts
        .map((_IngredientReviewDraft draft) => draft)
        .toList();
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext dialogContext) {
        return StatefulBuilder(
          builder: (BuildContext context, StateSetter setDialogState) {
            return AlertDialog(
              title: const Text('성분 선택 및 수정'),
              content: SizedBox(
                width: double.maxFinite,
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      const Text(
                        '체크된 성분만 저장돼요. 기타 원료처럼 함량이 없는 후보는 기본으로 제외했어요.',
                        style: TextStyle(
                          color: AppColor.inkSecondary,
                          fontSize: 13,
                          height: 1.35,
                          letterSpacing: 0,
                        ),
                      ),
                      const SizedBox(height: AppSpace.sm),
                      _IngredientBulkSelectionBar(
                        selectedCount: drafts
                            .where(
                              (_IngredientReviewDraft draft) => draft.selected,
                            )
                            .length,
                        selectableCount: drafts.length,
                        onPressed: drafts.isEmpty
                            ? null
                            : () {
                                final bool shouldSelectAll = !drafts.every(
                                  (_IngredientReviewDraft draft) =>
                                      draft.selected,
                                );
                                setDialogState(() {
                                  drafts = <_IngredientReviewDraft>[
                                    for (final _IngredientReviewDraft draft
                                        in drafts)
                                      draft.copyWith(selected: shouldSelectAll),
                                  ];
                                });
                              },
                      ),
                      const SizedBox(height: AppSpace.sm),
                      for (int index = 0; index < drafts.length; index++) ...[
                        _IngredientReviewTile(
                          draft: drafts[index],
                          onChanged: (_IngredientReviewDraft next) {
                            setDialogState(() {
                              drafts = <_IngredientReviewDraft>[
                                for (int i = 0; i < drafts.length; i++)
                                  i == index ? next : drafts[i],
                              ];
                            });
                          },
                        ),
                        if (index < drafts.length - 1)
                          const SizedBox(height: AppSpace.sm),
                      ],
                    ],
                  ),
                ),
              ),
              actions: <Widget>[
                TextButton(
                  onPressed: () => Navigator.of(dialogContext).pop(false),
                  child: const Text('취소'),
                ),
                FilledButton(
                  onPressed: () => Navigator.of(dialogContext).pop(true),
                  child: const Text('저장'),
                ),
              ],
            );
          },
        );
      },
    );
    if (confirmed == true && mounted) {
      setState(() {
        _ingredientDrafts = drafts;
        _syncPrimaryIngredientControllers();
      });
    }
  }

  Future<void> _editSingleIngredientDraft(
    BuildContext context,
    int draftIndex,
  ) async {
    final _IngredientReviewDraft draft = _ingredientDrafts[draftIndex];
    final TextEditingController nameController = TextEditingController(
      text: draft.displayName,
    );
    final TextEditingController amountController = TextEditingController(
      text: draft.amountText,
    );
    final TextEditingController unitController = TextEditingController(
      text: draft.unit,
    );
    try {
      final bool? confirmed = await _showEditDialog(
        context,
        title: '선택 성분 수정',
        fields: <Widget>[
          _ReviewTextField(
            controller: nameController,
            label: '대표 성분',
            hintText: '예: Vitamin D',
          ),
          if (_visibleOriginalName(draft.displayName, draft.originalName) !=
              null) ...<Widget>[
            const SizedBox(height: AppSpace.xs),
            _OriginalIngredientNameText(originalName: draft.originalName!),
          ],
          const SizedBox(height: AppSpace.sm),
          Row(
            children: <Widget>[
              Expanded(
                child: _ReviewTextField(
                  controller: amountController,
                  label: '함량',
                  hintText: '25',
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                ),
              ),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: _ReviewTextField(
                  controller: unitController,
                  label: '단위',
                  hintText: 'mg, mcg, IU',
                ),
              ),
            ],
          ),
        ],
      );
      if (confirmed == true && mounted) {
        setState(() {
          _ingredientDrafts = <_IngredientReviewDraft>[
            for (int index = 0; index < _ingredientDrafts.length; index++)
              index == draftIndex
                  ? _ingredientDrafts[index].copyWith(
                      displayName: nameController.text,
                      amountText: amountController.text,
                      unit: unitController.text,
                      selected: true,
                    )
                  : _ingredientDrafts[index],
          ];
          _syncPrimaryIngredientControllers();
        });
      }
    } finally {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        nameController.dispose();
        amountController.dispose();
        unitController.dispose();
      });
    }
  }

  /// 섭취 기준 수정 — 1일 복용량 스테퍼 + 복용 주기/시간 선택 칩
  /// (figma 855:23 섭취 기준 정보, 가이드 10 ③-P2 7).
  ///
  /// 자유 텍스트 입력 대신 컨트롤로 받아 코드 오타를 막는다. 시간 코드는
  /// 기록 화면과 같은 어휘(morning·lunch·evening·night — records_models
  /// `_timeOfDayHour` 매핑)를 쓴다. OCR이 그 외 값을 읽어온 경우엔 해당
  /// 값을 칩으로 보존해 사용자 확인 없이 지우지 않는다.
  Future<void> _editIntakeInfo(BuildContext context) async {
    const Map<String, String> frequencyOptions = <String, String>{
      'daily': '매일',
      'weekly': '매주',
    };
    const Map<String, String> timeOptions = <String, String>{
      'morning': '아침',
      'lunch': '점심',
      'evening': '저녁',
      'night': '밤',
    };
    int dailyServings = _dailyServings;
    String frequency = _nonEmpty(_frequencyController.text) ?? 'daily';
    final Set<String> timeOfDay = _splitCsv(_timeOfDayController.text).toSet();
    final Map<String, String> frequencyChips = <String, String>{
      ...frequencyOptions,
      if (!frequencyOptions.containsKey(frequency)) frequency: frequency,
    };
    final Map<String, String> timeChips = <String, String>{
      ...timeOptions,
      for (final String code in timeOfDay)
        if (!timeOptions.containsKey(code)) code: code,
    };
    // 라벨 문장도 로컬 사본으로 받아 저장 시에만 커밋한다 — 취소 시 라이브
    // 컨트롤러가 누설되던 비일관(스테퍼/칩은 폐기되는데 라벨만 보존)을 막는다.
    final TextEditingController labelController = TextEditingController(
      text: _intakeMethodTextController.text,
    );
    try {
      final bool? confirmed = await showDialog<bool>(
        context: context,
        builder: (BuildContext dialogContext) {
          return StatefulBuilder(
            builder: (BuildContext context, StateSetter setDialogState) {
              return AlertDialog(
                title: const Text('섭취 기준 수정'),
                content: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      _ReviewTextField(
                        controller: labelController,
                        label: '라벨 문장',
                        hintText: '예: 하루 1회 1정',
                      ),
                      const SizedBox(height: AppSpace.md),
                      const Text(
                        '1일 복용량',
                        style: TextStyle(
                          color: AppColor.inkSecondary,
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0,
                        ),
                      ),
                      Row(
                        children: <Widget>[
                          _StepperButton(
                            icon: Icons.remove_circle_outline,
                            onPressed: dailyServings <= 1
                                ? null
                                : () =>
                                      setDialogState(() => dailyServings -= 1),
                          ),
                          SizedBox(
                            width: 56,
                            child: Text(
                              '$dailyServings회',
                              textAlign: TextAlign.center,
                              style: const TextStyle(
                                color: AppColor.ink,
                                fontSize: 17,
                                fontWeight: FontWeight.w800,
                                letterSpacing: 0,
                              ),
                            ),
                          ),
                          _StepperButton(
                            icon: Icons.add_circle_outline,
                            onPressed: dailyServings >= 10
                                ? null
                                : () =>
                                      setDialogState(() => dailyServings += 1),
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpace.md),
                      const Text(
                        '복용 주기',
                        style: TextStyle(
                          color: AppColor.inkSecondary,
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0,
                        ),
                      ),
                      const SizedBox(height: AppSpace.sm),
                      Wrap(
                        spacing: AppSpace.sm,
                        runSpacing: AppSpace.sm,
                        children: <Widget>[
                          for (final MapEntry<String, String> option
                              in frequencyChips.entries)
                            _IntakeChoiceChip(
                              label: option.value,
                              selected: frequency == option.key,
                              onSelected: () =>
                                  setDialogState(() => frequency = option.key),
                            ),
                        ],
                      ),
                      const SizedBox(height: AppSpace.md),
                      const Text(
                        '복용 시간',
                        style: TextStyle(
                          color: AppColor.inkSecondary,
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0,
                        ),
                      ),
                      const SizedBox(height: AppSpace.sm),
                      Wrap(
                        spacing: AppSpace.sm,
                        runSpacing: AppSpace.sm,
                        children: <Widget>[
                          for (final MapEntry<String, String> option
                              in timeChips.entries)
                            _IntakeChoiceChip(
                              label: option.value,
                              selected: timeOfDay.contains(option.key),
                              onSelected: () {
                                setDialogState(() {
                                  if (timeOfDay.contains(option.key)) {
                                    timeOfDay.remove(option.key);
                                  } else {
                                    timeOfDay.add(option.key);
                                  }
                                });
                              },
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
                actions: <Widget>[
                  TextButton(
                    onPressed: () => Navigator.of(dialogContext).pop(false),
                    child: const Text('취소'),
                  ),
                  FilledButton(
                    onPressed: () => Navigator.of(dialogContext).pop(true),
                    child: const Text('저장'),
                  ),
                ],
              );
            },
          );
        },
      );
      if (confirmed == true && mounted) {
        setState(() {
          _intakeMethodTextController.text = labelController.text;
          _dailyServings = dailyServings;
          _frequencyController.text = frequency;
          _timeOfDayController.text = timeOfDay.join(', ');
        });
      }
    } finally {
      labelController.dispose();
    }
  }

  Future<void> _editPrecautionsInfo(BuildContext context) async {
    await _showEditDialog(
      context,
      title: '주의사항 수정',
      fields: <Widget>[
        _ReviewTextField(
          controller: _precautionsController,
          label: '주의사항',
          hintText: '한 줄에 한 문장씩 입력',
          maxLines: 5,
        ),
      ],
    );
  }

  Future<bool?> _showEditDialog(
    BuildContext context, {
    required String title,
    required List<Widget> fields,
  }) async {
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext dialogContext) {
        return AlertDialog(
          title: Text(title),
          content: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, children: fields),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('취소'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(dialogContext).pop(true),
              child: const Text('저장'),
            ),
          ],
        );
      },
    );
    if (confirmed == true && mounted) {
      setState(() {});
    }
    return confirmed;
  }

  /// 분석 결과 상단에 사용자가 첨부/촬영한 원본 이미지를 다시 보여준다(Figma 참고).
  /// 음식은 mealImagePath, 영양제는 업로드한 모든 supplementImagePaths 를 사용한다.
  /// 경로가 없거나 로컬 파일이 사라졌으면 아무것도 그리지 않는다(미허위 — 가짜 이미지 금지).
  List<Widget> _analyzedImageHeader(AppController? controller) {
    if (controller == null) return const <Widget>[];
    if (_isMeal) {
      final String? path = controller.mealImagePath;
      if (path == null) return const <Widget>[];
      final File file = File(path);
      if (!file.existsSync()) return const <Widget>[];
      return <Widget>[
        _AnalyzedImageCard(file: file),
        const SizedBox(height: AppSpace.md),
      ];
    }
    final List<File> files = controller.supplementImagePaths
        .map(File.new)
        .where((File file) => file.existsSync())
        .toList(growable: false);
    if (files.isEmpty) return const <Widget>[];
    return <Widget>[
      _AnalyzedSupplementImageGallery(
        files: files,
        selectedIndex: _selectedSupplementPreviewIndex,
        onSelected: (int index) {
          if (index == _selectedSupplementPreviewIndex) return;
          // Selecting a photo also moves the analysis result to that image's
          // per-image preview; clear the seed marker so the correction fields
          // re-seed from the newly selected preview.
          setState(() {
            _selectedSupplementPreviewIndex = index;
            _seededAnalysisId = null;
          });
        },
      ),
      const SizedBox(height: AppSpace.md),
    ];
  }

  /// 인식된 성분명 기반으로 백엔드가 제안한 분류(suggestedCategoryKeys)를 카탈로그와
  /// 대조해 분석 건당 1회 자동 선택한다. 단일 매칭일 때만 적용해 종합비타민 등 다중
  /// 분류 제품의 오선택을 피하고, 사용자가 직접 바꾼 선택은 덮어쓰지 않는다. 카탈로그
  /// 로드와 프리뷰 표시 순서가 비결정적이라 카탈로그가 빈 동안은 표시하고 재시도한다.
  void _maybeAutoSelectCategory(SupplementAnalysisPreview preview) {
    if (_categoryAutoSelectedAnalysisId == preview.analysisId) return;
    if (_supplementCategories.isEmpty) return;
    if (_selectedCategoryKey != null) {
      _categoryAutoSelectedAnalysisId = preview.analysisId;
      return;
    }
    final Set<String> catalogKeys = _supplementCategories
        .map((SupplementCategory category) => category.categoryKey)
        .toSet();
    final List<String> matches = preview.suggestedCategoryKeys
        .where(catalogKeys.contains)
        .toList(growable: false);
    _categoryAutoSelectedAnalysisId = preview.analysisId;
    if (matches.length == 1) {
      _selectedCategoryKey = matches.first;
    }
  }

  void _seedCorrectionFields(SupplementAnalysisPreview preview) {
    if (_seededAnalysisId == preview.analysisId) return;
    _seedingCorrectionFields = true;
    try {
      _seededAnalysisId = preview.analysisId;
      // 새 분석 건이 들어오면 분류 자동 선택을 초기화해, 이전 스캔의 선택이
      // 남지 않고 _maybeAutoSelectCategory가 이번 건의 제안으로 다시 채우게 한다.
      // (같은 분석 건 재빌드 시에는 이 블록을 건너뛰므로 사용자 선택은 보존된다.)
      _selectedCategoryKey = null;
      _categoryAutoSelectedAnalysisId = null;
      _productNameController.text = preview.parsedProduct.productName ?? '';
      _manufacturerController.text = preview.parsedProduct.manufacturer ?? '';
      SupplementIngredientCandidate? firstCandidate;
      for (final SupplementIngredientCandidate candidate
          in preview.ingredientCandidates) {
        if (candidate.amount != null && _nonEmpty(candidate.unit) != null) {
          firstCandidate = candidate;
          break;
        }
      }
      _ingredientNameController.text = firstCandidate?.displayName ?? '';
      _ingredientAmountController.text = firstCandidate?.amount == null
          ? ''
          : _formatEditableAmount(firstCandidate!.amount!);
      _ingredientUnitController.text = firstCandidate?.unit ?? '';
      _ingredientDrafts = _seedIngredientDrafts(preview.ingredientCandidates);
      _frequencyController.text =
          preview.intakeMethod.structured.frequency == 'unknown'
          ? ''
          : preview.intakeMethod.structured.frequency;
      _dailyServings =
          (preview.parsedProduct.dailyServings ??
                  preview.intakeMethod.structured.timesPerDay ??
                  1)
              .round()
              .clamp(1, 10)
              .toInt();
      _intakeMethodTextController.text = preview.intakeMethod.text ?? '';
      _precautionsController.text = preview.precautions
          .map((SupplementPreviewPrecaution precaution) => precaution.text)
          .join('\n');
      _timeOfDayController.text = preview.intakeMethod.structured.timeOfDay
          .join(', ');
    } finally {
      _seedingCorrectionFields = false;
    }
  }

  void _seedMealCorrectionFields(MealImageAnalysisPreview preview) {
    if (_seededMealAnalysisId == preview.analysisId) return;
    _seededMealAnalysisId = preview.analysisId;
    // 새 분석: 최고 신뢰도 후보를 기본 선택한다(0건이면 미선택).
    final List<MealFoodCandidate> candidates = preview.foodCandidates;
    final int? initialIndex = candidates.isEmpty ? null : 0;
    _selectedMealCandidateIndex = initialIndex;
    // 후보의 kcal/탄단지는 백엔드가 추정한 1회 섭취분(portion_amount 그램)에 대한
    // 값이다. portion_amount(예: 359 g)는 인분 수가 아니라 무게이므로 섭취량 배율로
    // 쓰면 안 된다 — 감지된 분량을 그대로 1인분으로 두고, 사용자가 토글로 조절한다.
    _mealPortionAmount = 1;
    _applySelectedCandidateToFields(preview);
  }

  /// 현재 선택된 후보(+섭취량)를 식단 확인 텍스트 필드에 반영한다.
  void _applySelectedCandidateToFields(MealImageAnalysisPreview preview) {
    _seedingCorrectionFields = true;
    try {
      final int? index = _selectedMealCandidateIndex;
      final MealFoodCandidate? candidate =
          (index != null && index < preview.foodCandidates.length)
          ? preview.foodCandidates[index]
          : null;
      _mealNameController.text = candidate?.displayName ?? '';
      _mealPortionAmountController.text = candidate == null
          ? ''
          : _formatOptionalAmount(_mealPortionAmount);
      _mealPortionUnitController.text = candidate == null
          ? ''
          : (candidate.portionUnit ?? 'serving');
      _mealKcalController.text = _formatOptionalAmount(candidate?.kcal);
      _mealCarbController.text = _formatOptionalAmount(candidate?.carbG);
      _mealProteinController.text = _formatOptionalAmount(candidate?.proteinG);
      _mealFatController.text = _formatOptionalAmount(candidate?.fatG);
      _mealSodiumController.text = _formatOptionalAmount(candidate?.sodiumMg);
    } finally {
      _seedingCorrectionFields = false;
    }
  }

  /// 후보 카드 선택 — 인덱스 후보로 필드를 다시 시드한다.
  void _selectMealCandidate(MealImageAnalysisPreview preview, int index) {
    if (index < 0 || index >= preview.foodCandidates.length) return;
    setState(() {
      _selectedMealCandidateIndex = index;
      // 후보 macros는 감지된 분량(portion_amount 그램) 기준 1인분 값 — 인분 배율은 1.
      _mealPortionAmount = 1;
      _applySelectedCandidateToFields(preview);
    });
  }

  /// 인라인 섭취량 프리셋 칩 선택 — 바텀시트 없이 즉시 섭취량을 반영한다.
  void _selectMealPortionPreset(
    MealImageAnalysisPreview preview,
    double amount,
  ) {
    final int? index = _selectedMealCandidateIndex;
    if (index == null || index >= preview.foodCandidates.length) return;
    final double clamped = clampPortion(amount);
    if (clamped == _mealPortionAmount) return;
    HapticFeedback.selectionClick();
    setState(() {
      _mealPortionAmount = clamped;
      _applySelectedCandidateToFields(preview);
    });
  }

  /// 섭취량 조절 바텀시트(figma 959:80)를 열고 선택 섭취량을 반영한다.
  Future<void> _adjustMealPortion(MealImageAnalysisPreview preview) async {
    final int? index = _selectedMealCandidateIndex;
    if (index == null || index >= preview.foodCandidates.length) return;
    final PortionSelection? selection = await showPortionSheet(
      context,
      foodName: preview.foodCandidates[index].displayName,
      initialAmount: _mealPortionAmount,
    );
    if (selection == null || !mounted) return;
    setState(() {
      _mealPortionAmount = selection.portionAmount;
      _applySelectedCandidateToFields(preview);
    });
  }

  String _primaryLabel(
    SupplementAnalysisPreview? preview,
    UserSupplementResponse? registered,
    MealRecordResponse? registeredMeal,
  ) {
    if (_isMeal) {
      if (registeredMeal != null) return '홈으로 돌아가기';
      if (widget.controller?.mealAnalysisPreview == null) return '다시 촬영하기';
      final bool hasMealContent =
          _nonEmpty(_mealNameController.text) != null ||
          _databaseMatchedFoods.isNotEmpty;
      return hasMealContent ? '확인 후 식단 저장' : '음식 직접 입력';
    }
    if (registered != null) return '챗으로 설명 보내기';
    if (preview == null) return '다시 촬영하기';
    if (!_hasReviewIngredient(preview)) return '성분 직접 입력';
    return '확인 후 저장';
  }

  Future<void> _handlePrimaryAction(BuildContext context) async {
    HapticFeedback.mediumImpact();
    if (widget.controller == null) {
      context.go('/shell/home');
      return;
    }
    final AppController appController = widget.controller!;
    if (_isMeal) {
      final MealImageAnalysisPreview? mealPreview =
          appController.mealAnalysisPreview;
      if (appController.lastRegisteredMeal != null) {
        context.go('/shell/home');
        return;
      }
      if (mealPreview == null) {
        appController.clearSupplementFlow();
        if (context.mounted) {
          context.go('/shell/camera');
        }
        return;
      }
      final bool hasMealContent =
          _nonEmpty(_mealNameController.text) != null ||
          _databaseMatchedFoods.isNotEmpty;
      if (!hasMealContent) {
        // 후보 0건·저신뢰·수동입력 폴백: 직접 입력 검색으로 음식을 담는다.
        await _openFoodSearchFallback(context);
        return;
      }
      await appController.confirmMealImagePreview(
        _mealConfirmationRequest(mealPreview),
      );
      return;
    }
    if (appController.lastRegisteredSupplement != null) {
      final bool queued = appController.queueSupplementExplanationForChat();
      if (queued && context.mounted) {
        context.go('/shell/chat');
      }
      return;
    }
    final List<_SupplementReviewGroup> reviewGroups = _supplementReviewGroups(
      appController,
    );
    final SupplementAnalysisPreview? preview = reviewGroups.isEmpty
        ? null
        : reviewGroups[_activeSupplementPreviewIndex(reviewGroups.length)]
              .preview;
    if (preview == null) {
      appController.clearSupplementFlow();
      if (context.mounted) {
        context.go('/shell/camera');
      }
      return;
    }
    if (!_hasReviewIngredient(preview)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('성분명을 입력하거나 라벨 사진을 다시 추가해주세요.')),
      );
      return;
    }
    final SupplementImpactPreviewResponse? impact =
        appController.supplementImpactPreview;
    if (impact != null && _hasHighSeverityRisk(impact)) {
      final bool proceed = await _confirmInteractionSoftBlock(
        context,
        impact,
        preview,
      );
      if (!proceed || !context.mounted) {
        return;
      }
    }
    await appController.registerSupplement(
      _registrationRequest(preview),
      refreshImpact: true,
      explainWithLocalLlm: true,
    );
    if (!context.mounted || appController.lastRegisteredSupplement == null) {
      return;
    }
    final bool queued = appController.queueSupplementExplanationForChat();
    if (queued) {
      GoRouter.maybeOf(context)?.go('/shell/chat');
    }
  }

  Future<void> _showOcrTextTable(
    BuildContext context,
    SupplementAnalysisPreview preview,
  ) async {
    final List<_OcrTextRowData> rows = _ocrTextRows(preview);
    await showDialog<void>(
      context: context,
      builder: (BuildContext dialogContext) {
        return AlertDialog(
          title: const Text('OCR 텍스트 전체'),
          content: SizedBox(
            key: const ValueKey<String>('ocr-text-table'),
            width: double.maxFinite,
            child: SingleChildScrollView(
              child: rows.isEmpty
                  ? const Text(
                      '표시할 OCR 텍스트가 없습니다.',
                      style: TextStyle(
                        color: AppColor.inkSecondary,
                        fontSize: 14,
                        height: 1.45,
                        letterSpacing: 0,
                      ),
                    )
                  : _OcrTextTable(rows: rows),
            ),
          ),
          actions: <Widget>[
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('닫기'),
            ),
          ],
        );
      },
    );
  }

  List<_OcrTextRowData> _ocrTextRows(SupplementAnalysisPreview preview) {
    final List<_OcrTextRowData> rows = <_OcrTextRowData>[];
    final Set<String> seen = <String>{};

    void addRow({
      required String section,
      required String source,
      required String text,
      String confidence = '-',
    }) {
      final String? normalizedText = _nonEmpty(text);
      if (normalizedText == null) return;
      final String key = normalizedText.toLowerCase();
      if (!seen.add(key)) return;
      rows.add(
        _OcrTextRowData(
          section: section,
          source: source,
          text: normalizedText,
          confidence: confidence,
        ),
      );
    }

    // Full OCR source text first (present only when the backend opt-in
    // store_raw_ocr_text is enabled), so the modal can show the raw source.
    final String? rawOcrText = _nonEmpty(preview.rawOcrText);
    if (rawOcrText != null) {
      addRow(section: 'OCR 원문', source: 'RAW', text: rawOcrText);
    }
    // Count the RAW row separately so it does not short-circuit the structured
    // fallback below — parsed product/ingredient rows must still render when the
    // label produced no evidence spans or sections.
    final int baseRowCount = rows.length;

    for (final SupplementPreviewEvidenceSpan span in preview.evidenceSpans) {
      final String? text = _nonEmpty(span.textExcerpt);
      if (text == null) continue;
      addRow(
        section: _sectionLabel(span.sectionType),
        source: span.sourceType.toUpperCase(),
        text: text,
        confidence: _confidenceLabel(span.confidence),
      );
    }
    for (final SupplementPreviewLabelSection section in preview.labelSections) {
      final String? text = _nonEmpty(section.textBundle);
      if (text == null) continue;
      addRow(
        section: _sectionLabel(section.sectionType),
        source: 'SECTION',
        text: text,
        confidence: _confidenceLabel(section.confidence),
      );
    }
    if (rows.length > baseRowCount) return rows;

    final SupplementParsedProduct product = preview.parsedProduct;
    final String? productName = _nonEmpty(product.productName);
    if (productName != null) {
      addRow(section: '제품명', source: 'PARSED', text: productName);
    }
    final String? manufacturer = _nonEmpty(product.manufacturer);
    if (manufacturer != null) {
      addRow(section: '제조사', source: 'PARSED', text: manufacturer);
    }
    for (final SupplementIngredientCandidate ingredient
        in preview.ingredientCandidates) {
      final String? text = _ingredientCandidateOcrText(ingredient);
      if (text == null) continue;
      addRow(
        section: '성분표',
        source: ingredient.source.toUpperCase(),
        text: text,
        confidence: _confidenceLabel(ingredient.confidence),
      );
    }
    final String? intakeMethod = _nonEmpty(preview.intakeMethod.text);
    if (intakeMethod != null) {
      addRow(
        section: '섭취 방법',
        source: 'PARSED',
        text: intakeMethod,
        confidence: _confidenceLabel(preview.intakeMethod.confidence),
      );
    }
    for (final SupplementPreviewPrecaution precaution in preview.precautions) {
      addRow(
        section: '주의사항',
        source: 'PARSED',
        text: precaution.text,
        confidence: _confidenceLabel(precaution.confidence),
      );
    }
    for (final SupplementPreviewFunctionalClaim claim
        in preview.functionalClaims) {
      addRow(
        section: '기능성',
        source: 'PARSED',
        text: claim.text,
        confidence: _confidenceLabel(claim.confidence),
      );
    }
    if (rows.isEmpty) {
      final SupplementImagePipelineMetadata metadata = preview.pipelineMetadata;
      final String statusText = metadata.ocrTextPresent
          ? 'OCR 결과가 구조화 단계로 전달됐지만 원문은 저장하지 않도록 설정되어 있어요. 카드에 표시된 추출값을 확인해주세요.'
          : 'OCR이 읽을 수 있는 텍스트를 만들지 못했어요. 라벨 영역을 더 크게 촬영하거나 OCR/ROI 설정을 확인해주세요.';
      addRow(section: 'OCR 상태', source: 'PIPELINE', text: statusText);
    }
    return rows;
  }

  static String? _ingredientCandidateOcrText(
    SupplementIngredientCandidate ingredient,
  ) {
    final String? displayName = _nonEmpty(ingredient.displayName);
    if (displayName == null) return null;
    final String? originalName = _nonEmpty(ingredient.originalName);
    final String? amountText = ingredient.amount == null
        ? null
        : _formatEditableAmount(ingredient.amount!);
    final String? unit = _nonEmpty(ingredient.unit);
    final String nameText = originalName == null || originalName == displayName
        ? displayName
        : '$displayName ($originalName)';
    final String? amountWithUnit = amountText == null
        ? null
        : unit == null
        ? amountText
        : '$amountText $unit';
    final String? dailyValue = ingredient.dailyValuePercent == null
        ? null
        : '${_formatEditableAmount(ingredient.dailyValuePercent!)}% DV';
    return <String>[nameText, ?amountWithUnit, ?dailyValue].join(' · ');
  }

  void _setIngredientDraftSelected(int index, bool selected) {
    if (index < 0 || index >= _ingredientDrafts.length) return;
    setState(() {
      _ingredientDrafts = <_IngredientReviewDraft>[
        for (int i = 0; i < _ingredientDrafts.length; i++)
          i == index
              ? _ingredientDrafts[i].copyWith(selected: selected)
              : _ingredientDrafts[i],
      ];
      _syncPrimaryIngredientControllers();
    });
  }

  void _setAllIngredientDraftsSelected(bool selected) {
    if (_ingredientDrafts.isEmpty) return;
    setState(() {
      _ingredientDrafts = <_IngredientReviewDraft>[
        for (final _IngredientReviewDraft draft in _ingredientDrafts)
          draft.copyWith(selected: selected),
      ];
      _syncPrimaryIngredientControllers();
    });
  }

  static String _sectionLabel(String sectionType) {
    return switch (sectionType) {
      'supplement_facts' || 'ingredients' || 'ingredient_candidates' => '성분표',
      'intake_method' => '섭취 방법',
      'precautions' => '주의사항',
      'product_name' => '제품명',
      _ => sectionType,
    };
  }

  static String _confidenceLabel(double? confidence) {
    if (confidence == null) return '-';
    return '${(confidence * 100).round()}%';
  }

  MealConfirmationRequest _mealConfirmationRequest(
    MealImageAnalysisPreview preview,
  ) {
    // 선택된 후보(없으면 첫 후보) 기준으로 confidence/source 추적값을 가져온다.
    final int? selectedIndex = _selectedMealCandidateIndex;
    final MealFoodCandidate? selectedCandidate =
        (selectedIndex != null && selectedIndex < preview.foodCandidates.length)
        ? preview.foodCandidates[selectedIndex]
        : (preview.foodCandidates.isEmpty
              ? null
              : preview.foodCandidates.first);
    final List<MealFoodItemInput> foodItems = <MealFoodItemInput>[
      // 손으로 채운 대표 항목은 이름이 있을 때만 포함한다. 검색 폴백만으로
      // 끼니를 만들 수 있도록(이름 미입력 + database_match 만) 비어 있으면 생략.
      if (_nonEmpty(_mealNameController.text) != null)
        MealFoodItemInput(
          displayName: _mealNameController.text.trim(),
          portionAmount: _parseOptionalDouble(
            _mealPortionAmountController.text,
          ),
          portionUnit: _nonEmpty(_mealPortionUnitController.text),
          kcal: _parseOptionalDouble(_mealKcalController.text),
          carbG: _parseOptionalDouble(_mealCarbController.text),
          proteinG: _parseOptionalDouble(_mealProteinController.text),
          fatG: _parseOptionalDouble(_mealFatController.text),
          sodiumMg: _parseOptionalDouble(_mealSodiumController.text),
          confidence: selectedCandidate?.confidence,
          source: selectedCandidate?.source ?? 'manual',
        ),
      // 직접 입력 검색에서 담은 카탈로그 항목 (source: 'database_match').
      ..._databaseMatchedFoods,
    ];
    // 모두 비어 있으면(예외적 호출) 빈 식단 행 하나로 폴백한다.
    return MealConfirmationRequest(
      analysisId: preview.analysisId,
      mealType: preview.mealType,
      eatenAt: preview.eatenAt,
      foodItems: foodItems.isEmpty
          ? <MealFoodItemInput>[const MealFoodItemInput(displayName: '식단')]
          : foodItems,
    );
  }

  /// Opens the direct-input food search fallback and merges picked catalog
  /// items into the meal confirm payload (guide 07 ⑦ — camera fallback only).
  Future<void> _openFoodSearchFallback(BuildContext context) async {
    final RecordsRepository repository = ProviderScope.containerOf(
      context,
    ).read(recordsRepositoryProvider);
    final List<MealFoodItemInput>? picked = await Navigator.of(context)
        .push<List<MealFoodItemInput>>(
          MaterialPageRoute<List<MealFoodItemInput>>(
            builder: (BuildContext context) =>
                FoodSearchScreen(repository: repository),
          ),
        );
    if (picked == null || picked.isEmpty || !mounted) return;
    setState(() {
      // 중복 카탈로그 id 는 한 번만 합류시킨다.
      final Set<String> seen = <String>{
        for (final MealFoodItemInput item in _databaseMatchedFoods)
          if (item.foodCatalogItemId != null) item.foodCatalogItemId!,
      };
      _databaseMatchedFoods = <MealFoodItemInput>[
        ..._databaseMatchedFoods,
        for (final MealFoodItemInput item in picked)
          if (item.foodCatalogItemId == null ||
              seen.add(item.foodCatalogItemId!))
            item,
      ];
    });
  }

  UserSupplementCreate _registrationRequest(SupplementAnalysisPreview preview) {
    final List<UserSupplementIngredientInput> ingredients =
        _selectedIngredientInputs();
    final String fallbackName = ingredients.isEmpty
        ? '영양제'
        : ingredients.first.displayName;
    return UserSupplementCreate(
      analysisId: preview.analysisId,
      displayName: _nonEmpty(_productNameController.text) ?? fallbackName,
      manufacturer: _nonEmpty(_manufacturerController.text),
      ingredients: ingredients,
      serving: SupplementServing(
        amount: preview.intakeMethod.structured.amountPerTime,
        unit:
            _nonEmpty(preview.parsedProduct.servingSize) ??
            _nonEmpty(preview.intakeMethod.structured.amountUnit),
        // 사용자 확정 스테퍼 값 — 섭취 기준 컨트롤 (가이드 10 ③-P2 7).
        dailyServings: _dailyServings.toDouble(),
      ),
      intakeSchedule: SupplementIntakeSchedule(
        frequency: _nonEmpty(_frequencyController.text) ?? 'daily',
        timeOfDay: _splitCsv(_timeOfDayController.text),
        timesPerDay: _dailyServings.toDouble(),
      ),
      // 사용자가 고른 분류 키 — 미선택 시 null (가이드 10 ③-P2 7).
      categoryKey: _selectedCategoryKey,
      precautionSnapshot: _confirmedPrecautions(),
      evidenceRefs: _registrationEvidenceRefs(preview),
    );
  }

  List<String> _registrationEvidenceRefs(SupplementAnalysisPreview preview) {
    final Set<String> seen = <String>{};
    final List<String> refs = <String>[];
    for (final SupplementPreviewEvidenceSpan span in preview.evidenceSpans) {
      final String ref = span.spanId.trim();
      if (ref.isEmpty || !seen.add(ref)) {
        continue;
      }
      refs.add(ref);
      if (refs.length >= 80) {
        break;
      }
    }
    return refs;
  }

  String _registrationIngredientSource(String source) {
    final String normalized = source.trim();
    if (normalized == 'user_confirmed' || normalized == 'ocr_llm_preview') {
      return normalized;
    }
    return 'ocr_llm_preview';
  }

  List<String> _confirmedPrecautions() {
    final Set<String> seen = <String>{};
    final List<String> values = <String>[];
    for (final String line in _precautionsController.text.split('\n')) {
      final String normalized = line.trim();
      if (normalized.isEmpty || !seen.add(normalized)) {
        continue;
      }
      values.add(normalized);
      if (values.length >= 40) {
        break;
      }
    }
    return values;
  }

  bool _hasReviewIngredient(SupplementAnalysisPreview preview) {
    return _selectedIngredientInputs().isNotEmpty ||
        _correctedIngredient() != null;
  }

  Future<void> _handleAnalysisExplanation(AppController controller) async {
    HapticFeedback.selectionClick();
    await controller.explainSupplementAnalysis(useLocalLlm: true);
  }

  /// Whether the impact preview carries a high-severity interaction risk that
  /// warrants a soft block before registration.
  bool _hasHighSeverityRisk(SupplementImpactPreviewResponse impact) {
    return impact.excessOrDuplicateRisks.isNotEmpty;
  }

  /// Shows the soft-block interaction warning and resolves to the user choice.
  ///
  /// Returns true when the user chooses to save anyway, false otherwise. When
  /// the user taps '안전 정보 자세히 보기' the relevant ingredient detail is opened
  /// (가이드 ④-4) and the save is aborted (false).
  Future<bool> _confirmInteractionSoftBlock(
    BuildContext context,
    SupplementImpactPreviewResponse impact,
    SupplementAnalysisPreview preview,
  ) async {
    final String body =
        _nonEmpty(impact.safeUserMessage) ?? '함께 드시는 영양제와 겹치는 성분이 있어요.';
    final SupplementIngredientCandidate? detailCandidate =
        _softBlockDetailCandidate(impact, preview);
    bool saveAnyway = false;
    bool viewDetail = false;
    await showInteractionWarningDialog(
      context,
      body: body,
      onViewDetail: () {
        viewDetail = true;
      },
      onSaveAnyway: () {
        saveAnyway = true;
      },
    );
    if (viewDetail && detailCandidate != null && mounted) {
      await _openIngredientDetail(detailCandidate);
    }
    return saveAnyway;
  }

  /// Picks the ingredient to open from the soft-block detail action: the first
  /// preview candidate whose name matches an excess/duplicate risk nutrient,
  /// else the first reviewable candidate.
  SupplementIngredientCandidate? _softBlockDetailCandidate(
    SupplementImpactPreviewResponse impact,
    SupplementAnalysisPreview preview,
  ) {
    final List<SupplementIngredientCandidate> candidates =
        preview.ingredientCandidates;
    if (candidates.isEmpty) return null;
    final Set<String> riskCodes = <String>{
      for (final SupplementNutritionInsight risk
          in impact.excessOrDuplicateRisks)
        risk.nutrientCode,
    };
    for (final SupplementIngredientCandidate candidate in candidates) {
      final String? code = candidate.nutrientCode;
      if (code != null && riskCodes.contains(code)) return candidate;
    }
    return candidates.first;
  }

  UserSupplementIngredientInput? _correctedIngredient() {
    final String? name = _nonEmpty(_ingredientNameController.text);
    if (name == null) return null;
    return UserSupplementIngredientInput(
      displayName: name,
      originalName: _primaryIngredientOriginalName(name),
      nutrientCode: null,
      amount: _parseOptionalDouble(_ingredientAmountController.text),
      unit: _nonEmpty(_ingredientUnitController.text),
      confidence: 1,
      source: 'user_confirmed',
    );
  }

  List<UserSupplementIngredientInput> _selectedIngredientInputs() {
    final List<UserSupplementIngredientInput> selected = _ingredientDrafts
        .where(
          (_IngredientReviewDraft draft) => draft.selected && draft.isValid,
        )
        .map(
          (_IngredientReviewDraft draft) => draft.toInput(
            source: _registrationIngredientSource(draft.source),
          ),
        )
        .toList(growable: false);
    if (selected.isNotEmpty) return selected;
    final UserSupplementIngredientInput? corrected = _correctedIngredient();
    if (corrected == null) return const <UserSupplementIngredientInput>[];
    return <UserSupplementIngredientInput>[corrected];
  }

  String? _primaryIngredientOriginalName(String displayName) {
    final String displayKey = displayName.trim().toLowerCase();
    for (final _IngredientReviewDraft draft in _ingredientDrafts) {
      if (draft.displayName.trim().toLowerCase() == displayKey) {
        return _nonEmpty(draft.originalName);
      }
    }
    for (final _IngredientReviewDraft draft in _ingredientDrafts) {
      final String? originalName = _nonEmpty(draft.originalName);
      if (originalName != null) return originalName;
    }
    return null;
  }

  void _syncSingleIngredientDraftFromFields() {
    final UserSupplementIngredientInput? corrected = _correctedIngredient();
    if (corrected == null) {
      _ingredientDrafts = const <_IngredientReviewDraft>[];
      return;
    }
    _ingredientDrafts = <_IngredientReviewDraft>[
      _IngredientReviewDraft.fromInput(corrected),
    ];
  }

  void _syncPrimaryIngredientControllers() {
    _IngredientReviewDraft? firstSelected;
    for (final _IngredientReviewDraft draft in _ingredientDrafts) {
      if (draft.selected && draft.isValid) {
        firstSelected = draft;
        break;
      }
    }
    _ingredientNameController.text = firstSelected?.displayName ?? '';
    _ingredientAmountController.text = firstSelected?.amountText ?? '';
    _ingredientUnitController.text = firstSelected?.unit ?? '';
  }

  List<_IngredientReviewDraft> _seedIngredientDrafts(
    List<SupplementIngredientCandidate> candidates,
  ) {
    return candidates
        .map(_IngredientReviewDraft.fromCandidate)
        .toList(growable: false);
  }

  static String _formatEditableAmount(double value) {
    return value == value.roundToDouble()
        ? value.toStringAsFixed(0)
        : value.toString();
  }

  static String _formatOptionalAmount(double? value) {
    if (value == null) return '';
    return _formatEditableAmount(value);
  }

  static double? _parseOptionalDouble(String value) {
    final String trimmed = value.trim();
    if (trimmed.isEmpty) return null;
    return double.tryParse(trimmed);
  }

  static List<String> _splitCsv(String value) {
    return value
        .split(',')
        .map((String part) => part.trim())
        .where((String part) => part.isNotEmpty)
        .toList(growable: false);
  }

  static String? _nonEmpty(String? value) {
    final String? trimmed = value?.trim();
    if (trimmed == null || trimmed.isEmpty) return null;
    return trimmed;
  }
}

class _SupplementReviewGroup {
  const _SupplementReviewGroup({
    required this.label,
    required this.preview,
    required this.sourcePreviews,
  });

  final String label;
  final SupplementAnalysisPreview preview;
  final List<SupplementAnalysisPreview> sourcePreviews;
}

class _MutableSupplementReviewGroup {
  _MutableSupplementReviewGroup({
    required this.identityKey,
    required this.previews,
  });

  final String? identityKey;
  final List<SupplementAnalysisPreview> previews;
}

class _IngredientReviewDraft {
  const _IngredientReviewDraft({
    required this.displayName,
    required this.originalName,
    required this.amountText,
    required this.unit,
    required this.selected,
    required this.nutrientCode,
    required this.confidence,
    required this.source,
    required this.dailyValuePercent,
  });

  factory _IngredientReviewDraft.fromCandidate(
    SupplementIngredientCandidate candidate,
  ) {
    final String amountText = candidate.amount == null
        ? ''
        : _AnalysisResultScreenState._formatEditableAmount(candidate.amount!);
    final bool hasAmountAndUnit =
        candidate.amount != null &&
        _AnalysisResultScreenState._nonEmpty(candidate.unit) != null;
    return _IngredientReviewDraft(
      displayName: candidate.displayName,
      originalName: candidate.originalName,
      amountText: amountText,
      unit: candidate.unit ?? '',
      selected: hasAmountAndUnit,
      nutrientCode: candidate.nutrientCode,
      confidence: candidate.confidence,
      source: candidate.source,
      dailyValuePercent: candidate.dailyValuePercent,
    );
  }

  factory _IngredientReviewDraft.fromInput(
    UserSupplementIngredientInput input,
  ) {
    return _IngredientReviewDraft(
      displayName: input.displayName,
      originalName: input.originalName,
      amountText: input.amount == null
          ? ''
          : _AnalysisResultScreenState._formatEditableAmount(input.amount!),
      unit: input.unit ?? '',
      selected: true,
      nutrientCode: input.nutrientCode,
      confidence: input.confidence,
      source: input.source,
      dailyValuePercent: input.dailyValuePercent,
    );
  }

  final String displayName;
  final String? originalName;
  final String amountText;
  final String unit;
  final bool selected;
  final String? nutrientCode;
  final double confidence;
  final String source;
  final double? dailyValuePercent;

  bool get isValid {
    return _AnalysisResultScreenState._nonEmpty(displayName) != null;
  }

  UserSupplementIngredientInput toInput({required String source}) {
    return UserSupplementIngredientInput(
      displayName: displayName.trim(),
      originalName: _AnalysisResultScreenState._nonEmpty(originalName),
      nutrientCode: nutrientCode,
      amount: _AnalysisResultScreenState._parseOptionalDouble(amountText),
      unit: _AnalysisResultScreenState._nonEmpty(unit),
      confidence: selected ? 1 : confidence,
      source: selected ? 'user_confirmed' : source,
      dailyValuePercent: dailyValuePercent,
    );
  }

  _IngredientReviewDraft copyWith({
    String? displayName,
    String? amountText,
    String? unit,
    bool? selected,
  }) {
    return _IngredientReviewDraft(
      displayName: displayName ?? this.displayName,
      originalName: originalName,
      amountText: amountText ?? this.amountText,
      unit: unit ?? this.unit,
      selected: selected ?? this.selected,
      nutrientCode: nutrientCode,
      confidence: confidence,
      source: source,
      dailyValuePercent: dailyValuePercent,
    );
  }
}

class _OriginalIngredientNameText extends StatelessWidget {
  const _OriginalIngredientNameText({required this.originalName});

  final String originalName;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Text(
        '원문: $originalName',
        style: const TextStyle(
          color: AppColor.inkSecondary,
          fontSize: 12,
          height: 1.35,
          fontWeight: FontWeight.w700,
          letterSpacing: 0,
        ),
      ),
    );
  }
}

class _IngredientReviewTile extends StatelessWidget {
  const _IngredientReviewTile({required this.draft, required this.onChanged});

  final _IngredientReviewDraft draft;
  final ValueChanged<_IngredientReviewDraft> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpace.sm),
      decoration: BoxDecoration(
        color: AppColor.section,
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(
          color: draft.selected ? AppColor.brand : const Color(0xFFE4E7E2),
        ),
      ),
      child: Column(
        children: <Widget>[
          CheckboxListTile(
            value: draft.selected,
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            title: Text(
              draft.displayName.isEmpty ? '성분명 없음' : draft.displayName,
              style: const TextStyle(
                color: AppColor.ink,
                fontSize: 14,
                fontWeight: FontWeight.w900,
                letterSpacing: 0,
              ),
            ),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                if (_AnalysisResultScreenState._visibleOriginalName(
                      draft.displayName,
                      draft.originalName,
                    ) !=
                    null)
                  Text(
                    '원문: ${draft.originalName}',
                    style: const TextStyle(
                      color: AppColor.inkSecondary,
                      fontSize: 12,
                      height: 1.3,
                      letterSpacing: 0,
                    ),
                  ),
                Text(
                  draft.amountText.isEmpty && draft.unit.isEmpty
                      ? '함량이 없어 기본 제외됨'
                      : '${draft.amountText} ${draft.unit}'.trim(),
                  style: const TextStyle(
                    color: AppColor.inkSecondary,
                    fontSize: 12,
                    height: 1.3,
                    letterSpacing: 0,
                  ),
                ),
              ],
            ),
            onChanged: (bool? value) {
              onChanged(draft.copyWith(selected: value ?? false));
            },
          ),
          TextFormField(
            initialValue: draft.displayName,
            decoration: const InputDecoration(
              labelText: '성분명',
              isDense: true,
              filled: true,
            ),
            onChanged: (String value) {
              onChanged(draft.copyWith(displayName: value));
            },
          ),
          const SizedBox(height: AppSpace.xs),
          Row(
            children: <Widget>[
              Expanded(
                child: TextFormField(
                  initialValue: draft.amountText,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(
                    labelText: '함량',
                    isDense: true,
                    filled: true,
                  ),
                  onChanged: (String value) {
                    onChanged(draft.copyWith(amountText: value));
                  },
                ),
              ),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: TextFormField(
                  initialValue: draft.unit,
                  decoration: const InputDecoration(
                    labelText: '단위',
                    isDense: true,
                    filled: true,
                  ),
                  onChanged: (String value) {
                    onChanged(draft.copyWith(unit: value));
                  },
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _IngredientAmountRowData {
  const _IngredientAmountRowData({
    required this.name,
    required this.amount,
    this.originalName,
    this.draftIndex,
    this.selected = false,
    this.candidate,
  });

  final String name;
  final String amount;
  final String? originalName;
  final int? draftIndex;
  final bool selected;

  /// 성분 상세 진입에 넘길 성분 행(없으면 행 탭 비활성).
  final SupplementIngredientCandidate? candidate;
}

/// 섭취 기준 스테퍼 버튼 — 시각 아이콘 28 유지하되 히트 영역 52px 확보
/// (시니어 최소 터치 타깃, 가이드 10 ③-P2 7).
class _StepperButton extends StatelessWidget {
  const _StepperButton({required this.icon, required this.onPressed});

  final IconData icon;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return IconButton(
      onPressed: onPressed,
      icon: Icon(icon),
      iconSize: 28,
      color: AppColor.brandDeep,
      disabledColor: AppColor.inkTertiary,
      constraints: const BoxConstraints(minWidth: 52, minHeight: 52),
      visualDensity: VisualDensity.standard,
    );
  }
}

/// 섭취 기준 선택 칩 — ChoiceChip/FilterChip 의 M3 기본색 대신
/// design_tokens_v2(brand/brandSoft) 를 쓰고 히트 영역 52px 를 확보한다
/// (가이드 10 ③-P2 7, 저장소 칩 컨벤션 정합).
class _IntakeChoiceChip extends StatelessWidget {
  const _IntakeChoiceChip({
    required this.label,
    required this.selected,
    required this.onSelected,
  });

  final String label;
  final bool selected;
  final VoidCallback onSelected;

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onTap: onSelected,
      child: Container(
        constraints: const BoxConstraints(minHeight: 52),
        alignment: Alignment.center,
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpace.md,
          vertical: AppSpace.sm,
        ),
        decoration: BoxDecoration(
          color: selected ? AppColor.brandSoft : AppColor.surface,
          borderRadius: BorderRadius.circular(AppRadius.full),
          border: Border.all(
            color: selected ? AppColor.brand : AppColor.border,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: selected ? AppColor.brandDeep : AppColor.inkSecondary,
            fontSize: 15,
            fontWeight: selected ? FontWeight.w800 : FontWeight.w600,
            letterSpacing: 0,
          ),
        ),
      ),
    );
  }
}

class _IngredientAmountTable extends StatelessWidget {
  const _IngredientAmountTable({
    required this.rows,
    required this.onSelectionChanged,
    required this.onAllSelectionChanged,
    this.onRowTap,
    this.onAddIngredient,
  });

  final List<_IngredientAmountRowData> rows;
  final void Function(int index, bool selected) onSelectionChanged;
  final ValueChanged<bool> onAllSelectionChanged;

  /// 성분 행(성분명/함량 셀) 탭 시 성분 상세 진입(가이드 ④-5). null 이면 비활성.
  final void Function(SupplementIngredientCandidate candidate)? onRowTap;

  /// 표 하단 '성분 직접 추가' 행 탭(가이드 10 ③-P2 7). null 이면 미노출.
  final VoidCallback? onAddIngredient;

  @override
  Widget build(BuildContext context) {
    final List<_IngredientAmountRowData> selectableRows = rows
        .where((_IngredientAmountRowData row) => row.draftIndex != null)
        .toList(growable: false);
    final int selectedCount = selectableRows
        .where((_IngredientAmountRowData row) => row.selected)
        .length;
    final int selectableCount = selectableRows.length;
    final bool allSelected =
        selectableCount > 0 && selectedCount == selectableCount;
    return ClipRRect(
      borderRadius: BorderRadius.circular(AppRadius.md),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: AppColor.surface,
          border: Border.all(color: AppColor.border),
          borderRadius: BorderRadius.circular(AppRadius.md),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            _IngredientBulkSelectionBar(
              selectedCount: selectedCount,
              selectableCount: selectableCount,
              onPressed: selectableCount == 0
                  ? null
                  : () => onAllSelectionChanged(!allSelected),
            ),
            const Divider(height: 1, thickness: 1, color: AppColor.border),
            Table(
              defaultVerticalAlignment: TableCellVerticalAlignment.middle,
              columnWidths: const <int, TableColumnWidth>{
                0: FixedColumnWidth(42),
                1: FlexColumnWidth(1.35),
                2: FlexColumnWidth(1),
              },
              border: const TableBorder(
                horizontalInside: BorderSide(color: AppColor.border),
              ),
              children: <TableRow>[
                TableRow(
                  decoration: BoxDecoration(color: AppColor.brandSoft),
                  children: const <Widget>[
                    _IngredientAmountCell(text: '선택', isHeader: true),
                    _IngredientAmountCell(text: '성분명', isHeader: true),
                    _IngredientAmountCell(text: '함량', isHeader: true),
                  ],
                ),
                for (final MapEntry<int, _IngredientAmountRowData> entry
                    in rows.asMap().entries)
                  TableRow(
                    children: <Widget>[
                      _IngredientSelectionCell(
                        row: entry.value,
                        rowIndex: entry.key,
                        onSelectionChanged: onSelectionChanged,
                      ),
                      _IngredientRowTapTarget(
                        rowIndex: entry.key,
                        candidate: onRowTap == null
                            ? null
                            : entry.value.candidate,
                        onRowTap: onRowTap,
                        child: _IngredientAmountCell(
                          text: entry.value.name,
                          secondaryText: entry.value.originalName == null
                              ? null
                              : '원문: ${entry.value.originalName}',
                        ),
                      ),
                      _IngredientRowTapTarget(
                        rowIndex: entry.key,
                        candidate: onRowTap == null
                            ? null
                            : entry.value.candidate,
                        onRowTap: onRowTap,
                        child: _IngredientAmountCell(
                          text: entry.value.amount,
                          pill: true,
                        ),
                      ),
                    ],
                  ),
              ],
            ),
            if (onAddIngredient != null) ...<Widget>[
              const Divider(height: 1, thickness: 1, color: AppColor.border),
              // 시니어 최소 터치 높이 52 확보.
              TextButton.icon(
                onPressed: onAddIngredient,
                style: TextButton.styleFrom(
                  minimumSize: const Size.fromHeight(52),
                ),
                icon: Icon(
                  Icons.add_rounded,
                  size: 20,
                  color: AppColor.brandDeep,
                ),
                label: Text(
                  '성분 직접 추가',
                  style: TextStyle(
                    color: AppColor.brandDeep,
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _IngredientBulkSelectionBar extends StatelessWidget {
  const _IngredientBulkSelectionBar({
    required this.selectedCount,
    required this.selectableCount,
    required this.onPressed,
  });

  final int selectedCount;
  final int selectableCount;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final bool allSelected =
        selectableCount > 0 && selectedCount == selectableCount;
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        AppSpace.sm,
        AppSpace.xs,
        AppSpace.xs,
        AppSpace.xs,
      ),
      child: Row(
        children: <Widget>[
          Expanded(
            child: Text(
              '선택 $selectedCount/$selectableCount',
              style: const TextStyle(
                color: AppColor.inkSecondary,
                fontSize: 12,
                fontWeight: FontWeight.w800,
                height: 1.25,
                letterSpacing: 0,
              ),
            ),
          ),
          TextButton.icon(
            key: const ValueKey<String>('ingredient-select-all-button'),
            onPressed: onPressed,
            style: TextButton.styleFrom(
              foregroundColor: AppColor.ink,
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpace.xs,
                vertical: 2,
              ),
              minimumSize: const Size(0, 32),
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            icon: Icon(
              allSelected ? Icons.remove_done_rounded : Icons.done_all_rounded,
              size: 17,
            ),
            label: Text(
              allSelected ? '전체 해제' : '전체 선택',
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w900,
                letterSpacing: 0,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _IngredientSelectionCell extends StatelessWidget {
  const _IngredientSelectionCell({
    required this.row,
    required this.rowIndex,
    required this.onSelectionChanged,
  });

  final _IngredientAmountRowData row;
  final int rowIndex;
  final void Function(int index, bool selected) onSelectionChanged;

  @override
  Widget build(BuildContext context) {
    final int? draftIndex = row.draftIndex;
    return Center(
      child: Checkbox(
        key: ValueKey<String>('ingredient-row-checkbox-$rowIndex'),
        value: row.selected,
        visualDensity: VisualDensity.compact,
        onChanged: draftIndex == null
            ? null
            : (bool? selected) {
                onSelectionChanged(draftIndex, selected ?? false);
              },
      ),
    );
  }
}

/// 성분 행 셀을 감싸 성분 상세 진입 탭을 받는다(레이아웃 변경 없음, 가이드 ④-5).
///
/// 후보가 없는 행(성분명 미확인)이나 onRowTap 미지정 시 셀을 그대로 통과시킨다.
class _IngredientRowTapTarget extends StatelessWidget {
  const _IngredientRowTapTarget({
    required this.rowIndex,
    required this.candidate,
    required this.onRowTap,
    required this.child,
  });

  final int rowIndex;
  final SupplementIngredientCandidate? candidate;
  final void Function(SupplementIngredientCandidate candidate)? onRowTap;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final SupplementIngredientCandidate? rowCandidate = candidate;
    final void Function(SupplementIngredientCandidate)? handler = onRowTap;
    if (rowCandidate == null || handler == null) {
      return child;
    }
    return GestureDetector(
      key: ValueKey<String>('ingredient-row-detail-$rowIndex'),
      behavior: HitTestBehavior.opaque,
      onTap: () => handler(rowCandidate),
      child: child,
    );
  }
}

class _OcrTextRowData {
  const _OcrTextRowData({
    required this.section,
    required this.source,
    required this.text,
    required this.confidence,
  });

  final String section;
  final String source;
  final String text;
  final String confidence;
}

class _OcrTextTable extends StatelessWidget {
  const _OcrTextTable({required this.rows});

  final List<_OcrTextRowData> rows;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(AppRadius.md),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: Colors.white,
          border: Border.all(color: const Color(0xFFE7EAF0)),
          borderRadius: BorderRadius.circular(AppRadius.md),
        ),
        child: Table(
          defaultVerticalAlignment: TableCellVerticalAlignment.middle,
          columnWidths: const <int, TableColumnWidth>{
            0: FixedColumnWidth(76),
            1: FixedColumnWidth(70),
            2: FlexColumnWidth(1),
            3: FixedColumnWidth(58),
          },
          border: const TableBorder(
            horizontalInside: BorderSide(color: Color(0xFFE7EAF0)),
          ),
          children: <TableRow>[
            const TableRow(
              decoration: BoxDecoration(color: Color(0xFFFFF7D6)),
              children: <Widget>[
                _IngredientAmountCell(text: '구역', isHeader: true),
                _IngredientAmountCell(text: '출처', isHeader: true),
                _IngredientAmountCell(text: '텍스트', isHeader: true),
                _IngredientAmountCell(text: '신뢰도', isHeader: true),
              ],
            ),
            for (final _OcrTextRowData row in rows)
              TableRow(
                children: <Widget>[
                  _IngredientAmountCell(text: row.section),
                  _IngredientAmountCell(text: row.source),
                  _IngredientAmountCell(text: row.text),
                  _IngredientAmountCell(text: row.confidence),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

class _IngredientAmountCell extends StatelessWidget {
  const _IngredientAmountCell({
    required this.text,
    this.secondaryText,
    this.isHeader = false,
    this.pill = false,
  });

  final String text;
  final String? secondaryText;
  final bool isHeader;
  // 함량 값을 옅은 회색 알약으로 표시 (figma 07 · 정보 확인·수정).
  final bool pill;

  @override
  Widget build(BuildContext context) {
    // figma 07 — 함량 값은 옅은 회색 알약(우측 정렬). 값이 없으면 알약 숨김.
    if (pill && !isHeader) {
      if (text.trim().isEmpty) return const SizedBox.shrink();
      return Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpace.sm,
          vertical: AppSpace.xs,
        ),
        child: Align(
          alignment: Alignment.centerRight,
          child: Container(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpace.md,
              vertical: 5,
            ),
            decoration: BoxDecoration(
              color: AppColor.sunken,
              borderRadius: BorderRadius.circular(AppRadius.full),
            ),
            child: Text(
              text,
              // 함량 칸이 좁아도 알약 텍스트는 한 줄 유지 (줄바꿈 방지).
              maxLines: 1,
              softWrap: false,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppColor.ink,
                fontSize: 14,
                fontWeight: FontWeight.w800,
                letterSpacing: 0,
              ),
            ),
          ),
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpace.sm,
        vertical: AppSpace.xs,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            text,
            softWrap: true,
            style: TextStyle(
              color: isHeader ? AppColor.inkSecondary : AppColor.ink,
              fontSize: isHeader ? 12 : 16,
              height: 1.35,
              fontWeight: FontWeight.w900,
              letterSpacing: 0,
            ),
          ),
          if (secondaryText != null && secondaryText!.isNotEmpty)
            Text(
              secondaryText!,
              softWrap: true,
              style: const TextStyle(
                color: AppColor.inkSecondary,
                fontSize: 11,
                height: 1.3,
                fontWeight: FontWeight.w700,
                letterSpacing: 0,
              ),
            ),
        ],
      ),
    );
  }
}

/// 분석 중 3단계 체크리스트 한 단계.
class _AnalysisStep {
  const _AnalysisStep({required this.label});

  /// 단계 라벨 (해요체 X — 짧은 명사구).
  final String label;
}

// 음식: 검출→분류→후보 정리 / 영양제: 검출→OCR 추출→AI 해석 (가이드 ④-2).
const List<_AnalysisStep> _kMealSteps = <_AnalysisStep>[
  _AnalysisStep(label: '음식 영역 검출'),
  _AnalysisStep(label: '음식 종류 분류'),
  _AnalysisStep(label: '후보 정리'),
];
const List<_AnalysisStep> _kSupplementSteps = <_AnalysisStep>[
  _AnalysisStep(label: '라벨 영역 검출'),
  _AnalysisStep(label: 'OCR 글자 추출'),
  _AnalysisStep(label: 'AI 해석'),
];

class _AnalysisInProgressScreen extends StatefulWidget {
  const _AnalysisInProgressScreen({required this.isMeal});

  final bool isMeal;

  @override
  State<_AnalysisInProgressScreen> createState() =>
      _AnalysisInProgressScreenState();
}

class _AnalysisInProgressScreenState extends State<_AnalysisInProgressScreen> {
  // ⚠️ 백엔드는 동기 202 단일 응답이고 진행률 스트림/폴링 라우트가 없다.
  //    (가이드 ③-2 공백) → 단계 전환은 순수 시간 기반 연출이며, 실제 단계
  //    완료 신호가 아니다. 완료 후 결과 화면에서 pipeline_metadata 로 실제
  //    수행 여부를 검증 표기한다(가이드 ④-2).
  static const Duration _stepInterval = Duration(milliseconds: 1100);

  int _activeStep = 0;
  Timer? _timer;

  List<_AnalysisStep> get _steps =>
      widget.isMeal ? _kMealSteps : _kSupplementSteps;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(_stepInterval, (Timer timer) {
      if (!mounted) return;
      // 마지막 단계 직전까지만 전진(완료 신호는 화면 전환이 담당).
      if (_activeStep >= _steps.length - 1) {
        timer.cancel();
        return;
      }
      setState(() => _activeStep += 1);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColor.section,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: <Widget>[
            _ResultTopBar(isMeal: widget.isMeal),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpace.page,
                  AppSpace.xl,
                  AppSpace.page,
                  AppSpace.xl,
                ),
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 420),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        Container(
                          width: 140,
                          height: 140,
                          padding: const EdgeInsets.all(AppSpace.md),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(AppRadius.xl),
                            boxShadow: AppShadow.elev1,
                          ),
                          child: Image.asset(
                            MascotFor.analyzing.asset,
                            fit: BoxFit.contain,
                          ),
                        ),
                        const SizedBox(height: AppSpace.lg),
                        const Text(
                          '분석을 하고 있어요.',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            color: AppColor.ink,
                            fontSize: 24,
                            fontWeight: FontWeight.w900,
                            height: 1.18,
                            letterSpacing: 0,
                          ),
                        ),
                        const SizedBox(height: AppSpace.lg),
                        _AnalysisChecklist(
                          steps: _steps,
                          activeStep: _activeStep,
                        ),
                        const SizedBox(height: AppSpace.lg),
                        Text(
                          widget.isMeal
                              ? '식단 후보를 확인하는 동안 다른 탭을 사용해도 괜찮아요.'
                              : '라벨을 함께 확인하는 동안 다른 탭을 사용해도 괜찮아요.',
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: AppColor.inkSecondary,
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            height: 1.45,
                            letterSpacing: 0,
                          ),
                        ),
                        const SizedBox(height: AppSpace.lg),
                        SizedBox(
                          width: double.infinity,
                          child: FilledButton.icon(
                            onPressed: () => context.go('/shell/home'),
                            icon: const Icon(Icons.home_rounded),
                            label: const Text('메인으로 이동'),
                            style: FilledButton.styleFrom(
                              backgroundColor: AppColor.brand,
                              foregroundColor: AppColor.ink,
                              textStyle: const TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w900,
                                letterSpacing: 0,
                              ),
                              padding: const EdgeInsets.symmetric(vertical: 14),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(
                                  AppRadius.full,
                                ),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
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

class _AnalysisChecklist extends StatelessWidget {
  const _AnalysisChecklist({required this.steps, required this.activeStep});

  final List<_AnalysisStep> steps;
  final int activeStep;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: <Widget>[
        for (int index = 0; index < steps.length; index++) ...<Widget>[
          _AnalysisChecklistRow(
            label: steps[index].label,
            done: index < activeStep,
            active: index == activeStep,
          ),
          if (index != steps.length - 1) const SizedBox(height: AppSpace.sm),
        ],
      ],
    );
  }
}

class _AnalysisChecklistRow extends StatelessWidget {
  const _AnalysisChecklistRow({
    required this.label,
    required this.done,
    required this.active,
  });

  final String label;
  final bool done;
  final bool active;

  @override
  Widget build(BuildContext context) {
    final Color leadingColor = done
        ? AppColor.success
        : active
        ? AppColor.brand
        : AppColor.inkDisabled;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpace.md,
        vertical: AppSpace.md,
      ),
      decoration: BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(
          color: active ? AppColor.brand : AppColor.border,
          width: active ? 1.5 : 1,
        ),
      ),
      child: Row(
        children: <Widget>[
          SizedBox(
            width: 22,
            height: 22,
            child: done
                ? const Icon(
                    Icons.check_circle_rounded,
                    size: 22,
                    color: AppColor.success,
                  )
                : active
                ? SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2.4,
                      valueColor: AlwaysStoppedAnimation<Color>(AppColor.brand),
                    ),
                  )
                : Icon(
                    Icons.radio_button_unchecked_rounded,
                    size: 20,
                    color: leadingColor,
                  ),
          ),
          const SizedBox(width: AppSpace.md),
          Expanded(
            child: Text(
              label,
              style: TextStyle(
                fontFamily: 'Pretendard',
                fontSize: 15,
                fontWeight: active || done ? FontWeight.w800 : FontWeight.w600,
                color: done || active ? AppColor.ink : AppColor.inkTertiary,
                letterSpacing: 0,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ResultTopBar extends StatelessWidget {
  const _ResultTopBar({required this.isMeal});

  final bool isMeal;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColor.section,
      padding: const EdgeInsets.fromLTRB(
        AppSpace.page,
        AppSpace.sm,
        AppSpace.page,
        AppSpace.sm,
      ),
      child: Row(
        children: <Widget>[
          GestureDetector(
            onTap: () =>
                context.canPop() ? context.pop() : context.go('/shell/home'),
            child: const SizedBox(
              width: 40,
              height: 40,
              child: Icon(Icons.close_rounded, color: AppColor.ink, size: 24),
            ),
          ),
          const Spacer(),
          Text(
            isMeal ? '식단 분석' : '영양제 분석',
            style: const TextStyle(
              color: AppColor.ink,
              fontSize: 16,
              fontWeight: FontWeight.w800,
              letterSpacing: 0,
            ),
          ),
          const Spacer(),
          const SizedBox(width: 40, height: 40),
        ],
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({
    required this.isMeal,
    required this.preview,
    required this.mealPreview,
    required this.registered,
    required this.registeredMeal,
    required this.busy,
    required this.onTap,
  });

  final bool isMeal;
  final SupplementAnalysisPreview? preview;
  final MealImageAnalysisPreview? mealPreview;
  final UserSupplementResponse? registered;
  final MealRecordResponse? registeredMeal;
  final bool busy;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final Widget card = Container(
      key: const ValueKey<String>('supplement-candidate-summary'),
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(
        AppSpace.cardInside,
        AppSpace.lg,
        AppSpace.cardInside,
        AppSpace.lg,
      ),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: <Color>[const Color(0xFFFFE07A), AppColor.brand],
        ),
        borderRadius: BorderRadius.circular(AppRadius.lg),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: AppColor.brand.withValues(alpha: 0.32),
            blurRadius: 18,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Row(
        children: <Widget>[
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.42),
              shape: BoxShape.circle,
            ),
            alignment: Alignment.center,
            child: Icon(
              isMeal ? Icons.restaurant_rounded : Icons.medication_rounded,
              color: AppColor.ink,
              size: 28,
            ),
          ),
          const SizedBox(width: AppSpace.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  busy ? '분석 중이에요' : '분석이 끝났어요',
                  style: TextStyle(
                    color: AppColor.ink.withValues(alpha: 0.65),
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  _headline(),
                  style: const TextStyle(
                    color: AppColor.ink,
                    fontSize: 19,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0,
                    height: 1.3,
                  ),
                ),
              ],
            ),
          ),
          // 탭 가능 단서 — 영양제 미리보기(onTap 존재)에서만 노출.
          // 식단 모드(onTap == null)에서는 행에 추가하지 않는다.
          if (onTap != null) ...<Widget>[
            const SizedBox(width: AppSpace.sm),
            _ocrHint(),
          ],
        ],
      ),
    );
    if (onTap == null) return card;
    return GestureDetector(onTap: onTap, child: card);
  }

  /// 카드 우측의 작은 시각 단서.
  ///
  /// 카드를 탭하면 인식한 라벨 글자 전체를 볼 수 있다는 점을 시니어도
  /// 알아보게 안내해요. 영양제 미리보기에서만 쓰이며, 탭 영역은 카드 전체라
  /// 터치 타깃은 48px 이상으로 유지돼요.
  Widget _ocrHint() {
    return Container(
      key: const ValueKey<String>('summary-card-ocr-hint'),
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpace.sm,
        vertical: AppSpace.xs,
      ),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.42),
        borderRadius: BorderRadius.circular(AppRadius.full),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          const Icon(Icons.unfold_more_rounded, color: AppColor.ink, size: 18),
          const SizedBox(width: 4),
          Text(
            '텍스트 보기',
            style: AppText.caption.copyWith(
              color: AppColor.ink,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  String _headline() {
    if (isMeal) {
      if (registeredMeal != null) {
        return '${registeredMeal!.foodItems.length}개 음식이 저장됐어요';
      }
      final MealImageAnalysisPreview? preview = mealPreview;
      if (preview == null) return '식단 사진을 분석해주세요';
      final int count = preview.foodCandidates.length;
      if (count > 0) return '음식 후보 $count개를 찾았어요';
      if (preview.pipelineMetadata.requiresManualEntry) {
        return '음식 후보를 직접 확인해주세요';
      }
      return '식단 분석이 끝났어요';
    }
    if (registered != null) return '${registered!.displayName} 저장이 끝났어요';
    final List<SupplementIngredientCandidate> candidates =
        preview?.ingredientCandidates ??
        const <SupplementIngredientCandidate>[];
    final int selectedByDefault = candidates
        .where(
          (SupplementIngredientCandidate candidate) =>
              candidate.amount != null &&
              candidate.unit?.trim().isNotEmpty == true,
        )
        .length;
    if (selectedByDefault > 0 && selectedByDefault < candidates.length) {
      return '저장 후보 $selectedByDefault개 · 검토 후보 ${candidates.length}개';
    }
    if (selectedByDefault > 0) return '성분 후보 $selectedByDefault개를 찾았어요';
    final int count = candidates.length;
    if (count > 0) return '검토가 필요한 성분 후보 $count개';
    if (preview != null) return '성분 후보가 비어 있어 다시 확인이 필요해요';
    return '카메라로 영양제 라벨을 촬영해주세요';
  }
}

class _SupplementPreviewTabs extends StatelessWidget {
  const _SupplementPreviewTabs({
    required this.groups,
    required this.selectedIndex,
    required this.onSelected,
  });

  final List<_SupplementReviewGroup> groups;
  final int selectedIndex;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: <Widget>[
          for (int index = 0; index < groups.length; index++) ...<Widget>[
            ChoiceChip(
              key: ValueKey<String>('supplement-preview-tab-$index'),
              selected: selectedIndex == index,
              label: Text(groups[index].label),
              selectedColor: AppColor.brand,
              labelStyle: TextStyle(
                color: selectedIndex == index
                    ? AppColor.ink
                    : AppColor.inkSecondary,
                fontWeight: FontWeight.w900,
                letterSpacing: 0,
              ),
              onSelected: (_) => onSelected(index),
            ),
            if (index < groups.length - 1) const SizedBox(width: AppSpace.xs),
          ],
        ],
      ),
    );
  }
}

class _ResultCard extends StatelessWidget {
  const _ResultCard({
    required this.color,
    required this.icon,
    required this.label,
    required this.value,
    required this.desc,
    this.big = false,
  });

  final Color color;
  final IconData icon;
  final String label;
  final String value;
  final String desc;
  final bool big;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpace.cardInside),
      decoration: BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        boxShadow: AppShadow.elev1,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, color: color, size: 24),
          ),
          const SizedBox(width: AppSpace.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  label,
                  style: TextStyle(
                    color: AppColor.inkSecondary,
                    fontSize: big ? 15 : 13,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  value,
                  style: TextStyle(
                    color: AppColor.ink,
                    fontSize: big ? 24 : 18,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0,
                    height: 1.2,
                  ),
                ),
                const SizedBox(height: 7),
                Text(
                  desc,
                  style: const TextStyle(
                    color: AppColor.inkSecondary,
                    fontSize: 13,
                    height: 1.38,
                    letterSpacing: 0,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// 직접 입력(음식 검색) 폴백 카드 — 카탈로그에서 음식을 찾아 담는다.
///
/// 카메라 분석 폴백(후보 0건·저신뢰·수동입력)에서 음식을 직접 검색해 끼니에
/// 합류시키는 진입점. 담은 항목은 confirm payload food_items[] 로 들어간다.
class _DatabaseMatchFallbackCard extends StatelessWidget {
  const _DatabaseMatchFallbackCard({
    required this.pickedFoods,
    required this.onOpenSearch,
    required this.onRemove,
  });

  final List<MealFoodItemInput> pickedFoods;
  final VoidCallback onOpenSearch;
  final ValueChanged<MealFoodItemInput> onRemove;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside),
      decoration: BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        border: Border.all(color: AppColor.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(Icons.search_rounded, size: 20, color: AppColor.brandDeep),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: Text(
                  '음식을 직접 검색해 담기',
                  style: AppText.body.copyWith(fontWeight: FontWeight.w800),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            '사진으로 알아보기 어려우면 음식 이름을 검색해 담아 보세요.',
            style: AppText.caption.copyWith(color: AppColor.inkTertiary),
          ),
          if (pickedFoods.isNotEmpty) ...<Widget>[
            const SizedBox(height: AppSpace.md),
            Wrap(
              spacing: AppSpace.sm,
              runSpacing: AppSpace.sm,
              children: <Widget>[
                for (final MealFoodItemInput item in pickedFoods)
                  _FallbackPickedChip(
                    label: item.displayName,
                    onRemove: () => onRemove(item),
                  ),
              ],
            ),
          ],
          const SizedBox(height: AppSpace.md),
          SizedBox(
            width: double.infinity,
            child: AppSecondaryButton(
              label: pickedFoods.isEmpty ? '직접 입력으로 찾기' : '더 담기',
              leading: const Icon(
                Icons.add_rounded,
                size: 18,
                color: AppColor.ink,
              ),
              onPressed: onOpenSearch,
            ),
          ),
        ],
      ),
    );
  }
}

class _FallbackPickedChip extends StatelessWidget {
  const _FallbackPickedChip({required this.label, required this.onRemove});

  final String label;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 7, 6, 7),
      decoration: BoxDecoration(
        color: AppColor.brandSoft,
        borderRadius: BorderRadius.circular(AppRadius.full),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Text(
            label,
            style: AppText.caption.copyWith(
              color: AppColor.brandDeep,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(width: 4),
          GestureDetector(
            onTap: onRemove,
            child: Icon(
              Icons.close_rounded,
              size: 16,
              color: AppColor.brandDeep,
            ),
          ),
        ],
      ),
    );
  }
}

/// 인라인 섭취량 토글(figma 06 심화) — 프리셋 칩으로 바텀시트 없이 섭취량 조절.
///
/// 상세 조절(그램 환산)은 음식 후보 카드의 '섭취량' 행(바텀시트)이 담당하고,
/// 여기선 ½/1/1.5/2 인분 빠른 선택만 제공한다. D2: 숫자(%) 노출 없음.
class _PortionSegment extends StatelessWidget {
  const _PortionSegment({
    required this.selectedAmount,
    required this.onSelected,
  });

  final double selectedAmount;
  final ValueChanged<double> onSelected;

  @override
  Widget build(BuildContext context) {
    return Row(
      key: const ValueKey<String>('portion-segment'),
      children: <Widget>[
        for (final double preset in kPortionPresets) ...<Widget>[
          Expanded(
            child: _PortionSegmentChip(
              number: _segmentNumber(preset),
              selected: selectedAmount == preset,
              onTap: () => onSelected(preset),
            ),
          ),
          if (preset != kPortionPresets.last)
            const SizedBox(width: AppSpace.sm),
        ],
      ],
    );
  }

  /// 세그먼트 칩의 인분 숫자만 ('½', '1', '1.5', '2'). 단위 '인분'은 칩 안의
  /// 별도 Text 로 붙여, 상세 시트의 'N인분' 한 덩어리 라벨 탭 단언과 글자 매칭이
  /// 겹치지 않게 한다(같은 의미·다른 위젯 구성).
  static String _segmentNumber(double preset) {
    if (preset == 0.5) return '½';
    return preset == preset.roundToDouble()
        ? preset.toStringAsFixed(0)
        : preset
              .toStringAsFixed(2)
              .replaceFirst(RegExp(r'0+$'), '')
              .replaceFirst(RegExp(r'\.$'), '');
  }
}

class _PortionSegmentChip extends StatelessWidget {
  const _PortionSegmentChip({
    required this.number,
    required this.selected,
    required this.onTap,
  });

  final String number;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final Color fg = selected ? AppColor.brandDeep : AppColor.inkSecondary;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        // 시니어 최소 터치 타깃 48px 확보.
        constraints: const BoxConstraints(minHeight: 48),
        padding: const EdgeInsets.symmetric(vertical: AppSpace.md),
        decoration: BoxDecoration(
          color: selected ? AppColor.brandSoft : AppColor.sunken,
          borderRadius: BorderRadius.circular(AppRadius.full),
          border: Border.all(
            color: selected ? AppColor.brand : AppColor.border,
            width: selected ? 1.5 : 1,
          ),
        ),
        alignment: Alignment.center,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: <Widget>[
            Text(
              number,
              style: TextStyle(
                fontFamily: 'Pretendard',
                fontSize: 15,
                fontWeight: FontWeight.w800,
                color: fg,
                letterSpacing: 0,
              ),
            ),
            const SizedBox(width: 2),
            Text(
              '인분',
              style: TextStyle(
                fontFamily: 'Pretendard',
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: fg,
                letterSpacing: 0,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 분석한 원본 이미지를 라운드 카드로 보여준다(Figma: 결과 화면 상단에 첨부/촬영
/// 이미지 노출, 직접 입력 화면과 동일한 스타일). 로드 실패 시 영역을 접는다.
class _AnalyzedImageCard extends StatelessWidget {
  const _AnalyzedImageCard({required this.file});

  final File file;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(AppRadius.lg),
      child: AspectRatio(
        aspectRatio: 16 / 10,
        child: Image.file(
          file,
          fit: BoxFit.cover,
          gaplessPlayback: true,
          errorBuilder:
              (BuildContext context, Object error, StackTrace? stack) =>
                  const SizedBox.shrink(),
        ),
      ),
    );
  }
}

/// 영양제 한 제품을 여러 장으로 촬영했을 때 모든 원본 이미지를 함께 보여준다.
/// 한 제품의 여러 라벨 사진은 각각 OCR 증거가 다르므로, 첫 장만 고정 노출하지
/// 않고 사용자가 큰 미리보기에서 직접 넘겨 확인할 수 있게 한다.
class _AnalyzedSupplementImageGallery extends StatefulWidget {
  const _AnalyzedSupplementImageGallery({
    required this.files,
    this.selectedIndex = 0,
    this.onSelected,
  });

  final List<File> files;

  /// Parent-controlled selected image index, kept in sync with the analysis
  /// result so selecting a photo also switches the shown result (and vice versa).
  final int selectedIndex;

  /// Reports a user-initiated image selection (swipe or thumbnail tap) upward.
  final ValueChanged<int>? onSelected;

  @override
  State<_AnalyzedSupplementImageGallery> createState() =>
      _AnalyzedSupplementImageGalleryState();
}

class _AnalyzedSupplementImageGalleryState
    extends State<_AnalyzedSupplementImageGallery> {
  late final PageController _pageController;
  int _selectedIndex = 0;

  int get _clampedWidgetIndex {
    if (widget.files.isEmpty) return 0;
    final int last = widget.files.length - 1;
    if (widget.selectedIndex < 0) return 0;
    if (widget.selectedIndex > last) return last;
    return widget.selectedIndex;
  }

  @override
  void initState() {
    super.initState();
    _selectedIndex = _clampedWidgetIndex;
    _pageController = PageController(initialPage: _selectedIndex);
  }

  @override
  void didUpdateWidget(covariant _AnalyzedSupplementImageGallery oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.files.isEmpty) {
      _selectedIndex = 0;
      return;
    }
    // Reverse sync: the parent moved the selected index (e.g. result/tab change)
    // → animate the gallery so the shown photo matches the result.
    final int target = _clampedWidgetIndex;
    if (widget.selectedIndex != oldWidget.selectedIndex &&
        target != _selectedIndex) {
      _selectedIndex = target;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted || !_pageController.hasClients) return;
        _pageController.animateToPage(
          target,
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeOutCubic,
        );
      });
    }
    // Clamp when the image list shrinks.
    if (_selectedIndex >= widget.files.length) {
      _selectedIndex = widget.files.length - 1;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted || !_pageController.hasClients) return;
        _pageController.jumpToPage(_selectedIndex);
      });
    }
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final List<File> files = widget.files;
    if (files.isEmpty) return const SizedBox.shrink();
    if (files.length == 1) {
      return _AnalyzedImageCard(file: files.first);
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Stack(
          children: <Widget>[
            ClipRRect(
              borderRadius: BorderRadius.circular(AppRadius.lg),
              child: AspectRatio(
                aspectRatio: 16 / 10,
                child: PageView.builder(
                  key: const ValueKey<String>('supplement-image-page-view'),
                  controller: _pageController,
                  itemCount: files.length,
                  onPageChanged: (int index) {
                    setState(() {
                      _selectedIndex = index;
                    });
                    widget.onSelected?.call(index);
                  },
                  itemBuilder: (BuildContext context, int index) {
                    return Image.file(
                      files[index],
                      fit: BoxFit.cover,
                      gaplessPlayback: true,
                      errorBuilder:
                          (
                            BuildContext context,
                            Object error,
                            StackTrace? stack,
                          ) => const SizedBox.shrink(),
                    );
                  },
                ),
              ),
            ),
            Positioned(
              right: AppSpace.sm,
              bottom: AppSpace.sm,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.58),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpace.sm,
                    vertical: 5,
                  ),
                  child: Text(
                    '${_selectedIndex + 1}/${files.length}',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpace.sm),
        SizedBox(
          height: 86,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: files.length,
            separatorBuilder: (BuildContext context, int index) =>
                const SizedBox(width: AppSpace.xs),
            itemBuilder: (BuildContext context, int index) {
              return _AnalyzedImageThumbnail(
                file: files[index],
                index: index,
                total: files.length,
                selected: index == _selectedIndex,
                onTap: () => _selectImage(index),
              );
            },
          ),
        ),
      ],
    );
  }

  void _selectImage(int index) {
    setState(() {
      _selectedIndex = index;
    });
    widget.onSelected?.call(index);
    if (!_pageController.hasClients) return;
    _pageController.animateToPage(
      index,
      duration: const Duration(milliseconds: 220),
      curve: Curves.easeOutCubic,
    );
  }
}

class _AnalyzedImageThumbnail extends StatelessWidget {
  const _AnalyzedImageThumbnail({
    required this.file,
    required this.index,
    required this.total,
    required this.selected,
    required this.onTap,
  });

  final File file;
  final int index;
  final int total;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: '영양제 라벨 사진 ${index + 1}/$total',
      image: true,
      selected: selected,
      button: true,
      child: GestureDetector(
        key: ValueKey<String>('supplement-image-thumbnail-$index'),
        onTap: onTap,
        child: DecoratedBox(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(AppRadius.md + 2),
            border: Border.all(
              color: selected ? AppColor.brand : Colors.transparent,
              width: 2,
            ),
          ),
          child: Padding(
            padding: const EdgeInsets.all(2),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(AppRadius.md),
              child: Stack(
                children: <Widget>[
                  SizedBox(
                    width: 76,
                    height: 86,
                    child: Image.file(
                      file,
                      fit: BoxFit.cover,
                      gaplessPlayback: true,
                      errorBuilder:
                          (
                            BuildContext context,
                            Object error,
                            StackTrace? stack,
                          ) => const SizedBox.shrink(),
                    ),
                  ),
                  Positioned(
                    left: 6,
                    top: 6,
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        color: Colors.black.withValues(alpha: 0.55),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 7,
                          vertical: 3,
                        ),
                        child: Text(
                          '${index + 1}',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 11,
                            fontWeight: FontWeight.w900,
                            letterSpacing: 0,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// 예상 영양소 카드(figma 06 심화) — 선택 후보의 예상 열량·탄단지를 읽기 전용
/// 표시한다. D2 준수: 매크로는 그램 값으로만 표기하고 신뢰도/기준치 %는 노출하지
/// 않는다. 섭취량(인분)에 비례해 스케일하며, 값이 없는 행은 숨긴다(미허위).
class _PredictedNutrientCard extends StatelessWidget {
  const _PredictedNutrientCard({
    required this.candidate,
    required this.portionAmount,
  });

  final MealFoodCandidate candidate;
  final double portionAmount;

  /// 섭취량(인분) 배율. 후보의 kcal/탄단지는 백엔드가 추정한 분량(portion_amount
  /// 그램)에 대한 1인분 값이므로, 그 값에 사용자가 고른 인분 수를 곱한다.
  /// (portion_amount 는 무게라서 배율 분모로 쓰지 않는다.)
  double get _scale => portionAmount <= 0 ? 1 : portionAmount;

  double? _scaled(double? value) => value == null ? null : value * _scale;

  @override
  Widget build(BuildContext context) {
    final double? kcal = _scaled(candidate.kcal);
    final double? carb = _scaled(candidate.carbG);
    final double? protein = _scaled(candidate.proteinG);
    final double? fat = _scaled(candidate.fatG);
    final double? sodium = _scaled(candidate.sodiumMg);
    return Container(
      key: const ValueKey<String>('predicted-nutrient-card'),
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside),
      decoration: BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        boxShadow: AppShadow.softCard,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          if (kcal != null) ...<Widget>[
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: <Widget>[
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpace.sm,
                    vertical: 3,
                  ),
                  decoration: BoxDecoration(
                    color: AppColor.brandSoft,
                    borderRadius: BorderRadius.circular(AppRadius.full),
                  ),
                  child: Text(
                    '예상 열량',
                    style: TextStyle(
                      color: AppColor.brandDeep,
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                      height: 1.2,
                      letterSpacing: 0,
                    ),
                  ),
                ),
                const Spacer(),
                Text(
                  _round(kcal),
                  style: const TextStyle(
                    color: AppColor.ink,
                    fontSize: 26,
                    fontWeight: FontWeight.w900,
                    height: 1.0,
                    letterSpacing: 0,
                  ),
                ),
                const SizedBox(width: 4),
                Padding(
                  padding: const EdgeInsets.only(bottom: 2),
                  child: Text(
                    'kcal',
                    style: AppText.caption.copyWith(
                      color: AppColor.inkTertiary,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              '${formatPortionLabel(portionAmount)} 기준',
              style: AppText.caption.copyWith(color: AppColor.inkTertiary),
            ),
            const SizedBox(height: AppSpace.md),
          ],
          // 매크로 행 — D2: 그램 값만, % 비노출. null 행은 숨김.
          _PredictedMacroRow(
            label: '탄수화물',
            grams: carb,
            color: AppColor.warning,
          ),
          // '단백질' 단독 텍스트는 영양분석 그리드와 충돌하므로 '단백질 (예상)' 사용.
          _PredictedMacroRow(
            label: '단백질 (예상)',
            grams: protein,
            color: AppColor.success,
          ),
          _PredictedMacroRow(label: '지방', grams: fat, color: AppColor.danger),
          _PredictedMacroRow(
            label: '나트륨',
            grams: sodium,
            color: AppColor.review,
            unit: 'mg',
          ),
        ],
      ),
    );
  }

  static String _round(double value) => value.round().toString();
}

/// 예상 매크로 한 행 — 색 점 + 라벨 + 채움 바 + 그램 값. 값이 null 이면 숨김.
class _PredictedMacroRow extends StatelessWidget {
  const _PredictedMacroRow({
    required this.label,
    required this.grams,
    required this.color,
    this.unit = 'g',
  });

  final String label;
  final double? grams;
  final Color color;
  final String unit;

  @override
  Widget build(BuildContext context) {
    final double? value = grams;
    if (value == null) return const SizedBox.shrink();
    // 채움 바는 단순 시각 단서(상한 100g/2000mg 가정) — 숫자(%)는 노출 안 함.
    final double cap = unit == 'mg' ? 2000 : 100;
    final double fill = (value / cap).clamp(0, 1).toDouble();
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpace.sm),
      child: Row(
        children: <Widget>[
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: AppSpace.sm),
          SizedBox(
            width: 84,
            child: Text(
              label,
              style: AppText.body.copyWith(color: AppColor.inkSecondary),
            ),
          ),
          const SizedBox(width: AppSpace.sm),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(AppRadius.full),
              child: LinearProgressIndicator(
                value: fill,
                minHeight: 6,
                backgroundColor: AppColor.sunken,
                valueColor: AlwaysStoppedAnimation<Color>(color),
              ),
            ),
          ),
          const SizedBox(width: AppSpace.sm),
          Text(
            '${value.round()}$unit',
            style: const TextStyle(
              color: AppColor.ink,
              fontSize: 15,
              fontWeight: FontWeight.w800,
              letterSpacing: 0,
            ),
          ),
        ],
      ),
    );
  }
}

class _MealReviewCorrectionCard extends StatelessWidget {
  const _MealReviewCorrectionCard({
    required this.mealNameController,
    required this.portionAmountController,
    required this.portionUnitController,
    required this.kcalController,
    required this.carbController,
    required this.proteinController,
    required this.fatController,
    required this.sodiumController,
    required this.requiresManualEntry,
  });

  final TextEditingController mealNameController;
  final TextEditingController portionAmountController;
  final TextEditingController portionUnitController;
  final TextEditingController kcalController;
  final TextEditingController carbController;
  final TextEditingController proteinController;
  final TextEditingController fatController;
  final TextEditingController sodiumController;
  final bool requiresManualEntry;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside),
      decoration: BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        boxShadow: AppShadow.elev1,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              const Expanded(
                child: Text(
                  '식단 확인',
                  style: TextStyle(
                    color: AppColor.ink,
                    fontSize: 18,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0,
                  ),
                ),
              ),
              if (requiresManualEntry)
                const Icon(
                  Icons.edit_note_rounded,
                  color: AppColor.warning,
                  size: 22,
                ),
            ],
          ),
          const SizedBox(height: AppSpace.md),
          _ReviewTextField(
            controller: mealNameController,
            label: '음식명',
            hintText: '예: 비빔밥',
          ),
          const SizedBox(height: AppSpace.sm),
          Row(
            children: <Widget>[
              Expanded(
                child: _ReviewTextField(
                  controller: portionAmountController,
                  label: '분량',
                  hintText: '1',
                  keyboardType: TextInputType.number,
                ),
              ),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: _ReviewTextField(
                  controller: portionUnitController,
                  label: '단위',
                  hintText: 'bowl',
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.sm),
          Row(
            children: <Widget>[
              Expanded(
                child: _ReviewTextField(
                  controller: kcalController,
                  label: 'kcal',
                  hintText: '520',
                  keyboardType: TextInputType.number,
                ),
              ),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: _ReviewTextField(
                  controller: sodiumController,
                  label: '나트륨 mg',
                  hintText: '820',
                  keyboardType: TextInputType.number,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.sm),
          Row(
            children: <Widget>[
              Expanded(
                child: _ReviewTextField(
                  controller: carbController,
                  label: '탄수화물 g',
                  hintText: '78',
                  keyboardType: TextInputType.number,
                ),
              ),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: _ReviewTextField(
                  controller: proteinController,
                  label: '단백질 g',
                  hintText: '18',
                  keyboardType: TextInputType.number,
                ),
              ),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: _ReviewTextField(
                  controller: fatController,
                  label: '지방 g',
                  hintText: '12',
                  keyboardType: TextInputType.number,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _PipelineLedStrip extends StatelessWidget {
  const _PipelineLedStrip({required this.metadata});

  final SupplementImagePipelineMetadata metadata;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: <Widget>[
        _PipelineLed(status: metadata.ocrStatus, stage: 'ocr'),
        const SizedBox(width: AppSpace.xs),
        _PipelineLed(status: metadata.visionStatus, stage: 'vision'),
        const SizedBox(width: AppSpace.xs),
        _PipelineLed(status: metadata.llmStatus, stage: 'llm'),
      ],
    );
  }
}

class _PipelineLed extends StatelessWidget {
  const _PipelineLed({required this.status, required this.stage});

  final String status;
  final String stage;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: '$stage $status',
      child: Container(
        key: ValueKey<String>('pipeline-led-$stage-$status'),
        width: 10,
        height: 10,
        decoration: BoxDecoration(
          color: _statusColor(status),
          shape: BoxShape.circle,
        ),
      ),
    );
  }

  Color _statusColor(String status) {
    return switch (status) {
      'success' => const Color(0xFF22B07D),
      'warning' => const Color(0xFFFFC107),
      'failed' => const Color(0xFFFF6B6B),
      _ => const Color(0xFFC7CDD6),
    };
  }
}

/// 영양제 분류 드롭다운 카드 (figma 855:23 — 가이드 10 ③-P2 7).
///
/// 카탈로그(`GET /supplements/categories`)에서 받은 분류 중 하나를 고른다.
/// '선택 안 함'(null)이 기본이며, 미선택 시 등록 요청에 category_key 를
/// 보내지 않는다.
class _CategoryDropdownCard extends StatelessWidget {
  const _CategoryDropdownCard({
    required this.categories,
    required this.selectedKey,
    required this.onChanged,
  });

  final List<SupplementCategory> categories;
  final String? selectedKey;
  final ValueChanged<String?> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside),
      decoration: BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        boxShadow: AppShadow.elev1,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: AppColor.brand.withValues(alpha: 0.13),
                  borderRadius: BorderRadius.circular(13),
                ),
                child: Icon(
                  Icons.category_rounded,
                  color: AppColor.brand,
                  size: 22,
                ),
              ),
              const SizedBox(width: AppSpace.sm),
              const Expanded(
                child: Text(
                  '분류',
                  style: TextStyle(
                    color: AppColor.ink,
                    fontSize: 17,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.sm),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: AppSpace.md),
            decoration: BoxDecoration(
              color: AppColor.surface,
              borderRadius: BorderRadius.circular(AppRadius.md),
              border: Border.all(color: AppColor.border),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String?>(
                value: selectedKey,
                isExpanded: true,
                borderRadius: BorderRadius.circular(AppRadius.md),
                icon: const Icon(
                  Icons.expand_more_rounded,
                  color: AppColor.inkSecondary,
                ),
                style: AppText.body.copyWith(color: AppColor.ink),
                items: <DropdownMenuItem<String?>>[
                  DropdownMenuItem<String?>(
                    child: Text(
                      '선택 안 함',
                      style: AppText.body.copyWith(
                        color: AppColor.inkSecondary,
                      ),
                    ),
                  ),
                  for (final SupplementCategory category in categories)
                    DropdownMenuItem<String?>(
                      value: category.categoryKey,
                      child: Text(
                        category.displayName,
                        overflow: TextOverflow.ellipsis,
                        style: AppText.body.copyWith(color: AppColor.ink),
                      ),
                    ),
                ],
                onChanged: onChanged,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// 핵심성분 배지 카드(figma 12) — 상위 성분의 함량과 충족 등급을 한눈에 보여준다.
///
/// 각 행: 성분명 · 함량값(w900) · 충족 등급 칩 · 채움 바.
/// D2 준수: 영양성분기준치(%DV)는 숫자로 노출하지 않고 충분/부족 등급 칩으로만
/// 표현하며, null 이면 '직접 확인' 칩과 빈 바(숨김)로 처리한다.
class _CoreIngredientCard extends StatelessWidget {
  const _CoreIngredientCard({required this.ingredients});

  final List<SupplementIngredientCandidate> ingredients;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const ValueKey<String>('core-ingredient-card'),
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside),
      decoration: BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        boxShadow: AppShadow.softCard,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Text(
            '핵심 성분 한눈에',
            style: TextStyle(
              color: AppColor.ink,
              fontSize: 17,
              fontWeight: FontWeight.w900,
              letterSpacing: 0,
            ),
          ),
          const SizedBox(height: AppSpace.md),
          for (int index = 0; index < ingredients.length; index++) ...<Widget>[
            if (index != 0) const SizedBox(height: AppSpace.md),
            _CoreIngredientRow(ingredient: ingredients[index]),
          ],
        ],
      ),
    );
  }
}

class _CoreIngredientRow extends StatelessWidget {
  const _CoreIngredientRow({required this.ingredient});

  final SupplementIngredientCandidate ingredient;

  @override
  Widget build(BuildContext context) {
    final double? dv = ingredient.dailyValuePercent;
    // 충족 등급(figma) — %DV ≥ 100 충분 / < 100 부족 / null 직접 확인.
    final (String gradeLabel, Color gradeFg, Color gradeBg) = dv == null
        ? ('직접 확인', AppColor.review, AppColor.reviewSoft)
        : dv >= 100
        ? ('충분', AppColor.success, AppColor.successSoft)
        : ('부족', AppColor.review, AppColor.reviewSoft);
    final double? fillValue = dv == null ? null : (dv / 100).clamp(0, 1);
    final Color fillColor = (dv != null && dv >= 100)
        ? AppColor.success
        : AppColor.review;
    final String? amountText = _amountText(ingredient.amount, ingredient.unit);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: Text(
                _displayName(ingredient.displayName, ingredient.originalName),
                style: const TextStyle(
                  color: AppColor.ink,
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  height: 1.3,
                  letterSpacing: 0,
                ),
              ),
            ),
            if (amountText != null) ...<Widget>[
              const SizedBox(width: AppSpace.sm),
              Text(
                amountText,
                style: const TextStyle(
                  color: AppColor.ink,
                  fontSize: 15,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 0,
                ),
              ),
            ],
            const SizedBox(width: AppSpace.sm),
            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpace.sm,
                vertical: 3,
              ),
              decoration: BoxDecoration(
                color: gradeBg,
                borderRadius: BorderRadius.circular(AppRadius.full),
              ),
              child: Text(
                gradeLabel,
                style: TextStyle(
                  color: gradeFg,
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                  height: 1.2,
                  letterSpacing: 0,
                ),
              ),
            ),
          ],
        ),
        if (fillValue != null) ...<Widget>[
          const SizedBox(height: AppSpace.sm),
          ClipRRect(
            borderRadius: BorderRadius.circular(AppRadius.full),
            child: LinearProgressIndicator(
              value: fillValue,
              minHeight: 6,
              backgroundColor: AppColor.sunken,
              valueColor: AlwaysStoppedAnimation<Color>(fillColor),
            ),
          ),
        ],
      ],
    );
  }

  /// 성분명 — 원문명이 다르면 병기, 같거나 없으면 표시명만.
  static String _displayName(String displayName, String? original) {
    final String display = displayName.trim();
    final String? originalName = original?.trim();
    if (originalName == null || originalName.isEmpty) return display;
    if (display.isEmpty) return originalName;
    if (originalName.toLowerCase() == display.toLowerCase()) return display;
    if (display.contains(originalName)) return display;
    return '$display ($originalName)';
  }

  /// 함량값(예: '25 mcg') — 함량이 없으면 null(값·바 숨김).
  static String? _amountText(double? amount, String? unit) {
    if (amount == null) return null;
    final String value = amount == amount.roundToDouble()
        ? amount.toStringAsFixed(0)
        : amount.toString();
    final String trimmedUnit = unit?.trim() ?? '';
    return trimmedUnit.isEmpty ? value : '$value $trimmedUnit';
  }
}

class _SupplementInfoCard extends StatelessWidget {
  const _SupplementInfoCard({
    required this.icon,
    required this.title,
    this.body,
    this.bodyWidget,
    required this.missingMessage,
    required this.onEdit,
    this.trailingCount,
  }) : assert(body != null || bodyWidget != null);

  final IconData icon;
  final String title;
  final String? body;
  final Widget? bodyWidget;
  final String? missingMessage;
  final VoidCallback? onEdit;

  /// 제목 우측 경량 카운트 라벨('성분 N개' 등). null 이면 미노출.
  final String? trailingCount;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside),
      decoration: BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        boxShadow: AppShadow.elev1,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: AppColor.brand.withValues(alpha: 0.13),
                  borderRadius: BorderRadius.circular(11),
                ),
                child: Icon(icon, color: AppColor.brand, size: 20),
              ),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  alignment: Alignment.centerLeft,
                  child: Text(
                    title,
                    maxLines: 1,
                    softWrap: false,
                    style: const TextStyle(
                      color: AppColor.ink,
                      fontSize: 17,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 0,
                    ),
                  ),
                ),
              ),
              if (trailingCount != null) ...<Widget>[
                const SizedBox(width: AppSpace.sm),
                Text(
                  trailingCount!,
                  style: const TextStyle(
                    color: AppColor.inkTertiary,
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0,
                  ),
                ),
              ],
              const SizedBox(width: AppSpace.xs),
              IconButton(
                tooltip: '$title 수정',
                onPressed: onEdit,
                icon: const Icon(Icons.edit_rounded),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.sm),
          bodyWidget ??
              Text(
                body!,
                style: const TextStyle(
                  color: AppColor.ink,
                  fontSize: 17,
                  height: 1.45,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 0,
                ),
              ),
          if (missingMessage != null) ...<Widget>[
            const SizedBox(height: AppSpace.sm),
            Text(
              missingMessage!,
              style: const TextStyle(
                color: AppColor.review,
                fontSize: 13,
                height: 1.4,
                fontWeight: FontWeight.w800,
                letterSpacing: 0,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _ReviewTextField extends StatelessWidget {
  const _ReviewTextField({
    required this.controller,
    required this.label,
    required this.hintText,
    this.keyboardType,
    this.maxLines = 1,
  });

  final TextEditingController controller;
  final String label;
  final String hintText;
  final TextInputType? keyboardType;
  final int maxLines;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      keyboardType: keyboardType,
      maxLines: maxLines,
      style: const TextStyle(
        color: AppColor.ink,
        fontSize: 14,
        fontWeight: FontWeight.w800,
        letterSpacing: 0,
      ),
      decoration: InputDecoration(
        labelText: label,
        hintText: hintText,
        isDense: true,
        filled: true,
        fillColor: const Color(0xFFF6F7F5),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.md),
          borderSide: const BorderSide(color: Color(0xFFE3E6E0)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.md),
          borderSide: const BorderSide(color: Color(0xFFE3E6E0)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.md),
          borderSide: BorderSide(color: AppColor.brand, width: 1.5),
        ),
      ),
    );
  }
}

class _ImpactPreviewCard extends StatelessWidget {
  const _ImpactPreviewCard({required this.preview, required this.explanation});

  final SupplementImpactPreviewResponse preview;
  final SupplementRecommendationExplainResponse? explanation;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside),
      decoration: BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        boxShadow: AppShadow.elev1,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Text(
            '로컬 LLM 설명',
            style: TextStyle(
              color: AppColor.ink,
              fontSize: 18,
              fontWeight: FontWeight.w900,
              letterSpacing: 0,
            ),
          ),
          const SizedBox(height: AppSpace.sm),
          Text(
            explanation?.safeUserMessage ?? preview.safeUserMessage,
            style: const TextStyle(
              color: AppColor.inkSecondary,
              fontSize: 14,
              height: 1.45,
              letterSpacing: 0,
            ),
          ),
          if (explanation != null) ...<Widget>[
            const SizedBox(height: AppSpace.sm),
            for (final String bullet in explanation!.explanationBullets.take(3))
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  '· $bullet',
                  style: const TextStyle(
                    color: AppColor.inkSecondary,
                    fontSize: 13,
                    height: 1.35,
                    letterSpacing: 0,
                  ),
                ),
              ),
            _ExplanationSourceList(citations: explanation!.sourceCitations),
          ],
        ],
      ),
    );
  }
}

class _AnalysisExplanationCard extends StatelessWidget {
  const _AnalysisExplanationCard({
    required this.explanation,
    required this.busy,
    required this.onExplain,
  });

  final SupplementRecommendationExplainResponse? explanation;
  final bool busy;
  final VoidCallback? onExplain;

  @override
  Widget build(BuildContext context) {
    final SupplementRecommendationExplainResponse? current = explanation;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside),
      decoration: BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        boxShadow: AppShadow.elev1,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Text(
            '등록 전 로컬 설명',
            style: TextStyle(
              color: AppColor.ink,
              fontSize: 18,
              fontWeight: FontWeight.w900,
              letterSpacing: 0,
            ),
          ),
          const SizedBox(height: AppSpace.sm),
          Text(
            current?.safeUserMessage ?? 'Ollama가 등록 전 분석 후보와 누락 섹션을 요약해요.',
            style: const TextStyle(
              color: AppColor.inkSecondary,
              fontSize: 14,
              height: 1.45,
              letterSpacing: 0,
            ),
          ),
          if (current != null) ...<Widget>[
            const SizedBox(height: AppSpace.sm),
            for (final String bullet in current.explanationBullets.take(3))
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  '· $bullet',
                  style: const TextStyle(
                    color: AppColor.inkSecondary,
                    fontSize: 13,
                    height: 1.35,
                    letterSpacing: 0,
                  ),
                ),
              ),
            _ExplanationSourceList(citations: current.sourceCitations),
          ],
          const SizedBox(height: AppSpace.md),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: busy ? null : onExplain,
              icon: const Icon(Icons.auto_awesome_rounded, size: 18),
              label: Text(busy ? '요청 중' : '분석 설명 받기'),
              style: OutlinedButton.styleFrom(
                foregroundColor: AppColor.ink,
                side: BorderSide(color: AppColor.brand),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(AppRadius.md),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ExplanationSourceList extends StatelessWidget {
  const _ExplanationSourceList({required this.citations});

  final List<SupplementExplanationSourceCitation> citations;

  @override
  Widget build(BuildContext context) {
    if (citations.isEmpty) {
      return const SizedBox.shrink();
    }
    return Padding(
      padding: const EdgeInsets.only(top: AppSpace.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Text(
            '출처',
            style: TextStyle(
              color: AppColor.ink,
              fontSize: 13,
              fontWeight: FontWeight.w800,
              letterSpacing: 0,
            ),
          ),
          const SizedBox(height: 4),
          for (final SupplementExplanationSourceCitation citation
              in citations.take(4))
            Text(
              '· ${citation.title} (${citation.sourcePath})',
              style: const TextStyle(
                color: AppColor.inkSecondary,
                fontSize: 12,
                height: 1.35,
                letterSpacing: 0,
              ),
            ),
        ],
      ),
    );
  }
}

class _StatusBanner extends StatelessWidget {
  const _StatusBanner({required this.error});

  final ApiError error;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF2F2),
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(color: const Color(0xFFFFD0D0)),
      ),
      child: Text(
        error.message,
        style: const TextStyle(
          color: Color(0xFFB42318),
          fontSize: 14,
          fontWeight: FontWeight.w700,
          height: 1.35,
          letterSpacing: 0,
        ),
      ),
    );
  }
}

class _MedicalNote extends StatelessWidget {
  const _MedicalNote();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFBEB),
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(color: const Color(0xFFFDE68A)),
      ),
      child: const Text(
        '의료적 진단·처방이 아닌 건강관리 참고 정보예요. 라벨과 복약 정보는 저장 전 직접 확인해주세요.',
        style: TextStyle(
          color: Color(0xFF92400E),
          fontSize: 13,
          height: 1.45,
          fontWeight: FontWeight.w700,
          letterSpacing: 0,
        ),
      ),
    );
  }
}

class _SaveButton extends StatelessWidget {
  const _SaveButton({
    required this.label,
    required this.busy,
    required this.onTap,
  });

  final String label;
  final bool busy;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 56,
      child: FilledButton(
        onPressed: busy ? null : onTap,
        style: FilledButton.styleFrom(
          backgroundColor: AppColor.brand,
          foregroundColor: AppColor.ink,
          disabledBackgroundColor: AppColor.inkDisabled.withValues(alpha: 0.16),
          disabledForegroundColor: AppColor.inkSecondary,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppRadius.full),
          ),
        ),
        child: Text(
          busy ? '처리 중' : label,
          style: const TextStyle(
            fontSize: 17,
            fontWeight: FontWeight.w900,
            letterSpacing: 0,
          ),
        ),
      ),
    );
  }
}
