# dev-guides/21 — 피드백 UI + Pull-to-refresh + 알림 등록

> **Phase**: 3 | **선행 작업**: [`17-feedback-and-notifications.md`](./17-feedback-and-notifications.md), [`13-mobile-dashboard.md`](./13-mobile-dashboard.md) | **예상 소요**: 3~4시간

---

## 🎯 작업 목표

사용자가 인식 결과나 분석 결과에 대해 평가할 수 있는 **피드백 UI**, 모든 데이터 화면에 통합된 **Pull-to-refresh**, FCM/APNs **푸시 토큰 등록** 흐름을 구현하여 Phase 3을 마무리한다.

---

## 📋 산출물

```
mobile/
├── lib/
│   ├── features/feedback/
│   │   ├── data/feedback_repository.dart
│   │   ├── domain/feedback_models.dart
│   │   └── presentation/
│   │       ├── widgets/
│   │       │   ├── feedback_dialog.dart        # 평점 + 코멘트 다이얼로그
│   │       │   ├── star_rating.dart            # 별점 위젯
│   │       │   └── inline_feedback_button.dart # 화면 내 피드백 트리거
│   │       └── providers/feedback_provider.dart
│   │
│   └── core/
│       └── notifications/
│           ├── push_token_service.dart         # FCM/APNs 토큰 획득·등록
│           └── push_token_provider.dart
│
├── ios/Runner/
│   ├── Info.plist                              # ⭐ 알림 권한
│   └── AppDelegate.swift                       # APNs 등록
│
└── android/app/src/main/
    └── AndroidManifest.xml                    # ⭐ POST_NOTIFICATIONS
```

---

## 📐 사용 시나리오

### 시나리오 1: 영양제 등록 직후 피드백

```
영양제 등록 완료 → "성분 인식이 정확했나요?" 자동 표시
                  → 별점 1~5 + (선택) 코멘트
                  → 백엔드 저장 → 닫기
```

### 시나리오 2: Pull-to-refresh

```
대시보드/영양/체중/활동/목적별 분석 등 데이터 화면
  → 사용자가 위에서 아래로 당김
  → ref.invalidate(...) 트리거
  → 백엔드 재조회 → 최신 데이터 표시
```

### 시나리오 3: 알림 토큰 등록

```
앱 시작 → 알림 권한 확인 (없으면 요청)
       → FCM/APNs 토큰 획득
       → POST /api/v1/devices 로 백엔드 등록
       → 토큰 갱신 시 자동 재등록
```

---

## 🔧 구현 명세

### 1. 피드백 모델

```dart
// lib/features/feedback/domain/feedback_models.dart
import 'package:freezed_annotation/freezed_annotation.dart';

part 'feedback_models.freezed.dart';
part 'feedback_models.g.dart';

enum FeedbackType {
  ocrAccuracy,
  llmParsing,
  mealRecognition,
  goalAnalysis,
  weightPrediction,
  general,
}

extension FeedbackTypeX on FeedbackType {
  String get apiCode => switch (this) {
    FeedbackType.ocrAccuracy => 'ocr_accuracy',
    FeedbackType.llmParsing => 'llm_parsing',
    FeedbackType.mealRecognition => 'meal_recognition',
    FeedbackType.goalAnalysis => 'goal_analysis',
    FeedbackType.weightPrediction => 'weight_prediction',
    FeedbackType.general => 'general',
  };

  String get questionKo => switch (this) {
    FeedbackType.ocrAccuracy => '영양제 성분이 정확하게 인식되었나요?',
    FeedbackType.llmParsing => '영양제 정보 분석이 도움이 되셨나요?',
    FeedbackType.mealRecognition => '식단이 정확하게 인식되었나요?',
    FeedbackType.goalAnalysis => '목적별 분석 결과가 유용했나요?',
    FeedbackType.weightPrediction => '체중 예측이 합리적이었나요?',
    FeedbackType.general => '앱 사용 경험은 어떠셨나요?',
  };
}

@freezed
class FeedbackRequest with _$FeedbackRequest {
  const factory FeedbackRequest({
    required String type,
    required int rating,
    String? comment,
    @JsonKey(name: 'context_id') String? contextId,
    Map<String, dynamic>? metadata,
  }) = _FeedbackRequest;

  factory FeedbackRequest.fromJson(Map<String, dynamic> json) =>
      _$FeedbackRequestFromJson(json);
}
```

### 2. 피드백 Repository

```dart
// lib/features/feedback/data/feedback_repository.dart
import 'package:dio/dio.dart';

class FeedbackRepository {
  FeedbackRepository(this._dio);
  final Dio _dio;

  Future<void> submit({
    required FeedbackType type,
    required int rating,
    String? comment,
    String? contextId,
    Map<String, dynamic>? metadata,
  }) async {
    await _dio.post<void>('/api/v1/feedback', data: {
      'type': type.apiCode,
      'rating': rating,
      if (comment != null) 'comment': comment,
      if (contextId != null) 'context_id': contextId,
      if (metadata != null) 'metadata': metadata,
    });
  }
}
```

### 3. 별점 위젯

```dart
// lib/features/feedback/presentation/widgets/star_rating.dart
import 'package:flutter/material.dart';

class StarRating extends StatelessWidget {
  const StarRating({
    super.key,
    required this.rating,
    required this.onChanged,
    this.size = 36,
  });

  final int rating;
  final ValueChanged<int> onChanged;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: List.generate(5, (i) {
        final filled = i < rating;
        return IconButton(
          onPressed: () => onChanged(i + 1),
          icon: Icon(
            filled ? Icons.star : Icons.star_border,
            size: size,
            color: filled ? Colors.amber : Colors.grey,
          ),
          padding: EdgeInsets.zero,
          constraints: BoxConstraints.tight(Size(size + 8, size + 8)),
        );
      }),
    );
  }
}
```

### 4. 피드백 다이얼로그

```dart
// lib/features/feedback/presentation/widgets/feedback_dialog.dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/feedback_repository.dart';
import '../../domain/feedback_models.dart';
import 'star_rating.dart';

class FeedbackDialog extends ConsumerStatefulWidget {
  const FeedbackDialog({
    super.key,
    required this.type,
    this.contextId,
    this.metadata,
  });

  final FeedbackType type;
  final String? contextId;
  final Map<String, dynamic>? metadata;

  /// 다이얼로그 헬퍼.
  static Future<bool?> show(
    BuildContext context, {
    required FeedbackType type,
    String? contextId,
    Map<String, dynamic>? metadata,
  }) {
    return showDialog<bool>(
      context: context,
      builder: (_) => FeedbackDialog(
        type: type,
        contextId: contextId,
        metadata: metadata,
      ),
    );
  }

  @override
  ConsumerState<FeedbackDialog> createState() => _FeedbackDialogState();
}

class _FeedbackDialogState extends ConsumerState<FeedbackDialog> {
  int _rating = 0;
  final _commentController = TextEditingController();
  bool _submitting = false;

  @override
  void dispose() {
    _commentController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_rating == 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('별점을 선택해주세요')),
      );
      return;
    }
    setState(() => _submitting = true);
    try {
      await ref.read(feedbackRepositoryProvider).submit(
            type: widget.type,
            rating: _rating,
            comment: _commentController.text.trim().isEmpty
                ? null
                : _commentController.text.trim(),
            contextId: widget.contextId,
            metadata: widget.metadata,
          );
      if (!mounted) return;
      Navigator.of(context).pop(true);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('피드백 감사합니다!')),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _submitting = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('피드백 전송에 실패했습니다')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.type.questionKo),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          StarRating(
            rating: _rating,
            onChanged: (v) => setState(() => _rating = v),
          ),
          const SizedBox(height: 8),
          if (_rating > 0)
            Text(_ratingLabel(_rating),
                style: const TextStyle(fontSize: 12, color: Colors.grey)),
          const SizedBox(height: 16),
          TextField(
            controller: _commentController,
            maxLines: 3,
            maxLength: 500,
            decoration: const InputDecoration(
              hintText: '추가 의견 (선택)',
              border: OutlineInputBorder(),
            ),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: _submitting ? null : () => Navigator.of(context).pop(false),
          child: const Text('나중에'),
        ),
        FilledButton(
          onPressed: _submitting ? null : _submit,
          child: _submitting
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('보내기'),
        ),
      ],
    );
  }

  String _ratingLabel(int rating) => switch (rating) {
        1 => '많이 부족했어요',
        2 => '아쉬웠어요',
        3 => '보통이에요',
        4 => '좋았어요',
        5 => '매우 좋아요',
        _ => '',
      };
}
```

### 5. 인라인 피드백 버튼 (화면 내 트리거)

```dart
// lib/features/feedback/presentation/widgets/inline_feedback_button.dart
import 'package:flutter/material.dart';

import '../../domain/feedback_models.dart';
import 'feedback_dialog.dart';

class InlineFeedbackButton extends StatelessWidget {
  const InlineFeedbackButton({
    super.key,
    required this.type,
    this.contextId,
  });

  final FeedbackType type;
  final String? contextId;

  @override
  Widget build(BuildContext context) {
    return TextButton.icon(
      onPressed: () => FeedbackDialog.show(
        context,
        type: type,
        contextId: contextId,
      ),
      icon: const Icon(Icons.feedback_outlined, size: 18),
      label: const Text('피드백 보내기'),
      style: TextButton.styleFrom(foregroundColor: Colors.grey.shade700),
    );
  }
}
```

### 6. 푸시 토큰 등록 서비스

```dart
// lib/core/notifications/push_token_service.dart
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:permission_handler/permission_handler.dart';

import '../network/dio_provider.dart';
import '../utils/logger.dart';

class PushTokenService {
  PushTokenService(this._dio);
  final Dio _dio;

  /// 알림 권한 요청 + 토큰 획득 + 백엔드 등록.
  Future<bool> initialize() async {
    // 1. 알림 권한
    final granted = await _requestPermission();
    if (!granted) {
      appLogger.i('Notification permission denied');
      return false;
    }

    // 2. 토큰 획득 (플랫폼별)
    String? token;
    if (Platform.isIOS) {
      // APNs 토큰 → FCM 토큰 변환 (Firebase 사용 시)
      await FirebaseMessaging.instance.requestPermission();
      token = await FirebaseMessaging.instance.getToken();
    } else if (Platform.isAndroid) {
      token = await FirebaseMessaging.instance.getToken();
    }

    if (token == null) {
      appLogger.w('Failed to obtain push token');
      return false;
    }

    // 3. 백엔드 등록
    await _registerToken(token);

    // 4. 토큰 갱신 시 자동 재등록
    FirebaseMessaging.instance.onTokenRefresh.listen(_registerToken);

    return true;
  }

  Future<bool> _requestPermission() async {
    if (Platform.isIOS) {
      final settings = await FirebaseMessaging.instance.requestPermission();
      return settings.authorizationStatus == AuthorizationStatus.authorized;
    } else {
      // Android 13+
      final status = await Permission.notification.request();
      return status.isGranted;
    }
  }

  Future<void> _registerToken(String token) async {
    try {
      await _dio.post<void>('/api/v1/devices', data: {
        'platform': Platform.isIOS ? 'ios' : 'android',
        'token': token,
      });
      appLogger.i('Push token registered');
    } catch (e) {
      appLogger.e('Token registration failed', error: e);
    }
  }
}
```

### 7. 푸시 토큰 Provider

```dart
// lib/core/notifications/push_token_provider.dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../network/dio_provider.dart';
import 'push_token_service.dart';

part 'push_token_provider.g.dart';

@riverpod
PushTokenService pushTokenService(PushTokenServiceRef ref) {
  return PushTokenService(ref.watch(dioProvider));
}

/// 앱 시작 시 1회 초기화.
@riverpod
Future<bool> pushTokenInit(PushTokenInitRef ref) async {
  final service = ref.watch(pushTokenServiceProvider);
  return service.initialize();
}
```

### 8. main.dart 통합

```dart
// lib/main.dart (수정)
import 'package:firebase_core/firebase_core.dart';
import 'firebase_options.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  setupLogger();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  runApp(const ProviderScope(child: LemonHealthcareApp()));
}
```

```dart
// lib/app.dart (수정)
class LemonHealthcareApp extends ConsumerStatefulWidget {
  // ...
}

class _LemonHealthcareAppState extends ConsumerState<LemonHealthcareApp> {
  @override
  void initState() {
    super.initState();
    // 1회만 푸시 토큰 등록 시도
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(pushTokenInitProvider);
    });
  }
  // ...
}
```

### 9. iOS/Android 설정

```xml
<!-- ios/Runner/Info.plist -->
<key>UIBackgroundModes</key>
<array>
  <string>remote-notification</string>
</array>
```

```xml
<!-- android/app/src/main/AndroidManifest.xml -->
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
<uses-permission android:name="android.permission.INTERNET" />
```

### 10. 기존 화면들에 피드백 통합

```dart
// 영양제 결과 화면 (예시 — 기존 코드 추가)
// 가이드 11의 SupplementResultScreen
class SupplementResultScreen extends ConsumerStatefulWidget {
  // ...
}

class _SupplementResultScreenState extends ConsumerState<SupplementResultScreen> {
  bool _feedbackShown = false;

  @override
  Widget build(BuildContext context) {
    // 화면 로드 후 1회만 피드백 다이얼로그 자동 표시
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_feedbackShown) {
        _feedbackShown = true;
        Future.delayed(const Duration(seconds: 2), () {
          if (mounted) {
            FeedbackDialog.show(
              context,
              type: FeedbackType.ocrAccuracy,
              contextId: widget.supplement.supplementId,
              metadata: {
                'ocr_engine': widget.supplement.ocrEngine,
                'llm_engine': widget.supplement.llmEngine,
              },
            );
          }
        });
      }
    });
    // ... 기존 본문
  }
}
```

### 11. Pull-to-refresh 통합 (기존 화면 수정)

```dart
// 모든 데이터 화면에 RefreshIndicator 추가
// 예: NutritionDashboardScreen, ActivityRecommendationScreen, ...

return RefreshIndicator(
  onRefresh: () async {
    ref.invalidate(latestDiagnosisProvider);
    // 추가로 invalidate 할 provider들
  },
  child: ListView(...),
);
```

> ⚠️ Pull-to-refresh는 `ListView`/`CustomScrollView` 등 스크롤 가능한 위젯이 필요. `Column` 으로 감싸지 말 것.

---

## 🧪 테스트

### 위젯 테스트

```dart
testWidgets('StarRating updates on tap', (tester) async {
  int rating = 0;
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      body: StarRating(rating: rating, onChanged: (v) => rating = v),
    ),
  ));

  // 3번째 별 탭 → rating = 3
  await tester.tap(find.byIcon(Icons.star_border).at(2));
  expect(rating, 3);
});

testWidgets('FeedbackDialog blocks submit when no rating', (tester) async {
  // ... show dialog
  await tester.tap(find.text('보내기'));
  expect(find.text('별점을 선택해주세요'), findsOneWidget);
});

testWidgets('FeedbackDialog submits with rating only', (tester) async {
  // ... show dialog, tap 4 stars, tap submit
  // verify: repository.submit called with rating=4, comment=null
});

testWidgets('FeedbackDialog submits with comment', (tester) async {
  // ... rating + comment + submit
});

testWidgets('FeedbackDialog handles network error', (tester) async {
  // ... mock repo throws
  expect(find.textContaining('실패'), findsOneWidget);
});

testWidgets('Pull to refresh triggers provider invalidation', (tester) async {
  // ... wrap with RefreshIndicator
  // drag down + release
  // verify: provider invalidated
});
```

### 통합 테스트

```dart
test('PushTokenService registers token on init', () async {
  final mockDio = MockDio();
  when(() => mockDio.post<void>(any(), data: any(named: 'data')))
      .thenAnswer((_) async => Response(
            requestOptions: RequestOptions(),
            statusCode: 200,
          ));

  final service = PushTokenService(mockDio);
  // ... mock Firebase Messaging
  await service.initialize();

  verify(() => mockDio.post<void>('/api/v1/devices', data: any(named: 'data'))).called(1);
});

test('Token refresh re-registers automatically', () async {
  // ... onTokenRefresh stream emits new token
  // verify: dio.post called again
});
```

### E2E 테스트 (Patrol)

```dart
patrolTest('영양제 등록 → 자동 피드백 다이얼로그', (PatrolTester $) async {
  await $.pumpWidget(const ProviderScope(child: LemonHealthcareApp()));

  // 영양제 등록 흐름 (가이드 11)
  // ... 사진 선택 → 업로드 → 결과 화면
  await $('성분 분석 결과').waitUntilVisible();

  // 2초 후 자동 피드백 다이얼로그
  await Future.delayed(const Duration(seconds: 3));
  await $('영양제 성분이 정확하게 인식되었나요?').waitUntilVisible();

  // 4점 + 코멘트 + 보내기
  await $.tester.tap(find.byIcon(Icons.star_border).at(3));
  await $.enterText(find.byType(TextField), '비타민 D만 누락');
  await $('보내기').tap();

  await $('피드백 감사합니다!').waitUntilVisible();
});
```

---

## ✅ Definition of Done

- [ ] FeedbackType enum + Freezed 모델
- [ ] `FeedbackRepository` (POST /api/v1/feedback)
- [ ] `StarRating` 위젯 (탭 인터랙션)
- [ ] `FeedbackDialog` (별점 + 코멘트 + 제출)
- [ ] `InlineFeedbackButton` (화면 내 트리거)
- [ ] `PushTokenService` (FCM/APNs 토큰 등록)
- [ ] `pushTokenInitProvider` (앱 시작 시 자동 호출)
- [ ] iOS/Android 알림 권한 설정
- [ ] Firebase 초기화 (main.dart)
- [ ] **모든 데이터 화면에 Pull-to-refresh 통합** (대시보드, 영양, 활동, 체중, 목적별)
- [ ] **영양제 등록 직후 자동 피드백 모달**
- [ ] **식단 등록 직후 자동 피드백 모달**
- [ ] 위젯 테스트 + Provider 테스트
- [ ] (선택) Patrol E2E 테스트
- [ ] iOS 시뮬레이터 + Android 에뮬레이터 정상 동작
- [ ] 실제 디바이스에서 푸시 알림 수신 확인
- [ ] `flutter analyze` + `flutter test` 통과

---

## 💡 구현 팁

### 피드백 다이얼로그 자동 표시 빈도

너무 자주 띄우면 사용자 불만:
- 영양제 등록: 매번 (인식 정확도가 핵심)
- 식단 등록: 매번
- 목적별 분석: 1주에 1회 (`shared_preferences` 로 마지막 표시 시각 저장)
- 일반 만족도: 사용 30회마다 1회

### Pull-to-refresh 일관성

```dart
// ❌ 잘못된 구조 (RefreshIndicator가 동작 안함)
RefreshIndicator(
  child: Column(
    children: [
      ListView(...),  // 내부에 ListView
    ],
  ),
)

// ✅ 올바른 구조
RefreshIndicator(
  child: ListView(  // 최상위에 ListView
    children: [...],
  ),
)
```

### 알림 권한 거부 처리

```dart
// 권한 거부됐다고 앱 기능 차단 X
// 대신 설정 화면에서 "알림 활성화" 옵션 제공
```

### Firebase 설정 파일

- iOS: `GoogleService-Info.plist` → `ios/Runner/`
- Android: `google-services.json` → `android/app/`
- `firebase_options.dart` → `flutterfire configure` 명령으로 자동 생성

---

## 🚫 이 작업에서 하지 말 것

- ❌ 피드백 다이얼로그 강제 (사용자가 닫을 수 있어야)
- ❌ 알림으로 광고·홍보 발송
- ❌ 사용자 PII (이름·이메일)를 metadata에 포함
- ❌ 동기 API 호출 (모든 호출은 await)

---

## 🎉 Phase 3 완료!

이 가이드 완료 시점에 Phase 3 핵심 산출물이 모두 동작합니다:

```
✅ Hall 동적 모델 — 30~365일 장기 체중 예측
✅ 5종 출력 완성 — 부족 영양소 + 권장 섭취량 + 체중 예측 + 운동 권고 + 목적별 분석
✅ 식단 인식 — 텍스트·이미지 양방향
✅ 사용자 피드백 — 별점·코멘트 수집 + 인식 정확도 개선 루프
✅ 푸시 알림 — FCM(Android) + APNs(iOS) 통합
✅ 컴플라이언스 — 모든 화면 면책 고지 + 의료법 표현 가이드 자동 검증
```

---

## 🔗 관련 문서

- [`/CLAUDE.md`](../../CLAUDE.md)
- [`/mobile/CLAUDE.md`](../../mobile/CLAUDE.md)
- [`/docs/10-compliance-checklist.md`](../10-compliance-checklist.md) — 알림 동의
- 이전: [`20-mobile-meal-input-screen.md`](./20-mobile-meal-input-screen.md)
- **Phase 4 시작 (W10 — 인수인계·발표)**: 별도 가이드 또는 발표 자료
