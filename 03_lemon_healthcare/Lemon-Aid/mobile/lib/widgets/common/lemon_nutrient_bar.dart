// widgets/common/lemon_nutrient_bar.dart — 영양소 5단계 라벨+색 바
//
// 다이어리 §14.6 NutrientBar 명세:
//   5단계 (deficient/low/adequate/excessive/risky)
//   바 12dp / 라벨 우측 / 수치 좌측 / 색맹 대응 라벨 병기

import 'package:flutter/material.dart';
import '../../utils/tokens.dart';

class LemonNutrientBar extends StatelessWidget {
  final String name; // 예: "단백질"
  final double percent; // 0.0 ~ 1.5+ (1.0 = 권장량 100%)
  final NutrientLevel level;
  final String? unit; // 예: "g"
  final double? value; // 예: 72.5
  final double? recommended; // 예: 65

  const LemonNutrientBar({
    super.key,
    required this.name,
    required this.percent,
    required this.level,
    this.unit,
    this.value,
    this.recommended,
  });

  @override
  Widget build(BuildContext context) {
    final color = level.color;
    final clampedRatio = percent.clamp(0.0, 1.5) / 1.5;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                name,
                style: LemonText.body.copyWith(fontWeight: FontWeight.w600),
              ),
            ),
            if (value != null) ...[
              Text(
                value!.toStringAsFixed(value! >= 100 ? 0 : 1),
                style: LemonText.bodyEmphasis,
              ),
              if (unit != null)
                Text(
                  unit!,
                  style: LemonText.caption.copyWith(
                    color: LemonColors.inkMute,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              const SizedBox(width: 8),
            ],
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(LemonRadius.sm),
              ),
              child: Text(
                level.label,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: color,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(LemonRadius.pill),
          child: Stack(
            children: [
              Container(height: 12, color: LemonColors.line),
              FractionallySizedBox(
                widthFactor: clampedRatio,
                child: Container(height: 12, color: color),
              ),
              // 권장량 100% 마커
              Positioned(
                left: MediaQuery.of(context).size.width * 0.5 - 32, // 대략 중앙
                child: Container(
                  width: 2,
                  height: 12,
                  color: LemonColors.ink.withValues(alpha: 0.3),
                ),
              ),
            ],
          ),
        ),
        if (recommended != null && value != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(
              '권장 ${recommended!.toStringAsFixed(0)}${unit ?? ''} · ${(percent * 100).toStringAsFixed(0)}%',
              style: LemonText.caption.copyWith(color: LemonColors.inkMute),
            ),
          ),
      ],
    );
  }
}
