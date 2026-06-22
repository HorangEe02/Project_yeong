// shared/theme/lemon_design_tokens.dart — Lemon Aid 전역 ThemeData
//
// SoT v1.1 §9.4: 전역 ThemeData 단일 출처.
// design_tokens_v2 (AppColor / LADS v2) 값을 기반으로 빌드.
//
// 변경 이력:
//   2026-06-10: v2 리베이스 — scaffoldBackground=AppColor.bg(#FFFFFF),
//               primary=AppColor.brand(#FFC700), ink=#191F28.
//               기존 웜톤 canvas/leaf-seed 폐기.
//               4색 브랜드 테마 지원을 위해 buildLemonAidTheme() 에
//               선택적 brandColor 파라미터 추가.
//
// 공개 API (app.dart 등 호환 유지):
//   buildLemonAidTheme([Color? brandColor])  — 기존 시그니처 + 옵션 파라미터
//   LemonColors                              — 참조용 유지 (내부 alias)
//   LemonSpacing / LemonRadius / LemonAssets — 유지

import 'package:flutter/material.dart';

// design_tokens_v2 색상 상수 (직접 inlining — import 순환 방지).
// 출처: mobile/lib/utils/design_tokens_v2.dart AppColor
const Color _brand = Color(0xFFFFC700); // AppColor.brand
const Color _bg = Color(0xFFFFFFFF); // AppColor.bg
const Color _ink = Color(0xFF191F28); // AppColor.ink
const Color _inkSecondary = Color(0xFF4E5968); // AppColor.inkSecondary
const Color _border = Color(0xFFEEF1F6); // AppColor.border

/// Reusable design tokens — Lemon Aid LADS v2 기반.
///
/// 외부에서 LemonColors.* 를 참조하는 코드와의 하위 호환을 위해 유지.
/// 신규 코드는 design_tokens_v2.dart 의 AppColor / AppText 등을 직접 사용.
final class LemonColors {
  LemonColors._();

  /// Primary brand color — AppColor.brand (#FFC700).
  static const Color lemon = _brand;

  /// Deep lemon shade for text on pale yellow surfaces.
  static const Color lemonDeep = Color(0xFFC99100); // AppColor.brandDeep

  /// App canvas (흰 배경) — AppColor.bg.
  static const Color canvas = _bg;

  /// Card surface — AppColor.surface.
  static const Color paper = _bg;

  /// Primary text color — AppColor.ink.
  static const Color ink = _ink;

  /// Secondary text color — AppColor.inkSecondary.
  static const Color inkSoft = _inkSecondary;

  /// Divider and border color — AppColor.border.
  static const Color border = _border;

  /// Success accent — AppColor.success.
  static const Color leaf = Color(0xFF22B07D);

  /// Data and trust accent — AppColor.info.
  static const Color sky = Color(0xFF2CA8E0);

  /// Review state color — AppColor.review.
  static const Color review = Color(0xFFB86A00);
}

/// Shared spacing constants.
final class LemonSpacing {
  LemonSpacing._();

  /// Compact spacing.
  static const double xs = 4;

  /// Small spacing.
  static const double sm = 8;

  /// Standard spacing.
  static const double md = 12;

  /// Page and card spacing.
  static const double lg = 16;

  /// Section spacing.
  static const double xl = 24;
}

/// Shared radius constants.
final class LemonRadius {
  LemonRadius._();

  /// Small control radius.
  static const double sm = 8;

  /// Standard control radius.
  static const double md = 14;

  /// Card radius.
  static const double lg = 20;

  /// Pill radius.
  static const double pill = 999;
}

/// Imported asset paths used by the current mobile app.
final class LemonAssets {
  LemonAssets._();

  /// Friendly mascot pose for dashboard and onboarding-like surfaces.
  static const String mascotHello = 'assets/mascot/poses/hello.png';

  /// Working mascot pose for OCR analysis surfaces.
  static const String mascotWorking = 'assets/mascot/poses/working.png';

  /// Fresh mascot pose for success states.
  static const String mascotFresh = 'assets/mascot/poses/fresh.png';
}

/// Builds the global app theme based on LADS v2 design tokens.
///
/// [brandColor] is optional — when provided (e.g. from [brandThemeProvider]),
/// the ThemeData colorScheme.primary will reflect the user-selected brand.
/// When null, defaults to AppColor.brand (#FFC700).
///
/// NOTE: Screens that reference the static AppColor.brand constant directly
/// (from design_tokens_v2.dart) will NOT respond to brandColor changes.
/// TODO(migrate): Replace AppColor.brand usages with
///   Theme.of(context).colorScheme.primary for full dynamic brand support.
ThemeData buildLemonAidTheme([Color? brandColor]) {
  final Color effectiveBrand = brandColor ?? _brand;

  final ColorScheme colorScheme = ColorScheme.fromSeed(
    seedColor: effectiveBrand,
    primary: effectiveBrand,
    onPrimary: _ink,
    surface: _bg,
    onSurface: _ink,
  );

  return ThemeData(
    colorScheme: colorScheme,
    scaffoldBackgroundColor: _bg,
    fontFamily: 'Pretendard',
    useMaterial3: true,
    appBarTheme: const AppBarTheme(
      backgroundColor: _bg,
      foregroundColor: _ink,
      centerTitle: false,
      elevation: 0,
      titleTextStyle: TextStyle(
        color: _ink,
        fontFamily: 'AtoZ',
        fontSize: 24,
        fontWeight: FontWeight.w800,
        letterSpacing: 0,
      ),
    ),
    cardTheme: CardThemeData(
      color: _bg,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(LemonRadius.lg),
        side: const BorderSide(color: _border),
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: _bg,
      indicatorColor: effectiveBrand.withValues(alpha: 0.28),
      labelTextStyle: WidgetStateProperty.resolveWith<TextStyle>(
        (Set<WidgetState> states) {
          return TextStyle(
            color: states.contains(WidgetState.selected)
                ? _ink
                : _inkSecondary,
            fontWeight: states.contains(WidgetState.selected)
                ? FontWeight.w700
                : FontWeight.w500,
            fontSize: 12,
            letterSpacing: 0,
          );
        },
      ),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: effectiveBrand,
        foregroundColor: _ink,
      ),
    ),
  );
}
