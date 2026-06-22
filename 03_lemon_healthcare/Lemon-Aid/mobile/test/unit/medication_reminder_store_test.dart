import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/core/storage/local_prefs.dart';
import 'package:lemon_aid_mobile/features/reminders/medication_reminder_models.dart';
import 'package:lemon_aid_mobile/features/reminders/medication_reminder_store.dart';
import 'package:lemon_aid_mobile/shared/services/local_notification_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('MedicationReminder JSON round-trip', () {
    test('serializes and restores all fields including weekdays', () {
      const MedicationReminder reminder = MedicationReminder(
        id: 'rem-1',
        hour: 9,
        minute: 30,
        weekdays: <int>{1, 3, 5},
        enabled: false,
        label: '오메가3',
        serverId: 'srv-9',
      );

      final MedicationReminder restored =
          MedicationReminder.fromJson(reminder.toJson());

      expect(restored.id, 'rem-1');
      expect(restored.hour, 9);
      expect(restored.minute, 30);
      expect(restored.weekdays, <int>{1, 3, 5});
      expect(restored.enabled, isFalse);
      expect(restored.label, '오메가3');
      expect(restored.serverId, 'srv-9');
      expect(restored.timeOfDay, '09:30');
    });

    test('clamps out-of-range hour and minute', () {
      final MedicationReminder restored = MedicationReminder.fromJson(
        <String, dynamic>{
          'id': 'r',
          'hour': 99,
          'minute': -4,
          'weekdays': <int>[1, 8, 0],
        },
      );

      expect(restored.hour, 23);
      expect(restored.minute, 0);
      // 8 과 0 은 무시되어 1 만 남는다.
      expect(restored.weekdays, <int>{1});
    });
  });

  group('MedicationReminder.nextOccurrence (weekday x time)', () {
    test('returns the next matching weekday/time after the reference', () {
      // 2026-06-12 는 금요일(weekday 5).
      const MedicationReminder reminder = MedicationReminder(
        id: 'r',
        hour: 8,
        minute: 0,
        weekdays: <int>{1}, // 월요일만
      );
      final DateTime from = DateTime(2026, 6, 12, 9); // 금 09:00
      final DateTime? next = reminder.nextOccurrence(from);

      expect(next, isNotNull);
      expect(next!.weekday, DateTime.monday);
      expect(next, DateTime(2026, 6, 15, 8)); // 다음 월요일 08:00
    });

    test('rolls to next week when today time already passed', () {
      // 금요일 reminder, 같은 날 시간이 지난 경우 → 다음 주 금요일.
      const MedicationReminder reminder = MedicationReminder(
        id: 'r',
        hour: 7,
        minute: 0,
        weekdays: <int>{5},
      );
      final DateTime from = DateTime(2026, 6, 12, 9); // 금 09:00 (07:00 지남)
      final DateTime? next = reminder.nextOccurrence(from);

      expect(next, DateTime(2026, 6, 19, 7)); // 다음 금요일 07:00
    });

    test('returns null when no weekdays selected', () {
      const MedicationReminder reminder = MedicationReminder(
        id: 'r',
        hour: 7,
        minute: 0,
        weekdays: <int>{},
      );
      expect(reminder.nextOccurrence(DateTime(2026, 6, 12)), isNull);
    });
  });

  group('buildScheduleEntries', () {
    test('emits one entry per weekday for enabled reminders only', () {
      const List<MedicationReminder> reminders = <MedicationReminder>[
        MedicationReminder(
          id: 'a',
          hour: 8,
          minute: 0,
          weekdays: <int>{1, 2, 3},
        ),
        MedicationReminder(
          id: 'b',
          hour: 20,
          minute: 0,
          weekdays: <int>{7},
          enabled: false, // 비활성 → 제외
        ),
      ];

      final List<ScheduledNotification> entries =
          buildScheduleEntries(reminders);

      expect(entries, hasLength(3));
      expect(entries.map((ScheduledNotification e) => e.weekday), <int>[1, 2, 3]);
      // id 는 reminder 별로 유니크해야 한다.
      expect(entries.map((ScheduledNotification e) => e.id).toSet(), hasLength(3));
    });
  });

  group('MedicationReminderStore persistence', () {
    test('saves and loads reminders via LocalPrefs', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final LocalPrefs prefs = await LocalPrefs.create();
      final MedicationReminderStore store = MedicationReminderStore(
        prefs: prefs,
      );

      await store.save(<MedicationReminder>[
        const MedicationReminder(
          id: 'rem-1',
          hour: 9,
          minute: 0,
          weekdays: <int>{1, 2},
        ),
      ]);

      final List<MedicationReminder> loaded =
          MedicationReminderStore(prefs: prefs).load();
      expect(loaded, hasLength(1));
      expect(loaded.single.id, 'rem-1');
      expect(loaded.single.weekdays, <int>{1, 2});
    });

    test('upsert replaces an existing reminder by id', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final LocalPrefs prefs = await LocalPrefs.create();
      final MedicationReminderStore store = MedicationReminderStore(
        prefs: prefs,
      );

      await store.save(<MedicationReminder>[
        const MedicationReminder(
          id: 'rem-1',
          hour: 9,
          minute: 0,
          weekdays: <int>{1},
        ),
      ]);
      final List<MedicationReminder> after = await store.upsert(
        const MedicationReminder(
          id: 'rem-1',
          hour: 21,
          minute: 30,
          weekdays: <int>{6, 7},
        ),
      );

      expect(after, hasLength(1));
      expect(after.single.hour, 21);
      expect(after.single.weekdays, <int>{6, 7});
    });
  });
}
