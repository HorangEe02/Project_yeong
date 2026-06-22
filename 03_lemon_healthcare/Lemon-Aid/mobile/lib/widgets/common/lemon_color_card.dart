// widgets/common/lemon_color_card.dart — 5컬러 카드 시스템
//
// 다이어리 §4.4 컬러 카드 시스템:
//   Lemon / Sky / Pink / Green / Blue
//
// 사용:
//   LemonColorCard.blue(child: ...) // 메인 액션
//   LemonColorCard.lemon(child: ..., accent: true) // 강조

import 'package:flutter/material.dart';
import '../../utils/tokens.dart';

enum LemonCardVariant { blue, lemon, sky, pink, green, plain }

class LemonColorCard extends StatelessWidget {
  final Widget child;
  final LemonCardVariant variant;
  final EdgeInsetsGeometry padding;
  final double radius;
  final VoidCallback? onTap;
  final bool showAccentBar; // 좌측 4dp 액센트 바
  final List<BoxShadow>? customShadow;

  const LemonColorCard({
    super.key,
    required this.child,
    this.variant = LemonCardVariant.plain,
    this.padding = const EdgeInsets.all(16),
    this.radius = LemonRadius.lg,
    this.onTap,
    this.showAccentBar = false,
    this.customShadow,
  });

  const LemonColorCard.blue({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.radius = LemonRadius.lg,
    this.onTap,
    this.showAccentBar = false,
    this.customShadow,
  }) : variant = LemonCardVariant.blue;

  const LemonColorCard.lemon({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.radius = LemonRadius.lg,
    this.onTap,
    this.showAccentBar = false,
    this.customShadow,
  }) : variant = LemonCardVariant.lemon;

  const LemonColorCard.sky({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.radius = LemonRadius.lg,
    this.onTap,
    this.showAccentBar = false,
    this.customShadow,
  }) : variant = LemonCardVariant.sky;

  const LemonColorCard.pink({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.radius = LemonRadius.lg,
    this.onTap,
    this.showAccentBar = false,
    this.customShadow,
  }) : variant = LemonCardVariant.pink;

  const LemonColorCard.green({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.radius = LemonRadius.lg,
    this.onTap,
    this.showAccentBar = false,
    this.customShadow,
  }) : variant = LemonCardVariant.green;

  const LemonColorCard.plain({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.radius = LemonRadius.lg,
    this.onTap,
    this.showAccentBar = false,
    this.customShadow,
  }) : variant = LemonCardVariant.plain;

  @override
  Widget build(BuildContext context) {
    final colors = _resolveColors();
    final container = Container(
      padding: padding,
      decoration: BoxDecoration(
        color: colors.bg,
        borderRadius: BorderRadius.circular(radius),
        boxShadow: customShadow ?? LemonShadow.sm,
        border: variant == LemonCardVariant.plain
            ? Border.all(color: LemonColors.line)
            : null,
      ),
      child: showAccentBar
          ? Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Container(
                  width: 4,
                  decoration: BoxDecoration(
                    color: colors.accent,
                    borderRadius: BorderRadius.circular(LemonRadius.sm),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(child: child),
              ],
            )
          : child,
    );

    if (onTap == null) return container;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(radius),
        child: container,
      ),
    );
  }

  _CardColors _resolveColors() {
    switch (variant) {
      case LemonCardVariant.blue:
        return _CardColors(
          bg: LemonColors.brandSoft,
          accent: LemonColors.brand,
        );
      case LemonCardVariant.lemon:
        return _CardColors(
          bg: LemonColors.citrusLight,
          accent: LemonColors.citrus,
        );
      case LemonCardVariant.sky:
        return _CardColors(bg: LemonColors.skyLight, accent: LemonColors.sky);
      case LemonCardVariant.pink:
        return _CardColors(bg: LemonColors.pinkLight, accent: LemonColors.pink);
      case LemonCardVariant.green:
        return _CardColors(
          bg: LemonColors.greenLight,
          accent: LemonColors.green,
        );
      case LemonCardVariant.plain:
        return _CardColors(bg: LemonColors.bgElev, accent: LemonColors.line);
    }
  }
}

class _CardColors {
  final Color bg;
  final Color accent;
  _CardColors({required this.bg, required this.accent});
}
