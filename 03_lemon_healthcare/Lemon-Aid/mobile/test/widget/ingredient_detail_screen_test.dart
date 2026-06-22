import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/features/nutrition/kdri_models.dart';
import 'package:lemon_aid_mobile/features/supplements/comprehensive_analysis_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_repository.dart';
import 'package:lemon_aid_mobile/screens/ingredient_detail_screen.dart';

// 사용자 노출 문구에 등장하면 안 되는 의료법 금칙어 (진단/처방/치료/효능).
const List<String> _forbiddenTerms = <String>['진단', '처방', '치료', '효능'];

void main() {
  testWidgets('renders identity, amount and %DV gauge from candidate', (
    WidgetTester tester,
  ) async {
    await _pumpDetail(
      tester,
      ingredient: _candidate(dailyValuePercent: 80),
      repository: _KdriRepository(result: _kdrisResult()),
    );
    await tester.pumpAndSettle();

    expect(find.text('비타민 C'), findsOneWidget);
    expect(find.text('500 mg'), findsOneWidget);
    expect(find.text('신뢰도 높음'), findsOneWidget);
    expect(
      find.byKey(const ValueKey<String>('ingredient-detail-amount-card')),
      findsOneWidget,
    );
    expect(find.textContaining('기준치 80%'), findsOneWidget);
    expect(find.textContaining('권장 범위'), findsOneWidget);
    // 신뢰도 % 숫자는 노출되지 않는다.
    expect(find.textContaining('92%'), findsNothing);
  });

  testWidgets('derives gauge percent from KDRIs when %DV is absent', (
    WidgetTester tester,
  ) async {
    await _pumpDetail(
      tester,
      ingredient: _candidate(amount: 100, unit: 'mg'),
      repository: _KdriRepository(result: _kdrisResult()),
    );
    await tester.pumpAndSettle();

    // 100mg / 100mg 기준 = 100% → 권장 범위.
    expect(find.textContaining('기준치 100%'), findsOneWidget);
  });

  testWidgets('flags over-upper-limit with danger wording when %DV exceeds UL', (
    WidgetTester tester,
  ) async {
    // reference 100mg, UL 2000mg → UL 은 2000% 위치. 2500% 면 상한 초과.
    await _pumpDetail(
      tester,
      ingredient: _candidate(dailyValuePercent: 2500),
      repository: _KdriRepository(result: _kdrisResult()),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('상한을 넘었어요'), findsOneWidget);
  });

  testWidgets('omits gauge when unit mismatch prevents a KDRIs ratio', (
    WidgetTester tester,
  ) async {
    await _pumpDetail(
      tester,
      // %DV 없음 + 단위 불일치(mcg vs mg) → 환산 날조 금지, 게이지 생략.
      ingredient: _candidate(amount: 100, unit: 'mcg', dailyValuePercent: null),
      repository: _KdriRepository(result: _kdrisResult()),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(
        const ValueKey<String>('ingredient-detail-gauge-unavailable'),
      ),
      findsOneWidget,
    );
    expect(find.textContaining('기준치 '), findsNothing);
  });

  testWidgets('falls back to amount-only view when KDRIs lookup fails', (
    WidgetTester tester,
  ) async {
    await _pumpDetail(
      tester,
      ingredient: _candidate(amount: 100, unit: 'mg', dailyValuePercent: null),
      repository: _KdriRepository(shouldFail: true),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey<String>('ingredient-detail-kdris-failed')),
      findsOneWidget,
    );
    // 함량은 그대로 표시되고 화면 자체는 유지된다.
    expect(find.text('100 mg'), findsOneWidget);
    expect(
      find.byKey(const ValueKey<String>('ingredient-detail-medical-note')),
      findsOneWidget,
    );
  });

  testWidgets('adds reference caption for non-official sample dataset', (
    WidgetTester tester,
  ) async {
    await _pumpDetail(
      tester,
      ingredient: _candidate(dailyValuePercent: 80),
      repository: _KdriRepository(result: _kdrisResult()),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('참고용 기준값이에요'), findsOneWidget);
  });

  testWidgets('renders helpful info bullets and source chips from explain', (
    WidgetTester tester,
  ) async {
    await _pumpDetail(
      tester,
      ingredient: _candidate(dailyValuePercent: 80),
      repository: _KdriRepository(result: _kdrisResult()),
      explanation: _explanation(),
    );
    await tester.pumpAndSettle();

    expect(find.text('이런 점에 도움을 줄 수 있어요'), findsOneWidget);
    expect(find.text('피로 회복에 참고할 수 있어요.'), findsOneWidget);
    expect(find.text('출처 · 비타민 C'), findsOneWidget);
  });

  testWidgets('hides helpful info section when no explanation is provided', (
    WidgetTester tester,
  ) async {
    await _pumpDetail(
      tester,
      ingredient: _candidate(dailyValuePercent: 80),
      repository: _KdriRepository(result: _kdrisResult()),
    );
    await tester.pumpAndSettle();

    expect(find.text('이런 점에 도움을 줄 수 있어요'), findsNothing);
    expect(
      find.byKey(const ValueKey<String>('ingredient-detail-helpful-card')),
      findsNothing,
    );
  });

  testWidgets(
    'shows caution banner only with chronic indications and a component match',
    (WidgetTester tester) async {
      await _pumpDetail(
        tester,
        ingredient: _candidate(dailyValuePercent: 80),
        repository: _KdriRepository(result: _kdrisResult()),
        comprehensive: _comprehensive(
          chronicIndications: <String>['diabetes'],
          cautionComponent: '비타민 C',
        ),
      );
      await tester.pumpAndSettle();

      expect(
        find.byKey(const ValueKey<String>('ingredient-detail-caution-banner')),
        findsOneWidget,
      );
      expect(find.text('복용 전 의료진과 상담해 보세요'), findsOneWidget);
    },
  );

  testWidgets('hides caution banner when no chronic disease indications', (
    WidgetTester tester,
  ) async {
    await _pumpDetail(
      tester,
      ingredient: _candidate(dailyValuePercent: 80),
      repository: _KdriRepository(result: _kdrisResult()),
      comprehensive: _comprehensive(
        chronicIndications: <String>[],
        cautionComponent: '비타민 C',
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey<String>('ingredient-detail-caution-banner')),
      findsNothing,
    );
  });

  testWidgets('hides caution banner when no component matches the ingredient', (
    WidgetTester tester,
  ) async {
    await _pumpDetail(
      tester,
      ingredient: _candidate(dailyValuePercent: 80),
      repository: _KdriRepository(result: _kdrisResult()),
      comprehensive: _comprehensive(
        chronicIndications: <String>['diabetes'],
        cautionComponent: '카페인',
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey<String>('ingredient-detail-caution-banner')),
      findsNothing,
    );
  });

  testWidgets('keeps the medical disclaimer footer present', (
    WidgetTester tester,
  ) async {
    await _pumpDetail(
      tester,
      ingredient: _candidate(dailyValuePercent: 80),
      repository: _KdriRepository(result: _kdrisResult()),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey<String>('ingredient-detail-medical-note')),
      findsOneWidget,
    );
  });

  testWidgets('keeps claim and insight cards free of forbidden terms', (
    WidgetTester tester,
  ) async {
    await _pumpDetail(
      tester,
      ingredient: _candidate(dailyValuePercent: 2500),
      repository: _KdriRepository(result: _kdrisResult()),
      explanation: _explanation(),
      comprehensive: _comprehensive(
        chronicIndications: <String>['diabetes'],
        cautionComponent: '비타민 C',
      ),
    );
    await tester.pumpAndSettle();

    // 금칙어 가드는 주장/안내 카드(식별·함량·도움·주의)에 적용한다. 하단 면책
    // 푸터는 "진단·처방이 아닌" 부정형 표준 문구라 의도적으로 제외한다.
    const List<ValueKey<String>> claimCardKeys = <ValueKey<String>>[
      ValueKey<String>('ingredient-detail-identity-card'),
      ValueKey<String>('ingredient-detail-amount-card'),
      ValueKey<String>('ingredient-detail-helpful-card'),
      ValueKey<String>('ingredient-detail-caution-banner'),
    ];
    for (final ValueKey<String> cardKey in claimCardKeys) {
      final Finder card = find.byKey(cardKey);
      expect(card, findsOneWidget, reason: '$cardKey 카드가 렌더돼야 합니다.');
      for (final Text text
          in tester.widgetList<Text>(find.descendant(
            of: card,
            matching: find.byType(Text),
          ))) {
        final String? data = text.data;
        if (data == null) continue;
        for (final String term in _forbiddenTerms) {
          expect(
            data.contains(term),
            isFalse,
            reason: '금칙어 "$term" 가 "$data" 에 노출되면 안 됩니다.',
          );
        }
      }
    }
  });

  testWidgets('uses "도움" wording instead of the forbidden "효능" label', (
    WidgetTester tester,
  ) async {
    await _pumpDetail(
      tester,
      ingredient: _candidate(dailyValuePercent: 80),
      repository: _KdriRepository(result: _kdrisResult()),
      explanation: _explanation(),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('도움을 줄 수 있어요'), findsOneWidget);
    expect(find.textContaining('효능'), findsNothing);
  });
}

Future<void> _pumpDetail(
  WidgetTester tester, {
  required SupplementIngredientCandidate ingredient,
  required LemonAidRepository repository,
  ComprehensiveDietAnalysis? comprehensive,
  SupplementRecommendationExplainResponse? explanation,
}) {
  return tester.pumpWidget(
    MaterialApp(
      home: IngredientDetailScreen(
        ingredient: ingredient,
        repository: repository,
        comprehensive: comprehensive,
        explanation: explanation,
      ),
    ),
  );
}

SupplementIngredientCandidate _candidate({
  String displayName = '비타민 C',
  String nutrientCode = 'vitamin_c_mg',
  double? amount = 500,
  String? unit = 'mg',
  double? dailyValuePercent,
}) {
  return SupplementIngredientCandidate(
    displayName: displayName,
    nutrientCode: nutrientCode,
    amount: amount,
    unit: unit,
    confidence: 0.92,
    source: 'ocr_llm_preview',
    dailyValuePercent: dailyValuePercent,
  );
}

KdriLookupResult _kdrisResult() {
  return const KdriLookupResult(
    references: <KdriReference>[
      KdriReference(
        nutrientCode: 'vitamin_c_mg',
        nutrientNameKo: '비타민 C',
        referenceType: 'RDA',
        referenceAmount: 100,
        referenceUnit: 'mg',
        ulAmount: 2000,
        ulUnit: 'mg',
        reviewStatus: 'reviewed',
      ),
    ],
    datasetStatus: 'sample',
    datasetVersion: 'kdris-2020-sample',
    note: '검수 진행 중인 표본 기준값입니다.',
  );
}

SupplementRecommendationExplainResponse _explanation() {
  return const SupplementRecommendationExplainResponse(
    safeUserMessage: '라벨 확인 값을 기준으로 안내합니다.',
    explanationBullets: <String>['피로 회복에 참고할 수 있어요.'],
    clinicalDisclaimer: '참고용 정보입니다.',
    blockedTermsDetected: <String>[],
    llmUsed: true,
    sourceCitations: <SupplementExplanationSourceCitation>[
      SupplementExplanationSourceCitation(
        title: '비타민 C',
        sourcePath: 'vitamin-c.md',
        heading: '참고',
        excerpt: '비타민 C는 개인 상태와 함께 확인합니다.',
        score: 9,
      ),
    ],
    warnings: <String>[],
  );
}

ComprehensiveDietAnalysis _comprehensive({
  required List<String> chronicIndications,
  required String cautionComponent,
}) {
  return ComprehensiveDietAnalysis(
    deficientNutrients: const <ComprehensiveDeficientNutrient>[],
    excessiveNutrients: const <ComprehensiveExcessiveNutrient>[],
    cautionaryComponents: <ComprehensiveCautionaryComponent>[
      ComprehensiveCautionaryComponent(
        component: cautionComponent,
        reason: '함께 복용 시 확인이 필요해요',
        severity: 'high',
        message: '함께 드시는 약이 있다면 미리 확인해 주세요.',
      ),
    ],
    purposeTargets: const <ComprehensivePurposeTarget>[],
    chronicDiseaseIndications: chronicIndications,
    warnings: const <String>[],
  );
}

class _KdriRepository implements LemonAidRepository {
  _KdriRepository({this.result, this.shouldFail = false});

  final KdriLookupResult? result;
  final bool shouldFail;

  @override
  Future<KdriLookupResult> lookupKdris({
    required int age,
    required String sex,
    String pregnancyStatus = 'none',
  }) async {
    if (shouldFail) {
      throw Exception('kdris lookup failed');
    }
    return result ?? KdriLookupResult.empty;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) {
    throw UnimplementedError('Unexpected call: ${invocation.memberName}');
  }
}
