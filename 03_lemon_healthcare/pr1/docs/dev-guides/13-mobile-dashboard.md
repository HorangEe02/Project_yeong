# dev-guides/13 — 모바일 대시보드 (5종 출력)

> **Phase**: 2 | **선행 작업**: [`10-mobile-flutter-setup.md`](./10-mobile-flutter-setup.md), [`12-mobile-healthkit-integration.md`](./12-mobile-healthkit-integration.md) | **예상 소요**: 4~5시간

---

## 🎯 작업 목표

5종 출력 중 Phase 2 범위인 ② 권장 섭취량, ③ 체중 변화 예측, ④ 운동 권고 화면 3개를 구현한다. fl_chart로 시각화, 면책 고지 의무 배치.

> Phase 3에서 ① 부족 영양소 결과 + ⑤ 목적별 분석 화면 추가.

---

## 📋 산출물

```
mobile/
├── lib/features/
│   ├── nutrition/
│   │   └── presentation/screens/nutrition_dashboard_screen.dart
│   ├── prediction/
│   │   └── presentation/screens/weight_prediction_screen.dart
│   ├── activity/
│   │   └── presentation/screens/activity_recommendation_screen.dart
│   └── home/
│       └── presentation/screens/dashboard_home_screen.dart  # 통합 진입점
└── test/
    ├── widget/
    │   ├── nutrition_dashboard_test.dart
    │   ├── weight_prediction_test.dart
    │   └── activity_recommendation_test.dart
    └── integration_test/
        └── dashboard_e2e_test.dart
```

---

## 📐 화면 구성

### 통합 홈 (Dashboard Home)

```
┌──────────────────────────────┐
│ 🍋 레몬헬스케어               │
├──────────────────────────────┤
│ 안녕하세요, 김건강님          │
│                              │
│ ┌────────────────────────┐   │
│ │ 오늘의 활동점수: 87     │   │
│ │ ████████░░             │   │
│ └────────────────────────┘   │
│                              │
│ [영양 분석] [체중 예측]       │
│ [운동 권고] [영양제 등록]     │
│                              │
│ [면책 고지]                   │
└──────────────────────────────┘
```

### ② 권장 섭취량 (Nutrition Dashboard)

```
┌──────────────────────────────┐
│ 권장 섭취량 분석              │
├──────────────────────────────┤
│ 부족 영양소 3종, 적정 12종     │
│                              │
│ [막대 차트]                   │
│ 비타민 D ▓▓░░░░░░░ 30%        │
│ 칼슘     ▓▓▓▓▓▓░░░ 65%        │
│ 철분     ▓▓▓▓▓▓▓▓▓ 95%        │
│ 비타민 C ▓▓▓▓▓▓▓▓▓▓▓ 200% ⚠   │
│                              │
│ [상세 보기 ▼]                  │
│  ↓                          │
│ 비타민 D 섭취량이 권장량의...  │
│                              │
│ [면책 고지]                   │
└──────────────────────────────┘
```

### ③ 체중 변화 예측 (Weight Prediction)

```
┌──────────────────────────────┐
│ 체중 변화 예측                │
├──────────────────────────────┤
│ 현재: 68.0 kg                 │
│                              │
│ ┌──────┬──────┬──────┐        │
│ │1주 후 │1개월 │3개월 │        │
│ │67.8  │67.2  │66.0  │        │
│ │-0.2  │-0.8  │-2.0  │        │
│ └──────┴──────┴──────┘        │
│                              │
│ [라인 차트]                   │
│   현재    1주    1개월   3개월 │
│  68.0 → 67.8 → 67.2 → 66.0   │
│                              │
│ [면책 고지 — weightPrediction] │
└──────────────────────────────┘
```

### ④ 운동 권고 (Activity Recommendation)

```
┌──────────────────────────────┐
│ 운동 권고                     │
├──────────────────────────────┤
│ 권장 걸음수                   │
│ 7,524 보 / 일                 │
│                              │
│ 오늘 걸음수: 6,432 (85%)       │
│ ████████░░                    │
│                              │
│ 활동점수                      │
│ ┌─v1─┬─v2─┬─v3─┬─v4─┐        │
│ │77.5│69.7│72.7│87.2│        │
│ └────┴────┴────┴────┘        │
│                              │
│ [면책 고지]                   │
└──────────────────────────────┘
```

---

## 🔧 구현 명세

### 1. `lib/features/home/presentation/screens/dashboard_home_screen.dart`

```dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../shared/widgets/disclaimer.dart';

class DashboardHomeScreen extends StatelessWidget {
  const DashboardHomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('레몬헬스케어')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _GreetingCard(name: '김건강'),
          const SizedBox(height: 16),
          _ActivitySummaryCard(),
          const SizedBox(height: 24),
          _MenuGrid(context: context),
          const SizedBox(height: 32),
          const MedicalDisclaimer(variant: DisclaimerVariant.main),
        ],
      ),
    );
  }
}

class _MenuGrid extends StatelessWidget {
  const _MenuGrid({required this.context});
  final BuildContext context;

  @override
  Widget build(BuildContext _) {
    final items = [
      _MenuItem('영양 분석', Icons.restaurant, '/nutrition'),
      _MenuItem('체중 예측', Icons.monitor_weight, '/prediction'),
      _MenuItem('운동 권고', Icons.directions_walk, '/activity'),
      _MenuItem('영양제 등록', Icons.medication, '/supplement'),
    ];

    return GridView.count(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 1.2,
      children: items.map((item) {
        return Card(
          child: InkWell(
            onTap: () => context.push(item.route),
            borderRadius: BorderRadius.circular(12),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(item.icon, size: 36),
                  const SizedBox(height: 8),
                  Text(item.label, style: const TextStyle(fontSize: 14)),
                ],
              ),
            ),
          ),
        );
      }).toList(),
    );
  }
}

class _MenuItem {
  const _MenuItem(this.label, this.icon, this.route);
  final String label;
  final IconData icon;
  final String route;
}
```

### 2. `lib/features/nutrition/presentation/screens/nutrition_dashboard_screen.dart`

```dart
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../shared/widgets/app_error.dart';
import '../../../../shared/widgets/app_loading.dart';
import '../../../../shared/widgets/disclaimer.dart';
import '../../../supplement/domain/supplement_models.dart';
import '../providers/nutrition_provider.dart';

/// 권장 섭취량 분석 대시보드.
class NutritionDashboardScreen extends ConsumerWidget {
  const NutritionDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncDiagnosis = ref.watch(latestDiagnosisProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('영양 분석')),
      body: asyncDiagnosis.when(
        data: (diagnosis) => _Content(diagnosis: diagnosis),
        loading: () => const AppLoading(message: '분석 결과 불러오는 중...'),
        error: (e, _) => AppError(
          message: e.toString(),
          onRetry: () => ref.invalidate(latestDiagnosisProvider),
        ),
      ),
    );
  }
}

class _Content extends StatelessWidget {
  const _Content({required this.diagnosis});
  final Diagnosis diagnosis;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _SummaryCard(diagnosis: diagnosis),
        const SizedBox(height: 24),
        _NutrientBarChart(diagnoses: diagnosis.diagnoses),
        const SizedBox(height: 24),
        _DiagnosisList(diagnoses: diagnosis.diagnoses),
        const SizedBox(height: 32),
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
            Text('전체 요약', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(diagnosis.summaryMessageKo),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _StatChip(
                  label: '부족',
                  count: diagnosis.deficientCount,
                  color: Colors.orange,
                ),
                _StatChip(
                  label: '적정',
                  count: diagnosis.adequateCount,
                  color: Colors.green,
                ),
                if (diagnosis.riskyCount > 0)
                  _StatChip(
                    label: '주의',
                    count: diagnosis.riskyCount,
                    color: Colors.red,
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _StatChip extends StatelessWidget {
  const _StatChip({
    required this.label,
    required this.count,
    required this.color,
  });

  final String label;
  final int count;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          '$count',
          style: TextStyle(
            fontSize: 32,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        Text(label),
      ],
    );
  }
}

/// 영양소별 막대 차트.
class _NutrientBarChart extends StatelessWidget {
  const _NutrientBarChart({required this.diagnoses});
  final List<NutrientDiagnosis> diagnoses;

  @override
  Widget build(BuildContext context) {
    if (diagnoses.isEmpty) {
      return const SizedBox.shrink();
    }
    // 상위 8개만 표시
    final items = diagnoses.take(8).toList();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '권장량 대비 섭취량',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 16),
            SizedBox(
              height: 220,
              child: BarChart(
                BarChartData(
                  alignment: BarChartAlignment.spaceAround,
                  maxY: 200,  // 200% 까지 표시
                  barGroups: List.generate(items.length, (i) {
                    final ratio = items[i].ratioPct.clamp(0, 200);
                    return BarChartGroupData(
                      x: i,
                      barRods: [
                        BarChartRodData(
                          toY: ratio.toDouble(),
                          color: _statusColor(items[i].status),
                          width: 20,
                          borderRadius: const BorderRadius.vertical(
                            top: Radius.circular(4),
                          ),
                        ),
                      ],
                    );
                  }),
                  titlesData: FlTitlesData(
                    leftTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 32,
                        getTitlesWidget: (v, _) => Text('${v.toInt()}%'),
                      ),
                    ),
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 60,
                        getTitlesWidget: (v, _) {
                          final i = v.toInt();
                          if (i >= items.length) return const SizedBox.shrink();
                          return Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Text(
                              items[i].nameKo,
                              style: const TextStyle(fontSize: 10),
                              textAlign: TextAlign.center,
                            ),
                          );
                        },
                      ),
                    ),
                    rightTitles: const AxisTitles(),
                    topTitles: const AxisTitles(),
                  ),
                  // 70%, 130% 기준선
                  extraLinesData: ExtraLinesData(
                    horizontalLines: [
                      HorizontalLine(y: 70, color: Colors.green, dashArray: [5, 5]),
                      HorizontalLine(y: 130, color: Colors.orange, dashArray: [5, 5]),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Color _statusColor(String status) {
    return switch (status) {
      'deficient' => Colors.red,
      'low' => Colors.orange,
      'adequate' => Colors.green,
      'excessive' => Colors.amber,
      'risky' => Colors.red.shade900,
      _ => Colors.grey,
    };
  }
}

/// 영양소별 상세 메시지 리스트.
class _DiagnosisList extends StatelessWidget {
  const _DiagnosisList({required this.diagnoses});
  final List<NutrientDiagnosis> diagnoses;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('상세 분석', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            ...diagnoses.map(
              (d) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          d.nameKo,
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(width: 8),
                        Text('${d.ratioPct.toStringAsFixed(0)}%'),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(d.messageKo, style: const TextStyle(fontSize: 14)),
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

### 3. `lib/features/prediction/presentation/screens/weight_prediction_screen.dart`

```dart
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../shared/widgets/app_loading.dart';
import '../../../../shared/widgets/disclaimer.dart';
import '../providers/prediction_provider.dart';

/// 체중 변화 예측 화면.
class WeightPredictionScreen extends ConsumerWidget {
  const WeightPredictionScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncPrediction = ref.watch(weightPredictionProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('체중 변화 예측')),
      body: asyncPrediction.when(
        data: (pred) => ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _StartingWeightCard(weight: pred.startingWeight),
            const SizedBox(height: 16),
            _PeriodCards(prediction: pred),
            const SizedBox(height: 24),
            _LineChart(prediction: pred),
            const SizedBox(height: 32),
            const MedicalDisclaimer(
              variant: DisclaimerVariant.weightPrediction,
            ),
          ],
        ),
        loading: () => const AppLoading(),
        error: (e, _) => Center(child: Text('$e')),
      ),
    );
  }
}

class _PeriodCards extends StatelessWidget {
  const _PeriodCards({required this.prediction});
  final WeightPrediction prediction;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _PeriodCard(
            label: '1주 후',
            weight: prediction.week1.predictedWeight,
            change: prediction.week1.correctedChange,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _PeriodCard(
            label: '1개월 후',
            weight: prediction.month1.predictedWeight,
            change: prediction.month1.correctedChange,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _PeriodCard(
            label: '3개월 후',
            weight: prediction.month3.predictedWeight,
            change: prediction.month3.correctedChange,
          ),
        ),
      ],
    );
  }
}

class _PeriodCard extends StatelessWidget {
  const _PeriodCard({
    required this.label,
    required this.weight,
    required this.change,
  });

  final String label;
  final double weight;
  final double change;

  @override
  Widget build(BuildContext context) {
    final isLoss = change < 0;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            Text(label, style: const TextStyle(fontSize: 12)),
            const SizedBox(height: 4),
            Text(
              '${weight.toStringAsFixed(1)}',
              style: const TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
            ),
            const Text('kg', style: TextStyle(fontSize: 12)),
            const SizedBox(height: 4),
            Text(
              '${change > 0 ? "+" : ""}${change.toStringAsFixed(1)}',
              style: TextStyle(
                fontSize: 12,
                color: isLoss ? Colors.green : Colors.orange,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LineChart extends StatelessWidget {
  const _LineChart({required this.prediction});
  final WeightPrediction prediction;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '체중 변화 추이',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 16),
            SizedBox(
              height: 220,
              child: LineChart(
                LineChartData(
                  lineBarsData: [
                    LineChartBarData(
                      spots: [
                        FlSpot(0, prediction.startingWeight),
                        FlSpot(7, prediction.week1.predictedWeight),
                        FlSpot(30, prediction.month1.predictedWeight),
                        FlSpot(90, prediction.month3.predictedWeight),
                      ],
                      isCurved: true,
                      color: Theme.of(context).colorScheme.primary,
                      barWidth: 3,
                      dotData: const FlDotData(show: true),
                    ),
                  ],
                  titlesData: FlTitlesData(
                    leftTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 40,
                        getTitlesWidget: (v, _) =>
                            Text('${v.toInt()}', style: const TextStyle(fontSize: 10)),
                      ),
                    ),
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        getTitlesWidget: (v, _) {
                          final labels = {0: '현재', 7: '1주', 30: '1개월', 90: '3개월'};
                          return Text(labels[v.toInt()] ?? '');
                        },
                      ),
                    ),
                    rightTitles: const AxisTitles(),
                    topTitles: const AxisTitles(),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StartingWeightCard extends StatelessWidget {
  const _StartingWeightCard({required this.weight});
  final double weight;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            const Icon(Icons.monitor_weight, size: 32),
            const SizedBox(width: 16),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('현재 체중'),
                Text(
                  '${weight.toStringAsFixed(1)} kg',
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
```

### 4. `lib/features/activity/presentation/screens/activity_recommendation_screen.dart`

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../shared/widgets/disclaimer.dart';
import '../providers/activity_provider.dart';

class ActivityRecommendationScreen extends ConsumerWidget {
  const ActivityRecommendationScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncActivity = ref.watch(activityScoreProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('운동 권고')),
      body: asyncActivity.when(
        data: (data) => ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _StepGoalCard(
              recommended: data.recommendedSteps,
              actual: data.actualSteps,
            ),
            const SizedBox(height: 24),
            _ScoreGrid(
              v1: data.v1Score,
              v2: data.v2Score,
              v3: data.v3Score,
              v4: data.v4Score,
            ),
            const SizedBox(height: 32),
            const MedicalDisclaimer(variant: DisclaimerVariant.main),
          ],
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('$e')),
      ),
    );
  }
}

class _StepGoalCard extends StatelessWidget {
  const _StepGoalCard({required this.recommended, required this.actual});

  final int recommended;
  final int actual;

  @override
  Widget build(BuildContext context) {
    final progress = recommended > 0 ? (actual / recommended).clamp(0.0, 1.5) : 0.0;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('권장 걸음수', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 4),
            Text(
              '$recommended 보 / 일',
              style: const TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 16),
            Text('오늘 걸음수: $actual (${(progress * 100).toInt()}%)'),
            const SizedBox(height: 8),
            LinearProgressIndicator(
              value: progress.clamp(0.0, 1.0),
              minHeight: 12,
              borderRadius: BorderRadius.circular(6),
            ),
          ],
        ),
      ),
    );
  }
}

class _ScoreGrid extends StatelessWidget {
  const _ScoreGrid({
    required this.v1,
    required this.v2,
    required this.v3,
    required this.v4,
  });

  final double v1;
  final double v2;
  final double v3;
  final double v4;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('활동점수', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(child: _ScoreTile(label: 'v1 (기본)', value: v1)),
                Expanded(child: _ScoreTile(label: 'v2 (심박)', value: v2)),
                Expanded(child: _ScoreTile(label: 'v3 (백분위)', value: v3)),
                Expanded(child: _ScoreTile(label: 'v4 (만성)', value: v4)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ScoreTile extends StatelessWidget {
  const _ScoreTile({required this.label, required this.value});

  final String label;
  final double value;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(label, style: const TextStyle(fontSize: 11)),
        const SizedBox(height: 4),
        Text(
          value.toStringAsFixed(1),
          style: const TextStyle(
            fontSize: 22,
            fontWeight: FontWeight.bold,
          ),
        ),
      ],
    );
  }
}
```

---

## 🧪 테스트

### 위젯 테스트

```dart
testWidgets('NutritionDashboard shows summary card', (tester) async {
  final fakeDiagnosis = Diagnosis(
    diagnoses: [],
    deficientCount: 2,
    riskyCount: 0,
    adequateCount: 8,
    summaryMessageKo: '분석한 영양소 10종 중 부족 2종, 적정 8종',
  );

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        latestDiagnosisProvider.overrideWith((ref) => Future.value(fakeDiagnosis)),
      ],
      child: const MaterialApp(home: NutritionDashboardScreen()),
    ),
  );
  await tester.pumpAndSettle();

  expect(find.text('영양 분석'), findsOneWidget);
  expect(find.text('전체 요약'), findsOneWidget);
  expect(find.text('2'), findsOneWidget);  // deficient count
  expect(find.byType(MedicalDisclaimer), findsOneWidget);
});

testWidgets('Weight prediction shows 3 period cards', (tester) async {
  // ... fake prediction
  // expect(find.text('1주 후'), findsOneWidget);
  // expect(find.text('1개월 후'), findsOneWidget);
  // expect(find.text('3개월 후'), findsOneWidget);
});

testWidgets('Activity screen shows step goal and 4 scores', (tester) async {
  // ...
});
```

### 골든 테스트

```dart
testGoldens('Dashboard screens match golden', (tester) async {
  await loadAppFonts();
  // 3개 화면 골든 캡처
});
```

### E2E 테스트 (Patrol)

```dart
patrolTest('대시보드 전체 흐름', (PatrolTester $) async {
  await $.pumpWidget(const ProviderScope(child: LemonHealthcareApp()));

  // 홈 → 영양 분석
  await $('영양 분석').tap();
  await $('전체 요약').waitUntilVisible();

  // 뒤로 → 체중 예측
  await $.native.pressBack();
  await $('체중 예측').tap();
  await $('1주 후').waitUntilVisible();
  await $('1개월 후').waitUntilVisible();
  await $('3개월 후').waitUntilVisible();

  // 체중 예측 면책 고지 검증 (다른 variant)
  await $.native.scrollDown();
  await $('급격한 체중 변화').waitUntilVisible();

  // 운동 권고
  await $.native.pressBack();
  await $('운동 권고').tap();
  await $('권장 걸음수').waitUntilVisible();
  await $('활동점수').waitUntilVisible();
});
```

---

## ✅ Definition of Done

- [ ] DashboardHomeScreen — 4개 메뉴 카드 + 활동 요약
- [ ] NutritionDashboardScreen — 요약 카드 + 막대 차트 + 상세 리스트
- [ ] WeightPredictionScreen — 시작 체중 + 3 기간 카드 + 라인 차트
- [ ] ActivityRecommendationScreen — 권장 걸음수 진행률 + 4개 점수
- [ ] **모든 화면에 MedicalDisclaimer 위젯 배치 (최하단)**
- [ ] 체중 예측 화면은 `weightPrediction` variant 사용
- [ ] fl_chart 사용 (BarChart, LineChart)
- [ ] 70% / 130% 기준선 표시 (영양 차트)
- [ ] 위젯 테스트 (각 화면 최소 3개 테스트)
- [ ] 골든 테스트 (시각 회귀)
- [ ] (선택) Patrol E2E 테스트
- [ ] iOS + Android 양쪽에서 정상 표시
- [ ] `flutter analyze` + `flutter test` 통과

---

## 💡 구현 팁

### fl_chart 색상

```dart
// 상태별 색상 일관성 유지
Color _statusColor(String status) {
  return switch (status) {
    'deficient' => Colors.red.shade400,
    'low' => Colors.orange,
    'adequate' => Colors.green,
    'excessive' => Colors.amber,
    'risky' => Colors.red.shade900,
    _ => Colors.grey,
  };
}
```

### 차트 데이터 포인트가 적을 때

3-4개 포인트만 있는 라인 차트는 `LineChart.curve` 활용하면 자연스러움. 또는 `BarChart` 가 더 적합할 수도.

### 면책 고지 변형 사용 규칙

| 화면 | variant |
|------|--------|
| 홈, 운동 권고, 영양 분석 | `main` |
| 체중 예측 | `weightPrediction` (특별 주의 문구) |
| 영양제 등록 결과 | `supplement` |

---

## 🚫 이 작업에서 하지 말 것

- ❌ ① 부족 영양소 결과 + ⑤ 목적별 분석 화면 (Phase 3)
- ❌ 차트 인터랙션 (탭 시 상세, Phase 3)
- ❌ 데이터 새로고침 / pull-to-refresh (Phase 3)
- ❌ 알림 통합 (Phase 4)

---

## 🎉 Phase 2 완료!

이 가이드 완료 시점에 Phase 2의 핵심 산출물이 모두 동작합니다:

```
✅ 백엔드: 영양제 사진 → OCR → LLM → 매칭 → 진단 (E2E)
✅ 모바일: 카메라 촬영 → 업로드 → 결과 표시
✅ 모바일: HealthKit/Health Connect 자동 데이터 수집
✅ 모바일: 5종 출력 중 3종 (영양·체중·운동) 화면 동작
```

Phase 3 (W8-W9) 에서는 Hall 모델 적용, 5종 출력 완성, 사용자 피드백 통합 진행.

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md)
- [`/mobile/CLAUDE.md`](../../mobile/CLAUDE.md)
- [`/docs/07-core-algorithm.md`](../07-core-algorithm.md) — 산출식 출력 명세
- [`/docs/10-compliance-checklist.md §2.3`](../10-compliance-checklist.md) — 면책 고지
- 이전: [`12-mobile-healthkit-integration.md`](./12-mobile-healthkit-integration.md)
- **Phase 3 시작**: 추후 작성 예정
