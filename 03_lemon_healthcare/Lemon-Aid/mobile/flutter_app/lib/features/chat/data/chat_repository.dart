import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/config/app_config.dart';
import '../../../core/network/lemon_api_client.dart';
import '../domain/chat_models.dart';

final Provider<ChatRepository> chatRepositoryProvider =
    Provider<ChatRepository>((Ref<ChatRepository> ref) {
  return ChatRepository();
});

class ChatRepository {
  ChatRepository({
    LemonApiClient? client,
    AppConfig? config,
  }) : _client = client ??
            LemonApiClient(config: config ?? AppConfig.fromEnvironment());

  final LemonApiClient _client;

  Future<void> grantSensitiveHealthAnalysisConsent() async {
    final response = await _client.postJson(
      '/api/v1/me/privacy/consents/sensitive_health_analysis',
      <String, dynamic>{},
    );
    _ensureSuccess(response, 'grant chatbot consent');
  }

  Future<ChatbotResponse> sendMessage(ChatbotRequest request) async {
    final response = await _client.postJson(
      '/api/v1/ai-agent/chat',
      request.toJson(),
    );
    _ensureSuccess(response, 'send chatbot message');
    final Map<String, dynamic>? data = response.data;
    if (data == null) {
      throw const ChatRepositoryException('Chatbot response body was empty.');
    }
    return ChatbotResponse.fromJson(data);
  }

  static void _ensureSuccess(
    Response<Map<String, dynamic>> response,
    String action,
  ) {
    final int? statusCode = response.statusCode;
    if (statusCode == null || statusCode < 200 || statusCode >= 300) {
      throw ChatRepositoryException(
        'Failed to $action. HTTP status: ${statusCode ?? 'unknown'}.',
      );
    }
  }
}

class ChatRepositoryException implements Exception {
  const ChatRepositoryException(this.message);

  final String message;

  @override
  String toString() => message;
}
