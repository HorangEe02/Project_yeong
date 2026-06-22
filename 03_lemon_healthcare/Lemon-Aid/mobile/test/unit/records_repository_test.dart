import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/dashboard/home_models.dart';
import 'package:lemon_aid_mobile/features/records/food_models.dart';
import 'package:lemon_aid_mobile/features/records/records_models.dart';
import 'package:lemon_aid_mobile/features/records/records_repository.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_repository.dart';

void main() {
  group('RecordsRepository.fetchMonth', () {
    test('passes a local month window and buckets by local day', () async {
      final _RecordingRepository backend = _RecordingRepository(
        meals: <HomeMeal>[_meal('m1', DateTime(2026, 6, 12, 8))],
      );
      final RecordsRepository repository = RecordsRepository(
        repository: backend,
      );

      final MonthRecords records = await repository.fetchMonth(
        DateTime(2026, 6, 3),
      );

      // 로컬 월초(6/1 00:00) ~ 월말(6/30 23:59:59.999) 윈도가 전달된다.
      expect(backend.lastFrom, DateTime(2026, 6));
      expect(
        backend.lastTo,
        DateTime(2026, 7).subtract(const Duration(milliseconds: 1)),
      );
      expect(records.hasMeal(DateTime(2026, 6, 12)), isTrue);
    });

    test('paginates meals until a short page is returned', () async {
      // 100건(full page) → 추가 페이지 → 짧은 페이지에서 멈춘다.
      final _RecordingRepository backend = _RecordingRepository.paged();
      final RecordsRepository repository = RecordsRepository(
        repository: backend,
      );

      await repository.fetchMonth(DateTime(2026, 6));

      expect(backend.mealOffsets, <int>[0, 100]);
    });

    test('caches a month and skips the network on re-entry', () async {
      final _RecordingRepository backend = _RecordingRepository();
      final RecordsRepository repository = RecordsRepository(
        repository: backend,
      );

      await repository.fetchMonth(DateTime(2026, 6));
      await repository.fetchMonth(DateTime(2026, 6, 20));
      expect(backend.mealCalls, 1);

      // 다른 달은 다시 로드한다.
      await repository.fetchMonth(DateTime(2026, 7));
      expect(backend.mealCalls, 2);
    });

    test('invalidateAll forces a reload', () async {
      final _RecordingRepository backend = _RecordingRepository();
      final RecordsRepository repository = RecordsRepository(
        repository: backend,
      );
      await repository.fetchMonth(DateTime(2026, 6));
      repository.invalidateAll();
      await repository.fetchMonth(DateTime(2026, 6));
      expect(backend.mealCalls, 2);
    });
  });

  group('RecordsRepository delete + search', () {
    test('deleteSupplement delegates and invalidates the cache', () async {
      final _RecordingRepository backend = _RecordingRepository();
      final RecordsRepository repository = RecordsRepository(
        repository: backend,
      );
      await repository.fetchMonth(DateTime(2026, 6));
      await repository.deleteSupplement('s1');
      expect(backend.deletedSupplements, <String>['s1']);
      // 무효화 후 재로드된다.
      await repository.fetchMonth(DateTime(2026, 6));
      expect(backend.mealCalls, 2);
    });

    test('searchFoods forwards query and cuisine', () async {
      final _RecordingRepository backend = _RecordingRepository();
      final RecordsRepository repository = RecordsRepository(
        repository: backend,
      );
      await repository.searchFoods(q: '비빔', cuisineCode: 'korean');
      expect(backend.lastSearchQ, '비빔');
      expect(backend.lastSearchCuisine, 'korean');
    });
  });
}

HomeMeal _meal(String id, DateTime eatenAt) {
  return HomeMeal(
    id: id,
    status: 'confirmed',
    mealType: 'lunch',
    eatenAt: eatenAt,
    foodItems: const <HomeFoodItem>[],
    nutrition: HomeMealNutrition.zero,
  );
}

class _RecordingRepository implements LemonAidRepository {
  _RecordingRepository({this.meals = const <HomeMeal>[]});

  factory _RecordingRepository.paged() {
    final _RecordingRepository repo = _RecordingRepository();
    repo._pagedMeals = true;
    return repo;
  }

  final List<HomeMeal> meals;
  bool _pagedMeals = false;

  int mealCalls = 0;
  final List<int> mealOffsets = <int>[];
  DateTime? lastFrom;
  DateTime? lastTo;
  final List<String> deletedSupplements = <String>[];
  String? lastSearchQ;
  String? lastSearchCuisine;

  @override
  Future<HomeMealsResult> fetchMeals({
    DateTime? from,
    DateTime? to,
    int limit = 50,
    int offset = 0,
  }) async {
    if (offset == 0) mealCalls += 1;
    mealOffsets.add(offset);
    lastFrom = from;
    lastTo = to;
    if (_pagedMeals) {
      if (offset == 0) {
        return HomeMealsResult(
          results: List<HomeMeal>.generate(
            100,
            (int i) => _meal('m$i', DateTime(2026, 6, 1, 12)),
          ),
          limit: 100,
          offset: 0,
        );
      }
      return HomeMealsResult(
        results: <HomeMeal>[_meal('m-last', DateTime(2026, 6, 2, 12))],
        limit: 100,
        offset: offset,
      );
    }
    if (offset > 0) return HomeMealsResult.empty;
    return HomeMealsResult(results: meals, limit: limit, offset: offset);
  }

  @override
  Future<HomeSupplementsResult> fetchSupplements({
    int limit = 50,
    int offset = 0,
  }) async {
    if (offset > 0) return HomeSupplementsResult.empty;
    return HomeSupplementsResult(
      results: const <HomeSupplement>[],
      limit: limit,
      offset: offset,
    );
  }

  @override
  Future<void> deleteSupplement(String supplementId) async {
    deletedSupplements.add(supplementId);
  }

  @override
  Future<FoodCatalogList> searchFoods({
    String? q,
    String? cuisineCode,
    int limit = 50,
    int offset = 0,
  }) async {
    lastSearchQ = q;
    lastSearchCuisine = cuisineCode;
    return FoodCatalogList.empty;
  }

  @override
  Future<FoodCuisineList> fetchCuisines() async => FoodCuisineList.empty;

  @override
  Future<void> deleteAnalysisResult(String resultId) async {}

  @override
  void close() {}

  @override
  dynamic noSuchMethod(Invocation invocation) {
    throw UnimplementedError('Unexpected call: ${invocation.memberName}');
  }
}
