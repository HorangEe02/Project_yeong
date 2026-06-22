# 48. Phase 0 Supplement OCR Baseline Freeze 상세 설계 및 구현 플랜

작성일: 2026-05-17
범위: 영양제 라벨 이미지 intake, OCR, layout parser, LLM structured parser, 사용자 확인 플로우의 기준선 고정
상태: Phase 0 계약/fixture/evaluator 구현 완료, API/service invariant 연결은 후속 R4 범위

## 1. 목적

Phase 0의 목적은 새 기능을 바로 추가하는 것이 아니라, 현재 섞여 있는 상태를 아래 세 가지로 고정하는 것이다.

- 실제 runtime code에 연결된 기능
- 문서 또는 계획에만 있는 기능
- 테스트나 독립 모듈은 있으나 사용자 플로우에 아직 연결되지 않은 기능

이 기준선이 없으면 이후 `SupplementParsedSnapshotV2`, layout parser 연결, OCR fallback, 추천 서비스 구현에서 같은 기능을 이미 구현된 것으로 오판할 수 있다. Phase 0은 팀이 같은 기준으로 구현 범위와 회귀 테스트 범위를 판단하도록 만드는 선행 게이트다.

## 2. 공식 문서 기반 전제

| 주제 | 공식 확인 내용 | Phase 0 반영 |
| --- | --- | --- |
| FastAPI file upload | FastAPI는 `File`/`UploadFile`로 multipart file upload를 받는다. `UploadFile`은 file metadata, async `read`, `seek`, `close`를 제공하고 uploaded files are sent as form data라고 설명한다. URL: <https://fastapi.tiangolo.com/tutorial/request-files/> | `/supplements/analyze`는 `UploadFile` + multipart form 계약을 유지한다. JSON body와 image file을 같은 request body에 섞지 않는다. |
| Google Vision document OCR | Google Vision `Feature.Type`은 `TEXT_DETECTION`과 `DOCUMENT_TEXT_DETECTION`을 구분하며, document에는 `DOCUMENT_TEXT_DETECTION`을 쓰라고 설명한다. URL: <https://cloud.google.com/vision/docs/reference/rest/v1/Feature> | 영양제 라벨의 dense text/table OCR 기준 feature는 `DOCUMENT_TEXT_DETECTION`으로 고정한다. |
| Google Vision layout | Google Vision dense document OCR는 `fullTextAnnotation` 기반 문서 텍스트 결과를 제공한다. URL: <https://cloud.google.com/vision/docs/fulltext-annotations> | provider raw JSON을 직접 파서에 넘기지 않고, repo 내부 `OCRResult.pages` 계층으로 정규화한 뒤 fixture와 layout parser 기준으로 삼는다. |

확인 한계:

- I cannot find the official documentation for a Google-recommended OCR confidence threshold such as `0.85` for Korean/English supplement labels. 따라서 confidence threshold는 공식 권장값이 아니라 프로젝트 fixture 평가 기준값으로만 취급한다.
- OCR 성공률과 필드 추출 정확도는 공식 문서에서 보장하는 값이 아니다. Phase 0에서는 팀 fixture 기준 측정값만 기록하고, 측정 전 성능 수치를 만들지 않는다.

## 3. 현재 기준선 분류 원칙

Phase 0 문서와 fixture report는 모든 기능을 아래 상태 중 하나로 표시한다.

| 상태 | 정의 | 예시 판정 기준 |
| --- | --- | --- |
| `runtime-connected` | API route, service, schema, test가 실제 사용자 플로우에 연결됨 | 모바일 또는 backend API에서 호출 가능하고 targeted test가 존재 |
| `runtime-gated` | 구현은 있으나 feature flag, consent, env, production guard에 의해 기본 비활성화 | Google Vision, CLOVA, local OCR처럼 설정과 consent가 맞을 때만 실행 |
| `module-only` | 독립 모듈과 unit test는 있으나 end-to-end 플로우에 아직 연결되지 않음 | layout parser가 OCR result와 parser snapshot 사이에 자동 연결되지 않은 상태 |
| `docs-only` | 설계 문서나 계획은 있으나 runtime code가 없음 | 추천/권장 서비스 설계만 있고 endpoint/service가 없는 상태 |
| `test-only` | test double 또는 mock 기반 검증만 있고 실제 provider smoke가 없음 | Google Vision mock은 통과했지만 실제 credential smoke 미수행 |
| `blocked` | 보안, privacy, auth, release signing 문제 때문에 배포 전 사용 금지 | release debug signing, public auth disabled, raw secret 노출 위험 |

이 분류는 구현 여부를 과장하지 않기 위한 것이다. 특히 `docs-only`와 `module-only`는 사용자에게 완성 기능으로 설명하지 않는다.

## 4. `SupplementParsedSnapshotV2` 계약 설계

### 4.1 설계 목표

`SupplementParsedSnapshotV2`는 OCR과 LLM parser가 만든 후보를 사용자 확인 화면과 추천 서비스가 같은 방식으로 읽기 위한 중간 계약이다. 이 계약은 의료 조언이나 복용 권장 판단을 포함하지 않는다. 라벨에서 확인 가능한 사실과 그 근거만 담는다.

### 4.2 비목표

- 질병 치료, 진단, 복용량 변경 조언
- 라벨에 없는 성분 또는 효능 추정
- LLM이 만든 nutrient code 확정
- raw image bytes, raw provider response, raw OCR text 전체 저장

### 4.3 최상위 구조

```json
{
  "schema_version": "supplement-parsed-snapshot-v2",
  "source": {
    "analysis_id": "uuid",
    "ocr_provider": "google_vision_document|clova_ocr|paddleocr_local|manual|none",
    "ocr_confidence": 0.91,
    "layout_available": true,
    "raw_image_stored": false,
    "raw_ocr_text_stored": false,
    "raw_provider_payload_stored": false
  },
  "product": {
    "product_name": "label-supported string or null",
    "manufacturer": "label-supported string or null",
    "barcode_text": "optional barcode candidate",
    "barcode_format": "optional barcode format"
  },
  "serving": {
    "serving_size_text": "2 tablets",
    "serving_amount": 2,
    "serving_unit": "tablets",
    "daily_servings": 1,
    "evidence_refs": ["section:intake_method:row:0:cell:1"]
  },
  "label_sections": [],
  "ingredient_candidates": [],
  "intake_method": {
    "text": "label-supported intake instruction or null",
    "structured": {
      "frequency": "daily|weekly|as_needed|unknown",
      "time_of_day": [],
      "with_food": "yes|no|unknown"
    },
    "evidence_refs": []
  },
  "precautions": [],
  "functional_claims": [],
  "low_confidence_fields": [],
  "warnings": []
}
```

### 4.4 필드별 규칙

| 필드 | 규칙 |
| --- | --- |
| `schema_version` | migration과 회귀 테스트 기준값이다. V1과 혼동하지 않도록 문자열 고정값을 둔다. |
| `source.ocr_provider` | provider label만 저장한다. API key, endpoint, request ID는 저장하지 않는다. |
| `source.ocr_confidence` | provider가 준 값 또는 내부 평균만 사용한다. 값이 없으면 `null`이다. |
| `source.raw_image_stored` | 정상 경로에서는 `false`여야 한다. learning pipeline은 별도 consent gate가 필요하다. |
| `source.raw_ocr_text_stored` | 정상 경로에서는 `false`여야 한다. OCR text hash는 허용 가능하나 raw text는 금지한다. |
| `source.raw_provider_payload_stored` | 정상 경로에서는 `false`여야 한다. provider 원본 JSON, request, secret header는 fixture/report에 저장하지 않는다. |
| `product` | label 또는 barcode lookup에서 확인 가능한 후보만 둔다. |
| `serving` | `serving_size_text` 원문과 파싱된 `amount/unit`을 분리한다. 현재 mobile처럼 원문 전체를 unit에 넣는 매핑은 금지한다. |
| `label_sections` | layout parser 결과의 section, row, cell을 allowlisted shape로 담는다. |
| `ingredient_candidates` | LLM 추출 후보이며 사용자 확인 전에는 확정 성분이 아니다. |
| `intake_method` | 라벨 문구 기반 구조화만 허용한다. 개인 복용 권장은 아니다. |
| `precautions` | 라벨 주의사항 문구를 분류한다. 약물 상호작용 단정은 금지한다. |
| `functional_claims` | 라벨의 기능성 표현 원문과 근거만 담는다. 새로운 효능 문장을 생성하지 않는다. |
| `low_confidence_fields` | UI에서 사용자가 반드시 확인해야 할 field path 목록이다. |
| `warnings` | OCR/파서 degraded 상태를 사용자에게 안전하게 알리는 문구다. |

### 4.5 ingredient candidate 구조

```json
{
  "display_name": "Vitamin C",
  "normalized_name": "vitamin c",
  "nutrient_code_candidates": [
    {
      "nutrient_code": "VITC",
      "match_method": "alias_exact|alias_fuzzy|manual",
      "confidence": 0.92
    }
  ],
  "amount": 500,
  "unit": "mg",
  "daily_amount": 500,
  "confidence": 0.88,
  "source": "ocr_llm_preview",
  "evidence_refs": ["section:nutrition_function_info:row:2:cell:0"]
}
```

규칙:

- `nutrient_code_candidates`는 deterministic matcher 결과다. LLM은 code를 확정하지 않는다.
- `daily_amount`는 `amount * daily_servings` 계산이 가능한 경우에만 산출한다.
- 같은 성분이 여러 줄에 나오는 경우 merge하지 않고 후보를 분리한 뒤, 후속 confirmation 단계에서 병합한다.

## 5. Fixture 세트 설계

### 5.1 경로

권장 경로:

- `backend/Nutrition-backend/tests/fixtures/supplement_labels/`
- `backend/Nutrition-backend/tests/fixtures/supplement_labels/images/`
- `backend/Nutrition-backend/tests/fixtures/supplement_labels/ocr/`
- `backend/Nutrition-backend/tests/fixtures/supplement_labels/expected/`

### 5.2 fixture manifest

파일: `backend/Nutrition-backend/tests/fixtures/supplement_labels/manifest.json`

```json
{
  "version": "2026-05-17-phase0",
  "cases": [
    {
      "case_id": "ko_en_dense_table_001",
      "image_path": "images/ko_en_dense_table_001.png",
      "ocr_text_path": "ocr/ko_en_dense_table_001.google_vision.txt",
      "expected_snapshot_path": "expected/ko_en_dense_table_001.snapshot_v2.json",
      "labels": ["ko", "en", "dense_table", "intake_method", "precautions"],
      "allowed_providers": ["google_vision_document", "clova_ocr", "paddleocr_local", "manual"],
      "contains_personal_data": false,
      "source": "team-owned synthetic or consent-cleared sample"
    }
  ]
}
```

### 5.3 최소 fixture 구성

| case id | 목적 | 필수 검증 |
| --- | --- | --- |
| `ko_dense_table_001` | 한국어 성분표, 1일 섭취량, 주의사항 | 성분명/함량/단위/섭취방법 section 분리 |
| `ko_en_dense_table_001` | 한국어+영어 혼합 포장 | mixed language 성분명 보존 |
| `low_quality_photo_001` | 흐림/기울어짐 | OCR 실패 warning, 사용자 수동 입력 경로 유지 |
| `no_layout_text_only_001` | OCRResult.pages 없음 | layout unavailable fallback |
| `manual_ocr_text_001` | 사용자가 붙여넣은 OCR text | raw text 미저장, hash 저장, user confirmation |
| `external_ocr_consent_missing_001` | 외부 OCR 동의 없음 | Google/CLOVA 호출 차단 |

### 5.4 이미지 fixture 정책

- 실제 상용 제품 라벨 이미지는 저작권과 개인정보 이슈가 있을 수 있으므로, 기본 fixture는 synthetic 또는 팀이 직접 촬영하고 사용 권한을 확인한 샘플만 사용한다.
- 이미지에 사람, 처방전, 검사표, 주소, 연락처 등 민감정보가 포함되면 supplement label fixture로 쓰지 않는다.
- fixture manifest에 `contains_personal_data=false`를 명시하고, review checklist에 근거를 남긴다.

## 6. 성공 기준

Phase 0에서는 “제품 성능 수치”가 아니라 “측정 가능한 기준과 측정 방식”을 고정한다.

### 6.1 OCR 성공률

정의:

- fixture case 중 OCR provider가 non-empty text를 반환하고, 필수 anchor 중 최소 하나를 감지하면 OCR 성공으로 본다.

측정 방식:

- `ocr_success_rate = successful_cases / executable_cases`
- provider별로 따로 기록한다.
- mock test 수치는 실제 provider 성능으로 주장하지 않는다.

권장 gate:

- `mock`: 100% 통과
- `real smoke`: 수치 기록만 수행, release gate로 쓰려면 별도 sample size와 재현 조건을 확정해야 한다.

### 6.2 필드 추출 정확도

정의:

- expected snapshot과 parser snapshot을 field path 단위로 비교한다.

필드 그룹:

- product fields
- serving fields
- ingredient name/amount/unit
- intake method
- precautions
- functional claims
- low confidence markers

측정 방식:

- exact match가 가능한 필드는 exact match
- 금액/함량 숫자는 numeric tolerance를 별도 설정하지 않는다. OCR/파서 단계에서는 정확한 숫자 보존이 중요하므로 다르면 실패로 기록한다.
- fuzzy match는 평가 리포트에서 보조 지표로만 둔다.

### 6.3 raw image/text 미저장

검증 항목:

- DB에 raw image bytes가 저장되지 않는다.
- DB에 raw OCR text 전체가 저장되지 않는다.
- audit metadata에 raw OCR text, provider request, API key, Authorization header가 없다.
- OCR text hash는 HMAC 기반 fingerprint로만 허용한다.

### 6.4 사용자 확인 필수

검증 항목:

- `/supplements/analyze` 결과 status는 confirmation required 계열이어야 한다.
- OCR/LLM 후보가 바로 `user_supplement` 확정 레코드로 저장되지 않는다.
- 등록 API는 별도 user confirmation payload를 요구한다.
- low confidence field가 있으면 모바일 UI에서 확인 대상으로 표시할 수 있어야 한다.

## 7. 회귀 테스트 범위

### 7.1 Google Vision mock

목표:

- `DOCUMENT_TEXT_DETECTION` 요청 feature 확인
- `fullTextAnnotation` hierarchy normalization 확인
- text-only fallback 확인
- transient error retry와 sanitized error 확인
- raw provider response 저장 금지 확인

테스트 파일 후보:

- `tests/unit/ocr/test_google_vision_provider.py`
- `tests/integration/api/test_supplement_analyze_google_vision.py`

### 7.2 CLOVA mock

목표:

- `X-OCR-SECRET` header는 request에만 쓰고 logs/audit에는 남기지 않는다.
- `fields[]`, `tables[]`가 `OCRResult.pages`로 정규화된다.
- WebP 입력은 bytes 변환 없이 `format=png`로 보내지 않도록 명확히 처리한다.
- external OCR consent가 없으면 호출되지 않는다.

테스트 파일 후보:

- `tests/unit/ocr/test_clova_provider.py`
- `tests/unit/services/test_supplement_image_analysis.py`

### 7.3 local OCR mock

목표:

- local OCR adapter는 network 없이 동작한다.
- dependency missing 시 graceful unavailable warning을 반환한다.
- primary OCR이 없어도 fallback-only 설정에서 실행할지 정책을 명확히 테스트한다.

테스트 파일 후보:

- `tests/unit/ocr/test_paddle_provider.py`
- `tests/unit/ocr/test_ocr_factory.py`
- `tests/unit/services/test_supplement_image_analysis.py`

### 7.4 manual OCR text

목표:

- `/supplements/analyses/{analysis_id}/ocr-text`가 raw text를 저장하지 않는다.
- OCR text hash 충돌/재입력 conflict를 처리한다.
- local Ollama parser unavailable과 invalid schema를 502 계열로 안전하게 매핑한다.
- parse 결과는 항상 confirmation required 상태로 남는다.

테스트 파일 후보:

- `tests/integration/api/test_supplement_ocr_text_api.py`
- `tests/unit/services/test_supplement_parser.py`

## 8. 구현 플랜

현재 반영 상태(2026-05-17):

| 항목 | 상태 | 구현 파일 |
| --- | --- | --- |
| R0 기준선 manifest | 완료 | `backend/Nutrition-backend/tests/fixtures/supplement_labels/manifest.json`, `images/*.png`, `ocr/*.txt` |
| R1 `SupplementParsedSnapshotV2` schema | 완료 | `backend/Nutrition-backend/src/models/schemas/supplement_snapshot.py` |
| R2 expected snapshot | 완료 | `backend/Nutrition-backend/tests/fixtures/supplement_labels/expected/*.snapshot_v2.json` |
| R3 baseline evaluator | 완료 | `backend/scripts/evaluate_supplement_ocr_baseline.py`, `backend/Nutrition-backend/tests/unit/scripts/test_evaluate_supplement_ocr_baseline.py` |
| R4 API/service invariant tests | 미완료 | 후속 Phase에서 `/supplements/analyze`, OCR consent, confirmation persistence와 연결 필요 |
| R5 documentation sync | 부분 완료 | 본 문서 구현 상태 반영 완료. current-state map과 모바일 문서의 표현 정리는 후속 문서 동기화 범위 |

### R0. 기준선 manifest 작성

파일:

- `docs/Nutrition-docs/48-phase0-supplement-ocr-baseline-freeze-design-plan.md`
- `backend/Nutrition-backend/tests/fixtures/supplement_labels/manifest.json`

작업:

- 현재 기능을 `runtime-connected`, `runtime-gated`, `module-only`, `docs-only`, `test-only`, `blocked`로 분류한다.
- fixture case id와 expected output 파일명을 고정한다.
- 실제 이미지는 synthetic 또는 consent-cleared sample만 추가한다.

완료 기준:

- manifest JSON parse 통과
- 문서에 공식 기준 URL 포함
- fixture policy에 raw data/privacy 제한 명시

### R1. `SupplementParsedSnapshotV2` Pydantic schema 추가

파일 후보:

- `backend/Nutrition-backend/src/models/schemas/supplement_parser.py`
- 또는 `backend/Nutrition-backend/src/models/schemas/supplement_snapshot.py`

작업:

- V1 schema와 호환되도록 신규 class를 추가한다.
- `extra="forbid"`와 bounded field length를 적용한다.
- `evidence_refs`, `low_confidence_fields`, `warnings`를 표준화한다.

완료 기준:

- `model_json_schema()` 생성 가능
- schema snapshot test 추가
- invalid extra field 거부 테스트 추가

### R2. fixture expected snapshot 추가

파일:

- `tests/fixtures/supplement_labels/expected/*.snapshot_v2.json`

작업:

- 최소 6개 case의 expected V2 snapshot을 작성한다.
- OCR provider별 expected를 분리한다.
- 수동 OCR text case는 image 없이도 동작하게 한다.

완료 기준:

- expected JSON parse 통과
- 모든 expected snapshot이 `SupplementParsedSnapshotV2` validation 통과

### R3. baseline evaluator script 추가

파일 후보:

- `backend/scripts/evaluate_supplement_ocr_baseline.py`
- `backend/Nutrition-backend/tests/unit/scripts/test_evaluate_supplement_ocr_baseline.py`

작업:

- manifest를 읽는다.
- actual parser output과 expected snapshot을 비교한다.
- OCR success rate, field exact match, raw storage invariant, confirmation invariant를 report한다.

완료 기준:

- fixture 없이도 친절한 error
- fixture가 있으면 deterministic JSON report 생성
- fake provider 기반 CI 실행 가능

### R4. API/service invariant tests 추가

작업:

- `/supplements/analyze` multipart contract 회귀 테스트
- raw image/text 미저장 테스트
- consent missing 시 외부 OCR 미호출 테스트
- confirmation required 상태 고정 테스트

완료 기준:

- targeted pytest 통과
- provider secret이 response/audit에 노출되지 않음

### R5. documentation sync

작업:

- `docs/Nutrition-docs/22-current-implementation-status-map.md` 또는 후속 status map에 Phase 0 분류표 반영
- `docs/Nutrition-docs/33-three-tier-ocr-pipeline-implementation-guide.md`에서 Phase 0 기준선 링크 추가
- 모바일 문서에는 아직 추천/권장 기능이 완성되지 않았음을 명시

완료 기준:

- planning doc과 current-state doc의 표현이 충돌하지 않음
- 팀원이 Phase 1 착수 전 이 문서를 기준으로 fixture/test 범위를 찾을 수 있음

## 9. 품질 게이트

권장 명령:

```bash
cd yeong-Lemon-Aid/backend
.venv/bin/python -m pytest \
  Nutrition-backend/tests/unit/ocr \
  Nutrition-backend/tests/unit/parsing/test_layout_parser.py \
  Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py \
  Nutrition-backend/tests/unit/services/test_supplement_parser.py \
  Nutrition-backend/tests/integration/api/test_supplement_analyze_google_vision.py \
  Nutrition-backend/tests/integration/api/test_supplement_ocr_text_api.py \
  -q --no-cov
```

추가 gate:

```bash
cd yeong-Lemon-Aid/backend
.venv/bin/python -m pytest Nutrition-backend/tests/unit/scripts/test_evaluate_supplement_ocr_baseline.py -q --no-cov
```

문서/JSON hygiene:

```bash
python -m json.tool backend/Nutrition-backend/tests/fixtures/supplement_labels/manifest.json >/dev/null
git diff --check
```

## 10. Phase 0 완료 정의

Phase 0은 아래 조건을 모두 만족해야 완료로 본다.

- `SupplementParsedSnapshotV2` 계약이 문서와 Pydantic schema 양쪽에 존재한다.
- 최소 fixture manifest와 expected snapshot이 존재한다.
- Google Vision mock, CLOVA mock, local OCR mock, manual OCR text 경로가 회귀 테스트 범위에 포함된다.
- raw image/text 미저장 invariant가 테스트로 고정된다.
- 모든 OCR/LLM 결과는 사용자 확인 전까지 preview 후보로만 남는다.
- 추천/권장 기능은 Phase 0에서 구현 완료로 표시하지 않는다.

## 11. 후속 Phase 연결

| 후속 Phase | Phase 0에서 넘겨야 하는 계약 |
| --- | --- |
| Phase 1 parser schema 확장 | `SupplementParsedSnapshotV2` Pydantic schema와 expected snapshot |
| Phase 2 layout parser 연결 | `label_sections`와 `evidence_refs` |
| Phase 3 OCR fallback 수정 | provider별 fixture와 fallback invariant |
| Phase 4 recommendation service | user-confirmed supplement ingredient와 daily amount 계산 기준 |
| Phase 5 mobile UX | low confidence fields, warnings, confirmation required status |
| Phase 6 release hardening | raw data 미저장, consent, auth, provider secret 처리 기준 |
