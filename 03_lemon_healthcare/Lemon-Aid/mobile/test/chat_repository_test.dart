import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:lemon_aid_mobile/core/api/api_client.dart';
import 'package:lemon_aid_mobile/features/chat/chat_models.dart';
import 'package:lemon_aid_mobile/features/chat/chat_repository.dart';

/// Configurable [http.BaseClient] fake so tests do not depend on a real socket.
class _FakeClient extends http.BaseClient {
  _FakeClient(this.handler);

  final Future<http.StreamedResponse> Function(http.Request request) handler;
  final List<http.Request> requests = <http.Request>[];

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final http.Request typed = request as http.Request;
    // Materialize the body so assertions can read it after send returns.
    requests.add(typed);
    return handler(typed);
  }
}

http.StreamedResponse _jsonResponse(
  Map<String, dynamic> body,
  int status,
) {
  return http.StreamedResponse(
    Stream<List<int>>.value(utf8.encode(jsonEncode(body))),
    status,
    headers: const <String, String>{'content-type': 'application/json'},
  );
}

Map<String, dynamic> _answerableResponse() {
  return <String, dynamic>{
    'request_id': 'chat-1',
    'message': '확인된 근거 기반 안내예요.',
    'provider': 'sglang',
    'used_tools': <String>['chatbot_agent'],
    'safety_warnings': <String>[],
    'source_families': <String>['nutrition_reference'],
    'answerability': 'answerable',
    'sources': <Map<String, dynamic>>[
      <String, dynamic>{'title': '식품영양 가이드', 'source_id': 'kfda-001'},
    ],
    'requires_user_approval': false,
    'ctas': <String>['오늘 식단도 봐줘', '영양제 같이 봐줘'],
  };
}

ChatRepository _repositoryFor(_FakeClient client) {
  return ChatRepository(
    apiClient: ApiClient(
      baseUrl: 'https://api.example.com/api/v1',
      httpClient: client,
    ),
  );
}

void main() {
  group('ChatRepository.sendMessage', () {
    test('posts a spec-shaped payload to /ai-agent/chat and parses the response',
        () async {
      final _FakeClient client = _FakeClient((http.Request request) async {
        return _jsonResponse(_answerableResponse(), 200);
      });
      final ChatRepository repository = _repositoryFor(client);

      final ChatbotResponse response = await repository.sendMessage(
        message: '비타민 D 얼마나 먹어야 해?',
        conversation: <ChatTurn>[
          ChatTurn(
            role: 'user',
            content: '안녕',
            createdAt: DateTime.utc(2026, 6, 1, 9),
          ),
        ],
      );

      // Path: ApiClient base already ends at /api/v1.
      expect(client.requests, hasLength(1));
      final http.Request sent = client.requests.single;
      expect(sent.method, 'POST');
      expect(sent.url.path, '/api/v1/ai-agent/chat');

      final Map<String, dynamic> body =
          jsonDecode(sent.body) as Map<String, dynamic>;
      expect(body['user_id'], 'mobile-client');
      expect(body['message'], '비타민 D 얼마나 먹어야 해?');
      expect((body['request_id'] as String).isNotEmpty, isTrue);
      expect(body['context'], <String, dynamic>{});
      final List<dynamic> conversation = body['conversation'] as List<dynamic>;
      expect(conversation, hasLength(1));
      final Map<String, dynamic> turn =
          conversation.single as Map<String, dynamic>;
      expect(turn['role'], 'user');
      expect(turn['content'], '안녕');
      expect(turn['created_at'], '2026-06-01T09:00:00.000Z');

      // Parsing.
      expect(response.provider, 'sglang');
      expect(response.message, '확인된 근거 기반 안내예요.');
      expect(response.isAnswerable, isTrue);
      expect(response.sources.single.label, '식품영양 가이드');
      expect(response.ctas, <String>['오늘 식단도 봐줘', '영양제 같이 봐줘']);
    });

    test('trims conversation history to the most recent 24 turns', () async {
      final _FakeClient client = _FakeClient((http.Request request) async {
        return _jsonResponse(_answerableResponse(), 200);
      });
      final ChatRepository repository = _repositoryFor(client);

      final List<ChatTurn> longHistory = <ChatTurn>[
        for (int i = 0; i < 30; i += 1)
          ChatTurn(
            role: i.isEven ? 'user' : 'assistant',
            content: 'turn-$i',
            createdAt: DateTime.utc(2026, 6, 1).add(Duration(minutes: i)),
          ),
      ];

      await repository.sendMessage(
        message: '최근 질문',
        conversation: longHistory,
      );

      final Map<String, dynamic> body =
          jsonDecode(client.requests.single.body) as Map<String, dynamic>;
      final List<dynamic> conversation = body['conversation'] as List<dynamic>;
      expect(conversation, hasLength(24));
      expect(
        (conversation.first as Map<String, dynamic>)['content'],
        'turn-6',
        reason: 'oldest 6 turns are dropped, keeping the most recent 24',
      );
      expect(
        (conversation.last as Map<String, dynamic>)['content'],
        'turn-29',
      );
    });

    test('attaches analysis_run_approval under context when provided', () async {
      final _FakeClient client = _FakeClient((http.Request request) async {
        return _jsonResponse(_answerableResponse(), 200);
      });
      final ChatRepository repository = _repositoryFor(client);

      await repository.sendMessage(
        message: '분석 실행',
        conversation: <ChatTurn>[],
        analysisRunApproval: <String, dynamic>{
          'approved': true,
          'analysis_kind': 'today_nutrition',
        },
      );

      final Map<String, dynamic> body =
          jsonDecode(client.requests.single.body) as Map<String, dynamic>;
      expect(
        body['context'],
        <String, dynamic>{
          'analysis_run_approval': <String, dynamic>{
            'approved': true,
            'analysis_kind': 'today_nutrition',
          },
        },
      );
    });

    test('parses an approval-required preview from the response', () async {
      final _FakeClient client = _FakeClient((http.Request request) async {
        final Map<String, dynamic> payload = _answerableResponse()
          ..['answerability'] = 'needs_more_info'
          ..['requires_user_approval'] = true
          ..['approval_preview'] = <String, dynamic>{
            'required': true,
            'approval_state': 'approval_required',
            'analysis_kind': 'today_nutrition',
            'snapshot_preview': <String, dynamic>{'kcal': 1800},
            'side_effects': <String>['오늘 분석 갱신'],
          };
        return _jsonResponse(payload, 200);
      });
      final ChatRepository repository = _repositoryFor(client);

      final ChatbotResponse response = await repository.sendMessage(
        message: '오늘 분석해줘',
        conversation: <ChatTurn>[],
      );

      expect(response.isAnswerable, isFalse);
      expect(response.needsAnalysisApproval, isTrue);
      expect(response.approvalPreview.analysisKind, 'today_nutrition');
      expect(response.approvalPreview.sideEffects, <String>['오늘 분석 갱신']);
    });

    test(
      'grants sensitive-health consent once on 403 consent_required and retries',
      () async {
        final List<String> calledPaths = <String>[];
        final _FakeClient client = _FakeClient((http.Request request) async {
          calledPaths.add(request.url.path);
          if (request.url.path.endsWith('/ai-agent/chat') &&
              calledPaths
                      .where((String p) => p.endsWith('/ai-agent/chat'))
                      .length ==
                  1) {
            // First chat attempt is gated on the sensitive-health consent.
            // FastAPI wraps the error under `detail`, where ApiError reads code.
            return _jsonResponse(
              <String, dynamic>{
                'detail': <String, dynamic>{
                  'code': 'consent_required',
                  'message': '민감 건강정보 분석 동의가 필요해요.',
                  'required_consents': <String>['sensitive_health_analysis'],
                },
              },
              403,
            );
          }
          if (request.url.path.endsWith('/sensitive_health_analysis')) {
            return _jsonResponse(<String, dynamic>{'granted': true}, 201);
          }
          // Retry after consent succeeds.
          return _jsonResponse(_answerableResponse(), 200);
        });
        final ChatRepository repository = _repositoryFor(client);

        final ChatbotResponse response = await repository.sendMessage(
          message: '오늘 저녁은?',
          conversation: <ChatTurn>[],
        );

        expect(calledPaths, <String>[
          '/api/v1/ai-agent/chat',
          '/api/v1/me/privacy/consents/sensitive_health_analysis',
          '/api/v1/ai-agent/chat',
        ]);
        expect(response.message, '확인된 근거 기반 안내예요.');
      },
    );
  });
}
