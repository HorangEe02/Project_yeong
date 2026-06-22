import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:lemon_aid_mobile/app_providers.dart';
import 'package:lemon_aid_mobile/core/api/api_client.dart';
import 'package:lemon_aid_mobile/core/storage/local_prefs.dart';
import 'package:lemon_aid_mobile/features/profile/profile_repository.dart';
import 'package:lemon_aid_mobile/screens/settings/profile_edit_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FakeClient extends http.BaseClient {
  _FakeClient(this.handler);

  final Future<http.StreamedResponse> Function(http.Request request) handler;
  final List<http.Request> requests = <http.Request>[];

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final http.Request typed = request as http.Request;
    requests.add(typed);
    return handler(typed);
  }
}

http.StreamedResponse _json(Map<String, dynamic> body, int status) {
  return http.StreamedResponse(
    Stream<List<int>>.value(utf8.encode(jsonEncode(body))),
    status,
    headers: const <String, String>{'content-type': 'application/json'},
  );
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  Future<void> pump(
    WidgetTester tester,
    _FakeClient client,
    LocalPrefs prefs,
  ) async {
    tester.view.physicalSize = const Size(1200, 2600);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

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
        child: const MaterialApp(home: ProfileEditScreen()),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
  }

  testWidgets('not_ready opens an empty form with a hint', (
    WidgetTester tester,
  ) async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
    final LocalPrefs prefs = await LocalPrefs.create();
    final _FakeClient client = _FakeClient(
      (http.Request request) async =>
          _json(<String, dynamic>{'status': 'not_ready'}, 200),
    );

    await pump(tester, client, prefs);

    expect(find.text('신체 정보를 입력하면 분석이 더 정확해져요'), findsOneWidget);
  });

  testWidgets('out-of-range height shows a validation message', (
    WidgetTester tester,
  ) async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
    final LocalPrefs prefs = await LocalPrefs.create();
    final _FakeClient client = _FakeClient(
      (http.Request request) async =>
          _json(<String, dynamic>{'status': 'not_ready'}, 200),
    );

    await pump(tester, client, prefs);

    await tester.enterText(
      find.widgetWithText(TextField, '예: 172'),
      '500',
    );
    await tester.tap(find.text('저장하기'));
    await tester.pump();

    expect(find.text('키는 30~260cm 사이로 입력해주세요.'), findsOneWidget);
    // 검증 실패 시 서버 저장 호출이 없어야 한다 (GET latest 1회만).
    expect(
      client.requests.where((http.Request r) => r.method == 'POST'),
      isEmpty,
    );
  });

  testWidgets('prefills existing snapshot values', (
    WidgetTester tester,
  ) async {
    SharedPreferences.setMockInitialValues(<String, Object>{
      'profile_display_name': '태동',
    });
    final LocalPrefs prefs = await LocalPrefs.create();
    final _FakeClient client = _FakeClient(
      (http.Request request) async => _json(<String, dynamic>{
        'sex': 'male',
        'birth_year': 1990,
        'height_cm': '172.00',
        'weight_kg': '68.00',
      }, 200),
    );

    await pump(tester, client, prefs);

    expect(find.text('172'), findsOneWidget);
    expect(find.text('68'), findsOneWidget);
    expect(find.text('1990'), findsOneWidget);
    expect(find.text('태동'), findsOneWidget);
  });
}
