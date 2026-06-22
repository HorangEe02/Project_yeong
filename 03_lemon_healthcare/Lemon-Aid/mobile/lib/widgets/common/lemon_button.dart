// widgets/common/lemon_button.dart — Lemon Aid 공통 버튼
//
// Figma export ZIP (LoginButtons.tsx) 1:1 변환:
//   - Tailwind w-[342px] rounded-[12px] h-[52px] px-6 gap-2
//   - flex items-center justify-center (가운데 정렬)
//   - cursor-pointer select-none (Material InkWell 대신 GestureDetector)
//   - font-bold 16/700, color은 variant마다 다름
//
// Variant 12종 — 다이어리 §14.6 표 정확 일치
// Elder Mode: height 60, fontSize 18, iconSize 22 (다이어리 §14.6 Elderly)

import 'package:flutter/material.dart';
import '../../utils/tokens.dart';

enum LemonButtonVariant {
  primary,
  secondary,
  ghost,
  danger,
  kakao,
  google,
  apple,
}

class LemonButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final LemonButtonVariant variant;
  final bool loading;
  final bool fullWidth;
  final Widget? leading;
  final double? height;
  final bool elderMode;

  const LemonButton({
    super.key,
    required this.label,
    this.onPressed,
    this.variant = LemonButtonVariant.primary,
    this.loading = false,
    this.fullWidth = true,
    this.leading,
    this.height,
    this.elderMode = false,
  });

  const LemonButton.primary({
    super.key,
    required this.label,
    this.onPressed,
    this.loading = false,
    this.fullWidth = true,
    this.leading,
    this.height,
    this.elderMode = false,
  }) : variant = LemonButtonVariant.primary;

  const LemonButton.secondary({
    super.key,
    required this.label,
    this.onPressed,
    this.loading = false,
    this.fullWidth = true,
    this.leading,
    this.height,
    this.elderMode = false,
  }) : variant = LemonButtonVariant.secondary;

  const LemonButton.ghost({
    super.key,
    required this.label,
    this.onPressed,
    this.loading = false,
    this.fullWidth = true,
    this.leading,
    this.height,
    this.elderMode = false,
  }) : variant = LemonButtonVariant.ghost;

  const LemonButton.danger({
    super.key,
    required this.label,
    this.onPressed,
    this.loading = false,
    this.fullWidth = true,
    this.leading,
    this.height,
    this.elderMode = false,
  }) : variant = LemonButtonVariant.danger;

  const LemonButton.kakao({
    super.key,
    required this.label,
    this.onPressed,
    this.loading = false,
    this.fullWidth = true,
    this.leading,
    this.height,
    this.elderMode = false,
  }) : variant = LemonButtonVariant.kakao;

  const LemonButton.google({
    super.key,
    required this.label,
    this.onPressed,
    this.loading = false,
    this.fullWidth = true,
    this.leading,
    this.height,
    this.elderMode = false,
  }) : variant = LemonButtonVariant.google;

  const LemonButton.apple({
    super.key,
    required this.label,
    this.onPressed,
    this.loading = false,
    this.fullWidth = true,
    this.leading,
    this.height,
    this.elderMode = false,
  }) : variant = LemonButtonVariant.apple;

  @override
  Widget build(BuildContext context) {
    final isDisabled = onPressed == null || loading;
    final colors = _resolveColors(isDisabled);
    final h = height ?? (elderMode ? 60.0 : 52.0);
    final fontSize = elderMode ? 18.0 : 16.0;
    final spinnerSize = elderMode ? 22.0 : 20.0;

    // Figma: gap-2 = 8px / px-6 = 24px / rounded-[12px]
    final content = Row(
      mainAxisAlignment: MainAxisAlignment.center,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (loading) ...[
          SizedBox(
            width: spinnerSize,
            height: spinnerSize,
            child: CircularProgressIndicator(
              strokeWidth: 2.2,
              color: colors.fg,
            ),
          ),
          const SizedBox(width: 8),
        ] else if (leading != null) ...[
          leading!,
          const SizedBox(width: 8),
        ],
        Text(
          label,
          style: TextStyle(
            fontFamily: LemonFont.body,
            fontSize: fontSize,
            fontWeight: FontWeight.w700,
            color: colors.fg,
            letterSpacing: 0,
            height: 1.0,
          ),
        ),
      ],
    );

    final button = Container(
      width: fullWidth ? double.infinity : null,
      height: h,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      decoration: BoxDecoration(
        color: colors.bg,
        borderRadius: BorderRadius.circular(LemonRadius.md),
        border: colors.border != null
            ? Border.all(color: colors.border!, width: 1.5)
            : null,
      ),
      alignment: Alignment.center,
      child: content,
    );

    if (isDisabled) {
      return Opacity(
        opacity: variant == LemonButtonVariant.kakao && loading ? 0.9 : 1.0,
        child: button,
      );
    }

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onPressed,
        borderRadius: BorderRadius.circular(LemonRadius.md),
        splashColor: colors.fg.withValues(alpha: 0.08),
        highlightColor: colors.fg.withValues(alpha: 0.04),
        child: button,
      ),
    );
  }

  _BtnColors _resolveColors(bool isDisabled) {
    if (isDisabled && variant == LemonButtonVariant.primary) {
      // Email Primary Disabled (Figma): bg #EEF0F4, fg #8B92A4
      return _BtnColors(bg: LemonColors.line, fg: LemonColors.inkMute);
    }

    switch (variant) {
      case LemonButtonVariant.primary:
        return _BtnColors(bg: LemonColors.brand, fg: Colors.white);
      case LemonButtonVariant.secondary:
        return _BtnColors(
          bg: LemonColors.bgElev,
          fg: LemonColors.brand,
          border: LemonColors.brand,
        );
      case LemonButtonVariant.ghost:
        return _BtnColors(bg: Colors.transparent, fg: LemonColors.brand);
      case LemonButtonVariant.danger:
        return _BtnColors(bg: LemonColors.danger, fg: Colors.white);
      case LemonButtonVariant.kakao:
        return _BtnColors(
          bg: const Color(0xFFFEE500),
          fg: const Color(0xFF191919),
        );
      case LemonButtonVariant.google:
        return _BtnColors(
          bg: Colors.white,
          fg: const Color(0xFF1F1F1F),
          border: const Color(0xFFDADCE0),
        );
      case LemonButtonVariant.apple:
        // Apple 공식: 검정 배경 + 흰 텍스트
        return _BtnColors(bg: const Color(0xFF000000), fg: Colors.white);
    }
  }
}

class _BtnColors {
  final Color bg;
  final Color fg;
  final Color? border;
  _BtnColors({required this.bg, required this.fg, this.border});
}
