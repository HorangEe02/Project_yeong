import '../../activity/domain/activity_models.dart';
import '../../food/domain/confirmed_food_entry.dart';
import '../../supplement/domain/supplement_analysis_preview.dart';

class DailyCoachingRequest {
  DailyCoachingRequest({
    required this.requestId,
    required this.userId,
    required this.context,
    required this.payload,
  });

  factory DailyCoachingRequest.fromConfirmedInputs({
    required List<ConfirmedFoodEntry> foods,
    required List<SupplementConfirmedInput> supplements,
    List<ConfirmedActivityEntry> activities = const <ConfirmedActivityEntry>[],
  }) {
    final String requestId =
        'mobile-daily-coaching-${DateTime.now().millisecondsSinceEpoch}';
    return DailyCoachingRequest(
      requestId: requestId,
      userId: 'mobile-client-placeholder',
      context: <String, dynamic>{
        'profile': <String, dynamic>{
          'goals': <String>['meal_management'],
        },
      },
      payload: <String, dynamic>{
        'date': DateTime.now().toIso8601String().substring(0, 10),
        'sources': foods
            .map((ConfirmedFoodEntry food) => food.toAgentSourceJson())
            .toList(growable: false),
        'foods': foods
            .map((ConfirmedFoodEntry food) => food.toAgentFoodJson())
            .toList(growable: false),
        'supplements': supplements
            .map(
              (SupplementConfirmedInput supplement) =>
                  supplement.toAgentSupplementJson(),
            )
            .toList(growable: false),
        'health_trends': activities.where(
          (ConfirmedActivityEntry activity) => activity.userConfirmed,
        )
            .map(
              (ConfirmedActivityEntry activity) =>
                  activity.toAgentHealthTrendJson(),
            )
            .toList(growable: false),
      },
    );
  }

  final String requestId;
  final String userId;
  final Map<String, dynamic> context;
  final Map<String, dynamic> payload;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'request_id': requestId,
      'user_id': userId,
      'context': context,
      'payload': payload,
    };
  }
}

class DailyCoachingResponse {
  DailyCoachingResponse({
    required this.requestId,
    required this.status,
    required this.approvalStatus,
    required this.message,
    required this.provider,
    required this.usedTools,
    required this.findings,
    required this.recommendations,
    required this.safetyWarnings,
  });

  factory DailyCoachingResponse.fromJson(Map<String, dynamic> json) {
    return DailyCoachingResponse(
      requestId: json['request_id'] as String? ?? '',
      status: json['status'] as String? ?? 'unknown',
      approvalStatus: json['approval_status'] as String? ?? 'unknown',
      message: json['message'] as String? ?? '',
      provider: json['provider'] as String? ?? 'unknown',
      usedTools: _stringList(json['used_tools']),
      findings: _mapList(json['findings']),
      recommendations: _mapList(json['recommendations']),
      safetyWarnings: _stringList(json['safety_warnings']),
    );
  }

  final String requestId;
  final String status;
  final String approvalStatus;
  final String message;
  final String provider;
  final List<String> usedTools;
  final List<Map<String, dynamic>> findings;
  final List<Map<String, dynamic>> recommendations;
  final List<String> safetyWarnings;

  bool get usedAgentMemory => usedTools.contains('agent_memory');
}

List<String> _stringList(Object? value) {
  if (value is! List<dynamic>) {
    return <String>[];
  }
  return value.whereType<String>().toList(growable: false);
}

List<Map<String, dynamic>> _mapList(Object? value) {
  if (value is! List<dynamic>) {
    return <Map<String, dynamic>>[];
  }
  return value
      .whereType<Map<dynamic, dynamic>>()
      .map((Map<dynamic, dynamic> item) => Map<String, dynamic>.from(item))
      .toList(growable: false);
}
