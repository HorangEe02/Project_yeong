// widgets/common/output_card.dart — 결과 카드 공통 셸
//
// 참조: mobile/CLAUDE.md §3.4 결과 카드 4 요소 / §6.3 만들 것
// 사용자와 함께 디자인 결정 진행 중 — 마지막 디자인 협의 시점에 다시 손볼 것.
//
// 약속 (CLAUDE.md §3.4):
//   1. 결과 큰 글씨   → headline
//   2. 확신 정도      → confidence (ConfidenceBadge, 0~1 double)
//   3. 출처 · 시간    → source
//   4. 다음 행동      → onTap (chevron)
//
// 좌측 44×44 아이콘 박스 + 본문 Column + 우측 chevron.

import 'package:flutter/material.dart';

import '../../utils/design_tokens_v2.dart';
import 'confidence_badge.dart';

class OutputCard extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color iconBg;
  final Color iconFg;
  final String headline;
  final String detail;
  final String source;

  /// 0~1 정규화 confidence. null 이면 뱃지 미표시.
  final double? confidence;
  final VoidCallback? onTap;

  const OutputCard({
    super.key,
    required this.label,
    required this.icon,
    required this.iconBg,
    required this.iconFg,
    required this.headline,
    required this.detail,
    required this.source,
    this.confidence,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return AppCard(
      onTap: onTap,
      padding: const EdgeInsets.all(AppSpace.lg),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: <Widget>[
          // 좌측 — 44×44 라운드 아이콘
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: iconBg,
              borderRadius: BorderRadius.circular(AppRadius.sm),
            ),
            alignment: Alignment.center,
            child: Icon(icon, size: 22, color: iconFg),
          ),
          const SizedBox(width: AppSpace.md),
          // 중앙 — 라벨 + 확신 / 헤드라인 / 디테일 / 출처
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Row(
                  children: <Widget>[
                    Text(label, style: AppText.micro),
                    if (confidence != null) ...<Widget>[
                      const SizedBox(width: AppSpace.sm),
                      ConfidenceBadge(confidence: confidence),
                    ],
                  ],
                ),
                const SizedBox(height: AppSpace.xs),
                Text(
                  headline,
                  style: AppText.subtitle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  detail,
                  style: AppText.body.copyWith(color: AppColor.inkSecondary),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: AppSpace.xs),
                Text(
                  source,
                  style: AppText.caption.copyWith(color: AppColor.inkTertiary),
                ),
              ],
            ),
          ),
          // 우측 — chevron
          if (onTap != null) ...<Widget>[
            const SizedBox(width: AppSpace.sm),
            const Icon(
              Icons.chevron_right_rounded,
              size: 24,
              color: AppColor.inkTertiary,
            ),
          ],
        ],
      ),
    );
  }
}
