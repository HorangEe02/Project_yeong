/// 환경 변수 — 빌드 시 ``--dart-define`` 으로 주입.
///
/// 예:
///   flutter run --dart-define=API_BASE_URL=http://localhost:8000
library;

import 'package:flutter/foundation.dart';

abstract class Env {
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  static const bool isDebug = kDebugMode;

  static const String environment = String.fromEnvironment(
    'ENVIRONMENT',
    defaultValue: 'development',
  );

  /// 운영 환경 여부 — HTTPS 강제, 디버그 로그 제거 가드.
  static bool get isProduction => environment == 'production';
}
