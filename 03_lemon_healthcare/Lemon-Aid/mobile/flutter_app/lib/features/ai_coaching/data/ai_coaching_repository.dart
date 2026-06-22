import '../../../core/config/app_config.dart';
import '../../../core/network/lemon_api_client.dart';
import '../domain/ai_coaching_models.dart';

class AiCoachingRepository {
  AiCoachingRepository({
    LemonApiClient? client,
    AppConfig? config,
  }) : _client = client ??
            LemonApiClient(config: config ?? AppConfig.fromEnvironment());

  final LemonApiClient _client;

  Future<void> grantSensitiveHealthAnalysisConsent() async {
    await _client.postJson(
      '/api/v1/me/privacy/consents/sensitive_health_analysis',
      <String, dynamic>{},
    );
  }

  Future<DailyCoachingResponse> runDailyCoaching(
    DailyCoachingRequest request,
  ) async {
    final response = await _client.postJson(
      '/api/v1/ai-agent/daily-coaching',
      request.toJson(),
    );
    return DailyCoachingResponse.fromJson(response.data ?? <String, dynamic>{});
  }
}
