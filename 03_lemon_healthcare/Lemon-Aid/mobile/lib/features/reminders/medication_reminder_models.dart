// features/reminders/medication_reminder_models.dart — 복약 알림 모델
//
// 가이드 08 (d). 로컬 스케줄이 1차 소스이고 서버(/notifications/reminders)는
// 동기화 사본이다. 각 알림은 시/분 + 요일 반복 set + 활성 토글을 가진다.

/// 단일 복약 알림 항목.
class MedicationReminder {
  /// 복약 알림을 생성한다.
  const MedicationReminder({
    required this.id,
    required this.hour,
    required this.minute,
    required this.weekdays,
    this.enabled = true,
    this.label = '복약 시간',
    this.serverId,
  });

  /// 로컬 식별자 (로컬 알림 id 시드로도 사용).
  final String id;

  /// 시(0~23).
  final int hour;

  /// 분(0~59).
  final int minute;

  /// 반복 요일 집합 (1=월 … 7=일, DateTime.weekday 규약).
  final Set<int> weekdays;

  /// 활성 여부.
  final bool enabled;

  /// 알림 본문 라벨 (대상 약 이름 등).
  final String label;

  /// 서버 reminder_preferences id (동기화 후 채워짐, 없으면 null).
  final String? serverId;

  /// `HH:MM` 형식 시간 문자열.
  String get timeOfDay =>
      '${hour.toString().padLeft(2, '0')}:${minute.toString().padLeft(2, '0')}';

  /// 일부 필드를 교체한 사본을 만든다.
  MedicationReminder copyWith({
    int? hour,
    int? minute,
    Set<int>? weekdays,
    bool? enabled,
    String? label,
    String? serverId,
    bool clearServerId = false,
  }) {
    return MedicationReminder(
      id: id,
      hour: hour ?? this.hour,
      minute: minute ?? this.minute,
      weekdays: weekdays ?? this.weekdays,
      enabled: enabled ?? this.enabled,
      label: label ?? this.label,
      serverId: clearServerId ? null : (serverId ?? this.serverId),
    );
  }

  /// 다음 발화 시각을 계산한다 (요일 × 시간 중 [from] 이후 가장 빠른 시점).
  ///
  /// 반복 요일이 비어 있으면 null. 오늘 해당 시간이 이미 지났으면 다음 발화 요일로
  /// 넘어간다. 최대 7일 안에 반드시 한 번은 발화하므로 7회 루프로 충분하다.
  DateTime? nextOccurrence(DateTime from) {
    if (weekdays.isEmpty) return null;
    for (int offset = 0; offset < 8; offset += 1) {
      final DateTime day = DateTime(
        from.year,
        from.month,
        from.day,
      ).add(Duration(days: offset));
      if (!weekdays.contains(day.weekday)) continue;
      final DateTime candidate = DateTime(
        day.year,
        day.month,
        day.day,
        hour,
        minute,
      );
      if (candidate.isAfter(from)) return candidate;
    }
    return null;
  }

  /// JSON 으로 직렬화한다 (shared_preferences 저장용).
  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'id': id,
      'hour': hour,
      'minute': minute,
      'weekdays': weekdays.toList(growable: false)..sort(),
      'enabled': enabled,
      'label': label,
      if (serverId != null) 'server_id': serverId,
    };
  }

  /// JSON 에서 복원한다.
  factory MedicationReminder.fromJson(Map<String, dynamic> json) {
    final Object? rawWeekdays = json['weekdays'];
    final Set<int> weekdays = <int>{};
    if (rawWeekdays is List<Object?>) {
      for (final Object? value in rawWeekdays) {
        if (value is int && value >= 1 && value <= 7) weekdays.add(value);
        if (value is num && value >= 1 && value <= 7) weekdays.add(value.toInt());
      }
    }
    return MedicationReminder(
      id: (json['id'] as Object?)?.toString() ?? '',
      hour: _clampInt(json['hour'], 0, 23),
      minute: _clampInt(json['minute'], 0, 59),
      weekdays: weekdays,
      enabled: json['enabled'] is bool ? json['enabled'] as bool : true,
      label: (json['label'] as Object?)?.toString() ?? '복약 시간',
      serverId: (json['server_id'] as Object?)?.toString(),
    );
  }

  static int _clampInt(Object? value, int lo, int hi) {
    int parsed;
    if (value is int) {
      parsed = value;
    } else if (value is num) {
      parsed = value.toInt();
    } else if (value is String) {
      parsed = int.tryParse(value.trim()) ?? lo;
    } else {
      parsed = lo;
    }
    if (parsed < lo) return lo;
    if (parsed > hi) return hi;
    return parsed;
  }
}
