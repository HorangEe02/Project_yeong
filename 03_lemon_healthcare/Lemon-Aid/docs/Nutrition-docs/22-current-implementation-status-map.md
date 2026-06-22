# Current Implementation Status Map

작성일: 2026-05-15

## Weekly Snapshot

스냅샷 기준: 2026-05-15 로컬 backend 재검증 결과. 상태값은 `done`, `open`, `blocked`만 사용하며, 이번 주간 범위에서 `blocked` 항목은 없다.

| 항목 | 상태 | 근거 | 남은 작업 |
| --- | --- | --- | --- |
| KDRIs 2025 전환 | `done` | `data/nutrition_reference/kdris/kdris_2025.csv` 1,795개 approved row 검증, KDRIs 2025 API/unit 테스트 기준 재정렬, `KDRIS_DATA_VERSION=2025`, `ALLOW_SAMPLE_KDRIS=false` | 없음 |
| JWT production 경로 | `done` | JWKS key rotation, missing `kid`, timeout, invalid alg, token-use/id-token confusion 테스트와 OpenAPI `BearerAuth` contract 통과 | 운영 배포 전 실제 IdP discovery preflight 실행 |
| 만성질환자 부족 영양소 우선순위 | `done` | chronic condition mapping, unknown disease ignore, 금지 표현 테스트 통과 | 질환별 룩업 확장은 추가 근거 확보 후 별도 진행 |
| Feature flag default-off 정리 | `done` | AI/vision/learning/Hall-lite 및 regulated feature flag 기본값과 production guard 정렬 | 없음 |

| 검증 | 명령 | 결과 |
| --- | --- | --- |
| Formatting | `.venv/bin/black --check src tests alembic` | pass, 160 files unchanged |
| Lint | `.venv/bin/ruff check src tests alembic` | pass |
| Type check | `.venv/bin/mypy src tests --strict` | pass, 155 source files |
| Full pytest coverage | `.venv/bin/python -m pytest --cov-report=term-missing` | pass, `313 passed, 1 skipped`, total coverage `87.75%` |
| KDRIs production validator | `.venv/bin/python scripts/validate_kdris_dataset.py --require-approved` | pass, 1,795 rows validated |

이전 계획 입력의 `267 passed, 1 skipped`와 2026-05-14 재검증의 `310 passed, 1 skipped`는 현재 코드 기준 재검증 결과와 다르므로, 이 주간 스냅샷에는 오늘 실행한 `313 passed, 1 skipped`를 실제 결과로 기록한다. 이번 재검증에서는 KDRIs 2025 기준 테스트 드리프트 7건과 `SecretStr` 타입 불일치 mypy 1건을 정리했다.

이 문서는 현재 로컬 코드 기준으로 실제 연결된 기능과 아직 스캐폴드 또는 설계 단계인 기능을 구분한다. 문서에 남아 있던 `OllamaAdapter`, Google/CLOVA OCR provider, `OCRPipeline`, `SupplementService` 같은 표현은 현행 구현체 이름이 아니라 과거 설계 예시 또는 후속 adapter 후보로 취급한다.

## 요약

| 영역 | 실제 연결 상태 | 현재 한계 |
| --- | --- | --- |
| Supplement image intake | `/api/v1/supplements/analyze`에서 라우터, 권한, 동의, 이미지 검증, preview 저장까지 연결됨 | 기본 호출은 OCR/YOLO adapter를 주입하지 않으므로 intake-only |
| Supplement OCR text parse | `/api/v1/supplements/analyses/{analysis_id}/ocr-text`에서 OCR text attach, local structured parser, 사용자 확인 preview 갱신까지 연결됨 | 외부 OCR provider adapter는 아직 미연결 |
| Supplement registration | `/api/v1/supplements`의 생성/조회/목록/삭제가 등록 서비스와 DB 모델까지 연결됨 | 저장 전 사용자 확인이 전제이며 자동 제품 매칭 고도화는 별도 과제 |
| Dashboard | `/api/v1/dashboard/summary`가 nutrition, activity, weight, supplement summary read model을 조회 | 프론트엔드 화면 구현 범위는 이 문서에서 검증하지 않음 |
| Privacy | `/api/v1/me/privacy/*`, 삭제 요청, 감사 로그, 동의 정책이 연결됨 | 이미지 학습 동의는 정책과 gate만 있으며 실제 업로드 플로우는 없음 |
| Health | `/api/v1/health/sync`가 모바일 health aggregate sync와 DB 저장까지 연결됨 | HealthKit/Health Connect 클라이언트 SDK 직접 연동은 서버 범위 밖 |
| Prediction/weight | `/api/v1/predictions/weight`가 selector를 통해 기본 7-step fallback과 Hall-lite feature-flag 경로에 연결됨 | 기본값은 기존 7-step이며 Hall-lite는 production sign-off 전 비활성 |
| OllamaSupplementParser | OCR text가 있을 때 `parse_supplement_analysis_ocr_text`에서 기본 parser로 사용됨 | 이미지 입력 기반 multimodal parser는 미연결 |
| AI/image/learning flags | 설정값과 production guard, 일부 서비스 gate까지 존재 | 실제 YOLO inference, pgvector table, embedding 생성, 이미지 학습 적재는 미구현 |

## Supplement Intake

현재 endpoint는 `backend/src/api/v1/supplements.py`의 `POST /api/v1/supplements/analyze`다. 이 라우트는 `supplement:write` scope와 `ocr_image_processing` 동의를 요구하고, 성공 시 `202 Accepted`와 `SupplementAnalysisPreview`를 반환한다.

실행 흐름은 다음과 같다.

1. `require_user_consent(..., ConsentType.OCR_IMAGE_PROCESSING)`로 OCR 이미지 처리 동의를 확인한다.
2. `analyze_supplement_image`를 호출한다.
3. `read_and_validate_supplement_image`가 파일 크기, MIME type, 이미지 pixel 제한을 검증한다.
4. `create_supplement_analysis_intake`가 `supplement_analysis_runs` preview row를 저장한다.
5. 기본 호출에는 OCR, parser, vision adapter가 주입되지 않으므로 raw image storage나 외부 provider 호출 없이 intake-only로 종료한다.

OCR provider 없이도 구조화 parsing을 검증할 수 있도록 `POST /api/v1/supplements/analyses/{analysis_id}/ocr-text`가 추가되어 있다. 이 라우트는 `ocr_image_processing` 동의를 요구하고, OCR text를 raw 저장하지 않은 채 `parse_supplement_analysis_ocr_text`로 넘긴다. 저장되는 것은 `ocr_text_hash`, `ocr_provider`, `ocr_confidence`, sanitized `parsed_snapshot`, warning metadata뿐이다. 성공 후에도 status는 `requires_confirmation`이며, 최종 저장은 별도 사용자 확인 flow를 거친다.

저장되는 DB 모델은 `SupplementAnalysisRun`이다. 현재 저장 항목은 `owner_subject`, `image_sha256`, `image_mime_type`, `image_size_bytes`, preview `status`, `parsed_snapshot`, `warnings`, `algorithm_version`, `expires_at` 등이다. raw image bytes와 raw OCR text는 저장하지 않는다.

## Supplement Registration

등록 endpoint는 `backend/src/api/v1/supplements.py`의 `POST /api/v1/supplements`다. 이 라우트는 `supplement:write` scope와 `sensitive_health_analysis` 동의를 요구한다.

연결된 서비스는 `backend/src/services/supplement_registration.py`이며, 주요 동작은 다음과 같다.

1. 사용자 확인 payload를 `UserSupplementCreate`로 검증한다.
2. 선택적으로 `analysis_id` preview 상태와 만료 여부를 확인한다.
3. `UserSupplement`, `UserSupplementIngredient` row를 저장한다.
4. preview에서 등록한 경우 `SupplementAnalysisRun.status`를 `confirmed`로 전환한다.

조회/목록/삭제도 같은 라우터에 연결되어 있다.

| Method | Path | 연결 상태 |
| --- | --- | --- |
| `GET` | `/api/v1/supplements` | current-user supplement list |
| `GET` | `/api/v1/supplements/{supplement_id}` | current-user supplement detail |
| `DELETE` | `/api/v1/supplements/{supplement_id}` | soft delete |

## Dashboard

Dashboard endpoint는 `backend/src/api/v1/dashboard.py`의 `GET /api/v1/dashboard/summary`다. `dashboard:read` scope와 `sensitive_health_analysis` 동의를 요구한다.

집계 서비스는 `backend/src/services/dashboard.py`의 `build_dashboard_summary`다. 현재 summary는 아래 read model을 조합한다.

| Dashboard 카드 | 데이터 소스 |
| --- | --- |
| Nutrition | latest `AnalysisResult`의 nutrition diagnosis snapshot |
| Activity | recent `HealthDailySummary`와 latest activity score `AnalysisResult` |
| Weight | recent `HealthDailySummary.weight_kg`와 latest weight prediction `AnalysisResult` |
| Supplements | active `UserSupplement` count와 review 필요 `SupplementAnalysisRun` count |

## Privacy

Privacy 라우터는 `backend/src/api/v1/privacy.py`이며 `/api/v1/me` prefix 아래에 연결된다.

| Method | Path | 연결 상태 |
| --- | --- | --- |
| `GET` | `/api/v1/me/privacy/consents` | 현재 동의 상태 조회 |
| `POST` | `/api/v1/me/privacy/consents/{consent_type}` | 동의 grant event 저장 |
| `DELETE` | `/api/v1/me/privacy/consents/{consent_type}` | 동의 revoke event 저장 |
| `POST` | `/api/v1/me/data-deletion-requests` | all-user-data 삭제 요청 생성 및 즉시 처리 |
| `GET` | `/api/v1/me/data-deletion-requests/{deletion_request_id}` | 삭제 요청 상태 조회 |

동의 정책은 `backend/src/privacy/consent_policies.py`의 `ACTIVE_CONSENT_POLICIES`에 정의되어 있다. 현재 포함된 consent type은 `sensitive_health_analysis`, `health_device_data`, `ocr_image_processing`, `data_retention`, `image_learning_dataset`이다.

`image_learning_dataset`은 이미지 학습 재사용을 위한 명시 동의 항목으로 추가되어 있지만, 실제 이미지 vector upload endpoint와 worker는 아직 없다.

## Health

Health endpoint는 `backend/src/api/v1/health.py`의 `POST /api/v1/health/sync`다. `health:write` scope와 `health_device_data` 동의를 요구한다.

연결된 서비스는 `backend/src/services/health_sync.py`의 `sync_health_daily_aggregates`다. DB 모델은 `HealthSyncBatch`와 `HealthDailySummary`이며, `source_platform`, `steps`, `weight_kg`, `resting_heart_rate_bpm`, `active_energy_kcal` 같은 일 단위 aggregate를 저장한다.

## Prediction/Weight

Weight prediction endpoint는 `backend/src/api/v1/predictions.py`의 `POST /api/v1/predictions/weight`다. 현재 구현은 `backend/src/prediction/selector.py`의 `predict_weight_periods_selected`를 통해 기본 7-step fallback과 Hall-lite feature-flag 경로에 연결되어 있다.

현재 알고리즘은 다음 성격이다.

- 기본 응답은 BMR/TDEE 기반 7-step 정적 근사다.
- `KCAL_PER_KG_FAT=7700.0`, 감량 보정 `0.85`, 증량 보정 `0.95`를 사용한다.
- 90일 이상 예측에는 동적 모델 검토 필요 warning을 반환한다.
- `backend/src/prediction/body_composition.py`가 Deurenberg 기반 초기 FM/FFM 추정과 측정 체지방률 우선 로직을 제공한다.
- `backend/src/prediction/hall.py`가 kJ 내부 단위, BMR/TDEE baseline 보정, Hall-lite 일별 시뮬레이션 primitive를 제공한다.
- `backend/src/prediction/selector.py`가 `feature_hall_lite_weight_prediction=false`, `weight_prediction_engine="static_7step"` 기본값에서 기존 7-step 결과를 유지한다.
- `weight_prediction_engine="auto"`와 feature flag가 모두 켜진 경우 90일 이상 기간은 Hall-lite 후보가 된다.
- production에서는 `FEATURE_HALL_LITE_WEIGHT_PREDICTION=true`가 validation sign-off 전 금지된다.

## OllamaSupplementParser

현행 구현체 이름은 `OllamaSupplementParser`다. `OllamaAdapter` 클래스는 현재 코드에 없다.

연결 지점은 `backend/src/services/supplement_parser.py`의 `parse_supplement_analysis_ocr_text`다. OCR adapter가 text를 반환하면 `analyze_supplement_image`가 이 함수를 호출하고, parser가 명시 주입되지 않은 경우 `OllamaSupplementParser(settings)`를 기본값으로 사용한다.

API 연결 지점은 `backend/src/api/v1/supplements.py`의 `POST /api/v1/supplements/analyses/{analysis_id}/ocr-text`다. 이 endpoint는 OCR provider가 아직 없는 환경에서도 OCR text 기반 structured preview를 생성하기 위한 우선 구현 경로다.

보호 장치는 다음과 같다.

- OCR text는 normalization 후 HMAC-SHA256 hash만 저장한다.
- raw OCR text와 Ollama raw response는 DB에 저장하지 않는다.
- `ALLOW_EXTERNAL_LLM=false`일 때 `OLLAMA_BASE_URL`은 `localhost`, `127.0.0.1`, `::1`만 허용한다.
- output은 `SupplementStructuredParseResult` Pydantic schema로 검증된다.

현재 연결되지 않은 부분은 다음과 같다.

- 이미지 파일을 직접 Ollama vision model로 보내는 multimodal Image-to-Text adapter
- `ENABLE_MULTIMODAL_LLM=true`에서 실행되는 별도 multimodal 라우팅
- `OllamaAdapter`라는 추상 adapter 구현체

## AI/Image/Learning Flags

주간 스냅샷 기준 `Feature flag default-off 정리`는 `done`이다. AI/vision/learning/Hall-lite gate와 non-P1 regulated feature flag는 기본 `false`이며, production에서는 sign-off 없이 `true`로 실행할 수 없도록 guard가 고정되어 있다.

| 설정 | 기본값 | 실제 연결 상태 |
| --- | --- | --- |
| `ALLOW_EXTERNAL_LLM` | `false` | production에서 true 금지. Ollama host local guard에 사용 |
| `LLM_PROVIDER` | `ollama` | `OllamaSupplementParser`가 local Ollama만 허용 |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | `OllamaSupplementParser`의 `/api/chat` 호출 endpoint |
| `OLLAMA_MODEL` | `qwen3.5:9b` | OCR text structured parsing model |
| `OLLAMA_VISION_MODEL` | `gemma4:e4b` | 설정만 존재. 런타임 미연결 |
| `ENABLE_MULTIMODAL_LLM` | `false` | production guard와 `llm/base.py` 계약에만 존재. 런타임 adapter 없음 |
| `ENABLE_VISION_CLASSIFIER` | `false` | `analyze_supplement_image`에서 vision adapter 필수 여부를 결정 |
| `VISION_CLASSIFIER_MODEL` | `yolov8n.pt` | 설정만 존재. 실제 Ultralytics runner 없음 |
| `ENABLE_IMAGE_LEARNING_PIPELINE` | `false` | `learning/consent_gate.py`와 retention helper에서만 사용 |
| `ENABLE_PGVECTOR_STORAGE` | `false` | learning gate와 `DisabledVectorStore` 계약에만 존재 |
| `EMBEDDING_MODEL` | `clip-ViT-B-32` | 설정만 존재. embedding runner 없음 |
| `IMAGE_RETENTION_DAYS` | `0` | retention helper와 learning gate에서 사용. 0은 즉시 삭제 정책 의미 |
| `FEATURE_PRESCRIPTION_OCR_INTAKE` | `false` | 설정과 문서 guardrail 성격. 전용 endpoint는 아직 없음 |
| `FEATURE_LAB_RESULT_OCR_INTAKE` | `false` | 설정과 문서 guardrail 성격. 전용 endpoint는 아직 없음 |
| `FEATURE_DOSAGE_CHANGE_RECOMMENDATION` | `false` | 직접 복용량 변경 안내 금지 guardrail 성격 |
| `FEATURE_MEDICATION_SAFETY_ALERT` | `false` | 설정 존재. 별도 알림 workflow는 이 문서에서 확인되지 않음 |

`config/implementation-readiness.settings.json`의 `FEATURE_HOSPITAL_MOCK_FHIR` 기본값도 `false`로 고정되어 있다. 현재 backend `Settings` 필드에는 대응 값이 없으므로, 이 문서에서는 runtime 연결 상태를 확인하지 않는다.

## Vision/YOLO Status

`backend/src/vision/yolo.py`의 `YoloLabelDetector`는 gated ROI-only detector entry point다. 실제 Ultralytics runtime은 `backend/src/vision/ultralytics_runner.py`에 격리되어 있으며, `ENABLE_VISION_CLASSIFIER=true`일 때만 lazy-load 된다.

현재 동작은 다음과 같다.

- `ENABLE_VISION_CLASSIFIER=false`이면 `VisionError`를 발생시킨다.
- `ENABLE_VISION_CLASSIFIER=true`이면 `supplement_label`, `supplement_bottle`, `blister_pack` ROI 후보만 허용한다.
- `ultralytics` optional dependency 또는 검증된 model weight가 없으면 `VisionError`로 fail closed 된다.
- 검출 결과는 `BoundingBox` metadata로만 반환되며 제품명, 성분명, 함량, 복용법을 반환하지 않는다.
- `/api/v1/supplements/analyze` 기본 호출에는 `VisionAdapter`가 주입되지 않는다.

따라서 문서나 코드에서 `YoloLabelDetector`를 “제품/성분 추출 모델”로 표현하면 안 된다. 정확한 표현은 “gated YOLO ROI helper”다.

멀티모달 Ollama와 YOLO 실험 상세 설계는 `docs/Nutrition-docs/30-multimodal-yolo-experiment-plan.md`를 따른다. 해당 플랜의 핵심 제약은 YOLO를 제품명/성분 추출 주 경로로 쓰지 않고, 영양제 병/라벨/블리스터 ROI 보조에만 쓰는 것이다.

## Learning/Vector DB Status

학습 파이프라인은 독립 모듈 골격에서 한 단계 진행되어, default-off 상태를 유지한 채 DB schema, object storage adapter, embedding runner, pgvector upsert adapter, worker 골격, analyze/confirmation 연결까지 추가되어 있다. 운영 활성화는 아직 금지이며 실제 PostgreSQL/pgvector, 실제 embedding model, 실제 object storage smoke test가 남아 있다.

| 파일 | 현재 역할 |
| --- | --- |
| `backend/src/learning/consent_gate.py` | 이미지 학습 재사용 가능 여부를 feature flag와 consent로 판단 |
| `backend/src/learning/retention.py` | retention 활성 여부와 만료 시각 계산 |
| `backend/src/learning/embeddings.py` | embedding 생성 adapter 계약과 disabled runner |
| `backend/src/learning/embedding_runner.py` | optional `sentence-transformers` 기반 local embedding runner |
| `backend/src/learning/object_storage.py` | disabled/local/S3-compatible image object storage adapter |
| `backend/src/learning/vector_store.py` | vector store 계약과 disabled pgvector store |
| `backend/src/learning/pgvector_store.py` | raw SQL `CAST(:embedding AS vector)` 기반 pgvector upsert adapter |
| `backend/src/learning/upsert_worker.py` | DB-backed embedding job worker |
| `backend/src/learning/pipeline.py` | analyze 단계 object 저장, confirmation 단계 job enqueue, deletion/retention helper |
| `backend/src/models/schemas/learning.py` | gate decision response schema |
| `backend/src/models/db/learning.py` | learning image object, embedding job, embedding record ORM schema |
| `backend/alembic/versions/0005_create_learning_vector_tables.py` | `vector` extension과 learning table migration |

아직 운영 전 확인이 필요한 것은 다음과 같다.

- 실제 PostgreSQL 환경에서 pgvector extension migration 적용
- `clip-ViT-B-32` output dimension probe와 `EMBEDDING_DIMENSIONS` 확정
- 실제 pgvector insert/query smoke test
- 실제 S3 또는 S3-compatible object storage smoke test
- fixture 기반 similarity 품질/latency 리포트와 HNSW index 추가 여부 결정

## 잔여 불일치 정리 기준

활성 문서에서 아래 표현은 현행 구현과 맞지 않으므로 정리 대상이다.

- `OllamaAdapter`: 현행 구현체는 `OllamaSupplementParser`
- `SupplementService`: 현행 이미지 분석 orchestration은 `analyze_supplement_image`
- `OCRPipeline`: 현행 runtime은 adapter 주입형 `SupplementImageAnalysisAdapters`
- `GoogleVisionOCR`, `ClovaOCR`: provider adapter 후보일 뿐 현재 코드에 없음
- `YoloLabelDetector`: gated YOLO ROI helper. 제품/성분 추출이 아니라 OCR ROI metadata만 반환

`docs/Nutrition-docs/previous-version/` 아래 문서는 과거 snapshot이므로 현재 구현 문서로 사용하지 않는다.
