// widgets/common/confidence_grade_chip.dart — 신뢰도 등급 칩
//
// figma 신뢰도 표기 규칙(확정): % 숫자 직접 노출 대신 등급 칩 기본.
//   높음        ≥ 0.85  (success)
//   보통        ≥ 0.6   (warning)
//   직접 확인 필요 그 외   (review) → LowConfidenceBanner 동반 권장
//
// 입력은 0~1 정규화된 double?. null 이면 위젯을 그리지 않음.

import 'package:flutter/material.dart';

import '../../utils/design_tokens_v2.dart';

/// 신뢰도 등급 (높음/보통/직접 확인 필요).
enum ConfidenceGrade {
  /// 신뢰도 높음 (≥ 0.85).
  high('높음'),

  /// 신뢰도 보통 (≥ 0.6).
  medium('보통'),

  /// 직접 확인 필요 (그 외 또는 미상).
  low('직접 확인 필요');

  const ConfidenceGrade(this.label);

  /// 칩에 표시되는 한국어 라벨.
  final String label;

  /// 0~1 정규화 신뢰도를 등급으로 변환한다.
  ///
  /// null 또는 0 미만 값은 [ConfidenceGrade.low] 로 처리한다.
  static ConfidenceGrade fromConfidence(double? confidence) {
    if (confidence == null) return ConfidenceGrade.low;
    if (confidence >= 0.85) return ConfidenceGrade.high;
    if (confidence >= 0.6) return ConfidenceGrade.medium;
    return ConfidenceGrade.low;
  }

  /// 저신뢰(직접 확인 필요)로 LowConfidenceBanner 노출 대상인지 여부.
  bool get isLowConfidence => this == ConfidenceGrade.low;
}

/// 신뢰도 등급 칩.
///
/// % 숫자를 노출하지 않고 등급 라벨만 표시한다.
class ConfidenceGradeChip extends StatelessWidget {
  /// 0~1 정규화 신뢰도. null 이면 직접 확인 필요로 표시한다.
  const ConfidenceGradeChip({super.key, this.confidence, this.compact = false});

  /// 0~1 정규화된 confidence 값.
  final double? confidence;

  /// 좁은 영역(카드 헤더 등)에서 더 작은 패딩을 쓸지 여부.
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final ConfidenceGrade grade = ConfidenceGrade.fromConfidence(confidence);
    final (Color bg, Color fg) = switch (grade) {
      ConfidenceGrade.high => (AppColor.successSoft, AppColor.success),
      ConfidenceGrade.medium => (AppColor.warningSoft, AppColor.review),
      ConfidenceGrade.low => (AppColor.reviewSoft, AppColor.review),
    };
    return Container(
      key: ValueKey<String>('confidence-grade-${grade.name}'),
      padding: EdgeInsets.symmetric(
        horizontal: compact ? AppSpace.sm : AppSpace.md,
        vertical: compact ? 2 : 4,
      ),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(AppRadius.full),
      ),
      child: Text(
        '신뢰도 ${grade.label}',
        style: TextStyle(
          fontFamily: 'Pretendard',
          fontSize: compact ? 11 : 12,
          fontWeight: FontWeight.w700,
          color: fg,
          height: 1.2,
          letterSpacing: 0,
        ),
      ),
    );
  }
}
