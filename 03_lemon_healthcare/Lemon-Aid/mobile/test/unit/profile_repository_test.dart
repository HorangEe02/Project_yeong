import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:lemon_aid_mobile/core/api/api_client.dart';
import 'package:lemon_aid_mobile/features/profile/profile_models.dart';
import 'package:lemon_aid_mobile/features/profile/profile_repository.dart';

/// 요청별로 응답을 구성할 수 있는 가짜 HTTP 클라이언트.
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

ProfileRepository _repoFor(_FakeClient client) {
  return ProfileRepository(
    apiClient: ApiClient(
      baseUrl: 'https://api.example.com/api/v1',
      httpClient: client,
    ),
  );
}

void main() {
  group('ProfileRepository.fetchLatest', () {
    test('maps {"status":"not_ready"} to null', () async {
      final _FakeClient client = _FakeClient(
        (http.Request request) async =>
            _json(<String, dynamic>{'status': 'not_ready'}, 200),
      );

      final BodyProfileSnapshot? snapshot = await _repoFor(client).fetchLatest();

      expect(snapshot, isNull);
      expect(
        client.requests.single.url.path,
        '/api/v1/health/profile-snapshots/latest',
      );
    });

    test('parses a populated snapshot', () async {
      final _FakeClient client = _FakeClient(
        (http.Request request) async => _json(<String, dynamic>{
          'sex': 'female',
          'birth_year': 1985,
          'height_cm': '165.50',
          'weight_kg': '58.20',
          'activity_level': 'active',
        }, 200),
      );

      final BodyProfileSnapshot? snapshot = await _repoFor(client).fetchLatest();

      expect(snapshot, isNotNull);
      expect(snapshot!.sex, ProfileSex.female);
      expect(snapshot.birthYear, 1985);
      expect(snapshot.heightCm, 165.5);
      expect(snapshot.weightKg, 58.2);
      expect(snapshot.summaryLine(), '165.5cm · 58.2kg');
    });
  });

  group('ProfileRepository.save', () {
    test('serializes decimals as fixed-2 strings and fixes source=manual',
        () async {
      final _FakeClient client = _FakeClient(
        (http.Request request) async => _json(<String, dynamic>{
          'id': 'p1',
          'effective_at': '2026-06-12T00:00:00Z',
          'height_cm': '172.00',
          'weight_kg': '68.00',
        }, 201),
      );

      await _repoFor(client).save(
        const BodyProfileSnapshot(
          sex: ProfileSex.male,
          birthYear: 1990,
          heightCm: 172,
          weightKg: 68,
        ),
      );

      final http.Request sent = client.requests.single;
      expect(sent.method, 'POST');
      expect(sent.url.path, '/api/v1/health/profile-snapshots');
      final Map<String, dynamic> body =
          jsonDecode(sent.body) as Map<String, dynamic>;
      expect(body['source'], 'manual');
      expect(body['sex'], 'male');
      expect(body['birth_year'], 1990);
      expect(body['height_cm'], '172.00');
      expect(body['weight_kg'], '68.00');
      expect(body.containsKey('waist_cm'), isFalse);
    });

    test('grants sensitive-health consent once on 403 and retries', () async {
      final List<String> paths = <String>[];
      final _FakeClient client = _FakeClient((http.Request request) async {
        paths.add(request.url.path);
        final bool isSave =
            request.url.path.endsWith('/health/profile-snapshots');
        final int saveCount =
            paths.where((String p) => p.endsWith('/health/profile-snapshots')).length;
        if (isSave && saveCount == 1) {
          return _json(<String, dynamic>{
            'detail': <String, dynamic>{
              'code': 'consent_required',
              'message': '민감 건강정보 분석 동의가 필요해요.',
              'required_consents': <String>['sensitive_health_analysis'],
            },
          }, 403);
        }
        if (request.url.path.endsWith('/sensitive_health_analysis')) {
          return _json(<String, dynamic>{'granted': true}, 201);
        }
        return _json(<String, dynamic>{'id': 'p1', 'effective_at': '2026-06-12T00:00:00Z'}, 201);
      });

      await _repoFor(client).save(const BodyProfileSnapshot(heightCm: 172));

      expect(paths, <String>[
        '/api/v1/health/profile-snapshots',
        '/api/v1/me/privacy/consents/sensitive_health_analysis',
        '/api/v1/health/profile-snapshots',
      ]);
    });
  });
}
