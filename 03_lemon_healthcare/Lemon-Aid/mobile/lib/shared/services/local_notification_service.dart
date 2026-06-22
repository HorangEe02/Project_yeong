// shared/services/local_notification_service.dart — 복약 로컬 알림 서비스
//
// 가이드 08 (d) step 20. flutter_local_notifications 래퍼.
//   - Android 채널 '복약 알림' + iOS Darwin 초기화
//   - 권한 요청 (Android 13+ POST_NOTIFICATIONS, iOS alert/sound/badge)
//   - 요일 × 시간 반복 알림 등록/해제 (zonedSchedule + dayOfWeekAndTime)
//
// 정확 알람은 Android 14+ 에서 기본 거부될 수 있어 inexactAllowWhileIdle 폴백을
// 사용한다(복약 알림은 ±수분 허용). 참조:
//   https://pub.dev/packages/flutter_local_notifications#-android-setup
//   https://pub.dev/packages/flutter_local_notifications#scheduling-a-notification
//
// 알림 실발송은 단위 테스트로 검증 불가하므로 스케줄 호출을 [ReminderScheduler]
// 인터페이스로 분리해 주입 가능하게 했다. 화면은 인터페이스만 의존한다.

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest_all.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

import '../../features/reminders/medication_reminder_models.dart';

/// 한 번의 zonedSchedule 호출에 대응하는 등록 명세 (테스트 검증용).
@immutable
class ScheduledNotification {
  /// 명세를 생성한다.
  const ScheduledNotification({
    required this.id,
    required this.weekday,
    required this.hour,
    required this.minute,
    required this.title,
    required this.body,
  });

  /// 알림 id (reminder.id + weekday 로 결정).
  final int id;

  /// 요일 (1=월 … 7=일).
  final int weekday;

  /// 시.
  final int hour;

  /// 분.
  final int minute;

  /// 알림 제목.
  final String title;

  /// 알림 본문.
  final String body;

  @override
  bool operator ==(Object other) =>
      other is ScheduledNotification &&
      other.id == id &&
      other.weekday == weekday &&
      other.hour == hour &&
      other.minute == minute &&
      other.title == title &&
      other.body == body;

  @override
  int get hashCode => Object.hash(id, weekday, hour, minute, title, body);
}

/// 복약 알림 스케줄러 인터페이스 (주입 가능 → 테스트에서 fake 로 교체).
abstract class ReminderScheduler {
  /// 알림 권한을 요청한다. 허용되면 true.
  Future<bool> ensurePermissions();

  /// 모든 복약 알림을 [reminders] 기준으로 재등록한다 (기존 전체 취소 후 재예약).
  ///
  /// Returns:
  ///   실제로 예약된 명세 목록.
  Future<List<ScheduledNotification>> reschedule(
    List<MedicationReminder> reminders,
  );

  /// 모든 복약 알림을 해제한다.
  Future<void> cancelAll();
}

/// 한 reminder + 요일 조합에 대한 안정적 알림 id 를 만든다.
///
/// reminder.id 해시(0~9999) × 10 + weekday(1~7) 로 충돌 가능성을 줄인다.
int notificationIdFor(String reminderId, int weekday) {
  final int base = (reminderId.hashCode & 0x7fffffff) % 100000;
  return base * 10 + weekday;
}

/// 요일×시간 반복 알림 명세를 계산하는 순수 함수 (실발송과 분리 — 테스트 가능).
///
/// 활성(enabled) 알림의 각 요일마다 하나의 [ScheduledNotification] 을 만든다.
List<ScheduledNotification> buildScheduleEntries(
  List<MedicationReminder> reminders,
) {
  final List<ScheduledNotification> entries = <ScheduledNotification>[];
  for (final MedicationReminder reminder in reminders) {
    if (!reminder.enabled) continue;
    for (final int weekday in (reminder.weekdays.toList()..sort())) {
      entries.add(
        ScheduledNotification(
          id: notificationIdFor(reminder.id, weekday),
          weekday: weekday,
          hour: reminder.hour,
          minute: reminder.minute,
          title: '복약 시간이에요',
          body: '${reminder.label} 챙기셨나요?',
        ),
      );
    }
  }
  return entries;
}

/// flutter_local_notifications 기반 실제 스케줄러.
class LocalNotificationService implements ReminderScheduler {
  /// 플러그인을 주입받거나 기본 인스턴스를 만든다.
  LocalNotificationService({FlutterLocalNotificationsPlugin? plugin})
    : _plugin = plugin ?? FlutterLocalNotificationsPlugin();

  /// 복약 알림 Android 채널 id.
  static const String channelId = 'medication_reminders';

  /// 복약 알림 Android 채널 이름.
  static const String channelName = '복약 알림';

  final FlutterLocalNotificationsPlugin _plugin;
  bool _initialized = false;

  /// 플러그인과 타임존 DB 를 1회 초기화한다.
  Future<void> init() async {
    if (_initialized) return;
    tzdata.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Seoul'));

    const AndroidInitializationSettings android =
        AndroidInitializationSettings('@mipmap/ic_launcher');
    // iOS: 권한은 첫 스케줄 시점에 명시 요청하므로 초기화 단계에서는 요청하지 않는다.
    const DarwinInitializationSettings ios = DarwinInitializationSettings(
      requestAlertPermission: false,
      requestBadgePermission: false,
      requestSoundPermission: false,
    );
    await _plugin.initialize(
      settings: const InitializationSettings(android: android, iOS: ios),
    );
    _initialized = true;
  }

  @override
  Future<bool> ensurePermissions() async {
    await init();
    if (defaultTargetPlatform == TargetPlatform.android) {
      final AndroidFlutterLocalNotificationsPlugin? android = _plugin
          .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin
          >();
      final bool? granted = await android?.requestNotificationsPermission();
      return granted ?? false;
    }
    if (defaultTargetPlatform == TargetPlatform.iOS) {
      final bool? granted = await _plugin
          .resolvePlatformSpecificImplementation<
            IOSFlutterLocalNotificationsPlugin
          >()
          ?.requestPermissions(alert: true, badge: true, sound: true);
      return granted ?? false;
    }
    return false;
  }

  @override
  Future<List<ScheduledNotification>> reschedule(
    List<MedicationReminder> reminders,
  ) async {
    await init();
    await _plugin.cancelAll();
    final List<ScheduledNotification> entries = buildScheduleEntries(reminders);
    for (final ScheduledNotification entry in entries) {
      await _plugin.zonedSchedule(
        id: entry.id,
        title: entry.title,
        body: entry.body,
        scheduledDate: _nextInstanceOf(entry.weekday, entry.hour, entry.minute),
        notificationDetails: const NotificationDetails(
          android: AndroidNotificationDetails(
            channelId,
            channelName,
            channelDescription: '복약 시간에 맞춰 알려드려요',
            importance: Importance.high,
            priority: Priority.high,
          ),
          iOS: DarwinNotificationDetails(),
        ),
        // Android 14+ 정확 알람 거부 대비 — 복약 알림은 ±수분 허용.
        androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
        matchDateTimeComponents: DateTimeComponents.dayOfWeekAndTime,
      );
    }
    return entries;
  }

  @override
  Future<void> cancelAll() async {
    await init();
    await _plugin.cancelAll();
  }

  /// [weekday] 요일 [hour]:[minute] 의 다음 발화 시각(local tz)을 만든다.
  tz.TZDateTime _nextInstanceOf(int weekday, int hour, int minute) {
    final tz.TZDateTime now = tz.TZDateTime.now(tz.local);
    tz.TZDateTime scheduled = tz.TZDateTime(
      tz.local,
      now.year,
      now.month,
      now.day,
      hour,
      minute,
    );
    while (scheduled.weekday != weekday || !scheduled.isAfter(now)) {
      scheduled = scheduled.add(const Duration(days: 1));
    }
    return scheduled;
  }
}
