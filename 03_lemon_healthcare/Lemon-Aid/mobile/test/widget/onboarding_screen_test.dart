import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/core/storage/local_prefs.dart';
import 'package:lemon_aid_mobile/features/onboarding/onboarding_screen.dart';
import 'package:lemon_aid_mobile/widgets/common/medical_disclaimer.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  Future<LocalPrefs> freshPrefs() async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
    return LocalPrefs.create();
  }

  Future<void> pump(
    WidgetTester tester,
    LocalPrefs prefs,
    VoidCallback onDone,
  ) async {
    tester.view.physicalSize = const Size(1200, 2600);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(home: OnboardingScreen(prefs: prefs, onDone: onDone)),
    );
    await tester.pump();
  }

  testWidgets('walks all 3 slides then sets the seen flag and calls onDone', (
    WidgetTester tester,
  ) async {
    final LocalPrefs prefs = await freshPrefs();
    bool done = false;
    await pump(tester, prefs, () => done = true);

    expect(prefs.onboardingSeen(), isFalse);
    expect(find.text('레몬에이드에 오신 걸\n환영해요'), findsOneWidget);

    await tester.tap(find.text('다음'));
    await tester.pumpAndSettle();
    expect(find.text('사진 한 장으로\n분석해요'), findsOneWidget);
    expect(find.byType(MedicalDisclaimer), findsOneWidget); // 분석 슬라이드 면책 고지

    await tester.tap(find.text('다음'));
    await tester.pumpAndSettle();
    expect(find.text('시작하기'), findsOneWidget);

    await tester.tap(find.text('시작하기'));
    await tester.pumpAndSettle();

    expect(prefs.onboardingSeen(), isTrue);
    expect(done, isTrue);
  });

  testWidgets('skip immediately sets the seen flag and calls onDone', (
    WidgetTester tester,
  ) async {
    final LocalPrefs prefs = await freshPrefs();
    bool done = false;
    await pump(tester, prefs, () => done = true);

    await tester.tap(find.text('건너뛰기'));
    await tester.pumpAndSettle();

    expect(prefs.onboardingSeen(), isTrue);
    expect(done, isTrue);
  });
}
