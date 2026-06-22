// utils/design_tokens_v3.dart — Lemon Aid Design System v3.0 (LADS)
//
// ⚠️  DEPRECATED — 이 파일은 폐기 예정입니다.
//
// 단일 출처(SoT v1.1 §9.4): mobile/lib/utils/design_tokens_v2.dart 를 사용하세요.
// 이 파일의 AppColor / AppText / AppRadius / AppSpacing / AppShadow 클래스는
// design_tokens_v3 전용 네이밍(예: AppColor.lemon400, AppSpacing.s24)을 사용하며
// design_tokens_v2 와 상충됩니다.
// 삭제 시기: 모든 import 가 제거된 것을 확인한 뒤 별도 PR에서 삭제 예정.
//
// §13 매니페스토: colors_and_type.css 단일 진실의 미러
// 원본: mobile/assets/design_system/colors_and_type.css
//
// liquid-glass + 레몬 옐로우 + 따뜻한 canvas
// Pillyze/Toss 모방 X. 차별화: 만성질환자 + 마스코트 + 의료 컴플라이언스
//
// 사용:
//   import '../utils/design_tokens_v3.dart' as ds;
//   Container(color: ds.AppColor.lemon400, ...)
//
import 'package:flutter/material.dart';
import 'dart:ui';

// ============================================================================
// COLORS — Brand + Neutrals + Semantic
// ============================================================================
class AppColor {
  // Lemon (Primary CTA / 브랜드)
  static const Color lemon50 = Color(0xFFFFFEF2); // warm white BG
  static const Color lemon100 = Color(0xFFFFF8C7); // primary container
  static const Color lemon200 = Color(0xFFFFEE7A); // shell highlight
  static const Color lemon300 = Color(0xFFFFDE3F); // midtone
  static const Color lemon400 = Color(0xFFFFCE00); // ★ PRIMARY BRAND
  static const Color lemon500 = Color(0xFFF0B800); // deep shadow
  static const Color lemon600 = Color(0xFFC99100); // text on lemon

  // Leaf (Secondary / Success / Growth)
  static const Color leaf50 = Color(0xFFECFBEE);
  static const Color leaf100 = Color(0xFFC9F2D0);
  static const Color leaf200 = Color(0xFF94E2A2);
  static const Color leaf300 = Color(0xFF6FCB73); // ★ SECONDARY
  static const Color leaf400 = Color(0xFF4FB964);
  static const Color leaf500 = Color(0xFF2EA354);
  static const Color leaf600 = Color(0xFF1F8A4A); // ★ SUCCESS
  static const Color leaf700 = Color(0xFF176B3A);

  // Sky (Trust / Data / Links)
  static const Color sky300 = Color(0xFF7BD0F4);
  static const Color sky400 = Color(0xFF4FC3F7);
  static const Color sky500 = Color(0xFF2CA8E0);

  // Neutrals — Warm Ink (cool grey 절대 X)
  static const Color ink900 = Color(
    0xFF1B1300,
  ); // ★ Primary text, warm near-black
  static const Color ink700 = Color(0xFF3C3526); // body
  static const Color ink500 = Color(0xFF6A6353); // secondary
  static const Color ink300 = Color(0xFFABA590); // placeholder
  static const Color ink200 = Color(0xFFD8D3BE); // divider
  static const Color ink100 = Color(0xFFEBE6D4); // surface stroke

  // Surface — 따뜻한 (NEVER cool grey)
  static const Color paper = Color(0xFFFFFDF6); // ★ card surface
  static const Color canvas = Color(0xFFFBF8EC); // ★ page BG

  // Semantic
  static const Color success = leaf600;
  static const Color successSoft = leaf100;
  static const Color warning = Color(0xFFFB8C00);
  static const Color warningSoft = Color(0xFFFFEACC);
  static const Color danger = Color(0xFFD9342B);
  static const Color dangerSoft = Color(0xFFFCE2E0);
  static const Color info = sky500;
  static const Color infoSoft = Color(0xFFDAF1FB);
  static const Color review = Color(0xFFB86A00); // "확인 필요" (warning 과 별도)
  static const Color reviewSoft = Color(0xFFFFE9C4);

  // OAuth Brand
  static const Color kakao = Color(0xFFFEE500);
  static const Color appleBlack = Color(0xFF1A1F2E);
}

// ============================================================================
// TYPOGRAPHY — AtoZ Display + Pretendard Body
// ============================================================================
class AppFont {
  static const String display = "AtoZ"; // 100/800/900 only
  static const String body = "Pretendard"; // 400/500/600/700/800
  static const String mono = "SF Mono"; // fallback chain via TextStyle

  // Scale (iOS 26 large-title cadence): 56 / 44 / 34 / 26 / 20 / 17 / 15 / 13 / 11
  static const double scaleDisplay56 = 56.0; // hero numbers
  static const double scaleDisplay44 = 44.0;
  static const double scaleDisplay34 = 34.0;
  static const double scaleHead26 = 26.0;
  static const double scaleHead20 = 20.0;
  static const double scaleBody17 = 17.0; // ★ 본문 (시니어 친화)
  static const double scaleBody15 = 15.0;
  static const double scaleCaption13 = 13.0;
  static const double scaleMicro11 = 11.0;
}

class AppText {
  // 워드마크 / hero (AtoZ ExtraBold)
  static const TextStyle wordmark = TextStyle(
    fontFamily: AppFont.display,
    fontWeight: FontWeight.w800,
    fontSize: AppFont.scaleDisplay44,
    letterSpacing: 0,
    color: AppColor.ink900,
  );

  // 큰 숫자 (대시보드 hero)
  static const TextStyle numXl = TextStyle(
    fontFamily: AppFont.display,
    fontWeight: FontWeight.w800,
    fontSize: AppFont.scaleDisplay56,
    letterSpacing: 0,
    fontFeatures: [FontFeature.tabularFigures()],
    color: AppColor.ink900,
  );

  // 섹션 헤더 (AtoZ ExtraBold 26+)
  static const TextStyle sectionHead = TextStyle(
    fontFamily: AppFont.display,
    fontWeight: FontWeight.w800,
    fontSize: AppFont.scaleHead26,
    color: AppColor.ink900,
  );

  // 본문 (Pretendard 17pt 시니어 친화)
  static const TextStyle body = TextStyle(
    fontFamily: AppFont.body,
    fontWeight: FontWeight.w400,
    fontSize: AppFont.scaleBody17,
    height: 1.5,
    color: AppColor.ink700,
  );

  // 본문 강조
  static const TextStyle bodyBold = TextStyle(
    fontFamily: AppFont.body,
    fontWeight: FontWeight.w700,
    fontSize: AppFont.scaleBody17,
    height: 1.5,
    color: AppColor.ink900,
  );

  // 보조 텍스트
  static const TextStyle caption = TextStyle(
    fontFamily: AppFont.body,
    fontWeight: FontWeight.w400,
    fontSize: AppFont.scaleCaption13,
    color: AppColor.ink500,
  );

  // 라벨 (단위 등)
  static const TextStyle label = TextStyle(
    fontFamily: AppFont.body,
    fontWeight: FontWeight.w500,
    fontSize: AppFont.scaleCaption13,
    color: AppColor.ink500,
    letterSpacing: 0.5,
  );

  // 버튼 (시니어 친화 17pt+)
  static const TextStyle button = TextStyle(
    fontFamily: AppFont.body,
    fontWeight: FontWeight.w700,
    fontSize: AppFont.scaleBody17,
    color: AppColor.ink900,
  );
}

// ============================================================================
// SHAPE — Radii / Spacing / Shadows
// ============================================================================
class AppRadius {
  static const double xs = 6.0;
  static const double sm = 10.0;
  static const double md = 14.0; // inputs / badges / chips
  static const double lg = 20.0; // ★ cards
  static const double xl = 28.0;
  static const double xxl = 36.0; // ★ sheets / liquid-glass
  static const double pill = 999.0;
}

class AppSpacing {
  static const double s4 = 4.0;
  static const double s8 = 8.0;
  static const double s12 = 12.0;
  static const double s16 = 16.0; // ★ page padding / card inside
  static const double s20 = 20.0;
  static const double s24 = 24.0; // ★ section default
  static const double s32 = 32.0;
  static const double s40 = 40.0;
  static const double s56 = 56.0;
}

class AppShadow {
  // shadow-1: hairlines / sticky chrome
  static const List<BoxShadow> level1 = [
    BoxShadow(color: Color(0x14000000), offset: Offset(0, 1), blurRadius: 2),
  ];

  // shadow-2: resting cards
  static const List<BoxShadow> level2 = [
    BoxShadow(
      color: Color(0x1A000000),
      offset: Offset(0, 4),
      blurRadius: 12,
      spreadRadius: -4,
    ),
  ];

  // shadow-3: raised sheets (modals)
  static const List<BoxShadow> level3 = [
    BoxShadow(
      color: Color(0x26000000),
      offset: Offset(0, 12),
      blurRadius: 32,
      spreadRadius: -8,
    ),
  ];

  // shadow-lemon: active primary CTA (warm yellow halo)
  static const List<BoxShadow> lemonHalo = [
    BoxShadow(
      color: Color(0x66FFCE00),
      offset: Offset(0, 6),
      blurRadius: 20,
      spreadRadius: -2,
    ),
  ];

  // Glass shadow (liquid-glass cards)
  static const List<BoxShadow> glass = [
    BoxShadow(
      color: Color(0x47D69E00),
      offset: Offset(0, 12),
      blurRadius: 32,
      spreadRadius: -8,
    ),
    BoxShadow(
      color: Color(0x14000000),
      offset: Offset(0, 2),
      blurRadius: 6,
      spreadRadius: -2,
    ),
  ];
}

// ============================================================================
// LIQUID GLASS — signature material
// ============================================================================
class AppGlass {
  // BackdropFilter blur 20px + saturate 140%
  static ImageFilter blur() => ImageFilter.blur(sigmaX: 20, sigmaY: 20);

  // glass fill: rgba(255, 255, 255, 0.55)
  static const Color fill = Color(0x8CFFFFFF);

  // inner highlight (top + bottom)
  static const BorderSide innerTopHL = BorderSide(
    color: Color(0xA6FFFFFF),
    width: 1,
  );
  static const BorderSide innerBotHL = BorderSide(
    color: Color(0x1EFFFFFF),
    width: 1,
  );
}

// ============================================================================
// ANIMATION — Easing + Durations
// ============================================================================
class AppAnim {
  // iOS 26 large-title easing
  static const Curve liquidGlass = Cubic(0.32, 0.72, 0, 1);

  // Durations
  static const Duration tap = Duration(milliseconds: 240);
  static const Duration sheet = Duration(milliseconds: 360);
  static const Duration pageTransition = Duration(milliseconds: 300);

  // Press state: scale 0.97
  static const double pressScale = 0.97;
}

// ============================================================================
// ACCESSIBILITY — 시니어 친화 최소값
// ============================================================================
class AppA11y {
  static const double minTouchTarget = 44.0; // 버튼 최소 (WCAG 2.5.5)
  static const double minTouchTargetSenior = 48.0; // 시니어 추가 마진
  static const double minBodyFontSize = 17.0; // 본문 최소
  static const double minContrastRatio = 4.5; // WCAG AA
}

// ============================================================================
// 차별화 메타 — §16 Lemon Aid 정체성
// ============================================================================
class AppIdentity {
  static const String productName = "Lemon Aid";
  static const String productNameKr = "레몬에이드";
  static const String tagline = "도움이 되는, 당신의 레몬에이드";
  static const String parent = "(주)레몬헬스케어";

  // 의료 컴플라이언스 표준 면책 (§14)
  static const String medicalDisclaimer =
      "본 서비스에서 제공하는 정보는 일반적인 건강 관리를 위한 참고 자료이며,\n"
      "의사·약사·영양사의 전문적 진단이나 처방을 대체하지 않습니다.";

  // 절대 금지 단어 (copywriter 검수)
  static const List<String> forbiddenWords = ["진단", "처방", "치료"];

  // Lemon Aid 표준 문구
  static const String agentIntro = "안녕하세요. 도움이 되는, 당신의 레몬에이드예요.";
  static const String emptyState = "아직 분석 데이터가 없어요. 영양제나 식단을 등록해 보세요.";
  static const String ocrLowConfidence = "라벨을 직접 확인해 주세요. 일부 항목은 확신도가 낮아요.";
  static const String approvalGate = "사진을 분석해도 될까요? 결과는 저장 전에 다시 보여드릴게요.";
}
