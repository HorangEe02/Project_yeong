import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_models.dart';
import 'package:lemon_aid_mobile/widgets/common/food_candidate_list.dart';

MealFoodCandidate _candidate({
  required String name,
  required double confidence,
  double? kcal,
  double? carbG,
  double? proteinG,
  double? fatG,
}) {
  return MealFoodCandidate(
    displayName: name,
    portionAmount: null,
    portionUnit: null,
    kcal: kcal,
    carbG: carbG,
    proteinG: proteinG,
    fatG: fatG,
    sodiumMg: null,
    confidence: confidence,
    source: 'vision',
  );
}

Future<void> _pumpList(
  WidgetTester tester, {
  required List<MealFoodCandidate> candidates,
  required int? selectedIndex,
  ValueChanged<int>? onSelect,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: FoodCandidateList(
            candidates: candidates,
            selectedIndex: selectedIndex,
            onSelect: onSelect ?? (int _) {},
            portionAmount: 1,
            onAdjustPortion: () {},
          ),
        ),
      ),
    ),
  );
}

void main() {
  testWidgets('renders grade chips from confidence without raw %', (
    WidgetTester tester,
  ) async {
    await _pumpList(
      tester,
      selectedIndex: 0,
      candidates: <MealFoodCandidate>[
        _candidate(name: '비빔밥', confidence: 0.92, kcal: 520, carbG: 78),
        _candidate(name: '제육덮밥', confidence: 0.62),
        _candidate(name: '김치찌개', confidence: 0.4),
      ],
    );

    // D2: 등급 칩만 노출, % 숫자 비노출.
    expect(find.text('신뢰도 높음'), findsOneWidget); // 0.92
    expect(find.text('신뢰도 보통'), findsOneWidget); // 0.62
    expect(find.text('신뢰도 직접 확인 필요'), findsOneWidget); // 0.4
    expect(find.textContaining('%'), findsNothing);
    expect(find.textContaining('92'), findsNothing);
  });

  testWidgets('shows nutrition summary only for present fields', (
    WidgetTester tester,
  ) async {
    await _pumpList(
      tester,
      selectedIndex: 0,
      candidates: <MealFoodCandidate>[
        _candidate(name: '비빔밥', confidence: 0.9, kcal: 520, proteinG: 18),
      ],
    );

    expect(find.textContaining('520kcal'), findsOneWidget);
    expect(find.textContaining('단 18g'), findsOneWidget);
    // 누락 필드(탄수/지방)는 표시되지 않는다.
    expect(find.textContaining('탄 '), findsNothing);
    expect(find.textContaining('지 '), findsNothing);
  });

  testWidgets('only the selected candidate shows the portion row', (
    WidgetTester tester,
  ) async {
    await _pumpList(
      tester,
      selectedIndex: 1,
      candidates: <MealFoodCandidate>[
        _candidate(name: '비빔밥', confidence: 0.9),
        _candidate(name: '제육덮밥', confidence: 0.8),
      ],
    );

    expect(find.text('섭취량'), findsOneWidget);
  });

  testWidgets('tapping a candidate reports the index', (
    WidgetTester tester,
  ) async {
    int? selected;
    await _pumpList(
      tester,
      selectedIndex: 0,
      onSelect: (int index) => selected = index,
      candidates: <MealFoodCandidate>[
        _candidate(name: '비빔밥', confidence: 0.9),
        _candidate(name: '제육덮밥', confidence: 0.8),
      ],
    );

    await tester.tap(find.text('제육덮밥'));
    await tester.pump();
    expect(selected, 1);
  });

  testWidgets('candidate copy carries no medical-claim words', (
    WidgetTester tester,
  ) async {
    await _pumpList(
      tester,
      selectedIndex: 0,
      candidates: <MealFoodCandidate>[
        _candidate(name: '비빔밥', confidence: 0.9),
      ],
    );

    for (final String banned in <String>['진단', '처방', '치료', '효능']) {
      expect(find.textContaining(banned), findsNothing);
    }
  });
}
