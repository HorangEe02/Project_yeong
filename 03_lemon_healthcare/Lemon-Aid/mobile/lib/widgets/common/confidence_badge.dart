// widgets/common/confidence_badge.dart — 확신도 뱃지
//
// 참조: mobile/CLAUDE.md §3.4 결과 카드 4 요소
// 사용자와 함께 디자인 결정 진행 중 — 마지막 디자인 협의 시점에 다시 손볼 것.
//
// 임계값 약속 (CLAUDE.md §3.4):
//   ≥ 0.8       → success  (초록)
//   0.6 ~ 0.8   → warning  (주황)
//   < 0.6       → danger   (검토 권장)
//
// 입력은 0~1 정규화된 double?. null 이면 위젯 자체를 그리지 않음 (SizedBox.shrink).
// "확신 85%" 같이 표시.

import 'package:flutter/material.dart';

import '../../utils/design_tokens_v2.dart';

class ConfidenceBadge extends StatelessWidget {
  /// 0~1 정규화된 confidence. null 이면 위젯 안 그림.
  final double? confidence;

  const ConfidenceBadge({super.key, this.confidence});

  @override
  Widget build(BuildContext context) {
    final double? c = confidence;
    if (c == null) return const SizedBox.shrink();

    final Color bg;
    final Color fg;
    if (c >= 0.8) {
      bg = AppColor.successSoft;
      fg = AppColor.success;
    } else if (c >= 0.6) {
      // warning 옅은 배경은 토큰에 없음 — 옅은 노랑 (yellowSoft) 대체.
      bg = AppColor.yellowSoft;
      fg = AppColor.warning;
    } else {
      bg = AppColor.dangerSoft;
      fg = AppColor.danger;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpace.sm, vertical: 2),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(AppRadius.full),
      ),
      child: Text(
        '확신 ${(c * 100).round()}%',
        style: TextStyle(
          fontFamily: 'Pretendard',
          fontSize: 10,
          fontWeight: FontWeight.w700,
          color: fg,
          height: 1.2,
          letterSpacing: 0,
        ),
      ),
    );
  }
}
