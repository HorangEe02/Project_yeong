// utils/tokens.dart — Lemon Aid 디자인 토큰
//
// ⚠️  DEPRECATED — 이 파일은 폐기 예정입니다.
//
// 단일 출처(SoT v1.1 §9.4): mobile/lib/utils/design_tokens_v2.dart 를 사용하세요.
// 이 파일의 LemonColors.brand 는 블루(#4267EC) 기반으로 현재 브랜드(#FFC700)와 불일치합니다.
// 마이그레이션: import 를 design_tokens_v2.dart 로 교체하고 AppColor.* 로 대응 상수를 매핑.
// 삭제 시기: 모든 import 가 제거된 것을 확인한 뒤 별도 PR에서 삭제 예정.
//
// 담당: B UI/UX (디자인 토큰 D2)
// 참조: PROJECT_GUIDE.md §4.2 UX 원칙 (만성질환자 50대+ 친화)
//        §15.1 B 담당
//
// 원칙:
// - MVP는 라이트 모드 단독 (다크 토큰은 v2)
// - 본문 16px+, 핵심 17~20px (50대 가독성)
// - 터치 영역 최소 48dp
// - 색만으로 구분 X — 텍스트 라벨 병기
// - 의료법 안전 표현 ("진단" "처방" X)

import 'package:flutter/material.dart';

/// Lemon Aid 색상 — 건강의신 톤 (2026-05-11 재정의)
/// 블루 메인 + 레몬 액센트 + 화이트 + 컬러 카드 시스템
/// 디자인 다이어리 §4.4 참조
class LemonColors {
  // ─── Brand (메인 블루) ───
  static const Color brand = Color(0xFF4267EC); // Blue 500 — 메인 CTA
  static const Color brandStrong = Color(0xFF2945C2); // Blue 700 — pressed
  static const Color brandDeep = Color(0xFF1E2E8E); // Blue 900 — 짙은 헤더
  static const Color brandTint = Color(0xFFDBE4FF); // Blue 100 — 선택 chip
  static const Color brandSoft = Color(0xFFEEF2FF); // Blue 50  — 카드 배경

  // ─── Accent (레몬 — 캐릭터·포인트) ───
  static const Color citrus = Color(0xFFFFD93D); // Lemon 300 — 레몬 캐릭터
  static const Color citrusLight = Color(0xFFFFF4C2); // Lemon 100 — 노랑 카드 배경

  // ─── Accent (분홍·연두·연파랑 — 컬러 카드) ───
  static const Color pink = Color(0xFFFFB6C1);
  static const Color pinkLight = Color(0xFFFFE6EA);
  static const Color green = Color(0xFFB8E994);
  static const Color greenLight = Color(0xFFEAF7DA);
  static const Color sky = Color(0xFFA4D8FF);
  static const Color skyLight = Color(0xFFE1F0FF);

  // ─── 배경 ───
  static const Color bg = Color(0xFFFFFFFF); // 화이트 베이스
  static const Color bgPage = Color(0xFFF8F9FB); // Scaffold (살짝 회색)
  static const Color bgElev = Color(0xFFFFFFFF); // 카드·시트

  // ─── 텍스트 (블루 베이스 검정) ───
  static const Color ink = Color(0xFF1A1F2E); // 본문
  static const Color inkSoft = Color(0xFF4A5165); // 부제
  static const Color inkMute = Color(0xFF8B92A4); // 도움말·캡션

  // ─── 라인 ───
  static const Color line = Color(0xFFEEF0F4); // 옅은 구분선
  static const Color lineStrong = Color(0xFFC4C9D4); // 입력 필드

  // ─── 의미 색상 ───
  static const Color success = Color(0xFF16A34A); // 충분
  static const Color warning = Color(0xFFF59E0B); // 부족 (호박색 — 블루와 조화)
  static const Color danger = Color(0xFFDC2626); // 결핍·UL 초과
  static const Color info = Color(0xFF4267EC); // 정보 = brand 재활용

  // ─── Deprecated aliases (마이그레이션 중 호환용) ───
  /// @deprecated brand 사용
  static const Color accent = brand;

  /// @deprecated brandStrong 사용
  static const Color accentStrong = brandStrong;
}

/// 영양소 충족률 5단계 (§8.6 결핍 진단 로직)
enum NutrientLevel {
  deficient, // < 0.35 결핍
  low, // 0.35~0.7 낮음
  adequate, // 0.7~1.3 적정
  excessive, // 1.3~UL 과다
  risky, // > UL 위험
}

extension NutrientLevelColors on NutrientLevel {
  Color get color {
    switch (this) {
      case NutrientLevel.deficient:
        return LemonColors.danger;
      case NutrientLevel.low:
        return LemonColors.warning;
      case NutrientLevel.adequate:
        return LemonColors.success;
      case NutrientLevel.excessive:
        return LemonColors.warning;
      case NutrientLevel.risky:
        return LemonColors.danger;
    }
  }

  String get label {
    switch (this) {
      case NutrientLevel.deficient:
        return '결핍';
      case NutrientLevel.low:
        return '약간 부족';
      case NutrientLevel.adequate:
        return '충분';
      case NutrientLevel.excessive:
        return '많음';
      case NutrientLevel.risky:
        return '주의';
    }
  }
}

/// 폰트 패밀리 (다이어리 §4.5a)
class LemonFont {
  /// 본문·라벨·카드 — Pretendard
  static const String body = 'Pretendard';

  /// 디스플레이·워드마크·큰 숫자 — Gmarket Sans Bold
  /// (assets/fonts/ 배치 전엔 Pretendard로 폴백)
  static const String display = 'GmarketSans';

  /// 영문 본문·외래어 — Plus Jakarta Sans
  static const String latin = 'PlusJakartaSans';
}

/// 타이포그래피 (50대+ 친화 — 본문 16px+, 핵심 17~20px)
/// 폰트 매핑: display/title = Gmarket Sans, 나머지 = Pretendard
class LemonText {
  static const TextStyle display = TextStyle(
    fontFamily: LemonFont.display,
    fontFamilyFallback: [LemonFont.body],
    fontSize: 32,
    fontWeight: FontWeight.w700,
    letterSpacing: 0,
    color: LemonColors.ink,
    height: 1.2,
  );

  static const TextStyle title = TextStyle(
    fontFamily: LemonFont.display,
    fontFamilyFallback: [LemonFont.body],
    fontSize: 24,
    fontWeight: FontWeight.w700,
    letterSpacing: 0,
    color: LemonColors.ink,
    height: 1.3,
  );

  static const TextStyle heading = TextStyle(
    fontFamily: LemonFont.body,
    fontSize: 20,
    fontWeight: FontWeight.w700,
    color: LemonColors.ink,
    height: 1.4,
  );

  static const TextStyle subheading = TextStyle(
    fontFamily: LemonFont.body,
    fontSize: 17,
    fontWeight: FontWeight.w600,
    color: LemonColors.ink,
    height: 1.5,
  );

  /// 본문 (50대 가독성 최우선 — 16px)
  static const TextStyle body = TextStyle(
    fontFamily: LemonFont.body,
    fontSize: 16,
    fontWeight: FontWeight.w400,
    color: LemonColors.ink,
    height: 1.6,
  );

  /// 강조 본문 (분석 결과 핵심 수치)
  static const TextStyle bodyEmphasis = TextStyle(
    fontFamily: LemonFont.body,
    fontFeatures: [FontFeature.tabularFigures()],
    fontSize: 17,
    fontWeight: FontWeight.w700,
    color: LemonColors.ink,
    height: 1.5,
  );

  /// 캡션 (출처·작은 안내)
  static const TextStyle caption = TextStyle(
    fontFamily: LemonFont.body,
    fontSize: 13,
    fontWeight: FontWeight.w400,
    color: LemonColors.inkMute,
    height: 1.5,
  );

  /// 면책 고지 (§19.3 표준 문구) — 조금 더 큰 13.5px
  static const TextStyle disclaimer = TextStyle(
    fontFamily: LemonFont.body,
    fontSize: 13,
    fontWeight: FontWeight.w400,
    color: LemonColors.inkSoft,
    height: 1.6,
  );
}

/// 간격 토큰 (만성질환자 친화 — 충분한 여백)
class LemonSpace {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 16;
  static const double lg = 24;
  static const double xl = 32;
  static const double xxl = 48;

  /// 터치 영역 최소 (Material 가이드라인 48dp)
  static const double touchTarget = 48;
}

/// 둥근 모서리
class LemonRadius {
  static const double sm = 6;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 24;
  static const double pill = 999;
}

/// 그림자 토큰 (5단 — 다이어리 §4.8)
/// 50대 친화: 그림자 약하게. 너무 진하면 잡티처럼 보임.
class LemonShadow {
  static const Color _ink = Color(0xFF1A1F2E);

  static const List<BoxShadow> none = <BoxShadow>[];

  static List<BoxShadow> get sm => [
    BoxShadow(
      color: _ink.withValues(alpha: 0.04),
      blurRadius: 2,
      offset: const Offset(0, 1),
    ),
  ];

  static List<BoxShadow> get md => [
    BoxShadow(
      color: _ink.withValues(alpha: 0.08),
      blurRadius: 12,
      offset: const Offset(0, 4),
    ),
  ];

  static List<BoxShadow> get lg => [
    BoxShadow(
      color: _ink.withValues(alpha: 0.12),
      blurRadius: 24,
      offset: const Offset(0, 8),
    ),
  ];

  static List<BoxShadow> get xl => [
    BoxShadow(
      color: _ink.withValues(alpha: 0.16),
      blurRadius: 48,
      offset: const Offset(0, 16),
    ),
  ];
}

/// 모션 토큰 (5단 — 다이어리 §4.9)
/// reduceMotion 활성화 시 모두 0ms로 강제 (utils/a11y.dart에서 체크)
class LemonMotion {
  static const Duration fast = Duration(milliseconds: 80);
  static const Duration base = Duration(milliseconds: 200);
  static const Duration slow = Duration(milliseconds: 320);
  static const Duration entry = Duration(milliseconds: 400);
  static const Duration exit = Duration(milliseconds: 160);

  static const Curve curveDefault = Curves.easeInOut;
  static const Curve curvePress = Curves.easeOut;
  static const Curve curveEntry = Cubic(0.2, 0, 0, 1);
  static const Curve curveExit = Curves.easeIn;
}

/// 고령자 모드 타입 변종 (다이어리 §4.5 — Settings 토글 ON 시 사용)
/// 사용처: 본문 16 → 19, 캐션 13 → 15, 터치 48 → 56 등
class LemonTextElder {
  static const TextStyle body = TextStyle(
    fontSize: 19,
    fontWeight: FontWeight.w400,
    color: LemonColors.ink,
    height: 1.7,
  );

  static const TextStyle bodyEmphasis = TextStyle(
    fontSize: 20,
    fontWeight: FontWeight.w700,
    color: LemonColors.ink,
    height: 1.6,
  );

  static const TextStyle subheading = TextStyle(
    fontSize: 20,
    fontWeight: FontWeight.w600,
    color: LemonColors.ink,
    height: 1.5,
  );

  static const TextStyle caption = TextStyle(
    fontSize: 15,
    fontWeight: FontWeight.w400,
    color: LemonColors.inkMute,
    height: 1.6,
  );
}

/// 고령자 모드 간격 — Settings 토글 ON 시 사용
/// 다이어리 §14.6 Figma 시안 정렬 (2026-05-11)
class LemonSpaceElder {
  static const double touchTarget = 60; // 56 → 60 (Figma 시안 일치)
  static const double minButtonHeight = 60;
  static const double iconSize = 22; // 기본 20 → 고령자 22
  static const double fontSizeButton = 18; // 기본 16 → 고령자 18
}

/// ThemeData 만들기 (MVP 라이트 단독)
ThemeData buildLemonTheme() {
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    colorScheme: const ColorScheme.light(
      primary: LemonColors.brand,
      onPrimary: Colors.white,
      secondary: LemonColors.citrus,
      onSecondary: LemonColors.ink,
      surface: LemonColors.bgElev,
      onSurface: LemonColors.ink,
      error: LemonColors.danger,
      onError: Colors.white,
    ),
    scaffoldBackgroundColor: LemonColors.bgPage,
    fontFamily: LemonFont
        .body, // 전체 기본 = Pretendard (display/title만 LemonText에서 override)
    // 본문 타이포 (50대+ 친화)
    textTheme: const TextTheme(
      displayLarge: LemonText.display,
      titleLarge: LemonText.title,
      headlineSmall: LemonText.heading,
      titleMedium: LemonText.subheading,
      bodyLarge: LemonText.bodyEmphasis,
      bodyMedium: LemonText.body,
      bodySmall: LemonText.caption,
    ),

    // 버튼 (터치 영역 48dp+)
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: LemonColors.brand,
        foregroundColor: Colors.white,
        minimumSize: const Size(double.infinity, LemonSpace.touchTarget),
        padding: const EdgeInsets.symmetric(
          horizontal: LemonSpace.lg,
          vertical: LemonSpace.md,
        ),
        textStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(LemonRadius.md),
        ),
      ),
    ),

    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: LemonColors.brand,
        minimumSize: const Size(double.infinity, LemonSpace.touchTarget),
        side: const BorderSide(color: LemonColors.brand, width: 1.5),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(LemonRadius.md),
        ),
      ),
    ),

    // 입력 필드 (큰 터치·큰 글씨)
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: LemonColors.bgElev,
      contentPadding: const EdgeInsets.symmetric(
        horizontal: LemonSpace.md,
        vertical: LemonSpace.md,
      ),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(LemonRadius.md),
        borderSide: const BorderSide(color: LemonColors.lineStrong),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(LemonRadius.md),
        borderSide: const BorderSide(color: LemonColors.brand, width: 2),
      ),
      labelStyle: LemonText.body,
      hintStyle: LemonText.body.copyWith(color: LemonColors.inkMute),
    ),

    // 앱바
    appBarTheme: const AppBarTheme(
      backgroundColor: LemonColors.bgPage,
      foregroundColor: LemonColors.ink,
      elevation: 0,
      scrolledUnderElevation: 1,
      centerTitle: false,
      titleTextStyle: LemonText.heading,
    ),

    // 카드
    cardTheme: CardThemeData(
      color: LemonColors.bgElev,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(LemonRadius.lg),
        side: const BorderSide(color: LemonColors.line),
      ),
      margin: const EdgeInsets.symmetric(
        horizontal: LemonSpace.md,
        vertical: LemonSpace.sm,
      ),
    ),

    // Chip (필터·선택)
    chipTheme: ChipThemeData(
      backgroundColor: LemonColors.bgElev,
      selectedColor: LemonColors.brandTint,
      disabledColor: LemonColors.line,
      labelStyle: LemonText.body.copyWith(fontSize: 15),
      secondaryLabelStyle: LemonText.body.copyWith(
        fontSize: 15,
        color: LemonColors.brandStrong,
        fontWeight: FontWeight.w600,
      ),
      padding: const EdgeInsets.symmetric(
        horizontal: LemonSpace.md,
        vertical: LemonSpace.sm,
      ),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(LemonRadius.pill),
        side: const BorderSide(color: LemonColors.line, width: 1),
      ),
      side: const BorderSide(color: LemonColors.line),
    ),

    // Bottom Navigation (건강의신 5탭 — 홈/건강/챗봇/응모권/설정)
    bottomNavigationBarTheme: const BottomNavigationBarThemeData(
      type: BottomNavigationBarType.fixed,
      backgroundColor: LemonColors.bgElev,
      selectedItemColor: LemonColors.brand,
      unselectedItemColor: LemonColors.inkMute,
      selectedLabelStyle: TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
      unselectedLabelStyle: TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w400,
      ),
      elevation: 8,
    ),

    // FAB (Camera 진입 — 응모권 적립)
    floatingActionButtonTheme: const FloatingActionButtonThemeData(
      backgroundColor: LemonColors.brand,
      foregroundColor: Colors.white,
      elevation: 4,
      shape: CircleBorder(),
    ),

    // Dialog
    dialogTheme: DialogThemeData(
      backgroundColor: LemonColors.bgElev,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(LemonRadius.xl),
      ),
      titleTextStyle: LemonText.heading,
      contentTextStyle: LemonText.body,
    ),

    // BottomSheet
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: LemonColors.bgElev,
      elevation: 0,
      modalElevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(LemonRadius.xl),
        ),
      ),
      showDragHandle: true,
      dragHandleColor: LemonColors.lineStrong,
    ),

    // Snackbar (명시 닫기 — 만성질환자 인지 부담 낮춤)
    snackBarTheme: SnackBarThemeData(
      backgroundColor: LemonColors.ink,
      contentTextStyle: LemonText.body.copyWith(color: Colors.white),
      actionTextColor: LemonColors.citrus,
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(LemonRadius.md),
      ),
      elevation: 4,
    ),

    // Divider
    dividerTheme: const DividerThemeData(
      color: LemonColors.line,
      thickness: 1,
      space: 1,
    ),

    // Switch (Settings 고령자 모드 토글)
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) return Colors.white;
        return LemonColors.bgElev;
      }),
      trackColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) return LemonColors.brand;
        return LemonColors.lineStrong;
      }),
    ),
  );
}
