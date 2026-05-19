/// 앱 전역 로거 — `logger` 패키지 기반.
library;

import 'package:flutter/foundation.dart';
import 'package:logger/logger.dart';

/// 앱 전역 로거. ``main()`` 진입 시 ``setupLogger()`` 1회 호출.
late Logger appLogger;

/// 로거 초기화. 디버그 모드면 verbose, 운영은 info 이상.
void setupLogger() {
  appLogger = Logger(
    level: kDebugMode ? Level.debug : Level.info,
    printer: PrettyPrinter(
      methodCount: 0,
      colors: true,
      printEmojis: true,
    ),
  );
}
