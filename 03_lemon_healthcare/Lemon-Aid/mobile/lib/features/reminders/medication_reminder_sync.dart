// features/reminders/medication_reminder_sync.dart — 복약 알림 서버 동기화
//
// 가이드 08 (d) + 현재 상태: notifications 라우트가 백엔드에 등록되어 있다
// (POST/GET/PATCH/{id}/disable /notifications/reminders, ReminderCategory 4종,
// 금칙어 검증 존재). 로컬 스케줄이 1차 소스이고 서버는 동기화 사본이다.
//
// 정책(요청 컨텍스트): 생성/토글 시 서버에도 반영하되, 서버 실패 시 로컬은
// 유지하고 호출자에게 재시도 안내만 한다 — 자동 무한 재시도는 하지 않는다.
//
// 서버 reminder_preferences 는 단일 time_of_day(HH:MM)만 저장하고 요일 반복
// 필드가 없으므로, 요일 set 은 로컬에만 두고 서버에는 시간·메시지만 보낸다.

import '../../core/api/api_client.dart';
import 'medication_reminder_models.dart';

/// 복약 알림 서버 동기화 결과.
class ReminderSyncResult {
  /// 동기화 결과를 생성한다.
  const ReminderSyncResult({required this.serverId, required this.synced});

  /// 서버 reminder id (실패 시 기존 값 또는 null).
  final String? serverId;

  /// 서버 반영 성공 여부.
  final bool synced;
}

/// `/notifications/reminders` 동기화 저장소 (서버는 동기화 사본).
class MedicationReminderSync {
  /// API 클라이언트를 주입받아 생성한다.
  MedicationReminderSync({required ApiClient apiClient})
    : _apiClient = apiClient;

  /// 알림 경로 (ApiClient base 가 이미 `/api/v1` 로 끝남).
  static const String _remindersPath = '/notifications/reminders';

  /// 복약 알림 서버 카테고리 (ReminderCategory).
  static const String _category = 'supplement_reminder';

  final ApiClient _apiClient;

  /// 로컬 알림 한 건을 서버에 새로 생성해 반영한다.
  ///
  /// ApiClient 는 PATCH 를 지원하지 않으므로 갱신은 (기존 서버 알림 disable 후)
  /// 새 알림 생성으로 처리한다 — 호출자가 [reminder.serverId] 가 있으면 먼저
  /// [disable] 을 호출한 뒤 이 메서드를 호출하면 된다.
  /// 서버 실패 시 예외를 잡아 `synced:false` 를 돌려준다 — 로컬은 유지된다.
  Future<ReminderSyncResult> push(MedicationReminder reminder) async {
    try {
      final Map<String, dynamic> json = await _apiClient.postJson(
        _remindersPath,
        body: <String, dynamic>{
          'category': _category,
          'time_of_day': reminder.timeOfDay,
          'enabled': reminder.enabled,
          'message': _safeMessage(reminder.label),
        },
        expectedStatusCodes: const <int>{201},
      );
      return ReminderSyncResult(
        serverId: (json['id'] as Object?)?.toString(),
        synced: true,
      );
    } on Object {
      // 서버 실패는 로컬을 막지 않는다. 호출자가 재시도 안내를 띄운다.
      return ReminderSyncResult(serverId: reminder.serverId, synced: false);
    }
  }

  /// 서버 알림을 비활성화한다 (POST /{id}/disable). 실패해도 로컬은 유지.
  Future<bool> disable(String serverId) async {
    try {
      await _apiClient.postJson(
        '$_remindersPath/${Uri.encodeComponent(serverId)}/disable',
        expectedStatusCodes: const <int>{200},
      );
      return true;
    } on Object {
      return false;
    }
  }

  /// 금칙어(진단/처방/치료)를 제거한 안전 메시지를 만든다.
  ///
  /// 백엔드 FORBIDDEN_REMINDER_TERMS 검증을 통과하도록 보수적으로 치환한다.
  static String _safeMessage(String label) {
    const List<String> forbidden = <String>[
      '진단',
      '처방',
      '치료',
      'diagnose',
      'prescribe',
      'treat',
      'treatment',
    ];
    String message = label.trim().isEmpty ? '복약 시간이에요' : '${label.trim()} 시간이에요';
    for (final String term in forbidden) {
      message = message.replaceAll(term, '');
    }
    final String collapsed = message.replaceAll(RegExp(r'\s+'), ' ').trim();
    return collapsed.isEmpty ? '복약 시간이에요' : collapsed;
  }
}
