/// 의료법 면책 고지 위젯 — 모든 권고 화면 하단 필수 (mobile/CLAUDE.md Rule 1).
///
/// 본문 텍스트는 [DisclaimerStrings] 에서 가져온다. 백엔드 ``safety/disclaimer.py``
/// 와 1:1 동기 (변경 시 양쪽 갱신).
library;

import 'package:flutter/material.dart';

/// 면책 유형.
///
/// Reference:
///   docs/10-compliance-checklist.md §2.3
enum DisclaimerVariant {
  /// 메인 — 영양·운동·목적별 분석 등 모든 권고 화면.
  main(DisclaimerStrings.mainKo),

  /// 영양제 등록 결과 화면.
  supplement(DisclaimerStrings.supplementKo),

  /// 체중 예측 화면 (트랙 D 스코프 외 — 후속 대시보드에서 사용).
  weightPrediction(DisclaimerStrings.weightPredictionKo);

  const DisclaimerVariant(this.text);
  final String text;
}

class MedicalDisclaimer extends StatelessWidget {
  const MedicalDisclaimer({
    super.key,
    this.variant = DisclaimerVariant.main,
  });

  final DisclaimerVariant variant;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    return Semantics(
      label: '의료 면책 고지',
      container: true,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: theme.colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Icon(
              Icons.info_outline,
              size: 22,
              color: theme.colorScheme.onSurfaceVariant,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                variant.text,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 백엔드 ``safety/disclaimer.py`` 의 한국어 본문과 1:1 동기.
abstract class DisclaimerStrings {
  static const String mainKo =
      '본 서비스에서 제공하는 정보는 일반적인 건강 관리를 위한 참고 자료이며, '
      '의사·약사·영양사의 전문적 판단을 대체하지 않습니다. 증상이 있거나 만성질환을 '
      '앓고 계신 경우, 반드시 전문가와 상담하시기 바랍니다.';

  static const String supplementKo =
      '영양제는 의약품이 아니며, 질병의 예방이나 효과를 보장하지 않습니다. 약을 '
      '복용 중이신 경우, 영양제와의 상호작용에 대해 의료진과 상담하세요.';

  static const String weightPredictionKo =
      '체중 변화 예측은 평균적인 수치를 바탕으로 산출되며, 개인의 대사·체질·'
      '생활습관에 따라 결과가 달라질 수 있습니다. 급격한 체중 변화는 건강에 '
      '해로울 수 있으니 의료진과 상담하세요.';

  static const String consultProfessionalKo =
      '섭취 가능 여부와 복용 시점은 약사 또는 의료진과 상담하시기 바랍니다.';
}
