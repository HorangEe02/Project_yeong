// test/widget/status_state_view_test.dart
//
// StatusStateView 변형별 타이틀/CTA 렌더 + 콜백 검증,
// 모달 3종(InteractionWarning / DeleteConfirm / Celebration) + UndoToast smoke 테스트.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/shared/widgets/status_state_view.dart';
import 'package:lemon_aid_mobile/widgets/common/app_modals.dart';

// ─────────────────────────────────────────────────
// 헬퍼
// ─────────────────────────────────────────────────

Widget _wrap(Widget child) => MaterialApp(
      home: Scaffold(body: child),
    );

// ─────────────────────────────────────────────────
// StatusStateView 테스트
// ─────────────────────────────────────────────────

void main() {
  group('StatusStateView — 변형별 타이틀', () {
    testWidgets('emptyNew: 타이틀과 CTA 렌더', (WidgetTester tester) async {
      var tapped = false;
      await tester.pumpWidget(
        _wrap(
          StatusStateView(
            variant: StatusStateVariant.emptyNew,
            onPrimary: () => tapped = true,
          ),
        ),
      );

      expect(find.text('아직 기록이 없어요'), findsOneWidget);
      expect(find.text('오늘 첫 끼니나 영양제를 사진으로 남겨볼까요?'), findsOneWidget);
      expect(find.text('촬영하기'), findsOneWidget);

      await tester.tap(find.text('촬영하기'));
      expect(tapped, isTrue);
    });

    testWidgets('syncFailed: 타이틀과 CTA 렌더', (WidgetTester tester) async {
      var tapped = false;
      await tester.pumpWidget(
        _wrap(
          StatusStateView(
            variant: StatusStateVariant.syncFailed,
            onPrimary: () => tapped = true,
          ),
        ),
      );

      expect(find.text('불러오지 못했어요'), findsOneWidget);
      expect(find.text('다시 시도'), findsOneWidget);

      await tester.tap(find.text('다시 시도'));
      expect(tapped, isTrue);
    });

    testWidgets('permissionDenied: 타이틀과 CTA 렌더', (WidgetTester tester) async {
      var tapped = false;
      await tester.pumpWidget(
        _wrap(
          StatusStateView(
            variant: StatusStateVariant.permissionDenied,
            onPrimary: () => tapped = true,
          ),
        ),
      );

      expect(find.text('권한이 필요해요'), findsOneWidget);
      expect(find.text('설정 열기'), findsOneWidget);

      await tester.tap(find.text('설정 열기'));
      expect(tapped, isTrue);
    });

    testWidgets('analysisFailed: 타이틀 + primary + secondary 렌더', (
      WidgetTester tester,
    ) async {
      var primaryTapped = false;
      var secondaryTapped = false;
      await tester.pumpWidget(
        _wrap(
          StatusStateView(
            variant: StatusStateVariant.analysisFailed,
            onPrimary: () => primaryTapped = true,
            onSecondary: () => secondaryTapped = true,
          ),
        ),
      );

      expect(find.text('분석하지 못했어요'), findsOneWidget);
      expect(find.text('다시 촬영'), findsOneWidget);
      expect(find.text('직접 입력하기'), findsOneWidget);

      await tester.tap(find.text('다시 촬영'));
      expect(primaryTapped, isTrue);

      await tester.tap(find.text('직접 입력하기'));
      expect(secondaryTapped, isTrue);
    });

    testWidgets('notificationsEmpty: 타이틀 렌더, CTA 없음', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        _wrap(
          const StatusStateView(
            variant: StatusStateVariant.notificationsEmpty,
          ),
        ),
      );

      expect(find.text('알림이 없어요'), findsOneWidget);
      expect(find.text('새로운 소식이 오면 여기에서 알려드릴게요'), findsOneWidget);
      // CTA 없음
      expect(find.byType(ElevatedButton), findsNothing);
      expect(find.byType(TextButton), findsNothing);
    });

    testWidgets('searchEmpty: 검색어 포함 타이틀 + CTA 렌더', (
      WidgetTester tester,
    ) async {
      var tapped = false;
      await tester.pumpWidget(
        _wrap(
          StatusStateView(
            variant: StatusStateVariant.searchEmpty,
            query: '비타민',
            onPrimary: () => tapped = true,
          ),
        ),
      );

      expect(find.textContaining('비타민'), findsOneWidget);
      expect(find.text('직접 추가하기'), findsOneWidget);

      await tester.tap(find.text('직접 추가하기'));
      expect(tapped, isTrue);
    });

    testWidgets('searchEmpty: 빈 검색어 처리', (WidgetTester tester) async {
      await tester.pumpWidget(
        _wrap(
          const StatusStateView(
            variant: StatusStateVariant.searchEmpty,
          ),
        ),
      );

      expect(find.text('검색 결과가 없어요'), findsOneWidget);
    });
  });

  // ─────────────────────────────────────────────────
  // 모달 smoke 테스트
  // ─────────────────────────────────────────────────

  group('showInteractionWarningDialog', () {
    testWidgets('타이틀·배너·버튼 렌더 확인', (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (BuildContext ctx) => ElevatedButton(
                key: const Key('open'),
                onPressed: () => showInteractionWarningDialog(
                  ctx,
                  body: '해당 영양제와 약물 간 주의가 필요해요.',
                  onViewDetail: () {},
                  onSaveAnyway: () {},
                ),
                child: const Text('열기'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byKey(const Key('open')));
      await tester.pumpAndSettle();

      expect(find.text('잠깐, 확인해 주세요'), findsOneWidget);
      expect(find.text('해당 영양제와 약물 간 주의가 필요해요.'), findsOneWidget);
      expect(find.text('드시기 전 의사·약사와 상담을 권해요'), findsOneWidget);
      expect(find.text('안전 정보 자세히 보기'), findsOneWidget);
      expect(find.text('그래도 저장할게요'), findsOneWidget);
    });

    testWidgets('onViewDetail 콜백 호출', (WidgetTester tester) async {
      var detailCalled = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (BuildContext ctx) => ElevatedButton(
                key: const Key('open'),
                onPressed: () => showInteractionWarningDialog(
                  ctx,
                  body: '주의가 필요해요.',
                  onViewDetail: () => detailCalled = true,
                  onSaveAnyway: () {},
                ),
                child: const Text('열기'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byKey(const Key('open')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('안전 정보 자세히 보기'));
      await tester.pumpAndSettle();

      expect(detailCalled, isTrue);
    });

    testWidgets('onSaveAnyway 콜백 호출', (WidgetTester tester) async {
      var saveAnywayTapped = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (BuildContext ctx) => ElevatedButton(
                key: const Key('open'),
                onPressed: () => showInteractionWarningDialog(
                  ctx,
                  body: '주의.',
                  onViewDetail: () {},
                  onSaveAnyway: () => saveAnywayTapped = true,
                ),
                child: const Text('열기'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byKey(const Key('open')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('그래도 저장할게요'));
      await tester.pumpAndSettle();

      expect(saveAnywayTapped, isTrue);
    });
  });

  group('showDeleteConfirmDialog', () {
    testWidgets('타이틀·레이블·버튼 렌더 확인', (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (BuildContext ctx) => ElevatedButton(
                key: const Key('open'),
                onPressed: () => showDeleteConfirmDialog(
                  ctx,
                  targetLabel: '비타민 C 1000mg',
                ),
                child: const Text('열기'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byKey(const Key('open')));
      await tester.pumpAndSettle();

      expect(find.text('이 기록을 삭제할까요?'), findsOneWidget);
      expect(find.textContaining('비타민 C 1000mg'), findsOneWidget);
      expect(find.text('취소'), findsOneWidget);
      expect(find.text('삭제'), findsOneWidget);
    });

    testWidgets('취소 버튼 → false 반환', (WidgetTester tester) async {
      bool? result;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (BuildContext ctx) => ElevatedButton(
                key: const Key('open'),
                onPressed: () async {
                  result = await showDeleteConfirmDialog(
                    ctx,
                    targetLabel: '기록',
                  );
                },
                child: const Text('열기'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byKey(const Key('open')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('취소'));
      await tester.pumpAndSettle();

      expect(result, isFalse);
    });

    testWidgets('삭제 버튼 → true 반환', (WidgetTester tester) async {
      bool? result;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (BuildContext ctx) => ElevatedButton(
                key: const Key('open'),
                onPressed: () async {
                  result = await showDeleteConfirmDialog(
                    ctx,
                    targetLabel: '기록',
                  );
                },
                child: const Text('열기'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byKey(const Key('open')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('삭제'));
      await tester.pumpAndSettle();

      expect(result, isTrue);
    });
  });

  group('showCelebrationDialog', () {
    testWidgets('타이틀·본문·확인 버튼 렌더 확인', (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (BuildContext ctx) => ElevatedButton(
                key: const Key('open'),
                onPressed: () => showCelebrationDialog(
                  ctx,
                  title: '목표 달성!',
                  body: '꾸준히 기록해 주셔서 감사해요.',
                ),
                child: const Text('열기'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byKey(const Key('open')));
      await tester.pumpAndSettle();

      expect(find.text('목표 달성!'), findsOneWidget);
      expect(find.text('꾸준히 기록해 주셔서 감사해요.'), findsOneWidget);
      expect(find.text('확인'), findsOneWidget);
    });

    testWidgets('확인 버튼으로 다이얼로그 닫힘', (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (BuildContext ctx) => ElevatedButton(
                key: const Key('open'),
                onPressed: () => showCelebrationDialog(
                  ctx,
                  title: '달성!',
                  body: '잘하셨어요.',
                ),
                child: const Text('열기'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byKey(const Key('open')));
      await tester.pumpAndSettle();

      expect(find.text('달성!'), findsOneWidget);

      await tester.tap(find.text('확인'));
      await tester.pumpAndSettle();

      expect(find.text('달성!'), findsNothing);
    });
  });

  group('showUndoToast', () {
    testWidgets('메시지와 실행취소 액션 렌더', (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (BuildContext ctx) => ElevatedButton(
                key: const Key('open'),
                onPressed: () => showUndoToast(
                  ctx,
                  message: '기록이 삭제되었어요.',
                  onUndo: () {},
                ),
                child: const Text('열기'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byKey(const Key('open')));
      await tester.pumpAndSettle();

      expect(find.text('기록이 삭제되었어요.'), findsOneWidget);
      expect(find.text('실행취소'), findsOneWidget);
    });

    testWidgets('실행취소 탭 → onUndo 콜백 호출', (WidgetTester tester) async {
      var undoCalled = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (BuildContext ctx) => ElevatedButton(
                key: const Key('open'),
                onPressed: () => showUndoToast(
                  ctx,
                  message: '삭제되었어요.',
                  onUndo: () => undoCalled = true,
                ),
                child: const Text('열기'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.byKey(const Key('open')));
      // SnackBar 입장 애니메이션이 끝날 때까지 대기
      await tester.pumpAndSettle();
      // SnackBarAction 은 TextButton 으로 렌더링 — 타입으로 찾아 탭
      await tester.tap(find.widgetWithText(TextButton, '실행취소'));
      await tester.pump();

      expect(undoCalled, isTrue);
    });
  });
}
