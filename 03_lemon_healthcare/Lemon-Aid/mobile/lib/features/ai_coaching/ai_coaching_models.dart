// features/ai_coaching/ai_coaching_models.dart — 오늘의 분석 AgentInput/AgentOutput 모델
//
// 백엔드 `/ai-agent/daily-coaching` 계약을 표현하는 순수 Dart 모델.
//   - DailyCoachingRequest : AgentInput. 당일 확정 식사·등록 영양제를 payload 로 묶는다.
//   - DailyCoachingResult  : AgentOutput. status/approval/findings/recommendations/actions 파싱.
//
// 모든 fromJson 은 null-safe 하게 작성해 서버 응답 변동에 견디게 한다.
// 의료법 가드: 사용자 노출 라벨은 "확인"·"안내"·"근거" 사용 (진단/처방/치료/효능 금지).

/// `/ai-agent/daily-coaching` 요청(AgentInput) 본문.
class DailyCoachingRequest {
  /// 오늘의 분석 요청을 생성한다.
  ///
  /// Args:
  ///   requestId: 호출 추적용 멱등 키.
  ///   date: 분석 기준일 (YYYY-MM-DD).
  ///   foods: 당일 확정 식사 항목 payload 목록.
  ///   supplements: 등록 영양제 payload 목록.
  const DailyCoachingRequest({
    required this.requestId,
    required this.date,
    required this.foods,
    required this.supplements,
  });

  /// 호출 추적용 멱등 키.
  final String requestId;

  /// 분석 기준일 (YYYY-MM-DD).
  final String date;

  /// 당일 확정 식사 항목 payload 목록.
  final List<Map<String, dynamic>> foods;

  /// 등록 영양제 payload 목록.
  final List<Map<String, dynamic>> supplements;

  /// AgentInput 형태로 직렬화한다.
  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'request_id': requestId,
      // 서버가 인증 주체로 user_id 를 덮어쓰므로 고정 placeholder 로 충분하다.
      'user_id': 'mobile-client',
      'payload': <String, dynamic>{
        'date': date,
        // lemon_ai_agent 오케스트레이터는 sources[] 의 user_confirmed 로
        // 확정 여부를 판정한다(미확정 OCR 소스면 preview 로 강등). 앱은
        // 확정 기록만 보내므로 소스 유형별 confirmed 엔트리를 동봉한다.
        'sources': <Map<String, dynamic>>[
          if (foods.isNotEmpty)
            <String, dynamic>{
              'source_type': 'food_user_input',
              'user_confirmed': true,
            },
          if (supplements.isNotEmpty)
            <String, dynamic>{
              'source_type': 'supplement_user_input',
              'user_confirmed': true,
            },
        ],
        'foods': foods,
        'supplements': supplements,
        'health_trends': <Map<String, dynamic>>[],
      },
      'context': <String, dynamic>{
        'profile': <String, dynamic>{
          'goals': <String>['meal_management'],
        },
      },
    };
  }
}

/// 오늘의 분석 한 줄 실천 항목 (recommendation/action 통합 뷰).
class DailyCoachingItem {
  /// 실천 리스트 항목을 생성한다.
  const DailyCoachingItem({
    required this.title,
    required this.subtitle,
    required this.priority,
    required this.requiresUserApproval,
  });

  /// 항목 제목.
  final String title;

  /// 보조 설명 (rationale/category). 없으면 빈 문자열.
  final String subtitle;

  /// 정렬 우선순위 (작을수록 먼저). 미지정은 큰 값으로 뒤로 민다.
  final int priority;

  /// 사용자 확정이 필요한 action 인지 여부.
  final bool requiresUserApproval;
}

/// `/ai-agent/daily-coaching` 응답(AgentOutput).
class DailyCoachingResult {
  /// 오늘의 분석 결과를 생성한다.
  const DailyCoachingResult({
    required this.status,
    required this.approvalStatus,
    required this.requiresUserApproval,
    required this.message,
    required this.findings,
    required this.items,
    required this.safetyWarnings,
  });

  /// 처리 상태 (예: ok / blocked).
  final String status;

  /// 승인 상태 (예: not_required / required).
  final String approvalStatus;

  /// 미확정 기록 등으로 사용자 확정이 필요한지 여부.
  final bool requiresUserApproval;

  /// 종합 코멘트 보조 메시지.
  final String message;

  /// 발견 사항 (코멘트 보조).
  final List<DailyCoachingFinding> findings;

  /// 실천 리스트 항목 (recommendations + actions, priority 순 최대 5개).
  final List<DailyCoachingItem> items;

  /// 안전 경고 문구.
  final List<String> safetyWarnings;

  /// AgentOutput JSON 을 null-safe 하게 파싱한다.
  ///
  /// recommendations 와 actions 를 하나의 실천 리스트로 합치고 priority 로
  /// 정렬한 뒤 최대 5개로 자른다.
  factory DailyCoachingResult.fromJson(Map<String, dynamic> json) {
    final List<DailyCoachingFinding> findings = _objectList(json['findings'])
        .map(DailyCoachingFinding.fromJson)
        .toList(growable: false);

    final List<DailyCoachingItem> recommendations =
        _objectList(json['recommendations'])
            .map(_recommendationToItem)
            .toList();
    final List<DailyCoachingItem> actions = _objectList(json['actions'])
        .map(_actionToItem)
        .toList();

    final List<DailyCoachingItem> merged = <DailyCoachingItem>[
      ...recommendations,
      ...actions,
    ]..sort(
        (DailyCoachingItem a, DailyCoachingItem b) =>
            a.priority.compareTo(b.priority),
      );

    return DailyCoachingResult(
      status: _text(json['status']) ?? 'unknown',
      approvalStatus: _text(json['approval_status']) ?? 'unknown',
      requiresUserApproval: json['requires_user_approval'] as bool? ?? false,
      message: _text(json['message']) ?? '',
      findings: findings,
      items: merged.take(5).toList(growable: false),
      safetyWarnings: _stringList(json['safety_warnings']),
    );
  }

  /// 실천 리스트가 비었는지 여부.
  bool get hasItems => items.isNotEmpty;

  static DailyCoachingItem _recommendationToItem(Map<String, dynamic> json) {
    return DailyCoachingItem(
      title: _text(json['title']) ?? '',
      subtitle: _text(json['rationale']) ?? _text(json['category']) ?? '',
      priority: _priority(json['priority']),
      requiresUserApproval: false,
    );
  }

  static DailyCoachingItem _actionToItem(Map<String, dynamic> json) {
    return DailyCoachingItem(
      title: _text(json['title']) ?? '',
      subtitle: _text(json['action_type']) ?? '',
      // actions 는 priority 가 없을 수 있어 recommendations 뒤로 보낸다.
      priority: _priority(json['priority'], fallback: 100),
      requiresUserApproval: json['requires_user_approval'] as bool? ?? false,
    );
  }
}

/// 발견 사항 (코멘트 보조).
class DailyCoachingFinding {
  /// 발견 사항을 생성한다.
  const DailyCoachingFinding({
    required this.nutrient,
    required this.level,
    required this.message,
  });

  /// 관련 영양소 코드/이름.
  final String nutrient;

  /// 수준 라벨 (예: low / high / ok).
  final String level;

  /// 사용자용 안내 메시지.
  final String message;

  /// finding JSON 을 파싱한다.
  factory DailyCoachingFinding.fromJson(Map<String, dynamic> json) {
    return DailyCoachingFinding(
      nutrient: _text(json['nutrient']) ?? '',
      level: _text(json['level']) ?? '',
      message: _text(json['message']) ?? '',
    );
  }
}

// ─── 공통 null-safe 헬퍼 ───────────────────────────

int _priority(Object? value, {int fallback = 50}) {
  if (value is int) return value;
  if (value is double) return value.round();
  if (value is String) {
    final int? parsed = int.tryParse(value.trim());
    if (parsed != null) return parsed;
    // 문자열 우선순위 라벨도 견고하게 매핑한다.
    switch (value.trim().toLowerCase()) {
      case 'high':
        return 0;
      case 'medium':
        return 50;
      case 'low':
        return 90;
    }
  }
  return fallback;
}

String? _text(Object? value) {
  if (value is String) {
    final String trimmed = value.trim();
    return trimmed.isEmpty ? null : trimmed;
  }
  return null;
}

List<String> _stringList(Object? value) {
  if (value is! List) return const <String>[];
  return value
      .map((Object? item) => item?.toString())
      .whereType<String>()
      .where((String item) => item.trim().isNotEmpty)
      .toList(growable: false);
}

List<Map<String, dynamic>> _objectList(Object? value) {
  if (value is! List) return const <Map<String, dynamic>>[];
  final List<Map<String, dynamic>> out = <Map<String, dynamic>>[];
  for (final Object? item in value) {
    if (item is Map<String, dynamic>) {
      out.add(item);
    } else if (item is Map<Object?, Object?>) {
      out.add(Map<String, dynamic>.from(item));
    }
  }
  return out;
}
