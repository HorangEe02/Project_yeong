import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;
import 'package:lemon_aid_mobile/app_controller.dart';
import 'package:lemon_aid_mobile/core/api/api_client.dart';
import 'package:lemon_aid_mobile/core/storage/local_prefs.dart';
import 'package:lemon_aid_mobile/features/consent/consent_models.dart';
import 'package:lemon_aid_mobile/features/dashboard/dashboard_models.dart';
import 'package:lemon_aid_mobile/features/dashboard/home_models.dart';
import 'package:lemon_aid_mobile/features/nutrition/kdri_models.dart';
import 'package:lemon_aid_mobile/features/profile/profile_repository.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_repository.dart';
import 'package:lemon_aid_mobile/features/supplements/comprehensive_analysis_models.dart';
import 'package:lemon_aid_mobile/screens/dashboard_screen.dart';
import 'package:lemon_aid_mobile/shared/score_label_colors.dart';
import 'package:lemon_aid_mobile/utils/design_tokens_v2.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('shows the ready health score and a calm interaction state', (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      repository: _HomeRepository(
        healthScore: const DashboardHealthScore(
          status: HealthScoreStatus.ready,
          score: 78,
          label: 'good',
          labelText: '좋아요',
          message: '오늘 활동량이 좋아요.',
        ),
        supplements: const HomeSupplementsResult(
          results: <HomeSupplement>[
            HomeSupplement(
              id: 'sup-1',
              displayName: '비타민 D',
              manufacturer: '레몬랩스',
              categoryLabel: '비타민B',
              schedule: HomeSupplementSchedule(
                frequency: 'daily',
                timeOfDay: <String>['morning'],
                timesPerDay: 1,
              ),
            ),
          ],
          limit: 50,
          offset: 0,
        ),
        impact: _impact(risks: const <SupplementNutritionInsight>[]),
      ),
    );
    await controller.bootstrap();

    await _pumpScreen(tester, controller);

    expect(find.text('78'), findsOneWidget);
    expect(find.text('오늘의 분석'), findsOneWidget);
    expect(find.textContaining('오늘 활동량이 좋아요.'), findsOneWidget);
    // 홈 라벨 캡션이 오늘의 분석과 같은 등급 매핑 색을 쓴다
    // (가이드 06 §4.4-4 두 화면 정합 회귀 가드).
    final Text labelCaption = tester.widget<Text>(find.text('좋아요'));
    expect(labelCaption.style?.color, scoreLabelColor('good'));
    expect(find.text('안심하고 드셔도 돼요'), findsOneWidget);
    expect(find.text('영양제 관리'), findsOneWidget);
    expect(find.text('비타민 D'), findsOneWidget);
    // 사용자가 고른 분류가 영양제 행에 칩으로 표시된다 (가이드 10 P2 7 후속).
    expect(find.text('비타민B'), findsOneWidget);
    // 복약 카드 빈 상태 (약 0개).
    expect(find.text('복약 관리'), findsOneWidget);
    expect(find.text('약 등록하기'), findsOneWidget);
    // '영양소 상세 보기'는 풀폭 옐로 CTA 스타일 (figma 268:24, 가이드 10 ③-P2 5).
    expect(
      find.ancestor(
        of: find.text('영양소 상세 보기'),
        matching: find.byWidgetPredicate(
          (Widget w) =>
              w is Container &&
              w.decoration is BoxDecoration &&
              (w.decoration! as BoxDecoration).color == AppColor.brandSoft,
        ),
      ),
      findsOneWidget,
    );
  });

  testWidgets('injects the backend KDRI energy target into the kcal row', (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      repository: _HomeRepository(
        healthScore: const DashboardHealthScore(
          status: HealthScoreStatus.notReady,
        ),
        supplements: HomeSupplementsResult.empty,
        impact: _impact(risks: const <SupplementNutritionInsight>[]),
        kdris: const KdriLookupResult(
          references: <KdriReference>[
            KdriReference(
              nutrientCode: 'energy_kcal',
              referenceType: 'EER',
              referenceUnit: 'kcal',
              referenceAmount: 1700,
            ),
          ],
          datasetStatus: 'official',
          datasetVersion: 'kdris-2025',
        ),
      ),
    );
    await controller.bootstrap();

    await _pumpScreen(
      tester,
      controller,
      profileRepository: _profileRepository(<String, dynamic>{
        'sex': 'female',
        'birth_year': 1961,
      }),
    );

    // 백엔드 EER 값이 그대로 '소비/목표' 모드로 주입된다 — 클라이언트 계산
    // 금지 (가이드 02 ④-13).
    expect(find.textContaining('/ 1700 kcal'), findsOneWidget);
    expect(find.textContaining('오늘 기록 합계'), findsNothing);
    // 잔여는 표시하되, 소모 kcal 은 Health Connect 주입 전에는 어떤 추정치도
    // 노출하지 않는다 (가이드 02 ④-14 — 날조 금지).
    expect(
      find.textContaining('더 먹을 수 있어요', findRichText: true),
      findsOneWidget,
    );
    expect(find.textContaining('kcal 소모', findRichText: true), findsNothing);
  });

  testWidgets('keeps the totals-only kcal mode without a profile snapshot', (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      repository: _HomeRepository(
        healthScore: const DashboardHealthScore(
          status: HealthScoreStatus.notReady,
        ),
        supplements: HomeSupplementsResult.empty,
        impact: _impact(risks: const <SupplementNutritionInsight>[]),
      ),
    );
    await controller.bootstrap();

    await _pumpScreen(
      tester,
      controller,
      profileRepository: _profileRepository(<String, dynamic>{
        'status': 'not_ready',
      }),
    );

    // 프로필 미확보 시 목표 추정치를 날조하지 않는다 — 기록 합계 모드 유지.
    expect(find.textContaining('오늘 기록 합계'), findsOneWidget);
  });

  testWidgets('shows the not_ready prompt when the score is unavailable', (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      repository: _HomeRepository(
        healthScore: const DashboardHealthScore(
          status: HealthScoreStatus.notReady,
        ),
        supplements: HomeSupplementsResult.empty,
        impact: _impact(risks: const <SupplementNutritionInsight>[]),
      ),
    );
    await controller.bootstrap();

    await _pumpScreen(tester, controller);

    expect(find.text('기록을 추가하면 점수를 보여드려요'), findsOneWidget);
    // 영양제·약이 모두 없으면 상호작용 카드는 ③ 미등록 안내 상태.
    expect(find.text('등록된 영양제·약이 없어요'), findsOneWidget);
  });

  testWidgets('lists interaction risks when the preview reports them', (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      repository: _HomeRepository(
        healthScore: const DashboardHealthScore(
          status: HealthScoreStatus.notReady,
        ),
        supplements: const HomeSupplementsResult(
          results: <HomeSupplement>[
            HomeSupplement(
              id: 'sup-1',
              displayName: '비타민 D',
              manufacturer: null,
              schedule: null,
            ),
          ],
          limit: 50,
          offset: 0,
        ),
        impact: _impact(
          risks: const <SupplementNutritionInsight>[
            SupplementNutritionInsight(
              nutrientCode: 'vitamin_d',
              nutrientName: '비타민 D',
              actionLabel: '중복 확인',
              reasonCode: 'duplicate_input',
              supplementDailyAmount: 50,
              estimatedTotalAmount: 50,
              referenceUnit: 'mcg',
              userMessage: '비타민 D 섭취가 겹칠 수 있어요.',
            ),
          ],
        ),
      ),
    );
    await controller.bootstrap();

    await _pumpScreen(tester, controller);

    expect(find.text('확인이 필요해요 · 1건'), findsOneWidget);
    expect(find.textContaining('비타민 D 섭취가 겹칠 수 있어요.'), findsOneWidget);
  });

  testWidgets('renders the medication card list with class and tag labels', (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      repository: _HomeRepository(
        healthScore: const DashboardHealthScore(
          status: HealthScoreStatus.notReady,
        ),
        supplements: HomeSupplementsResult.empty,
        impact: _impact(risks: const <SupplementNutritionInsight>[]),
        medications: const HomeMedicationsResult(
          items: <HomeMedication>[
            HomeMedication(
              id: 'med-1',
              displayName: '아모디핀',
              medicationClass: 'calcium_channel_blocker',
              conditionTags: <String>['hypertension', 'diabetes', 'other'],
            ),
          ],
        ),
      ),
    );
    await controller.bootstrap();

    await _pumpScreen(tester, controller);

    expect(find.text('복약 관리'), findsOneWidget);
    expect(find.text('아모디핀'), findsOneWidget);
    expect(find.text('칼슘 채널 차단제'), findsOneWidget);
    // condition_tags 칩 최대 2 + n.
    expect(find.text('고혈압'), findsOneWidget);
    expect(find.text('당뇨'), findsOneWidget);
    expect(find.text('+1'), findsOneWidget);
    // 약 ≥1 이면 상호작용 카드에 약 기준 각주가 붙는다.
    expect(find.textContaining('등록한 약 1개 기준으로 함께 살펴봐요'), findsOneWidget);
  });

  testWidgets('toggles the medication intake check', (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      repository: _HomeRepository(
        healthScore: const DashboardHealthScore(
          status: HealthScoreStatus.notReady,
        ),
        supplements: HomeSupplementsResult.empty,
        impact: _impact(risks: const <SupplementNutritionInsight>[]),
        medications: const HomeMedicationsResult(
          items: <HomeMedication>[
            HomeMedication(id: 'med-1', displayName: '아모디핀'),
          ],
        ),
      ),
    );
    await controller.bootstrap();

    await _pumpScreen(tester, controller);

    expect(find.text('0/1 완료'), findsOneWidget);

    await tester.ensureVisible(find.text('아모디핀'));
    await tester.pump();
    await tester.tap(find.text('아모디핀'));
    await tester.pump();

    expect(find.text('1/1 완료'), findsOneWidget);
  });

  testWidgets('add medication sheet keeps the submit disabled until a name is '
      'entered', (WidgetTester tester) async {
    final AppController controller = AppController(
      repository: _HomeRepository(
        healthScore: const DashboardHealthScore(
          status: HealthScoreStatus.notReady,
        ),
        supplements: HomeSupplementsResult.empty,
        impact: _impact(risks: const <SupplementNutritionInsight>[]),
      ),
    );
    await controller.bootstrap();

    await _pumpScreen(tester, controller);

    await tester.ensureVisible(find.text('약 등록하기'));
    await tester.pump();
    await tester.tap(find.text('약 등록하기'));
    await tester.pumpAndSettle();

    expect(find.text('약 추가'), findsOneWidget);
    // 이름이 비어 있으면 '추가하기' 버튼은 비활성 (onPressed null).
    final AppPrimaryButton disabled = tester.widget<AppPrimaryButton>(
      find.widgetWithText(AppPrimaryButton, '추가하기'),
    );
    expect(disabled.enabled, isFalse);

    await tester.enterText(find.byType(TextField).first, '아모디핀');
    await tester.pump();

    final AppPrimaryButton enabled = tester.widget<AppPrimaryButton>(
      find.widgetWithText(AppPrimaryButton, '추가하기'),
    );
    expect(enabled.enabled, isTrue);
  });

  testWidgets('new medication card copy avoids prohibited medical terms', (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      repository: _HomeRepository(
        healthScore: const DashboardHealthScore(
          status: HealthScoreStatus.notReady,
        ),
        supplements: HomeSupplementsResult.empty,
        impact: _impact(risks: const <SupplementNutritionInsight>[]),
        medications: const HomeMedicationsResult(
          items: <HomeMedication>[
            HomeMedication(id: 'med-1', displayName: '아모디핀'),
          ],
        ),
      ),
    );
    await controller.bootstrap();

    await _pumpScreen(tester, controller);

    // 복약 카드/각주 신규 문구.
    const List<String> newCopy = <String>[
      '복약 관리',
      '약 변경은 의사·약사와 상담해주세요.',
      '복용 중인 약을 등록하면 음식·영양제 궁합을 확인해드려요.',
      '등록한 약 1개 기준으로 함께 살펴봐요 · 방금 확인',
      '복용 시점·용량 안내는 의사·약사와 상담해주세요.',
    ];
    const List<String> bannedTerms = <String>['진단', '처방', '치료', '효능'];
    for (final String copy in newCopy) {
      for (final String banned in bannedTerms) {
        expect(
          copy.contains(banned),
          isFalse,
          reason: '"$copy" 에 금칙어 "$banned" 가 포함됨',
        );
      }
    }
  });

  testWidgets('shows the kcal watch-lock caption without an estimate', (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      repository: _HomeRepository(
        healthScore: const DashboardHealthScore(
          status: HealthScoreStatus.ready,
          score: 70,
        ),
        supplements: HomeSupplementsResult.empty,
        impact: _impact(risks: const <SupplementNutritionInsight>[]),
      ),
    );
    await controller.bootstrap();

    await _pumpScreen(tester, controller);

    // 목표 kcal 미연동 — 잠금 캡션 노출, 소모/잔여 추정치 미노출.
    expect(find.text('워치를 연동하면 소모·잔여 칼로리도 보여드려요'), findsOneWidget);
    expect(find.text('오늘 먹은 음식 합계예요'), findsOneWidget);
    // '소모'/'더 먹을 수 있어요' 같은 추정 문구는 어디에도 없다.
    expect(find.textContaining('kcal 소모'), findsNothing);
    expect(find.textContaining('더 먹을 수 있어요'), findsNothing);
  });

  testWidgets("today's analysis card exposes a '자세히' deep link affordance", (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      repository: _HomeRepository(
        healthScore: const DashboardHealthScore(
          status: HealthScoreStatus.ready,
          score: 78,
          message: '오늘 활동량이 좋아요.',
        ),
        supplements: HomeSupplementsResult.empty,
        impact: _impact(risks: const <SupplementNutritionInsight>[]),
      ),
    );
    await controller.bootstrap();

    await _pumpScreen(tester, controller);

    expect(find.text('오늘의 분석'), findsOneWidget);
    expect(find.text('자세히'), findsOneWidget);
  });

  testWidgets("today's analysis card deep-links to the score tab", (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      repository: _HomeRepository(
        healthScore: const DashboardHealthScore(
          status: HealthScoreStatus.ready,
          score: 78,
          message: '오늘 활동량이 좋아요.',
        ),
        supplements: HomeSupplementsResult.empty,
        impact: _impact(risks: const <SupplementNutritionInsight>[]),
      ),
    );
    await controller.bootstrap();

    final GoRouter router = GoRouter(
      initialLocation: '/shell/home',
      routes: <RouteBase>[
        GoRoute(
          path: '/shell/home',
          builder: (BuildContext context, GoRouterState state) =>
              DashboardScreen(controller: controller),
        ),
        GoRoute(
          path: '/shell/score',
          builder: (BuildContext context, GoRouterState state) =>
              const Scaffold(body: Text('분석 탭 화면')),
        ),
      ],
    );

    await tester.pumpWidget(MaterialApp.router(routerConfig: router));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pump(const Duration(milliseconds: 1300));
    await tester.pump(const Duration(milliseconds: 400));

    await tester.ensureVisible(find.text('자세히'));
    await tester.pump();
    await tester.tap(find.text('자세히'));
    await tester.pumpAndSettle();

    expect(find.text('분석 탭 화면'), findsOneWidget);
  });

  testWidgets('persists the supplement check across a screen rebuild', (
    WidgetTester tester,
  ) async {
    SharedPreferences.setMockInitialValues(<String, Object>{});
    final LocalPrefs prefs = await LocalPrefs.create();
    final AppController controller = AppController(
      repository: _HomeRepository(
        healthScore: const DashboardHealthScore(
          status: HealthScoreStatus.notReady,
        ),
        supplements: const HomeSupplementsResult(
          results: <HomeSupplement>[
            HomeSupplement(
              id: 'sup-1',
              displayName: '비타민 D',
              manufacturer: null,
              schedule: null,
            ),
          ],
          limit: 50,
          offset: 0,
        ),
        impact: _impact(risks: const <SupplementNutritionInsight>[]),
      ),
    );
    await controller.bootstrap();

    await tester.pumpWidget(
      MaterialApp(
        home: DashboardScreen(controller: controller, localPrefs: prefs),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pump(const Duration(milliseconds: 1300));
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.text('0/1 완료'), findsOneWidget);
    await tester.ensureVisible(find.text('비타민 D'));
    await tester.pump();
    await tester.tap(find.text('비타민 D'));
    await tester.pump();
    expect(find.text('1/1 완료'), findsOneWidget);

    // 토글이 prefs(오늘 날짜 키)에 영속됐는지 직접 확인.
    final DateTime today = DateTime.now();
    expect(prefs.supplementCheckedIds(today), contains('sup-1'));

    // 같은 prefs 를 가진 새 화면을 다시 띄우면 체크가 복원된다.
    await tester.pumpWidget(
      MaterialApp(
        home: DashboardScreen(controller: controller, localPrefs: prefs),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pump(const Duration(milliseconds: 1300));
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.text('1/1 완료'), findsOneWidget);
  });

  testWidgets('long-pressing a supplement deletes it with an undo toast', (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      repository: _HomeRepository(
        healthScore: const DashboardHealthScore(
          status: HealthScoreStatus.notReady,
        ),
        supplements: const HomeSupplementsResult(
          results: <HomeSupplement>[
            HomeSupplement(
              id: 'sup-1',
              displayName: '비타민 D',
              manufacturer: null,
              schedule: null,
            ),
          ],
          limit: 50,
          offset: 0,
        ),
        impact: _impact(risks: const <SupplementNutritionInsight>[]),
      ),
    );
    await controller.bootstrap();
    await _pumpScreen(tester, controller);

    expect(find.text('비타민 D'), findsOneWidget);
    await tester.ensureVisible(find.text('비타민 D'));
    await tester.pump();
    await tester.longPress(find.text('비타민 D'));
    await tester.pumpAndSettle();

    // 삭제 확인 모달 → 삭제.
    expect(find.text('이 기록을 삭제할까요?'), findsOneWidget);
    await tester.tap(find.text('삭제'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    // 낙관적 제거 + 실행취소 토스트.
    expect(find.text('영양제를 삭제했어요'), findsOneWidget);
    expect(find.text('실행취소'), findsOneWidget);
    expect(controller.homeSupplements.results, isEmpty);

    // 실행취소 시 복원된다.
    await tester.tap(find.text('실행취소'));
    await tester.pump();
    expect(controller.homeSupplements.results.length, 1);
  });

  testWidgets('renders the persistent weekly strip in main mode', (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      repository: _HomeRepository(
        healthScore: const DashboardHealthScore(
          status: HealthScoreStatus.notReady,
        ),
        supplements: HomeSupplementsResult.empty,
        impact: _impact(risks: const <SupplementNutritionInsight>[]),
      ),
    );
    await controller.bootstrap();

    await _pumpScreen(tester, controller);

    // 노랑 브랜드 헤더 (color: AppColor.brand) — 모든 헤더 스코프의 기준.
    final Finder header = find.byWidgetPredicate(
      (Widget w) => w is Container && w.color == AppColor.brand,
    );
    expect(header, findsOneWidget);

    // 요일 라벨 월~일이 메인 모드 헤더에 상시 노출된다.
    for (final String label in const <String>[
      '월',
      '화',
      '수',
      '목',
      '금',
      '토',
      '일',
    ]) {
      expect(
        find.descendant(of: header, matching: find.text(label)),
        findsOneWidget,
      );
    }

    // 월 드롭다운은 현재 선택 월을 보여준다 (오늘 기준).
    final DateTime now = DateTime.now();
    expect(
      find.descendant(of: header, matching: find.text('${now.month}월')),
      findsOneWidget,
    );

    // 헤더 '오늘' pill = softCard 그림자 컨테이너 안의 '오늘' 텍스트.
    // (히어로 카드의 brand 배지 '오늘'과 구분하기 위해 데코로 스코프.)
    final Finder todayPill = find.ancestor(
      of: find.text('오늘'),
      matching: find.byWidgetPredicate(
        (Widget w) =>
            w is Container &&
            w.decoration is BoxDecoration &&
            (w.decoration! as BoxDecoration).boxShadow == AppShadow.softCard,
      ),
    );

    // 오늘이면 헤더 '오늘' pill 은 숨김.
    expect(todayPill, findsNothing);

    // 이전 주로 이동 후 과거 날짜를 선택하면 헤더 '오늘' pill 이 나타난다.
    // 헤더 안 좌측 화살표만 탭 (히어로 카드의 하루 이동 화살표와 구분).
    await tester.tap(
      find.descendant(
        of: header,
        matching: find.byIcon(Icons.chevron_left_rounded),
      ),
    );
    await tester.pump();
    // 지난주 7일 중 헤더 strip 안에서 고유한 day 숫자를 골라 탭한다.
    final DateTime lastMonday = DateTime(
      now.year,
      now.month,
      now.day,
    ).subtract(Duration(days: now.weekday - 1 + 7));
    Finder? pastDay;
    for (int i = 0; i < 7; i++) {
      final Finder candidate = find.descendant(
        of: header,
        matching: find.text('${lastMonday.add(Duration(days: i)).day}'),
      );
      if (candidate.evaluate().length == 1) {
        pastDay = candidate;
        break;
      }
    }
    expect(pastDay, isNotNull, reason: '헤더 strip 에 고유한 day 숫자가 하나도 없음');
    await tester.tap(pastDay!);
    await tester.pump();
    // 본문 페이드 전환(AnimatedSwitcher 280ms)과 새 히어로 카드 진입
    // 애니메이션이 끝나길 기다린다 (_pumpScreen 과 동일 cadence — 펜딩 타이머 방지).
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pump(const Duration(milliseconds: 1300));
    await tester.pump(const Duration(milliseconds: 400));
    expect(todayPill, findsOneWidget);

    // 헤더(주간 strip)에는 신뢰도 % 가 노출되지 않는다.
    // (히어로 카드의 매크로 % '탄/단/지'는 헤더 밖이므로 스코프 제외.)
    expect(
      find.descendant(of: header, matching: find.textContaining('%')),
      findsNothing,
    );
  });
}

Future<void> _pumpScreen(
  WidgetTester tester,
  AppController controller, {
  ProfileRepository? profileRepository,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: DashboardScreen(
        controller: controller,
        profileRepository: profileRepository,
      ),
    ),
  );
  // 진입 애니메이션(게이지 차오름·스태거)이 끝나길 기다린다.
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 400));
  await tester.pump(const Duration(milliseconds: 1300));
  await tester.pump(const Duration(milliseconds: 400));
}

class _FakeClient extends http.BaseClient {
  _FakeClient(this.handler);

  final Future<http.StreamedResponse> Function(http.Request request) handler;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    return handler(request as http.Request);
  }
}

http.StreamedResponse _jsonResponse(Map<String, dynamic> body, int status) {
  return http.StreamedResponse(
    Stream<List<int>>.value(utf8.encode(jsonEncode(body))),
    status,
    headers: const <String, String>{'content-type': 'application/json'},
  );
}

// GET /health/profile-snapshots/latest 가 [latestBody] 를 돌려주는 저장소.
ProfileRepository _profileRepository(Map<String, dynamic> latestBody) {
  return ProfileRepository(
    apiClient: ApiClient(
      baseUrl: 'https://api.example.com/api/v1',
      httpClient: _FakeClient(
        (http.Request request) async => _jsonResponse(latestBody, 200),
      ),
    ),
  );
}

SupplementImpactPreviewResponse _impact({
  required List<SupplementNutritionInsight> risks,
}) {
  return SupplementImpactPreviewResponse(
    calculationVersion: 'v1',
    referenceVersion: 'kdri-2020',
    sourceManifestVersion: null,
    dataStatus: 'ready',
    currentSupplementContributions: const <SupplementContributionAggregate>[],
    deficiencySupportCandidates: const <SupplementNutritionInsight>[],
    excessOrDuplicateRisks: risks,
    missingProfileFields: const <String>[],
    safeUserMessage: risks.isEmpty
        ? '지금 등록된 영양제에서 중복·상한 신호는 없어요.'
        : '겹치는 성분이 있어 확인이 필요해요.',
    clinicalDisclaimer: '의료적 진단이 아니에요.',
    warnings: const <String>[],
    requiresUserConfirmation: risks.isNotEmpty,
  );
}

class _HomeRepository implements LemonAidRepository {
  _HomeRepository({
    required this.healthScore,
    required this.supplements,
    required this.impact,
    this.medications = HomeMedicationsResult.empty,
    this.kdris = KdriLookupResult.empty,
  });

  final DashboardHealthScore healthScore;
  final HomeSupplementsResult supplements;
  final SupplementImpactPreviewResponse impact;
  final HomeMedicationsResult medications;
  final KdriLookupResult kdris;

  @override
  Future<KdriLookupResult> lookupKdris({
    required int age,
    required String sex,
    String pregnancyStatus = 'none',
  }) async {
    return kdris;
  }

  @override
  Future<ConsentState> fetchConsents() async {
    return ConsentState(
      consents: <ConsentStatus>[
        _granted(AppController.ocrConsent),
        _granted(AppController.healthConsent),
      ],
    );
  }

  ConsentStatus _granted(String consentType) {
    return ConsentStatus(
      consentType: consentType,
      policyVersion: 'test',
      title: consentType,
      required: true,
      granted: true,
      occurredAt: DateTime.utc(2026, 6, 10),
      revokedAt: null,
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
        latestSteps: 5000,
        latestActivityScore: 80,
      ),
      weight: const DashboardWeightSummary(
        dataStatus: 'not_ready',
        latestWeightKg: null,
        predictedWeightKg: null,
      ),
      supplements: const DashboardSupplementSummary(
        registeredCount: 1,
        requiresReviewCount: 0,
      ),
      disclaimers: const <String>[],
      algorithmVersion: 'test',
      healthScore: healthScore,
    );
  }

  @override
  Future<HomeMealsResult> fetchMeals({
    DateTime? from,
    DateTime? to,
    int limit = 50,
    int offset = 0,
  }) async {
    return HomeMealsResult.empty;
  }

  @override
  Future<HomeSupplementsResult> fetchSupplements({
    int limit = 50,
    int offset = 0,
  }) async {
    return supplements;
  }

  @override
  Future<HomeMedicationsResult> fetchMedications() async {
    return medications;
  }

  @override
  Future<SupplementImpactPreviewResponse>
  fetchLatestSupplementRecommendation() async {
    return impact;
  }

  @override
  Future<ComprehensiveDietAnalysis> analyzeComprehensive({
    required List<Map<String, Object?>> ingredients,
    Map<String, dynamic>? userProfile,
    String persona = 'B',
  }) async {
    return ComprehensiveDietAnalysis.empty;
  }

  @override
  void close() {}

  @override
  dynamic noSuchMethod(Invocation invocation) {
    throw UnimplementedError('Unexpected call: ${invocation.memberName}');
  }
}
