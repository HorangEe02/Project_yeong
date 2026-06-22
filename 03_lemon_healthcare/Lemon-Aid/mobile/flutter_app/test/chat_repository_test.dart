import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_healthcare/core/network/lemon_api_client.dart';
import 'package:lemon_healthcare/features/chat/data/chat_repository.dart';
import 'package:lemon_healthcare/features/chat/domain/chat_models.dart';

void main() {
  test('chat repository posts consent and chatbot request to backend', () async {
    final _FakeApiClient client = _FakeApiClient(
      responses: <_FakeResponse>[
        _FakeResponse(statusCode: 201, data: <String, dynamic>{'status': 'granted'}),
        _FakeResponse(
          statusCode: 200,
          data: <String, dynamic>{
            'request_id': 'chat-1',
            'message': '검수 근거 기반 답변입니다.',
            'provider': 'sglang',
            'used_tools': <String>['chatbot_agent'],
            'safety_warnings': <String>[],
            'source_families': <String>['nutrition_reference'],
            'answerability': 'answerable',
            'sources': <Map<String, dynamic>>[],
            'requires_user_approval': false,
            'ctas': <String>[],
          },
        ),
      ],
    );
    final ChatRepository repository = ChatRepository(client: client);

    await repository.grantSensitiveHealthAnalysisConsent();
    final ChatbotResponse response = await repository.sendMessage(
      ChatbotRequest.compose(message: '오늘 저녁은?', conversation: <ChatTurn>[]),
    );

    expect(client.paths, <String>[
      '/api/v1/me/privacy/consents/sensitive_health_analysis',
      '/api/v1/ai-agent/chat',
    ]);
    expect(response.provider, 'sglang');
    expect(response.message, '검수 근거 기반 답변입니다.');
  });

  test('chat repository throws instead of rendering auth failures as answers',
      () async {
    final ChatRepository repository = ChatRepository(
      client: _FakeApiClient(
        responses: <_FakeResponse>[
          _FakeResponse(
            statusCode: 401,
            data: <String, dynamic>{'detail': 'Not authenticated'},
          ),
        ],
      ),
    );

    expect(
      repository.grantSensitiveHealthAnalysisConsent(),
      throwsA(isA<ChatRepositoryException>()),
    );
  });
}

class _FakeApiClient implements LemonApiClient {
  _FakeApiClient({required List<_FakeResponse> responses})
      : _responses = List<_FakeResponse>.of(responses);

  final List<_FakeResponse> _responses;
  final List<String> paths = <String>[];

  @override
  Future<Response<Map<String, dynamic>>> postJson(
    String path,
    Map<String, dynamic> body,
  ) async {
    paths.add(path);
    final _FakeResponse response = _responses.removeAt(0);
    return Response<Map<String, dynamic>>(
      requestOptions: RequestOptions(path: path),
      statusCode: response.statusCode,
      data: response.data,
    );
  }

  @override
  Future<Response<Map<String, dynamic>>> getJson(String path) {
    throw UnimplementedError();
  }

  @override
  Future<Response<Map<String, dynamic>>> patchJson(
    String path,
    Map<String, dynamic> body,
  ) {
    throw UnimplementedError();
  }

  @override
  Future<Response<Map<String, dynamic>>> postMultipart(String path, FormData body) {
    throw UnimplementedError();
  }
}

class _FakeResponse {
  _FakeResponse({required this.statusCode, required this.data});

  final int statusCode;
  final Map<String, dynamic> data;
}
