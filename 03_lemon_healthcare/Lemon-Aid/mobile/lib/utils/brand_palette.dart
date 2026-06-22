// utils/brand_palette.dart — Lemon Aid 4색 브랜드 테마 팔레트
//
// SoT v1.1 §9.5: 사용자가 설정에서 선택할 수 있는 4색 브랜드 테마 정의.
// 기본값: yellow (#FFC700, design_tokens_v2 AppColor.brand 와 일치).
// brandThemeNotifier → AppColors.brand 동적 반영 구상.
//
// 2026-06-12: Figma 01_Design_System(DesignSystem_v2.0) 4모드×5단계 정의에 정렬.
// 비-yellow pressed/soft hex 교정 + deep/tint 단계 추가.

import 'package:flutter/material.dart';

/// 사용자가 선택 가능한 브랜드 테마 색상 4종.
enum BrandTheme {
  /// 기본 레몬 옐로우 — design_tokens_v2 AppColor.brand 와 동일.
  yellow,

  /// 퍼플
  purple,

  /// 그린
  green,

  /// 블루
  blue,
}

/// 각 BrandTheme 에 대응하는 색상 값.
extension BrandThemeColor on BrandTheme {
  /// 메인 브랜드 색상.
  Color get color {
    switch (this) {
      case BrandTheme.yellow:
        return const Color(0xFFFFC700);
      case BrandTheme.purple:
        return const Color(0xFF8B7EE8);
      case BrandTheme.green:
        return const Color(0xFF5FBF7A);
      case BrandTheme.blue:
        return const Color(0xFF4D9CFF);
    }
  }

  /// 눌림 상태 (약간 어두운 톤).
  Color get pressedColor {
    switch (this) {
      case BrandTheme.yellow:
        return const Color(0xFFE5B300);
      case BrandTheme.purple:
        return const Color(0xFF7164DB);
      case BrandTheme.green:
        return const Color(0xFF4AA663);
      case BrandTheme.blue:
        return const Color(0xFF3884E5);
    }
  }

  /// 깊은 톤 (브랜드 배경 위 텍스트 등).
  Color get deepColor {
    switch (this) {
      case BrandTheme.yellow:
        return const Color(0xFFC99100);
      case BrandTheme.purple:
        return const Color(0xFF4F44A6);
      case BrandTheme.green:
        return const Color(0xFF2F7C44);
      case BrandTheme.blue:
        return const Color(0xFF1F5BB8);
    }
  }

  /// 옅은 소프트 배경 (chip, badge 등).
  Color get softColor {
    switch (this) {
      case BrandTheme.yellow:
        return const Color(0xFFFFF6CC);
      case BrandTheme.purple:
        return const Color(0xFFEEEBFD);
      case BrandTheme.green:
        return const Color(0xFFE4F4E8);
      case BrandTheme.blue:
        return const Color(0xFFE3F0FF);
    }
  }

  /// 소프트보다 한 단계 진한 틴트 (선택 배경 등).
  Color get tintColor {
    switch (this) {
      case BrandTheme.yellow:
        return const Color(0xFFFFF0A8);
      case BrandTheme.purple:
        return const Color(0xFFE2DDFB);
      case BrandTheme.green:
        return const Color(0xFFD4EDDA);
      case BrandTheme.blue:
        return const Color(0xFFCEE3FF);
    }
  }

  /// 화면에 표시할 한국어 레이블.
  String get label {
    switch (this) {
      case BrandTheme.yellow:
        return '옐로우';
      case BrandTheme.purple:
        return '퍼플';
      case BrandTheme.green:
        return '그린';
      case BrandTheme.blue:
        return '블루';
    }
  }
}
