import '../../../core/config/app_config.dart';
import '../../../core/network/lemon_api_client.dart';
import '../domain/user_medication_models.dart';

class UserMedicationRepository {
  UserMedicationRepository({
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

  Future<List<UserMedication>> listMedications() async {
    final response = await _client.getJson('/api/v1/me/medications');
    final Object? items = response.data?['items'];
    if (items is! List<dynamic>) {
      return <UserMedication>[];
    }
    return items
        .whereType<Map<dynamic, dynamic>>()
        .map(
          (Map<dynamic, dynamic> item) =>
              UserMedication.fromJson(Map<String, dynamic>.from(item)),
        )
        .toList(growable: false);
  }

  Future<UserMedication> createMedication(UserMedicationDraft draft) async {
    final response = await _client.postJson(
      '/api/v1/me/medications',
      draft.toJson(),
    );
    return UserMedication.fromJson(response.data ?? <String, dynamic>{});
  }

  Future<UserMedication> deactivateMedication(String id) async {
    final response = await _client.postJson(
      '/api/v1/me/medications/$id/deactivate',
      <String, dynamic>{},
    );
    return UserMedication.fromJson(response.data ?? <String, dynamic>{});
  }
}
