import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:lemon_aid_mobile/app_providers.dart';
import 'package:lemon_aid_mobile/core/api/api_client.dart';
import 'package:lemon_aid_mobile/features/auth/token_session.dart';
import 'package:lemon_aid_mobile/features/privacy/privacy_repository.dart';
import 'package:lemon_aid_mobile/screens/settings/withdraw_screen.dart';

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
  Future<void> pump(WidgetTester tester, _FakeClient client) async {
    tester.view.physicalSize = const Size(1200, 2600);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          bearerTokenStoreProvider.overrideWithValue(MemoryBearerTokenStore()),
          privacyRepositoryProvider.overrideWithValue(
            PrivacyRepository(
              apiClient: ApiClient(
                baseUrl: 'https://api.example.com/api/v1',
                httpClient: client,
              ),
            ),
          ),
        ],
        child: const MaterialApp(home: WithdrawScreen()),
      ),
    );
    await tester.pump();
  }

  testWidgets('withdraw button is disabled until the confirm box is checked',
      (WidgetTester tester) async {
    final _FakeClient client = _FakeClient(
      (http.Request request) async => _json(<String, dynamic>{'id': 'd1'}, 202),
    );
    await pump(tester, client);

    final Finder button = find.widgetWithText(InkWell, '탈퇴하기');
    // 체크 전 탭 → API 호출 없음.
    await tester.tap(button, warnIfMissed: false);
    await tester.pump();
    expect(client.requests, isEmpty);

    // 확인 체크 후 탭 → 최종 다이얼로그 경유.
    await tester.tap(find.byType(Checkbox));
    await tester.pumpAndSettle();
    await tester.tap(button);
    await tester.pumpAndSettle();

    // showDeleteConfirmDialog 가 떠야 한다.
    expect(find.text('삭제'), findsOneWidget);

    // 최종 '삭제' 확인 → 202 요청 발생.
    await tester.tap(find.text('삭제'));
    await tester.pumpAndSettle();

    expect(client.requests, hasLength(1));
    expect(
      client.requests.single.url.path,
      '/api/v1/me/data-deletion-requests',
    );
    final Map<String, dynamic> body =
        jsonDecode(client.requests.single.body) as Map<String, dynamic>;
    expect(body['request_type'], 'all_user_data');
    expect(find.text('요청을 접수했어요'), findsOneWidget);
  });

  testWidgets('copy avoids prohibited medical terms', (
    WidgetTester tester,
  ) async {
    final _FakeClient client = _FakeClient(
      (http.Request request) async => _json(<String, dynamic>{'id': 'd1'}, 202),
    );
    await pump(tester, client);
    await tester.pump(const Duration(milliseconds: 50));

    const List<String> banned = <String>['진단', '처방', '치료', '효능'];
    final Iterable<Text> texts = tester.widgetList<Text>(find.byType(Text));
    for (final Text widget in texts) {
      final String? data = widget.data;
      if (data == null) continue;
      for (final String term in banned) {
        expect(data.contains(term), isFalse, reason: '"$data" 에 "$term"');
      }
    }
  });
}
