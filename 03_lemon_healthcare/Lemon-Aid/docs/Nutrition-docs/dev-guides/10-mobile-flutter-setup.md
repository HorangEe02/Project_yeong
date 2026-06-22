# dev-guides/10 — Flutter 프로젝트 골격

> **Phase**: 2 | **선행 작업**: 없음 (모바일 트랙 시작) | **예상 소요**: 3~4시간

---

## 🎯 작업 목표

Flutter 모바일 앱의 기본 골격(라우팅, 테마, 상태 관리, API 클라이언트)을 구축하여 이후 화면 구현을 시작할 수 있는 환경을 갖춘다. `mobile/CLAUDE.md` 명세에 정의된 폴더 구조·의존성·패턴을 그대로 따른다.

---

## 📋 산출물

```
mobile/
├── pubspec.yaml                 # ⭐ mobile/CLAUDE.md 참조
├── analysis_options.yaml        # ⭐ mobile/CLAUDE.md 참조
├── .env.example
├── .gitignore
├── README.md
│
├── lib/
│   ├── main.dart                # 진입점
│   ├── app.dart                 # MaterialApp
│   │
│   ├── core/
│   │   ├── config/
│   │   │   └── env.dart         # 환경 변수 로드
│   │   ├── theme/
│   │   │   ├── app_theme.dart
│   │   │   └── colors.dart
│   │   ├── routing/
│   │   │   └── app_router.dart  # go_router
│   │   ├── network/
│   │   │   ├── api_client.dart  # Dio + Retrofit
│   │   │   ├── dio_provider.dart
│   │   │   └── interceptors.dart
│   │   ├── storage/
│   │   │   └── secure_storage.dart
│   │   └── utils/
│   │       └── logger.dart
│   │
│   ├── shared/
│   │   ├── widgets/
│   │   │   ├── disclaimer.dart  # ⭐ MedicalDisclaimer (mobile/CLAUDE.md)
│   │   │   ├── app_loading.dart
│   │   │   └── app_error.dart
│   │   └── models/
│   │       └── api_error.dart
│   │
│   └── features/
│       └── home/
│           └── presentation/
│               └── screens/
│                   └── home_screen.dart  # 임시 홈
│
└── test/
    ├── unit/
    │   └── core/
    │       └── network/
    │           └── api_client_test.dart
    └── widget/
        └── shared/
            └── disclaimer_test.dart
```

---

## 🔧 구현 명세

### 1. `lib/main.dart`

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'core/utils/logger.dart';

/// 앱 진입점.
///
/// Riverpod ProviderScope로 감싸 전역 상태를 활성화한다.
void main() {
  setupLogger();
  runApp(
    const ProviderScope(
      child: LemonHealthcareApp(),
    ),
  );
}
```

### 2. `lib/app.dart`

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/routing/app_router.dart';
import 'core/theme/app_theme.dart';

/// 루트 위젯.
///
/// MaterialApp.router를 구성하고 테마·라우팅을 주입한다.
class LemonHealthcareApp extends ConsumerWidget {
  const LemonHealthcareApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);

    return MaterialApp.router(
      title: '레몬헬스케어',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      routerConfig: router,
      locale: const Locale('ko', 'KR'),
      supportedLocales: const [Locale('ko', 'KR')],
    );
  }
}
```

### 3. `lib/core/config/env.dart`

```dart
import 'package:flutter/foundation.dart';

/// 환경 변수 (빌드 시 --dart-define 으로 주입).
///
/// 사용 예:
///   flutter run --dart-define=API_BASE_URL=https://api.lemonhc.com
abstract class Env {
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  static const bool isDebug = kDebugMode;

  static const String environment = String.fromEnvironment(
    'ENVIRONMENT',
    defaultValue: 'development',
  );
}
```

### 4. `lib/core/theme/colors.dart`

```dart
import 'package:flutter/material.dart';

/// Lemon Healthcare 브랜드 컬러.
///
/// Reference:
///   mobile/CLAUDE.md - UI/UX 표준
abstract class AppColors {
  // Primary (브랜드 옐로우)
  static const Color primary = Color(0xFFFFD700);
  static const Color primaryContainer = Color(0xFFFFF9C4);
  static const Color onPrimary = Color(0xFF1A1A1A);

  // Secondary (신뢰감 블루)
  static const Color secondary = Color(0xFF4FC3F7);
  static const Color secondaryContainer = Color(0xFFE1F5FE);

  // Status
  static const Color error = Color(0xFFD32F2F);
  static const Color success = Color(0xFF388E3C);
  static const Color warning = Color(0xFFFB8C00);

  // Surface
  static const Color surfaceLight = Color(0xFFFFFFFF);
  static const Color surfaceDark = Color(0xFF121212);
}
```

### 5. `lib/core/theme/app_theme.dart`

```dart
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'colors.dart';

/// 앱 테마 (Material 3).
abstract class AppTheme {
  static ThemeData get light => _build(Brightness.light);
  static ThemeData get dark => _build(Brightness.dark);

  static ThemeData _build(Brightness brightness) {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: AppColors.primary,
      brightness: brightness,
    );

    return ThemeData(
      colorScheme: colorScheme,
      useMaterial3: true,
      fontFamily: GoogleFonts.notoSansKr().fontFamily,
      textTheme: GoogleFonts.notoSansKrTextTheme(
        ThemeData(brightness: brightness).textTheme,
      ),
      appBarTheme: AppBarTheme(
        centerTitle: true,
        elevation: 0,
        backgroundColor: colorScheme.surface,
        foregroundColor: colorScheme.onSurface,
      ),
      cardTheme: CardTheme(
        elevation: 1,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        ),
      ),
    );
  }
}
```

### 6. `lib/core/routing/app_router.dart`

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../features/home/presentation/screens/home_screen.dart';

part 'app_router.g.dart';

/// go_router Provider.
///
/// 라우트 정의는 features/별로 확장. Phase 2 초기엔 home만.
@riverpod
GoRouter appRouter(AppRouterRef ref) {
  return GoRouter(
    initialLocation: '/',
    debugLogDiagnostics: true,
    routes: [
      GoRoute(
        path: '/',
        name: 'home',
        builder: (context, state) => const HomeScreen(),
      ),
      // TODO: 영양제 등록, 대시보드 등 추가
    ],
  );
}
```

### 7. `lib/core/network/dio_provider.dart`

```dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../config/env.dart';
import 'interceptors.dart';

part 'dio_provider.g.dart';

/// Dio 인스턴스 Provider.
@riverpod
Dio dio(DioRef ref) {
  final dio = Dio(BaseOptions(
    baseUrl: Env.apiBaseUrl,
    connectTimeout: const Duration(seconds: 10),
    receiveTimeout: const Duration(seconds: 30),
    sendTimeout: const Duration(seconds: 30),
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    },
  ));

  // Interceptors
  dio.interceptors.addAll([
    AuthInterceptor(ref),
    LoggingInterceptor(),
    ErrorInterceptor(),
  ]);

  return dio;
}
```

### 8. `lib/core/network/interceptors.dart`

```dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../storage/secure_storage.dart';
import '../utils/logger.dart';

/// 인증 토큰 자동 첨부.
class AuthInterceptor extends Interceptor {
  AuthInterceptor(this._ref);

  final Ref _ref;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final storage = _ref.read(secureStorageProvider);
    final token = await storage.read('auth_token');
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }
}

/// 요청·응답 로깅 (개발용).
class LoggingInterceptor extends Interceptor {
  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) {
    appLogger.d('→ ${options.method} ${options.uri}');
    handler.next(options);
  }

  @override
  void onResponse(
    Response<dynamic> response,
    ResponseInterceptorHandler handler,
  ) {
    appLogger.d(
      '← ${response.statusCode} ${response.requestOptions.uri}',
    );
    handler.next(response);
  }
}

/// 공통 에러 처리.
class ErrorInterceptor extends Interceptor {
  @override
  void onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) {
    appLogger.e(
      'API Error: ${err.response?.statusCode} ${err.requestOptions.uri}',
      error: err,
    );
    // TODO: 401 → 로그아웃 처리
    handler.next(err);
  }
}
```

### 9. `lib/core/network/api_client.dart`

```dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:retrofit/retrofit.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../shared/models/api_error.dart';
import 'dio_provider.dart';

part 'api_client.g.dart';

/// 백엔드 API 클라이언트 (Retrofit 자동 생성).
///
/// 새 엔드포인트는 여기에 메서드 추가하고 build_runner 실행.
@RestApi()
abstract class ApiClient {
  factory ApiClient(Dio dio, {String baseUrl}) = _ApiClient;

  // Phase 2 진행하며 추가:
  // - registerSupplement
  // - getActivityScore
  // - getNutritionDiagnosis
  // - getWeightPrediction
}

/// ApiClient Provider.
@riverpod
ApiClient apiClient(ApiClientRef ref) {
  final dio = ref.watch(dioProvider);
  return ApiClient(dio);
}
```

### 10. `lib/core/storage/secure_storage.dart`

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'secure_storage.g.dart';

/// 민감 정보 (토큰, 사용자 ID 등) 안전 저장.
///
/// iOS: KeyChain
/// Android: EncryptedSharedPreferences
class SecureStorage {
  SecureStorage(this._storage);

  final FlutterSecureStorage _storage;

  Future<void> write(String key, String value) =>
      _storage.write(key: key, value: value);

  Future<String?> read(String key) => _storage.read(key: key);

  Future<void> delete(String key) => _storage.delete(key: key);

  Future<void> deleteAll() => _storage.deleteAll();
}

@riverpod
SecureStorage secureStorage(SecureStorageRef ref) {
  return SecureStorage(const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  ));
}
```

### 11. `lib/core/utils/logger.dart`

```dart
import 'package:flutter/foundation.dart';
import 'package:logger/logger.dart';

/// 앱 전역 로거.
late final Logger appLogger;

/// 로거 초기화. main.dart에서 1회 호출.
void setupLogger() {
  appLogger = Logger(
    level: kDebugMode ? Level.debug : Level.info,
    printer: PrettyPrinter(
      methodCount: 0,
      colors: true,
      printEmojis: true,
    ),
  );
}
```

### 12. `lib/shared/widgets/disclaimer.dart`

`mobile/CLAUDE.md` Pattern 4를 그대로 구현. (이미 명세 정의됨)

### 13. `lib/shared/widgets/app_loading.dart`

```dart
import 'package:flutter/material.dart';

/// 표준 로딩 위젯.
class AppLoading extends StatelessWidget {
  const AppLoading({super.key, this.message});

  final String? message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const CircularProgressIndicator(),
          if (message != null) ...[
            const SizedBox(height: 16),
            Text(message!),
          ],
        ],
      ),
    );
  }
}
```

### 14. `lib/shared/widgets/app_error.dart`

```dart
import 'package:flutter/material.dart';

/// 표준 에러 위젯.
class AppError extends StatelessWidget {
  const AppError({
    super.key,
    required this.message,
    this.onRetry,
  });

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.error_outline,
              size: 48,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: 16),
            Text(
              message,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            if (onRetry != null) ...[
              const SizedBox(height: 24),
              FilledButton(
                onPressed: onRetry,
                child: const Text('다시 시도'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
```

### 15. `lib/features/home/presentation/screens/home_screen.dart`

```dart
import 'package:flutter/material.dart';

import '../../../../shared/widgets/disclaimer.dart';

/// 임시 홈 화면 (Phase 2 후반에 본격 대시보드로 교체).
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('레몬헬스케어')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: const [
          Card(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '환영합니다',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  SizedBox(height: 8),
                  Text('만성질환자 중심의 AI 헬스케어 서비스'),
                ],
              ),
            ),
          ),
          SizedBox(height: 24),
          MedicalDisclaimer(variant: DisclaimerVariant.main),
        ],
      ),
    );
  }
}
```

---

## 🧪 테스트

### 단위 테스트 (`test/unit/core/network/api_client_test.dart`)

```dart
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import '../../../helpers/test_helpers.dart';

void main() {
  group('Dio interceptors', () {
    test('AuthInterceptor adds Bearer token when present', () async {
      // Arrange
      final mockStorage = MockSecureStorage();
      when(() => mockStorage.read('auth_token'))
          .thenAnswer((_) async => 'test_token');

      // Act
      final options = RequestOptions(path: '/test');
      final handler = MockHandler();
      // ...

      // Assert
      // expect(options.headers['Authorization'], 'Bearer test_token');
    });

    test('AuthInterceptor skips when no token', () async {
      // ...
    });
  });
}
```

### 위젯 테스트 (`test/widget/shared/disclaimer_test.dart`)

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:lemon_healthcare/shared/widgets/disclaimer.dart';

void main() {
  group('MedicalDisclaimer', () {
    testWidgets('renders main variant text', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: MedicalDisclaimer(variant: DisclaimerVariant.main),
          ),
        ),
      );

      expect(find.textContaining('의사·약사·영양사'), findsOneWidget);
      expect(find.byIcon(Icons.info_outline), findsOneWidget);
    });

    testWidgets('renders supplement variant', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: MedicalDisclaimer(variant: DisclaimerVariant.supplement),
          ),
        ),
      );

      expect(find.textContaining('의약품이 아니'), findsOneWidget);
    });

    testWidgets('renders weightPrediction variant', (tester) async {
      // ...
    });
  });
}
```

### 골든 테스트 (`test/widget/shared/disclaimer_golden_test.dart`)

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:golden_toolkit/golden_toolkit.dart';

void main() {
  testGoldens('Disclaimer variants match golden', (tester) async {
    final builder = DeviceBuilder()
      ..addScenario(
        widget: const MedicalDisclaimer(variant: DisclaimerVariant.main),
        name: 'main',
      )
      ..addScenario(
        widget: const MedicalDisclaimer(variant: DisclaimerVariant.supplement),
        name: 'supplement',
      );

    await tester.pumpDeviceBuilder(builder);
    await screenMatchesGolden(tester, 'disclaimer_variants');
  });
}
```

---

## ✅ Definition of Done

- [ ] `pubspec.yaml` 작성 (mobile/CLAUDE.md 명세)
- [ ] `analysis_options.yaml` (very_good_analysis + 추가 룰)
- [ ] `flutter pub get` 정상
- [ ] `dart run build_runner build` 정상 (코드 생성 파일들)
- [ ] `lib/main.dart` + `lib/app.dart` 작성
- [ ] `lib/core/` 모든 모듈 작성 (config/theme/routing/network/storage/utils)
- [ ] `lib/shared/widgets/` (disclaimer, app_loading, app_error)
- [ ] `lib/features/home/` 임시 홈 화면
- [ ] 단위 테스트 (interceptors)
- [ ] 위젯 테스트 (MedicalDisclaimer 3가지 variant 모두)
- [ ] 골든 테스트 (시각 회귀 검출)
- [ ] `flutter analyze` 통과 (warning 0)
- [ ] `flutter test` 통과
- [ ] iOS 시뮬레이터 + Android 에뮬레이터 양쪽에서 정상 빌드·실행
- [ ] 홈 화면에서 면책 고지 표시 확인

---

## 💡 구현 팁

### Riverpod 코드 생성 워크플로

```bash
# 변경 후 한 번씩 (또는 watch 모드)
dart run build_runner build --delete-conflicting-outputs

# 변경 감시 모드 (개발 중)
dart run build_runner watch --delete-conflicting-outputs
```

### `--dart-define` 으로 환경 분리

```bash
# 개발
flutter run --dart-define=API_BASE_URL=http://localhost:8000

# 스테이징
flutter run --dart-define=API_BASE_URL=https://staging.api.lemonhc.com

# 운영 빌드
flutter build apk \
  --dart-define=API_BASE_URL=https://api.lemonhc.com \
  --dart-define=ENVIRONMENT=production
```

### 의존성 주입 (Riverpod over GetIt)

```dart
// ❌ GetIt 같은 서비스 로케이터
final apiClient = GetIt.I<ApiClient>();

// ✅ Riverpod
final apiClient = ref.watch(apiClientProvider);
```

### Material 3 + ColorScheme.fromSeed

브랜드 컬러 하나만 정해도 자동으로 전체 팔레트 생성:

```dart
ColorScheme.fromSeed(seedColor: AppColors.primary)
// → primary, primaryContainer, onPrimary, secondary, ...
```

---

## 🚫 이 작업에서 하지 말 것

- ❌ 백엔드 API 직접 호출 (라우터 정의만, 실제 호출은 다음 작업)
- ❌ 카메라·HealthKit 통합 (별도 가이드 11, 12)
- ❌ 대시보드 화면 (가이드 13)
- ❌ 인증 플로우 구현 (Phase 3 마일스톤)

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md)
- [`/mobile/CLAUDE.md`](../../mobile/CLAUDE.md) — 이 작업의 기반 문서
- [`/docs/Nutrition-docs/06-tech-stack.md`](../06-tech-stack.md)
- 다음: [`11-mobile-camera-screen.md`](./11-mobile-camera-screen.md)
