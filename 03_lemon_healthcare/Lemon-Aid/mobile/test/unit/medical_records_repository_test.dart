import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:lemon_aid_mobile/core/api/api_client.dart';
import 'package:lemon_aid_mobile/core/api/api_error.dart';
import 'package:lemon_aid_mobile/features/medical/medical_models.dart';
import 'package:lemon_aid_mobile/features/medical/medical_records_repository.dart';

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

MedicalRecordsRepository _repoFor(_FakeClient client) {
  return MedicalRecordsRepository(
    apiClient: ApiClient(
      baseUrl: 'https://api.example.com/api/v1',
      httpClient: client,
    ),
  );
}

void main() {
  group('MedicalRecordsRepository.addCondition', () {
    test('calls create then confirm in order with the right payloads',
        () async {
      final List<String> paths = <String>[];
      final _FakeClient client = _FakeClient((http.Request request) async {
        paths.add(request.url.path);
        if (request.url.path == '/api/v1/medical-records') {
          return _json(<String, dynamic>{
            'id': 'rec-1',
            'record_type': 'condition',
            'status': 'requires_review',
            'conditions': <Map<String, dynamic>>[
              <String, dynamic>{'id': 'c1', 'condition_text': '당뇨'},
            ],
          }, 201);
        }
        // confirm
        return _json(<String, dynamic>{
          'id': 'rec-1',
          'record_type': 'condition',
          'status': 'active',
          'conditions': <Map<String, dynamic>>[
            <String, dynamic>{
              'id': 'c1',
              'condition_text': '당뇨',
              'clinical_status': 'active',
            },
          ],
        }, 200);
      });

      final MedicalRecord record = await _repoFor(client).addCondition('당뇨');

      expect(paths, <String>[
        '/api/v1/medical-records',
        '/api/v1/medical-records/rec-1/confirm',
      ]);

      final Map<String, dynamic> createBody =
          jsonDecode(client.requests[0].body) as Map<String, dynamic>;
      expect(createBody['record_type'], 'condition');
      expect(createBody['source'], 'user_manual');
      expect(createBody['user_confirmed'], true);
      final Map<String, dynamic> condition =
          createBody['condition'] as Map<String, dynamic>;
      expect(condition['condition_text'], '당뇨');
      expect(condition['clinical_status'], 'active');
      expect(condition['source'], 'user_confirmed');

      final Map<String, dynamic> confirmBody =
          jsonDecode(client.requests[1].body) as Map<String, dynamic>;
      expect(confirmBody['user_confirmed'], true);
      expect(confirmBody['status'], 'active');

      expect(record.status, 'active');
      expect(record.primaryConditionText, '당뇨');
    });

    test('rejects empty condition text without calling the API', () async {
      final _FakeClient client = _FakeClient(
        (http.Request request) async => _json(<String, dynamic>{}, 201),
      );

      expect(
        () => _repoFor(client).addCondition('   '),
        throwsA(isA<ArgumentError>()),
      );
      expect(client.requests, isEmpty);
    });
  });

  group('MedicalRecordsRepository.archive', () {
    test('confirms with status archived', () async {
      final _FakeClient client = _FakeClient(
        (http.Request request) async => _json(<String, dynamic>{
          'id': 'rec-9',
          'record_type': 'condition',
          'status': 'archived',
        }, 200),
      );

      final MedicalRecord record = await _repoFor(client).archive('rec-9');

      expect(
        client.requests.single.url.path,
        '/api/v1/medical-records/rec-9/confirm',
      );
      final Map<String, dynamic> body =
          jsonDecode(client.requests.single.body) as Map<String, dynamic>;
      expect(body['status'], 'archived');
      expect(record.status, 'archived');
    });

    test('surfaces 409 medical_record_not_confirmable as ApiError', () async {
      final _FakeClient client = _FakeClient(
        (http.Request request) async => _json(<String, dynamic>{
          'detail': <String, dynamic>{
            'code': 'medical_record_not_confirmable',
            'message': '확정할 수 없어요.',
          },
        }, 409),
      );

      await expectLater(
        _repoFor(client).archive('rec-9'),
        throwsA(
          isA<ApiError>().having(
            (ApiError e) => e.code,
            'code',
            'medical_record_not_confirmable',
          ),
        ),
      );
    });
  });

  group('MedicalRecordsRepository.list', () {
    test('parses records array', () async {
      final _FakeClient client = _FakeClient(
        (http.Request request) async => _json(<String, dynamic>{
          'records': <Map<String, dynamic>>[
            <String, dynamic>{
              'id': 'rec-1',
              'record_type': 'condition',
              'status': 'active',
              'conditions': <Map<String, dynamic>>[
                <String, dynamic>{'id': 'c1', 'condition_text': '고혈압'},
              ],
            },
          ],
        }, 200),
      );

      final List<MedicalRecord> records = await _repoFor(client).list();

      expect(records, hasLength(1));
      expect(records.single.isActiveCondition, isTrue);
      expect(records.single.primaryConditionText, '고혈압');
      expect(
        client.requests.single.url.queryParameters['include_archived'],
        'false',
      );
    });
  });
}
