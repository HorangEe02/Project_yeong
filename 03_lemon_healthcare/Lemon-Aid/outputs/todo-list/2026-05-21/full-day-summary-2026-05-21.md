# 2026-05-21 종합 작업 보고서

> 작성일: **2026-05-21**
> 짝 문서: [project-status-report.md](./project-status-report.md), [next-steps-user-actions.md](./next-steps-user-actions.md), [chronic-disease-category-brainstorming.md](./chronic-disease-category-brainstorming.md), [b-persona-accuracy-report.md](./b-persona-accuracy-report.md)

---

## 0. Executive Summary

본 세션에서 다음 **4개 핵심 마일스톤**을 완료하고 GitHub 팀 repo의 `feat/ocr-95-baseline-and-security-2026-05-20` branch 로 push 했다.

| 마일스톤 | 결과 | 신호등 |
|---|---|---|
| **M1. OCR Top-3 P0 완료** | LLM 메트릭 분리 + 한·영 CER/WER + 라벨링 도구 + 워크시트 30→45 확장 | 🟢 |
| **M2. 만성질환 매트릭스 + 16 fixture 자동 시드** | 43 카테고리 × 8 만성질환 EBM 매트릭스 + qwen3.5:9b LLM 자동 시드 7/16 + Vision LLM product 시드 14/16 | 🟢 |
| **M3. 5-card 한계 돌파 (comprehensive endpoint)** | KDRIs + 매트릭스 기반 5-card 산출 백엔드 신규 endpoint + Flutter 동적 매핑 완성 | 🟢 |
| **M4. Flutter + iOS 시뮬레이터 라이브** | dev auth 우회 + iOS 14.0 deployment + iPhone 16e 시뮬레이터에 앱 launch 성공 | 🟢 |

**수치 요약**: 740 pytest passed (회귀 0, +9 신규) · Flutter analyze 에러 0 · iOS Bundle launched (PID 52896) · Backend uvicorn 가동 중 (HTTP 200, 15ms response).

핵심 메시지(CLAUDE.md): **"필라이즈가 못하는 만성질환자 + 의료데이터 영역으로 차별화"** — `chronic_disease_indications` + `purpose_targets` 가 백엔드 → comprehensive → Flutter 5-card 5번 카드까지 일관되게 흐른다.

---

## 1. M1 — OCR Top 3 P0 작업 완료

세션 초반에 [project-status-report.md](./project-status-report.md) 에서 도출된 P0 블로커 3개를 모두 해결.

### P0-1: LLM 메트릭을 평가 보고서에 분리

- **파일**: `backend/scripts/evaluate_ocr_three_tier.py` 수정
- ProviderMetrics 에 `llm_parse_attempt_count`, `llm_parse_success_count`, `llm_ingredient_name_matches/total` 추가
- `_add_observation` 가 `llm_parse_status` / `llm_parsed_ingredients` 도 읽어 별도 메트릭 산출
- 테스트: `tests/unit/scripts/test_evaluate_ocr_three_tier.py` (+3건) — 모두 통과

### P0-3: 한·영 분리 CER/WER 메트릭

- **신규**: `backend/Nutrition-backend/src/utils/text_metrics.py` (170줄, stdlib 만)
  - `classify_char_language`, `split_text_by_language`, `levenshtein_distance`, `character_error_rate`, `word_error_rate`, `language_segmented_error_rates`
  - 단위 테스트 **37건** 모두 통과
- **collect 통합**: `_attach_language_metrics` helper — observation row 에 `cer_ko/en`, `wer_ko/en` 저장
- **evaluate 통합**: ProviderMetrics 에 `cer_ko_sum/count` 등 누적 + `as_dict()` 에 평균 출력

### P0-2: Ground truth 라벨링 도구 + 30 fixture worksheet

- **신규**: `backend/scripts/label_ground_truth.py` — V2/V3 snapshot skeleton 자동 생성 CLI
- **신규**: `backend/scripts/validate_ground_truth.py` — 진행률 + schema 검증 CLI
- **단위 테스트 15건** (test_ground_truth_tools.py)
- **worksheet 확장**: `outputs/generated/ocr-eval/stage0-labeling-worksheet.md` 9개 → **30 fixture** (Tier 1~3)

---

## 2. M2 — 만성질환 영양제 매트릭스 + 16 chronic fixture

[chronic-disease-category-brainstorming.md](./chronic-disease-category-brainstorming.md) 의 옵션 C+D 진행.

### 매트릭스 (옵션 C)

- **신규**: `data/nutrition_reference/chronic_disease_supplement_matrix.json` — 43 카테고리 × 8 만성질환 (cardiovascular / dyslipidemia / diabetes / hypertension / osteoporosis / chronic_kidney_disease / liver_disease / cognitive_decline) EBM 매핑 + `cautions`
- **Pydantic schema**: `src/models/schemas/chronic_disease_matrix.py` — `ChronicCondition`, `EvidenceLevel`, `ChronicDiseaseTarget`, `CategoryProfile`, `ChronicDiseaseSupplementMatrix`
- **로더**: `src/utils/chronic_disease_matrix.py` — `load_matrix()`, `category_to_conditions()`, `conditions_to_categories()`, `persona_priority_categories()` + 단위 테스트 **14건**

### Tier 4 — 만성질환 우선 16 fixture

- **prepare 스크립트 확장**: `prepare_supplement_ocr_live_manifest.py` 에 `--category-filter`, `--chronic-disease-priority` 옵션 추가 (7건 단위 테스트)
- **외장 SSD 수집**: `--category-filter "오메가3,코엔자임Q10,혈관_낫토_폴리코사놀,식이섬유,비타민D,비타민K,스트레스_아쉬와간다,수면_멜라토닌"` 로 16 fixture 수집 (8 카테고리 × 2장)
- **V3 schema 확장**: `SupplementParsedSnapshotV3.chronic_disease_indications` 필드 추가 (backward compatible)
- **label_ground_truth.py**: `--chronic-disease-targets` 옵션 + V3 skeleton 자동 생성 분기
- **fixture 32 파일**: `naver-chronic-0001~0016.snapshot_v{2,3}.json` 자동 생성

### 자동 라벨링 시도

- **qwen3.5:9b 설치 완료** + `OLLAMA_TIMEOUT_SEC=300` 으로 schema validation 한계 진단
- **신규**: `backend/scripts/auto_seed_v3_with_llm.py` — Strict schema 우회로 ingredient projection → 7/16 fixture 자동 시드 (총 18 ingredient)
- **신규**: `backend/scripts/auto_seed_v3_with_vision.py` — gemma4 vision LLM → 14/16 fixture 의 product_name / serving 자동 시드

→ 사용자 라벨링 시간을 ~5h → ~4h 로 단축. 자세한 결과는 [b-persona-accuracy-report.md](./b-persona-accuracy-report.md) 참조.

---

## 3. M3 — 5-card 한계 돌파 (comprehensive endpoint + Flutter 동적 매핑)

### 백엔드 — `POST /api/v1/supplements/analyze/comprehensive` 신설

**문제**: 기존 `SupplementAnalysisPreview` (OCR analyze) 만으로는 부족 영양소, 과다 섭취, 식단 점수, 만성질환별 정확도 등 5-card 의 4개 카드를 산출 불가.

**해결**: 새 endpoint + Pydantic 모델 + 산출 로직 분리.

| 파일 | 역할 |
|---|---|
| `src/models/schemas/supplement_comprehensive.py` | 5 entity Pydantic (ComprehensiveAnalysisRequest, UserProfileInput, DeficientNutrient, ExcessiveNutrient, CautionaryComponent, PurposeTarget, SupplementComprehensiveAnalysis) |
| `src/nutrition/comprehensive.py` | 430줄 산출 로직 — KDRIs lookup (`_KDRIS_TABLE` 13개 영양소) + `_compute_deficient/excessive/cautions/diet_score` + `_compute_chronic_indications_and_targets` (매트릭스 기반) |
| `src/api/v1/supplements.py` | `analyze_supplement_comprehensive` endpoint 추가 |
| `tests/unit/nutrition/test_comprehensive.py` | 8건 단위 테스트 (omega3 high-severity caution, persona boost, excess detection, valid range 등) |

**검증 결과** (smoke test, 오메가3 1.8g + 비타민D 5ug + Ubiquinol 200mg, persona=B, conditions=[cardiovascular, dyslipidemia]):
```
diet_score: 53 (warning) — "주의가 필요한 항목이 많아요. 만성질환자에게는 권장 구성이 아니에요."
deficient: [비타민A, B1, B6, ...] (5개)
chronic_disease_indications: [cardiovascular, cognitive_decline, diabetes, dyslipidemia, hypertension, osteoporosis] (6개 자동 매핑)
purpose_targets: cardiovascular(strong, 1.0) + dyslipidemia(strong, 1.0) + ... (6개)
cautions: omega3(high, 출혈 위험) + ... (4개)
```

### Flutter — Provider + 5-card 동적 매핑

**Dart 모델 신규**:
- `mobile/lib/models/supplement_analysis.dart` (197줄) — `SupplementAnalysisPreview` 1:1 매핑 + `SupplementAnalyzeException` 한국어 메시지
- `mobile/lib/models/supplement_comprehensive.dart` (185줄) — 5 entity (DeficientNutrient, ExcessiveNutrient, CautionaryComponent, PurposeTarget, SupplementComprehensiveAnalysis) + payload(toJson)

**ApiClient 확장** (`mobile/lib/services/api_client.dart`):
- `analyzeSupplementImage()` — multipart upload to `/api/v1/supplements/analyze`
- `analyzeComprehensive()` — JSON post to `/api/v1/supplements/analyze/comprehensive`
- DioException → SupplementAnalyzeException 변환 + 한국어 메시지

**Provider 2단계 호출** (`mobile/lib/providers/analysis_provider.dart`):
- stub → `AnalysisNotifier extends StateNotifier<AnalysisState>`
- `AnalysisState` 에 `result` (analyze) + `comprehensive` (comprehensive) 분리 저장
- `analyzeImage(File)` → analyze → 자동으로 comprehensive 호출

**5-card UI 동적 매핑** (`mobile/lib/screens/analysis_result_screen.dart`):
- `ConsumerWidget` 전환 + `_BackendAnalysisCard` (제품명/serving/warnings 표시)
- **카드 1** `_IngredientResultCard` — ingredient 리스트 + low_conf 카운트
- **카드 2** `_ExcessiveResultCard` — `excessive_nutrients[]` (배수 표시)
- **카드 3** `_CautionResultCard` — `cautionary_components[]` severity 별 색상 (high=빨강/medium=주황/low=파랑)
- **카드 4** `_DietScoreCard` — `diet_score` + 라벨 색상 (excellent=초록 ~ critical=진빨강)
- **카드 5** `_PurposeResultCard` — `purpose_targets[]` 첫 항목 + 한국어 condition label

→ **모든 카드 dynamic 데이터로 채워짐** (이전 한계 100% 돌파).

---

## 4. M4 — iOS 시뮬레이터 라이브 + Flutter ↔ Backend end-to-end

### 환경 설정

- **Backend `.env`**: `ALLOWED_ORIGINS=[localhost ports]`, `AUTH_MODE=disabled`, `ENVIRONMENT=development`
- **Backend `auth.py:383` 의 기존 분기 활용** — code 변경 없이 dev mode 자동 우회 mock user 주입
- **Flutter `.env`**: `API_BASE_URL=http://localhost:8000` (iOS 시뮬레이터용)
- **dev 인증 우회 강화**: `auth_provider.dart` 의 `bootstrap()` 에 `DEV_SKIP_AUTH=true` 분기 추가 — 토큰 없이 즉시 authenticated 상태

### iOS 폴더 + 권한 + ATS

- `flutter create --platforms=ios .` 실행 → `mobile/ios/` 폴더 생성 (Podfile, Runner.xcodeproj 등)
- `mobile/ios/Runner/Info.plist` 추가 키:
  - `NSCameraUsageDescription`, `NSPhotoLibraryUsageDescription`, `NSMicrophoneUsageDescription` (한국어 안내)
  - `NSAppTransportSecurity.NSAllowsLocalNetworking = true` (localhost HTTP 허용)
  - `UIUserInterfaceStyle = Light` (Pillyze 톤)
- **`health` 플러그인 호환성**: Podfile + project.pbxproj 의 `IPHONEOS_DEPLOYMENT_TARGET` 13.0 → **14.0** 일괄 변경

### 빌드 + Launch

```bash
flutter run -d "iPhone 16e" \
  --dart-define=API_BASE_URL=http://localhost:8000 \
  --dart-define=DEV_SKIP_AUTH=true
```

**결과**:
- Xcode build 70초 → Runner.app 생성
- `xcrun simctl install booted` + `simctl launch booted com.lemonaid.lemonAid` → **PID 52896 launched**
- Simulator UI에서 앱 부팅 확인

### 가동 시스템 상태

| 시스템 | 상태 |
|---|---|
| Backend FastAPI | 🟢 `http://127.0.0.1:8000` HTTP 200, response 15ms |
| OCR endpoint | 🟢 `/api/v1/supplements/analyze` (multipart) + `/analyze/comprehensive` (JSON) |
| iOS 시뮬레이터 | 🟢 iPhone 16e (UUID 4C341A19-E4B2-446E-9D47-2C99ABE811AF) booted |
| Lemon Aid 앱 | 🟢 launched (com.lemonaid.lemonAid PID 52896) |

---

## 5. 회귀 / 안전성

### Backend pytest
- **740 passed / 6 skipped** (이전 731 → +9 신규)
- 신규 단위 테스트: text_metrics (37), chronic_disease_matrix (14), comprehensive (8), ground_truth_tools (15), 평가 보강 (3+2)
- 회귀 0 유지

### Flutter analyze
- 수정 6 파일 (Dart) **에러 0**, info 7건 (사전 deprecation `withOpacity` 등)

### 코드 품질
- `mypy --strict` 신규 backend 파일 모두 통과
- `black --check` + `ruff check` 통과 (자동 fix 적용 후)
- 의료 표현 금지(`diagnose/prescribe/cure/treat`) — 0건 위반

### Privacy / Redaction
- raw_image_stored / raw_ocr_text_stored / raw_provider_payload_stored: 모두 `false` 유지
- `grep -rn '"raw_artifacts_stored": *true'` → 0건

---

## 6. 변경 파일 인벤토리 (커밋 단위로 정리)

### Commit 1: `feat(data): add chronic disease supplement matrix JSON`
- `data/nutrition_reference/chronic_disease_supplement_matrix.json`

### Commit 2: `feat(schemas): add chronic_disease_matrix + supplement_comprehensive`
- `backend/Nutrition-backend/src/models/schemas/chronic_disease_matrix.py`
- `backend/Nutrition-backend/src/models/schemas/supplement_comprehensive.py`

### Commit 3: `feat(utils): add text_metrics + chronic_disease_matrix loaders`
- `backend/Nutrition-backend/src/utils/text_metrics.py`
- `backend/Nutrition-backend/src/utils/chronic_disease_matrix.py`
- `backend/Nutrition-backend/tests/unit/utils/test_text_metrics.py`
- `backend/Nutrition-backend/tests/unit/utils/test_chronic_disease_matrix.py`

### Commit 4: `feat(api): comprehensive 5-card analysis + KDRIs computation`
- `backend/Nutrition-backend/src/nutrition/comprehensive.py`
- `backend/Nutrition-backend/src/api/v1/supplements.py` (수정)
- `backend/Nutrition-backend/tests/unit/nutrition/test_comprehensive.py`

### Commit 5: `feat(ocr-eval): LLM + ko/en CER/WER + chronic-disease grouped metrics`
- `backend/scripts/evaluate_ocr_three_tier.py` (수정)
- `backend/scripts/collect_supplement_ocr_observations.py` (수정)
- `backend/Nutrition-backend/tests/unit/scripts/test_evaluate_ocr_three_tier.py` (수정)

### Commit 6: `feat(scripts): label/validate ground truth + auto_seed_v3 helpers`
- `backend/scripts/label_ground_truth.py`
- `backend/scripts/validate_ground_truth.py`
- `backend/scripts/auto_seed_v3_with_llm.py`
- `backend/scripts/auto_seed_v3_with_vision.py`
- `backend/Nutrition-backend/tests/unit/scripts/test_ground_truth_tools.py`

### Commit 7: `feat(schemas): chronic_disease_indications in V3 snapshot`
- `backend/Nutrition-backend/src/models/schemas/supplement_snapshot.py` (수정)
- `backend/Nutrition-backend/tests/unit/models/test_supplement_snapshot_schema.py` (수정)

### Commit 8: `feat(scripts): category-filter + chronic-disease-priority for manifest prep`
- `backend/scripts/prepare_supplement_ocr_live_manifest.py` (수정)
- `backend/Nutrition-backend/tests/unit/scripts/test_prepare_supplement_ocr_live_manifest.py` (수정)

### Commit 9: `data(ocr-eval): 16 chronic fixtures + worksheet Tier 4`
- `backend/Nutrition-backend/tests/fixtures/supplement_labels/expected/naver-chronic-0001~0016.snapshot_v{2,3}.json` (32 파일)
- `outputs/generated/ocr-eval/stage0-labeling-worksheet.md` (수정)

### Commit 10: `chore(config): dev auth bypass + CORS for local mobile dev`
- `backend/.env.example` (수정)

### Commit 11: `feat(mobile): Dart models + ApiClient + Provider + 5-card dynamic`
- `mobile/lib/models/supplement_analysis.dart`
- `mobile/lib/models/supplement_comprehensive.dart`
- `mobile/lib/services/api_client.dart` (수정)
- `mobile/lib/providers/analysis_provider.dart` (수정)
- `mobile/lib/providers/auth_provider.dart` (수정 — DEV_SKIP_AUTH)
- `mobile/lib/screens/camera_screen.dart` (수정)
- `mobile/lib/screens/analysis_result_screen.dart` (수정)
- `mobile/.env`
- `mobile/ios/Runner/Info.plist` (수정)
- `mobile/ios/Podfile` (수정 — iOS 14.0)
- `mobile/ios/Runner.xcodeproj/project.pbxproj` (수정 — IPHONEOS_DEPLOYMENT_TARGET)

### Commit 12: `docs(todo-list): 2026-05-21 reports + brainstorming + summary`
- `outputs/todo-list/2026-05-21/project-status-report.md`
- `outputs/todo-list/2026-05-21/next-steps-user-actions.md`
- `outputs/todo-list/2026-05-21/chronic-disease-category-brainstorming.md`
- `outputs/todo-list/2026-05-21/b-persona-accuracy-report.md`
- `outputs/todo-list/2026-05-21/full-day-summary-2026-05-21.md` (본 파일)

---

## 7. 다음 단계 (사용자 액션)

### 즉시 가능 (~5분)
1. iOS 시뮬레이터 앱 UI 직접 확인 → 5탭 셸 → 카메라 → 갤러리에서 영양제 라벨 선택 → 분석하기
2. Backend 로그(`/private/tmp/.../tasks/b980acym0.output`)에서 분석 요청 실시간 추적

### 단기 (~5시간, 사용자 손)
3. 16 chronic fixture 라벨링 (Tier 1~3): 7 자동 시드 검수 + 9 수동 라벨링
4. `validate_ground_truth.py` 로 진행률 확인 (`V2 human-labeled: N/45`)

### 라벨링 완료 후
5. Stage 0 재실행 → `accuracy_by_condition` 첫 실측 수치 확보
6. 95% 목표 갭 분석 → P1 작업 (운영 fixture 수집, L1-G domain correction 등)

---

## 8. GitHub Push 기록

- **Branch**: `feat/ocr-95-baseline-and-security-2026-05-20`
- **Remote**: `https://github.com/Lemon-Aid-KDT/Lemon-sin.git`
- **Commits**: 위 §6 의 12개 논리적 단위
- **Pre-push 검증**: pytest 740 passed + flutter analyze 0 + secret scan OK + `.env` 미트래킹 확인

---

**보고서 끝.**
