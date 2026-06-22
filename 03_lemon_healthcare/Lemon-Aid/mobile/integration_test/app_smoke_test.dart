// Lemon-Aid end-to-end integration test harness (scaffold).
//
// This file establishes the `integration_test/` directory + binding so the team
// has a runnable e2e entry point. The boot smoke verifies the integration
// harness initializes and renders a frame (runs under `flutter test` on the
// host and on a device/simulator).
//
// TODO(e2e): full 촬영/갤러리 → /supplements/analyze → 확인(POST /supplements)
//   흐름을 실기기/시뮬레이터에서 patrol로 자동화한다.
//   - 권한 다이얼로그(카메라/사진/헬스)는 patrol로 처리.
//   - 백엔드는 로컬 docker(lemon-aid-backend-1) 또는 목 서버로 고정.
//   - 분할 동의(OCR vs SENSITIVE_HEALTH_ANALYSIS) 재진입 경로를 포함한다.
//
// Run (host):   flutter test integration_test/app_smoke_test.dart
// Run (device): flutter test integration_test/ -d <device-id>

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Lemon-Aid e2e (scaffold)', () {
    testWidgets('integration harness boots and renders a frame', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: Center(child: Text('e2e-harness-ok'))),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('e2e-harness-ok'), findsOneWidget);
    });
  });
}
