import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:lemon_aid_mobile/core/api/api_client.dart';
import 'package:lemon_aid_mobile/core/api/api_error.dart';
import 'package:lemon_aid_mobile/features/dashboard/home_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_repository.dart';

void main() {
  test('fetchMedications reads the items wrapper from GET /me/medications', () async {
    final _ScriptedClient client = _ScriptedClient(<_StubResponse>[
      _StubResponse(
        statusCode: 200,
        body: <String, Object?>{
          'items': <Object?>[
            <String, Object?>{
              'id': 'med-1',
              'display_name': '아모디핀',
              'medication_class': 'calcium_channel_blocker',
              'condition_tags': <String>['hypertension'],
              'confirmation_status': 'user_confirmed',
              'is_active': true,
              'last_confirmed_at': '2026-06-10T00:00:00Z',
              'created_at': '2026-06-10T00:00:00Z',
              'updated_at': '2026-06-10T00:00:00Z',
            },
          ],
        },
      ),
    ]);
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: client,
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    final HomeMedicationsResult result = await repository.fetchMedications();

    expect(client.requests.single.method, 'GET');
    expect(client.requests.single.url.path, '/api/v1/me/medications');
    expect(result.items.single.displayName, '아모디핀');
    expect(result.items.single.medicationClassLabel, '칼슘 채널 차단제');
  });

  test('createMedication posts only the allowed forbid-safe fields', () async {
    final _ScriptedClient client = _ScriptedClient(<_StubResponse>[
      _StubResponse(statusCode: 201, body: _medicationJson('med-9')),
    ]);
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: client,
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    final HomeMedication created = await repository.createMedication(
      const MedicationCreateRequest(
        displayName: '아모디핀',
        medicationClass: 'calcium_channel_blocker',
        conditionTags: <String>['hypertension'],
      ),
    );

    final http.Request request = client.requests.single as http.Request;
    final Map<String, dynamic> body =
        jsonDecode(request.body) as Map<String, dynamic>;
    expect(request.method, 'POST');
    expect(request.url.path, '/api/v1/me/medications');
    expect(body['display_name'], '아모디핀');
    expect(body['medication_class'], 'calcium_channel_blocker');
    expect(body['condition_tags'], <String>['hypertension']);
    expect(body['is_active'], isTrue);
    // 용량/OCR 필드는 전송 금지.
    expect(body.containsKey('dosage'), isFalse);
    expect(body.containsKey('normalized_name'), isFalse);
    expect(created.id, 'med-9');
  });

  test('createMedication rejects an unknown medication class before sending', () async {
    final _ScriptedClient client = _ScriptedClient(<_StubResponse>[]);
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: client,
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    expect(
      () => repository.createMedication(
        const MedicationCreateRequest(
          displayName: '아모디핀',
          medicationClass: 'unknown_class',
        ),
      ),
      throwsArgumentError,
    );
    expect(client.requests, isEmpty);
  });

  test('createMedication grants consent and retries once on 403 consent_required', () async {
    final _ScriptedClient client = _ScriptedClient(<_StubResponse>[
      // 1) POST /me/medications → 403 consent_required
      _StubResponse(
        statusCode: 403,
        body: <String, Object?>{
          'detail': <String, Object?>{
            'code': 'consent_required',
            'message': '민감 건강정보 분석 동의가 필요해요.',
            'required_consents': <String>['sensitive_health_analysis'],
          },
        },
      ),
      // 2) grantConsent → POST /me/privacy/consents/... → 201
      _StubResponse(
        statusCode: 201,
        body: <String, Object?>{
          'consent_type': 'sensitive_health_analysis',
          'policy_version': 'v1',
          'granted': true,
          'occurred_at': '2026-06-10T00:00:00Z',
        },
      ),
      // 3) retry POST /me/medications → 201
      _StubResponse(statusCode: 201, body: _medicationJson('med-retry')),
    ]);
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: client,
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    final HomeMedication created = await repository.createMedication(
      const MedicationCreateRequest(displayName: '아모디핀'),
    );

    expect(created.id, 'med-retry');
    expect(client.requests.map((http.BaseRequest r) => r.url.path).toList(), <String>[
      '/api/v1/me/medications',
      '/api/v1/me/privacy/consents/sensitive_health_analysis',
      '/api/v1/me/medications',
    ]);
  });

  test('createMedication does not retry on a non-consent error', () async {
    final _ScriptedClient client = _ScriptedClient(<_StubResponse>[
      _StubResponse(
        statusCode: 422,
        body: <String, Object?>{
          'detail': <String, Object?>{
            'code': 'validation_error',
            'message': '입력을 확인해주세요.',
          },
        },
      ),
    ]);
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: client,
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    await expectLater(
      repository.createMedication(
        const MedicationCreateRequest(displayName: '아모디핀'),
      ),
      throwsA(
        isA<ApiError>().having(
          (ApiError e) => e.statusCode,
          'statusCode',
          422,
        ),
      ),
    );
    expect(client.requests, hasLength(1));
  });

  test('deactivateMedication posts to the deactivate path', () async {
    final _ScriptedClient client = _ScriptedClient(<_StubResponse>[
      _StubResponse(
        statusCode: 200,
        body: _medicationJson('med-1', isActive: false),
      ),
    ]);
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: client,
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    final HomeMedication result = await repository.deactivateMedication('med-1');

    expect(client.requests.single.method, 'POST');
    expect(
      client.requests.single.url.path,
      '/api/v1/me/medications/med-1/deactivate',
    );
    expect(result.isActive, isFalse);
  });

  test('reactivateMedication patches is_active true for undo', () async {
    final _ScriptedClient client = _ScriptedClient(<_StubResponse>[
      _StubResponse(statusCode: 200, body: _medicationJson('med-1')),
    ]);
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: client,
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    final HomeMedication result = await repository.reactivateMedication('med-1');

    final http.Request request = client.requests.single as http.Request;
    final Map<String, dynamic> body =
        jsonDecode(request.body) as Map<String, dynamic>;
    expect(request.url.path, '/api/v1/me/medications/med-1');
    expect(body['is_active'], isTrue);
    expect(result.isActive, isTrue);
  });

  test('deactivateMedication rejects a blank id before sending', () async {
    final _ScriptedClient client = _ScriptedClient(<_StubResponse>[]);
    final ApiClient apiClient = ApiClient(
      baseUrl: 'http://localhost:8000/api/v1',
      httpClient: client,
    );
    addTearDown(apiClient.close);
    final BackendLemonAidRepository repository = BackendLemonAidRepository(
      apiClient: apiClient,
    );

    expect(() => repository.deactivateMedication('  '), throwsArgumentError);
    expect(client.requests, isEmpty);
  });
}

Map<String, Object?> _medicationJson(String id, {bool isActive = true}) {
  return <String, Object?>{
    'id': id,
    'display_name': '아모디핀',
    'medication_class': 'calcium_channel_blocker',
    'condition_tags': <String>['hypertension'],
    'confirmation_status': 'user_confirmed',
    'is_active': isActive,
    'last_confirmed_at': '2026-06-10T00:00:00Z',
    'created_at': '2026-06-10T00:00:00Z',
    'updated_at': '2026-06-10T00:00:00Z',
  };
}

class _StubResponse {
  const _StubResponse({required this.statusCode, required this.body});

  final int statusCode;
  final Map<String, Object?> body;
}

class _ScriptedClient extends http.BaseClient {
  _ScriptedClient(this._responses);

  final List<_StubResponse> _responses;
  final List<http.BaseRequest> requests = <http.BaseRequest>[];
  int _index = 0;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    requests.add(request);
    if (_index >= _responses.length) {
      throw StateError('No scripted response for request #$_index');
    }
    final _StubResponse stub = _responses[_index];
    _index += 1;
    return http.StreamedResponse(
      Stream<List<int>>.value(utf8.encode(jsonEncode(stub.body))),
      stub.statusCode,
      headers: <String, String>{'content-type': 'application/json'},
    );
  }
}
