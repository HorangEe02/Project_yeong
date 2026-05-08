# dev-guides/12 — HealthKit + Health Connect 연동

> **Phase**: 2 | **선행 작업**: [`10-mobile-flutter-setup.md`](./10-mobile-flutter-setup.md) | **예상 소요**: 4~5시간

---

## 🎯 작업 목표

iOS HealthKit과 Android Health Connect를 통해 걸음수·심박수·체중 데이터를 자동 수집하는 모듈을 구현한다. 별도 동의 UI, 권한 요청, 백그라운드 동기화, 폴백(수동 입력) 모두 포함.

---

## 📋 산출물

```
mobile/
├── lib/features/health/
│   ├── data/
│   │   ├── health_repository.dart        # health 패키지 래퍼
│   │   └── health_sync_service.dart      # 백엔드 동기화
│   ├── domain/
│   │   ├── health_data.dart              # Freezed 모델
│   │   └── health_consent.dart           # 동의 상태 모델
│   └── presentation/
│       ├── screens/
│       │   ├── health_consent_screen.dart   # 별도 동의 UI
│       │   └── health_dashboard_screen.dart # 데이터 확인
│       ├── widgets/
│       │   ├── consent_card.dart
│       │   ├── permission_status.dart
│       │   └── manual_input_dialog.dart  # 폴백
│       └── providers/
│           ├── health_provider.dart
│           └── health_consent_provider.dart
├── ios/Runner/
│   ├── Info.plist                        # ⭐ HealthKit 권한
│   └── Runner.entitlements              # ⭐ HealthKit Capability
└── android/app/src/main/
    └── AndroidManifest.xml              # ⭐ Health Connect 권한
```

---

## 📐 데이터 흐름

```
┌─────────────────────────────────────┐
│ 1단계: 별도 동의 UI                   │
│ (앱 첫 실행 또는 헬스 메뉴 진입 시)    │
│                                     │
│ - 수집 데이터 명시 (걸음수·심박·체중)  │
│ - 사용 목적 (활동점수·체중 예측)       │
│ - 동의 / 거부                        │
└─────────────────────────────────────┘
            │ 동의
            ▼
┌─────────────────────────────────────┐
│ 2단계: OS 권한 요청                  │
│                                     │
│ iOS: HealthKit 권한 다이얼로그        │
│ Android: Health Connect 권한 화면    │
└─────────────────────────────────────┘
            │ 허락
            ▼
┌─────────────────────────────────────┐
│ 3단계: 데이터 읽기                    │
│                                     │
│ - 최근 30일 걸음수                    │
│ - 최근 7일 심박수 (평균)              │
│ - 최근 측정 체중                      │
└─────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────┐
│ 4단계: 백엔드 동기화                  │
│                                     │
│ POST /api/v1/health/sync             │
│ - 가명처리된 데이터만 전송             │
└─────────────────────────────────────┘
            │
            ▼
   (실패 폴백) 수동 입력 다이얼로그
```

---

## 🔧 구현 명세

### 1. iOS 권한 (`ios/Runner/Info.plist`)

```xml
<key>NSHealthShareUsageDescription</key>
<string>활동점수 산출과 체중 변화 예측을 위해 걸음수, 심박수, 체중 데이터를 읽습니다. 모든 데이터는 사용자 동의 하에 가명 처리되어 분석에만 사용되며, 제3자에게 제공되지 않습니다.</string>

<key>NSHealthUpdateUsageDescription</key>
<string>(선택) 활동점수 결과를 건강 앱에 기록합니다.</string>
```

### 2. iOS Capability (`ios/Runner/Runner.entitlements`)

```xml
<plist version="1.0">
<dict>
  <key>com.apple.developer.healthkit</key>
  <true/>
  <key>com.apple.developer.healthkit.access</key>
  <array/>
</dict>
</plist>
```

> ⚠️ Xcode → Signing & Capabilities → "+ Capability" → HealthKit 추가도 필수.

### 3. Android (`android/app/src/main/AndroidManifest.xml`)

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

  <!-- Health Connect 권한 -->
  <uses-permission android:name="android.permission.health.READ_STEPS" />
  <uses-permission android:name="android.permission.health.READ_HEART_RATE" />
  <uses-permission android:name="android.permission.health.READ_WEIGHT" />

  <!-- 백그라운드 (선택) -->
  <uses-permission
    android:name="android.permission.health.READ_HEALTH_DATA_IN_BACKGROUND" />

  <queries>
    <!-- Health Connect 앱 존재 여부 확인 -->
    <package android:name="com.google.android.apps.healthdata" />
  </queries>

  <application ...>
    <!-- Health Connect 권한 사용 목적 액티비티 -->
    <activity-alias
      android:name="ViewPermissionUsageActivity"
      android:exported="true"
      android:targetActivity=".MainActivity"
      android:permission="android.permission.START_VIEW_PERMISSION_USAGE">
      <intent-filter>
        <action android:name="android.intent.action.VIEW_PERMISSION_USAGE" />
        <category android:name="android.intent.category.HEALTH_PERMISSIONS" />
      </intent-filter>
    </activity-alias>
  </application>
</manifest>
```

### 4. `lib/features/health/domain/health_data.dart`

```dart
import 'package:freezed_annotation/freezed_annotation.dart';

part 'health_data.freezed.dart';
part 'health_data.g.dart';

@freezed
class DailySteps with _$DailySteps {
  const factory DailySteps({
    required DateTime date,
    required int steps,
  }) = _DailySteps;

  factory DailySteps.fromJson(Map<String, dynamic> json) =>
      _$DailyStepsFromJson(json);
}

@freezed
class HeartRateSummary with _$HeartRateSummary {
  const factory HeartRateSummary({
    required DateTime date,
    required double avgBpm,
    required int targetZoneMinutes,  // 목표심박 구간 유지 시간
  }) = _HeartRateSummary;

  factory HeartRateSummary.fromJson(Map<String, dynamic> json) =>
      _$HeartRateSummaryFromJson(json);
}

@freezed
class WeightRecord with _$WeightRecord {
  const factory WeightRecord({
    required DateTime measuredAt,
    required double weightKg,
  }) = _WeightRecord;

  factory WeightRecord.fromJson(Map<String, dynamic> json) =>
      _$WeightRecordFromJson(json);
}

@freezed
class HealthSyncData with _$HealthSyncData {
  const factory HealthSyncData({
    required List<DailySteps> steps,
    required List<HeartRateSummary> heartRate,
    required List<WeightRecord> weights,
  }) = _HealthSyncData;

  factory HealthSyncData.fromJson(Map<String, dynamic> json) =>
      _$HealthSyncDataFromJson(json);
}
```

### 5. `lib/features/health/data/health_repository.dart`

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:health/health.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../core/utils/logger.dart';
import '../domain/health_data.dart';

part 'health_repository.g.dart';


/// HealthKit/Health Connect 통합 Repository.
class HealthRepository {
  HealthRepository({Health? health}) : _health = health ?? Health();

  final Health _health;

  /// 수집 대상 데이터 종류.
  static const _types = [
    HealthDataType.STEPS,
    HealthDataType.HEART_RATE,
    HealthDataType.WEIGHT,
  ];

  /// 권한 요청.
  ///
  /// Returns: 모든 타입에 대한 읽기 권한이 허락되면 true.
  Future<bool> requestPermissions() async {
    await Health().configure();
    final permissions = _types.map((_) => HealthDataAccess.READ).toList();
    final granted = await _health.requestAuthorization(
      _types,
      permissions: permissions,
    );
    appLogger.i('Health permissions granted: $granted');
    return granted;
  }

  /// 권한 상태 확인.
  Future<bool> hasPermissions() async {
    final granted = await _health.hasPermissions(_types);
    return granted ?? false;
  }

  /// 최근 N일 걸음수 조회.
  Future<List<DailySteps>> getDailySteps({int days = 30}) async {
    final now = DateTime.now();
    final start = now.subtract(Duration(days: days));

    final result = <DailySteps>[];
    for (var d = 0; d < days; d++) {
      final dayStart = DateTime(start.year, start.month, start.day + d);
      final dayEnd = dayStart.add(const Duration(days: 1));

      final steps = await _health.getTotalStepsInInterval(dayStart, dayEnd);
      result.add(DailySteps(
        date: dayStart,
        steps: steps ?? 0,
      ));
    }
    return result;
  }

  /// 최근 N일 심박수 요약.
  Future<List<HeartRateSummary>> getHeartRateSummary({int days = 7}) async {
    final now = DateTime.now();
    final start = now.subtract(Duration(days: days));

    final raw = await _health.getHealthDataFromTypes(
      types: [HealthDataType.HEART_RATE],
      startTime: start,
      endTime: now,
    );

    // 일별 그룹핑
    final grouped = <DateTime, List<HealthDataPoint>>{};
    for (final point in raw) {
      final day = DateTime(
        point.dateFrom.year,
        point.dateFrom.month,
        point.dateFrom.day,
      );
      grouped.putIfAbsent(day, () => []).add(point);
    }

    final result = <HeartRateSummary>[];
    grouped.forEach((day, points) {
      final values = points
          .map((p) => (p.value as NumericHealthValue).numericValue.toDouble())
          .toList();
      final avg = values.isEmpty
          ? 0.0
          : values.reduce((a, b) => a + b) / values.length;

      // 목표 심박 구간 (220 - age × 0.5~0.7) 유지 시간 계산
      // 간단히: avg가 60% 부근이면 30분, 아니면 비례 계산
      // 실제로는 더 정교한 분석 필요 (Phase 3)
      final targetMinutes = avg > 80 && avg < 140 ? 30 : 0;

      result.add(HeartRateSummary(
        date: day,
        avgBpm: avg,
        targetZoneMinutes: targetMinutes,
      ));
    });

    return result;
  }

  /// 최근 체중 기록.
  Future<List<WeightRecord>> getWeightRecords({int days = 30}) async {
    final now = DateTime.now();
    final start = now.subtract(Duration(days: days));

    final raw = await _health.getHealthDataFromTypes(
      types: [HealthDataType.WEIGHT],
      startTime: start,
      endTime: now,
    );

    return raw.map((p) => WeightRecord(
          measuredAt: p.dateFrom,
          weightKg: (p.value as NumericHealthValue).numericValue.toDouble(),
        )).toList();
  }

  /// 전체 데이터 일괄 수집.
  Future<HealthSyncData> getAllData() async {
    final results = await Future.wait([
      getDailySteps(days: 30),
      getHeartRateSummary(days: 7),
      getWeightRecords(days: 30),
    ]);
    return HealthSyncData(
      steps: results[0] as List<DailySteps>,
      heartRate: results[1] as List<HeartRateSummary>,
      weights: results[2] as List<WeightRecord>,
    );
  }
}

@riverpod
HealthRepository healthRepository(HealthRepositoryRef ref) {
  return HealthRepository();
}
```

### 6. `lib/features/health/presentation/providers/health_consent_provider.dart`

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../../core/storage/secure_storage.dart';

part 'health_consent_provider.g.dart';

/// 별도 동의 상태.
@riverpod
class HealthConsent extends _$HealthConsent {
  static const _key = 'health_consent_granted';

  @override
  Future<bool> build() async {
    final storage = ref.read(secureStorageProvider);
    final value = await storage.read(_key);
    return value == 'true';
  }

  /// 동의 부여.
  Future<void> grant() async {
    final storage = ref.read(secureStorageProvider);
    await storage.write(_key, 'true');
    state = const AsyncData(true);
  }

  /// 동의 철회.
  Future<void> revoke() async {
    final storage = ref.read(secureStorageProvider);
    await storage.delete(_key);
    state = const AsyncData(false);
  }
}
```

### 7. `lib/features/health/presentation/screens/health_consent_screen.dart`

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/health_repository.dart';
import '../providers/health_consent_provider.dart';

/// 헬스 데이터 별도 동의 화면.
///
/// Reference:
///   docs/10-compliance-checklist.md §5.2 (별도 동의 의무)
class HealthConsentScreen extends ConsumerStatefulWidget {
  const HealthConsentScreen({super.key});

  @override
  ConsumerState<HealthConsentScreen> createState() =>
      _HealthConsentScreenState();
}

class _HealthConsentScreenState extends ConsumerState<HealthConsentScreen> {
  bool _agreedDataCollection = false;
  bool _agreedPurpose = false;
  bool _isLoading = false;

  bool get _canProceed => _agreedDataCollection && _agreedPurpose;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('건강 데이터 사용 동의')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildIntro(),
          const SizedBox(height: 24),
          _buildDataList(),
          const SizedBox(height: 24),
          _buildPurpose(),
          const SizedBox(height: 24),
          _buildAgreements(),
          const SizedBox(height: 32),
          FilledButton(
            onPressed: _canProceed && !_isLoading ? _proceed : null,
            child: _isLoading
                ? const CircularProgressIndicator()
                : const Text('동의하고 계속'),
          ),
          TextButton(
            onPressed: _isLoading ? null : () => context.pop(),
            child: const Text('나중에 하기'),
          ),
        ],
      ),
    );
  }

  Widget _buildIntro() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '활동점수와 체중 변화 예측을 위해\n건강 데이터 접근 권한이 필요합니다',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 12),
        Text(
          '본 데이터는 분석 목적으로만 사용되며, '
          '가명 처리되어 제3자에게 제공되지 않습니다.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      ],
    );
  }

  Widget _buildDataList() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '수집 데이터',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            const _DataItem(icon: Icons.directions_walk, label: '걸음수 (최근 30일)'),
            const _DataItem(icon: Icons.favorite, label: '심박수 (최근 7일)'),
            const _DataItem(icon: Icons.monitor_weight, label: '체중 (최근 30일)'),
          ],
        ),
      ),
    );
  }

  Widget _buildPurpose() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '사용 목적',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            const Text('• 활동점수 산출 (걸음수·심박수)'),
            const Text('• 체중 변화 예측 (체중 추이)'),
            const Text('• 운동 권고 정보 제공'),
          ],
        ),
      ),
    );
  }

  Widget _buildAgreements() {
    return Column(
      children: [
        CheckboxListTile(
          value: _agreedDataCollection,
          onChanged: (v) => setState(() => _agreedDataCollection = v ?? false),
          title: const Text('건강 데이터 수집에 동의합니다 (필수)'),
        ),
        CheckboxListTile(
          value: _agreedPurpose,
          onChanged: (v) => setState(() => _agreedPurpose = v ?? false),
          title: const Text('위 사용 목적에 동의합니다 (필수)'),
        ),
      ],
    );
  }

  Future<void> _proceed() async {
    setState(() => _isLoading = true);

    // 1. 별도 동의 저장
    await ref.read(healthConsentProvider.notifier).grant();

    // 2. OS 권한 요청
    final repo = ref.read(healthRepositoryProvider);
    final granted = await repo.requestPermissions();

    if (!mounted) return;
    setState(() => _isLoading = false);

    if (granted) {
      context.go('/health/dashboard');
    } else {
      _showPermissionDialog();
    }
  }

  void _showPermissionDialog() {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('권한이 거부되었습니다'),
        content: const Text(
          '설정에서 건강 데이터 접근 권한을 허락하시면 자동 수집을 시작합니다. '
          '수동으로 입력하실 수도 있습니다.',
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              context.go('/health/manual-input');
            },
            child: const Text('수동 입력'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('확인'),
          ),
        ],
      ),
    );
  }
}

class _DataItem extends StatelessWidget {
  const _DataItem({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(icon, size: 20),
          const SizedBox(width: 12),
          Text(label),
        ],
      ),
    );
  }
}
```

### 8. `lib/features/health/presentation/widgets/manual_input_dialog.dart` (폴백)

```dart
import 'package:flutter/material.dart';

/// HealthKit/Health Connect를 사용하지 못할 때 수동 입력 다이얼로그.
class ManualInputDialog extends StatefulWidget {
  const ManualInputDialog({super.key});

  @override
  State<ManualInputDialog> createState() => _ManualInputDialogState();
}

class _ManualInputDialogState extends State<ManualInputDialog> {
  final _stepsController = TextEditingController();
  final _weightController = TextEditingController();

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('건강 정보 입력'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          TextField(
            controller: _stepsController,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: '오늘 걸음수'),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _weightController,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(labelText: '체중 (kg)'),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('취소'),
        ),
        FilledButton(
          onPressed: _save,
          child: const Text('저장'),
        ),
      ],
    );
  }

  void _save() {
    final steps = int.tryParse(_stepsController.text);
    final weight = double.tryParse(_weightController.text);
    Navigator.pop(context, {'steps': steps, 'weight': weight});
  }
}
```

---

## 🧪 테스트

### 단위 테스트 (Repository, 모킹)

```dart
test('HealthRepository.getDailySteps returns correct data', () async {
  final mockHealth = MockHealth();
  when(() => mockHealth.getTotalStepsInInterval(any(), any()))
      .thenAnswer((_) async => 8000);

  final repo = HealthRepository(health: mockHealth);
  final steps = await repo.getDailySteps(days: 7);

  expect(steps.length, 7);
  expect(steps.first.steps, 8000);
});

test('hasPermissions returns false when not granted', () async {
  final mockHealth = MockHealth();
  when(() => mockHealth.hasPermissions(any())).thenAnswer((_) async => false);

  final repo = HealthRepository(health: mockHealth);
  expect(await repo.hasPermissions(), false);
});
```

### 위젯 테스트 (동의 화면)

```dart
testWidgets('Cannot proceed without both checkboxes', (tester) async {
  await tester.pumpWidget(
    ProviderScope(
      child: MaterialApp(home: HealthConsentScreen()),
    ),
  );

  // 초기 상태: 비활성
  final button = find.widgetWithText(FilledButton, '동의하고 계속');
  expect(tester.widget<FilledButton>(button).onPressed, isNull);

  // 한 개만 체크
  await tester.tap(find.byType(Checkbox).first);
  await tester.pump();
  expect(tester.widget<FilledButton>(button).onPressed, isNull);

  // 둘 다 체크
  await tester.tap(find.byType(Checkbox).last);
  await tester.pump();
  expect(tester.widget<FilledButton>(button).onPressed, isNotNull);
});
```

### E2E 테스트 (Patrol)

```dart
patrolTest('Health consent → permission → data display', (PatrolTester $) async {
  await $.pumpWidget(const ProviderScope(child: LemonHealthcareApp()));

  await $('건강 데이터 연동').tap();

  // 동의 체크박스
  await $.tap(find.byType(Checkbox).first);
  await $.tap(find.byType(Checkbox).at(1));

  await $('동의하고 계속').tap();

  // OS 권한 다이얼로그 자동 처리
  await $.native.grantPermissionWhenInUse();

  await $('대시보드').waitUntilVisible();
});
```

---

## ✅ Definition of Done

- [ ] iOS Info.plist + Capability 설정
- [ ] Android Manifest 권한 + activity-alias
- [ ] Freezed 모델 (DailySteps, HeartRateSummary, WeightRecord)
- [ ] `HealthRepository` (권한 + 데이터 조회 + 일괄 수집)
- [ ] `HealthConsent` Provider (별도 동의 영속화)
- [ ] `HealthConsentScreen` (별도 동의 UI + 체크박스 2개)
- [ ] `ManualInputDialog` 폴백
- [ ] 권한 거부 시 수동 입력 안내
- [ ] 단위 테스트 (Repository 모킹)
- [ ] 위젯 테스트 (동의 화면)
- [ ] (선택) Patrol E2E 테스트
- [ ] iOS 디바이스 (HealthKit) 정상 동작 확인
- [ ] Android 디바이스 (Health Connect 앱 설치 후) 동작 확인
- [ ] `flutter analyze` + `flutter test` 통과

---

## 💡 구현 팁

### Health Connect 사전 설치 안내

Android에서는 Health Connect 앱이 별도 설치되어야 함 (Android 13까지). 14+에서는 OS 통합. 사용자 안내 필요:

```dart
Future<bool> isHealthConnectAvailable() async {
  if (!Platform.isAndroid) return true;
  // health 패키지 isAvailable 사용 또는 별도 체크
  // ...
}
```

### 백그라운드 동기화 (Phase 3)

Phase 2에서는 **앱 활성화 시 동기화** 만. 백그라운드 (HKObserverQuery, Health Connect Background) 는 Phase 3에서.

### 데이터 가명처리

```dart
// ❌ 그대로 백엔드 전송
await api.syncHealth({"user_email": "user@example.com", "steps": 8000});

// ✅ 백엔드에는 user_id (UUID)만, 이메일·이름 제외
await api.syncHealth({"steps": 8000, "date": "2026-05-03"});
// 인증 헤더의 토큰으로 user_id 식별
```

### 심박 영역 계산 (간단판)

```dart
// 간단 버전 (Phase 2)
final targetMinutes = avg > 80 && avg < 140 ? 30 : 0;

// 정교한 버전 (Phase 3): 사용자 나이 기반 동적 계산
final maxHr = 220 - userAge;
final targetMin = maxHr * 0.5;
final targetMax = maxHr * 0.7;
final pointsInZone = points.where((p) => p.value > targetMin && p.value < targetMax);
final durationMin = pointsInZone.length / 4;  // 15초 간격 가정
```

---

## 🚫 이 작업에서 하지 말 것

- ❌ 백그라운드 자동 동기화 (Phase 3)
- ❌ 활동점수 직접 계산 (백엔드 API 호출)
- ❌ 데이터를 로컬 DB에 영속 저장 (전송 후 즉시 폐기)
- ❌ HealthKit 데이터 쓰기 (읽기만)

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md)
- [`/mobile/CLAUDE.md`](../../mobile/CLAUDE.md)
- [`/docs/09-data-catalog.md §6`](../09-data-catalog.md) — HealthKit·Health Connect 카탈로그
- [`/docs/10-compliance-checklist.md §5.2`](../10-compliance-checklist.md) — 별도 동의
- 이전: [`11-mobile-camera-screen.md`](./11-mobile-camera-screen.md)
- 다음: [`13-mobile-dashboard.md`](./13-mobile-dashboard.md)
