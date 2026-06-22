class ConfirmedActivityEntry {
  ConfirmedActivityEntry({
    required this.date,
    required this.steps,
    required this.activeMinutes,
    required this.activityEnergyKcal,
    required this.workoutType,
    required this.source,
    required this.userConfirmed,
  });

  final DateTime date;
  final int steps;
  final int activeMinutes;
  final int activityEnergyKcal;
  final String workoutType;
  final String source;
  final bool userConfirmed;

  Map<String, dynamic> toAgentHealthTrendJson() {
    return <String, dynamic>{
      'metric': 'activity_context',
      'date': date.toIso8601String().substring(0, 10),
      'steps': steps,
      'active_minutes': activeMinutes,
      'activity_energy_kcal': activityEnergyKcal,
      'workout_type': workoutType,
      'source': source,
      'user_confirmed': true,
      'summary':
          '확정된 활동 기록: $steps걸음, 활동 $activeMinutes분, 에너지 ${activityEnergyKcal}kcal',
    };
  }
}
