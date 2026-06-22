// features/records/food_models.dart — 직접 입력(음식 검색) 모델
//
// 가이드 07 ⑤:
//   - GET /meals/cuisines → 분류 필터 칩 (FoodCuisine.displayNameKo).
//   - GET /meals/foods    → 검색 결과 행 (FoodCatalogItem.canonicalNameKo).
//
// 담은 항목은 카메라 분석 폴백의 confirm payload food_items[] 로 합류한다
// (source: 'database_match'). 파싱은 null-safe.

/// 음식 분류(요리 계열) 한 건 — 필터 칩.
class FoodCuisine {
  /// 분류를 생성한다.
  const FoodCuisine({
    required this.id,
    required this.cuisineCode,
    required this.displayNameKo,
    required this.sortOrder,
  });

  /// 분류 식별자.
  final String id;

  /// 분류 코드 (검색 쿼리 cuisine_code 로 전달).
  final String cuisineCode;

  /// 한국어 표시명 (칩 라벨).
  final String displayNameKo;

  /// 표시 순서.
  final int sortOrder;

  /// /meals/cuisines 의 단일 항목을 파싱한다.
  factory FoodCuisine.fromJson(Map<String, dynamic> json) {
    return FoodCuisine(
      id: (json['id'] as Object?)?.toString() ?? '',
      cuisineCode: (json['cuisine_code'] as Object?)?.toString() ?? '',
      displayNameKo: (json['display_name_ko'] as Object?)?.toString() ?? '',
      sortOrder: _intOrZero(json['sort_order']),
    );
  }
}

/// GET /meals/cuisines 응답 컨테이너.
class FoodCuisineList {
  /// 분류 목록을 생성한다.
  const FoodCuisineList({required this.results});

  /// 활성 분류 목록.
  final List<FoodCuisine> results;

  /// 빈 목록.
  static const FoodCuisineList empty = FoodCuisineList(
    results: <FoodCuisine>[],
  );

  /// /meals/cuisines 응답을 파싱한다 (sort_order 오름차순 정렬).
  factory FoodCuisineList.fromJson(Map<String, dynamic> json) {
    final List<FoodCuisine> items = _objectList(
      json['results'],
    ).map(FoodCuisine.fromJson).toList(growable: false);
    final List<FoodCuisine> sorted = List<FoodCuisine>.of(items)
      ..sort(
        (FoodCuisine a, FoodCuisine b) => a.sortOrder.compareTo(b.sortOrder),
      );
    return FoodCuisineList(results: sorted);
  }
}

/// 음식 카탈로그 항목 한 건 — 검색 결과 행.
class FoodCatalogItem {
  /// 음식 항목을 생성한다.
  const FoodCatalogItem({
    required this.id,
    required this.cuisineCode,
    required this.courseCode,
    required this.canonicalNameKo,
    this.canonicalNameEn,
    required this.source,
  });

  /// 카탈로그 항목 식별자 (confirm 의 food_catalog_item_id).
  final String id;

  /// 분류 코드.
  final String cuisineCode;

  /// 코스 코드.
  final String courseCode;

  /// 한국어 정식 명칭 (행 제목).
  final String canonicalNameKo;

  /// 영어 정식 명칭 (있을 때).
  final String? canonicalNameEn;

  /// 카탈로그 출처 마커.
  final String source;

  /// /meals/foods 의 단일 항목을 파싱한다.
  factory FoodCatalogItem.fromJson(Map<String, dynamic> json) {
    return FoodCatalogItem(
      id: (json['id'] as Object?)?.toString() ?? '',
      cuisineCode: (json['cuisine_code'] as Object?)?.toString() ?? '',
      courseCode: (json['course_code'] as Object?)?.toString() ?? '',
      canonicalNameKo: (json['canonical_name_ko'] as Object?)?.toString() ?? '',
      canonicalNameEn: _optionalText(json['canonical_name_en']),
      source: (json['source'] as Object?)?.toString() ?? '',
    );
  }
}

/// GET /meals/foods 응답 컨테이너.
class FoodCatalogList {
  /// 음식 목록 결과를 생성한다.
  const FoodCatalogList({
    required this.results,
    required this.limit,
    required this.offset,
  });

  /// 음식 항목 목록.
  final List<FoodCatalogItem> results;

  /// 페이지 크기.
  final int limit;

  /// 페이지 오프셋.
  final int offset;

  /// 빈 결과.
  static const FoodCatalogList empty = FoodCatalogList(
    results: <FoodCatalogItem>[],
    limit: 0,
    offset: 0,
  );

  /// /meals/foods 응답을 파싱한다.
  factory FoodCatalogList.fromJson(Map<String, dynamic> json) {
    return FoodCatalogList(
      results: _objectList(
        json['results'],
      ).map(FoodCatalogItem.fromJson).toList(growable: false),
      limit: _intOrZero(json['limit']),
      offset: _intOrZero(json['offset']),
    );
  }
}

// ─── null-safe 헬퍼 ───────────────────────────────

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

String? _optionalText(Object? value) {
  if (value is String) {
    final String trimmed = value.trim();
    return trimmed.isEmpty ? null : trimmed;
  }
  return null;
}

int _intOrZero(Object? value) {
  if (value is int) return value;
  if (value is double) return value.round();
  if (value is String) return int.tryParse(value.trim()) ?? 0;
  return 0;
}
