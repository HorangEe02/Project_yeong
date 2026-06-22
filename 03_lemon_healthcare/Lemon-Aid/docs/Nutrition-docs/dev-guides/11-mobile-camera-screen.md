# dev-guides/11 — 모바일 카메라/갤러리 화면

> **Phase**: 2 | **선행 작업**: [`10-mobile-flutter-setup.md`](./10-mobile-flutter-setup.md), [`09-supplement-registration-api.md`](./09-supplement-registration-api.md) | **예상 소요**: 3~4시간

> **Superseded note (2026-05-15)**: This guide is historical and still shows an older direct upload assumption. The current P2 mobile implementation follows [`docs/Integration-docs/04-p2-mobile-frontend-minimum-screen-plan.md`](../../Integration-docs/04-p2-mobile-frontend-minimum-screen-plan.md) and uploads images to `POST /api/v1/supplements/analyze` before OCR text review and user-confirmed `POST /api/v1/supplements` registration.

---

## 🎯 작업 목표

영양제 라벨을 촬영하거나 갤러리에서 선택하여 백엔드에 업로드하는 화면을 구현한다. 권한 요청·이미지 크롭·업로드 진행률·에러 처리 모두 포함.

---

## 📋 산출물

```
mobile/
├── lib/features/supplement/
│   ├── data/
│   │   └── supplement_repository.dart
│   ├── domain/
│   │   ├── supplement_models.dart        # Freezed 모델
│   │   └── supplement_models.freezed.dart
│   └── presentation/
│       ├── screens/
│       │   ├── supplement_capture_screen.dart  # 메인 화면
│       │   └── supplement_result_screen.dart   # 결과 화면
│       ├── widgets/
│       │   ├── source_selector.dart      # 카메라/갤러리 선택
│       │   ├── upload_progress.dart      # 업로드 진행
│       │   └── ingredient_card.dart      # 결과 카드
│       └── providers/
│           ├── supplement_provider.dart
│           └── supplement_provider.g.dart
├── ios/Runner/Info.plist                  # ⭐ 권한 설명 추가
└── android/app/src/main/AndroidManifest.xml  # ⭐ 권한 추가
```

---

## 📐 화면 흐름

```
┌─────────────────────────┐
│ SupplementCaptureScreen │
│                         │
│  [영양제 등록]          │
│                         │
│  📷 카메라로 촬영        │ ← 권한 요청
│  🖼  갤러리에서 선택     │ ← 권한 요청
│                         │
└─────────────────────────┘
           │
           ▼ 사용자 선택
┌─────────────────────────┐
│ image_picker            │ → 사진 획득
└─────────────────────────┘
           │
           ▼
┌─────────────────────────┐
│ image_cropper           │ → 영역 조정
└─────────────────────────┘
           │
           ▼
┌─────────────────────────┐
│ Upload + 진행률          │
│ POST /api/v1/supplements │
└─────────────────────────┘
           │
           ▼
┌─────────────────────────┐
│ SupplementResultScreen  │
│                         │
│ 제품명, 성분, 진단 표시   │
│ (면책 고지 필수)         │
└─────────────────────────┘
```

---

## 🔧 구현 명세

### 1. iOS 권한 설명 (`ios/Runner/Info.plist`)

```xml
<key>NSCameraUsageDescription</key>
<string>영양제 라벨을 촬영하여 성분을 분석하기 위해 카메라 권한이 필요합니다.</string>

<key>NSPhotoLibraryUsageDescription</key>
<string>영양제 라벨 사진을 선택하여 성분을 분석하기 위해 사진 권한이 필요합니다.</string>

<key>NSPhotoLibraryAddUsageDescription</key>
<string>분석한 영양제 정보를 사진으로 저장하기 위해 권한이 필요합니다.</string>
```

### 2. Android 권한 (`android/app/src/main/AndroidManifest.xml`)

```xml
<manifest>
  <!-- 카메라 -->
  <uses-permission android:name="android.permission.CAMERA" />

  <!-- 갤러리 (Android 13+ 분리) -->
  <uses-permission android:name="android.permission.READ_MEDIA_IMAGES" />
  <uses-permission
    android:name="android.permission.READ_EXTERNAL_STORAGE"
    android:maxSdkVersion="32" />

  <!-- 인터넷 -->
  <uses-permission android:name="android.permission.INTERNET" />

  <application ...>
    <!-- ... -->
  </application>
</manifest>
```

### 3. `lib/features/supplement/domain/supplement_models.dart`

```dart
import 'package:freezed_annotation/freezed_annotation.dart';

part 'supplement_models.freezed.dart';
part 'supplement_models.g.dart';

/// 영양제 등록 응답.
@freezed
class SupplementResponse with _$SupplementResponse {
  const factory SupplementResponse({
    required String supplementId,
    String? productName,
    String? manufacturer,
    required List<Ingredient> ingredients,
    required Diagnosis diagnosis,
    required String ocrEngine,
    required String llmEngine,
    required double elapsedMs,
  }) = _SupplementResponse;

  factory SupplementResponse.fromJson(Map<String, dynamic> json) =>
      _$SupplementResponseFromJson(json);
}

@freezed
class Ingredient with _$Ingredient {
  const factory Ingredient({
    required String code,
    required String nameKo,
    required double amount,
    required String unit,
  }) = _Ingredient;

  factory Ingredient.fromJson(Map<String, dynamic> json) =>
      _$IngredientFromJson(json);
}

@freezed
class Diagnosis with _$Diagnosis {
  const factory Diagnosis({
    required List<NutrientDiagnosis> diagnoses,
    required int deficientCount,
    required int riskyCount,
    required int adequateCount,
    required String summaryMessageKo,
  }) = _Diagnosis;

  factory Diagnosis.fromJson(Map<String, dynamic> json) =>
      _$DiagnosisFromJson(json);
}

@freezed
class NutrientDiagnosis with _$NutrientDiagnosis {
  const factory NutrientDiagnosis({
    required String code,
    required String nameKo,
    required String status,
    required double intakeAmount,
    double? referenceAmount,
    required double ratioPct,
    required String unit,
    double? upperLimit,
    required String messageKo,
  }) = _NutrientDiagnosis;

  factory NutrientDiagnosis.fromJson(Map<String, dynamic> json) =>
      _$NutrientDiagnosisFromJson(json);
}
```

### 4. `lib/features/supplement/data/supplement_repository.dart`

```dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../core/network/dio_provider.dart';
import '../domain/supplement_models.dart';

part 'supplement_repository.g.dart';

/// 영양제 등록 Repository.
class SupplementRepository {
  SupplementRepository(this._dio);

  final Dio _dio;

  /// 이미지를 백엔드에 업로드하고 분석 결과를 받는다.
  ///
  /// [onProgress] 는 0.0~1.0 진행률.
  Future<SupplementResponse> register({
    required String imagePath,
    void Function(double)? onProgress,
  }) async {
    final formData = FormData.fromMap({
      'image': await MultipartFile.fromFile(
        imagePath,
        filename: 'supplement.jpg',
      ),
    });

    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/supplements/register',
      data: formData,
      onSendProgress: (sent, total) {
        if (total > 0 && onProgress != null) {
          onProgress(sent / total);
        }
      },
    );

    if (response.data == null) {
      throw const FormatException('Empty response');
    }
    return SupplementResponse.fromJson(response.data!);
  }
}

@riverpod
SupplementRepository supplementRepository(SupplementRepositoryRef ref) {
  return SupplementRepository(ref.watch(dioProvider));
}
```

### 5. `lib/features/supplement/presentation/providers/supplement_provider.dart`

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../data/supplement_repository.dart';
import '../../domain/supplement_models.dart';

part 'supplement_provider.g.dart';

/// 영양제 등록 상태.
sealed class SupplementState {
  const SupplementState();
}

class IdleState extends SupplementState {
  const IdleState();
}

class UploadingState extends SupplementState {
  const UploadingState(this.progress);
  final double progress;
}

class SuccessState extends SupplementState {
  const SuccessState(this.response);
  final SupplementResponse response;
}

class ErrorState extends SupplementState {
  const ErrorState(this.message);
  final String message;
}

/// 영양제 등록 Notifier.
@riverpod
class SupplementNotifier extends _$SupplementNotifier {
  @override
  SupplementState build() => const IdleState();

  /// 이미지 업로드 + 분석.
  Future<void> register(String imagePath) async {
    state = const UploadingState(0);
    try {
      final response = await ref.read(supplementRepositoryProvider).register(
            imagePath: imagePath,
            onProgress: (p) => state = UploadingState(p),
          );
      state = SuccessState(response);
    } catch (e) {
      state = ErrorState(_mapError(e));
    }
  }

  /// 초기화 (다시 등록).
  void reset() => state = const IdleState();

  String _mapError(Object e) {
    // 사용자 친화 에러 메시지로 변환
    return '등록에 실패했습니다. 잠시 후 다시 시도해주세요.';
  }
}
```

### 6. `lib/features/supplement/presentation/screens/supplement_capture_screen.dart`

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_cropper/image_cropper.dart';
import 'package:image_picker/image_picker.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../../../shared/widgets/app_error.dart';
import '../../../../shared/widgets/disclaimer.dart';
import '../providers/supplement_provider.dart';
import '../widgets/source_selector.dart';
import '../widgets/upload_progress.dart';

/// 영양제 사진 등록 화면.
class SupplementCaptureScreen extends ConsumerWidget {
  const SupplementCaptureScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(supplementNotifierProvider);

    // 성공 시 결과 화면으로 자동 이동
    ref.listen<SupplementState>(supplementNotifierProvider, (prev, next) {
      if (next is SuccessState) {
        context.pushReplacement('/supplement/result',
            extra: next.response);
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('영양제 등록')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Expanded(child: _buildBody(context, ref, state)),
            const MedicalDisclaimer(variant: DisclaimerVariant.supplement),
          ],
        ),
      ),
    );
  }

  Widget _buildBody(
    BuildContext context,
    WidgetRef ref,
    SupplementState state,
  ) {
    return switch (state) {
      IdleState() => SourceSelector(
          onCamera: () => _pickAndUpload(context, ref, ImageSource.camera),
          onGallery: () => _pickAndUpload(context, ref, ImageSource.gallery),
        ),
      UploadingState(:final progress) => UploadProgress(progress: progress),
      ErrorState(:final message) => AppError(
          message: message,
          onRetry: () => ref
              .read(supplementNotifierProvider.notifier)
              .reset(),
        ),
      SuccessState() => const SizedBox.shrink(),
    };
  }

  Future<void> _pickAndUpload(
    BuildContext context,
    WidgetRef ref,
    ImageSource source,
  ) async {
    // 1. 권한 요청
    final permission = source == ImageSource.camera
        ? Permission.camera
        : Permission.photos;
    final status = await permission.request();
    if (!status.isGranted) {
      if (!context.mounted) return;
      _showPermissionDeniedDialog(context, source);
      return;
    }

    // 2. 사진 선택
    final picker = ImagePicker();
    final pickedFile = await picker.pickImage(
      source: source,
      maxWidth: 2048,
      imageQuality: 85,
    );
    if (pickedFile == null) return;

    // 3. 크롭
    final cropped = await ImageCropper().cropImage(
      sourcePath: pickedFile.path,
      aspectRatio: const CropAspectRatio(ratioX: 1, ratioY: 1),
      compressFormat: ImageCompressFormat.jpg,
      compressQuality: 85,
      uiSettings: [
        AndroidUiSettings(
          toolbarTitle: '영양제 라벨 영역 조정',
          lockAspectRatio: false,
        ),
        IOSUiSettings(title: '영양제 라벨 영역 조정'),
      ],
    );
    if (cropped == null) return;

    // 4. 업로드
    if (!context.mounted) return;
    await ref
        .read(supplementNotifierProvider.notifier)
        .register(cropped.path);
  }

  void _showPermissionDeniedDialog(
    BuildContext context,
    ImageSource source,
  ) {
    final what = source == ImageSource.camera ? '카메라' : '사진 보관함';
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('$what 권한이 필요합니다'),
        content: Text(
          '$what 사용을 허용하면 영양제 라벨 사진을 등록할 수 있습니다. '
          '설정에서 권한을 변경해주세요.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.pop(ctx);
              openAppSettings();
            },
            child: const Text('설정으로 이동'),
          ),
        ],
      ),
    );
  }
}
```

### 7. `lib/features/supplement/presentation/widgets/source_selector.dart`

```dart
import 'package:flutter/material.dart';

/// 카메라/갤러리 선택 카드.
class SourceSelector extends StatelessWidget {
  const SourceSelector({
    super.key,
    required this.onCamera,
    required this.onGallery,
  });

  final VoidCallback onCamera;
  final VoidCallback onGallery;

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: [
        const SizedBox(height: 24),
        Text(
          '영양제 라벨 사진을 등록해주세요',
          style: Theme.of(context).textTheme.titleLarge,
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 8),
        Text(
          '제품명, 성분, 함량이 잘 보이는 사진을 선택해주세요.',
          style: Theme.of(context).textTheme.bodyMedium,
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 32),
        _SourceCard(
          icon: Icons.camera_alt,
          label: '카메라로 촬영',
          onTap: onCamera,
        ),
        const SizedBox(height: 16),
        _SourceCard(
          icon: Icons.photo_library,
          label: '갤러리에서 선택',
          onTap: onGallery,
        ),
      ],
    );
  }
}

class _SourceCard extends StatelessWidget {
  const _SourceCard({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              Icon(icon, size: 32),
              const SizedBox(width: 16),
              Text(label, style: Theme.of(context).textTheme.titleMedium),
            ],
          ),
        ),
      ),
    );
  }
}
```

### 8. `lib/features/supplement/presentation/widgets/upload_progress.dart`

```dart
import 'package:flutter/material.dart';

/// 업로드 진행률 표시.
class UploadProgress extends StatelessWidget {
  const UploadProgress({super.key, required this.progress});

  final double progress;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          SizedBox(
            width: 80,
            height: 80,
            child: CircularProgressIndicator(
              value: progress > 0 ? progress : null,
              strokeWidth: 6,
            ),
          ),
          const SizedBox(height: 24),
          Text(
            progress < 1.0
                ? '업로드 중... ${(progress * 100).toInt()}%'
                : '분석 중입니다...\n잠시만 기다려주세요',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyLarge,
          ),
          const SizedBox(height: 16),
          if (progress >= 1.0)
            const Text(
              '영양제 성분 인식과 분석에는 약 5초가 소요됩니다.',
              textAlign: TextAlign.center,
            ),
        ],
      ),
    );
  }
}
```

---

## 🧪 테스트

### 위젯 테스트

```dart
// test/widget/supplement/source_selector_test.dart
testWidgets('SourceSelector calls callbacks', (tester) async {
  var cameraTapped = false;
  var galleryTapped = false;

  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: SourceSelector(
          onCamera: () => cameraTapped = true,
          onGallery: () => galleryTapped = true,
        ),
      ),
    ),
  );

  await tester.tap(find.text('카메라로 촬영'));
  expect(cameraTapped, isTrue);

  await tester.tap(find.text('갤러리에서 선택'));
  expect(galleryTapped, isTrue);
});

testWidgets('UploadProgress shows percentage', (tester) async {
  await tester.pumpWidget(
    const MaterialApp(home: Scaffold(body: UploadProgress(progress: 0.65))),
  );
  expect(find.text('업로드 중... 65%'), findsOneWidget);
});
```

### Provider 테스트

```dart
// test/unit/supplement/supplement_provider_test.dart
test('SupplementNotifier transitions Idle → Uploading → Success', () async {
  final mockRepo = MockRepo();
  when(() => mockRepo.register(...)).thenAnswer((_) async => fakeResponse);

  final container = ProviderContainer(
    overrides: [
      supplementRepositoryProvider.overrideWithValue(mockRepo),
    ],
  );

  expect(container.read(supplementNotifierProvider), isA<IdleState>());

  await container
      .read(supplementNotifierProvider.notifier)
      .register('/path/to/image.jpg');

  expect(container.read(supplementNotifierProvider), isA<SuccessState>());
});
```

### 통합 테스트 (E2E)

```dart
// integration_test/supplement_flow_test.dart
import 'package:patrol/patrol.dart';

void main() {
  patrolTest('영양제 등록 전체 흐름', (PatrolTester $) async {
    await $.pumpWidget(const ProviderScope(child: LemonHealthcareApp()));

    // 메인 → 영양제 등록 진입
    await $('영양제 등록').tap();

    // 갤러리 선택
    await $('갤러리에서 선택').tap();
    await $.native.grantPermissionWhenInUse();

    // (사진 선택은 시뮬레이터/디바이스 환경에 의존)
    // ...

    // 결과 화면 검증
    await $('성분 분석 결과').waitUntilVisible();
  });
}
```

---

## ✅ Definition of Done

- [ ] `Info.plist` + `AndroidManifest.xml` 권한·설명 추가
- [ ] Freezed 모델 + 생성 코드
- [ ] `SupplementRepository` (Dio multipart)
- [ ] `SupplementNotifier` (4가지 상태: Idle/Uploading/Success/Error)
- [ ] `SupplementCaptureScreen` (카메라/갤러리 + 권한 + 크롭 + 업로드)
- [ ] `SourceSelector`, `UploadProgress` 위젯
- [ ] 권한 거부 시 설정 이동 다이얼로그
- [ ] 면책 고지 위젯 화면 하단에 필수 배치
- [ ] 단위 테스트 + 위젯 테스트
- [ ] (선택) Patrol E2E 테스트
- [ ] iOS/Android 양쪽에서 정상 동작 확인
- [ ] `flutter analyze` 통과 + `flutter test` 통과

---

## 💡 구현 팁

### 권한 요청 흐름

```
1. 사용자가 버튼 탭
2. permission_handler로 권한 요청
3. 권한 거부 시 친절한 설명 + 설정 이동 옵션
4. 권한 허락 시 image_picker 호출
```

### 에러 메시지 사용자 친화

```dart
String _mapError(Object e) {
  if (e is DioException) {
    switch (e.response?.statusCode) {
      case 400:
        return '이미지 형식 또는 크기에 문제가 있습니다.';
      case 401:
        return '로그인이 필요합니다.';
      case 422:
        return '영양제 정보를 인식하지 못했습니다. 다른 사진으로 시도해주세요.';
      case 500:
        return '서버 오류입니다. 잠시 후 다시 시도해주세요.';
    }
    if (e.type == DioExceptionType.connectionTimeout) {
      return '네트워크 연결이 느립니다. Wi-Fi 환경에서 시도해주세요.';
    }
  }
  return '예상치 못한 오류가 발생했습니다.';
}
```

### sealed class + switch 표현식

Dart 3+ sealed class 활용으로 컴파일 시 모든 상태 처리 강제:

```dart
return switch (state) {
  IdleState() => ...,
  UploadingState() => ...,
  SuccessState() => ...,
  ErrorState() => ...,
  // 새 상태 추가 시 컴파일 에러로 누락 방지
};
```

---

## 🚫 이 작업에서 하지 말 것

- ❌ 결과 화면 내부 디자인 깊이 들어가기 (가이드 13에서)
- ❌ HealthKit 통합 (가이드 12)
- ❌ 라우터에 결과 화면 등록만 하고 화면은 다음 작업에서 채움 OK

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md)
- [`/mobile/CLAUDE.md`](../../mobile/CLAUDE.md)
- [`/docs/Nutrition-docs/10-compliance-checklist.md §5.2`](../10-compliance-checklist.md) — 권한 정책
- 이전: [`10-mobile-flutter-setup.md`](./10-mobile-flutter-setup.md)
- 다음: [`12-mobile-healthkit-integration.md`](./12-mobile-healthkit-integration.md)
