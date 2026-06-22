// widgets/common/diet_result_cards.dart — 식단 종합 결과(C 하이브리드) 카드 모음
//
// figma 채택안 C: 점수 링 게이지 + 헤드라인 → 주의 성분 카드(최우선) →
// 부족/과다 2열 카드 → 목적별 카드 → 개인화 카드.
// 모든 산출은 백엔드 책임 — 이 위젯들은 표시만 담당 (mobile/CLAUDE.md).
// 신뢰도는 ConfidenceGradeChip 으로 등급 표기, % 직접 노출 금지.

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../features/supplements/comprehensive_analysis_models.dart';
import '../../utils/design_tokens_v2.dart';
import 'confidence_grade_chip.dart';

/// 식단 점수 링 게이지 + 헤드라인 카드.
///
/// figma C 상단: 작은 마스코트 자리(아이콘) + 링 게이지(식단 점수) +
/// 헤드라인 + 신뢰도 칩.
class DietScoreHeaderCard extends StatelessWidget {
  /// 식단 점수 헤더 카드를 만든다.
  const DietScoreHeaderCard({
    super.key,
    required this.score,
    this.headline,
    this.message,
    this.confidence,
  });

  /// 0~100 식단 점수.
  final double score;

  /// 헤드라인(예: 균형이 잘 잡혔어요).
  final String? headline;

  /// 보조 메시지.
  final String? message;

  /// 점수 신뢰도 (0~1).
  final double? confidence;

  @override
  Widget build(BuildContext context) {
    final double clamped = score.clamp(0, 100).toDouble();
    return Container(
      key: const ValueKey<String>('diet-score-header'),
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside),
      decoration: BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        boxShadow: AppShadow.elev1,
      ),
      child: Row(
        children: <Widget>[
          _ScoreRing(score: clamped),
          const SizedBox(width: AppSpace.lg),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  headline ?? '식단 분석이 끝났어요',
                  style: const TextStyle(
                    color: AppColor.ink,
                    fontSize: 19,
                    fontWeight: FontWeight.w900,
                    height: 1.3,
                    letterSpacing: 0,
                  ),
                ),
                if (message != null && message!.trim().isNotEmpty) ...<Widget>[
                  const SizedBox(height: 6),
                  Text(
                    message!,
                    style: const TextStyle(
                      color: AppColor.inkSecondary,
                      fontSize: 14,
                      height: 1.4,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0,
                    ),
                  ),
                ],
                const SizedBox(height: AppSpace.sm),
                ConfidenceGradeChip(confidence: confidence, compact: true),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ScoreRing extends StatelessWidget {
  const _ScoreRing({required this.score});

  final double score;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 84,
      height: 84,
      child: CustomPaint(
        painter: _ScoreRingPainter(score / 100),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Text(
                score.round().toString(),
                style: const TextStyle(
                  color: AppColor.ink,
                  fontSize: 26,
                  fontWeight: FontWeight.w900,
                  height: 1,
                  letterSpacing: 0,
                ),
              ),
              const Text(
                '점',
                style: TextStyle(
                  color: AppColor.inkTertiary,
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  height: 1.2,
                  letterSpacing: 0,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ScoreRingPainter extends CustomPainter {
  _ScoreRingPainter(this.ratio);

  final double ratio;

  @override
  void paint(Canvas canvas, Size size) {
    final Offset center = Offset(size.width / 2, size.height / 2);
    final double radius = math.min(size.width, size.height) / 2 - 6;
    final Paint track = Paint()
      ..color = AppColor.border
      ..style = PaintingStyle.stroke
      ..strokeWidth = 9
      ..strokeCap = StrokeCap.round;
    canvas.drawCircle(center, radius, track);
    final Paint progress = Paint()
      ..color = AppColor.brand
      ..style = PaintingStyle.stroke
      ..strokeWidth = 9
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi / 2,
      2 * math.pi * ratio.clamp(0, 1),
      false,
      progress,
    );
  }

  @override
  bool shouldRepaint(_ScoreRingPainter oldDelegate) =>
      oldDelegate.ratio != ratio;
}

/// 주의 성분 카드 — figma C 최우선 배치.
///
/// ⚠ 태그 + 성분·사유 + (출처 라인) + 자세히 chevron.
class CautionaryComponentCard extends StatelessWidget {
  /// 주의 성분 카드를 만든다.
  const CautionaryComponentCard({
    super.key,
    required this.components,
    this.onTapDetail,
  });

  /// 표시할 주의 성분 목록.
  final List<ComprehensiveCautionaryComponent> components;

  /// '자세히' 탭 콜백.
  final VoidCallback? onTapDetail;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const ValueKey<String>('cautionary-component-card'),
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpace.cardInside),
      decoration: BoxDecoration(
        color: AppColor.dangerSoft,
        borderRadius: BorderRadius.circular(AppRadius.lg),
        border: Border.all(color: const Color(0xFFF6C9CD)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              const Text('⚠', style: TextStyle(fontSize: 16)),
              const SizedBox(width: AppSpace.sm),
              const Expanded(
                child: Text(
                  '주의 성분',
                  style: TextStyle(
                    color: AppColor.ink,
                    fontSize: 16,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0,
                  ),
                ),
              ),
              if (onTapDetail != null)
                GestureDetector(
                  onTap: onTapDetail,
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      Text(
                        '자세히',
                        style: TextStyle(
                          color: AppColor.danger,
                          fontSize: 13,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 0,
                        ),
                      ),
                      Icon(
                        Icons.chevron_right_rounded,
                        color: AppColor.danger,
                        size: 18,
                      ),
                    ],
                  ),
                ),
            ],
          ),
          for (final ComprehensiveCautionaryComponent component
              in components) ...<Widget>[
            const SizedBox(height: AppSpace.md),
            _CautionaryRow(component: component),
          ],
        ],
      ),
    );
  }
}

class _CautionaryRow extends StatelessWidget {
  const _CautionaryRow({required this.component});

  final ComprehensiveCautionaryComponent component;

  @override
  Widget build(BuildContext context) {
    final String? reason = component.reason?.trim().isEmpty == true
        ? null
        : component.reason;
    final String? message = component.message?.trim().isEmpty == true
        ? null
        : component.message;
    final String? citation = component.sourceCitation?.trim().isEmpty == true
        ? null
        : component.sourceCitation;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          component.component,
          style: const TextStyle(
            color: AppColor.ink,
            fontSize: 15,
            fontWeight: FontWeight.w900,
            height: 1.35,
            letterSpacing: 0,
          ),
        ),
        if (reason != null) ...<Widget>[
          const SizedBox(height: 2),
          Text(
            reason,
            style: const TextStyle(
              color: AppColor.inkSecondary,
              fontSize: 13,
              height: 1.4,
              fontWeight: FontWeight.w600,
              letterSpacing: 0,
            ),
          ),
        ],
        if (message != null) ...<Widget>[
          const SizedBox(height: 2),
          Text(
            message,
            style: const TextStyle(
              color: AppColor.inkSecondary,
              fontSize: 13,
              height: 1.4,
              fontWeight: FontWeight.w600,
              letterSpacing: 0,
            ),
          ),
        ],
        if (citation != null) ...<Widget>[
          const SizedBox(height: 4),
          Text(
            '출처 · $citation',
            style: const TextStyle(
              color: AppColor.inkTertiary,
              fontSize: 12,
              height: 1.35,
              fontWeight: FontWeight.w600,
              letterSpacing: 0,
            ),
          ),
        ],
      ],
    );
  }
}

/// 부족/과다 영양소 2열 카드.
///
/// 각 카드: 영양소명 + 신뢰도 칩 + 권고 1줄 + (출처).
class NutrientInsightGrid extends StatelessWidget {
  /// 부족/과다 영양소 그리드를 만든다.
  const NutrientInsightGrid({
    super.key,
    required this.deficient,
    required this.excessive,
  });

  /// 부족 영양소.
  final List<ComprehensiveDeficientNutrient> deficient;

  /// 과다 섭취 영양소.
  final List<ComprehensiveExcessiveNutrient> excessive;

  @override
  Widget build(BuildContext context) {
    final List<Widget> cards = <Widget>[
      for (final ComprehensiveDeficientNutrient nutrient in deficient)
        _NutrientInsightCard(
          title: nutrient.nutrientName ?? nutrient.nutrientCode,
          tag: '부족',
          tagColor: AppColor.warning,
          recommendation: nutrient.message,
          confidence: nutrient.confidence,
        ),
      for (final ComprehensiveExcessiveNutrient nutrient in excessive)
        _NutrientInsightCard(
          title: nutrient.nutrientName ?? nutrient.nutrientCode,
          tag: '과다',
          tagColor: AppColor.danger,
          recommendation: nutrient.message,
          confidence: nutrient.confidence,
        ),
    ];
    if (cards.isEmpty) return const SizedBox.shrink();
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        const double gap = AppSpace.sm;
        final double cardWidth = (constraints.maxWidth - gap) / 2;
        return Wrap(
          spacing: gap,
          runSpacing: gap,
          children: <Widget>[
            for (final Widget card in cards)
              SizedBox(width: cardWidth, child: card),
          ],
        );
      },
    );
  }
}

class _NutrientInsightCard extends StatelessWidget {
  const _NutrientInsightCard({
    required this.title,
    required this.tag,
    required this.tagColor,
    required this.recommendation,
    required this.confidence,
  });

  final String title;
  final String tag;
  final Color tagColor;
  final String? recommendation;
  final double? confidence;

  @override
  Widget build(BuildContext context) {
    final String? recommendationText =
        recommendation?.trim().isEmpty == true ? null : recommendation;
    return Container(
      padding: const EdgeInsets.all(AppSpace.md),
      decoration: BoxDecoration(
        color: AppColor.surface,
        borderRadius: BorderRadius.circular(AppRadius.md),
        boxShadow: AppShadow.elev1,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: tagColor.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(AppRadius.full),
                ),
                child: Text(
                  tag,
                  style: TextStyle(
                    color: tagColor,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpace.xs),
          Text(
            title,
            style: const TextStyle(
              color: AppColor.ink,
              fontSize: 15,
              fontWeight: FontWeight.w900,
              height: 1.3,
              letterSpacing: 0,
            ),
          ),
          if (recommendationText != null) ...<Widget>[
            const SizedBox(height: 4),
            Text(
              recommendationText,
              style: const TextStyle(
                color: AppColor.inkSecondary,
                fontSize: 13,
                height: 1.4,
                fontWeight: FontWeight.w600,
                letterSpacing: 0,
              ),
            ),
          ],
          const SizedBox(height: AppSpace.sm),
          ConfidenceGradeChip(confidence: confidence, compact: true),
        ],
      ),
    );
  }
}

/// 목적별(만성질환 등) 카드.
class PurposeTargetCard extends StatelessWidget {
  /// 목적별 카드를 만든다.
  const PurposeTargetCard({super.key, required this.targets, this.onTapMore});

  /// 목적별 분석 목록.
  final List<ComprehensivePurposeTarget> targets;

  /// '더 보기' 탭 콜백.
  final VoidCallback? onTapMore;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const ValueKey<String>('purpose-target-card'),
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
                  '목적별 분석',
                  style: TextStyle(
                    color: AppColor.ink,
                    fontSize: 16,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0,
                  ),
                ),
              ),
              if (onTapMore != null)
                GestureDetector(
                  onTap: onTapMore,
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      Text(
                        '더 보기',
                        style: TextStyle(
                          color: AppColor.inkSecondary,
                          fontSize: 13,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 0,
                        ),
                      ),
                      Icon(
                        Icons.chevron_right_rounded,
                        color: AppColor.inkTertiary,
                        size: 18,
                      ),
                    ],
                  ),
                ),
            ],
          ),
          for (final ComprehensivePurposeTarget target in targets) ...<Widget>[
            const SizedBox(height: AppSpace.md),
            _PurposeRow(target: target),
          ],
        ],
      ),
    );
  }
}

class _PurposeRow extends StatelessWidget {
  const _PurposeRow({required this.target});

  final ComprehensivePurposeTarget target;

  @override
  Widget build(BuildContext context) {
    final String? message = target.message?.trim().isEmpty == true
        ? null
        : target.message;
    final String? citation = target.sourceCitation?.trim().isEmpty == true
        ? null
        : target.sourceCitation;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          target.condition,
          style: const TextStyle(
            color: AppColor.ink,
            fontSize: 15,
            fontWeight: FontWeight.w900,
            height: 1.3,
            letterSpacing: 0,
          ),
        ),
        if (message != null) ...<Widget>[
          const SizedBox(height: 2),
          Text(
            message,
            style: const TextStyle(
              color: AppColor.inkSecondary,
              fontSize: 13,
              height: 1.4,
              fontWeight: FontWeight.w600,
              letterSpacing: 0,
            ),
          ),
        ],
        if (citation != null) ...<Widget>[
          const SizedBox(height: 4),
          Text(
            '출처 · $citation',
            style: const TextStyle(
              color: AppColor.inkTertiary,
              fontSize: 12,
              height: 1.35,
              fontWeight: FontWeight.w600,
              letterSpacing: 0,
            ),
          ),
        ],
      ],
    );
  }
}
