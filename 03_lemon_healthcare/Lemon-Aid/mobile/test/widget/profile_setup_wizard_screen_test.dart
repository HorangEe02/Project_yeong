import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:lemon_aid_mobile/app_providers.dart';
import 'package:lemon_aid_mobile/core/api/api_client.dart';
import 'package:lemon_aid_mobile/features/auth/signup_wizard/profile_setup_wizard_screen.dart';
import 'package:lemon_aid_mobile/features/profile/profile_repository.dart';

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

  Future<void> pump(WidgetTester tester, _FakeClient client) async {
    tester.view.physicalSize = const Size(1200, 2600);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          profileRepositoryProvider.overrideWithValue(
            ProfileRepository(
              apiClient: ApiClient(
                baseUrl: 'https://api.example.com/api/v1',
                httpClient: client,
              ),
            ),
          ),
        ],
        child: const MaterialApp(home: ProfileSetupWizardScreen()),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
  }

  testWidgets('submits sex + body to /health/profile-snapshots', (
    WidgetTester tester,
  ) async {
    final _FakeClient client = _FakeClient((http.Request request) async {
      if (request.method == 'POST' &&
          request.url.path.endsWith('/health/profile-snapshots')) {
        return _json(<String, dynamic>{
          'id': 'snap-1',
          'sex': 'male',
          'height_cm': '168.00',
          'created_at': '2026-06-13T00:00:00Z',
        }, 201);
      }
      return _json(<String, dynamic>{'status': 'not_ready'}, 200);
    });

    await pump(tester, client);

    await tester.tap(find.text('남성'));
    await tester.pump();
    await tester.tap(find.text('다음'));
    await tester.pump();
    await tester.enterText(find.widgetWithText(TextField, '예: 168'), '168');
    await tester.pump();
    await tester.tap(find.text('다음'));
    await tester.pump();
    await tester.tap(find.text('저장하기'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));

    final List<http.Request> posts = client.requests
        .where(
          (http.Request r) =>
              r.method == 'POST' &&
              r.url.path.endsWith('/health/profile-snapshots'),
        )
        .toList();
    expect(posts, hasLength(1));
    final Map<String, dynamic> body =
        jsonDecode(posts.first.body) as Map<String, dynamic>;
    expect(body['sex'], 'male');
    expect(body['height_cm'], '168.00');
    expect(body['source'], 'manual');
    expect(find.text('프로필을 저장했어요'), findsOneWidget);
  });

  testWidgets('out-of-range height shows a validation message', (
    WidgetTester tester,
  ) async {
    final _FakeClient client = _FakeClient(
      (http.Request request) async =>
          _json(<String, dynamic>{'status': 'not_ready'}, 200),
    );

    await pump(tester, client);

    await tester.tap(find.text('다음'));
    await tester.pump();
    await tester.enterText(find.widgetWithText(TextField, '예: 168'), '500');
    await tester.pump();

    expect(find.text('키는 30~260cm 사이로 입력해 주세요.'), findsOneWidget);
    expect(
      client.requests.where((http.Request r) => r.method == 'POST'),
      isEmpty,
    );
  });
}
