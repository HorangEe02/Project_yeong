import '../domain/activity_models.dart';

class ActivityRepository {
  ConfirmedActivityEntry createManualActivity({
    required DateTime date,
    required int steps,
    required int activeMinutes,
    required int activityEnergyKcal,
    required String workoutType,
    required bool userConfirmed,
  }) {
    return ConfirmedActivityEntry(
      date: date,
      steps: steps,
      activeMinutes: activeMinutes,
      activityEnergyKcal: activityEnergyKcal,
      workoutType: workoutType,
      source: 'manual',
      userConfirmed: userConfirmed,
    );
  }
}
