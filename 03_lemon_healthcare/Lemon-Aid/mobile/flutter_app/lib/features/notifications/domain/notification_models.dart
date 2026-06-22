enum ReminderCategory {
  supplementReminder('supplement_reminder', '영양제'),
  mealCheckIn('meal_check_in', '식사 확인'),
  dailyCoachingPrompt('daily_coaching_prompt', '오늘의 코칭'),
  safetyFollowUp('safety_follow_up', '주의 확인');

  const ReminderCategory(this.apiValue, this.label);

  final String apiValue;
  final String label;

  static ReminderCategory fromApiValue(String value) {
    return ReminderCategory.values.firstWhere(
      (ReminderCategory category) => category.apiValue == value,
      orElse: () => ReminderCategory.dailyCoachingPrompt,
    );
  }
}

class ReminderPreference {
  ReminderPreference({
    required this.id,
    required this.category,
    required this.timeOfDay,
    required this.timezone,
    required this.enabled,
    required this.message,
  });

  factory ReminderPreference.fromJson(Map<String, dynamic> json) {
    return ReminderPreference(
      id: json['id'] as String? ?? '',
      category: ReminderCategory.fromApiValue(json['category'] as String? ?? ''),
      timeOfDay: json['time_of_day'] as String? ?? '',
      timezone: json['timezone'] as String? ?? 'Asia/Seoul',
      enabled: json['enabled'] as bool? ?? false,
      message: json['message'] as String? ?? '',
    );
  }

  final String id;
  final ReminderCategory category;
  final String timeOfDay;
  final String timezone;
  final bool enabled;
  final String message;
}

class ReminderPreferenceDraft {
  ReminderPreferenceDraft({
    required this.category,
    required this.timeOfDay,
    required this.timezone,
    required this.enabled,
    required this.message,
  });

  final ReminderCategory category;
  final String timeOfDay;
  final String timezone;
  final bool enabled;
  final String message;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'category': category.apiValue,
      'time_of_day': timeOfDay,
      'timezone': timezone,
      'enabled': enabled,
      'message': message,
    };
  }
}
