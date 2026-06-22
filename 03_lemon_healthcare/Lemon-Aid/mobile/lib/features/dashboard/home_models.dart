// features/dashboard/home_models.dart — 홈 탭 실데이터 모델 (P0 배치 A)
//
// 백엔드 계약(확정)에 대한 null-safe fromJson 파서.
//   - DashboardHealthScore : GET /dashboard/summary 의 옵셔널 health_score 블록.
//       블록 부재·미지 필드 → not_ready 로 견고하게 파싱.
//   - HomeMealsResult / HomeMeal / HomeFoodItem / HomeMealNutrition
//       : GET /meals 응답.
//   - HomeSupplementsResult / HomeSupplement / HomeSupplementSchedule
//       : GET /supplements 응답.
//
// 연산은 모두 백엔드. 모바일은 표시·합산만 (kcal/매크로 클라이언트 합산은
// 단순 더하기 — 알고리즘 아님).

/// 건강 점수 데이터 준비 상태.
enum HealthScoreStatus {
  /// 점수를 표시할 수 있는 상태.
  ready,

  /// 데이터가 부족해 점수를 보여줄 수 없는 상태.
  notReady,
}

/// 홈 건강 점수 카드를 채우는 옵셔널 health_score 블록.
///
/// 백엔드가 병렬 구현 중이므로 블록 자체가 없을 수 있고, 일부 필드만 올 수도 있다.
/// 어느 경우든 [HealthScoreStatus.notReady] 로 안전하게 수렴한다.
class DashboardHealthScore {
  /// 홈 건강 점수를 생성한다.
  const DashboardHealthScore({
    required this.status,
    this.score,
    this.label,
    this.labelText,
    this.message,
    this.measuredDate,
    this.algorithmVersion,
    this.disclaimers = const <String>[],
  });

  /// 데이터 준비 상태.
  final HealthScoreStatus status;

  /// 0~100 정수 점수 (ready 일 때만 의미 있음).
  final int? score;

  /// 등급 코드 (excellent/good/moderate/warning/needs_attention 등).
  final String? label;

  /// 등급 한국어 표기 (예: '좋아요').
  final String? labelText;

  /// 사용자에게 보여줄 코멘트.
  final String? message;

  /// 측정 기준일 (YYYY-MM-DD).
  final String? measuredDate;

  /// 알고리즘 버전.
  final String? algorithmVersion;

  /// 사용자용 면책 문구.
  final List<String> disclaimers;

  /// 점수를 표시할 수 있는지 여부.
  bool get isReady => status == HealthScoreStatus.ready && score != null;

  /// dashboard summary 본문에서 옵셔널 health_score 블록을 안전하게 파싱한다.
  ///
  /// 블록이 없으면 [DashboardHealthScore.notReady] 를 반환한다.
  factory DashboardHealthScore.fromSummaryJson(Map<String, dynamic> summary) {
    final Map<String, dynamic>? block = _optionalMap(summary['health_score']);
    if (block == null) {
      return const DashboardHealthScore(status: HealthScoreStatus.notReady);
    }
    return DashboardHealthScore.fromJson(block);
  }

  /// health_score 블록 객체를 null-safe 하게 파싱한다.
  factory DashboardHealthScore.fromJson(Map<String, dynamic> json) {
    final int? score = _optionalIntLenient(json['score']);
    final String rawStatus = (json['data_status'] as Object?)?.toString() ?? '';
    final bool ready = rawStatus == 'ready' && score != null;
    return DashboardHealthScore(
      status: ready ? HealthScoreStatus.ready : HealthScoreStatus.notReady,
      score: score,
      label: _optionalText(json['label']),
      labelText: _optionalText(json['label_text']),
      message: _optionalText(json['message']),
      measuredDate: _optionalText(json['measured_date']),
      algorithmVersion: _optionalText(json['algorithm_version']),
      disclaimers: _stringList(json['disclaimers']),
    );
  }
}

/// GET /meals 응답 컨테이너.
class HomeMealsResult {
  /// 식단 목록 결과를 생성한다.
  const HomeMealsResult({
    required this.results,
    required this.limit,
    required this.offset,
  });

  /// 식단 레코드 목록.
  final List<HomeMeal> results;

  /// 페이지 크기.
  final int limit;

  /// 페이지 오프셋.
  final int offset;

  /// 빈 결과.
  static const HomeMealsResult empty = HomeMealsResult(
    results: <HomeMeal>[],
    limit: 0,
    offset: 0,
  );

  /// GET /meals 응답을 파싱한다.
  factory HomeMealsResult.fromJson(Map<String, dynamic> json) {
    return HomeMealsResult(
      results: _objectList(
        json['results'],
      ).map(HomeMeal.fromJson).toList(growable: false),
      limit: _optionalIntLenient(json['limit']) ?? 0,
      offset: _optionalIntLenient(json['offset']) ?? 0,
    );
  }
}

/// 단일 식단 레코드.
class HomeMeal {
  /// 식단 레코드를 생성한다.
  const HomeMeal({
    required this.id,
    required this.status,
    required this.mealType,
    required this.eatenAt,
    required this.foodItems,
    required this.nutrition,
  });

  /// 식단 식별자.
  final String id;

  /// 상태 코드 (방어적으로 문자열 그대로 보관).
  final String status;

  /// 끼니 유형 (breakfast/lunch/dinner/snack/unknown — 응답 값 그대로).
  final String mealType;

  /// 섭취 시각.
  final DateTime? eatenAt;

  /// 음식 항목 목록.
  final List<HomeFoodItem> foodItems;

  /// 끼니 영양 합계.
  final HomeMealNutrition nutrition;

  /// 대표 메뉴명 (첫 음식 항목 표시명). 없으면 null.
  String? get primaryName {
    for (final HomeFoodItem item in foodItems) {
      final String name = item.displayName.trim();
      if (name.isNotEmpty) return name;
    }
    return null;
  }

  /// /meals 응답의 단일 항목을 파싱한다.
  factory HomeMeal.fromJson(Map<String, dynamic> json) {
    final List<HomeFoodItem> items = _objectList(
      json['food_items'],
    ).map(HomeFoodItem.fromJson).toList(growable: false);
    final Map<String, dynamic>? summary = _optionalMap(
      json['nutrition_summary'],
    );
    // 서버 요약(totals)을 우선 쓰되, 요약에 유효한 kcal이 없으면 음식 항목 합계로
    // 폴백한다 — 요약 구조 불일치/누락이 끼니 kcal을 0으로 만들지 않도록 한다.
    final HomeMealNutrition fromItems = HomeMealNutrition.fromFoodItems(items);
    final HomeMealNutrition? fromSummary = summary != null
        ? HomeMealNutrition.fromJson(summary)
        : null;
    final HomeMealNutrition nutrition =
        (fromSummary != null && fromSummary.kcal > 0) ? fromSummary : fromItems;
    return HomeMeal(
      id: (json['id'] as Object?)?.toString() ?? '',
      status: (json['status'] as Object?)?.toString() ?? 'unknown',
      mealType: (json['meal_type'] as Object?)?.toString() ?? 'unknown',
      eatenAt: _optionalDateTime(json['eaten_at']),
      foodItems: items,
      nutrition: nutrition,
    );
  }
}

/// 식단 내 단일 음식 항목.
class HomeFoodItem {
  /// 음식 항목을 생성한다.
  const HomeFoodItem({
    required this.displayName,
    required this.kcal,
    required this.carbG,
    required this.proteinG,
    required this.fatG,
    this.sodiumMg = 0,
  });

  /// 표시명.
  final String displayName;

  /// 칼로리.
  final double kcal;

  /// 탄수화물(g).
  final double carbG;

  /// 단백질(g).
  final double proteinG;

  /// 지방(g).
  final double fatG;

  /// 나트륨(mg).
  final double sodiumMg;

  /// 음식 항목을 파싱한다.
  factory HomeFoodItem.fromJson(Map<String, dynamic> json) {
    return HomeFoodItem(
      displayName: _optionalText(json['display_name']) ?? '',
      kcal: _optionalDoubleLenient(json['kcal']) ?? 0,
      carbG: _optionalDoubleLenient(json['carb_g']) ?? 0,
      proteinG: _optionalDoubleLenient(json['protein_g']) ?? 0,
      fatG: _optionalDoubleLenient(json['fat_g']) ?? 0,
      sodiumMg: _optionalDoubleLenient(json['sodium_mg']) ?? 0,
    );
  }
}

/// 끼니 영양 합계.
class HomeMealNutrition {
  /// 끼니 영양 합계를 생성한다.
  const HomeMealNutrition({
    required this.kcal,
    required this.carbG,
    required this.proteinG,
    required this.fatG,
  });

  /// 칼로리 합계.
  final double kcal;

  /// 탄수화물(g) 합계.
  final double carbG;

  /// 단백질(g) 합계.
  final double proteinG;

  /// 지방(g) 합계.
  final double fatG;

  /// 0 합계.
  static const HomeMealNutrition zero = HomeMealNutrition(
    kcal: 0,
    carbG: 0,
    proteinG: 0,
    fatG: 0,
  );

  /// nutrition_summary 객체를 파싱한다 (필드명은 흔한 변형을 모두 시도).
  ///
  /// 백엔드 confirmed meal 요약은 `{status, items_count, totals:{kcal,carb_g,...}}`
  /// 구조라 합계가 `totals` 하위에 들어있다. `totals`를 우선 사용하고, 평탄
  /// (top-level) 구조도 하위 호환으로 지원한다.
  factory HomeMealNutrition.fromJson(Map<String, dynamic> json) {
    final Map<String, dynamic> source = _optionalMap(json['totals']) ?? json;
    return HomeMealNutrition(
      kcal:
          _firstNumber(source, const <String>[
            'kcal',
            'total_kcal',
            'energy_kcal',
          ]) ??
          0,
      carbG:
          _firstNumber(source, const <String>[
            'carb_g',
            'total_carb_g',
            'carbohydrate_g',
          ]) ??
          0,
      proteinG:
          _firstNumber(source, const <String>['protein_g', 'total_protein_g']) ??
          0,
      fatG: _firstNumber(source, const <String>['fat_g', 'total_fat_g']) ?? 0,
    );
  }

  /// nutrition_summary 가 없을 때 음식 항목에서 합산한다.
  factory HomeMealNutrition.fromFoodItems(List<HomeFoodItem> items) {
    double kcal = 0;
    double carb = 0;
    double protein = 0;
    double fat = 0;
    for (final HomeFoodItem item in items) {
      kcal += item.kcal;
      carb += item.carbG;
      protein += item.proteinG;
      fat += item.fatG;
    }
    return HomeMealNutrition(
      kcal: kcal,
      carbG: carb,
      proteinG: protein,
      fatG: fat,
    );
  }

  /// 다른 합계를 더한 새 합계를 반환한다.
  HomeMealNutrition operator +(HomeMealNutrition other) {
    return HomeMealNutrition(
      kcal: kcal + other.kcal,
      carbG: carbG + other.carbG,
      proteinG: proteinG + other.proteinG,
      fatG: fatG + other.fatG,
    );
  }
}

/// GET /supplements 응답 컨테이너.
class HomeSupplementsResult {
  /// 영양제 목록 결과를 생성한다.
  const HomeSupplementsResult({
    required this.results,
    required this.limit,
    required this.offset,
  });

  /// 영양제 레코드 목록.
  final List<HomeSupplement> results;

  /// 페이지 크기.
  final int limit;

  /// 페이지 오프셋.
  final int offset;

  /// 빈 결과.
  static const HomeSupplementsResult empty = HomeSupplementsResult(
    results: <HomeSupplement>[],
    limit: 0,
    offset: 0,
  );

  /// GET /supplements 응답을 파싱한다.
  factory HomeSupplementsResult.fromJson(Map<String, dynamic> json) {
    return HomeSupplementsResult(
      results: _objectList(
        json['results'],
      ).map(HomeSupplement.fromJson).toList(growable: false),
      limit: _optionalIntLenient(json['limit']) ?? 0,
      offset: _optionalIntLenient(json['offset']) ?? 0,
    );
  }
}

/// 단일 영양제 레코드.
class HomeSupplement {
  /// 영양제 레코드를 생성한다.
  const HomeSupplement({
    required this.id,
    required this.displayName,
    required this.manufacturer,
    required this.schedule,
    this.categoryLabel,
    this.registeredAt,
  });

  /// 영양제 식별자.
  final String id;

  /// 표시명.
  final String displayName;

  /// 제조사 (있을 때).
  final String? manufacturer;

  /// 사용자가 고른 분류의 표시 라벨 (미선택이면 null).
  ///
  /// 응답 `categories[0].display_name`(사용자 선택이 우선 반영됨)을 쓰고,
  /// 비면 `category_key`로 폴백한다.
  final String? categoryLabel;

  /// 섭취 일정 요약 (intake_schedule 가 없으면 null).
  final HomeSupplementSchedule? schedule;

  /// 등록 시각 — user_confirmed_at 우선, 없으면 created_at (캘린더 날짜 분배용).
  ///
  /// /supplements 응답에는 날짜 범위 필터가 없으므로 등록일 기준으로 집계한다
  /// (가이드 07 §4 "등록일 기준").
  final DateTime? registeredAt;

  /// /supplements 응답의 단일 항목을 파싱한다.
  factory HomeSupplement.fromJson(Map<String, dynamic> json) {
    final Map<String, dynamic>? scheduleJson = _optionalMap(
      json['intake_schedule'],
    );
    return HomeSupplement(
      id: (json['id'] as Object?)?.toString() ?? '',
      displayName: _optionalText(json['display_name']) ?? '',
      manufacturer: _optionalText(json['manufacturer']),
      categoryLabel: _categoryLabel(json),
      schedule: scheduleJson != null
          ? HomeSupplementSchedule.fromJson(scheduleJson)
          : null,
      registeredAt:
          _optionalDateTime(json['user_confirmed_at']) ??
          _optionalDateTime(json['created_at']),
    );
  }

  /// 응답에서 분류 표시 라벨을 고른다 (categories[0].display_name 우선,
  /// 비면 category_key 폴백, 둘 다 없으면 null).
  static String? _categoryLabel(Map<String, dynamic> json) {
    final Object? categories = json['categories'];
    if (categories is List<dynamic>) {
      for (final Object? row in categories) {
        if (row is Map<String, dynamic>) {
          final String? label = _optionalText(row['display_name']);
          if (label != null) {
            return label;
          }
        }
      }
    }
    return _optionalText(json['category_key']);
  }
}

/// 영양제 섭취 일정 요약.
class HomeSupplementSchedule {
  /// 섭취 일정을 생성한다.
  const HomeSupplementSchedule({
    required this.frequency,
    required this.timeOfDay,
    required this.timesPerDay,
  });

  /// 빈도 (예: daily).
  final String? frequency;

  /// 섭취 시간대 목록 (예: morning, evening).
  final List<String> timeOfDay;

  /// 하루 섭취 횟수.
  final int? timesPerDay;

  /// intake_schedule 객체를 파싱한다.
  factory HomeSupplementSchedule.fromJson(Map<String, dynamic> json) {
    return HomeSupplementSchedule(
      frequency: _optionalText(json['frequency']),
      timeOfDay: _stringList(json['time_of_day']),
      timesPerDay: _optionalIntLenient(json['times_per_day']),
    );
  }

  /// 한 줄 한국어 요약 (예: '매일 · 아침, 저녁'). 비어 있으면 null.
  String? get summary {
    final List<String> parts = <String>[];
    final String? freq = frequency?.trim();
    if (freq != null && freq.isNotEmpty) {
      parts.add(_frequencyLabel(freq));
    }
    if (timeOfDay.isNotEmpty) {
      parts.add(timeOfDay.map(_timeOfDayLabel).join(', '));
    } else if (timesPerDay != null && timesPerDay! > 0) {
      parts.add('하루 $timesPerDay회');
    }
    if (parts.isEmpty) return null;
    return parts.join(' · ');
  }

  static String _frequencyLabel(String value) {
    switch (value.toLowerCase()) {
      case 'daily':
        return '매일';
      case 'weekly':
        return '매주';
      default:
        return value;
    }
  }

  static String _timeOfDayLabel(String value) {
    switch (value.toLowerCase()) {
      case 'morning':
        return '아침';
      case 'noon':
      case 'lunch':
        return '점심';
      case 'evening':
        return '저녁';
      case 'night':
        return '밤';
      default:
        return value;
    }
  }
}

/// GET /me/medications 응답 컨테이너.
///
/// meals/supplements 의 `results` 와 달리 래퍼 키가 `items` 다
/// (백엔드 `UserMedicationListResponse`).
class HomeMedicationsResult {
  /// 복약 목록 결과를 생성한다.
  const HomeMedicationsResult({required this.items});

  /// 복약 레코드 목록 (활성·비활성 모두 — 서버가 활성 우선 정렬).
  final List<HomeMedication> items;

  /// 빈 결과.
  static const HomeMedicationsResult empty = HomeMedicationsResult(
    items: <HomeMedication>[],
  );

  /// 활성 약만 추린 목록.
  List<HomeMedication> get activeItems => items
      .where((HomeMedication item) => item.isActive)
      .toList(growable: false);

  /// GET /me/medications 응답을 파싱한다.
  factory HomeMedicationsResult.fromJson(Map<String, dynamic> json) {
    return HomeMedicationsResult(
      items: _objectList(
        json['items'],
      ).map(HomeMedication.fromJson).toList(growable: false),
    );
  }
}

/// 단일 복약 레코드.
class HomeMedication {
  /// 복약 레코드를 생성한다.
  const HomeMedication({
    required this.id,
    required this.displayName,
    this.medicationClass,
    this.conditionTags = const <String>[],
    this.confirmationStatus,
    this.isActive = true,
  });

  /// 복약 식별자.
  final String id;

  /// 표시명.
  final String displayName;

  /// 약 분류 코드 (허용 16종 중 하나 또는 null).
  final String? medicationClass;

  /// 질환 태그 코드 목록 (허용 8종).
  final List<String> conditionTags;

  /// 확인 상태 코드 (예: user_confirmed).
  final String? confirmationStatus;

  /// 활성 여부.
  final bool isActive;

  /// medication_class 코드의 한국어 표시명. 미지정/미지 코드는 null.
  String? get medicationClassLabel => kMedicationClassLabels[medicationClass];

  /// condition_tags 코드를 한국어 표시명으로 매핑 (미지 코드는 코드 원문 유지).
  List<String> get conditionTagLabels => conditionTags
      .map((String code) => kConditionTagLabels[code] ?? code)
      .toList(growable: false);

  /// /me/medications 응답의 단일 항목을 파싱한다.
  factory HomeMedication.fromJson(Map<String, dynamic> json) {
    final Object? active = json['is_active'];
    return HomeMedication(
      id: (json['id'] as Object?)?.toString() ?? '',
      displayName: _optionalText(json['display_name']) ?? '',
      medicationClass: _optionalText(json['medication_class']),
      conditionTags: _stringList(json['condition_tags']),
      confirmationStatus: _optionalText(json['confirmation_status']),
      isActive: active is bool ? active : true,
    );
  }
}

/// 허용 약 분류 코드 → 한국어 표시명.
///
/// 출처(미러링): backend/Nutrition-backend/src/models/schemas/user_medication.py
/// 의 `ALLOWED_MEDICATION_CLASSES` (16종). 코드/순서를 그대로 따른다.
const Map<String, String> kMedicationClassLabels = <String, String>{
  'ace_inhibitor': 'ACE 억제제',
  'arb': 'ARB(안지오텐신 차단제)',
  'beta_blocker': '베타 차단제',
  'calcium_channel_blocker': '칼슘 채널 차단제',
  'diuretic': '이뇨제',
  'maoi': 'MAO 억제제',
  'nitrate': '질산염제',
  'pde5_inhibitor': 'PDE5 억제제',
  'ssri': 'SSRI',
  'snri': 'SNRI',
  'statin': '스타틴',
  'thyroid_hormone': '갑상선 호르몬제',
  'warfarin': '와파린',
  'anticoagulant': '항응고제',
  'diabetes_medication': '당뇨약',
  'other': '기타',
};

/// 허용 질환 태그 코드 → 한국어 표시명.
///
/// 출처(미러링): 위 파일의 `ALLOWED_CONDITION_TAGS` (8종).
const Map<String, String> kConditionTagLabels = <String, String>{
  'hypertension': '고혈압',
  'diabetes': '당뇨',
  'kidney_disease': '신장질환',
  'dyslipidemia': '이상지질혈증',
  'thyroid_disease': '갑상선질환',
  'heart_disease': '심장질환',
  'mental_health': '정신건강',
  'other': '기타',
};

// ─── 공통 null-safe 헬퍼 ───────────────────────────

Map<String, dynamic>? _optionalMap(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map<Object?, Object?>) return Map<String, dynamic>.from(value);
  return null;
}

List<Map<String, dynamic>> _objectList(Object? value) {
  if (value is! List) return const <Map<String, dynamic>>[];
  final List<Map<String, dynamic>> out = <Map<String, dynamic>>[];
  for (final Object? item in value) {
    final Map<String, dynamic>? map = _optionalMap(item);
    if (map != null) out.add(map);
  }
  return out;
}

List<String> _stringList(Object? value) {
  if (value is! List) return const <String>[];
  return value
      .whereType<Object?>()
      .map((Object? item) => item?.toString())
      .whereType<String>()
      .where((String item) => item.trim().isNotEmpty)
      .toList(growable: false);
}

String? _optionalText(Object? value) {
  if (value is String) {
    final String trimmed = value.trim();
    return trimmed.isEmpty ? null : trimmed;
  }
  return null;
}

int? _optionalIntLenient(Object? value) {
  if (value is int) return value;
  if (value is double) return value.round();
  if (value is String) return int.tryParse(value.trim());
  return null;
}

double? _optionalDoubleLenient(Object? value) {
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value.trim());
  return null;
}

DateTime? _optionalDateTime(Object? value) {
  if (value is String) return DateTime.tryParse(value.trim());
  return null;
}

double? _firstNumber(Map<String, dynamic> json, List<String> keys) {
  for (final String key in keys) {
    final double? parsed = _optionalDoubleLenient(json[key]);
    if (parsed != null) return parsed;
  }
  return null;
}
