import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/core/storage/local_prefs.dart';
import 'package:lemon_aid_mobile/features/profile/profile_interests_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  Future<LocalPrefs> freshPrefs() async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
    return LocalPrefs.create();
  }

  Future<void> pump(WidgetTester tester, LocalPrefs prefs) async {
    tester.view.physicalSize = const Size(1200, 2600);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(home: ProfileInterestsScreen(prefs: prefs)),
    );
    await tester.pump();
  }

  testWidgets('selecting purpose + concern persists to local storage', (
    WidgetTester tester,
  ) async {
    final LocalPrefs prefs = await freshPrefs();
    await pump(tester, prefs);

    expect(find.text('가입 목적'), findsOneWidget);
    expect(find.text('관리 모드'), findsOneWidget);
    expect(find.text('건강 고민'), findsOneWidget);
    expect(find.text('영양제 섭취 관리'), findsOneWidget);
    expect(find.text('피로감'), findsOneWidget);

    await tester.tap(find.text('영양제 섭취 관리'));
    await tester.pump();
    await tester.tap(find.text('피로감'));
    await tester.pump();
    await tester.tap(find.text('저장하기'));
    await tester.pump();

    expect(prefs.profilePurposes(), <String>['supplement']);
    expect(prefs.profileConcerns(), <String>['fatigue']);
    expect(prefs.profileCareMode(), 'wellness');
    expect(find.text('관심 목적을 저장했어요'), findsOneWidget);
  });

  testWidgets('prefills existing selections so a no-op save keeps them', (
    WidgetTester tester,
  ) async {
    final LocalPrefs prefs = await freshPrefs();
    await prefs.setProfileCareMode('chronic');
    await prefs.setProfilePurposes(<String>['diet']);
    await prefs.setProfileConcerns(<String>['bp']);

    await pump(tester, prefs);
    await tester.tap(find.text('저장하기'));
    await tester.pump();

    expect(prefs.profilePurposes(), <String>['diet']);
    expect(prefs.profileConcerns(), <String>['bp']);
    expect(prefs.profileCareMode(), 'chronic');
  });

  testWidgets('chronic care mode stores chronic purpose and condition', (
    WidgetTester tester,
  ) async {
    final LocalPrefs prefs = await freshPrefs();
    await pump(tester, prefs);

    await tester.tap(find.text('만성질환·복약 동반 관리'));
    await tester.pump();
    expect(find.text('만성질환·복약 관련 관리 항목'), findsOneWidget);

    await tester.tap(find.text('당뇨'));
    await tester.pump();
    await tester.tap(find.text('저장하기'));
    await tester.pump();

    expect(prefs.profileCareMode(), 'chronic');
    expect(prefs.profilePurposes(), contains('chronic'));
    expect(prefs.profileConcerns(), contains('diabetes'));
  });
}
