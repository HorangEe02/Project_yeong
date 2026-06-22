// features/records/records_models.dart — 캘린더(월 단위) 집계 모델
//
// 가이드 07 ②: 월 그리드 + 일자별 기록 점 + 일자 상세 카드.
//   - GET /meals (월 범위) 끼니 + GET /supplements (등록일 기준) 영양제를
//     로컬 타임존 날짜로 버킷팅한다.
//   - 끼니 점 = 그 날 끼니 기록 존재, 영양제 점 = 그 날 영양제 등록 존재.
//   - 일자 상세 카드는 [DayRecords] 의 끼니·영양제 행을 그대로 표시한다.
//
// 연산은 모두 백엔드. 모바일은 표시·날짜 버킷팅·합산만(알고리즘 아님).
//
// 파싱은 home_models 의 HomeMeal / HomeSupplement 를 그대로 재사용한다.

import '../dashboard/home_models.dart';

/// 한 달치 기록 — 일(day) → [DayRecords] 맵.
///
/// 키는 로컬 타임존 기준 `yyyy-MM-dd` 문자열. 빈 날은 맵에 없다.
class MonthRecords {
  /// 한 달치 기록을 생성한다.
  const MonthRecords({required this.monthKey, required this.days});

  /// 이 달의 식별 키 (`yyyy-MM`, 로컬).
  final String monthKey;

  /// 일자 키(`yyyy-MM-dd`) → 그 날의 기록.
  final Map<String, DayRecords> days;

  /// 빈 달.
  static const MonthRecords empty = MonthRecords(
    monthKey: '',
    days: <String, DayRecords>{},
  );

  /// 로컬 [month] 의 `yyyy-MM` 키.
  static String keyForMonth(DateTime month) {
    final String m = month.month.toString().padLeft(2, '0');
    return '${month.year}-$m';
  }

  /// 로컬 [day] 의 `yyyy-MM-dd` 키.
  static String keyForDay(DateTime day) {
    final String m = day.month.toString().padLeft(2, '0');
    final String d = day.day.toString().padLeft(2, '0');
    return '${day.year}-$m-$d';
  }

  /// 특정 [day] 의 기록 (없으면 빈 [DayRecords]).
  DayRecords forDay(DateTime day) {
    return days[keyForDay(day)] ?? DayRecords.empty;
  }

  /// [day] 에 끼니 기록이 있으면 true (식단 점).
  bool hasMeal(DateTime day) => forDay(day).meals.isNotEmpty;

  /// [day] 에 영양제 등록이 있으면 true (영양제 점).
  bool hasSupplement(DateTime day) => forDay(day).supplements.isNotEmpty;

  /// 끼니/영양제를 로컬 날짜로 버킷팅해 한 달치 맵을 만든다.
  ///
  /// Args:
  ///   month: 대상 달 (year·month 만 사용).
  ///   meals: 그 달 범위로 조회한 끼니 (eaten_at 로 버킷팅).
  ///   supplements: 등록 영양제 (user_confirmed_at → created_at 순으로 날짜 결정).
  factory MonthRecords.fromData({
    required DateTime month,
    required List<HomeMeal> meals,
    required List<HomeSupplement> supplements,
  }) {
    final Map<String, List<HomeMeal>> mealBuckets = <String, List<HomeMeal>>{};
    for (final HomeMeal meal in meals) {
      final DateTime? eatenAt = meal.eatenAt;
      if (eatenAt == null) continue;
      final DateTime local = eatenAt.toLocal();
      if (local.year != month.year || local.month != month.month) continue;
      (mealBuckets[keyForDay(local)] ??= <HomeMeal>[]).add(meal);
    }

    final Map<String, List<HomeSupplement>> supplementBuckets =
        <String, List<HomeSupplement>>{};
    for (final HomeSupplement supplement in supplements) {
      final DateTime? registeredAt = supplement.registeredAt;
      if (registeredAt == null) continue;
      final DateTime local = registeredAt.toLocal();
      if (local.year != month.year || local.month != month.month) continue;
      (supplementBuckets[keyForDay(local)] ??= <HomeSupplement>[]).add(
        supplement,
      );
    }

    final Set<String> allKeys = <String>{
      ...mealBuckets.keys,
      ...supplementBuckets.keys,
    };
    final Map<String, DayRecords> days = <String, DayRecords>{};
    for (final String key in allKeys) {
      days[key] = DayRecords(
        meals: mealBuckets[key] ?? const <HomeMeal>[],
        supplements: supplementBuckets[key] ?? const <HomeSupplement>[],
      );
    }
    return MonthRecords(monthKey: keyForMonth(month), days: days);
  }
}

/// 하루치 끼니·영양제 기록.
class DayRecords {
  /// 하루치 기록을 생성한다.
  const DayRecords({required this.meals, required this.supplements});

  /// 그 날 끼니 목록.
  final List<HomeMeal> meals;

  /// 그 날 등록한 영양제 목록.
  final List<HomeSupplement> supplements;

  /// 빈 하루.
  static const DayRecords empty = DayRecords(
    meals: <HomeMeal>[],
    supplements: <HomeSupplement>[],
  );

  /// 기록 건수 (끼니 + 영양제).
  int get totalCount => meals.length + supplements.length;

  /// 그 날 끼니 kcal 합계 (nutrition_summary 누락은 0 처리).
  int get totalKcal {
    double sum = 0;
    for (final HomeMeal meal in meals) {
      sum += meal.nutrition.kcal;
    }
    return sum.round();
  }

  /// 시간 오름차순으로 병합한 타임라인 (끼니 + 영양제).
  ///
  /// 정렬 규칙(가이드 ⑦): 시각 오름차순. **동시각이면 끼니를 영양제보다 먼저**
  /// 표시한다(같은 분에 식사·영양제가 함께 기록된 경우 식사를 먼저 보여줘 자연
  /// 스럽게 읽히게 한다). 시각은 모두 로컬 타임존으로 변환해 비교한다.
  List<RecordTimelineEntry> get timeline {
    final List<RecordTimelineEntry> entries = <RecordTimelineEntry>[
      for (final HomeMeal meal in meals)
        if (meal.eatenAt != null) RecordTimelineEntry.meal(meal),
      for (final HomeSupplement supplement in supplements)
        RecordTimelineEntry.supplement(supplement),
    ];
    entries.sort((RecordTimelineEntry a, RecordTimelineEntry b) {
      final int byTime = a.sortTime.compareTo(b.sortTime);
      if (byTime != 0) return byTime;
      // 동시각 — 끼니 우선(meal=0, supplement=1).
      return a.kind.sortRank.compareTo(b.kind.sortRank);
    });
    return entries;
  }
}

/// 타임라인 항목 종류.
enum RecordTimelineKind {
  /// 끼니 기록.
  meal,

  /// 영양제 등록.
  supplement;

  /// 동시각 정렬 우선순위 (끼니가 영양제보다 먼저).
  int get sortRank => this == RecordTimelineKind.meal ? 0 : 1;
}

/// 오늘의 기록 타임라인의 한 행 (끼니 또는 영양제).
///
/// 시각은 로컬 타임존 기준:
///   - 끼니: `eaten_at` 로컬 변환.
///   - 영양제: `intake_schedule` 의 시각 단서가 있으면 그 시각, 없으면 등록일
///     (`user_confirmed_at`→`created_at`) 의 시각.
class RecordTimelineEntry {
  /// 타임라인 항목을 생성한다.
  const RecordTimelineEntry({
    required this.kind,
    required this.sortTime,
    required this.title,
    this.subtitle,
    this.trailing,
    this.meal,
    this.supplement,
  });

  /// 항목 종류.
  final RecordTimelineKind kind;

  /// 정렬·표기에 쓰는 로컬 시각.
  final DateTime sortTime;

  /// 행 제목 (대표 메뉴명 / 영양제명).
  final String title;

  /// 행 보조 설명 (끼니 항목 요약 / 영양제 안내).
  final String? subtitle;

  /// 행 우측 보조 텍스트 (끼니 kcal 등).
  final String? trailing;

  /// 끼니 항목일 때 원본 끼니.
  final HomeMeal? meal;

  /// 영양제 항목일 때 원본 영양제.
  final HomeSupplement? supplement;

  /// `HH:mm` 로컬 시각 라벨.
  String get timeLabel {
    final String h = sortTime.hour.toString().padLeft(2, '0');
    final String m = sortTime.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }

  /// 끼니 한 행을 만든다.
  factory RecordTimelineEntry.meal(HomeMeal meal) {
    final DateTime local = (meal.eatenAt ?? DateTime.now()).toLocal();
    final String primary = meal.primaryName ?? '식단 기록';
    final int extra = meal.foodItems.length - 1;
    final String title = extra > 0 ? '$primary 외 $extra개' : primary;
    return RecordTimelineEntry(
      kind: RecordTimelineKind.meal,
      sortTime: local,
      title: title,
      subtitle: _mealTypeLabel(meal.mealType),
      trailing: '${meal.nutrition.kcal.round()} kcal',
      meal: meal,
    );
  }

  /// 영양제 한 행을 만든다.
  factory RecordTimelineEntry.supplement(HomeSupplement supplement) {
    final DateTime base = (supplement.registeredAt ?? DateTime.now()).toLocal();
    final DateTime sortTime = _scheduleTime(base, supplement.schedule);
    final String name = supplement.displayName.isNotEmpty
        ? supplement.displayName
        : '영양제';
    return RecordTimelineEntry(
      kind: RecordTimelineKind.supplement,
      sortTime: sortTime,
      title: name,
      subtitle: supplement.schedule?.summary ?? '등록된 영양제',
      supplement: supplement,
    );
  }

  /// 영양제 시각 — intake_schedule 의 time_of_day 단서가 있으면 대표 시각으로,
  /// 없으면 등록일 시각을 그대로 쓴다 (가이드 ②/④).
  static DateTime _scheduleTime(
    DateTime registeredAt,
    HomeSupplementSchedule? schedule,
  ) {
    final List<String> times = schedule?.timeOfDay ?? const <String>[];
    if (times.isEmpty) return registeredAt;
    int? hour;
    for (final String slot in times) {
      final int? mapped = _timeOfDayHour(slot);
      if (mapped != null) {
        hour = hour == null ? mapped : (mapped < hour ? mapped : hour);
      }
    }
    if (hour == null) return registeredAt;
    return DateTime(
      registeredAt.year,
      registeredAt.month,
      registeredAt.day,
      hour,
    );
  }

  static int? _timeOfDayHour(String slot) {
    switch (slot.toLowerCase()) {
      case 'morning':
        return 8;
      case 'noon':
      case 'lunch':
        return 12;
      case 'evening':
        return 18;
      case 'night':
        return 21;
      default:
        return null;
    }
  }

  static String _mealTypeLabel(String mealType) {
    switch (mealType.toLowerCase()) {
      case 'breakfast':
        return '아침';
      case 'lunch':
        return '점심';
      case 'dinner':
        return '저녁';
      case 'snack':
        return '간식';
      default:
        return '끼니';
    }
  }
}
