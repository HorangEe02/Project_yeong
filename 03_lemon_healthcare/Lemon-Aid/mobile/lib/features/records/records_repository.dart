// features/records/records_repository.dart — 캘린더 월 단위 로더 + 캐시
//
// 가이드 07 ④: GET /meals(월 범위) + GET /supplements 를 합쳐 [MonthRecords]
// 로 만든다. 월 단위 1회 로드 후 세션 메모리에 캐시하고, 같은 달 재진입 시
// 네트워크를 생략한다. 월 이동 시 재로드.
//
// 홈 컨트롤러(최근 7일 윈도)를 건드리지 않고 캘린더 전용으로 분리해 홈 성능을
// 유지한다. 연산은 모두 백엔드 — 여기서는 표시·날짜 버킷팅만 한다.

import '../dashboard/home_models.dart';
import '../supplements/supplement_repository.dart';
import 'food_models.dart';
import 'records_models.dart';

/// 한 페이지 최대 조회 수 (백엔드 limit 상한).
const int _kPageLimit = 100;

/// 페이지네이션 안전 상한 (무한 루프 방지). 끼니 3회×31일≈93건이라 보통 1페이지.
const int _kMaxPages = 12;

/// 캘린더 화면이 사용하는 월 단위 기록 로더.
class RecordsRepository {
  /// 백엔드 리포지토리를 주입받아 생성한다.
  RecordsRepository({required LemonAidRepository repository})
    : _repository = repository;

  final LemonAidRepository _repository;
  final Map<String, MonthRecords> _cache = <String, MonthRecords>{};

  /// [month] 의 기록을 가져온다. 캐시에 있으면 즉시 반환한다.
  ///
  /// 끼니는 로컬 월초 00:00 ~ 월말 23:59:59.999 를 UTC 로 변환해 조회하고,
  /// 영양제는 날짜 필터가 없어 전량 조회 후 등록일로 분배한다.
  Future<MonthRecords> fetchMonth(DateTime month) async {
    final String key = MonthRecords.keyForMonth(month);
    final MonthRecords? cached = _cache[key];
    if (cached != null) return cached;

    final DateTime monthStart = DateTime(month.year, month.month);
    final DateTime monthEnd = DateTime(
      month.year,
      month.month + 1,
    ).subtract(const Duration(milliseconds: 1));

    final List<HomeMeal> meals = await _fetchAllMeals(monthStart, monthEnd);
    final List<HomeSupplement> supplements = await _fetchAllSupplements();

    final MonthRecords records = MonthRecords.fromData(
      month: monthStart,
      meals: meals,
      supplements: supplements,
    );
    _cache[key] = records;
    return records;
  }

  /// 특정 달 캐시를 무효화한다 (그 달의 기록 변경 시).
  void invalidateMonth(DateTime month) {
    _cache.remove(MonthRecords.keyForMonth(month));
  }

  /// 전체 캐시를 비운다 (confirm·저장·삭제 등 어떤 기록 변경 후 호출 가능).
  void invalidateAll() {
    _cache.clear();
  }

  /// 음식 카탈로그를 검색한다 (직접 입력 화면).
  Future<FoodCatalogList> searchFoods({
    String? q,
    String? cuisineCode,
    int offset = 0,
  }) {
    return _repository.searchFoods(
      q: q,
      cuisineCode: cuisineCode,
      limit: _kPageLimit,
      offset: offset,
    );
  }

  /// 음식 분류 칩 목록을 가져온다.
  Future<FoodCuisineList> fetchCuisines() => _repository.fetchCuisines();

  /// 영양제를 삭제한다 (soft-delete). 성공 시 전체 캐시 무효화.
  Future<void> deleteSupplement(String supplementId) async {
    await _repository.deleteSupplement(supplementId);
    invalidateAll();
  }

  /// 분석 결과를 삭제한다. 성공 시 전체 캐시 무효화.
  Future<void> deleteAnalysisResult(String resultId) async {
    await _repository.deleteAnalysisResult(resultId);
    invalidateAll();
  }

  Future<List<HomeMeal>> _fetchAllMeals(DateTime from, DateTime to) async {
    final List<HomeMeal> all = <HomeMeal>[];
    int offset = 0;
    for (int page = 0; page < _kMaxPages; page += 1) {
      final HomeMealsResult result = await _repository.fetchMeals(
        from: from,
        to: to,
        limit: _kPageLimit,
        offset: offset,
      );
      all.addAll(result.results);
      if (result.results.length < _kPageLimit) break;
      offset += _kPageLimit;
    }
    return all;
  }

  Future<List<HomeSupplement>> _fetchAllSupplements() async {
    final List<HomeSupplement> all = <HomeSupplement>[];
    int offset = 0;
    for (int page = 0; page < _kMaxPages; page += 1) {
      final HomeSupplementsResult result = await _repository.fetchSupplements(
        limit: _kPageLimit,
        offset: offset,
      );
      all.addAll(result.results);
      if (result.results.length < _kPageLimit) break;
      offset += _kPageLimit;
    }
    return all;
  }
}
