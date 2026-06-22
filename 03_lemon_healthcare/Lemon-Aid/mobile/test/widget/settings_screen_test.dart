import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:lemon_aid_mobile/app_controller.dart';
import 'package:lemon_aid_mobile/app_providers.dart';
import 'package:lemon_aid_mobile/core/api/api_client.dart';
import 'package:lemon_aid_mobile/core/storage/local_prefs.dart';
import 'package:lemon_aid_mobile/features/auth/token_session.dart';
import 'package:lemon_aid_mobile/features/profile/profile_repository.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_repository.dart';
import 'package:lemon_aid_mobile/screens/settings_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

// SettingsScreen 은 build 경로에서 repository 를 호출하지 않으므로(소비는
// consentState getter — bootstrap 전에는 null) 미사용 메서드는 noSuchMethod
// 로 처리하는 최소 fake 로 충분하다.
class _NoopRepository implements LemonAidRepository {
  @override
  dynamic noSuchMethod(Invocation invocation) =>
      throw UnimplementedError('Unexpected call: ${invocation.memberName}');
}

class _FakeClient extends http.BaseClient {
  _FakeClient(this.handler);

  final Future<http.StreamedResponse> Function(http.Request request) handler;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    return handler(request as http.Request);
  }
}

http.StreamedResponse _json(Map<String, dynamic> body, int status) {
  return http.StreamedResponse(
    Stream<List<int>>.value(utf8.encode(jsonEncode(body))),
    status,
    headers: const <String, String>{'content-type': 'application/json'},
  );
}

Future<void> _pump(
  WidgetTester tester,
  LocalPrefs prefs, {
  http.StreamedResponse Function(http.Request request)? latestResponse,
}) async {
  tester.view.physicalSize = const Size(1200, 3200);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);

  final _FakeClient client = _FakeClient(
    (http.Request request) async =>
        latestResponse?.call(request) ??
        // 기본: 프로필 latest 는 not_ready (스냅샷 없음).
        _json(<String, dynamic>{'status': 'not_ready'}, 200),
  );

  await tester.pumpWidget(
    ProviderScope(
      overrides: <Override>[
        localPrefsProvider.overrideWith((Ref ref) => prefs),
        profileRepositoryProvider.overrideWithValue(
          ProfileRepository(
            apiClient: ApiClient(
              baseUrl: 'https://api.example.com/api/v1',
              httpClient: client,
            ),
          ),
        ),
      ],
      child: MaterialApp(
        home: SettingsScreen(
          controller: AppController(repository: _NoopRepository()),
          session: TokenSessionController(
            store: MemoryBearerTokenStore(),
            releaseMode: false,
          ),
        ),
      ),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 50));
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('header shows inclusive days-with-app from the first launch', (
    WidgetTester tester,
  ) async {
    // 13일 전 최초 실행 → 오늘 포함 14일째.
    final DateTime first = DateTime.now().subtract(const Duration(days: 13));
    SharedPreferences.setMockInitialValues(<String, Object>{
      'app.first_launch': DateTime(
        first.year,
        first.month,
        first.day,
      ).toIso8601String(),
      'profile_display_name': '태동',
    });
    final LocalPrefs prefs = await LocalPrefs.create();

    await _pump(tester, prefs);

    expect(find.text('태동님'), findsOneWidget);
    expect(find.text('레몬에이드와 함께한 지 14일째'), findsOneWidget);
  });

  testWidgets('days line survives a non-JSON-object profile response', (
    WidgetTester tester,
  ) async {
    // 프록시/캡티브 포털이 200으로 HTML 본문을 주면 ApiClient 가 ApiError 가
    // 아닌 FormatException 을 던진다. 이 경우에도 로컬 경과일은 유지돼야 한다.
    final DateTime first = DateTime.now().subtract(const Duration(days: 6));
    SharedPreferences.setMockInitialValues(<String, Object>{
      'app.first_launch': DateTime(
        first.year,
        first.month,
        first.day,
      ).toIso8601String(),
    });
    final LocalPrefs prefs = await LocalPrefs.create();

    await _pump(
      tester,
      prefs,
      latestResponse: (http.Request request) => http.StreamedResponse(
        Stream<List<int>>.value('<html>captive portal</html>'.codeUnits),
        200,
        headers: const <String, String>{'content-type': 'text/html'},
      ),
    );

    // 스냅샷 조회가 FormatException 으로 실패해도 경과일 라인은 렌더된다.
    expect(find.text('레몬에이드와 함께한 지 7일째'), findsOneWidget);
  });

  testWidgets('service info row opens a sheet with disclaimer and version', (
    WidgetTester tester,
  ) async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
    final LocalPrefs prefs = await LocalPrefs.create();

    await _pump(tester, prefs);

    await tester.tap(find.text('서비스 정보'));
    await tester.pumpAndSettle();

    expect(
      find.textContaining('의사·약사·영양사의 진단을 대신하진 않아요'),
      findsOneWidget,
    );
    expect(find.text('v1.0.0 · Lemon Aid'), findsWidgets);
  });

  testWidgets('service info content avoids forbidden medical terms beyond the '
      'standard disclaimer', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
    final LocalPrefs prefs = await LocalPrefs.create();

    await _pump(tester, prefs);
    await tester.tap(find.text('서비스 정보'));
    await tester.pumpAndSettle();

    // 표준 면책 문장은 '진단'을 부정 맥락으로 포함하므로 화이트리스트.
    const String standardDisclaimer =
        '레몬에이드는 건강 관리를 도와드리는 서비스로\n의사·약사·영양사의 진단을 대신하진 않아요.';
    final Iterable<Text> texts = tester.widgetList<Text>(find.byType(Text));
    for (final Text text in texts) {
      final String data = text.data ?? '';
      if (data == standardDisclaimer) {
        continue;
      }
      for (final String term in const <String>['진단', '처방', '치료', '효능']) {
        expect(data.contains(term), isFalse, reason: '금칙어 "$term" in "$data"');
      }
    }
  });
}
