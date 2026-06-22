# dev-guides/20 — 식단 입력 화면 (텍스트 + 이미지)

> **Phase**: 3 | **선행 작업**: [`16-meal-recognition.md`](./16-meal-recognition.md), [`11-mobile-camera-screen.md`](./11-mobile-camera-screen.md) | **예상 소요**: 3~4시간

---

## 🎯 작업 목표

사용자가 식사 정보를 텍스트 또는 사진으로 입력하면 백엔드 LLM이 분석하여 영양소로 변환하는 화면을 구현한다. 입력 → 인식 결과 미리보기 → 사용자 수정 → 저장 흐름.

---

## 📋 산출물

```
mobile/
└── lib/features/meal/
    ├── data/
    │   └── meal_repository.dart
    ├── domain/
    │   └── meal_models.dart                  # Freezed
    └── presentation/
        ├── screens/
        │   ├── meal_input_screen.dart        # 메인 (텍스트/이미지 선택)
        │   └── meal_review_screen.dart       # 인식 결과 미리보기
        ├── widgets/
        │   ├── input_method_selector.dart    # 텍스트/사진 토글
        │   ├── meal_text_input.dart          # 텍스트 입력
        │   ├── meal_image_picker.dart        # 사진 선택 (가이드 11 패턴)
        │   ├── meal_item_editable.dart       # 수정 가능한 음식 항목
        │   └── meal_summary.dart             # 칼로리·영양소 요약
        └── providers/
            └── meal_provider.dart
```

---

## 📐 화면 흐름

```
┌──────────────────────┐
│ 식단 입력             │
├──────────────────────┤
│ ① 텍스트   ② 사진     │  ← 입력 방식 토글
├──────────────────────┤
│                      │
│ [텍스트 모드]          │
│ ┌────────────────┐   │
│ │ 점심: 공기밥 1개,│   │
│ │ 김치찌개 1그릇  │   │
│ │ 계란말이 1개    │   │
│ └────────────────┘   │
│                      │
│ [분석하기] 버튼        │
│                      │
└──────────────────────┘
         │
         ▼ 백엔드 호출
┌──────────────────────┐
│ 인식 결과 확인         │
├──────────────────────┤
│ 점심                  │
│ ─────────────         │
│ ◉ 공기밥 1공기 (210g) │  ← 수정 가능
│ ◉ 김치찌개 1그릇(300g)│
│ ◉ 계란말이 1개  (80g) │
│                      │
│ + 음식 추가           │
│                      │
│ [영양소 요약]          │
│ 칼로리 약 670kcal     │
│ 단백질 28g 탄수 75g... │
│                      │
│ [저장하기]            │
│                      │
│ [면책 고지]           │
└──────────────────────┘
```

---

## 🔧 구현 명세

### 1. Freezed 모델

```dart
// lib/features/meal/domain/meal_models.dart
import 'package:freezed_annotation/freezed_annotation.dart';

part 'meal_models.freezed.dart';
part 'meal_models.g.dart';

/// 인식된 음식 한 개.
@freezed
class MealItem with _$MealItem {
  const factory MealItem({
    required String nameKo,
    required String estimatedAmount,
    required double estimatedGrams,
  }) = _MealItem;

  factory MealItem.fromJson(Map<String, dynamic> json) =>
      _$MealItemFromJson(json);
}

/// 인식된 식사 전체.
@freezed
class RecognizedMeal with _$RecognizedMeal {
  const factory RecognizedMeal({
    required String mealType,
    required List<MealItem> items,
    required String engine,
  }) = _RecognizedMeal;

  factory RecognizedMeal.fromJson(Map<String, dynamic> json) =>
      _$RecognizedMealFromJson(json);
}

/// 식단 등록 응답 (영양소 분석 포함).
@freezed
class MealRegistration with _$MealRegistration {
  const factory MealRegistration({
    required String mealId,
    required RecognizedMeal recognized,
    required double estimatedKcal,
    required Map<String, double> nutrientSummary,
  }) = _MealRegistration;

  factory MealRegistration.fromJson(Map<String, dynamic> json) =>
      _$MealRegistrationFromJson(json);
}
```

### 2. Repository

```dart
// lib/features/meal/data/meal_repository.dart
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../core/network/dio_provider.dart';
import '../domain/meal_models.dart';

part 'meal_repository.g.dart';

class MealRepository {
  MealRepository(this._dio);
  final Dio _dio;

  /// 텍스트로 식단 인식 요청.
  Future<RecognizedMeal> recognizeFromText(String text) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/meals/recognize/text',
      data: {'text': text},
    );
    return RecognizedMeal.fromJson(response.data!);
  }

  /// 이미지로 식단 인식 요청.
  Future<RecognizedMeal> recognizeFromImage({
    required String imagePath,
    void Function(double)? onProgress,
  }) async {
    final formData = FormData.fromMap({
      'image': await MultipartFile.fromFile(imagePath, filename: 'meal.jpg'),
    });
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/meals/recognize/image',
      data: formData,
      onSendProgress: (s, t) {
        if (t > 0) onProgress?.call(s / t);
      },
    );
    return RecognizedMeal.fromJson(response.data!);
  }

  /// 사용자 확인 후 최종 저장 (영양소 분석 포함).
  Future<MealRegistration> saveMeal(RecognizedMeal meal) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/api/v1/meals',
      data: meal.toJson(),
    );
    return MealRegistration.fromJson(response.data!);
  }
}

@riverpod
MealRepository mealRepository(MealRepositoryRef ref) {
  return MealRepository(ref.watch(dioProvider));
}
```

### 3. State + Provider

```dart
// lib/features/meal/presentation/providers/meal_provider.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../data/meal_repository.dart';
import '../../domain/meal_models.dart';

part 'meal_provider.g.dart';

sealed class MealState {
  const MealState();
}

class MealIdle extends MealState {
  const MealIdle();
}

class MealRecognizing extends MealState {
  const MealRecognizing(this.progress);
  final double progress;
}

class MealReviewing extends MealState {
  const MealReviewing(this.meal);
  final RecognizedMeal meal;
}

class MealSaving extends MealState {
  const MealSaving();
}

class MealSaved extends MealState {
  const MealSaved(this.registration);
  final MealRegistration registration;
}

class MealError extends MealState {
  const MealError(this.message);
  final String message;
}

@riverpod
class MealNotifier extends _$MealNotifier {
  @override
  MealState build() => const MealIdle();

  Future<void> recognizeText(String text) async {
    if (text.trim().isEmpty) {
      state = const MealError('식사 내용을 입력해주세요');
      return;
    }
    state = const MealRecognizing(0);
    try {
      final meal = await ref.read(mealRepositoryProvider).recognizeFromText(text);
      state = MealReviewing(meal);
    } catch (e) {
      state = MealError(_mapError(e));
    }
  }

  Future<void> recognizeImage(String imagePath) async {
    state = const MealRecognizing(0);
    try {
      final meal = await ref.read(mealRepositoryProvider).recognizeFromImage(
            imagePath: imagePath,
            onProgress: (p) => state = MealRecognizing(p),
          );
      state = MealReviewing(meal);
    } catch (e) {
      state = MealError(_mapError(e));
    }
  }

  /// 사용자 수정 반영.
  void updateItems(List<MealItem> updatedItems) {
    final current = state;
    if (current is MealReviewing) {
      state = MealReviewing(current.meal.copyWith(items: updatedItems));
    }
  }

  /// 최종 저장.
  Future<void> save() async {
    final current = state;
    if (current is! MealReviewing) return;
    state = const MealSaving();
    try {
      final reg = await ref.read(mealRepositoryProvider).saveMeal(current.meal);
      state = MealSaved(reg);
    } catch (e) {
      state = MealError(_mapError(e));
    }
  }

  void reset() => state = const MealIdle();

  String _mapError(Object e) {
    if (e is DioException) {
      switch (e.response?.statusCode) {
        case 400: return '입력에 문제가 있습니다.';
        case 422: return '음식을 인식하지 못했습니다.';
        case 500: return '서버 오류입니다.';
      }
    }
    return '알 수 없는 오류가 발생했습니다.';
  }
}
```

### 4. 입력 화면

```dart
// lib/features/meal/presentation/screens/meal_input_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../../../../shared/widgets/disclaimer.dart';
import '../providers/meal_provider.dart';
import '../widgets/input_method_selector.dart';
import '../widgets/meal_text_input.dart';
import '../widgets/meal_image_picker.dart';

/// 식단 입력 메인 화면.
class MealInputScreen extends ConsumerStatefulWidget {
  const MealInputScreen({super.key});

  @override
  ConsumerState<MealInputScreen> createState() => _MealInputScreenState();
}

class _MealInputScreenState extends ConsumerState<MealInputScreen> {
  InputMethod _method = InputMethod.text;
  final _textController = TextEditingController();

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(mealNotifierProvider);

    // 인식 완료 시 미리보기 화면으로 이동
    ref.listen<MealState>(mealNotifierProvider, (_, next) {
      if (next is MealReviewing) {
        context.push('/meal/review');
      } else if (next is MealError) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(next.message)),
        );
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('식단 입력')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            InputMethodSelector(
              method: _method,
              onChanged: (m) => setState(() => _method = m),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: switch (_method) {
                InputMethod.text => MealTextInput(
                    controller: _textController,
                    isLoading: state is MealRecognizing,
                    onSubmit: () => ref
                        .read(mealNotifierProvider.notifier)
                        .recognizeText(_textController.text),
                  ),
                InputMethod.image => MealImagePicker(
                    isLoading: state is MealRecognizing,
                    onPicked: (path) => ref
                        .read(mealNotifierProvider.notifier)
                        .recognizeImage(path),
                  ),
              },
            ),
            const MedicalDisclaimer(variant: DisclaimerVariant.main),
          ],
        ),
      ),
    );
  }
}
```

### 5. 입력 방식 토글

```dart
// lib/features/meal/presentation/widgets/input_method_selector.dart
import 'package:flutter/material.dart';

enum InputMethod { text, image }

class InputMethodSelector extends StatelessWidget {
  const InputMethodSelector({
    super.key,
    required this.method,
    required this.onChanged,
  });

  final InputMethod method;
  final ValueChanged<InputMethod> onChanged;

  @override
  Widget build(BuildContext context) {
    return SegmentedButton<InputMethod>(
      segments: const [
        ButtonSegment(
          value: InputMethod.text,
          label: Text('텍스트로 입력'),
          icon: Icon(Icons.edit),
        ),
        ButtonSegment(
          value: InputMethod.image,
          label: Text('사진으로 입력'),
          icon: Icon(Icons.camera_alt),
        ),
      ],
      selected: {method},
      onSelectionChanged: (s) => onChanged(s.first),
    );
  }
}
```

### 6. 텍스트 입력 위젯

```dart
// lib/features/meal/presentation/widgets/meal_text_input.dart
import 'package:flutter/material.dart';

class MealTextInput extends StatelessWidget {
  const MealTextInput({
    super.key,
    required this.controller,
    required this.isLoading,
    required this.onSubmit,
  });

  final TextEditingController controller;
  final bool isLoading;
  final VoidCallback onSubmit;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          controller: controller,
          maxLines: 6,
          enabled: !isLoading,
          decoration: const InputDecoration(
            hintText: '예: 점심 — 공기밥 1개, 김치찌개 1그릇, 계란말이 1개',
            border: OutlineInputBorder(),
            alignLabelWithHint: true,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          '음식 이름과 양을 자유롭게 적어주세요',
          style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
        ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: isLoading ? null : onSubmit,
          icon: isLoading
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.auto_awesome),
          label: Text(isLoading ? 'AI 분석 중...' : '분석하기'),
        ),
      ],
    );
  }
}
```

### 7. 이미지 선택 위젯

```dart
// lib/features/meal/presentation/widgets/meal_image_picker.dart
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:permission_handler/permission_handler.dart';

class MealImagePicker extends StatelessWidget {
  const MealImagePicker({
    super.key,
    required this.isLoading,
    required this.onPicked,
  });

  final bool isLoading;
  final ValueChanged<String> onPicked;

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('사진에서 음식을 인식하는 중...'),
          ],
        ),
      );
    }

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.restaurant, size: 64, color: Colors.grey),
          const SizedBox(height: 16),
          const Text('식사 사진을 선택해주세요'),
          const SizedBox(height: 24),
          Wrap(
            spacing: 12,
            children: [
              FilledButton.icon(
                onPressed: () => _pick(context, ImageSource.camera),
                icon: const Icon(Icons.camera_alt),
                label: const Text('카메라'),
              ),
              FilledButton.icon(
                onPressed: () => _pick(context, ImageSource.gallery),
                icon: const Icon(Icons.photo_library),
                label: const Text('갤러리'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _pick(BuildContext context, ImageSource source) async {
    // 권한 요청 (가이드 11과 동일)
    final perm = source == ImageSource.camera
        ? Permission.camera
        : Permission.photos;
    final status = await perm.request();
    if (!status.isGranted) return;

    final picked = await ImagePicker().pickImage(
      source: source,
      maxWidth: 2048,
      imageQuality: 85,
    );
    if (picked != null) onPicked(picked.path);
  }
}
```

### 8. 미리보기·수정 화면

```dart
// lib/features/meal/presentation/screens/meal_review_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../shared/widgets/disclaimer.dart';
import '../providers/meal_provider.dart';
import '../widgets/meal_item_editable.dart';

class MealReviewScreen extends ConsumerWidget {
  const MealReviewScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(mealNotifierProvider);

    if (state is! MealReviewing) {
      return const Scaffold(
        body: Center(child: Text('인식된 식단이 없습니다.')),
      );
    }

    final items = state.meal.items;

    ref.listen<MealState>(mealNotifierProvider, (_, next) {
      if (next is MealSaved) {
        context.go('/meal/saved/${next.registration.mealId}');
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('인식 결과 확인')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  const Icon(Icons.info_outline, color: Colors.blue),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '인식된 음식과 양을 확인해주세요. 잘못된 부분은 수정할 수 있습니다.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            _mealTypeLabel(state.meal.mealType),
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          ...List.generate(items.length, (i) => MealItemEditable(
                item: items[i],
                onChanged: (updated) {
                  final newList = [...items]..[i] = updated;
                  ref.read(mealNotifierProvider.notifier).updateItems(newList);
                },
                onDelete: () {
                  final newList = [...items]..removeAt(i);
                  ref.read(mealNotifierProvider.notifier).updateItems(newList);
                },
              )),
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: () {/* 음식 추가 다이얼로그 */},
            icon: const Icon(Icons.add),
            label: const Text('음식 추가'),
          ),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: items.isEmpty
                ? null
                : () => ref.read(mealNotifierProvider.notifier).save(),
            child: const Text('저장하기'),
          ),
          const SizedBox(height: 16),
          const MedicalDisclaimer(variant: DisclaimerVariant.main),
        ],
      ),
    );
  }

  String _mealTypeLabel(String type) => switch (type) {
        'breakfast' => '아침',
        'lunch' => '점심',
        'dinner' => '저녁',
        _ => '간식',
      };
}
```

### 9. 수정 가능한 음식 항목

```dart
// lib/features/meal/presentation/widgets/meal_item_editable.dart
import 'package:flutter/material.dart';

import '../../domain/meal_models.dart';

class MealItemEditable extends StatelessWidget {
  const MealItemEditable({
    super.key,
    required this.item,
    required this.onChanged,
    required this.onDelete,
  });

  final MealItem item;
  final ValueChanged<MealItem> onChanged;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.nameKo,
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${item.estimatedAmount} (약 ${item.estimatedGrams.toInt()}g)',
                    style: const TextStyle(fontSize: 12, color: Colors.grey),
                  ),
                ],
              ),
            ),
            IconButton(
              icon: const Icon(Icons.edit, size: 20),
              onPressed: () => _showEditDialog(context),
            ),
            IconButton(
              icon: const Icon(Icons.delete_outline, size: 20),
              onPressed: onDelete,
            ),
          ],
        ),
      ),
    );
  }

  void _showEditDialog(BuildContext context) {
    final nameController = TextEditingController(text: item.nameKo);
    final gramsController = TextEditingController(
      text: item.estimatedGrams.toInt().toString(),
    );

    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('음식 수정'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: nameController,
              decoration: const InputDecoration(labelText: '음식 이름'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: gramsController,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: '양 (g)',
                suffixText: 'g',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: () {
              final newGrams = double.tryParse(gramsController.text) ?? item.estimatedGrams;
              onChanged(item.copyWith(
                nameKo: nameController.text,
                estimatedGrams: newGrams,
              ));
              Navigator.pop(ctx);
            },
            child: const Text('저장'),
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
testWidgets('Toggle switches between text and image input', (tester) async {
  await tester.pumpWidget(
    const ProviderScope(
      child: MaterialApp(home: MealInputScreen()),
    ),
  );

  expect(find.byType(MealTextInput), findsOneWidget);

  await tester.tap(find.text('사진으로 입력'));
  await tester.pump();

  expect(find.byType(MealImagePicker), findsOneWidget);
});

testWidgets('Empty text shows error', (tester) async {
  // ... text input empty + submit
  expect(find.text('식사 내용을 입력해주세요'), findsOneWidget);
});

testWidgets('Edit dialog updates item grams', (tester) async {
  // ...
  await tester.tap(find.byIcon(Icons.edit).first);
  await tester.enterText(find.widgetWithText(TextField, '양 (g)'), '300');
  await tester.tap(find.text('저장'));
  // verify: onChanged called with grams=300
});

testWidgets('Delete removes item from list', (tester) async {
  // ...
  await tester.tap(find.byIcon(Icons.delete_outline).first);
  // verify: items.length decreased
});
```

### Provider 테스트

```dart
test('MealNotifier transitions Idle → Recognizing → Reviewing', () async {
  final mockRepo = MockMealRepo();
  when(() => mockRepo.recognizeFromText(any()))
      .thenAnswer((_) async => fakeMeal);

  final container = ProviderContainer(
    overrides: [mealRepositoryProvider.overrideWithValue(mockRepo)],
  );

  expect(container.read(mealNotifierProvider), isA<MealIdle>());
  await container.read(mealNotifierProvider.notifier).recognizeText('밥 1공기');
  expect(container.read(mealNotifierProvider), isA<MealReviewing>());
});

test('updateItems modifies state in MealReviewing', () async {
  // ... state to MealReviewing
  // updateItems with new list
  // verify state.meal.items == newList
});
```

### E2E 테스트 (Patrol)

```dart
patrolTest('식단 텍스트 입력 → 인식 → 수정 → 저장', (PatrolTester $) async {
  await $.pumpWidget(const ProviderScope(child: LemonHealthcareApp()));

  await $('식단 입력').tap();
  await $.enterText(
    find.byType(TextField),
    '점심: 공기밥 1개, 김치찌개 1그릇',
  );
  await $('분석하기').tap();

  await $('인식 결과 확인').waitUntilVisible();
  expect($.tester.widget<List>(...).length, greaterThan(0));

  await $('저장하기').tap();
  await $('저장됨').waitUntilVisible();
});
```

---

## ✅ Definition of Done

- [ ] Freezed 모델 (MealItem, RecognizedMeal, MealRegistration)
- [ ] `MealRepository` (텍스트·이미지 인식 + 저장)
- [ ] `MealNotifier` (6가지 상태)
- [ ] `MealInputScreen` (토글 + 텍스트/이미지)
- [ ] `MealReviewScreen` (수정 + 저장)
- [ ] `InputMethodSelector`, `MealTextInput`, `MealImagePicker`
- [ ] `MealItemEditable` (수정 + 삭제)
- [ ] **MedicalDisclaimer 모든 화면 하단**
- [ ] 라우팅: `/meal`, `/meal/review`
- [ ] 위젯 테스트 + Provider 테스트
- [ ] (선택) Patrol E2E
- [ ] iOS/Android 양쪽 정상 동작
- [ ] `flutter analyze` + `flutter test` 통과

---

## 💡 구현 팁

### 사용자 수정 가능성 강조

LLM 인식이 100% 정확하지 않으므로, **수정 UI를 누구나 쉽게 발견** 할 수 있도록 설계:
- ✏ 연필 아이콘 명확히
- 🗑 삭제 아이콘
- "+ 음식 추가" 버튼

### 텍스트 입력 가이드

```
✅ 좋은 예시 (LLM이 잘 인식):
  "점심 — 공기밥 1개, 김치찌개 1그릇, 계란말이 1개"
  "아침: 토스트 2장, 우유 1컵"

❌ 어려운 예시:
  "맛있는 한식 먹었음"
  "점심에 뭐 먹었지... 밥이랑 반찬"
```

### 비용 관리

- 텍스트는 이미지보다 10배 저렴 → 기본값
- 이미지는 부정확하면 사용자가 결과 보고 텍스트로 보충 가능

---

## 🚫 이 작업에서 하지 말 것

- ❌ 식단 칼로리 직접 계산 (백엔드 영양소 합산만)
- ❌ "이 식단은 좋다/나쁘다" 평가
- ❌ 영양제 추천 (다른 화면에서)

---

## 🔗 관련 문서

- [`/mobile/CLAUDE.md`](../../mobile/CLAUDE.md)
- 이전: [`19-mobile-goal-analysis-screen.md`](./19-mobile-goal-analysis-screen.md)
- 다음: [`21-mobile-feedback-ui.md`](./21-mobile-feedback-ui.md)
