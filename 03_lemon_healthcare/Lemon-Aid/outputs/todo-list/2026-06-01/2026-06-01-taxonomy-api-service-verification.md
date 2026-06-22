# 2026-06-01 Taxonomy API/Service 검증 기록

> 작성 기준: 2026-06-01
> 대상: backend taxonomy catalog, supplement/meal query filter, scope contract, mobile background analysis/chat 연결 변경

---

## 1. Backend 검증

### Ruff

```bash
cd backend
.venv/bin/python -m ruff check Nutrition-backend/src
```

결과:

```text
All checks passed!
```

### Targeted Pytest

```bash
cd backend
.venv/bin/python -m pytest --no-cov \
  Nutrition-backend/tests/unit/security/test_scopes.py \
  Nutrition-backend/tests/unit/db/test_models.py \
  Nutrition-backend/tests/unit/schemas/test_taxonomy_schemas.py \
  Nutrition-backend/tests/integration/api/test_p1_api_contract.py
```

결과:

```text
42 passed, 1 warning in 2.79s
```

검증된 항목:

- `meal:read` scope가 `meal:write`와 독립적으로 등록됨
- taxonomy DB 모델과 constraints/index가 metadata에 등록됨
- public taxonomy schema가 safe field만 직렬화함
- catalog endpoints가 OpenAPI contract에 등록됨
- user supplement stale taxonomy filter가 `422`를 반환함
- meal list는 `meal:read` scope를 요구하고, `meal:write`만 있으면 거부됨
- meal taxonomy stale filter가 `422`를 반환함

---

## 2. Mobile 검증

### Targeted Flutter Test

```bash
cd mobile
flutter test \
  test/unit/app_controller_test.dart \
  test/unit/supplement_models_test.dart \
  test/unit/supplement_repository_test.dart \
  test/unit/api_client_robustness_test.dart \
  test/widget/analysis_result_screen_test.dart \
  test/widget/camera_readiness_widget_test.dart \
  test/widget/source_camera_screen_test.dart \
  test/widget/chat_screen_test.dart
```

결과:

```text
All tests passed!
```

검증된 항목:

- background supplement/meal analysis 시작 시 이전 preview를 즉시 비움
- 분석 완료 notice에서 결과 화면으로 이동 가능한 route가 설정됨
- local LLM 설명 실패 시에도 등록된 영양제 정보는 유지됨
- impact check 실패 시 chat 설명 draft를 생성하고 1회성으로 consume 가능함
- API timeout/oversized upload/403 mapping이 앱에서 hang 없이 처리됨
- camera bridge preview, gallery pick, batch image 추가, role-aware retake가 유지됨

### Flutter Analyze

```bash
cd mobile
flutter analyze lib \
  test/unit/app_controller_test.dart \
  test/unit/supplement_models_test.dart \
  test/unit/supplement_repository_test.dart \
  test/unit/api_client_robustness_test.dart \
  test/widget/analysis_result_screen_test.dart \
  test/widget/camera_readiness_widget_test.dart \
  test/widget/source_camera_screen_test.dart \
  test/widget/chat_screen_test.dart
```

결과:

```text
No issues found! (ran in 1.6s)
```

---

## 3. 커밋 전 제외 기준

### Frontend

```bash
cd frontend
npm run build
npm run typecheck
```

결과:

```text
next build: compiled successfully
tsc --noEmit: pass
```

참고:

- `.next/types`가 오래된 상태에서 `npm run typecheck`를 먼저 실행하면 missing generated type 경고가 날 수 있어, clean 검증은 `npm run build` 후 `npm run typecheck` 순서로 확인했다.

### Diff / Secret Hygiene

```bash
git diff --check
git diff --cached --check
git diff --cached --name-only --diff-filter=ACMRT \
  | xargs detect-secrets scan -n --exclude-files 'package-lock\.json|.*\.png$'
```

결과:

```text
git diff --check: pass
git diff --cached --check: pass
detect-secrets staged scan: results {}
```

---

## 4. 커밋 전 제외 기준

Stage 제외:

- `.env`, `.env.local`, `.vercel/.env.*.local`
- raw OCR/provider payload
- `data/nutrition_reference/crawling-image/`
- `data/nutrition_reference/sample-image/`
- `.DS_Store`, `__pycache__`, `.omc_probe_*`
- 시뮬레이터/에뮬레이터 스크린샷 원본

Stage 포함 의도:

- backend API/service/schema/model/test 변경
- mobile background analysis/chat/camera/test 변경
- frontend Vercel source/config 파일
- mobile launcher icon/app icon asset 변경
- `outputs/todo-list/2026-06-01` 작업 기록 문서
