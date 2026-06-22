import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:lemon_aid_mobile/core/api/api_client.dart';
import 'package:lemon_aid_mobile/core/api/api_error.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_repository.dart';

/// Configurable [http.BaseClient] fake so tests do not depend on a real socket.
class _FakeClient extends http.BaseClient {
  _FakeClient(this.handler);

  final Future<http.StreamedResponse> Function(http.BaseRequest request)
  handler;
  int sendCount = 0;
  http.BaseRequest? lastRequest;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    sendCount += 1;
    lastRequest = request;
    return handler(request);
  }
}

http.StreamedResponse _jsonResponse(Map<String, dynamic> body, int status) {
  return http.StreamedResponse(
    Stream<List<int>>.value(utf8.encode(jsonEncode(body))),
    status,
  );
}

String _writeTempFile(String name, List<int> bytes) {
  final Directory dir = Directory.systemTemp.createTempSync('lemon_api_test');
  final File file = File('${dir.path}/$name')..writeAsBytesSync(bytes);
  return file.path;
}

void main() {
  group('ApiClient robustness', () {
    test('maps a slow response to a 408 ApiError instead of hanging', () async {
      final _FakeClient client = _FakeClient((http.BaseRequest request) async {
        await Future<void>.delayed(const Duration(milliseconds: 300));
        return _jsonResponse(<String, dynamic>{'ok': true}, 200);
      });
      final ApiClient api = ApiClient(
        baseUrl: 'https://api.example.com/api/v1',
        httpClient: client,
        requestTimeout: const Duration(milliseconds: 50),
      );

      await expectLater(
        api.getJson('/dashboard/summary'),
        throwsA(
          isA<ApiError>().having(
            (ApiError e) => e.statusCode,
            'statusCode',
            408,
          ),
        ),
      );
    });

    test('maps a socket failure to a safe network ApiError', () async {
      final _FakeClient client = _FakeClient((http.BaseRequest request) async {
        throw const SocketException('Connection refused');
      });
      final ApiClient api = ApiClient(
        baseUrl: 'https://api.example.com/api/v1',
        httpClient: client,
      );

      await expectLater(
        api.getJson('/dashboard/summary'),
        throwsA(
          isA<ApiError>()
              .having((ApiError e) => e.statusCode, 'statusCode', 0)
              .having((ApiError e) => e.code, 'code', 'network_unavailable')
              .having(
                (ApiError e) => e.message,
                'message',
                contains('서버에 연결하지 못했어요'),
              ),
        ),
      );
    });

    test(
      'maps a package http client failure to a safe network ApiError',
      () async {
        final _FakeClient client = _FakeClient((
          http.BaseRequest request,
        ) async {
          throw http.ClientException('Connection closed before full header');
        });
        final ApiClient api = ApiClient(
          baseUrl: 'https://api.example.com/api/v1',
          httpClient: client,
        );

        await expectLater(
          api.getJson('/dashboard/summary'),
          throwsA(
            isA<ApiError>()
                .having((ApiError e) => e.statusCode, 'statusCode', 0)
                .having((ApiError e) => e.code, 'code', 'network_unavailable')
                .having(
                  (ApiError e) => e.message,
                  'message',
                  contains('서버에 연결하지 못했어요'),
                ),
          ),
        );
      },
    );

    test('rejects an oversized upload before sending (413)', () async {
      final _FakeClient client = _FakeClient((http.BaseRequest request) async {
        return _jsonResponse(<String, dynamic>{'ok': true}, 202);
      });
      final ApiClient api = ApiClient(
        baseUrl: 'https://api.example.com/api/v1',
        httpClient: client,
        maxUploadBytes: 8,
      );
      final String path = _writeTempFile('big.jpg', List<int>.filled(64, 0xFF));

      await expectLater(
        api.postMultipart(
          '/supplements/analyze',
          fileField: 'image',
          filePath: path,
        ),
        throwsA(
          isA<ApiError>().having(
            (ApiError e) => e.statusCode,
            'statusCode',
            413,
          ),
        ),
      );
      expect(client.sendCount, 0, reason: 'must fail fast before any upload');
    });

    test('rejects an unsupported image format with a clear 415', () async {
      final _FakeClient client = _FakeClient((http.BaseRequest request) async {
        return _jsonResponse(<String, dynamic>{'ok': true}, 202);
      });
      final ApiClient api = ApiClient(
        baseUrl: 'https://api.example.com/api/v1',
        httpClient: client,
      );
      // Non-image bytes with an unsupported extension -> sniff + extension both miss.
      final String path = _writeTempFile('label.heic', <int>[0, 1, 2, 3, 4, 5]);

      await expectLater(
        api.postMultipart(
          '/supplements/analyze',
          fileField: 'image',
          filePath: path,
        ),
        throwsA(
          isA<ApiError>().having(
            (ApiError e) => e.statusCode,
            'statusCode',
            415,
          ),
        ),
      );
      expect(client.sendCount, 0, reason: 'unsupported format must not upload');
    });
  });

  group('BackendLemonAidRepository.registerSupplement', () {
    test(
      'POSTs the confirmation to /supplements and maps a 403 to ApiError',
      () async {
        final _FakeClient client = _FakeClient((
          http.BaseRequest request,
        ) async {
          return _jsonResponse(<String, dynamic>{
            'code': 'consent_required',
            'message': 'sensitive health consent required',
          }, 403);
        });
        final BackendLemonAidRepository repository = BackendLemonAidRepository(
          apiClient: ApiClient(
            baseUrl: 'https://api.example.com/api/v1',
            httpClient: client,
          ),
        );

        const UserSupplementCreate request = UserSupplementCreate(
          analysisId: null,
          displayName: 'Vitamin C',
          manufacturer: 'Lemon Labs',
          ingredients: <UserSupplementIngredientInput>[
            UserSupplementIngredientInput(
              displayName: 'Vitamin C',
              nutrientCode: null,
              amount: 1000,
              unit: 'mg',
              confidence: 1,
              source: 'user_confirmed',
            ),
          ],
          serving: SupplementServing(
            amount: 1,
            unit: 'tablet',
            dailyServings: 1,
          ),
          intakeSchedule: SupplementIntakeSchedule(
            frequency: 'daily',
            timeOfDay: <String>[],
          ),
        );

        await expectLater(
          repository.registerSupplement(request),
          throwsA(
            isA<ApiError>().having(
              (ApiError e) => e.statusCode,
              'statusCode',
              403,
            ),
          ),
        );

        final http.BaseRequest? sent = client.lastRequest;
        expect(sent, isNotNull);
        expect(sent!.method, 'POST');
        expect(sent.url.path, endsWith('/supplements'));
        expect(sent.url.path, isNot(endsWith('/supplements/analyze')));
        expect((sent as http.Request).body, contains('Vitamin C'));
      },
    );
  });
}
