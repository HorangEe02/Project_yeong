import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/app_controller.dart';
import 'package:lemon_aid_mobile/features/consent/consent_models.dart';
import 'package:lemon_aid_mobile/features/dashboard/dashboard_models.dart';
import 'package:lemon_aid_mobile/features/dashboard/home_models.dart';
import 'package:lemon_aid_mobile/features/records/records_repository.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_repository.dart';
import 'package:lemon_aid_mobile/screens/calendar_screen.dart';

void main() {
  final DateTime now = DateTime.now();
  final DateTime today = DateTime(now.year, now.month, now.day);

  Future<void> pump(
    WidgetTester tester,
    _CalendarRepository repo,
  ) async {
    // 월 그리드(최대 6행) + 상세 카드 + 면책 푸터가 한 화면에 다 들어오도록
    // 충분히 큰 테스트 뷰포트를 사용한다 (ListView lazy build 회피).
    tester.view.physicalSize = const Size(1200, 2400);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final AppController controller = AppController(repository: repo);
    await tester.pumpWidget(
      MaterialApp(
        home: CalendarScreen(
          repository: RecordsRepository(repository: repo),
          controller: controller,
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
  }

  testWidgets('renders the month grid and weekday header', (
    WidgetTester tester,
  ) async {
    await pump(tester, _CalendarRepository());
    await tester.pumpAndSettle();

    expect(find.text('캘린더'), findsOneWidget);
    expect(find.text('${now.year}년 ${now.month}월'), findsOneWidget);
    // 요일 헤더 — 색+텍스트 병행.
    for (final String label in <String>['일', '월', '화', '수', '목', '금', '토']) {
      expect(find.text(label), findsWidgets);
    }
    // 면책 푸터.
    expect(find.textContaining('의학적 판단을 대신하지 않아요'), findsOneWidget);
  });

  testWidgets('shows a day detail with record rows when records exist', (
    WidgetTester tester,
  ) async {
    final _CalendarRepository repo = _CalendarRepository(
      meals: <HomeMeal>[
        HomeMeal(
          id: 'm1',
          status: 'confirmed',
          mealType: 'lunch',
          eatenAt: DateTime(today.year, today.month, today.day, 12),
          foodItems: const <HomeFoodItem>[
            HomeFoodItem(
              displayName: '비빔밥',
              kcal: 600,
              carbG: 0,
              proteinG: 0,
              fatG: 0,
            ),
          ],
          nutrition: const HomeMealNutrition(
            kcal: 600,
            carbG: 0,
            proteinG: 0,
            fatG: 0,
          ),
        ),
      ],
      supplements: <HomeSupplement>[
        HomeSupplement(
          id: 's1',
          displayName: '오메가3',
          manufacturer: null,
          schedule: null,
          registeredAt: DateTime(today.year, today.month, today.day, 9),
        ),
      ],
    );
    await pump(tester, repo);
    await tester.pumpAndSettle();

    // 선택일(오늘) 상세 카드 — 기록 N건 칩 + 행.
    expect(find.text('기록 2건'), findsOneWidget);
    expect(find.text('비빔밥'), findsOneWidget);
    expect(find.text('600 kcal'), findsOneWidget);
    expect(find.text('오메가3'), findsOneWidget);
  });

  testWidgets('shows an empty state for a day without records', (
    WidgetTester tester,
  ) async {
    await pump(tester, _CalendarRepository());
    await tester.pumpAndSettle();

    // 기록이 없으면 일자 상세에 emptyNew 상태.
    expect(find.text('기록 0건'), findsOneWidget);
    expect(find.text('아직 기록이 없어요'), findsOneWidget);
  });

  testWidgets('falls back to syncFailed when the month load fails', (
    WidgetTester tester,
  ) async {
    await pump(tester, _CalendarRepository(failMeals: true));
    await tester.pumpAndSettle();

    expect(find.text('불러오지 못했어요'), findsOneWidget);
  });

  testWidgets('calendar copy avoids prohibited medical terms', (
    WidgetTester tester,
  ) async {
    await pump(tester, _CalendarRepository());
    await tester.pumpAndSettle();

    const List<String> banned = <String>['진단', '처방', '치료', '효능'];
    final Iterable<Text> texts = tester.widgetList<Text>(find.byType(Text));
    for (final Text widget in texts) {
      final String? data = widget.data;
      if (data == null) continue;
      for (final String term in banned) {
        expect(
          data.contains(term),
          isFalse,
          reason: '"$data" 에 금칙어 "$term" 가 포함됨',
        );
      }
    }
  });
}

class _CalendarRepository implements LemonAidRepository {
  _CalendarRepository({
    this.meals = const <HomeMeal>[],
    this.supplements = const <HomeSupplement>[],
    this.failMeals = false,
  });

  final List<HomeMeal> meals;
  final List<HomeSupplement> supplements;
  final bool failMeals;

  @override
  Future<ConsentState> fetchConsents() async {
    return ConsentState(
      consents: <ConsentStatus>[
        ConsentStatus(
          consentType: AppController.ocrConsent,
          policyVersion: 'test',
          title: 'ocr',
          required: true,
          granted: true,
          occurredAt: DateTime.utc(2026, 6, 10),
          revokedAt: null,
        ),
        ConsentStatus(
          consentType: AppController.healthConsent,
          policyVersion: 'test',
          title: 'health',
          required: true,
          granted: true,
          occurredAt: DateTime.utc(2026, 6, 10),
          revokedAt: null,
        ),
      ],
    );
  }

  @override
  Future<HomeMealsResult> fetchMeals({
    DateTime? from,
    DateTime? to,
    int limit = 50,
    int offset = 0,
  }) async {
    if (failMeals) {
      throw StateError('boom');
    }
    if (offset > 0) {
      return HomeMealsResult.empty;
    }
    return HomeMealsResult(results: meals, limit: limit, offset: offset);
  }

  @override
  Future<HomeSupplementsResult> fetchSupplements({
    int limit = 50,
    int offset = 0,
  }) async {
    if (offset > 0) {
      return HomeSupplementsResult.empty;
    }
    return HomeSupplementsResult(
      results: supplements,
      limit: limit,
      offset: offset,
    );
  }

  @override
  Future<DashboardSummary> fetchDashboardSummary({int days = 30}) async {
    return DashboardSummary(
      asOf: DateTime.utc(2026, 6, 10),
      nutrition: const DashboardNutritionSummary(
        dataStatus: 'ready',
        lowCount: 0,
        highCount: 0,
        datasetVersion: 'test',
      ),
      activity: const DashboardActivitySummary(
        dataStatus: 'ready',
        latestSteps: 0,
        latestActivityScore: 0,
      ),
      weight: const DashboardWeightSummary(
        dataStatus: 'not_ready',
        latestWeightKg: null,
        predictedWeightKg: null,
      ),
      supplements: const DashboardSupplementSummary(
        registeredCount: 0,
        requiresReviewCount: 0,
      ),
      disclaimers: const <String>[],
      algorithmVersion: 'test',
      healthScore: const DashboardHealthScore(
        status: HealthScoreStatus.notReady,
      ),
    );
  }

  @override
  Future<HomeMedicationsResult> fetchMedications() async {
    return HomeMedicationsResult.empty;
  }

  @override
  void close() {}

  @override
  dynamic noSuchMethod(Invocation invocation) {
    throw UnimplementedError('Unexpected call: ${invocation.memberName}');
  }
}
