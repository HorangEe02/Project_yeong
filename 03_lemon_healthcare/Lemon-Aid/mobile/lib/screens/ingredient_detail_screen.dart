// screens/ingredient_detail_screen.dart — 성분 상세 화면 (figma 12-④ `947:49`).
//
// 분석 결과의 성분 한 줄을 받아 식별·함량·권장량 게이지·도움 정보·질환 조건부
// 주의 배너·면책 푸터를 표시한다. 연산은 백엔드 책임 — 모바일은 표시·매핑만
// 담당한다 (mobile/CLAUDE.md). KDRIs(GET /nutrition/kdris) 만 신규 조회하고,
// 실패하면 권장량 카드를 생략한다(빈 화면 금지).

import 'package:flutter/material.dart';

import '../core/api/api_error.dart';
import '../features/nutrition/kdri_models.dart';
import '../features/supplements/comprehensive_analysis_models.dart';
import '../features/supplements/supplement_models.dart';
import '../features/supplements/supplement_repository.dart';
import '../utils/design_tokens_v2.dart';
import '../widgets/common/confidence_grade_chip.dart';

/// 성분 상세 화면.
///
/// 진입 인자는 분석 결과가 이미 보유한 데이터(preview 성분 행 + comprehensive +
/// explain)이며, 상세 화면에서는 KDRIs 만 신규 호출한다.
class IngredientDetailScreen extends StatefulWidget {
  /// 성분 상세 화면을 만든다.
  ///
  /// Args:
  ///   ingredient: 분석 결과의 성분 행.
  ///   repository: KDRIs 조회용 repository.
  ///   comprehensive: 질환 조건부 주의 배너용 종합 분석(없으면 배너 생략).
  ///   explanation: 도움 정보 리스트용 explain 응답(없으면 도움 정보 생략).
  ///   age: KDRIs 조회용 나이(보유 시).
  ///   sex: KDRIs 조회용 성별(`male`/`female`, 보유 시).
  ///   pregnancyStatus: KDRIs 조회용 임신/수유 상태.
  const IngredientDetailScreen({
    super.key,
    required this.ingredient,
    required this.repository,
    this.comprehensive,
    this.explanation,
    this.age = 30,
    this.sex = 'female',
    this.pregnancyStatus = 'none',
  });

  /// 분석 결과의 성분 행.
  final SupplementIngredientCandidate ingredient;

  /// KDRIs 조회용 repository.
  final LemonAidRepository repository;

  /// 질환 조건부 주의 배너용 종합 분석.
  final ComprehensiveDietAnalysis? comprehensive;

  /// 도움 정보 리스트용 explain 응답.
  final SupplementRecommendationExplainResponse? explanation;

  /// KDRIs 조회용 나이.
  final int age;

  /// KDRIs 조회용 성별 (`male` / `female`).
  final String sex;

  /// KDRIs 조회용 임신/수유 상태.
  final String pregnancyStatus;

  @override
  State<IngredientDetailScreen> createState() => _IngredientDetailScreenState();
}

class _IngredientDetailScreenState extends State<IngredientDetailScreen> {
  bool _loadingKdris = true;
  bool _kdrisFailed = false;
  KdriReference? _reference;
  KdriLookupResult? _lookup;

  @override
  void initState() {
    super.initState();
    _loadKdris();
  }

  Future<void> _loadKdris() async {
    try {
      final KdriLookupResult result = await widget.repository.lookupKdris(
        age: widget.age,
        sex: widget.sex,
        pregnancyStatus: widget.pregnancyStatus,
      );
      if (!mounted) return;
      setState(() {
        _lookup = result;
        _reference = result.referenceFor(widget.ingredient.nutrientCode);
        _loadingKdris = false;
        _kdrisFailed = false;
      });
    } on ApiError {
      _markKdrisFailed();
    } on ArgumentError {
      _markKdrisFailed();
    } on Exception {
      _markKdrisFailed();
    }
  }

  void _markKdrisFailed() {
    if (!mounted) return;
    setState(() {
      _loadingKdris = false;
      _kdrisFailed = true;
    });
  }

  @override
  Widget build(BuildContext context) {
    final SupplementIngredientCandidate ingredient = widget.ingredient;
    return Scaffold(
      backgroundColor: AppColor.section,
      appBar: AppBar(
        backgroundColor: AppColor.section,
        elevation: 0,
        foregroundColor: AppColor.ink,
        title: const Text(
          '성분 상세',
          style: TextStyle(
            fontFamily: 'Pretendard',
            fontSize: 18,
            fontWeight: FontWeight.w800,
            color: AppColor.ink,
            letterSpacing: 0,
          ),
        ),
      ),
      body: SafeArea(
        top: false,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(
            AppSpace.page,
            AppSpace.lg,
            AppSpace.page,
            AppSpace.xl,
          ),
          children: <Widget>[
            _IdentityCard(ingredient: ingredient),
            const SizedBox(height: AppSpace.md),
            _AmountGaugeSection(
              ingredient: ingredient,
              loading: _loadingKdris,
              failed: _kdrisFailed,
              reference: _reference,
              lookup: _lookup,
            ),
            ..._helpfulInfoSection(),
            ..._cautionBannerSection(),
            // 함유 식품 칩 섹션은 백엔드 공백(KDRIs/comprehensive 응답에 식품
            // 출처 데이터 없음)으로 비표시한다. 임의 정적 사전 금지 — 라우트
            // 신설 후 표시 (가이드 ④-3, ⑤ 백엔드 공백 ①).
            const SizedBox(height: AppSpace.lg),
            const _IngredientMedicalNote(),
          ],
        ),
      ),
    );
  }

  /// '이런 점에 도움을 줄 수 있어요' 리스트. explain 응답의 bullets/citations 가
  /// 있을 때만 표시한다(없으면 생략 — 날조 금지). figma 라벨 '효능'은 의료법
  /// 금칙어라 대체 문구를 사용한다.
  List<Widget> _helpfulInfoSection() {
    final SupplementRecommendationExplainResponse? explanation =
        widget.explanation;
    if (explanation == null) return const <Widget>[];
    final List<String> bullets = explanation.explanationBullets
        .where((String bullet) => bullet.trim().isNotEmpty)
        .toList(growable: false);
    if (bullets.isEmpty) return const <Widget>[];
    return <Widget>[
      const SizedBox(height: AppSpace.md),
      _HelpfulInfoCard(
        bullets: bullets,
        citations: explanation.sourceCitations,
      ),
    ];
  }

  /// 질환 조건부 주의 배너. comprehensive 의 cautionary_components 중 이 성분과
  /// 매칭되고 chronic_disease_indications 가 있을 때만 표시한다(가이드 ④-3).
  List<Widget> _cautionBannerSection() {
    final ComprehensiveDietAnalysis? comprehensive = widget.comprehensive;
    if (comprehensive == null) return const <Widget>[];
    if (comprehensive.chronicDiseaseIndications.isEmpty) {
      return const <Widget>[];
    }
    final ComprehensiveCautionaryComponent? match = _matchedCaution(
      comprehensive,
    );
    if (match == null) return const <Widget>[];
    return <Widget>[
      const SizedBox(height: AppSpace.md),
      _CautionBannerCard(component: match),
    ];
  }

  ComprehensiveCautionaryComponent? _matchedCaution(
    ComprehensiveDietAnalysis comprehensive,
  ) {
    final String ingredientKey = _normalize(widget.ingredient.displayName);
    final String? originalKey = widget.ingredient.originalName == null
        ? null
        : _normalize(widget.ingredient.originalName!);
    for (final ComprehensiveCautionaryComponent component
        in comprehensive.cautionaryComponents) {
      final String componentKey = _normalize(component.component);
      if (componentKey.isEmpty) continue;
      if (componentKey == ingredientKey ||
          (originalKey != null && componentKey == originalKey) ||
          ingredientKey.contains(componentKey) ||
          componentKey.contains(ingredientKey)) {
        return component;
      }
    }
    return null;
  }

  static String _normalize(String value) {
    return value.trim().toLowerCase().replaceAll(RegExp(r'\s+'), ' ');
  }
}

/// 식별 카드: 성분명 + 분류 서브텍스트 + 신뢰도 등급 칩.
class _IdentityCard extends StatelessWidget {
  const _IdentityCard({required this.ingredient});

  final SupplementIngredientCandidate ingredient;

  @override
  Widget build(BuildContext context) {
    final String? subtitle = _classification(ingredient);
    return Container(
      key: const ValueKey<String>('ingredient-detail-identity-card'),
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
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Expanded(
                child: Text(
                  _displayName(ingredient),
                  style: const TextStyle(
                    fontFamily: 'Pretendard',
                    color: AppColor.ink,
                    fontSize: 22,
                    fontWeight: FontWeight.w900,
                    height: 1.3,
                    letterSpacing: 0,
                  ),
                ),
              ),
              const SizedBox(width: AppSpace.sm),
              ConfidenceGradeChip(confidence: ingredient.confidence),
            ],
          ),
          if (subtitle != null) ...<Widget>[
            const SizedBox(height: AppSpace.xs),
            Text(
              subtitle,
              style: const TextStyle(
                fontFamily: 'Pretendard',
                color: AppColor.inkSecondary,
                fontSize: 15,
                fontWeight: FontWeight.w600,
                height: 1.4,
                letterSpacing: 0,
              ),
            ),
          ],
        ],
      ),
    );
  }

  /// 성분명 — 영문 원문이 다르면 '한글(영문)'으로 병기, 같거나 없으면 표시명만.
  String _displayName(SupplementIngredientCandidate ingredient) {
    final String display = ingredient.displayName.trim();
    final String? original = ingredient.originalName?.trim();
    if (original == null || original.isEmpty) return display;
    if (display.isEmpty) return original;
    if (original.toLowerCase() == display.toLowerCase()) return display;
    if (display.contains(original)) return display;
    return '$display ($original)';
  }

  String? _classification(SupplementIngredientCandidate ingredient) {
    final String? code = ingredient.nutrientCode?.trim();
    if (code != null && code.isNotEmpty) {
      return '영양소 코드 · $code';
    }
    return null;
  }
}

/// 함량 + 기준치 게이지 섹션을 상태에 따라 렌더한다.
class _AmountGaugeSection extends StatelessWidget {
  const _AmountGaugeSection({
    required this.ingredient,
    required this.loading,
    required this.failed,
    required this.reference,
    required this.lookup,
  });

  final SupplementIngredientCandidate ingredient;
  final bool loading;
  final bool failed;
  final KdriReference? reference;
  final KdriLookupResult? lookup;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const ValueKey<String>('ingredient-detail-amount-card'),
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
            '이 제품 함량',
            style: TextStyle(
              fontFamily: 'Pretendard',
              color: AppColor.inkSecondary,
              fontSize: 15,
              fontWeight: FontWeight.w700,
              letterSpacing: 0,
            ),
          ),
          const SizedBox(height: AppSpace.xs),
          Text(
            _amountText(),
            style: const TextStyle(
              fontFamily: 'Pretendard',
              color: AppColor.ink,
              fontSize: 26,
              fontWeight: FontWeight.w900,
              height: 1.2,
              letterSpacing: 0,
            ),
          ),
          const SizedBox(height: AppSpace.md),
          ..._gaugeChildren(),
        ],
      ),
    );
  }

  String _amountText() {
    final double? amount = ingredient.amount;
    if (amount == null) return '함량 확인 필요';
    final String amountText = _formatAmount(amount);
    final String? unit = _nonEmpty(ingredient.unit);
    if (unit == null) return amountText;
    return '$amountText $unit';
  }

  List<Widget> _gaugeChildren() {
    if (loading) {
      return const <Widget>[
        Padding(
          padding: EdgeInsets.symmetric(vertical: AppSpace.sm),
          child: Center(
            child: SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(strokeWidth: 2.4),
            ),
          ),
        ),
      ];
    }
    if (failed) {
      // KDRIs 조회 실패 — 게이지 대신 안내(화면 자체는 유지, 가이드 ⑥).
      return const <Widget>[
        Text(
          '기준 정보를 불러오지 못했어요. 함량만 표시할게요.',
          key: ValueKey<String>('ingredient-detail-kdris-failed'),
          style: TextStyle(
            fontFamily: 'Pretendard',
            color: AppColor.inkSecondary,
            fontSize: 14,
            height: 1.45,
            fontWeight: FontWeight.w600,
            letterSpacing: 0,
          ),
        ),
      ];
    }

    final _GaugeModel? gauge = _buildGauge();
    if (gauge == null) {
      // %DV·KDRIs 모두 없거나 단위 불일치 — 게이지 생략 + 직접 확인 안내.
      return const <Widget>[
        Row(
          children: <Widget>[
            Icon(Icons.info_outline_rounded, color: AppColor.review, size: 18),
            SizedBox(width: AppSpace.xs),
            Expanded(
              child: Text(
                '기준치를 직접 확인해 주세요.',
                key: ValueKey<String>('ingredient-detail-gauge-unavailable'),
                style: TextStyle(
                  fontFamily: 'Pretendard',
                  color: AppColor.review,
                  fontSize: 14,
                  height: 1.4,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0,
                ),
              ),
            ),
          ],
        ),
      ];
    }

    return <Widget>[
      _GaugeBar(model: gauge),
      const SizedBox(height: AppSpace.sm),
      _GaugeLegend(model: gauge),
      if (_needsReferenceCaption()) ...<Widget>[
        const SizedBox(height: AppSpace.sm),
        Text(
          _referenceCaption(),
          style: const TextStyle(
            fontFamily: 'Pretendard',
            color: AppColor.inkTertiary,
            fontSize: 12,
            height: 1.4,
            fontWeight: FontWeight.w600,
            letterSpacing: 0,
          ),
        ),
      ],
    ];
  }

  /// 기준치 게이지 모델을 만든다.
  ///
  /// dailyValuePercent 가 있으면 우선 사용하고, 없으면 KDRIs reference_amount
  /// 대비 클라이언트 표시 계산을 한다(단위 일치 시에만 — 불일치면 null 반환해
  /// 게이지를 생략한다, 환산 날조 금지).
  _GaugeModel? _buildGauge() {
    final double? percent = _resolvePercent();
    if (percent == null) return null;
    final KdriReference? ref = reference;
    // 상한(UL) 마커: ul_amount 와 함량 단위가 일치할 때만 % 위치를 계산한다.
    double? ulPercent;
    if (ref != null &&
        ref.ulAmount != null &&
        ref.referenceAmount != null &&
        ref.referenceAmount! > 0 &&
        _unitsMatch(ref.ulUnit ?? ref.referenceUnit, ref.referenceUnit)) {
      ulPercent = (ref.ulAmount! / ref.referenceAmount!) * 100;
    }
    return _GaugeModel(percent: percent, ulPercent: ulPercent);
  }

  double? _resolvePercent() {
    final double? dv = ingredient.dailyValuePercent;
    if (dv != null && dv >= 0) return dv;
    final KdriReference? ref = reference;
    final double? amount = ingredient.amount;
    if (ref == null ||
        amount == null ||
        ref.referenceAmount == null ||
        ref.referenceAmount! <= 0) {
      return null;
    }
    // 단위 불일치면 환산 없이 게이지를 생략한다(가이드 ⑥ — 환산 날조 금지).
    if (!_unitsMatch(ingredient.unit, ref.referenceUnit)) return null;
    return (amount / ref.referenceAmount!) * 100;
  }

  bool _needsReferenceCaption() {
    final KdriLookupResult? result = lookup;
    if (result == null) return false;
    if (!result.isOfficialDataset) return true;
    final String? status = reference?.reviewStatus?.trim().toLowerCase();
    return status != null && status != 'reviewed' && status != 'approved';
  }

  String _referenceCaption() {
    final String? note = _nonEmpty(lookup?.note);
    if (note != null) return '참고용 기준값이에요. $note';
    return '참고용 기준값이에요.';
  }

  static bool _unitsMatch(String? left, String? right) {
    final String? a = _nonEmpty(left)?.toLowerCase();
    final String? b = _nonEmpty(right)?.toLowerCase();
    if (a == null || b == null) return false;
    return a == b;
  }

  static String _formatAmount(double value) {
    if (value == value.roundToDouble()) {
      return value.toStringAsFixed(0);
    }
    return value
        .toStringAsFixed(2)
        .replaceAll(RegExp(r'0+$'), '')
        .replaceAll(RegExp(r'\.$'), '');
  }
}

/// 기준치 게이지 표시 모델(채움 % + 상한 마커 %).
class _GaugeModel {
  const _GaugeModel({required this.percent, this.ulPercent});

  /// 권장량 대비 채움 비율(%). 0 이상.
  final double percent;

  /// 상한(UL) 마커 위치(%). 없으면 null.
  final double? ulPercent;

  /// 게이지 색 단계: 100% 이하 success, 100~UL review, UL 초과 danger.
  _GaugeLevel get level {
    if (ulPercent != null && percent > ulPercent!) return _GaugeLevel.over;
    if (percent > 100) return _GaugeLevel.review;
    return _GaugeLevel.ok;
  }
}

/// 게이지 색 단계.
enum _GaugeLevel { ok, review, over }

/// 권장량 100% 기준 채움 바 + 상한(UL) 마커.
class _GaugeBar extends StatelessWidget {
  const _GaugeBar({required this.model});

  final _GaugeModel model;

  @override
  Widget build(BuildContext context) {
    final (Color fill, _, _) = _levelColors(model.level);
    // 스케일: UL 이 있으면 UL 까지, 없으면 최소 120% 까지 그린다.
    final double scaleMax = model.ulPercent == null
        ? (model.percent > 120 ? model.percent : 120)
        : (model.percent > model.ulPercent! ? model.percent : model.ulPercent!);
    final double fillFraction = (model.percent / scaleMax).clamp(0.0, 1.0);
    final double? ulFraction = model.ulPercent == null
        ? null
        : (model.ulPercent! / scaleMax).clamp(0.0, 1.0);
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final double width = constraints.maxWidth;
        return SizedBox(
          height: 16,
          child: Stack(
            children: <Widget>[
              Container(
                decoration: BoxDecoration(
                  color: AppColor.sunken,
                  borderRadius: BorderRadius.circular(AppRadius.full),
                ),
              ),
              FractionallySizedBox(
                widthFactor: fillFraction,
                child: Container(
                  decoration: BoxDecoration(
                    color: fill,
                    borderRadius: BorderRadius.circular(AppRadius.full),
                  ),
                ),
              ),
              if (ulFraction != null)
                Positioned(
                  left: (width * ulFraction - 1).clamp(0.0, width - 2),
                  top: -2,
                  bottom: -2,
                  child: Container(width: 2, color: AppColor.danger),
                ),
            ],
          ),
        );
      },
    );
  }
}

/// 게이지 아래 범례: 채움 % 라벨 + 상한 라벨(아이콘·텍스트 병행, 색 단독 금지).
class _GaugeLegend extends StatelessWidget {
  const _GaugeLegend({required this.model});

  final _GaugeModel model;

  @override
  Widget build(BuildContext context) {
    final (Color color, IconData icon, String label) = _legendFor(model);
    return Row(
      children: <Widget>[
        Icon(icon, color: color, size: 18),
        const SizedBox(width: AppSpace.xs),
        Expanded(
          child: Text(
            label,
            style: TextStyle(
              fontFamily: 'Pretendard',
              color: color,
              fontSize: 14,
              fontWeight: FontWeight.w800,
              height: 1.35,
              letterSpacing: 0,
            ),
          ),
        ),
      ],
    );
  }

  (Color, IconData, String) _legendFor(_GaugeModel model) {
    final String percentText = '기준치 ${model.percent.round()}%';
    switch (model.level) {
      case _GaugeLevel.ok:
        return (
          AppColor.success,
          Icons.check_circle_outline_rounded,
          '$percentText · 권장 범위예요',
        );
      case _GaugeLevel.review:
        return (
          AppColor.review,
          Icons.info_outline_rounded,
          '$percentText · 권장량을 넘었어요',
        );
      case _GaugeLevel.over:
        return (
          AppColor.danger,
          Icons.warning_amber_rounded,
          '$percentText · 상한을 넘었어요',
        );
    }
  }
}

(Color, Color, Color) _levelColors(_GaugeLevel level) {
  switch (level) {
    case _GaugeLevel.ok:
      return (AppColor.success, AppColor.successSoft, AppColor.success);
    case _GaugeLevel.review:
      return (AppColor.review, AppColor.reviewSoft, AppColor.review);
    case _GaugeLevel.over:
      return (AppColor.danger, AppColor.dangerSoft, AppColor.danger);
  }
}

/// '이런 점에 도움을 줄 수 있어요' 카드(출처 칩 포함).
class _HelpfulInfoCard extends StatelessWidget {
  const _HelpfulInfoCard({required this.bullets, required this.citations});

  final List<String> bullets;
  final List<SupplementExplanationSourceCitation> citations;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const ValueKey<String>('ingredient-detail-helpful-card'),
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
            '이런 점에 도움을 줄 수 있어요',
            style: TextStyle(
              fontFamily: 'Pretendard',
              color: AppColor.ink,
              fontSize: 18,
              fontWeight: FontWeight.w900,
              height: 1.3,
              letterSpacing: 0,
            ),
          ),
          const SizedBox(height: AppSpace.sm),
          for (final String bullet in bullets.take(4))
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Icon(Icons.circle, size: 6, color: AppColor.brand),
                  ),
                  const SizedBox(width: AppSpace.sm),
                  Expanded(
                    child: Text(
                      bullet,
                      style: const TextStyle(
                        fontFamily: 'Pretendard',
                        color: AppColor.ink,
                        fontSize: 15,
                        height: 1.5,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 0,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          if (citations.isNotEmpty) ...<Widget>[
            const SizedBox(height: AppSpace.md),
            Wrap(
              spacing: AppSpace.xs,
              runSpacing: AppSpace.xs,
              children: <Widget>[
                for (final SupplementExplanationSourceCitation citation
                    in citations.take(4))
                  _SourceChip(label: '출처 · ${citation.title}'),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

/// 출처 칩.
class _SourceChip extends StatelessWidget {
  const _SourceChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpace.md, vertical: 4),
      decoration: BoxDecoration(
        color: AppColor.brandSoft,
        borderRadius: BorderRadius.circular(AppRadius.full),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontFamily: 'Pretendard',
          color: AppColor.brandDeep,
          fontSize: 12,
          fontWeight: FontWeight.w700,
          height: 1.2,
          letterSpacing: 0,
        ),
      ),
    );
  }
}

/// 질환 조건부 주의 배너(상담 권고형 워딩).
class _CautionBannerCard extends StatelessWidget {
  const _CautionBannerCard({required this.component});

  final ComprehensiveCautionaryComponent component;

  @override
  Widget build(BuildContext context) {
    final bool high = (component.severity ?? '').trim().toLowerCase() == 'high';
    final Color accent = high ? AppColor.danger : AppColor.review;
    final Color accentSoft = high ? AppColor.dangerSoft : AppColor.reviewSoft;
    final String? message = _nonEmpty(component.message);
    final String? reason = _nonEmpty(component.reason);
    return Container(
      key: const ValueKey<String>('ingredient-detail-caution-banner'),
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside),
      decoration: BoxDecoration(
        color: accentSoft,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        border: Border.all(color: accent.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(Icons.warning_amber_rounded, color: accent, size: 20),
              const SizedBox(width: AppSpace.sm),
              Expanded(
                child: Text(
                  '복용 전 의료진과 상담해 보세요',
                  style: TextStyle(
                    fontFamily: 'Pretendard',
                    color: accent,
                    fontSize: 16,
                    fontWeight: FontWeight.w900,
                    height: 1.3,
                    letterSpacing: 0,
                  ),
                ),
              ),
            ],
          ),
          if (message != null || reason != null) ...<Widget>[
            const SizedBox(height: AppSpace.sm),
            Text(
              message ?? reason!,
              style: const TextStyle(
                fontFamily: 'Pretendard',
                color: AppColor.ink,
                fontSize: 15,
                height: 1.5,
                fontWeight: FontWeight.w600,
                letterSpacing: 0,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// 성분 상세 화면 하단 면책 푸터.
class _IngredientMedicalNote extends StatelessWidget {
  const _IngredientMedicalNote();

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const ValueKey<String>('ingredient-detail-medical-note'),
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFBEB),
        borderRadius: BorderRadius.circular(AppRadius.md),
        border: Border.all(color: const Color(0xFFFDE68A)),
      ),
      child: const Text(
        '의료적 진단·처방이 아닌 건강관리 참고 정보예요. 기준치는 개인 상태에 따라 달라질 수 있으니 '
        '직접 확인해 주세요.',
        style: TextStyle(
          fontFamily: 'Pretendard',
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

String? _nonEmpty(String? value) {
  if (value == null) return null;
  final String trimmed = value.trim();
  return trimmed.isEmpty ? null : trimmed;
}
