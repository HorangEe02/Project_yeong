# dev-guides/19 — 목적별 분석 화면 (5종 출력 ⑤)

> **Phase**: 3 | **선행 작업**: [`15-goal-based-analysis.md`](./15-goal-based-analysis.md), [`18-mobile-deficient-screen.md`](./18-mobile-deficient-screen.md) | **예상 소요**: 3~4시간

---

## 🎯 작업 목표

5종 출력의 마지막 ⑤ 목적별 분석 화면을 구현한다. 사용자가 "눈 건강", "피로 회복" 등 7가지 목적 중 선택하면 관련 핵심 영양소 분석과 식약처 인정 기능성 표시를 보여준다.

---

## 📋 산출물

```
mobile/
└── lib/features/goal_analysis/
    ├── data/goal_repository.dart
    ├── domain/goal_models.dart                # Freezed
    └── presentation/
        ├── screens/
        │   ├── goal_selection_screen.dart     # 7개 목적 선택
        │   └── goal_analysis_screen.dart      # 결과 화면
        ├── widgets/
        │   ├── goal_card.dart                 # 목적 카드
        │   ├── nutrient_function_card.dart    # 영양소 + 기능성 표시
        │   └── recommended_foods_section.dart
        └── providers/
            ├── goals_list_provider.dart
            └── goal_analysis_provider.dart
```

---

## 📐 화면 흐름

```
┌──────────────────────────────┐         ┌──────────────────────────────┐
│ 목적 선택                    │   →     │ 피로 회복 분석               │
│                              │         │                              │
│ 어떤 부분이                  │         │ [요약]                       │
│ 궁금하신가요?                │         │ 피로 회복과 관련된 영양소     │
│                              │         │ 4종 중 2종 부족              │
│ ┌──────────┬──────────┐      │         │                              │
│ │👁 눈 건강 │❤ 면역력  │      │         │ ┌───────────────────────┐  │
│ ├──────────┼──────────┤      │         │ │ 비타민 B1             │  │
│ │🫀혈행 개선│💪피로 회복│      │         │ │ ⚪⚪░░░ 30% (결핍)      │  │
│ ├──────────┼──────────┤      │         │ │ 식약처 인정 기능성:     │  │
│ │🦴뼈 건강 │🌿간 건강 │      │         │ │ "비타민 B1은 에너지     │  │
│ ├──────────┼──────────┤      │         │ │ 생산에 필요"            │  │
│ │🌾장 건강 │          │      │         │ └───────────────────────┘  │
│ └──────────┴──────────┘      │         │ ...                          │
│                              │         │                              │
│                              │         │ [권장 식품]                  │
│                              │         │ 현미, 통밀, 견과류           │
│                              │         │                              │
│                              │         │ [면책 고지 — main]            │
└──────────────────────────────┘         └──────────────────────────────┘
```

---

## 🔧 구현 명세

### 1. Freezed 모델

```dart
// lib/features/goal_analysis/domain/goal_models.dart
import 'package:freezed_annotation/freezed_annotation.dart';

part 'goal_models.freezed.dart';
part 'goal_models.g.dart';

@freezed
class HealthGoal with _$HealthGoal {
  const factory HealthGoal({
    required String code,
    required String nameKo,
    required String nameEn,
    required String descriptionKo,
    required List<GoalNutrient> coreNutrients,
    required List<String> foodRecommendationsKo,
  }) = _HealthGoal;

  factory HealthGoal.fromJson(Map<String, dynamic> json) =>
      _$HealthGoalFromJson(json);
}

@freezed
class GoalNutrient with _$GoalNutrient {
  const factory GoalNutrient({
    required String code,
    required double weight,
    required String mfdsFunctionKo,
  }) = _GoalNutrient;

  factory GoalNutrient.fromJson(Map<String, dynamic> json) =>
      _$GoalNutrientFromJson(json);
}

@freezed
class GoalAnalysis with _$GoalAnalysis {
  const factory GoalAnalysis({
    required HealthGoal goal,
    required List<GoalNutrientAnalysis> relatedNutrients,
    required int deficientCount,
    required int adequateCount,
    required String summaryMessageKo,
    required List<String> foodRecommendationsKo,
  }) = _GoalAnalysis;

  factory GoalAnalysis.fromJson(Map<String, dynamic> json) =>
      _$GoalAnalysisFromJson(json);
}

@freezed
class GoalNutrientAnalysis with _$GoalNutrientAnalysis {
  const factory GoalNutrientAnalysis({
    required NutrientDiagnosis diagnosis,
    required double weight,
    required String mfdsFunctionKo,
  }) = _GoalNutrientAnalysis;

  factory GoalNutrientAnalysis.fromJson(Map<String, dynamic> json) =>
      _$GoalNutrientAnalysisFromJson(json);
}
```

### 2. Repository

```dart
// lib/features/goal_analysis/data/goal_repository.dart
import 'package:dio/dio.dart';

class GoalRepository {
  GoalRepository(this._dio);
  final Dio _dio;

  /// 7개 목적 리스트 조회.
  Future<List<HealthGoal>> listGoals() async {
    final response = await _dio.get<List<dynamic>>('/api/v1/goals');
    return response.data!
        .map((json) => HealthGoal.fromJson(json as Map<String, dynamic>))
        .toList();
  }

  /// 특정 목적 분석.
  Future<GoalAnalysis> analyzeGoal(String goalCode) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/goals/$goalCode/analyze',
    );
    return GoalAnalysis.fromJson(response.data!);
  }
}
```

### 3. 목적 선택 화면

```dart
// lib/features/goal_analysis/presentation/screens/goal_selection_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../shared/widgets/disclaimer.dart';
import '../providers/goals_list_provider.dart';
import '../widgets/goal_card.dart';

class GoalSelectionScreen extends ConsumerWidget {
  const GoalSelectionScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncGoals = ref.watch(goalsListProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('목적별 분석')),
      body: asyncGoals.when(
        data: (goals) => ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              '어떤 부분이\n궁금하신가요?',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            const Text('관심 있는 건강 목적을 선택해주세요'),
            const SizedBox(height: 24),
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 1.1,
              ),
              itemCount: goals.length,
              itemBuilder: (_, i) => GoalCard(
                goal: goals[i],
                onTap: () => context.push('/goal-analysis/${goals[i].code}'),
              ),
            ),
            const SizedBox(height: 24),
            const MedicalDisclaimer(variant: DisclaimerVariant.main),
          ],
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('$e')),
      ),
    );
  }
}
```

### 4. 목적 카드 위젯

```dart
// lib/features/goal_analysis/presentation/widgets/goal_card.dart
import 'package:flutter/material.dart';

class GoalCard extends StatelessWidget {
  const GoalCard({super.key, required this.goal, required this.onTap});

  final HealthGoal goal;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final icon = _iconFor(goal.code);
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(icon, style: const TextStyle(fontSize: 36)),
              const SizedBox(height: 8),
              Text(
                goal.nameKo,
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 4),
              Text(
                goal.descriptionKo,
                style: const TextStyle(fontSize: 11),
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _iconFor(String code) {
    return switch (code) {
      'eye_health' => '👁',
      'liver_health' => '🌿',
      'fatigue_recovery' => '💪',
      'immunity' => '❤',
      'blood_circulation' => '🫀',
      'gut_health' => '🌾',
      'bone_health' => '🦴',
      _ => '🍋',
    };
  }
}
```

### 5. 분석 결과 화면

```dart
// lib/features/goal_analysis/presentation/screens/goal_analysis_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../shared/widgets/disclaimer.dart';
import '../providers/goal_analysis_provider.dart';
import '../widgets/nutrient_function_card.dart';
import '../widgets/recommended_foods_section.dart';

class GoalAnalysisScreen extends ConsumerWidget {
  const GoalAnalysisScreen({super.key, required this.goalCode});
  final String goalCode;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncAnalysis = ref.watch(goalAnalysisProvider(goalCode));

    return Scaffold(
      appBar: AppBar(title: const Text('분석 결과')),
      body: asyncAnalysis.when(
        data: (analysis) => RefreshIndicator(
          onRefresh: () async => ref.invalidate(goalAnalysisProvider(goalCode)),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _GoalHeader(goal: analysis.goal),
              const SizedBox(height: 16),
              _SummaryCard(analysis: analysis),
              const SizedBox(height: 24),
              Text(
                '관련 영양소 (${analysis.relatedNutrients.length})',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              ...analysis.relatedNutrients.map(
                (n) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: NutrientFunctionCard(analysis: n),
                ),
              ),
              const SizedBox(height: 16),
              RecommendedFoodsSection(foods: analysis.foodRecommendationsKo),
              const SizedBox(height: 32),
              const MedicalDisclaimer(variant: DisclaimerVariant.main),
            ],
          ),
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('$e')),
      ),
    );
  }
}

class _GoalHeader extends StatelessWidget {
  const _GoalHeader({required this.goal});
  final HealthGoal goal;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(_iconFor(goal.code), style: const TextStyle(fontSize: 48)),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(goal.nameKo, style: Theme.of(context).textTheme.headlineSmall),
              Text(goal.descriptionKo, style: const TextStyle(fontSize: 12)),
            ],
          ),
        ),
      ],
    );
  }

  String _iconFor(String code) {
    return switch (code) {
      'eye_health' => '👁',
      'fatigue_recovery' => '💪',
      _ => '🍋',
    };
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.analysis});
  final GoalAnalysis analysis;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: analysis.deficientCount > 0
          ? Colors.orange.shade50
          : Colors.green.shade50,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(
              analysis.deficientCount > 0
                  ? Icons.info_outline
                  : Icons.check_circle_outline,
              size: 32,
              color: analysis.deficientCount > 0
                  ? Colors.orange
                  : Colors.green,
            ),
            const SizedBox(width: 12),
            Expanded(child: Text(analysis.summaryMessageKo)),
          ],
        ),
      ),
    );
  }
}
```

### 6. 영양소 + 식약처 기능성 카드

```dart
// lib/features/goal_analysis/presentation/widgets/nutrient_function_card.dart
import 'package:flutter/material.dart';

import '../../domain/goal_models.dart';

/// 영양소 진단 + 식약처 인정 기능성 표시.
class NutrientFunctionCard extends StatelessWidget {
  const NutrientFunctionCard({super.key, required this.analysis});
  final GoalNutrientAnalysis analysis;

  @override
  Widget build(BuildContext context) {
    final d = analysis.diagnosis;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 영양소명 + 가중치 표시
            Row(
              children: [
                Expanded(
                  child: Text(
                    d.nameKo,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                if (analysis.weight >= 0.9)
                  const Chip(
                    label: Text('핵심', style: TextStyle(fontSize: 10)),
                    visualDensity: VisualDensity.compact,
                  ),
              ],
            ),
            const SizedBox(height: 8),
            // 진행률 바
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: (d.ratioPct / 100).clamp(0.0, 1.0),
                minHeight: 6,
                color: _color(d.ratioPct),
                backgroundColor: Colors.grey.shade200,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              '${d.ratioPct.toStringAsFixed(0)}% (${_label(d.status)})',
              style: TextStyle(fontSize: 11, color: Colors.grey.shade700),
            ),
            const SizedBox(height: 12),
            // 식약처 인정 기능성 표시
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.blue.shade50,
                borderRadius: BorderRadius.circular(6),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.verified_outlined, size: 16, color: Colors.blue),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      analysis.mfdsFunctionKo,
                      style: const TextStyle(fontSize: 12),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Color _color(double pct) {
    if (pct < 35) return Colors.red;
    if (pct < 70) return Colors.orange;
    if (pct <= 130) return Colors.green;
    return Colors.amber;
  }

  String _label(String status) {
    return switch (status) {
      'deficient' => '결핍',
      'low' => '부족',
      'adequate' => '적정',
      'excessive' => '과다',
      'risky' => '주의',
      _ => '?',
    };
  }
}
```

### 7. 권장 식품 섹션

```dart
// lib/features/goal_analysis/presentation/widgets/recommended_foods_section.dart
import 'package:flutter/material.dart';

class RecommendedFoodsSection extends StatelessWidget {
  const RecommendedFoodsSection({super.key, required this.foods});
  final List<String> foods;

  @override
  Widget build(BuildContext context) {
    if (foods.isEmpty) return const SizedBox.shrink();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.restaurant, color: Colors.orange),
                const SizedBox(width: 8),
                Text(
                  '권장 식품',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ],
            ),
            const SizedBox(height: 12),
            ...foods.map(
              (food) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    const Text('• '),
                    Expanded(child: Text(food, style: const TextStyle(fontSize: 14))),
                  ],
                ),
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
testWidgets('GoalCard shows icon and name', (tester) async {
  final goal = HealthGoal(
    code: 'fatigue_recovery',
    nameKo: '피로 회복',
    nameEn: 'Fatigue Recovery',
    descriptionKo: '에너지 대사를 위한 영양 관리',
    coreNutrients: const [],
    foodRecommendationsKo: const [],
  );

  await tester.pumpWidget(MaterialApp(
    home: Scaffold(body: GoalCard(goal: goal, onTap: () {})),
  ));

  expect(find.text('💪'), findsOneWidget);
  expect(find.text('피로 회복'), findsOneWidget);
});

testWidgets('NutrientFunctionCard shows MFDS function text', (tester) async {
  final analysis = GoalNutrientAnalysis(
    diagnosis: NutrientDiagnosis(...),
    weight: 1.0,
    mfdsFunctionKo: '비타민 B1은 에너지 생산에 필요',
  );

  await tester.pumpWidget(...);
  expect(find.textContaining('에너지 생산에 필요'), findsOneWidget);
  expect(find.text('핵심'), findsOneWidget);  // weight 1.0
});

testWidgets('Goal selection grid shows 7 cards', (tester) async {
  // ...
  expect(find.byType(GoalCard), findsNWidgets(7));
});

testWidgets('No diagnose word in MFDS text', (tester) async {
  // ... fake analysis with verified MFDS text
  // 의료법 표현 가이드 자동 검증
});
```

### 컴플라이언스 테스트

```dart
test('All goal data complies with medical regulations', () async {
  final repo = GoalRepository(...);
  final goals = await repo.listGoals();

  const forbidden = ['진단', '처방', '치료', '확실히', '완치'];
  for (final goal in goals) {
    for (final term in forbidden) {
      for (final n in goal.coreNutrients) {
        expect(n.mfdsFunctionKo.contains(term), isFalse,
            reason: '$term in ${goal.code}/${n.code}');
      }
    }
  }
});
```

---

## ✅ Definition of Done

- [ ] Freezed 모델 (HealthGoal, GoalNutrient, GoalAnalysis 등)
- [ ] `GoalRepository` (목록 + 분석)
- [ ] `goalsListProvider`, `goalAnalysisProvider`
- [ ] `GoalSelectionScreen` (7개 카드 그리드)
- [ ] `GoalAnalysisScreen` (요약 + 영양소 + 권장 식품)
- [ ] `GoalCard` (이모지 아이콘 + 설명)
- [ ] `NutrientFunctionCard` (진행률 + 식약처 기능성)
- [ ] `RecommendedFoodsSection`
- [ ] **모든 화면에 MedicalDisclaimer**
- [ ] 라우팅: `/goal-analysis` (선택), `/goal-analysis/:code` (결과)
- [ ] 위젯 테스트 (각 위젯)
- [ ] 컴플라이언스 테스트 (의료법 표현 자동 검증)
- [ ] 골든 테스트
- [ ] `flutter analyze` + `flutter test` 통과

---

## 💡 구현 팁

### 식약처 인정 기능성 표시 강조

```dart
// 일반 텍스트와 시각적으로 구분 (✓ 마크 + 파란 배경)
// → 사용자가 "공식 인정 정보" 라고 인식
```

### 라우팅 파라미터

```dart
// go_router 정의
GoRoute(
  path: '/goal-analysis',
  name: 'goal-selection',
  builder: (_, __) => const GoalSelectionScreen(),
  routes: [
    GoRoute(
      path: ':code',
      name: 'goal-analysis-result',
      builder: (_, state) => GoalAnalysisScreen(
        goalCode: state.pathParameters['code']!,
      ),
    ),
  ],
),
```

---

## 🚫 이 작업에서 하지 말 것

- ❌ 식약처 인정 외 효능 주장
- ❌ "이 영양제를 드시면..." 표현
- ❌ 질병 위험 진단 표현

---

## 🔗 관련 문서

- [`/mobile/CLAUDE.md`](../../mobile/CLAUDE.md)
- 이전: [`18-mobile-deficient-screen.md`](./18-mobile-deficient-screen.md)
- 다음: [`20-mobile-meal-input-screen.md`](./20-mobile-meal-input-screen.md)
