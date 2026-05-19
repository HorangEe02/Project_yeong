/// ``MedicalDisclaimer`` 위젯 테스트 — 3 variant 텍스트 + Icon.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_healthcare/shared/widgets/disclaimer.dart';

void main() {
  Future<void> pump(WidgetTester tester, DisclaimerVariant variant) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: MedicalDisclaimer(variant: variant)),
      ),
    );
  }

  group('MedicalDisclaimer', () {
    testWidgets('main variant — 의사·약사·영양사 문구 가시', (WidgetTester tester) async {
      await pump(tester, DisclaimerVariant.main);
      expect(find.textContaining('의사·약사·영양사'), findsOneWidget);
      expect(find.byIcon(Icons.info_outline), findsOneWidget);
    });

    testWidgets('supplement variant — 의약품이 아닙니다 문구 가시', (WidgetTester tester) async {
      await pump(tester, DisclaimerVariant.supplement);
      expect(find.textContaining('의약품이 아니'), findsOneWidget);
    });

    testWidgets('weightPrediction variant — 급격한 체중 변화 문구 가시', (WidgetTester tester) async {
      await pump(tester, DisclaimerVariant.weightPrediction);
      expect(find.textContaining('급격한 체중'), findsOneWidget);
    });

    test('DisclaimerStrings — 모든 본문이 비어있지 않음', () {
      expect(DisclaimerStrings.mainKo, isNotEmpty);
      expect(DisclaimerStrings.supplementKo, isNotEmpty);
      expect(DisclaimerStrings.weightPredictionKo, isNotEmpty);
      expect(DisclaimerStrings.consultProfessionalKo, isNotEmpty);

      // 면책 본문은 '의사·약사·영양사' 등 핵심 키워드 포함.
      // (의료법 금지표현 grep 회귀는 별도 CI bash 스크립트 — disclaimer 본문은
      //  부정문 맥락에서 사용 가능하므로 disclaimer_test 에서 grep 안 함.)
      expect(DisclaimerStrings.mainKo, contains('의사'));
      expect(DisclaimerStrings.supplementKo, contains('의약품'));
    });
  });
}
