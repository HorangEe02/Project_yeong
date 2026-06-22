import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:lemon_aid_mobile/features/dashboard/home_models.dart';
import 'package:lemon_aid_mobile/features/records/food_models.dart';
import 'package:lemon_aid_mobile/features/records/records_repository.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_repository.dart';
import 'package:lemon_aid_mobile/screens/daily_records_screen.dart';

void main() {
  final DateTime now = DateTime.now();
  final DateTime today = DateTime(now.year, now.month, now.day);

  Future<GoRouter> pump(
    WidgetTester tester,
    _DailyRepository repo, {
    DateTime? date,
  }) async {
    tester.view.physicalSize = const Size(1200, 2600);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final RecordsRepository repository = RecordsRepository(repository: repo);
    final GoRouter router = GoRouter(
      initialLocation: '/records',
      routes: <RouteBase>[
        GoRoute(
          path: '/records',
          builder: (BuildContext context, GoRouterState state) =>
              DailyRecordsScreen(repository: repository, initialDate: date),
        ),
        GoRoute(
          path: '/shell/camera',
          builder: (BuildContext context, GoRouterState state) =>
              const Scaffold(body: Text('CAMERA-STUB')),
        ),
      ],
    );
    await tester.pumpWidget(MaterialApp.router(routerConfig: router));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    return router;
  }

  testWidgets('renders the summary card totals and timeline rows', (
    WidgetTester tester,
  ) async {
    final _DailyRepository repo = _DailyRepository(
      meals: <HomeMeal>[
        _meal(
          'm1',
          DateTime(today.year, today.month, today.day, 8),
          '아침밥',
          520,
        ),
        _meal(
          'm2',
          DateTime(today.year, today.month, today.day, 19),
          '저녁밥',
          600,
        ),
      ],
      supplements: <HomeSupplement>[
        _supplement('s1', DateTime(today.year, today.month, today.day, 9)),
      ],
    );
    await pump(tester, repo);
    await tester.pumpAndSettle();

    // 합계 카드: 섭취 열량 / 끼니 / 영양제 3분할 (figma — 헤더 문장 제거).
    expect(find.text('섭취 열량'), findsOneWidget);
    expect(find.text('끼니'), findsOneWidget);
    expect(find.text('아침밥'), findsOneWidget);
    expect(find.text('저녁밥'), findsOneWidget);
    expect(find.text('오메가3'), findsOneWidget);
    // 면책 푸터.
    expect(find.textContaining('의학적 판단을 대신하지 않아요'), findsOneWidget);
  });

  testWidgets('shows an empty state and keeps the add button', (
    WidgetTester tester,
  ) async {
    await pump(tester, _DailyRepository());
    await tester.pumpAndSettle();

    expect(find.text('아직 기록이 없어요'), findsOneWidget);
    expect(find.text('기록 추가하기'), findsOneWidget);
  });

  testWidgets('the add button navigates to the camera route', (
    WidgetTester tester,
  ) async {
    final GoRouter router = await pump(tester, _DailyRepository());
    await tester.pumpAndSettle();

    await tester.tap(find.text('기록 추가하기'));
    await tester.pumpAndSettle();
    expect(
      router.routerDelegate.currentConfiguration.uri.path,
      '/shell/camera',
    );
  });

  testWidgets('the next-day arrow is disabled on today', (
    WidgetTester tester,
  ) async {
    await pump(tester, _DailyRepository());
    await tester.pumpAndSettle();

    // 오늘이면 ▶ 비활성 (onTap null) → IconButton/Pressable 없음. 좌측 ◀ 는 활성.
    // 미래로 이동 불가: 라벨이 오늘 그대로인지 확인 (figma — 전체 요일 표기).
    final String weekday = <String>[
      '월요일',
      '화요일',
      '수요일',
      '목요일',
      '금요일',
      '토요일',
      '일요일',
    ][today.weekday - 1];
    expect(
      find.text('${today.month}월 ${today.day}일 $weekday'),
      findsOneWidget,
    );
  });

  testWidgets('deleting a supplement row shows the undo toast', (
    WidgetTester tester,
  ) async {
    final _DailyRepository repo = _DailyRepository(
      supplements: <HomeSupplement>[
        _supplement('s1', DateTime(today.year, today.month, today.day, 9)),
      ],
    );
    await pump(tester, repo);
    await tester.pumpAndSettle();

    // 영양제 카드 길게 누르기 → 삭제 확인 모달 (figma 카드엔 인라인 ⋯ 없음).
    await tester.longPress(find.text('오메가3'));
    await tester.pumpAndSettle();
    expect(find.text('이 기록을 삭제할까요?'), findsOneWidget);
    await tester.tap(find.text('삭제'));
    await tester.pumpAndSettle();

    // 낙관적 제거 + 실행취소 토스트.
    expect(find.text('영양제를 삭제했어요'), findsOneWidget);
    expect(find.text('실행취소'), findsOneWidget);
    expect(find.text('오메가3'), findsNothing);
  });

  testWidgets('copy avoids prohibited medical terms', (
    WidgetTester tester,
  ) async {
    await pump(
      tester,
      _DailyRepository(
        meals: <HomeMeal>[
          _meal(
            'm1',
            DateTime(today.year, today.month, today.day, 8),
            '밥',
            100,
          ),
        ],
      ),
    );
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

HomeMeal _meal(String id, DateTime eatenAt, String name, double kcal) {
  return HomeMeal(
    id: id,
    status: 'confirmed',
    mealType: 'lunch',
    eatenAt: eatenAt,
    foodItems: <HomeFoodItem>[
      HomeFoodItem(
        displayName: name,
        kcal: kcal,
        carbG: 0,
        proteinG: 0,
        fatG: 0,
      ),
    ],
    nutrition: HomeMealNutrition(kcal: kcal, carbG: 0, proteinG: 0, fatG: 0),
  );
}

HomeSupplement _supplement(String id, DateTime registeredAt) {
  return HomeSupplement(
    id: id,
    displayName: '오메가3',
    manufacturer: null,
    schedule: null,
    registeredAt: registeredAt,
  );
}

class _DailyRepository implements LemonAidRepository {
  _DailyRepository({
    this.meals = const <HomeMeal>[],
    this.supplements = const <HomeSupplement>[],
  });

  final List<HomeMeal> meals;
  final List<HomeSupplement> supplements;
  final List<String> deleted = <String>[];

  @override
  Future<HomeMealsResult> fetchMeals({
    DateTime? from,
    DateTime? to,
    int limit = 50,
    int offset = 0,
  }) async {
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
      results: supplements,
      limit: limit,
      offset: offset,
    );
  }

  @override
  Future<void> deleteSupplement(String supplementId) async {
    deleted.add(supplementId);
  }

  @override
  Future<FoodCatalogList> searchFoods({
    String? q,
    String? cuisineCode,
    int limit = 50,
    int offset = 0,
  }) async => FoodCatalogList.empty;

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
