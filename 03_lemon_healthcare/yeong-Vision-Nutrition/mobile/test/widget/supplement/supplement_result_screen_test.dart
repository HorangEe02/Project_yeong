/// SupplementResultScreen 위젯 테스트 — fake response → 안전 위젯 + IngredientCard 가시.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_healthcare/features/supplement/domain/supplement_models.dart';
import 'package:lemon_healthcare/features/supplement/presentation/screens/supplement_result_screen.dart';
import 'package:lemon_healthcare/features/supplement/presentation/widgets/ingredient_card.dart';
import 'package:lemon_healthcare/features/supplement/presentation/widgets/status_chip.dart';
import 'package:lemon_healthcare/shared/models/emergency_contact.dart';
import 'package:lemon_healthcare/shared/widgets/consult_professional.dart';
import 'package:lemon_healthcare/shared/widgets/disclaimer.dart';
import 'package:lemon_healthcare/shared/widgets/emergency_resources.dart';

SupplementResponse _fakeResponse({
  List<String> unmatched = const <String>[],
}) =>
    SupplementResponse(
      supplementId: 'sup-1',
      productName: '종합비타민',
      manufacturer: '레몬제약',
      ingredients: const <Ingredient>[
        Ingredient(
          code: 'vitamin_c_mg',
          nameKo: '비타민 C',
          amount: 1000,
          unit: 'mg',
        ),
        Ingredient(
          code: 'vitamin_d_iu',
          nameKo: '비타민 D',
          amount: 400,
          unit: 'IU',
        ),
      ],
      unmatchedIngredientNames: unmatched,
      diagnosis: const DiagnosisResult(
        diagnoses: <NutrientDiagnosis>[
          NutrientDiagnosis(
            code: 'vitamin_c_mg',
            nameKo: '비타민 C',
            rda: 100,
            actual: 1000,
            unit: 'mg',
            ratio: 10,
            status: NutrientStatus.excessive,
            messageKo: '비타민 C 섭취가 권장량의 1000% 수준입니다.',
          ),
          NutrientDiagnosis(
            code: 'vitamin_d_iu',
            nameKo: '비타민 D',
            rda: 400,
            actual: 400,
            unit: 'IU',
            ratio: 1,
            status: NutrientStatus.adequate,
            messageKo: '비타민 D 섭취가 적정 수준입니다.',
          ),
        ],
        deficientCount: 0,
        riskyCount: 0,
        adequateCount: 1,
        summaryMessageKo: '1개 적정, 1개 과다',
      ),
      ocrEngine: 'google_vision_v1',
      llmEngine: 'ollama',
      elapsedMs: 3000,
      disclaimers: const <String>[],
      emergencyResources: const <EmergencyContact>[
        EmergencyContact(name: '응급의료정보', phone: '1339'),
      ],
      consultProfessionalMessageKo: '약사 또는 의료진과 상담하시기 바랍니다.',
    );

Future<void> _pumpResultScreen(
  WidgetTester tester, {
  List<String> unmatched = const <String>[],
}) async {
  // Result 화면이 길어 기본 800x600 viewport 에선 ListView 하단 위젯이
  // lazy build 되지 않음 (ConsultProfessional, "다시 등록" 버튼, unmatched
  // 섹션 등). 모든 위젯을 단일 frame 에서 검증할 수 있도록 surface size 확장.
  tester.view.physicalSize = const Size(800, 2400);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);

  await tester.pumpWidget(
    ProviderScope(
      child: MaterialApp(
        home: SupplementResultScreen(
          response: _fakeResponse(unmatched: unmatched),
        ),
      ),
    ),
  );
}

void main() {
  testWidgets('제품명/제조사 헤더 표시', (WidgetTester tester) async {
    await _pumpResultScreen(tester);
    expect(find.text('종합비타민'), findsOneWidget); // AppBar title
    expect(find.text('제조사: 레몬제약'), findsOneWidget);
  });

  testWidgets('IngredientCard 가 성분 수만큼 가시', (WidgetTester tester) async {
    await _pumpResultScreen(tester);
    expect(find.byType(IngredientCard), findsNWidgets(2));
    expect(find.text('비타민 C'), findsWidgets);
    expect(find.text('비타민 D'), findsWidgets);
  });

  testWidgets('StatusChip — excessive → "과다", adequate → "적정"',
      (WidgetTester tester) async {
    await _pumpResultScreen(tester);
    expect(find.byType(StatusChip), findsNWidgets(2));
    expect(find.text('과다'), findsOneWidget);
    // "적정" 은 IngredientCard chip + SummaryCard CountChip 모두에서 등장 가능.
    expect(find.text('적정'), findsWidgets);
  });

  testWidgets('MedicalDisclaimer(supplement) 가시', (WidgetTester tester) async {
    await _pumpResultScreen(tester);
    final Finder finder = find.byType(MedicalDisclaimer);
    expect(finder, findsOneWidget);
    final MedicalDisclaimer widget = tester.widget(finder);
    expect(widget.variant, DisclaimerVariant.supplement);
  });

  testWidgets('EmergencyResources 가시', (WidgetTester tester) async {
    await _pumpResultScreen(tester);
    expect(find.byType(EmergencyResources), findsOneWidget);
  });

  testWidgets('ConsultProfessional 가시 — 백엔드 메시지 전달',
      (WidgetTester tester) async {
    await _pumpResultScreen(tester);
    final Finder finder = find.byType(ConsultProfessional);
    expect(finder, findsOneWidget);
    final ConsultProfessional widget = tester.widget(finder);
    expect(widget.message, '약사 또는 의료진과 상담하시기 바랍니다.');
  });

  testWidgets('unmatched 빈 리스트 → 섹션 미가시', (WidgetTester tester) async {
    await _pumpResultScreen(tester);
    expect(find.text('권장량 정보 없는 성분'), findsNothing);
  });

  testWidgets('unmatched 비어있지 않으면 섹션 + chip 가시',
      (WidgetTester tester) async {
    await _pumpResultScreen(tester, unmatched: <String>['루테인', '코엔자임 Q10']);
    expect(find.text('권장량 정보 없는 성분'), findsOneWidget);
    expect(find.widgetWithText(Chip, '루테인'), findsOneWidget);
    expect(find.widgetWithText(Chip, '코엔자임 Q10'), findsOneWidget);
  });

  testWidgets('"다시 등록" 버튼 가시', (WidgetTester tester) async {
    await _pumpResultScreen(tester);
    expect(find.widgetWithText(FilledButton, '다시 등록'), findsOneWidget);
  });
}
