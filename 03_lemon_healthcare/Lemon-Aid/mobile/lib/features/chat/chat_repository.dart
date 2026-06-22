// features/chat/chat_repository.dart — 레몬봇 챗 API 저장소
//
// `/ai-agent/chat` 호출을 캡슐화한다. 화면은 이 저장소만 호출하고
// 페이로드 구성·동의 재시도·응답 파싱은 모두 여기서 담당한다.

import 'dart:math';

import '../../core/api/api_client.dart';
import '../../core/api/api_error.dart';
import 'chat_models.dart';

/// Backend-facing repository for the chatbot tab.
class ChatRepository {
  /// Creates a chat repository.
  ///
  /// Args:
  ///   apiClient: Minimal API client for `/api/v1`.
  ChatRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  /// Chat endpoint below `/api/v1` (ApiClient base already ends at `/api/v1`).
  static const String _chatPath = '/ai-agent/chat';

  /// Consent grant endpoint for sensitive health analysis.
  static const String _consentPath =
      '/me/privacy/consents/sensitive_health_analysis';

  /// Backend caps conversation history at 24 turns.
  static const int _maxConversationTurns = 24;

  /// Backend caps message length at 4000 characters.
  static const int _maxMessageLength = 4000;

  /// Chat synthesis runs a local-LLM RAG pass (wiki retrieval + Gemma), which is
  /// far slower than a normal request, so it overrides the default 30s timeout.
  static const Duration _chatTimeout = Duration(seconds: 90);

  final ApiClient _apiClient;
  final Random _random = Random();

  /// Sends a chat message and returns the parsed chatbot response.
  ///
  /// On a `403` with `consent_required`, grants the sensitive-health-analysis
  /// consent once and retries the original request.
  ///
  /// Args:
  ///   message: User message (trimmed and capped at 4000 characters).
  ///   conversation: Prior turns; trimmed to the most recent 24.
  ///   analysisRunApproval: Optional approval payload attached under
  ///     `context.analysis_run_approval` to resume a gated analysis run.
  ///
  /// Returns:
  ///   Parsed [ChatbotResponse].
  ///
  /// Raises:
  ///   ApiError: If the backend returns an unexpected status code.
  Future<ChatbotResponse> sendMessage({
    required String message,
    required List<ChatTurn> conversation,
    Map<String, dynamic>? analysisRunApproval,
  }) async {
    final Map<String, dynamic> body = _composeRequest(
      message: message,
      conversation: conversation,
      analysisRunApproval: analysisRunApproval,
    );
    try {
      return await _postChat(body);
    } on ApiError catch (error) {
      if (!_isConsentRequired(error)) {
        rethrow;
      }
      await _grantSensitiveHealthAnalysisConsent();
      // Retry exactly once after the consent is granted.
      return _postChat(body);
    }
  }

  /// Releases repository resources.
  void close() {
    _apiClient.close();
  }

  Future<ChatbotResponse> _postChat(Map<String, dynamic> body) async {
    final Map<String, dynamic> json = await _apiClient.postJson(
      _chatPath,
      body: body,
      timeout: _chatTimeout,
    );
    return ChatbotResponse.fromJson(json);
  }

  Future<void> _grantSensitiveHealthAnalysisConsent() async {
    await _apiClient.postJson(
      _consentPath,
      expectedStatusCodes: const <int>{201},
    );
  }

  Map<String, dynamic> _composeRequest({
    required String message,
    required List<ChatTurn> conversation,
    Map<String, dynamic>? analysisRunApproval,
  }) {
    final String trimmedMessage = message.trim();
    final String cappedMessage = trimmedMessage.length > _maxMessageLength
        ? trimmedMessage.substring(0, _maxMessageLength)
        : trimmedMessage;
    final List<ChatTurn> recentTurns = conversation.length > _maxConversationTurns
        ? conversation.sublist(conversation.length - _maxConversationTurns)
        : conversation;

    final Map<String, dynamic> context = <String, dynamic>{};
    if (analysisRunApproval != null && analysisRunApproval.isNotEmpty) {
      context['analysis_run_approval'] = analysisRunApproval;
    }

    return <String, dynamic>{
      'request_id': _newRequestId(),
      // The server overrides user_id with the authenticated principal, so a
      // fixed placeholder is sufficient.
      'user_id': 'mobile-client',
      'message': cappedMessage,
      'conversation': recentTurns
          .map((ChatTurn turn) => turn.toJson())
          .toList(growable: false),
      'context': context,
    };
  }

  /// Builds a unique, UUID-ish request id from a timestamp and random suffix.
  String _newRequestId() {
    final int micros = DateTime.now().microsecondsSinceEpoch;
    final int salt = _random.nextInt(1 << 32);
    return 'mobile-chat-$micros-${salt.toRadixString(16)}';
  }

  static bool _isConsentRequired(ApiError error) {
    return error.statusCode == 403 && error.code == 'consent_required';
  }
}
