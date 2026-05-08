# mobile/CLAUDE.md — 모바일 작업 컨텍스트 (Tier 2)

> 이 문서는 **모바일(`mobile/`) 디렉토리에서 작업할 때 추가로 읽어야 하는 컨텍스트**입니다.  
> 루트 `CLAUDE.md`와 함께 사용하세요.

---

## 🎯 모바일의 역할

- 사용자 입력 수집 (프로필, 영양제 사진, 식단)
- HealthKit/Health Connect 자동 데이터 수집 (걸음수·심박수·체중)
- 백엔드 API 호출 + 결과 표시
- 5종 출력 대시보드 시각화
- **연산은 모두 백엔드** — 모바일은 표시·입력만

> ⚠️ Phase 2~3에서 모바일이 직접 알고리즘을 구현하면 안 됨. 모든 산출식은 백엔드 API 경유.

---

## 📂 모바일 폴더 구조 (절대 준수)

```
mobile/
├── CLAUDE.md                    ← 이 파일
├── pubspec.yaml                 # 의존성·메타정보
├── analysis_options.yaml        # Dart 린트 규칙
├── README.md                    # 모바일 개발 가이드
├── .env                         # API 엔드포인트 등 (gitignore)
├── .env.example
│
├── lib/
│   ├── main.dart                # 진입점
│   ├── app.dart                 # MaterialApp + 라우팅
│   │
│   ├── core/                    # 핵심 인프라
│   │   ├── config/              # 환경 설정
│   │   ├── theme/               # Material 3 테마
│   │   ├── routing/             # go_router 정의
│   │   ├── network/             # Dio 클라이언트, Interceptors
│   │   ├── storage/             # SharedPreferences, secure_storage
│   │   └── utils/
│   │
│   ├── features/                # 기능별 모듈
│   │   ├── onboarding/          # 첫 진입 + 동의 UI
│   │   │   ├── data/
│   │   │   ├── domain/
│   │   │   └── presentation/
│   │   │       ├── screens/
│   │   │       ├── widgets/
│   │   │       └── providers/   # Riverpod
│   │   ├── supplement/          # 영양제 등록
│   │   ├── meal/                # 식단 입력
│   │   ├── health/              # HealthKit/Health Connect
│   │   ├── activity/            # 활동점수 화면
│   │   ├── nutrition/           # 영양 분석 화면
│   │   ├── prediction/          # 체중 예측 화면
│   │   └── profile/             # 사용자 프로필
│   │
│   ├── shared/                  # 공통 위젯·서비스
│   │   ├── widgets/             # 재사용 위젯
│   │   │   ├── disclaimer.dart  # ⭐ 면책 고지 위젯 (필수)
│   │   │   ├── loading.dart
│   │   │   └── error.dart
│   │   ├── models/              # 공통 데이터 모델
│   │   └── services/
│   │
│   └── l10n/                    # 다국어 (한국어 메인)
│       └── intl_ko.arb
│
├── ios/                         # iOS 빌드 설정
│   ├── Runner/
│   │   └── Info.plist           # ⭐ HealthKit 권한 설명
│   └── Podfile
│
├── android/                     # Android 빌드 설정
│   ├── app/
│   │   └── src/main/
│   │       └── AndroidManifest.xml  # ⭐ Health Connect 권한
│   └── build.gradle
│
└── test/
    ├── unit/                    # 비즈니스 로직 단위 테스트
    ├── widget/                  # 위젯 테스트
    └── integration_test/        # E2E 통합 테스트
```

---

## 📦 표준 의존성 (`pubspec.yaml`)

```yaml
name: lemon_healthcare
description: "만성질환자 중심의 AI 헬스케어 플랫폼"
publish_to: 'none'
version: 0.1.0+1

environment:
  sdk: '>=3.4.0 <4.0.0'
  flutter: '>=3.24.0'

dependencies:
  flutter:
    sdk: flutter

  # 상태 관리
  flutter_riverpod: ^2.5.1
  riverpod_annotation: ^2.3.5

  # 라우팅
  go_router: ^14.2.0

  # 네트워크
  dio: ^5.4.0
  retrofit: ^4.1.0

  # 데이터 모델 (코드 생성)
  json_annotation: ^4.9.0
  freezed_annotation: ^2.4.1

  # 스토리지
  shared_preferences: ^2.2.0
  flutter_secure_storage: ^9.0.0

  # 헬스 데이터
  health: ^11.0.0  # ⭐ HealthKit + Health Connect 통합
  permission_handler: ^11.3.0

  # 카메라·이미지
  image_picker: ^1.1.0
  image_cropper: ^7.0.0
  cached_network_image: ^3.3.0

  # UI
  fl_chart: ^0.68.0  # 차트
  flutter_svg: ^2.0.10
  google_fonts: ^6.2.0

  # 유틸
  intl: ^0.19.0
  logger: ^2.3.0
  collection: ^1.18.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  integration_test:
    sdk: flutter

  # 린트
  flutter_lints: ^4.0.0
  very_good_analysis: ^6.0.0  # 더 엄격한 린트

  # 코드 생성
  build_runner: ^2.4.10
  riverpod_generator: ^2.4.0
  retrofit_generator: ^9.1.0
  json_serializable: ^6.8.0
  freezed: ^2.5.0

  # 테스트
  mocktail: ^1.0.0
  golden_toolkit: ^0.15.0  # 골든 테스트
  patrol: ^3.6.0  # E2E 테스트

flutter:
  uses-material-design: true
  generate: true  # l10n
```

---

## 🔧 `analysis_options.yaml` (엄격 모드)

```yaml
include: package:very_good_analysis/analysis_options.yaml

analyzer:
  language:
    strict-casts: true
    strict-inference: true
    strict-raw-types: true
  exclude:
    - "**/*.g.dart"
    - "**/*.freezed.dart"
    - "**/generated_plugin_registrant.dart"

linter:
  rules:
    # 추가 권장 규칙
    always_declare_return_types: true
    always_specify_types: true  # 타입 명시 강제
    avoid_print: true           # print() 금지
    prefer_const_constructors: true
    require_trailing_commas: true
    sort_constructors_first: true
    use_build_context_synchronously: true
    use_super_parameters: true
```

---

## 🧱 표준 코드 패턴

### Pattern 1. Riverpod 상태 관리 (코드 생성 방식)

```dart
// lib/features/activity/presentation/providers/activity_provider.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../domain/activity_score.dart';
import '../../data/activity_repository.dart';

part 'activity_provider.g.dart';

/// 활동점수 상태 Provider.
///
/// 사용자 프로필을 기반으로 백엔드에서 v1~v4 활동점수를 가져온다.
@riverpod
class ActivityScoreNotifier extends _$ActivityScoreNotifier {
  @override
  Future<ActivityScore> build() async {
    final repository = ref.read(activityRepositoryProvider);
    return repository.getActivityScore();
  }

  /// 사용자가 직접 새로고침 요청 시 호출.
  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      final repository = ref.read(activityRepositoryProvider);
      return repository.getActivityScore();
    });
  }
}
```

### Pattern 2. Dio API 클라이언트 (Retrofit)

```dart
// lib/core/network/api_client.dart
import 'package:dio/dio.dart';
import 'package:retrofit/retrofit.dart';

import '../../shared/models/activity_score.dart';

part 'api_client.g.dart';

/// 백엔드 API 클라이언트.
///
/// Dio + Retrofit 기반. 자동으로 JSON 직렬화/역직렬화 처리.
@RestApi()
abstract class ApiClient {
  factory ApiClient(Dio dio, {String baseUrl}) = _ApiClient;

  /// 활동점수 조회.
  @POST('/api/v1/activity/score')
  Future<ActivityScore> getActivityScore(
    @Body() ActivityRequest request,
  );

  /// 영양제 등록 (multipart 업로드).
  @POST('/api/v1/supplements/register')
  @MultiPart()
  Future<SupplementResponse> registerSupplement(
    @Part(name: 'image') List<int> imageBytes,
  );
}
```

### Pattern 3. Freezed 데이터 모델

```dart
// lib/shared/models/activity_score.dart
import 'package:freezed_annotation/freezed_annotation.dart';

part 'activity_score.freezed.dart';
part 'activity_score.g.dart';

/// 활동점수 응답 모델.
@freezed
class ActivityScore with _$ActivityScore {
  const factory ActivityScore({
    required int recommendedSteps,
    required double v1Score,
    required double v2Score,
    required double v3Score,
    required double v4Score,
  }) = _ActivityScore;

  factory ActivityScore.fromJson(Map<String, dynamic> json) =>
      _$ActivityScoreFromJson(json);
}
```

### Pattern 4. ⭐ 면책 고지 위젯 (필수)

```dart
// lib/shared/widgets/disclaimer.dart
import 'package:flutter/material.dart';

/// 의료법 면책 고지 위젯.
///
/// 모든 권고 화면(영양·체중·운동·목적별 분석)에 반드시 사용.
/// 컴플라이언스 §2.3 표준 문구를 그대로 사용.
class MedicalDisclaimer extends StatelessWidget {
  const MedicalDisclaimer({
    super.key,
    this.variant = DisclaimerVariant.main,
  });

  final DisclaimerVariant variant;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          const Icon(Icons.info_outline, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              variant.text,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        ],
      ),
    );
  }
}

/// 면책 고지 유형.
///
/// Reference:
///   docs/10-compliance-checklist.md §2.3
enum DisclaimerVariant {
  /// 메인 디스클레이머 (모든 권고 화면).
  main(
    '본 서비스에서 제공하는 정보는 일반적인 건강 관리를 위한 참고 자료이며, '
    '의사·약사·영양사의 전문적 진단이나 처방을 대체하지 않습니다.',
  ),

  /// 영양제 화면용.
  supplement(
    '영양제는 의약품이 아니며, 질병의 예방이나 치료를 보장하지 않습니다. '
    '약을 복용 중이신 경우, 영양제와의 상호작용에 대해 의료진과 상담하세요.',
  ),

  /// 체중 예측 화면용.
  weightPrediction(
    '체중 변화 예측은 평균적인 수치를 바탕으로 산출되며, 개인의 대사·체질·'
    '생활습관에 따라 결과가 달라질 수 있습니다. 급격한 체중 변화는 건강에 '
    '해로울 수 있으니 의료진과 상담하세요.',
  );

  const DisclaimerVariant(this.text);
  final String text;
}
```

### Pattern 5. 화면 (Screen) 표준 구조

```dart
// lib/features/activity/presentation/screens/activity_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../shared/widgets/disclaimer.dart';
import '../providers/activity_provider.dart';

/// 활동점수 화면.
///
/// v1~v4 활동점수와 권장 걸음수를 표시한다.
class ActivityScreen extends ConsumerWidget {
  const ActivityScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final scoreAsync = ref.watch(activityScoreNotifierProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('활동점수')),
      body: scoreAsync.when(
        data: (score) => _ScoreContent(score: score),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => _ErrorView(error: error),
      ),
    );
  }
}

class _ScoreContent extends StatelessWidget {
  const _ScoreContent({required this.score});

  final ActivityScore score;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // 점수 카드들 ...
        const SizedBox(height: 24),
        // ⭐ 모든 권고 화면 하단에 면책 고지 필수
        const MedicalDisclaimer(variant: DisclaimerVariant.main),
      ],
    );
  }
}
```

---

## 🔥 모바일 작업 절대 규칙

### Rule 1. ⭐ 모든 권고 화면에 면책 고지 필수

영양·체중·운동·목적별 분석 화면 4개에 **반드시 `MedicalDisclaimer` 위젯 사용**. 새 화면을 만들 때 누락하면 PR 거절.

### Rule 2. 사용자 노출 텍스트는 한국어 (l10n)

```dart
// ❌ 하드코딩
Text('운동 권고')

// ✅ l10n 사용 (Phase 3에서 본격 도입)
Text(AppLocalizations.of(context)!.activityRecommendation)

// Phase 2 동안은 const 변수로 분리
class AppStrings {
  static const String activityTitle = '활동 분석';
  static const String activityRecommendation = '운동 권고';
}
```

### Rule 3. 의료법 표현 가이드 준수

UI에 표시되는 텍스트에 **금지 단어** 사용 X (루트 CLAUDE.md Rule 1 참조):

```dart
// ❌
Text('당뇨 진단 결과') 
Text('이 영양제를 처방드립니다')

// ✅
Text('혈당 관리 권고')
Text('비타민 D 섭취량을 늘리는 것을 고려해보세요')
```

### Rule 4. 외부 호출은 Repository 경유

```dart
// ❌ 화면에서 직접 Dio 호출
Future<void> _fetch() async {
  final response = await Dio().get(...);
}

// ✅ Repository 경유
final repository = ref.read(activityRepositoryProvider);
final score = await repository.getActivityScore();
```

### Rule 5. 민감 정보 처리

- **API 키·비밀번호**: 절대 mobile에 X (백엔드만)
- **사용자 만성질환**: `flutter_secure_storage` 사용 (KeyChain/EncryptedSharedPreferences)
- **걸음수·심박수**: HealthKit/Health Connect에서만, 임시 메모리에만

### Rule 6. ⭐ HealthKit/Health Connect 권한 요청 흐름

```
1. 동의 화면 (별도 동의 UI)
   ↓ 사용자 명시 동의
2. permission_handler로 카메라·사진·헬스 권한 요청
   ↓ 권한 허락
3. health 패키지로 데이터 읽기
   ↓
4. 백엔드 동기화
```

> ⚠️ 권한 요청 전에 **반드시 사용 목적을 한국어로 설명**하는 다이얼로그를 띄워야 함 (앱스토어 심사 통과 필수).

### Rule 7. 비동기 컨텍스트 안전

```dart
// ❌ async 후 context 사용 (lint 경고)
Future<void> _save() async {
  await _saveData();
  Navigator.of(context).pop();  // context가 더 이상 유효하지 않을 수 있음
}

// ✅ mounted 체크
Future<void> _save() async {
  await _saveData();
  if (!mounted) return;
  Navigator.of(context).pop();
}
```

---

## 🧪 테스트 전략 (3-Tier)

### Tier 1: 단위 테스트 (`test/unit/`)
- 비즈니스 로직, 변환 함수, 모델 직렬화
- 외부 의존성 모두 모킹 (mocktail)
- 빠르고 결정론적

### Tier 2: 위젯 테스트 (`test/widget/`)
- 단일 위젯 또는 화면 렌더링
- ProviderScope 오버라이드로 의존성 주입
- 골든 테스트로 시각 회귀 검출

### Tier 3: 통합 테스트 (`integration_test/`)
- 실제 디바이스/시뮬레이터에서 E2E
- patrol 패키지로 권한 다이얼로그 자동 처리
- 핵심 시나리오 (영양제 등록, HealthKit 연동) 자동화

```bash
# 단위·위젯 테스트
flutter test --coverage

# 통합 테스트 (디바이스 필요)
flutter test integration_test/
```

---

## 🛠 자주 사용하는 명령어

```bash
# 환경
flutter doctor -v
flutter pub get
flutter pub upgrade

# 코드 생성 (변경 후 필수)
dart run build_runner build --delete-conflicting-outputs
dart run build_runner watch       # 변경 감시

# 정적 분석
flutter analyze
dart format lib test --line-length=100

# 테스트
flutter test                                    # 전체
flutter test test/widget/                       # 위젯만
flutter test --coverage                         # 커버리지
flutter test integration_test/                  # E2E

# 실행
flutter devices                                 # 디바이스 목록
flutter run                                     # 기본
flutter run -d "iPhone 15"                      # iOS 시뮬
flutter run -d emulator-5554                    # Android emul

# 빌드
flutter build apk --debug                       # Android Debug
flutter build appbundle                         # Google Play 업로드
flutter build ios --no-codesign                 # iOS 빌드 검증
flutter build ipa                               # App Store 업로드 (Mac만)
```

---

## 🔒 보안 체크리스트

- [ ] API 키·시크릿 절대 mobile에 X
- [ ] HTTPS 강제 (HTTP 차단)
- [ ] `flutter_secure_storage` 로 민감 데이터 저장
- [ ] HealthKit/Health Connect 권한 사용 목적 명시
- [ ] Info.plist + AndroidManifest 최소 권한만
- [ ] 빌드 변수 (.env) gitignore 확인
- [ ] 민감 정보 logger 출력 금지
- [ ] 디버그 모드에서만 `flutter_debug_overlay` 사용

---

## 🎨 UI/UX 표준

### Material 3 테마 색상

```dart
// lib/core/theme/colors.dart
class AppColors {
  // Lemon Healthcare 브랜드 컬러
  static const primary = Color(0xFFFFD700);      // 메인 옐로우
  static const primaryContainer = Color(0xFFFFF9C4);
  static const secondary = Color(0xFF4FC3F7);    // 신뢰감 블루
  static const error = Color(0xFFD32F2F);
  static const success = Color(0xFF388E3C);
  static const warning = Color(0xFFFB8C00);
}
```

### 폰트

- **한글**: Noto Sans KR (Google Fonts)
- **영문·숫자**: Inter

### 간격 표준

```dart
class Spacing {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 16;
  static const double lg = 24;
  static const double xl = 32;
}
```

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../CLAUDE.md) — 프로젝트 루트 컨텍스트
- [`/backend/CLAUDE.md`](../backend/CLAUDE.md) — 백엔드 API 패턴
- [`/docs/06-tech-stack.md`](../docs/06-tech-stack.md) — Flutter 기술 의사결정
- [`/docs/10-compliance-checklist.md`](../docs/10-compliance-checklist.md) — 면책 고지·권한 정책

---

**마지막 갱신**: 2026-05-03 | **버전**: v1.0
