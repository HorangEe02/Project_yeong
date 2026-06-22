import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lemon_aid_mobile/app_controller.dart';
import 'package:lemon_aid_mobile/app_providers.dart';
import 'package:lemon_aid_mobile/features/consent/consent_models.dart';
import 'package:lemon_aid_mobile/features/dashboard/dashboard_models.dart';
import 'package:lemon_aid_mobile/features/dashboard/home_models.dart';
import 'package:lemon_aid_mobile/features/nutrition/kdri_models.dart';
import 'package:lemon_aid_mobile/features/supplements/comprehensive_analysis_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_models.dart';
import 'package:lemon_aid_mobile/features/records/food_models.dart';
import 'package:lemon_aid_mobile/features/supplements/supplement_repository.dart';
import 'package:lemon_aid_mobile/screens/analysis_result_screen.dart';
import 'package:lemon_aid_mobile/shared/widgets/low_confidence_banner.dart';

void main() {
  testWidgets('renders source-style analysis result with real pipeline data', (
    WidgetTester tester,
  ) async {
    final _ReviewRepository repository = _ReviewRepository();
    final AppController controller = AppController(
      repository: _ReviewRepository(
        preview: repository._preview(
          ingredientName: '비타민 D',
          originalIngredientName: 'Vitamin D',
        ),
      ),
    );
    await controller.analyzeImage(
      '/tmp/supplement-label.jpg',
      ocrProvider: 'paddleocr',
    );

    await tester.pumpWidget(
      MaterialApp(home: AnalysisResultScreen(controller: controller)),
    );
    await tester.pumpAndSettle();

    expect(find.text('영양제 분석'), findsOneWidget);
    expect(find.text('성분 후보 1개를 찾았어요'), findsOneWidget);
    expect(
      find.byKey(const ValueKey<String>('pipeline-led-ocr-success')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey<String>('pipeline-led-vision-success')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey<String>('pipeline-led-llm-success')),
      findsOneWidget,
    );
    expect(find.text('영양제명'), findsOneWidget);
    expect(find.text('상세 성분 및 함량'), findsOneWidget);
    expect(find.byType(Table), findsOneWidget);
    expect(find.text('성분명'), findsOneWidget);
    expect(find.text('함량'), findsOneWidget);
    expect(find.text('비타민 D (Vitamin D)'), findsOneWidget);
    expect(find.text('원문: Vitamin D'), findsNothing);
    expect(find.text('25 mcg'), findsOneWidget);
    expect(
      tester
          .widgetList<Text>(find.text('비타민 D (Vitamin D)'))
          .any(
            (Text widget) =>
                widget.style?.fontWeight == FontWeight.w900 &&
                widget.style?.fontSize == 16,
          ),
      isTrue,
    );
    // 요약 카드에 탭 가능 단서가 보여야 사용자가 라벨 글자 보기를 발견한다.
    expect(
      find.byKey(const ValueKey<String>('summary-card-ocr-hint')),
      findsOneWidget,
    );
    expect(find.text('텍스트 보기'), findsOneWidget);
    expect(find.byIcon(Icons.unfold_more_rounded), findsOneWidget);

    await tester.tap(
      find.byKey(const ValueKey<String>('supplement-candidate-summary')),
    );
    await tester.pumpAndSettle();

    expect(find.text('OCR 텍스트 전체'), findsOneWidget);
    expect(find.text('구역'), findsOneWidget);
    expect(find.text('비타민 D 25 mcg'), findsOneWidget);
    await tester.tap(find.text('닫기'));
    await tester.pumpAndSettle();

    await tester.scrollUntilVisible(find.text('섭취 방법'), 120);
    expect(find.text('섭취 방법'), findsOneWidget);
    expect(find.textContaining('하루 1회 1캡슐'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('섭취 시 주의사항'), 220);
    expect(find.text('섭취 시 주의사항'), findsOneWidget);
    expect(find.textContaining('전문가와 상담'), findsOneWidget);
    expect(find.text('OCR'), findsNothing);
    expect(find.text('YOLO ROI'), findsNothing);
    expect(find.text('Ollama'), findsNothing);
    expect(find.text('주의사항이 보이게 한 장 더 촬영해주세요'), findsNothing);
    expect(find.text('Analysis progress'), findsNothing);
    expect(find.textContaining('OCR Auto'), findsNothing);
  });

  testWidgets('shows the raw OCR source row in the OCR text modal', (
    WidgetTester tester,
  ) async {
    final _ReviewRepository repository = _ReviewRepository();
    final AppController controller = AppController(
      repository: _ReviewRepository(
        preview: repository._preview(
          rawOcrText: '비타민 D 1000 IU\n칼슘 200 mg',
        ),
      ),
    );
    await controller.analyzeImage(
      '/tmp/supplement-label.jpg',
      ocrProvider: 'paddleocr',
    );

    await tester.pumpWidget(
      MaterialApp(home: AnalysisResultScreen(controller: controller)),
    );
    await tester.pumpAndSettle();

    await tester.tap(
      find.byKey(const ValueKey<String>('supplement-candidate-summary')),
    );
    await tester.pumpAndSettle();

    expect(find.text('OCR 텍스트 전체'), findsOneWidget);
    expect(find.text('OCR 원문'), findsOneWidget);
    expect(find.textContaining('칼슘 200 mg'), findsWidgets);
    await tester.tap(find.text('닫기'));
    await tester.pumpAndSettle();
  });

  testWidgets('keeps parsed rows alongside the RAW OCR row when no spans exist', (
    WidgetTester tester,
  ) async {
    final _ReviewRepository repository = _ReviewRepository();
    final AppController controller = AppController(
      repository: _ReviewRepository(
        preview: repository._preview(
          rawOcrText: '비타민 D 1000 IU',
          includeSupplementFactsSection: false,
          includeIntakeSection: false,
          includePrecautionsSection: false,
        ),
      ),
    );
    await controller.analyzeImage(
      '/tmp/supplement-label.jpg',
      ocrProvider: 'paddleocr',
    );

    await tester.pumpWidget(
      MaterialApp(home: AnalysisResultScreen(controller: controller)),
    );
    await tester.pumpAndSettle();

    await tester.tap(
      find.byKey(const ValueKey<String>('supplement-candidate-summary')),
    );
    await tester.pumpAndSettle();

    // Both the RAW dump and the parsed ingredient fallback must render — the RAW
    // row must not short-circuit the structured rows.
    expect(find.text('OCR 텍스트 전체'), findsOneWidget);
    expect(find.text('OCR 원문'), findsOneWidget);
    expect(find.text('OCR_LLM_PREVIEW'), findsWidgets);
    await tester.tap(find.text('닫기'));
    await tester.pumpAndSettle();
  });

  testWidgets('opens ingredient detail when an ingredient row is tapped', (
    WidgetTester tester,
  ) async {
    final _ReviewRepository sourceRepository = _ReviewRepository();
    final _ReviewRepository repository = _ReviewRepository(
      preview: sourceRepository._preview(
        ingredientName: '비타민 D',
        originalIngredientName: 'Vitamin D',
      ),
    );
    final AppController controller = AppController(repository: repository);
    await controller.analyzeImage(
      '/tmp/supplement-label.jpg',
      ocrProvider: 'paddleocr',
    );

    await tester.pumpWidget(
      MaterialApp(home: AnalysisResultScreen(controller: controller)),
    );
    await tester.pumpAndSettle();

    // 성분 행(figma 12-④ 진입) — 행 탭 → 성분 상세 화면 push.
    await tester.tap(
      find.byKey(const ValueKey<String>('ingredient-row-detail-0')).first,
    );
    await tester.pumpAndSettle();

    expect(find.text('성분 상세'), findsOneWidget);
    expect(
      find.byKey(const ValueKey<String>('ingredient-detail-identity-card')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey<String>('ingredient-detail-medical-note')),
      findsOneWidget,
    );
  });

  testWidgets('preserves OCR original ingredient name after single edit', (
    WidgetTester tester,
  ) async {
    final _ReviewRepository sourceRepository = _ReviewRepository();
    final _ReviewRepository repository = _ReviewRepository(
      preview: sourceRepository._preview(
        ingredientName: '글루코사민 염산염',
        originalIngredientName: 'Glucosamine Hydrochloride',
        ingredientAmount: 1500,
        ingredientUnit: 'mg',
      ),
    );
    final AppController controller = AppController(repository: repository);
    await controller.analyzeImage(
      '/tmp/supplement-label.jpg',
      ocrProvider: 'paddleocr',
    );

    await tester.pumpWidget(
      MaterialApp(home: AnalysisResultScreen(controller: controller)),
    );
    await tester.pumpAndSettle();

    expect(find.text('글루코사민 염산염 (Glucosamine Hydrochloride)'), findsOneWidget);
    expect(find.text('원문: Glucosamine Hydrochloride'), findsNothing);

    await tester.tap(find.byTooltip('상세 성분 및 함량 수정'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).at(0), '글루코사민 HCl');
    await tester.tap(find.text('저장'));
    await tester.pumpAndSettle();

    expect(find.text('글루코사민 HCl (Glucosamine Hydrochloride)'), findsOneWidget);
    expect(find.text('원문: Glucosamine Hydrochloride'), findsNothing);

    await tester.tap(find.text('확인 후 저장'));
    await tester.pumpAndSettle();

    expect(
      repository.registeredRequest?.ingredients.single.displayName,
      '글루코사민 HCl',
    );
    expect(
      repository.registeredRequest?.ingredients.single.originalName,
      'Glucosamine Hydrochloride',
    );
  });

  testWidgets('intake controls persist stepper and chip choices', (
    WidgetTester tester,
  ) async {
    // 섭취 기준 컨트롤 — 1일 복용량 스테퍼 + 주기/시간 선택 칩
    // (figma 855:23, 가이드 10 ③-P2 7).
    final _ReviewRepository repository = _ReviewRepository();
    final AppController controller = AppController(repository: repository);
    await controller.analyzeImage(
      '/tmp/supplement-label.jpg',
      ocrProvider: 'paddleocr',
    );

    await tester.pumpWidget(
      MaterialApp(home: AnalysisResultScreen(controller: controller)),
    );
    await tester.pumpAndSettle();

    await tester.scrollUntilVisible(find.byTooltip('섭취 방법 수정'), 220);
    await tester.ensureVisible(find.byTooltip('섭취 방법 수정'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('섭취 방법 수정'));
    await tester.pumpAndSettle();

    expect(find.text('1일 복용량'), findsOneWidget);
    // 시드 1회(라벨 dailyServings) → 스테퍼 +1 → 2회.
    await tester.tap(find.byIcon(Icons.add_circle_outline));
    await tester.pump();
    await tester.ensureVisible(find.text('매주'));
    await tester.tap(find.text('매주'));
    await tester.pump();
    await tester.ensureVisible(find.text('저녁'));
    await tester.tap(find.text('저녁'));
    await tester.pump();
    await tester.tap(find.text('저장'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('확인 후 저장'));
    await tester.pumpAndSettle();

    final UserSupplementCreate? request = repository.registeredRequest;
    expect(request?.serving.dailyServings, 2);
    expect(request?.intakeSchedule?.timesPerDay, 2);
    expect(request?.intakeSchedule?.frequency, 'weekly');
    // OCR이 읽어온 morning 은 보존되고 사용자가 evening 을 추가한다.
    expect(
      request?.intakeSchedule?.timeOfDay,
      containsAll(<String>['morning', 'evening']),
    );
  });

  testWidgets('manually added ingredient is saved as user_confirmed', (
    WidgetTester tester,
  ) async {
    // 성분 직접 추가 — OCR이 놓친 성분을 수동 입력으로 보탠다
    // (figma 855:23, 가이드 10 ③-P2 7).
    final _ReviewRepository repository = _ReviewRepository();
    final AppController controller = AppController(repository: repository);
    await controller.analyzeImage(
      '/tmp/supplement-label.jpg',
      ocrProvider: 'paddleocr',
    );

    await tester.pumpWidget(
      MaterialApp(home: AnalysisResultScreen(controller: controller)),
    );
    await tester.pumpAndSettle();

    await tester.scrollUntilVisible(find.text('성분 직접 추가'), 220);
    await tester.ensureVisible(find.text('성분 직접 추가'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('성분 직접 추가'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).at(0), '아연');
    await tester.enterText(find.byType(TextField).at(1), '10');
    await tester.enterText(find.byType(TextField).at(2), 'mg');
    await tester.tap(find.text('저장'));
    await tester.pumpAndSettle();

    expect(find.text('아연'), findsOneWidget);

    await tester.tap(find.text('확인 후 저장'));
    await tester.pumpAndSettle();

    final List<UserSupplementIngredientInput> ingredients =
        repository.registeredRequest?.ingredients ??
        const <UserSupplementIngredientInput>[];
    final UserSupplementIngredientInput added = ingredients.singleWhere(
      (UserSupplementIngredientInput input) => input.displayName == '아연',
    );
    expect(added.amount, 10);
    expect(added.unit, 'mg');
    expect(added.source, 'user_confirmed');
  });

  testWidgets('category dropdown sends the chosen category_key', (
    WidgetTester tester,
  ) async {
    // 분류 드롭다운 — 카탈로그에서 고른 분류가 등록 요청 category_key 로 간다
    // (figma 855:23, 가이드 10 ③-P2 7).
    final _ReviewRepository repository = _ReviewRepository(
      supplementCategories: const <SupplementCategory>[
        SupplementCategory(
          categoryKey: '비타민B',
          displayName: '비타민B',
          sortOrder: 1,
        ),
        SupplementCategory(
          categoryKey: '오메가3',
          displayName: '오메가3',
          sortOrder: 2,
        ),
      ],
    );
    final AppController controller = AppController(repository: repository);
    await controller.analyzeImage(
      '/tmp/supplement-label.jpg',
      ocrProvider: 'paddleocr',
    );

    await tester.pumpWidget(
      MaterialApp(home: AnalysisResultScreen(controller: controller)),
    );
    await tester.pumpAndSettle();

    // 카탈로그가 로드되면 '분류' 카드가 노출되고, 기본값은 '선택 안 함'이다.
    expect(find.text('분류'), findsOneWidget);
    await tester.ensureVisible(find.text('선택 안 함'));
    await tester.tap(find.text('선택 안 함'));
    await tester.pumpAndSettle();
    // 드롭다운 메뉴에서 비타민B 를 고른다.
    await tester.tap(find.text('비타민B').last);
    await tester.pumpAndSettle();

    await tester.tap(find.text('확인 후 저장'));
    await tester.pumpAndSettle();

    expect(repository.registeredRequest?.categoryKey, '비타민B');
    // 미선택 시에는 키를 보내지 않는다(별도 케이스): toJson 직렬화 확인.
    expect(repository.registeredRequest?.toJson()['category_key'], '비타민B');
  });

  testWidgets('omitting the category sends no category_key', (
    WidgetTester tester,
  ) async {
    // 분류를 고르지 않으면 등록 요청에 category_key 가 빠진다.
    final _ReviewRepository repository = _ReviewRepository(
      supplementCategories: const <SupplementCategory>[
        SupplementCategory(
          categoryKey: '비타민B',
          displayName: '비타민B',
          sortOrder: 1,
        ),
      ],
    );
    final AppController controller = AppController(repository: repository);
    await controller.analyzeImage(
      '/tmp/supplement-label.jpg',
      ocrProvider: 'paddleocr',
    );

    await tester.pumpWidget(
      MaterialApp(home: AnalysisResultScreen(controller: controller)),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('확인 후 저장'));
    await tester.pumpAndSettle();

    expect(repository.registeredRequest?.categoryKey, isNull);
    expect(
      repository.registeredRequest?.toJson().containsKey('category_key'),
      isFalse,
    );
  });

  testWidgets('renders analyzing page while background analysis runs', (
    WidgetTester tester,
  ) async {
    final _PendingReviewRepository repository = _PendingReviewRepository();
    final AppController controller = AppController(repository: repository);
    addTearDown(() {
      repository.complete();
      controller.dispose();
    });

    await controller.startSupplementImageAnalysis('/tmp/supplement-label.jpg');

    await tester.pumpWidget(
      MaterialApp(home: AnalysisResultScreen(controller: controller)),
    );
    await tester.pump();

    expect(find.text('분석을 하고 있어요.'), findsOneWidget);
    expect(find.text('메인으로 이동'), findsOneWidget);
    // 영양제 3단계 체크리스트(검출→OCR 추출→AI 해석) 표출.
    expect(find.text('라벨 영역 검출'), findsOneWidget);
    expect(find.text('OCR 글자 추출'), findsOneWidget);
    expect(find.text('AI 해석'), findsOneWidget);
    // 클라이언트 연출 — 시간이 지나면 다음 단계가 켜진다.
    await tester.pump(const Duration(milliseconds: 1200));
    expect(find.text('라벨 영역 검출'), findsOneWidget);
  });

  testWidgets('meal analyzing page shows the food 3-step checklist', (
    WidgetTester tester,
  ) async {
    final _PendingMealRepository repository = _PendingMealRepository();
    final AppController controller = AppController(repository: repository);
    addTearDown(() {
      repository.complete();
      controller.dispose();
    });

    await controller.startMealImageAnalysis('/tmp/meal.png');

    await tester.pumpWidget(
      MaterialApp(
        home: AnalysisResultScreen(mode: 'meal', controller: controller),
      ),
    );
    await tester.pump();

    expect(find.text('분석을 하고 있어요.'), findsOneWidget);
    expect(find.text('메인으로 이동'), findsOneWidget);
    // 음식 3단계 체크리스트(검출→분류→후보 정리).
    expect(find.text('음식 영역 검출'), findsOneWidget);
    expect(find.text('음식 종류 분류'), findsOneWidget);
    expect(find.text('후보 정리'), findsOneWidget);
  });

  testWidgets(
    'surfaces recognized label text when structured ingredients are empty',
    (WidgetTester tester) async {
      final _ReviewRepository repository = _ReviewRepository(
        preview: _recognizedTextPreview(),
      );
      final AppController controller = AppController(repository: repository);
      await controller.analyzeImage(
        '/tmp/supplement-label.jpg',
        ocrProvider: 'paddleocr',
      );

      await tester.pumpWidget(
        MaterialApp(home: AnalysisResultScreen(controller: controller)),
      );
      await tester.pumpAndSettle();

      // Tier B: OCR read the label text but produced no structured rows, so the
      // recognized section text is shown instead of the dead-end placeholder.
      expect(find.text('읽어온 라벨 글자예요. 직접 확인하고 성분을 추가해주세요.'), findsOneWidget);
      expect(find.text('성분·함량'), findsOneWidget);
      expect(find.text('비타민C 1000mg, 아연 15mg'), findsOneWidget);
      expect(find.text('성분명과 함량을 확인할 수 없어요.'), findsNothing);

      // "전체 보기" routes to the existing OCR-text dialog.
      expect(find.text('인식된 텍스트 전체 보기'), findsOneWidget);
      await tester.ensureVisible(find.text('인식된 텍스트 전체 보기'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('인식된 텍스트 전체 보기'));
      await tester.pumpAndSettle();
      expect(find.text('OCR 텍스트 전체'), findsOneWidget);
    },
  );

  testWidgets(
    'registers user-corrected ingredient when OCR candidates are empty',
    (WidgetTester tester) async {
      final _ReviewRepository repository = _ReviewRepository(
        preview: _emptyCandidatePreview(),
      );
      final AppController controller = AppController(repository: repository);
      await controller.analyzeImage(
        '/tmp/supplement-label.jpg',
        ocrProvider: 'paddleocr',
      );

      await tester.pumpWidget(
        MaterialApp(home: AnalysisResultScreen(controller: controller)),
      );
      await tester.pumpAndSettle();

      expect(find.text('성분 직접 입력'), findsOneWidget);
      expect(find.text('제품명이 보이게 한 장 더 촬영해주세요'), findsOneWidget);
      expect(find.text('성분표가 보이게 한 장 더 촬영해주세요'), findsOneWidget);
      expect(find.text('읽어온 라벨 글자예요. 직접 확인하고 성분을 추가해주세요.'), findsOneWidget);
      expect(find.text('성분명과 함량을 확인할 수 없어요.'), findsNothing);

      await tester.tap(find.byTooltip('영양제명 수정'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField).at(0), '수정 비타민 D');
      await tester.enterText(find.byType(TextField).at(1), 'Lemon Lab');
      await tester.tap(find.text('저장'));
      await tester.pumpAndSettle();

      await tester.tap(find.byTooltip('상세 성분 및 함량 수정'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField).at(0), 'Vitamin D3');
      await tester.enterText(find.byType(TextField).at(1), '25');
      await tester.enterText(find.byType(TextField).at(2), 'mcg');
      await tester.tap(find.text('저장'));
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(find.byTooltip('섭취 시 주의사항 수정'), 220);
      await tester.drag(find.byType(ListView), const Offset(0, -260));
      await tester.pumpAndSettle();
      expect(find.text('해당 이미지에는 해당하는 내용이 없습니다'), findsWidgets);
      await tester.tap(find.byTooltip('섭취 시 주의사항 수정'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byType(TextField).first,
        '임신 중이면 전문가와 상담하세요.',
      );
      await tester.tap(find.text('저장'));
      await tester.pumpAndSettle();

      expect(find.text('확인 후 저장'), findsOneWidget);
      await tester.tap(find.text('확인 후 저장'));
      await tester.pumpAndSettle();

      expect(repository.registeredRequest?.displayName, '수정 비타민 D');
      expect(repository.registeredRequest?.manufacturer, 'Lemon Lab');
      expect(
        repository.registeredRequest?.ingredients.single.displayName,
        'Vitamin D3',
      );
      expect(repository.registeredRequest?.ingredients.single.amount, 25);
      expect(repository.registeredRequest?.ingredients.single.unit, 'mcg');
      expect(
        repository.registeredRequest?.ingredients.single.source,
        'user_confirmed',
      );
      expect(repository.registeredRequest?.evidenceRefs, <String>[
        'span-empty',
      ]);
      expect(repository.registeredRequest?.precautionSnapshot, <String>[
        '임신 중이면 전문가와 상담하세요.',
      ]);
      expect(repository.explainUsedLocalLlm, isTrue);
      expect(controller.lastRegisteredSupplement?.displayName, '수정 비타민 D');
      expect(controller.pendingChatExplanationDraft, isNotNull);
      expect(
        controller.pendingChatExplanationDraft?.assistantMessage,
        contains('성분과 함유량'),
      );
      expect(
        controller.pendingChatExplanationDraft?.assistantMessage,
        contains('Vitamin D3: 25 mcg'),
      );
      expect(
        controller.pendingChatExplanationDraft?.assistantMessage,
        contains('출처'),
      );
      expect(
        controller.pendingChatExplanationDraft?.assistantMessage,
        contains('vitamin-d.md'),
      );
    },
  );

  testWidgets('normalizes OCR provider source for supplement registration', (
    WidgetTester tester,
  ) async {
    final _ReviewRepository sourceRepository = _ReviewRepository();
    final _ReviewRepository repository = _ReviewRepository(
      preview: sourceRepository._preview(
        ingredientName: '비타민 D',
        originalIngredientName: 'Vitamin D',
        ingredientSource: 'clova_ocr',
        includeSecondIngredient: true,
      ),
    );
    final AppController controller = AppController(repository: repository);
    await controller.analyzeImage(
      '/tmp/supplement-label.jpg',
      ocrProvider: 'clova',
    );

    await tester.pumpWidget(
      MaterialApp(home: AnalysisResultScreen(controller: controller)),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('확인 후 저장'));
    await tester.pumpAndSettle();

    expect(
      repository.registeredRequest?.ingredients.first.source,
      'user_confirmed',
    );
    expect(repository.registeredRequest?.ingredients, hasLength(1));
    expect(
      repository.registeredRequest?.ingredients.single.displayName,
      '비타민 D',
    );
    expect(
      repository.registeredRequest?.ingredients.single.originalName,
      'Vitamin D',
    );
    expect(
      controller.pendingChatExplanationDraft?.assistantMessage,
      contains('비타민 D (Vitamin D): 25 mcg'),
    );
    expect(repository.registeredRequest?.evidenceRefs, <String>[
      'span-1',
      'span-2',
      'span-3',
    ]);
  });

  testWidgets('lets reviewers choose name-only ingredient candidates', (
    WidgetTester tester,
  ) async {
    final _ReviewRepository sourceRepository = _ReviewRepository();
    final _ReviewRepository repository = _ReviewRepository(
      preview: sourceRepository._preview(includeSecondIngredient: true),
    );
    final AppController controller = AppController(repository: repository);
    await controller.analyzeImage('/tmp/supplement-label.jpg');

    await tester.pumpWidget(
      MaterialApp(home: AnalysisResultScreen(controller: controller)),
    );
    await tester.pumpAndSettle();

    expect(find.text('저장 후보 1개 · 검토 후보 2개'), findsOneWidget);
    expect(find.text('Vitamin D'), findsOneWidget);
    expect(find.text('25 mcg'), findsOneWidget);
    expect(find.text('Sunflower oil'), findsOneWidget);
    expect(find.text('선택 1/2'), findsOneWidget);
    expect(find.text('전체 선택'), findsOneWidget);
    expect(
      find.byKey(const ValueKey<String>('ingredient-row-checkbox-0')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey<String>('ingredient-row-checkbox-1')),
      findsOneWidget,
    );
    expect(
      tester
          .widget<Checkbox>(
            find.byKey(const ValueKey<String>('ingredient-row-checkbox-0')),
          )
          .value,
      isTrue,
    );
    expect(
      tester
          .widget<Checkbox>(
            find.byKey(const ValueKey<String>('ingredient-row-checkbox-1')),
          )
          .value,
      isFalse,
    );

    await tester.tap(
      find.byKey(const ValueKey<String>('ingredient-select-all-button')),
    );
    await tester.pumpAndSettle();
    expect(find.text('선택 2/2'), findsOneWidget);
    expect(find.text('전체 해제'), findsOneWidget);
    expect(
      tester
          .widget<Checkbox>(
            find.byKey(const ValueKey<String>('ingredient-row-checkbox-0')),
          )
          .value,
      isTrue,
    );
    expect(
      tester
          .widget<Checkbox>(
            find.byKey(const ValueKey<String>('ingredient-row-checkbox-1')),
          )
          .value,
      isTrue,
    );

    await tester.tap(
      find.byKey(const ValueKey<String>('ingredient-select-all-button')),
    );
    await tester.pumpAndSettle();
    expect(find.text('선택 0/2'), findsOneWidget);
    expect(find.text('전체 선택'), findsOneWidget);
    expect(
      tester
          .widget<Checkbox>(
            find.byKey(const ValueKey<String>('ingredient-row-checkbox-0')),
          )
          .value,
      isFalse,
    );
    expect(
      tester
          .widget<Checkbox>(
            find.byKey(const ValueKey<String>('ingredient-row-checkbox-1')),
          )
          .value,
      isFalse,
    );

    await tester.tap(
      find.byKey(const ValueKey<String>('ingredient-select-all-button')),
    );
    await tester.pumpAndSettle();
    await tester.tap(
      find.byKey(const ValueKey<String>('ingredient-row-checkbox-0')),
    );
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<Checkbox>(
            find.byKey(const ValueKey<String>('ingredient-row-checkbox-0')),
          )
          .value,
      isFalse,
    );
    expect(
      tester
          .widget<Checkbox>(
            find.byKey(const ValueKey<String>('ingredient-row-checkbox-1')),
          )
          .value,
      isTrue,
    );
    await tester.tap(find.byTooltip('상세 성분 및 함량 수정'));
    await tester.pumpAndSettle();

    expect(find.text('선택 성분 수정'), findsOneWidget);
    await tester.enterText(
      find.byType(TextField).at(0),
      'Sunflower oil extract',
    );
    await tester.tap(find.widgetWithText(FilledButton, '저장'));
    await tester.pumpAndSettle();

    expect(find.text('Sunflower oil extract'), findsOneWidget);
    expect(find.text('함량 확인 필요'), findsOneWidget);

    await tester.tap(find.text('확인 후 저장'));
    await tester.pumpAndSettle();

    expect(repository.registeredRequest?.ingredients, hasLength(1));
    expect(
      repository.registeredRequest?.ingredients.single.displayName,
      'Sunflower oil extract',
    );
    expect(repository.registeredRequest?.ingredients.single.amount, isNull);
    expect(repository.registeredRequest?.ingredients.single.unit, isNull);
  });

  testWidgets('switches between multi-image supplement result tabs', (
    WidgetTester tester,
  ) async {
    final _ReviewRepository repository = _ReviewRepository();
    final AppController controller = AppController(repository: repository);
    await controller.analyzeImages(const <SupplementImageUpload>[
      SupplementImageUpload(path: '/tmp/supplement-a.jpg'),
      SupplementImageUpload(path: '/tmp/supplement-b.jpg'),
    ], sameSupplementBatch: false);

    await tester.pumpWidget(
      MaterialApp(home: AnalysisResultScreen(controller: controller)),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey<String>('supplement-preview-tab-0')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey<String>('supplement-preview-tab-1')),
      findsOneWidget,
    );
    expect(find.text('비타민 D'), findsWidgets);
    expect(find.text('오메가-3'), findsOneWidget);
    expect(find.text('Omega-3'), findsNothing);

    await tester.tap(
      find.byKey(const ValueKey<String>('supplement-preview-tab-1')),
    );
    await tester.pumpAndSettle();

    expect(find.text('Omega-3'), findsOneWidget);
    expect(find.text('1000 mg'), findsOneWidget);
  });

  testWidgets(
    'single-product batch keeps one result per photo (gallery-driven)',
    (WidgetTester tester) async {
      final _ReviewRepository repository = _ReviewRepository();
      final AppController controller = AppController(repository: repository);
      // sameSupplementBatch: true was previously collapsed into ONE merged
      // result; now each photo keeps its own per-image result so selecting a
      // photo (gallery or tab) also switches the shown analysis result.
      await controller.analyzeImages(const <SupplementImageUpload>[
        SupplementImageUpload(path: '/tmp/supplement-a.jpg'),
        SupplementImageUpload(path: '/tmp/supplement-b.jpg'),
      ], sameSupplementBatch: true);

      await tester.pumpWidget(
        MaterialApp(home: AnalysisResultScreen(controller: controller)),
      );
      await tester.pumpAndSettle();

      expect(
        find.byKey(const ValueKey<String>('supplement-preview-tab-0')),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey<String>('supplement-preview-tab-1')),
        findsOneWidget,
      );
      // Per-image: the second photo's ingredient is not shown until selected.
      expect(find.text('Omega-3'), findsNothing);

      await tester.tap(
        find.byKey(const ValueKey<String>('supplement-preview-tab-1')),
      );
      await tester.pumpAndSettle();

      expect(find.text('Omega-3'), findsOneWidget);
      expect(find.text('1000 mg'), findsOneWidget);
    },
  );

  testWidgets(
    'groups front and facts photos into supplement-level result tabs',
    (WidgetTester tester) async {
      final SupplementMultiImageAnalysisPreview multiPreview =
          _threeSupplementMultiPreview();
      final _ReviewRepository repository = _ReviewRepository(
        multiPreview: multiPreview,
      );
      final AppController controller = AppController(repository: repository);
      await controller.analyzeImages(const <SupplementImageUpload>[
        SupplementImageUpload(path: '/tmp/lemon-multi-front.jpg'),
        SupplementImageUpload(path: '/tmp/lemon-multi-facts.jpg'),
        SupplementImageUpload(path: '/tmp/omega-plus.jpg'),
        SupplementImageUpload(path: '/tmp/magnesium-calm.jpg'),
      ], sameSupplementBatch: false);

      await tester.pumpWidget(
        MaterialApp(home: AnalysisResultScreen(controller: controller)),
      );
      await tester.pumpAndSettle();

      expect(
        find.byKey(const ValueKey<String>('supplement-preview-tab-0')),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey<String>('supplement-preview-tab-1')),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey<String>('supplement-preview-tab-2')),
        findsOneWidget,
      );
      expect(
        find.byKey(const ValueKey<String>('supplement-preview-tab-3')),
        findsNothing,
      );
      expect(find.text('Merged batch'), findsNothing);
      expect(find.text('Lemon Multi'), findsWidgets);
      expect(find.text('Vitamin C'), findsOneWidget);
      expect(find.text('500 mg'), findsOneWidget);

      await tester.tap(
        find.byKey(const ValueKey<String>('supplement-preview-tab-1')),
      );
      await tester.pumpAndSettle();

      expect(find.text('Omega Plus'), findsWidgets);
      expect(find.text('Omega-3'), findsOneWidget);
      expect(find.text('1000 mg'), findsOneWidget);
      expect(find.text('Vitamin C'), findsNothing);

      await tester.tap(
        find.byKey(const ValueKey<String>('supplement-preview-tab-2')),
      );
      await tester.pumpAndSettle();

      expect(find.text('Magnesium Calm'), findsWidgets);
      expect(find.text('Magnesium'), findsOneWidget);
      expect(find.text('200 mg'), findsOneWidget);
      expect(find.text('Omega-3'), findsNothing);
    },
  );

  testWidgets('renders meal analysis with food YOLO endpoint data', (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      repository: _ReviewRepository(),
    );
    await controller.analyzeMealImage('/tmp/meal.png', mealType: 'lunch');

    await tester.pumpWidget(
      MaterialApp(
        home: AnalysisResultScreen(mode: 'meal', controller: controller),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('식단 분석'), findsOneWidget);
    expect(find.text('음식 후보 1개를 찾았어요'), findsOneWidget);
    // 식단 모드는 요약 카드 onTap 이 없어 탭 가능 단서를 표시하지 않는다.
    expect(
      find.byKey(const ValueKey<String>('summary-card-ocr-hint')),
      findsNothing,
    );
    // 후보 선택 본편(figma 852:23): 후보 카드 헤더 + 후보명 + 등급 칩(% 비노출).
    expect(find.text('어떤 음식이 맞나요?'), findsOneWidget);
    expect(find.text('비빔밥'), findsWidgets);
    expect(find.text('신뢰도 높음'), findsWidgets);
    // 최고 신뢰도 후보가 기본 선택되어 섭취량 행이 노출된다(기본 1인분).
    expect(find.text('섭취량'), findsOneWidget);
    expect(find.text('1인분'), findsWidgets);
    // % 숫자(신뢰도 88%)는 노출되지 않는다.
    expect(find.textContaining('88%'), findsNothing);
  });

  testWidgets('confirms meal analysis into user-reviewed meal record', (
    WidgetTester tester,
  ) async {
    final _ReviewRepository repository = _ReviewRepository();
    final AppController controller = AppController(repository: repository);
    await controller.analyzeMealImage('/tmp/meal.png', mealType: 'lunch');

    await tester.pumpWidget(
      MaterialApp(
        home: AnalysisResultScreen(mode: 'meal', controller: controller),
      ),
    );
    await tester.pumpAndSettle();

    await _scrollResultDetails(tester);
    expect(find.text('식단 확인'), findsOneWidget);
    await tester.enterText(find.byType(TextField).first, '수정 비빔밥');
    await tester.tap(find.text('확인 후 식단 저장'));
    await tester.pumpAndSettle();

    expect(repository.confirmedMealId, '00000000-0000-0000-0000-000000000201');
    expect(
      repository.confirmedMealRequest?.foodItems.single.displayName,
      '수정 비빔밥',
    );
    expect(
      controller.lastRegisteredMeal?.foodItems.single.displayName,
      '수정 비빔밥',
    );
  });

  testWidgets(
    'meal candidate portion sheet reflects portion_amount in confirm payload',
    (WidgetTester tester) async {
      final _ReviewRepository repository = _ReviewRepository();
      final AppController controller = AppController(repository: repository);
      await controller.analyzeMealImage('/tmp/meal.png', mealType: 'lunch');

      await tester.pumpWidget(
        MaterialApp(
          home: AnalysisResultScreen(mode: 'meal', controller: controller),
        ),
      );
      await tester.pumpAndSettle();

      // 후보가 기본 선택되어 섭취량 행이 보인다 — 탭해서 바텀시트를 연다.
      await tester.tap(find.text('섭취량'));
      await tester.pumpAndSettle();

      // figma 959:80 — 프리셋 칩 + 그램 환산.
      expect(find.text('얼마나 드셨어요?'), findsOneWidget);
      expect(find.text('약 150g'), findsNothing); // 아직 1.5 선택 전
      await tester.tap(find.text('1.5인분'));
      await tester.pumpAndSettle();
      expect(find.text('약 150g'), findsOneWidget);
      await tester.tap(find.text('이 양으로 담기'));
      await tester.pumpAndSettle();

      // 저장 → confirm payload 의 portion_amount 가 1.5 로 반영된다.
      await tester.tap(find.text('확인 후 식단 저장'));
      await tester.pumpAndSettle();

      final MealFoodItemInput saved =
          repository.confirmedMealRequest!.foodItems.single;
      expect(saved.displayName, '비빔밥');
      expect(saved.portionAmount, 1.5);
      expect(saved.portionUnit, 'serving');
    },
  );

  testWidgets(
    'meal manual-entry fallback merges database_match items into confirm',
    (WidgetTester tester) async {
      final _ReviewRepository repository = _ReviewRepository(
        mealPreviewJson: _manualEntryMealPreviewJson,
        foodCatalog: const <FoodCatalogItem>[
          FoodCatalogItem(
            id: 'cat-1',
            cuisineCode: 'korean',
            courseCode: 'rice',
            canonicalNameKo: '김치볶음밥',
            source: 'seed',
          ),
        ],
      );
      final AppController controller = AppController(repository: repository);
      await controller.analyzeMealImage('/tmp/meal.png', mealType: 'lunch');

      await tester.pumpWidget(
        ProviderScope(
          overrides: <Override>[
            lemonAidRepositoryProvider.overrideWithValue(repository),
          ],
          child: MaterialApp(
            home: AnalysisResultScreen(mode: 'meal', controller: controller),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // 저장 버튼 라벨(하단 고정)은 즉시 보인다.
      expect(find.text('음식 직접 입력'), findsOneWidget);

      // 후보 0건 + 수동입력 → 직접 입력 폴백 카드. 하단으로 스크롤해 노출.
      await _scrollResultDetails(tester);
      expect(find.text('음식을 직접 검색해 담기'), findsOneWidget);

      // 폴백 카드의 '직접 입력으로 찾기' → 음식 검색 화면 진입.
      await tester.tap(find.text('직접 입력으로 찾기'));
      await tester.pumpAndSettle();
      expect(find.text('직접 입력'), findsOneWidget);

      // 검색 결과를 ⊕ 로 담고 '기록에 추가하기' 로 합류.
      await tester.tap(find.byIcon(Icons.add_rounded).first);
      await tester.pumpAndSettle();
      await tester.tap(find.text('기록에 추가하기'));
      await tester.pumpAndSettle();

      // 분석 결과 화면으로 복귀 + 저장 버튼이 활성 라벨로 바뀜.
      expect(find.text('확인 후 식단 저장'), findsOneWidget);
      await tester.tap(find.text('확인 후 식단 저장'));
      await tester.pumpAndSettle();

      // confirm payload 에 database_match 항목이 합류됐는지.
      final MealFoodItemInput merged =
          repository.confirmedMealRequest!.foodItems.single;
      expect(merged.displayName, '김치볶음밥');
      expect(merged.foodCatalogItemId, 'cat-1');
      expect(merged.source, 'database_match');
    },
  );

  testWidgets(
    'renders figma C-hybrid diet result with score and prioritized caution',
    (WidgetTester tester) async {
      final _ComprehensiveMealRepository repository =
          _ComprehensiveMealRepository(comprehensive: _comprehensiveAnalysis());
      final AppController controller = AppController(repository: repository);
      await controller.analyzeMealImage('/tmp/meal.png', mealType: 'lunch');

      await tester.pumpWidget(
        MaterialApp(
          home: AnalysisResultScreen(mode: 'meal', controller: controller),
        ),
      );
      await tester.pumpAndSettle();

      // Score ring header + grade chip (no raw % exposure).
      expect(
        find.byKey(const ValueKey<String>('diet-score-header')),
        findsOneWidget,
      );
      expect(find.text('균형이 잘 잡혔어요'), findsOneWidget);
      expect(find.text('신뢰도 높음'), findsOneWidget);

      // Cautionary component card is the top-priority insight card.
      expect(
        find.byKey(const ValueKey<String>('cautionary-component-card')),
        findsOneWidget,
      );
      expect(find.text('카페인'), findsOneWidget);
      expect(find.text('출처 · caffeine.md'), findsOneWidget);

      // Nutrient grid renders below the priority caution card.
      expect(find.text('단백질'), findsOneWidget);

      // The caution card sits above the nutrient grid (priority placement).
      final double cautionTop = tester
          .getTopLeft(
            find.byKey(const ValueKey<String>('cautionary-component-card')),
          )
          .dy;
      final double proteinTop = tester.getTopLeft(find.text('단백질')).dy;
      expect(cautionTop, lessThan(proteinTop));

      // The save CTA lives in the persistent bottom bar (always visible).
      expect(find.text('확인 후 식단 저장'), findsOneWidget);

      // The comprehensive request carried the meal nutrient totals.
      expect(repository.comprehensiveIngredients, isNotNull);
      expect(
        repository.comprehensiveIngredients!
            .map((Map<String, Object?> row) => row['nutrient_code'])
            .toList(),
        containsAll(<String>['carbohydrate_g', 'protein_g', 'fat_g']),
      );

      // Purpose card renders after scrolling it into view.
      await tester.scrollUntilVisible(
        find.byKey(const ValueKey<String>('purpose-target-card')),
        160,
      );
      expect(find.text('당뇨'), findsOneWidget);

      // Base meal candidate selection remains intact below the C-hybrid cards.
      await tester.scrollUntilVisible(find.text('어떤 음식이 맞나요?'), 160);
      expect(find.text('어떤 음식이 맞나요?'), findsOneWidget);
    },
  );

  testWidgets('shows low-confidence banner when diet score confidence is low', (
    WidgetTester tester,
  ) async {
    final _ComprehensiveMealRepository repository =
        _ComprehensiveMealRepository(
          comprehensive: _comprehensiveAnalysis(scoreConfidence: 0.4),
        );
    final AppController controller = AppController(repository: repository);
    await controller.analyzeMealImage('/tmp/meal.png', mealType: 'lunch');

    await tester.pumpWidget(
      MaterialApp(
        home: AnalysisResultScreen(mode: 'meal', controller: controller),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('신뢰도 직접 확인 필요'), findsWidgets);
    expect(find.byType(LowConfidenceBanner), findsOneWidget);
  });

  testWidgets('keeps base meal layout when comprehensive analysis is empty', (
    WidgetTester tester,
  ) async {
    final _ComprehensiveMealRepository repository =
        _ComprehensiveMealRepository();
    final AppController controller = AppController(repository: repository);
    await controller.analyzeMealImage('/tmp/meal.png', mealType: 'lunch');

    await tester.pumpWidget(
      MaterialApp(
        home: AnalysisResultScreen(mode: 'meal', controller: controller),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey<String>('diet-score-header')),
      findsNothing,
    );
    expect(
      find.byKey(const ValueKey<String>('cautionary-component-card')),
      findsNothing,
    );
    expect(find.text('어떤 음식이 맞나요?'), findsOneWidget);
    expect(find.text('확인 후 식단 저장'), findsOneWidget);
  });

  testWidgets('predicted nutrient card shows grams without any % (D2)', (
    WidgetTester tester,
  ) async {
    final _ReviewRepository repository = _ReviewRepository(
      mealPreviewJson: _predictedNutrientMealPreviewJson,
    );
    final AppController controller = AppController(repository: repository);
    await controller.analyzeMealImage('/tmp/meal.png', mealType: 'lunch');

    await tester.pumpWidget(
      MaterialApp(
        home: AnalysisResultScreen(mode: 'meal', controller: controller),
      ),
    );
    await tester.pumpAndSettle();

    // 예상 영양소 카드(읽기 전용) — 1인분 기준 기본 노출.
    expect(
      find.byKey(const ValueKey<String>('predicted-nutrient-card')),
      findsOneWidget,
    );
    // D2: 매크로는 그램 값으로만, 단백질은 분석 그리드와 충돌 피해 '단백질 (예상)'.
    expect(find.text('단백질 (예상)'), findsOneWidget);
    expect(find.text('탄수화물'), findsOneWidget);
    expect(find.text('지방'), findsOneWidget);
    // 신뢰도/기준치 % 숫자는 어디에도 노출되지 않는다.
    expect(find.textContaining('%'), findsNothing);
    expect(find.textContaining('88%'), findsNothing);
  });

  testWidgets('core ingredient card uses grade chips without any % (D2)', (
    WidgetTester tester,
  ) async {
    final _ReviewRepository repository = _ReviewRepository(
      preview: _coreIngredientPreview(),
    );
    final AppController controller = AppController(repository: repository);
    await controller.analyzeImage(
      '/tmp/supplement-label.jpg',
      ocrProvider: 'paddleocr',
    );

    await tester.pumpWidget(
      MaterialApp(home: AnalysisResultScreen(controller: controller)),
    );
    await tester.pumpAndSettle();

    // 핵심성분 배지 카드 — dailyValuePercent 가 있을 때만 노출(리스트 하단이라 스크롤).
    await tester.scrollUntilVisible(
      find.byKey(const ValueKey<String>('core-ingredient-card')),
      200,
    );
    expect(
      find.byKey(const ValueKey<String>('core-ingredient-card')),
      findsOneWidget,
    );
    // 충족 등급은 칩(충분/부족)으로만, %DV 숫자는 노출하지 않는다.
    expect(find.text('충분'), findsWidgets);
    expect(find.text('부족'), findsWidgets);
    expect(find.textContaining('%'), findsNothing);
    expect(find.textContaining('120'), findsNothing);
  });
}

Future<void> _scrollResultDetails(WidgetTester tester) async {
  await tester.drag(find.byType(ListView), const Offset(0, -700));
  await tester.pumpAndSettle();
}

class _ReviewRepository implements LemonAidRepository {
  _ReviewRepository({
    SupplementAnalysisPreview? preview,
    SupplementMultiImageAnalysisPreview? multiPreview,
    ComprehensiveDietAnalysis? comprehensive,
    Map<String, Object?>? mealPreviewJson,
    this.foodCatalog = const <FoodCatalogItem>[],
    this.supplementCategories = const <SupplementCategory>[],
  }) : _previewOverride = preview,
       _multiPreviewOverride = multiPreview,
       _comprehensiveOverride = comprehensive,
       _mealPreviewJsonOverride = mealPreviewJson;

  final SupplementAnalysisPreview? _previewOverride;
  final SupplementMultiImageAnalysisPreview? _multiPreviewOverride;
  final ComprehensiveDietAnalysis? _comprehensiveOverride;
  final Map<String, Object?>? _mealPreviewJsonOverride;

  /// Curated categories returned by the 분류 드롭다운 catalog fetch.
  final List<SupplementCategory> supplementCategories;

  /// Catalog rows returned by the direct-input food search fallback.
  List<FoodCatalogItem> foodCatalog;
  UserSupplementCreate? registeredRequest;
  String? confirmedMealId;
  MealConfirmationRequest? confirmedMealRequest;
  List<Map<String, Object?>>? comprehensiveIngredients;
  bool explainUsedLocalLlm = false;

  @override
  Future<ComprehensiveDietAnalysis> analyzeComprehensive({
    required List<Map<String, Object?>> ingredients,
    Map<String, dynamic>? userProfile,
    String persona = 'B',
  }) async {
    comprehensiveIngredients = ingredients;
    return _comprehensiveOverride ?? ComprehensiveDietAnalysis.empty;
  }

  @override
  Future<KdriLookupResult> lookupKdris({
    required int age,
    required String sex,
    String pregnancyStatus = 'none',
  }) async {
    return const KdriLookupResult(
      references: <KdriReference>[],
      datasetStatus: 'sample',
      datasetVersion: 'kdris-2020-sample',
    );
  }

  @override
  Future<SupplementAnalysisPreview> analyzeSupplementImage(
    String imagePath, {
    String ocrProvider = 'configured',
  }) async {
    return _previewOverride ?? _preview();
  }

  @override
  Future<MealImageAnalysisPreview> analyzeMealImage(
    String imagePath, {
    String mealType = 'unknown',
  }) async {
    return MealImageAnalysisPreview.fromJson(
      _mealPreviewJsonOverride ?? _mealPreviewJson,
    );
  }

  @override
  Future<MealRecordResponse> confirmMealImagePreview(
    String mealId,
    MealConfirmationRequest request,
  ) {
    confirmedMealId = mealId;
    confirmedMealRequest = request;
    return Future<MealRecordResponse>.value(
      _mealRecordFromRequest(mealId, request),
    );
  }

  @override
  Future<SupplementMultiImageAnalysisPreview> analyzeSupplementImagesOneShot(
    List<SupplementImageUpload> images, {
    String ocrProvider = 'configured',
    String mergeStrategy = 'single_product',
  }) => analyzeSupplementImages(images, ocrProvider: ocrProvider);

  @override
  Future<SupplementMultiImageAnalysisPreview> analyzeSupplementImages(
    List<SupplementImageUpload> images, {
    String ocrProvider = 'configured',
  }) {
    return Future<SupplementMultiImageAnalysisPreview>.value(
      _multiPreviewOverride ?? _multiPreview(),
    );
  }

  @override
  Future<SupplementAnalysisSession> createSupplementAnalysisSession() {
    throw UnimplementedError();
  }

  @override
  Future<SupplementMultiImageAnalysisPreview>
  uploadSupplementAnalysisSessionImage(
    String analysisGroupId,
    SupplementImageUpload image, {
    String ocrProvider = 'configured',
    String? clientRequestId,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<SupplementMultiImageAnalysisPreview> finalizeSupplementAnalysisSession(
    String analysisGroupId,
  ) {
    throw UnimplementedError();
  }

  @override
  Future<FoodCatalogList> searchFoods({
    String? q,
    String? cuisineCode,
    int limit = 50,
    int offset = 0,
  }) async {
    return FoodCatalogList(results: foodCatalog, limit: limit, offset: offset);
  }

  @override
  Future<FoodCuisineList> fetchCuisines() async => FoodCuisineList.empty;

  @override
  Future<List<SupplementCategory>> fetchSupplementCategories() async =>
      supplementCategories;

  @override
  Future<void> deleteSupplement(String supplementId) async {
    throw UnimplementedError();
  }

  @override
  Future<void> deleteAnalysisResult(String resultId) async {
    throw UnimplementedError();
  }

  @override
  Future<MealRecordResponse> updateMealRecord(
    String mealId,
    MealConfirmationRequest request,
  ) async {
    throw UnimplementedError();
  }

  @override
  Future<void> deleteMealRecord(String mealId) async {
    throw UnimplementedError();
  }

  @override
  void close() {}

  @override
  Future<HomeMedicationsResult> fetchMedications() async {
    return HomeMedicationsResult.empty;
  }

  @override
  Future<HomeMedication> createMedication(MedicationCreateRequest request) {
    throw UnimplementedError();
  }

  @override
  Future<HomeMedication> deactivateMedication(String medicationId) {
    throw UnimplementedError();
  }

  @override
  Future<HomeMedication> reactivateMedication(String medicationId) {
    throw UnimplementedError();
  }

  @override
  Future<ConsentState> fetchConsents() {
    throw UnimplementedError();
  }

  @override
  Future<DashboardSummary> fetchDashboardSummary({int days = 30}) {
    return Future<DashboardSummary>.value(_dashboardSummary());
  }

  @override
  Future<HomeMealsResult> fetchMeals({
    DateTime? from,
    DateTime? to,
    int limit = 50,
    int offset = 0,
  }) {
    return Future<HomeMealsResult>.value(HomeMealsResult.empty);
  }

  @override
  Future<HomeSupplementsResult> fetchSupplements({
    int limit = 50,
    int offset = 0,
  }) {
    return Future<HomeSupplementsResult>.value(HomeSupplementsResult.empty);
  }

  @override
  Future<ConsentAction> grantConsent(String consentType) {
    throw UnimplementedError();
  }

  @override
  Future<SupplementAnalysisPreview> parseOcrText({
    required String analysisId,
    required SupplementOCRTextParseRequest request,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<UserSupplementResponse> registerSupplement(
    UserSupplementCreate request,
  ) {
    registeredRequest = request;
    return Future<UserSupplementResponse>.value(
      UserSupplementResponse(
        id: 'supplement-1',
        displayName: request.displayName,
        manufacturer: request.manufacturer,
        precautionSnapshot: request.precautionSnapshot,
      ),
    );
  }

  @override
  Future<SupplementImpactPreviewResponse> previewSupplementImpact(
    SupplementImpactPreviewRequest request,
  ) {
    return Future<SupplementImpactPreviewResponse>.value(_impactPreview());
  }

  @override
  Future<SupplementImpactPreviewResponse>
  fetchLatestSupplementRecommendation() {
    throw UnimplementedError();
  }

  @override
  Future<SupplementRecommendationExplainResponse>
  explainSupplementRecommendation(
    SupplementImpactPreviewResponse preview, {
    bool useLocalLlm = false,
  }) {
    explainUsedLocalLlm = useLocalLlm;
    return Future<SupplementRecommendationExplainResponse>.value(
      const SupplementRecommendationExplainResponse(
        safeUserMessage: 'Local explanation ready.',
        explanationBullets: <String>['라벨 확인 값을 기준으로 설명합니다.'],
        clinicalDisclaimer: 'Reference information only.',
        blockedTermsDetected: <String>[],
        llmUsed: true,
        sourceCitations: <SupplementExplanationSourceCitation>[
          SupplementExplanationSourceCitation(
            title: '비타민 D',
            sourcePath: 'vitamin-d.md',
            heading: '확인 필요',
            excerpt: '비타민 D는 개인 상태와 함께 확인합니다.',
            score: 9,
          ),
        ],
        warnings: <String>[],
      ),
    );
  }

  @override
  Future<SupplementRecommendationExplainResponse> explainSupplementAnalysis(
    String analysisId, {
    bool useLocalLlm = false,
  }) {
    return Future<SupplementRecommendationExplainResponse>.value(
      const SupplementRecommendationExplainResponse(
        safeUserMessage: 'Analysis explanation ready.',
        explanationBullets: <String>['성분 후보를 등록 전에 확인합니다.'],
        clinicalDisclaimer: 'Reference information only.',
        blockedTermsDetected: <String>[],
        llmUsed: true,
        sourceCitations: <SupplementExplanationSourceCitation>[
          SupplementExplanationSourceCitation(
            title: '성분표 확인',
            sourcePath: 'supplement-label.md',
            heading: '라벨',
            excerpt: '성분표는 저장 전 확인합니다.',
            score: 5,
          ),
        ],
        warnings: <String>[],
      ),
    );
  }

  SupplementAnalysisPreview _preview({
    String analysisId = 'analysis-1',
    String? productName = '비타민 D',
    String? manufacturer = 'Lemon Lab',
    String ingredientName = 'Vitamin D',
    String? originalIngredientName,
    double? ingredientAmount = 25,
    String? ingredientUnit = 'mcg',
    String ingredientSource = 'ocr_llm_preview',
    bool includeSecondIngredient = false,
    bool includeIngredientCandidates = true,
    bool includeSupplementFactsSection = true,
    bool includeIntakeSection = true,
    bool includePrecautionsSection = true,
    String imageRole = 'supplement_facts',
    List<String> missingRequiredSections = const <String>[],
    String? rawOcrText,
  }) {
    final List<SupplementIngredientCandidate> ingredients =
        includeIngredientCandidates
        ? <SupplementIngredientCandidate>[
            SupplementIngredientCandidate(
              displayName: ingredientName,
              originalName: originalIngredientName,
              nutrientCode: ingredientName.toLowerCase().replaceAll(' ', '_'),
              amount: ingredientAmount,
              unit: ingredientUnit,
              confidence: 0.92,
              source: ingredientSource,
            ),
          ]
        : <SupplementIngredientCandidate>[];
    if (includeIngredientCandidates && includeSecondIngredient) {
      ingredients.add(
        SupplementIngredientCandidate(
          displayName: 'Sunflower oil',
          nutrientCode: null,
          amount: null,
          unit: null,
          confidence: 0.81,
          source: ingredientSource,
        ),
      );
    }
    final String ingredientText =
        '$ingredientName ${ingredientAmount?.toStringAsFixed(0) ?? ''} ${ingredientUnit ?? ''}'
            .trim();
    final List<SupplementPreviewLabelSection> labelSections =
        <SupplementPreviewLabelSection>[
          if (includeSupplementFactsSection)
            SupplementPreviewLabelSection(
              sectionId: 'section-1',
              sectionType: 'supplement_facts',
              headingText: 'Supplement Facts',
              textBundle: ingredientText,
              confidence: 0.91,
              requiresReview: false,
              evidenceRefs: const <String>['span-1'],
            ),
          if (includeIntakeSection)
            const SupplementPreviewLabelSection(
              sectionId: 'section-2',
              sectionType: 'intake_method',
              headingText: 'Directions',
              textBundle: '하루 1회 1캡슐',
              confidence: 0.9,
              requiresReview: false,
              evidenceRefs: <String>['span-2'],
            ),
          if (includePrecautionsSection)
            const SupplementPreviewLabelSection(
              sectionId: 'section-3',
              sectionType: 'precautions',
              headingText: 'Warning',
              textBundle: '임신 중이면 전문가와 상담하세요.',
              confidence: 0.88,
              requiresReview: false,
              evidenceRefs: <String>['span-3'],
            ),
        ];
    final List<SupplementPreviewEvidenceSpan> evidenceSpans =
        <SupplementPreviewEvidenceSpan>[
          if (includeSupplementFactsSection)
            SupplementPreviewEvidenceSpan(
              spanId: 'span-1',
              sourceType: 'ocr',
              sectionType: 'supplement_facts',
              textExcerpt: ingredientText,
              pageIndex: null,
              cellRef: null,
              confidence: 0.91,
            ),
          if (includeIntakeSection)
            const SupplementPreviewEvidenceSpan(
              spanId: 'span-2',
              sourceType: 'ocr',
              sectionType: 'intake_method',
              textExcerpt: '하루 1회 1캡슐',
              pageIndex: null,
              cellRef: null,
              confidence: 0.9,
            ),
          if (includePrecautionsSection)
            const SupplementPreviewEvidenceSpan(
              spanId: 'span-3',
              sourceType: 'ocr',
              sectionType: 'precautions',
              textExcerpt: '임신 중이면 전문가와 상담하세요.',
              pageIndex: null,
              cellRef: null,
              confidence: 0.88,
            ),
        ];
    return SupplementAnalysisPreview(
      analysisId: analysisId,
      status: 'requires_confirmation',
      parsedProduct: SupplementParsedProduct(
        productName: productName,
        manufacturer: manufacturer,
        servingSize: 'capsule',
        dailyServings: 1,
      ),
      ingredientCandidates: ingredients,
      layoutAvailable: true,
      layoutFallbackReason: null,
      labelSections: labelSections,
      intakeMethod: includeIntakeSection
          ? const SupplementPreviewIntakeMethod(
              text: '하루 1회 1캡슐',
              structured: SupplementPreviewStructuredIntakeMethod(
                frequency: 'daily',
                timeOfDay: <String>['morning'],
                timesPerDay: 1,
                amountPerTime: 1,
                amountUnit: 'capsule',
                withFood: 'unknown',
              ),
              confidence: 0.9,
              requiresReview: false,
              evidenceRefs: <String>['span-2'],
            )
          : SupplementPreviewIntakeMethod.empty,
      precautions: includePrecautionsSection
          ? const <SupplementPreviewPrecaution>[
              SupplementPreviewPrecaution(
                text: '임신 중이면 전문가와 상담하세요.',
                category: 'pregnancy',
                severity: 'review',
                confidence: 0.88,
                requiresReview: false,
                evidenceRefs: <String>['span-3'],
              ),
            ]
          : const <SupplementPreviewPrecaution>[],
      functionalClaims: const <SupplementPreviewFunctionalClaim>[],
      evidenceSpans: evidenceSpans,
      imageQualityReport: null,
      analysisScope: 'supplement_label',
      actionRequired: 'none',
      detectedProductRegions: const <SupplementDetectedProductRegion>[],
      selectedRegionId: null,
      missingRequiredSections: missingRequiredSections,
      imageRole: imageRole,
      multiImageGroupId: null,
      sourceType: 'uploaded_image',
      identityConflict: null,
      pipelineMetadata: SupplementImagePipelineMetadata(
        intakeCompleted: true,
        imageCount: 1,
        imageRole: imageRole,
        visionRoiUsed: true,
        ocrStatus: 'success',
        visionStatus: 'success',
        llmStatus: 'success',
        ocrProvider: 'paddleocr_local',
        ocrTextPresent: true,
        ocrConfidenceBucket: 'high',
        roiCount: 1,
        sectionCount: labelSections.length,
        llmParserUsed: true,
        parserContractVersion: 'test-parser-v3',
        missingRequiredSections: missingRequiredSections,
        rawImageStored: false,
        rawOcrTextStored: false,
      ),
      rawOcrText: rawOcrText,
      lowConfidenceFields: const <String>[],
      warnings: const <String>[],
      algorithmVersion: 'test',
      sourceManifestVersion: null,
      expiresAt: DateTime.utc(2026, 5, 26),
    );
  }

  SupplementMultiImageAnalysisPreview _multiPreview() {
    final List<SupplementAnalysisPreview> previews =
        <SupplementAnalysisPreview>[
          _preview(),
          _preview(
            analysisId: 'analysis-2',
            productName: '오메가-3',
            manufacturer: 'Ocean Lab',
            ingredientName: 'Omega-3',
            ingredientAmount: 1000,
            ingredientUnit: 'mg',
          ),
        ];
    return SupplementMultiImageAnalysisPreview(
      analysisGroupId: 'multi-analysis-1',
      imageCount: previews.length,
      previews: previews,
      mergedPreview: null,
      missingRequiredSections: const <String>[],
      actionRequired: 'none',
      pipelineMetadata: previews.first.pipelineMetadata,
      expiresAt: previews.first.expiresAt,
    );
  }
}

/// Meal-flow repository whose meal preview carries nutrition totals so the
/// comprehensive diet analysis call fires with real nutrient rows.
class _ComprehensiveMealRepository extends _ReviewRepository {
  _ComprehensiveMealRepository({super.comprehensive});

  @override
  Future<MealImageAnalysisPreview> analyzeMealImage(
    String imagePath, {
    String mealType = 'unknown',
  }) async {
    return MealImageAnalysisPreview.fromJson(_mealPreviewWithTotalsJson);
  }
}

ComprehensiveDietAnalysis _comprehensiveAnalysis({
  double scoreConfidence = 0.9,
}) {
  return ComprehensiveDietAnalysis.fromJson(<String, dynamic>{
    'diet_score': 78,
    'diet_score_label': '균형이 잘 잡혔어요',
    'diet_score_message': '나트륨만 조금 줄이면 좋아요.',
    'diet_score_confidence': scoreConfidence,
    'deficient_nutrients': <Object?>[
      <String, dynamic>{
        'nutrient_code': 'protein_g',
        'nutrient_name': '단백질',
        'deficit_ratio': 0.5,
        'unit': 'g',
        'confidence': 0.7,
        'message': '단백질이 더 필요해요.',
      },
    ],
    'excessive_nutrients': <Object?>[
      <String, dynamic>{
        'nutrient_code': 'sodium_mg',
        'nutrient_name': '나트륨',
        'excess_ratio': 1.1,
        'unit': 'mg',
        'confidence': 0.4,
        'message': '나트륨을 조금 줄여보세요.',
      },
    ],
    'cautionary_components': <Object?>[
      <String, dynamic>{
        'component': '카페인',
        'reason': '늦은 시간 섭취',
        'severity': 'high',
        'message': '저녁 섭취는 피하는 게 좋아요.',
        'source_citation': 'caffeine.md',
      },
    ],
    'purpose_targets': <Object?>[
      <String, dynamic>{
        'condition': '당뇨',
        'relevance_score': 0.8,
        'evidence_level': 'moderate',
        'message': 'GI 지수를 함께 확인해보세요.',
      },
    ],
    'chronic_disease_indications': <String>[],
    'warnings': <String>[],
  });
}

final Map<String, Object?> _mealPreviewWithTotalsJson = <String, Object?>{
  ..._mealPreviewJson,
  'nutrition_estimate_summary': <String, Object?>{
    'status': 'detected_review_required',
    'items': <Object?>[],
    'totals': <String, Object?>{
      'carb_g': 78,
      'protein_g': 18,
      'fat_g': 12,
      'sodium_mg': 820,
    },
    'detector_used': true,
  },
};

SupplementMultiImageAnalysisPreview _threeSupplementMultiPreview() {
  final _ReviewRepository source = _ReviewRepository();
  final List<SupplementAnalysisPreview> previews = <SupplementAnalysisPreview>[
    source._preview(
      analysisId: 'analysis-a-front',
      productName: 'Lemon Multi',
      manufacturer: 'Lemon Lab',
      includeIngredientCandidates: false,
      includeSupplementFactsSection: false,
      includeIntakeSection: false,
      includePrecautionsSection: false,
      imageRole: 'front_label',
      missingRequiredSections: const <String>[
        'supplement_facts',
        'intake_method',
        'precautions',
      ],
    ),
    source._preview(
      analysisId: 'analysis-a-facts',
      productName: null,
      manufacturer: null,
      ingredientName: 'Vitamin C',
      ingredientAmount: 500,
      ingredientUnit: 'mg',
      includeIntakeSection: false,
      includePrecautionsSection: false,
      missingRequiredSections: const <String>[
        'product_name',
        'intake_method',
        'precautions',
      ],
    ),
    source._preview(
      analysisId: 'analysis-b',
      productName: 'Omega Plus',
      manufacturer: 'Ocean Lab',
      ingredientName: 'Omega-3',
      ingredientAmount: 1000,
      ingredientUnit: 'mg',
      missingRequiredSections: const <String>[],
    ),
    source._preview(
      analysisId: 'analysis-c',
      productName: 'Magnesium Calm',
      manufacturer: 'Mineral Lab',
      ingredientName: 'Magnesium',
      ingredientAmount: 200,
      ingredientUnit: 'mg',
      missingRequiredSections: const <String>[],
    ),
  ];
  return SupplementMultiImageAnalysisPreview(
    analysisGroupId: 'multi-analysis-three-products',
    imageCount: previews.length,
    previews: previews,
    mergedPreview: source._preview(
      analysisId: 'analysis-global',
      productName: 'Merged batch',
      manufacturer: 'Global Lab',
      ingredientName: 'Global Ingredient',
      ingredientAmount: 1,
      ingredientUnit: 'mg',
    ),
    missingRequiredSections: const <String>[],
    actionRequired: 'none',
    pipelineMetadata: previews.first.pipelineMetadata,
    expiresAt: previews.first.expiresAt,
  );
}

class _PendingReviewRepository extends _ReviewRepository {
  final Completer<SupplementAnalysisPreview> _completer =
      Completer<SupplementAnalysisPreview>();

  @override
  Future<SupplementAnalysisPreview> analyzeSupplementImage(
    String imagePath, {
    String ocrProvider = 'configured',
  }) {
    return _completer.future;
  }

  void complete() {
    if (!_completer.isCompleted) {
      _completer.complete(_preview());
    }
  }
}

class _PendingMealRepository extends _ReviewRepository {
  final Completer<MealImageAnalysisPreview> _completer =
      Completer<MealImageAnalysisPreview>();

  @override
  Future<MealImageAnalysisPreview> analyzeMealImage(
    String imagePath, {
    String mealType = 'unknown',
  }) {
    return _completer.future;
  }

  void complete() {
    if (!_completer.isCompleted) {
      _completer.complete(MealImageAnalysisPreview.fromJson(_mealPreviewJson));
    }
  }
}

SupplementAnalysisPreview _emptyCandidatePreview() {
  return SupplementAnalysisPreview(
    analysisId: 'analysis-empty',
    status: 'requires_confirmation',
    parsedProduct: const SupplementParsedProduct(
      productName: null,
      manufacturer: null,
      servingSize: null,
      dailyServings: null,
    ),
    ingredientCandidates: const <SupplementIngredientCandidate>[],
    layoutAvailable: true,
    layoutFallbackReason: null,
    labelSections: const <SupplementPreviewLabelSection>[],
    intakeMethod: SupplementPreviewIntakeMethod.empty,
    precautions: const <SupplementPreviewPrecaution>[],
    functionalClaims: const <SupplementPreviewFunctionalClaim>[],
    evidenceSpans: const <SupplementPreviewEvidenceSpan>[
      SupplementPreviewEvidenceSpan(
        spanId: 'span-empty',
        sourceType: 'ocr',
        sectionType: 'supplement_facts',
        textExcerpt: '라벨 일부만 확인됨',
        pageIndex: null,
        cellRef: null,
        confidence: 0.42,
      ),
    ],
    imageQualityReport: null,
    analysisScope: 'supplement_label',
    actionRequired: 'review_required',
    detectedProductRegions: const <SupplementDetectedProductRegion>[],
    selectedRegionId: null,
    missingRequiredSections: const <String>[
      'product_name',
      'supplement_facts',
      'intake_method',
      'precautions',
    ],
    imageRole: 'unknown',
    multiImageGroupId: null,
    sourceType: 'uploaded_image',
    identityConflict: null,
    pipelineMetadata: const SupplementImagePipelineMetadata(
      intakeCompleted: true,
      imageCount: 1,
      imageRole: 'unknown',
      visionRoiUsed: false,
      ocrStatus: 'success',
      visionStatus: 'skipped',
      llmStatus: 'warning',
      ocrProvider: 'paddleocr_local',
      ocrTextPresent: true,
      ocrConfidenceBucket: 'low',
      roiCount: 0,
      sectionCount: 0,
      llmParserUsed: true,
      parserContractVersion: 'test-parser-v3',
      missingRequiredSections: <String>[
        'product_name',
        'supplement_facts',
        'intake_method',
        'precautions',
      ],
      rawImageStored: false,
      rawOcrTextStored: false,
    ),
    lowConfidenceFields: const <String>['ingredient_candidates'],
    warnings: const <String>['Automatic parsing needs review.'],
    algorithmVersion: 'test',
    sourceManifestVersion: null,
    expiresAt: DateTime.utc(2026, 5, 26),
  );
}

/// OCR이 성분 섹션 글자는 읽었지만 구조화 성분 후보가 비어 있는 미리보기.
SupplementAnalysisPreview _recognizedTextPreview() {
  return SupplementAnalysisPreview(
    analysisId: 'analysis-recognized-text',
    status: 'requires_confirmation',
    parsedProduct: const SupplementParsedProduct(
      productName: null,
      manufacturer: null,
      servingSize: null,
      dailyServings: null,
    ),
    ingredientCandidates: const <SupplementIngredientCandidate>[],
    layoutAvailable: true,
    layoutFallbackReason: null,
    labelSections: const <SupplementPreviewLabelSection>[
      SupplementPreviewLabelSection(
        sectionId: 'section-facts',
        sectionType: 'supplement_facts',
        headingText: '성분·함량',
        textBundle: '비타민C 1000mg, 아연 15mg',
        confidence: 0.61,
        requiresReview: true,
        evidenceRefs: <String>['span-facts'],
      ),
    ],
    intakeMethod: SupplementPreviewIntakeMethod.empty,
    precautions: const <SupplementPreviewPrecaution>[],
    functionalClaims: const <SupplementPreviewFunctionalClaim>[],
    evidenceSpans: const <SupplementPreviewEvidenceSpan>[
      SupplementPreviewEvidenceSpan(
        spanId: 'span-facts',
        sourceType: 'ocr',
        sectionType: 'supplement_facts',
        textExcerpt: '비타민C 1000mg, 아연 15mg',
        pageIndex: null,
        cellRef: null,
        confidence: 0.61,
      ),
    ],
    imageQualityReport: null,
    analysisScope: 'supplement_label',
    actionRequired: 'review_required',
    detectedProductRegions: const <SupplementDetectedProductRegion>[],
    selectedRegionId: null,
    missingRequiredSections: const <String>[
      'product_name',
      'intake_method',
      'precautions',
    ],
    imageRole: 'unknown',
    multiImageGroupId: null,
    sourceType: 'uploaded_image',
    identityConflict: null,
    pipelineMetadata: const SupplementImagePipelineMetadata(
      intakeCompleted: true,
      imageCount: 1,
      imageRole: 'unknown',
      visionRoiUsed: false,
      ocrStatus: 'success',
      visionStatus: 'skipped',
      llmStatus: 'warning',
      ocrProvider: 'clova_ocr',
      ocrTextPresent: true,
      ocrConfidenceBucket: 'medium',
      roiCount: 0,
      sectionCount: 1,
      llmParserUsed: true,
      parserContractVersion: 'test-parser-v3',
      missingRequiredSections: <String>[
        'product_name',
        'intake_method',
        'precautions',
      ],
      rawImageStored: false,
      rawOcrTextStored: false,
    ),
    lowConfidenceFields: const <String>['ingredient_candidates'],
    warnings: const <String>['Automatic parsing needs review.'],
    algorithmVersion: 'test',
    sourceManifestVersion: null,
    expiresAt: DateTime.utc(2026, 5, 26),
  );
}

/// 매크로가 채워진 음식 후보(예상 영양소 카드 가드용).
final Map<String, Object?> _predictedNutrientMealPreviewJson =
    <String, Object?>{
      ..._mealPreviewJson,
      'food_candidates': <Object?>[
        <String, Object?>{
          'display_name': '비빔밥',
          'portion_amount': 1,
          'portion_unit': 'serving',
          'kcal': 520,
          'carb_g': 78,
          'protein_g': 18,
          'fat_g': 12,
          'sodium_mg': 820,
          'confidence': 0.88,
          'source': 'vision',
        },
      ],
    };

/// dailyValuePercent 가 채워진 성분 후보(핵심성분 배지 카드 가드용).
SupplementAnalysisPreview _coreIngredientPreview() {
  final _ReviewRepository source = _ReviewRepository();
  final SupplementAnalysisPreview base = source._preview();
  return SupplementAnalysisPreview(
    analysisId: base.analysisId,
    status: base.status,
    parsedProduct: base.parsedProduct,
    ingredientCandidates: const <SupplementIngredientCandidate>[
      SupplementIngredientCandidate(
        displayName: '비타민 C',
        originalName: 'Vitamin C',
        nutrientCode: 'vitamin_c',
        amount: 1000,
        unit: 'mg',
        confidence: 0.92,
        source: 'ocr_llm_preview',
        dailyValuePercent: 120,
      ),
      SupplementIngredientCandidate(
        displayName: '아연',
        originalName: 'Zinc',
        nutrientCode: 'zinc',
        amount: 5,
        unit: 'mg',
        confidence: 0.9,
        source: 'ocr_llm_preview',
        dailyValuePercent: 60,
      ),
    ],
    layoutAvailable: base.layoutAvailable,
    layoutFallbackReason: base.layoutFallbackReason,
    labelSections: base.labelSections,
    intakeMethod: base.intakeMethod,
    precautions: base.precautions,
    functionalClaims: base.functionalClaims,
    evidenceSpans: base.evidenceSpans,
    imageQualityReport: base.imageQualityReport,
    analysisScope: base.analysisScope,
    actionRequired: base.actionRequired,
    detectedProductRegions: base.detectedProductRegions,
    selectedRegionId: base.selectedRegionId,
    missingRequiredSections: base.missingRequiredSections,
    imageRole: base.imageRole,
    multiImageGroupId: base.multiImageGroupId,
    sourceType: base.sourceType,
    identityConflict: base.identityConflict,
    pipelineMetadata: base.pipelineMetadata,
    lowConfidenceFields: base.lowConfidenceFields,
    warnings: base.warnings,
    algorithmVersion: base.algorithmVersion,
    sourceManifestVersion: base.sourceManifestVersion,
    expiresAt: base.expiresAt,
  );
}

final Map<String, Object?> _mealPreviewJson = <String, Object?>{
  'analysis_id': '00000000-0000-0000-0000-000000000101',
  'meal_id': '00000000-0000-0000-0000-000000000201',
  'status': 'requires_confirmation',
  'meal_type': 'lunch',
  'eaten_at': '2026-05-28T03:00:00Z',
  'food_candidates': <Object?>[
    <String, Object?>{
      'display_name': '비빔밥',
      'portion_amount': null,
      'portion_unit': null,
      'kcal': null,
      'carb_g': null,
      'protein_g': null,
      'fat_g': null,
      'sodium_mg': null,
      'confidence': 0.88,
      'source': 'vision',
    },
  ],
  'nutrition_estimate_summary': <String, Object?>{
    'status': 'detected_review_required',
    'items': <Object?>[],
    'totals': <String, Object?>{},
    'detector_used': true,
  },
  'warning_codes': <String>['food_detection_review_required'],
  'pipeline_metadata': <String, Object?>{
    'intake_completed': true,
    'detector_model': 'food_yolo_local:best.pt',
    'classifier_model': null,
    'detector_used': true,
    'classifier_used': false,
    'raw_image_stored': false,
    'raw_provider_payload_stored': false,
    'requires_manual_entry': false,
  },
  'algorithm_version': 'food-image-preview-v1.0.0',
  'created_at': '2026-05-28T03:00:01Z',
};

// 후보 0건 + requires_manual_entry: 카메라 분석 폴백(직접 입력) 진입 케이스.
final Map<String, Object?> _manualEntryMealPreviewJson = <String, Object?>{
  'analysis_id': '00000000-0000-0000-0000-000000000101',
  'meal_id': '00000000-0000-0000-0000-000000000201',
  'status': 'requires_confirmation',
  'meal_type': 'lunch',
  'eaten_at': '2026-05-28T03:00:00Z',
  'food_candidates': <Object?>[],
  'nutrition_estimate_summary': <String, Object?>{
    'status': 'manual_entry_required',
    'items': <Object?>[],
    'totals': <String, Object?>{},
    'detector_used': false,
  },
  'warning_codes': <String>['food_detection_manual_entry_required'],
  'pipeline_metadata': <String, Object?>{
    'intake_completed': true,
    'detector_model': null,
    'classifier_model': null,
    'detector_used': false,
    'classifier_used': false,
    'raw_image_stored': false,
    'raw_provider_payload_stored': false,
    'requires_manual_entry': true,
  },
  'algorithm_version': 'food-image-preview-v1.0.0',
  'created_at': '2026-05-28T03:00:01Z',
};

MealRecordResponse _mealRecordFromRequest(
  String mealId,
  MealConfirmationRequest request,
) {
  final MealFoodItemInput item = request.foodItems.first;
  return MealRecordResponse(
    id: mealId,
    status: 'confirmed',
    mealType: request.mealType ?? 'unknown',
    eatenAt: request.eatenAt ?? DateTime.utc(2026, 5, 28, 3),
    foodItems: <MealFoodItemResponse>[
      MealFoodItemResponse(
        id: '00000000-0000-0000-0000-000000000301',
        displayName: item.displayName,
        portionAmount: item.portionAmount,
        portionUnit: item.portionUnit,
        kcal: item.kcal,
        carbG: item.carbG,
        proteinG: item.proteinG,
        fatG: item.fatG,
        sodiumMg: item.sodiumMg,
        confidence: item.confidence,
        source: item.source,
      ),
    ],
    nutritionSummary: const <String, Object?>{'status': 'user_confirmed'},
    confirmedAt: DateTime.utc(2026, 5, 28, 3, 5),
    createdAt: DateTime.utc(2026, 5, 28, 3),
  );
}

DashboardSummary _dashboardSummary() {
  return DashboardSummary(
    asOf: DateTime.utc(2026, 5, 28),
    nutrition: const DashboardNutritionSummary(
      dataStatus: 'partial',
      lowCount: 0,
      highCount: 0,
      datasetVersion: 'test',
    ),
    activity: const DashboardActivitySummary(
      dataStatus: 'partial',
      latestSteps: null,
      latestActivityScore: null,
    ),
    weight: const DashboardWeightSummary(
      dataStatus: 'partial',
      latestWeightKg: null,
      predictedWeightKg: null,
    ),
    supplements: const DashboardSupplementSummary(
      registeredCount: 1,
      requiresReviewCount: 0,
    ),
    disclaimers: const <String>[],
    algorithmVersion: 'test',
  );
}

SupplementImpactPreviewResponse _impactPreview() {
  return const SupplementImpactPreviewResponse(
    calculationVersion: 'supplement-impact-v1.0.0',
    referenceVersion: '2025',
    sourceManifestVersion: null,
    dataStatus: 'partial',
    currentSupplementContributions: <SupplementContributionAggregate>[],
    deficiencySupportCandidates: <SupplementNutritionInsight>[],
    excessOrDuplicateRisks: <SupplementNutritionInsight>[],
    missingProfileFields: <String>[],
    safeUserMessage: 'Impact ready.',
    clinicalDisclaimer: 'Reference information only.',
    warnings: <String>[],
    requiresUserConfirmation: true,
  );
}
