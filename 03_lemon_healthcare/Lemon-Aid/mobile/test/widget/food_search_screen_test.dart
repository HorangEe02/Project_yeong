import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/records/food_models.dart';
import 'package:lemon_aid_mobile/features/records/records_repository.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_repository.dart';
import 'package:lemon_aid_mobile/screens/food_search_screen.dart';

void main() {
  Future<void> pump(WidgetTester tester, _SearchRepository repo) async {
    tester.view.physicalSize = const Size(1200, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        home: FoodSearchScreen(repository: RecordsRepository(repository: repo)),
      ),
    );
    await tester.pump();
  }

  testWidgets('renders cuisine chips and search results', (
    WidgetTester tester,
  ) async {
    final _SearchRepository repo = _SearchRepository(
      cuisines: <FoodCuisine>[
        const FoodCuisine(
          id: 'c1',
          cuisineCode: 'korean',
          displayNameKo: '한식',
          sortOrder: 0,
        ),
      ],
      results: <FoodCatalogItem>[
        const FoodCatalogItem(
          id: 'f1',
          cuisineCode: 'korean',
          courseCode: 'rice',
          canonicalNameKo: '비빔밥',
          source: 'seed',
        ),
      ],
    );
    await pump(tester, repo);
    await tester.pumpAndSettle();

    expect(find.text('전체'), findsOneWidget);
    expect(find.text('한식'), findsOneWidget);
    expect(find.text('비빔밥'), findsOneWidget);
  });

  testWidgets('debounces text input before searching', (
    WidgetTester tester,
  ) async {
    final _SearchRepository repo = _SearchRepository();
    await pump(tester, repo);
    await tester.pumpAndSettle();
    repo.queries.clear();

    await tester.enterText(find.byType(TextField), '비');
    await tester.enterText(find.byType(TextField), '비빔');
    // 300ms 전에는 검색이 나가지 않는다.
    await tester.pump(const Duration(milliseconds: 100));
    expect(repo.queries, isEmpty);
    // 300ms 후 마지막 입력으로 1회 검색.
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pumpAndSettle();
    expect(repo.queries, <String?>['비빔']);
  });

  testWidgets('selecting a chip filters by cuisine code', (
    WidgetTester tester,
  ) async {
    final _SearchRepository repo = _SearchRepository(
      cuisines: <FoodCuisine>[
        const FoodCuisine(
          id: 'c1',
          cuisineCode: 'korean',
          displayNameKo: '한식',
          sortOrder: 0,
        ),
      ],
    );
    await pump(tester, repo);
    await tester.pumpAndSettle();
    repo.cuisineFilters.clear();

    await tester.tap(find.text('한식'));
    await tester.pumpAndSettle();
    expect(repo.cuisineFilters, contains('korean'));
  });

  testWidgets('empty results show the searchEmpty state with the query', (
    WidgetTester tester,
  ) async {
    final _SearchRepository repo = _SearchRepository();
    await pump(tester, repo);
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), '없는음식');
    await tester.pump(const Duration(milliseconds: 350));
    await tester.pumpAndSettle();

    expect(find.text("'없는음식' 검색 결과가 없어요"), findsOneWidget);
  });

  testWidgets('picking an item adds it and returns it on confirm', (
    WidgetTester tester,
  ) async {
    final _SearchRepository repo = _SearchRepository(
      results: <FoodCatalogItem>[
        const FoodCatalogItem(
          id: 'f1',
          cuisineCode: 'korean',
          courseCode: 'rice',
          canonicalNameKo: '비빔밥',
          source: 'seed',
        ),
      ],
    );
    List<MealFoodItemInput>? popped;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (BuildContext context) {
              return ElevatedButton(
                onPressed: () async {
                  popped = await Navigator.of(context)
                      .push<List<MealFoodItemInput>>(
                        MaterialPageRoute<List<MealFoodItemInput>>(
                          builder: (BuildContext context) => FoodSearchScreen(
                            repository: RecordsRepository(repository: repo),
                          ),
                        ),
                      );
                },
                child: const Text('open'),
              );
            },
          ),
        ),
      ),
    );
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();

    // ⊕ 로 담기 → '담은 항목 1개' 바 노출.
    await tester.tap(find.byIcon(Icons.add_rounded));
    await tester.pumpAndSettle();
    expect(find.text('담은 항목 1개'), findsOneWidget);

    await tester.tap(find.text('기록에 추가하기'));
    await tester.pumpAndSettle();

    expect(popped, isNotNull);
    expect(popped!.length, 1);
    expect(popped!.first.displayName, '비빔밥');
    expect(popped!.first.foodCatalogItemId, 'f1');
    expect(popped!.first.source, 'database_match');
  });

  testWidgets('copy avoids prohibited medical terms', (
    WidgetTester tester,
  ) async {
    await pump(tester, _SearchRepository());
    await tester.pumpAndSettle();

    const List<String> banned = <String>['진단', '처방', '치료', '효능'];
    final Iterable<Text> texts = tester.widgetList<Text>(find.byType(Text));
    for (final Text widget in texts) {
      final String? data = widget.data;
      if (data == null) continue;
      for (final String term in banned) {
        expect(data.contains(term), isFalse, reason: '"$data" 에 "$term"');
      }
    }
  });
}

class _SearchRepository implements LemonAidRepository {
  _SearchRepository({
    this.cuisines = const <FoodCuisine>[],
    this.results = const <FoodCatalogItem>[],
  });

  final List<FoodCuisine> cuisines;
  final List<FoodCatalogItem> results;
  final List<String?> queries = <String?>[];
  final List<String?> cuisineFilters = <String?>[];

  @override
  Future<FoodCuisineList> fetchCuisines() async =>
      FoodCuisineList(results: cuisines);

  @override
  Future<FoodCatalogList> searchFoods({
    String? q,
    String? cuisineCode,
    int limit = 50,
    int offset = 0,
  }) async {
    queries.add(q);
    cuisineFilters.add(cuisineCode);
    // 빈 검색어가 아닌 '없는음식' 쿼리는 빈 결과.
    if (q == '없는음식') return FoodCatalogList.empty;
    return FoodCatalogList(results: results, limit: limit, offset: offset);
  }

  @override
  void close() {}

  @override
  dynamic noSuchMethod(Invocation invocation) {
    throw UnimplementedError('Unexpected call: ${invocation.memberName}');
  }
}
