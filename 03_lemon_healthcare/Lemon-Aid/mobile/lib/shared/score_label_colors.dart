// shared/score_label_colors.dart — 건강 점수 등급 라벨 → 시맨틱 색 매핑
//
// 가이드 06 §2.4 확정안: 서버 `health_score.label` 5단계를 success/warning/
// danger 3토큰으로 변환한다. 홈 점수 카드(health_hero_card)와 오늘의 분석
// (score_screen)의 링·칩이 이 매핑 하나를 공유해 두 화면의 등급 색 불일치를
// 막는다 (점수 보류 결정 #5 "홈 카드·오늘의 분석 링 = 같은 score" 정합).
//
// 모바일은 label 문자열만 소비한다 — 점수→색 재계산 금지 (점수 산식·라벨
// 경계는 백엔드 단일 소유). null·미지 값(서버 신규 라벨)은 현행 브랜드 색
// 폴백.

import 'package:flutter/material.dart';

import '../utils/design_tokens_v2.dart';

/// 등급 라벨의 전경 색 — 링 진행·칩 텍스트에 쓴다.
///
/// Args:
///   label: 서버 등급 코드 (excellent/good/moderate/warning/needs_attention).
///
/// Returns:
///   시맨틱 전경 색. null·미지 값은 [AppColor.brand].
Color scoreLabelColor(String? label) {
  switch (label) {
    case 'excellent':
    case 'good':
      return AppColor.success;
    case 'moderate':
      return AppColor.warning;
    case 'warning':
    case 'needs_attention':
      return AppColor.danger;
    default:
      return AppColor.brand;
  }
}

/// 등급 라벨의 soft 배경 색 — 칩 배경에 쓴다.
///
/// Args:
///   label: 서버 등급 코드 (excellent/good/moderate/warning/needs_attention).
///
/// Returns:
///   시맨틱 soft 배경 색. null·미지 값은 [AppColor.brandSoft].
Color scoreLabelSoftColor(String? label) {
  switch (label) {
    case 'excellent':
    case 'good':
      return AppColor.successSoft;
    case 'moderate':
      return AppColor.warningSoft;
    case 'warning':
    case 'needs_attention':
      return AppColor.dangerSoft;
    default:
      return AppColor.brandSoft;
  }
}
