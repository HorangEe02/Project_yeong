/// 앱 진입점.
///
/// Riverpod ``ProviderScope`` 로 감싸 전역 상태 활성화 + 로거 초기화.
///
/// Reference:
///   mobile/CLAUDE.md
///   docs/dev-guides/10-mobile-flutter-setup.md
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'core/utils/logger.dart';

void main() {
  setupLogger();
  runApp(
    const ProviderScope(
      child: LemonHealthcareApp(),
    ),
  );
}
