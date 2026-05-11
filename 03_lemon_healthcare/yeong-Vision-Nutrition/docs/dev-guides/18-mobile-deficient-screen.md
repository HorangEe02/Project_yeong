# dev-guides/18 — 부족 영양소 결과 화면 (5종 출력 ①)

> **Phase**: 3 | **선행 작업**: [`13-mobile-dashboard.md`](./13-mobile-dashboard.md), [`06-deficient-nutrient-diagnosis.md`](./06-deficient-nutrient-diagnosis.md) | **예상 소요**: 3~4시간

---

## 🎯 작업 목표

5종 출력의 첫 번째 출력인 **부족 영양소** 화면을 구현한다. 영양제 등록 직후 자동으로 표시되며, 부족 영양소 우선·UL 위험 강조·식약처 인정 식품 권장이 핵심.

---

## 📋 산출물

```
mobile/
└── lib/features/nutrition/
    ├── data/
    │   └── nutrition_repository.dart
    ├── domain/
    │   └── deficient_models.dart           # Freezed
    └── presentation/
        ├── screens/
        │   └── deficient_nutrients_screen.dart  # 메인 화면
        ├── widgets/
        │   ├── deficient_nutrient_card.dart
        │   ├── status_badge.dart
        │   ├── recommended_foods_card.dart
        │   └── ul_warning_banner.dart       # UL 초과 강조
        └── providers/
            └── deficient_provider.dart
```

---

## 📐 화면 구성

```
┌─────────────────────────────────┐
│ 부족 영양소 분석                  │
├─────────────────────────────────┤
│                                 │
│ ⚠ 비타민 C 섭취량이 상한치를 초과 │ ← UL 경고 배너 (있을 때만)
│                                 │
│ [요약]                          │
│ 분석 영양소 12종 중              │
│ 부족 3종 / 적정 8종 / 주의 1종   │
│                                 │
├─ 부족·결핍 영양소 (3) ──────────┤
│ ┌─────────────────────────┐    │
│ │ 비타민 D       30%       │    │
│ │ ⚪⚪⚪⚪⚪⚪⚪░░░░          │    │
│ │ 25 IU / 권장 1000 IU      │    │
│ │ 햇볕 노출과 등푸른생선...  │    │
│ └─────────────────────────┘    │
│ ...                            │
│                                │
├─ 적정 영양소 (8) ────────────────┤
│ ✓ 비타민 C ✓ 칼슘 ✓ 철분 ...    │
│                                │
├─────────────────────────────────┤
│ [면책 고지 — main]              │
└─────────────────────────────────┘
```

---

## 🔧 구현 명세

### 1. 데이터 모델 (Freezed)

대부분의 모델은 가이드 11에서 이미 정의됨 (`Ingredient`, `Diagnosis`, `NutrientDiagnosis`). 추가 필요한 것:

```dart
// lib/features/nutrition/domain/deficient_models.dart
import 'package:freezed_annotation/freezed_annotation.dart';

part 'deficient_models.freezed.dart';
part 'deficient_models.g.dart';

/// 부족 영양소 화면 통합 데이터.
@freezed
class DeficientAnalysis with _$DeficientAnalysis {
  const factory DeficientAnalysis({
    required Diagnosis diagnosis,
    required Map<String, List<String>> recommendedFoods,
  }) = _DeficientAnalysis;

  factory DeficientAnalysis.fromJson(Map<String, dynamic> json) =>
      _$DeficientAnalysisFromJson(json);
}
```

### 2. Repository

```dart
// lib/features/nutrition/data/nutrition_repository.dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../core/network/dio_provider.dart';
import '../domain/deficient_models.dart';

part 'nutrition_repository.g.dart';

class NutritionRepository {
  NutritionRepository(this._dio);
  final Dio _dio;

  /// 최신 부족 영양소 분석 조회.
  Future<DeficientAnalysis> getLatestDiagnosis() async {
    final response = await _dio.get<Map<String, dynamic>>(
      '/api/v1/nutrition/diagnosis/latest',
    );
    return DeficientAnalysis.fromJson(response.data!);
  }
}

@riverpod
NutritionRepository nutritionRepository(NutritionRepositoryRef ref) {
  return NutritionRepository(ref.watch(dioProvider));
}
```

### 3. Provider

```dart
// lib/features/nutrition/presentation/providers/deficient_provider.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../data/nutrition_repository.dart';
import '../../domain/deficient_models.dart';

part 'deficient_provider.g.dart';

@riverpod
Future<DeficientAnalysis> deficientAnalysis(
  DeficientAnalysisRef ref,
) async {
  return ref.watch(nutritionRepositoryProvider).getLatestDiagnosis();
}
```

### 4. 메인 화면

```dart
// lib/features/nutrition/presentation/screens/deficient_nutrients_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../shared/widgets/app_error.dart';
import '../../../../shared/widgets/app_loading.dart';
import '../../../../shared/widgets/disclaimer.dart';
import '../providers/deficient_provider.dart';
import '../widgets/deficient_nutrient_card.dart';
import '../widgets/recommended_foods_card.dart';
import '../widgets/ul_warning_banner.dart';

/// 부족 영양소 분석 결과 화면 (5종 출력 ①).
class DeficientNutrientsScreen extends ConsumerWidget {
  const DeficientNutrientsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncAnalysis = ref.watch(deficientAnalysisProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('부족 영양소 분석')),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(deficientAnalysisProvider),
        child: asyncAnalysis.when(
          data: (analysis) => _Content(analysis: analysis),
          loading: () => const AppLoading(message: '분석 중...'),
          error: (e, _) => AppError(
            message: '$e',
            onRetry: () => ref.invalidate(deficientAnalysisProvider),
          ),
        ),
      ),
    );
  }
}

class _Content extends StatelessWidget {
  const _Content({required this.analysis});
  final DeficientAnalysis analysis;

  @override
  Widget build(BuildContext context) {
    final diagnosis = analysis.diagnosis;
    final deficient = diagnosis.diagnoses
        .where((d) => d.status == 'deficient' || d.status == 'low')
        .toList();
    final adequate = diagnosis.diagnoses
        .where((d) => d.status == 'adequate')
        .toList();
    final risky = diagnosis.diagnoses
        .where((d) => d.status == 'risky')
        .toList();

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // UL 초과 영양소가 있으면 상단 경고
        if (risky.isNotEmpty) ...[
          ULWarningBanner(riskyNutrients: risky),
          const SizedBox(height: 16),
        ],

        // 요약 카드
        _SummaryCard(diagnosis: diagnosis),
        const SizedBox(height: 24),

        // 부족 영양소 (우선 표시)
        if (deficient.isNotEmpty) ...[
          Text(
            '부족·결핍 영양소 (${deficient.length})',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          ...deficient.map(
            (d) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: DeficientNutrientCard(
                diagnosis: d,
                recommendedFoods: analysis.recommendedFoods[d.code] ?? const [],
              ),
            ),
          ),
          const SizedBox(height: 24),
        ],

        // 적정 영양소 (요약만)
        if (adequate.isNotEmpty) ...[
          Text(
            '적정 영양소 (${adequate.length})',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: adequate
                .map((d) => Chip(
                      label: Text('✓ ${d.nameKo}'),
                      backgroundColor: Colors.green.shade50,
                    ))
                .toList(),
          ),
          const SizedBox(height: 24),
        ],

        const MedicalDisclaimer(variant: DisclaimerVariant.main),
      ],
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.diagnosis});
  final Diagnosis diagnosis;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(diagnosis.summaryMessageKo),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _StatBox(label: '부족', count: diagnosis.deficientCount, color: Colors.orange),
                _StatBox(label: '적정', count: diagnosis.adequateCount, color: Colors.green),
                if (diagnosis.riskyCount > 0)
                  _StatBox(label: '주의', count: diagnosis.riskyCount, color: Colors.red),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _StatBox extends StatelessWidget {
  const _StatBox({required this.label, required this.count, required this.color});
  final String label;
  final int count;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text('$count',
            style: TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.bold,
              color: color,
            )),
        Text(label),
      ],
    );
  }
}
```

### 5. 부족 영양소 카드 위젯

```dart
// lib/features/nutrition/presentation/widgets/deficient_nutrient_card.dart
import 'package:flutter/material.dart';

import '../../../../shared/models/api_models.dart';
import 'status_badge.dart';

class DeficientNutrientCard extends StatelessWidget {
  const DeficientNutrientCard({
    super.key,
    required this.diagnosis,
    required this.recommendedFoods,
  });

  final NutrientDiagnosis diagnosis;
  final List<String> recommendedFoods;

  @override
  Widget build(BuildContext context) {
    final ratio = (diagnosis.ratioPct / 100).clamp(0.0, 2.0);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    diagnosis.nameKo,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                StatusBadge(status: diagnosis.status),
              ],
            ),
            const SizedBox(height: 8),
            // 진행률 바
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: ratio.clamp(0.0, 1.0),
                minHeight: 8,
                color: _ratioColor(diagnosis.ratioPct),
                backgroundColor: Colors.grey.shade200,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '${diagnosis.intakeAmount.toStringAsFixed(1)} ${diagnosis.unit} '
              '/ 권장 ${diagnosis.referenceAmount?.toStringAsFixed(1)} ${diagnosis.unit} '
              '(${diagnosis.ratioPct.toStringAsFixed(0)}%)',
              style: const TextStyle(fontSize: 13),
            ),
            const SizedBox(height: 12),
            // 메시지
            Text(diagnosis.messageKo),
            // 권장 식품 (있을 때만)
            if (recommendedFoods.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Divider(),
              const SizedBox(height: 8),
              Text(
                '권장 식품',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 4),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: recommendedFoods.take(5).map((food) {
                  return Chip(
                    label: Text(food, style: const TextStyle(fontSize: 12)),
                    visualDensity: VisualDensity.compact,
                  );
                }).toList(),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Color _ratioColor(double pct) {
    if (pct < 35) return Colors.red;
    if (pct < 70) return Colors.orange;
    if (pct <= 130) return Colors.green;
    if (pct <= 200) return Colors.amber;
    return Colors.red.shade900;
  }
}
```

### 6. 상태 배지 + UL 경고 배너

```dart
// lib/features/nutrition/presentation/widgets/status_badge.dart
import 'package:flutter/material.dart';

class StatusBadge extends StatelessWidget {
  const StatusBadge({super.key, required this.status});
  final String status;

  @override
  Widget build(BuildContext context) {
    final config = _config(status);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: config.bgColor,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        config.label,
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.bold,
          color: config.textColor,
        ),
      ),
    );
  }

  ({String label, Color bgColor, Color textColor}) _config(String status) {
    return switch (status) {
      'deficient' => (label: '결핍', bgColor: Colors.red.shade100, textColor: Colors.red.shade900),
      'low' => (label: '부족', bgColor: Colors.orange.shade100, textColor: Colors.orange.shade900),
      'adequate' => (label: '적정', bgColor: Colors.green.shade100, textColor: Colors.green.shade900),
      'excessive' => (label: '과다', bgColor: Colors.amber.shade100, textColor: Colors.amber.shade900),
      'risky' => (label: '주의', bgColor: Colors.red.shade200, textColor: Colors.red.shade900),
      _ => (label: '?', bgColor: Colors.grey.shade100, textColor: Colors.grey.shade900),
    };
  }
}
```

```dart
// lib/features/nutrition/presentation/widgets/ul_warning_banner.dart
class ULWarningBanner extends StatelessWidget {
  const ULWarningBanner({super.key, required this.riskyNutrients});
  final List<NutrientDiagnosis> riskyNutrients;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: Colors.red.shade50,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            const Icon(Icons.warning_amber, color: Colors.red),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '상한 섭취량 초과 영양소',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: Colors.red.shade900,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    riskyNutrients.map((n) => n.nameKo).join(', '),
                    style: const TextStyle(fontSize: 13),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '전문가 상담을 권장합니다.',
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade700),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
```

---

## 🧪 테스트

### 위젯 테스트

```dart
testWidgets('DeficientNutrientCard shows correct ratio color', (tester) async {
  final diagnosis = NutrientDiagnosis(
    code: 'vitamin_d_ug',
    nameKo: '비타민 D',
    status: 'deficient',
    intakeAmount: 5,
    referenceAmount: 25,
    ratioPct: 20,
    unit: 'μg',
    messageKo: '부족합니다',
  );

  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: DeficientNutrientCard(
          diagnosis: diagnosis,
          recommendedFoods: const ['연어', '계란'],
        ),
      ),
    ),
  );

  expect(find.text('비타민 D'), findsOneWidget);
  expect(find.text('결핍'), findsOneWidget);  // status badge
  expect(find.text('연어'), findsOneWidget);
  expect(find.text('계란'), findsOneWidget);
});

testWidgets('UL warning banner shown for risky nutrients', (tester) async {
  // ... fake risky list
  expect(find.text('상한 섭취량 초과 영양소'), findsOneWidget);
  expect(find.text('전문가 상담을 권장합니다.'), findsOneWidget);
});

testWidgets('Adequate nutrients shown as chips', (tester) async {
  // ...
  expect(find.byType(Chip), findsNWidgets(8));
});

testWidgets('Pull to refresh invalidates provider', (tester) async {
  // ...
});
```

### Provider 테스트

```dart
test('DeficientAnalysisProvider fetches from repository', () async {
  final mockRepo = MockRepo();
  when(() => mockRepo.getLatestDiagnosis())
      .thenAnswer((_) async => fakeAnalysis);

  final container = ProviderContainer(
    overrides: [
      nutritionRepositoryProvider.overrideWithValue(mockRepo),
    ],
  );

  final result = await container.read(deficientAnalysisProvider.future);
  expect(result.diagnosis.diagnoses.length, greaterThan(0));
});
```

### 골든 테스트

```dart
testGoldens('Deficient nutrients screen golden', (tester) async {
  await loadAppFonts();
  final builder = DeviceBuilder()
    ..addScenario(
      widget: const ProviderScope(
        child: MaterialApp(home: DeficientNutrientsScreen()),
      ),
      name: 'with_deficient',
    );
  await tester.pumpDeviceBuilder(builder);
  await screenMatchesGolden(tester, 'deficient_screen');
});
```

---

## ✅ Definition of Done

- [ ] `DeficientAnalysis` Freezed 모델
- [ ] `NutritionRepository` (백엔드 호출)
- [ ] `deficientAnalysisProvider` (Riverpod)
- [ ] `DeficientNutrientsScreen` (메인)
- [ ] `DeficientNutrientCard` (개별 영양소)
- [ ] `StatusBadge` (5가지 상태 배지)
- [ ] `ULWarningBanner` (UL 초과 강조)
- [ ] Pull-to-refresh 동작
- [ ] **MedicalDisclaimer 화면 하단 필수**
- [ ] 위젯 테스트 (각 위젯 + 화면)
- [ ] Provider 테스트
- [ ] 골든 테스트
- [ ] 라우팅 등록 (`/nutrition/deficient`)
- [ ] `flutter analyze` + `flutter test` 통과

---

## 💡 구현 팁

### 정보 우선순위

```
1. UL 초과 (위험) — 최상단 빨간 배너
2. 부족·결핍 (관리 필요) — 큰 카드, 식품 권장 포함
3. 적정 (안심) — Chip 으로 압축
4. 과다 (주의) — 중간 강조
```

### 색상 체계

색상은 영양소별 일관성 유지:
- 적정: 초록
- 부족: 주황
- 결핍·위험: 빨강
- 과다: 노랑

---

## 🚫 이 작업에서 하지 말 것

- ❌ "이 영양제를 드세요" 표현 (식품·성분만)
- ❌ "X 질병 위험" 진단 표현
- ❌ 차트만 표시하고 설명 누락
- ❌ 면책 고지 누락 → PR 거절

---

## 🔗 관련 문서

- [`/mobile/CLAUDE.md`](../../mobile/CLAUDE.md)
- 이전: [`17-feedback-and-notifications.md`](./17-feedback-and-notifications.md)
- 다음: [`19-mobile-goal-analysis-screen.md`](./19-mobile-goal-analysis-screen.md)
