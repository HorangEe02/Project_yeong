// features/reminders/medication_reminder_store.dart — 복약 알림 로컬 영속
//
// 가이드 08 (d). shared_preferences(LocalPrefs)에 복약 알림 JSON 목록을 저장한다.
// 로컬 스케줄이 1차 소스이며, 서버 reminder_preferences 동기화는 별도
// (medication_reminder_sync) 레이어가 담당한다.

import '../../core/storage/local_prefs.dart';
import 'medication_reminder_models.dart';

/// 복약 알림 목록을 LocalPrefs 에 영속하는 스토어.
class MedicationReminderStore {
  /// LocalPrefs 래퍼를 주입받아 생성한다.
  ///
  /// [prefs] 가 null 이면(아직 로딩 중) 인메모리로만 동작하며 저장은 무시된다.
  MedicationReminderStore({LocalPrefs? prefs}) : _prefs = prefs;

  final LocalPrefs? _prefs;

  /// 저장된 복약 알림 목록을 읽는다.
  List<MedicationReminder> load() {
    final List<Map<String, dynamic>>? raw = _prefs?.medicationReminders();
    if (raw == null) return <MedicationReminder>[];
    return raw
        .map(MedicationReminder.fromJson)
        .where((MedicationReminder r) => r.id.isNotEmpty)
        .toList(growable: false);
  }

  /// 복약 알림 목록 전체를 저장한다.
  Future<void> save(List<MedicationReminder> reminders) async {
    await _prefs?.setMedicationReminders(
      reminders.map((MedicationReminder r) => r.toJson()).toList(growable: false),
    );
  }

  /// 하나의 알림을 추가하거나(같은 id) 교체하고 저장한다.
  Future<List<MedicationReminder>> upsert(MedicationReminder reminder) async {
    final List<MedicationReminder> current = load();
    final int index = current.indexWhere(
      (MedicationReminder r) => r.id == reminder.id,
    );
    final List<MedicationReminder> next = List<MedicationReminder>.of(current);
    if (index >= 0) {
      next[index] = reminder;
    } else {
      next.add(reminder);
    }
    await save(next);
    return next;
  }

  /// 주어진 id 의 알림을 제거하고 저장한다.
  Future<List<MedicationReminder>> remove(String id) async {
    final List<MedicationReminder> next = load()
        .where((MedicationReminder r) => r.id != id)
        .toList(growable: false);
    await save(next);
    return next;
  }
}
