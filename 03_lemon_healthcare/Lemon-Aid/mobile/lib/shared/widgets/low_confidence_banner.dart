// shared/widgets/low_confidence_banner.dart — 저신뢰 경고 배너
//
// warningSoft 배경 라운드 배너.
// 표시 임계 판단은 호출부 책임 — 이 위젯은 표시만 담당.
//
// 사용:
//   if (confidence < 0.6)
//     const LowConfidenceBanner()

import 'package:flutter/material.dart';

import '../../utils/design_tokens_v2.dart';

/// 저신뢰(AI 확실하지 않음) 경고 배너.
///
/// 표시 여부 결정은 호출부에서 처리한다.
/// 이 위젯은 항상 배너를 렌더링한다.
class LowConfidenceBanner extends StatelessWidget {
  const LowConfidenceBanner({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpace.lg,
        vertical: AppSpace.md,
      ),
      decoration: BoxDecoration(
        color: AppColor.warningSoft,
        borderRadius: BorderRadius.circular(AppRadius.sm),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Padding(
            padding: EdgeInsets.only(top: 1),
            child: Text(
              '⚠',
              style: TextStyle(
                fontSize: 14,
                height: 1.4,
              ),
            ),
          ),
          const SizedBox(width: AppSpace.sm),
          Expanded(
            child: RichText(
              text: const TextSpan(
                children: <InlineSpan>[
                  TextSpan(
                    text: 'AI가 확실하지 않아요',
                    style: TextStyle(
                      fontFamily: 'Pretendard',
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: AppColor.ink,
                      height: 1.4,
                    ),
                  ),
                  TextSpan(
                    text:
                        '\n신뢰도가 낮아 결과가 정확하지 않을 수 있어요. 직접 확인하거나 다시 촬영해 주세요.',
                    style: TextStyle(
                      fontFamily: 'Pretendard',
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                      color: AppColor.inkSecondary,
                      height: 1.4,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
