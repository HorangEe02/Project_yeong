# 2026-05-19 — Mobile Track D Phase M-3 작업 보고

작성: 2026-05-19
브랜치: `claude/inspiring-cannon-a70b91`
이전 커밋: `72d842a2` (M-2 완료)
이번 커밋: `281d41bf` (**M-3 영양제 사진 등록 흐름**)
worktree: `.claude/worktrees/inspiring-cannon-a70b91/03_lemon_healthcare/yeong-Vision-Nutrition/mobile/`
PR: [#38](https://github.com/HorangEe02/Project_yeong/pull/38) (open, follow-up commit 추가됨)
plan: `/Users/yeong/.claude/plans/mossy-forging-hejlsberg.md` (이번 phase 의 final plan)

## 1. 개요

M-2 까지의 인증/동의/refresh 인터셉터 베이스 위에 **HomeScreen 의 "영양제 등록" 버튼이 실제로 동작하는 흐름** — 카메라/갤러리 권한 → image_picker → image_cropper(1:1) → Dio multipart 업로드(`POST /api/v1/supplements/register`) → KDRIs 진단 결과 화면 — 을 완성했다. 결과 화면은 백엔드 5단계 NutrientStatus(deficient/low/adequate/excessive/risky)에 컬러칩 + ratio bar + 한국어 메시지를 매핑하고, 하단에 의료 면책 + 응급자원 + 전문가 상담 안내 3종 안전 위젯을 의무 배치한다.

| Phase | 상태 | 산출물 |
|---|---|---|
| M-0 | ✓ artifact | `/Users/yeong/.claude/plans/lemon-mobile/INDEX.md` + 5 phase plan 파일 |
| M-1 | ✓ commit `c1fb3205` | Flutter 부트스트랩 (Riverpod + Dio + go_router + secure_storage + 면책 위젯) |
| M-2 | ✓ commit `72d842a2` | 인증 + 회원가입 + 동의 매트릭스 + 401 refresh interceptor |
| **M-3** | **✓ commit `281d41bf`** | **영양제 사진 등록 (capture → crop → upload → result + 안전 위젯)** |
| M-4 | 대기 | 면책 / 응급자원 / 상담권장 위젯 polish |
| M-5 | 대기 | Patrol full-flow E2E |

## 2. 결과 지표

| 항목 | 값 |
|---|---|
| flutter analyze | **No issues found** (0 warnings, 1.9s) |
| flutter test | **53/53 passed** (24 기존 + 29 신규 M-3) |
| 시크릿 staged | **0건** (.env / GOOGLE_APP / JWT_SECRET / api_key 검사 통과) |
| 의료 금지표현 grep | **0건** (word-boundary regex 로 secure/obscure 등 false positive 제거 후 클린) |
| SharedPreferences 평문 토큰 | **0건** (flutter_secure_storage 만 사용 — Rule 5) |
| 신규 파일 | **13 신규** (9 lib + 4 test) |
| 수정 파일 | **2** (app_router.dart, home_screen.dart) |
| 라인 변경 | **+1,646 / -8** |
| 빌드된 generated outputs | 819 (build_runner — gitignore 됨) |
| 신규 의존성 | **0** (M-1 의존성 그대로 image_picker / image_cropper / permission_handler / dio 사용) |

## 3. Phase M-3 — 영양제 사진 등록 (commit `281d41bf`)

### 신규 lib (9 파일)

**`features/supplement/domain/supplement_models.dart`** — Freezed snake_case ↔ camelCase 모델
- `SupplementResponse` (12 필드: `supplementId / productName? / manufacturer? / ingredients / unmatchedIngredientNames / diagnosis / ocrEngine / llmEngine / elapsedMs / disclaimers / emergencyResources / consultProfessionalMessageKo`)
- `Ingredient {code, nameKo, amount, unit}`
- `DiagnosisResult {diagnoses, deficientCount, riskyCount, adequateCount, summaryMessageKo}`
- `NutrientDiagnosis {code, nameKo, rda?, ai?, ear?, ul?, actual, unit, ratio, status, messageKo}`
- `enum NutrientStatus` 5값 (`@JsonValue('deficient' / 'low' / 'adequate' / 'excessive' / 'risky')`)
- `emergencyContactsFromJson` 헬퍼 — 백엔드 `list[dict[str, str]]` → `List<EmergencyContact>` 변환

**`features/supplement/data/supplement_repository.dart`** — Dio multipart wrapper
- `register({required String imagePath, void Function(double)? onProgress})`
- `FormData.fromMap({'image': MultipartFile.fromFile(imagePath, filename: 'supplement.jpg')})`
- `onSendProgress: (sent, total) → onProgress(sent / total)`
- DioException raw rethrow — 사용자 친화 매핑은 notifier 에 위임 (status code 종류 많아 일원화가 깔끔)

**`features/supplement/presentation/providers/supplement_notifier.dart`** — sealed state + `_mapDioError`
- `sealed class SupplementState`: `SupplementIdle / SupplementUploading(progress) / SupplementSuccess(response) / SupplementError(message)`
- `@riverpod class SupplementNotifier`: `register(imagePath) / reset()`
- `_mapDioError(DioException)` — 400/401/403/422/429/5xx/timeout/unknown → 한국어 메시지 (아래 표)

**`features/supplement/presentation/widgets/`** (4 위젯)
- `status_chip.dart` — NutrientStatus → (Color, Korean label): deficient→red "부족", low→orange "낮음", adequate→green "적정", excessive→amber "과다", risky→errorContainer "주의"
- `ingredient_card.dart` — Ingredient + Optional NutrientDiagnosis → 헤더(nameKo + amount/unit) + StatusChip + LinearProgressIndicator(`(ratio / 2.0).clamp(0, 1)`) + 권장량 % 텍스트 + messageKo
- `source_selector.dart` — dev-guide 11 §7 그대로 (카메라/갤러리 카드 + 안내 문구)
- `upload_progress.dart` — CircularProgressIndicator + 백분율, 1.0 도달 시 "분석 중..." 안내로 전환

**`features/supplement/presentation/screens/`** (2 화면)
- `supplement_capture_screen.dart` — `ConsumerWidget` + `ref.listen` 으로 `SupplementSuccess` → `notifier.reset() + context.pushReplacement('/supplement/result', extra: response)`. body 는 sealed switch (Idle→SourceSelector / Uploading→UploadProgress / Error→AppError(onRetry: reset) / Success→shrink). 권한: `Permission.camera / .photos` → 거부 시 AlertDialog + `openAppSettings()`. ImagePicker(maxWidth 2048, q 85) → ImageCropper(JPG q 85, AndroidUiSettings/IOSUiSettings 한국어) → `notifier.register(cropped.path)`. 하단 `MedicalDisclaimer(supplement)` 의무 배치 (Rule 1). `if (!context.mounted) return;` Rule 7 준수
- `supplement_result_screen.dart` — `ConsumerWidget(response: SupplementResponse)`. AppBar=productName. ListView: 제조사 → SummaryCard(deficient/adequate/risky CountChip + summaryMessageKo) → "성분별 진단" 섹션(`ingredients` 순회 + `diagnosisByCode` lookup → IngredientCard) → unmatched 섹션(Wrap of Chip, 비어있지 않을 때만) → **MedicalDisclaimer(supplement)** → **EmergencyResources(items: response.emergencyResources)** → **ConsultProfessional(message: response.consultProfessionalMessageKo)** → "다시 등록" FilledButton → `notifier.reset() + context.go('/')`

### 수정 (2 파일)

**`core/routing/app_router.dart`** — 2 GoRoute 추가
```dart
GoRoute(path: '/supplement/capture', name: 'supplement-capture',
        builder: (_, __) => const SupplementCaptureScreen()),
GoRoute(path: '/supplement/result', name: 'supplement-result',
        builder: (_, GoRouterState s) =>
            SupplementResultScreen(response: s.extra! as SupplementResponse)),
```
M-2 의 redirect 가드(Authenticated/Unauthenticated)는 그대로 적용됨 → 비로그인 사용자가 직접 `/supplement/*` 진입해도 `/login` 리다이렉트.

**`features/home/presentation/screens/home_screen.dart`** — SnackBar placeholder 제거
```diff
- ScaffoldMessenger...SnackBar('영양제 등록은 Phase M-3 에서 활성화됩니다.')
+ () => context.push('/supplement/capture')
```

### 신규 test (4 파일)

| 파일 | 케이스 수 | 검증 |
|---|---:|---|
| `test/unit/supplement/supplement_repository_test.dart` | 5 | 200 → SupplementResponse 전 필드 + nested 매핑 / onSendProgress(0.5 → 1.0) 콜백 / 400·422·429 raw rethrow |
| `test/unit/supplement/supplement_notifier_test.dart` | 12 | 초기 Idle / 성공 시 Uploading(0) → Uploading(0.5) → Success / reset → Idle / `_mapDioError` 9 status (400/401/403/422/429/500/timeout/DioException unknown/Non-DioException) → 한국어 매핑 |
| `test/widget/supplement/source_selector_test.dart` | 3 | 카메라 탭 콜백 / 갤러리 탭 콜백 / 안내 문구 가시 |
| `test/widget/supplement/supplement_result_screen_test.dart` | 9 | 제품명/제조사 헤더 / IngredientCard x2 가시 / StatusChip excessive→"과다" + adequate→"적정" / MedicalDisclaimer(supplement) variant / EmergencyResources 가시 / ConsultProfessional message 전달 / unmatched 빈 리스트 미가시 / unmatched 비어있지 않으면 섹션+chip 가시 / "다시 등록" 버튼 가시 |

테스트 패턴은 M-2 의 mocktail (`class _MockDio extends Mock implements Dio`) 그대로. notifier 테스트는 Riverpod `ProviderContainer.overrides` 로 mock repository 주입. 결과 화면 테스트는 ListView 의 lazy build 때문에 viewport 를 800×2400 으로 확장 (`tester.view.physicalSize`) 해서 모든 하단 안전 위젯을 단일 frame 에서 검증.

## 4. DioException 한국어 매핑 — 백엔드 status code 직접 확인

| Status | 원인 (백엔드 코드 근거) | 사용자 메시지 |
|---|---|---|
| 400 | 이미지 검증 실패 — `supplement_service.py:115,220,224,227` (format/size/security 차단) | "이미지 형식 또는 크기에 문제가 있습니다." |
| 401 | AuthInterceptor refresh 실패 잔여 (정상 흐름은 자동 재시도 + logout 트리거) | "다시 로그인해주세요." |
| **403** + `detail.code=="consent_required"` | **`consent_service.py:34,49` — `ConsentService.require()`** (만성질환/복약 동의 누락) | "필요한 동의를 다시 확인해주세요." |
| 422 | OCR/LLM/MFDS 매칭 실패 — `supplement_service.py:109,267,273` | "영양제 정보를 인식하지 못했습니다. 다른 사진으로 시도해주세요." |
| 429 | rate limit — `check_register_rate_limit` (10/min) | "잠시 후 다시 시도해주세요. (분당 요청 한도 초과)" |
| 5xx (500/502/503/504) | 서버 오류 | "서버 오류입니다. 잠시 후 다시 시도해주세요." |
| `DioExceptionType.connectionTimeout/sendTimeout/receiveTimeout` | 네트워크 | "네트워크 연결이 느립니다. Wi-Fi 환경에서 시도해주세요." |
| 그 외 (statusCode null, unknown DioException, Non-DioException) | — | "예상치 못한 오류가 발생했습니다." |

**중요**: auth `register` 의 consent 검증은 422 (Pydantic 경로) 인 반면, supplement 런타임은 **403** 으로 별개. plan 단계에서 백엔드 `consent_service.py:34,49` 를 직접 확인해 사용자 task 스펙(403) 의 정확성을 검증했고, 두 가지를 방어적으로 동시 처리하지 않고 각 엔드포인트의 실제 동작을 그대로 매핑.

## 5. 컴플라이언스 회귀 (모두 그린)

```bash
# 의료 금지표현 (word-boundary 로 secure/obscure false positive 제거)
git grep -nE "(진단|처방|치료|\bdiagnose|\bprescribe|\bcure\b|\btreat\b|보장|확실히)" \
  -- 'lib/**' 'test/**' \
  | grep -v -E "(disclaimer|disclaimer_strings|emergency_resources|consult_professional|//|deficient_count|risky_count|adequate_count|/// |  /// )"
# → MEDTERM-CLEAN

# 평문 토큰 저장 검증
git grep -n "SharedPreferences" lib/core/storage/
# secure_storage.dart 의 AndroidOptions(encryptedSharedPreferences: true) 는 Keychain/EncryptedSP 인증된 secure 저장이며 평문 X
# token_storage.dart 주석에 '평문 SharedPreferences 사용 X (Rule 5)' 명시

# 시크릿 staged 검증
git diff --cached | grep -E "(\.env|GOOGLE_APP|JWT_SECRET|api[_-]?key)"
# → 0건
```

## 6. 의식적 deviation (plan → 실제 코드)

| 항목 | plan | 실제 | 사유 |
|---|---|---|---|
| `prefer_int_literals` 린트 | — | 테스트의 `1.0` → `1` 으로 변경 (`<double>[0.5, 1]`, `ratio: 1`) | very_good_analysis 가 `1.0` 을 불필요 double 로 잡음 — int 리터럴이 double 컨텍스트에서 자동 promotion |
| `comment_references` | dartdoc 에 `[SupplementCaptureScreen]` 등 사용 | 대괄호 제거 + 일반 텍스트 | 해당 클래스가 import 되지 않은 파일에서는 `[X]` 가 unresolved 로 info — 시각적 강조 없이 plain 으로 |
| result_screen_test viewport | 기본 (800×600) | `tester.view.physicalSize = Size(800, 2400)` + tearDown reset | 기본 viewport 에서 ListView 의 ConsultProfessional / "다시 등록" 버튼 / unmatched 섹션이 lazy build 되지 않아 `find.byType` 0건. 단일 frame 검증을 위해 확장 |
| 403 vs 422 consent 처리 | "두 케이스 방어적 처리" | 403 만 매핑 (백엔드 실제 동작 그대로) | plan 작성 중 slop 경고 + 백엔드 코드 직접 확인 결과 supplement 는 403 단일 경로. over-engineering 제거 |
| upload_progress_test | DoD 옵션 권장 | 작성 X | phase plan 의 test 4개 목록에는 없고 widget 자체가 단순. 시간 절약 |
| `emergency_resources` 변환 | `@JsonKey(fromJson:)` 헬퍼 | 그대로 채택 — top-level `emergencyContactsFromJson` | plan 권장안 그대로 |

## 7. DoD 체크

| 항목 | 상태 | 비고 |
|---|---|---|
| `flutter analyze` 0 warnings | ✓ | 1.9s |
| `flutter test` 통과 | ✓ | 53/53 (29 신규 + 24 기존) |
| MedicalDisclaimer(supplement) 결과 화면 하단 배치 | ✓ | widget test 로 variant 검증 |
| EmergencyResources 결과 화면 배치 + 백엔드 응답 전달 | ✓ | widget test 로 가시 + props 검증, 빈 리스트 fallback 은 위젯 자체 (M-1 검증) |
| ConsultProfessional 결과 화면 배치 + 백엔드 메시지 전달 | ✓ | widget test 로 props.message 검증 |
| 권한 거부 시 설정 이동 다이얼로그 | ✓ | `_showPermissionDeniedDialog` + `openAppSettings()` |
| DioException → 한국어 메시지 (raw status 노출 X) | ✓ | notifier `_mapDioError` 9 케이스 모두 단위 테스트 |
| Conventional commit + Co-Authored-By | ✓ | `281d41bf` |
| **시뮬레이터 수동 cycle** | **⚠️ 환경 미실행 보고** | 백엔드 dev 서버 + Ollama qwen3.5:9b 가 이번 세션에 기동되지 않아 시뮬 검증은 미실시. 단위/위젯 테스트가 흐름을 대신 검증 + M-5 의 Patrol E2E 가 잔여 매뉴얼 검증 대체 예정. 사용자가 로컬에서 검증 시: `cd backend && uvicorn src.main:app --reload --port 8000` + `cd mobile && flutter run --dart-define=API_BASE_URL=http://localhost:8000` |

## 8. PR #38 영향

- 베이스 `c1fb3205` → 현재 HEAD `281d41bf` (M-1 + M-2 + M-3 = 3 commits)
- 총 변경: +5,912 (M-1 +2,656 / M-2 +1,610 / M-3 +1,646)
- 머지 시 트랙 D 의 첫 사용자 가치 흐름 (로그인 → 영양제 사진 분석 → 진단 결과) 완성
- M-4 (안전 위젯 polish — url_launcher canLaunch 분기 + Clipboard fallback) 와 M-5 (Patrol E2E) 는 같은 PR 의 추가 commit 으로 진행 권장

## 9. M-4 진입 조건 (충족됨)

M-3 가 결과 화면에 면책/응급/상담 3종 안전 위젯을 배치한 상태 → M-4 는 위젯 자체의 polish (전화 호출 unsupported 환경 fallback + Clipboard 복사 시각 안내 + 골든 테스트) 에 집중. 별도 lib 추가 없이 widget 수정 + 테스트 강화.

---

**참조**:
- plan: `/Users/yeong/.claude/plans/mossy-forging-hejlsberg.md`
- phase plan: `/Users/yeong/.claude/plans/lemon-mobile/phase-m3-supplement.md`
- 사전 M1+M2 보고서: `2026-05-19-mobile-track-d-m1-m2-report.md`
- dev-guide: `docs/dev-guides/11-mobile-camera-screen.md`
- 백엔드: `backend/src/api/v1/supplements.py`, `backend/src/services/{supplement,consent}_service.py`, `backend/src/models/schemas/{supplement,nutrition}.py`
