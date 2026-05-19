/// Lemon Healthcare 브랜드 컬러.
///
/// Reference:
///   mobile/CLAUDE.md - UI/UX 표준
library;

import 'package:flutter/material.dart';

abstract class AppColors {
  // Primary — 브랜드 옐로우
  static const Color primary = Color(0xFFFFD700);
  static const Color primaryContainer = Color(0xFFFFF9C4);
  static const Color onPrimary = Color(0xFF1A1A1A);

  // Secondary — 신뢰감 블루
  static const Color secondary = Color(0xFF4FC3F7);
  static const Color secondaryContainer = Color(0xFFE1F5FE);

  // Status
  static const Color error = Color(0xFFD32F2F);
  static const Color success = Color(0xFF388E3C);
  static const Color warning = Color(0xFFFB8C00);

  // Nutrient status (Phase M-3 결과 화면용)
  static const Color statusDeficient = Color(0xFFEF5350);
  static const Color statusLow = Color(0xFFFB8C00);
  static const Color statusAdequate = Color(0xFF66BB6A);
  static const Color statusExcessive = Color(0xFFFFB300);
  static const Color statusRisky = Color(0xFFB71C1C);
}
