import '../../../core/config/app_config.dart';
import '../../../core/network/lemon_api_client.dart';
import '../domain/notification_models.dart';

class NotificationRepository {
  NotificationRepository({
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

  Future<List<ReminderPreference>> listReminders() async {
    final response = await _client.getJson('/api/v1/notifications/reminders');
    final Object? items = response.data?['items'];
    if (items is! List<dynamic>) {
      return <ReminderPreference>[];
    }
    return items
        .whereType<Map<dynamic, dynamic>>()
        .map(
          (Map<dynamic, dynamic> item) =>
              ReminderPreference.fromJson(Map<String, dynamic>.from(item)),
        )
        .toList(growable: false);
  }

  Future<ReminderPreference> createReminder(
    ReminderPreferenceDraft draft,
  ) async {
    final response = await _client.postJson(
      '/api/v1/notifications/reminders',
      draft.toJson(),
    );
    return ReminderPreference.fromJson(response.data ?? <String, dynamic>{});
  }

  Future<ReminderPreference> updateReminder(
    String id,
    ReminderPreferenceDraft draft,
  ) async {
    final response = await _client.patchJson(
      '/api/v1/notifications/reminders/$id',
      draft.toJson(),
    );
    return ReminderPreference.fromJson(response.data ?? <String, dynamic>{});
  }

  Future<ReminderPreference> disableReminder(String id) async {
    final response = await _client.postJson(
      '/api/v1/notifications/reminders/$id/disable',
      <String, dynamic>{},
    );
    return ReminderPreference.fromJson(response.data ?? <String, dynamic>{});
  }
}
