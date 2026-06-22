// features/chat/chat_analysis_models.dart — 분석 스냅샷 typed 모델
//
// `/ai-agent/chat` 응답의 `today_analysis`(today-analysis-snapshot-v1) 와
// `smart_analysis`(health-analysis-snapshot-v1) opaque map 을 챗 인라인 카드가
// 쓰기 좋은 typed 모델로 변환한다. 모든 fromJson 은 null-safe — 필드 누락/타입
// 불일치 시 빈 값으로 떨어진다. (가이드 05 잔여 (a))
//
// 의료법 가드: 점수는 서버가 준 값만 노출(날조 금지), % 미노출, 등급 라벨은
// 가공 없는 한국어 안내. priority_adjustments / strengths / missing_records 등
// 서버 코드 문자열은 display 헬퍼에서만 안전한 한국어로 매핑한다.

/// Typed view of the `today_analysis` snapshot block.
class ChatTodayAnalysis {
  /// Creates a today-analysis snapshot view.
  ChatTodayAnalysis({
    required this.status,
    required this.score,
    required this.scoreName,
    required this.strengths,
    required this.priorityAdjustments,
    required this.recommendedFoods,
    required this.checklistActions,
    required this.missingRecords,
    required this.stale,
  });

  /// Parses the snapshot from a decoded JSON object (null-safe).
  factory ChatTodayAnalysis.fromJson(Map<String, dynamic> json) {
    return ChatTodayAnalysis(
      status: _string(json['status']),
      score: _intOrNull(json['score']),
      scoreName: _string(json['score_name']),
      strengths: _stringList(json['strengths']),
      priorityAdjustments: _stringList(json['priority_adjustments']),
      recommendedFoods: _stringList(json['recommended_foods']),
      checklistActions: _stringList(json['checklist_actions']),
      missingRecords: _stringList(json['missing_records']),
      stale: json['stale'] == true,
    );
  }

  /// `analysis_pending` (점수 null) 또는 `ready_for_analysis`.
  final String status;

  /// Server-provided integer score, or null when analysis is pending.
  final int? score;

  /// Server-provided Korean score label (e.g. "오늘 현재 분석 점수").
  final String scoreName;

  /// Strength codes surfaced by the backend.
  final List<String> strengths;

  /// Priority adjustment (nutrient axis) codes.
  final List<String> priorityAdjustments;

  /// Recommended food strings (as supplied by the backend).
  final List<String> recommendedFoods;

  /// Checklist action strings.
  final List<String> checklistActions;

  /// Missing record codes that block scoring.
  final List<String> missingRecords;

  /// Whether the snapshot is stale.
  final bool stale;

  /// Whether the backend withheld a score (pending) or sent none.
  bool get isPending => status == 'analysis_pending' || score == null;

  /// Whether the snapshot carries any displayable content.
  bool get isEmpty =>
      status.isEmpty &&
      score == null &&
      strengths.isEmpty &&
      priorityAdjustments.isEmpty &&
      missingRecords.isEmpty &&
      checklistActions.isEmpty &&
      recommendedFoods.isEmpty;
}

/// Typed view of the `smart_analysis` snapshot block.
class ChatSmartAnalysis {
  /// Creates a smart (health) analysis snapshot view.
  ChatSmartAnalysis({
    required this.readinessLevel,
    required this.coverage,
    required this.strengths,
    required this.nutrientPriorities,
    required this.recommendedFoods,
    required this.checklistActions,
    required this.chatSignalStages,
  });

  /// Parses the snapshot from a decoded JSON object (null-safe).
  factory ChatSmartAnalysis.fromJson(Map<String, dynamic> json) {
    return ChatSmartAnalysis(
      readinessLevel: _string(json['readiness_level']),
      coverage: _coverage(json['coverage']),
      strengths: _stringList(json['strengths']),
      nutrientPriorities: _stringList(json['nutrient_priorities']),
      recommendedFoods: _stringList(json['recommended_foods']),
      checklistActions: _stringList(json['checklist_actions']),
      chatSignalStages: _stringList(json['chat_signal_stages']),
    );
  }

  /// Readiness level code (e.g. `level_2_recent_pattern`).
  final String readinessLevel;

  /// Coverage flags keyed by axis (`food`/`supplement`/`checklist`/`chat_signals`).
  final Map<String, bool> coverage;

  /// Strength codes surfaced by the backend.
  final List<String> strengths;

  /// Nutrient priority (axis) codes.
  final List<String> nutrientPriorities;

  /// Recommended food strings (as supplied by the backend).
  final List<String> recommendedFoods;

  /// Checklist action strings.
  final List<String> checklistActions;

  /// Chat signal stage codes.
  final List<String> chatSignalStages;

  /// Number of covered axes (0–4).
  int get coveredCount => coverage.values.where((bool v) => v).length;

  /// Whether the snapshot carries any displayable content.
  bool get isEmpty =>
      readinessLevel.isEmpty &&
      coveredCount == 0 &&
      nutrientPriorities.isEmpty &&
      strengths.isEmpty &&
      recommendedFoods.isEmpty &&
      checklistActions.isEmpty;
}

String _string(Object? value) {
  return value is String ? value : '';
}

int? _intOrNull(Object? value) {
  if (value is int) {
    return value;
  }
  if (value is num) {
    return value.toInt();
  }
  return null;
}

List<String> _stringList(Object? value) {
  if (value is! List<dynamic>) {
    return <String>[];
  }
  return value.whereType<String>().toList(growable: false);
}

Map<String, bool> _coverage(Object? value) {
  if (value is! Map<dynamic, dynamic>) {
    return <String, bool>{};
  }
  final Map<String, bool> result = <String, bool>{};
  value.forEach((dynamic key, dynamic item) {
    if (item is bool) {
      result[key.toString()] = item;
    }
  });
  return result;
}
