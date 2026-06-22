import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:lemon_aid_mobile/app_providers.dart';
import 'package:lemon_aid_mobile/core/api/api_client.dart';
import 'package:lemon_aid_mobile/features/medical/medical_records_repository.dart';
import 'package:lemon_aid_mobile/screens/settings/health_profile_screen.dart';

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
          medicalRecordsRepositoryProvider.overrideWithValue(
            MedicalRecordsRepository(
              apiClient: ApiClient(
                baseUrl: 'https://api.example.com/api/v1',
                httpClient: client,
              ),
            ),
          ),
        ],
        child: const MaterialApp(home: HealthProfileScreen()),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
  }

  testWidgets('restores existing conditions and shows disclaimer footer',
      (WidgetTester tester) async {
    final _FakeClient client = _FakeClient((http.Request request) async {
      if (request.method == 'GET') {
        return _json(<String, dynamic>{
          'records': <Map<String, dynamic>>[
            <String, dynamic>{
              'id': 'rec-1',
              'record_type': 'condition',
              'status': 'active',
              'conditions': <Map<String, dynamic>>[
                <String, dynamic>{'id': 'c1', 'condition_text': '당뇨'},
              ],
            },
          ],
        }, 200);
      }
      return _json(<String, dynamic>{}, 200);
    });

    await pump(tester, client);

    expect(find.text('당뇨'), findsOneWidget);
    expect(
      find.text('입력하신 정보는 건강 참고용이며 의료 행위를 대신하지 않아요'),
      findsOneWidget,
    );
  });

  testWidgets('direct-input chip reveals a text field', (
    WidgetTester tester,
  ) async {
    final _FakeClient client = _FakeClient(
      (http.Request request) async =>
          _json(<String, dynamic>{'records': <Map<String, dynamic>>[]}, 200),
    );
    await pump(tester, client);

    expect(find.text('질환명을 입력해주세요 (최대 180자)'), findsNothing);
    await tester.tap(find.text('직접 입력'));
    await tester.pump();
    expect(find.text('질환명을 입력해주세요 (최대 180자)'), findsOneWidget);
  });

  testWidgets('copy avoids prohibited medical terms', (
    WidgetTester tester,
  ) async {
    final _FakeClient client = _FakeClient(
      (http.Request request) async =>
          _json(<String, dynamic>{'records': <Map<String, dynamic>>[]}, 200),
    );
    await pump(tester, client);

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
