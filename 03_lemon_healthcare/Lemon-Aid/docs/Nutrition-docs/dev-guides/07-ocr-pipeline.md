# dev-guides/07 — OCR Intake Pipeline Current Status

작성일: 2026-05-13

이 문서는 현재 코드에 존재하는 OCR intake 연결 상태만 설명한다. 과거 provider별 설계 예시는 `docs/Nutrition-docs/previous-version/dev-guide-07-ocr-pipeline-design-example.md`로 이동했다.

## 현재 구현

현재 서버는 영양제 이미지 업로드를 intake-only로 처리할 수 있다.

| 구간 | 현재 파일 | 상태 |
| --- | --- | --- |
| 이미지 검증 | `backend/src/services/supplement_intake.py` | 연결됨 |
| OCR adapter 계약 | `backend/src/ocr/base.py` | 연결됨 |
| no-op OCR provider | `backend/src/ocr/providers/noop.py` | 구현됨 |
| 이미지 분석 orchestration | `backend/src/services/supplement_image_analysis.py` | 연결됨 |
| API endpoint | `backend/src/api/v1/supplements.py` | `POST /api/v1/supplements/analyze` 연결됨 |
| OCR text attach endpoint | `backend/src/api/v1/supplements.py` | `POST /api/v1/supplements/analyses/{analysis_id}/ocr-text` 연결됨 |

기본 이미지 업로드 API 호출은 OCR provider를 주입하지 않는다. 따라서 현재 production-safe 기본 동작은 이미지 검증, hash 생성, preview 저장까지 수행하고 OCR text 추출은 실행하지 않는 방식이다. OCR provider 없이도 구조화 parsing을 검증할 수 있도록, 기존 preview에 OCR text를 별도로 attach하는 endpoint가 추가되어 있다.

## Runtime Flow

```text
POST /api/v1/supplements/analyze
  -> require OCR_IMAGE_PROCESSING consent
  -> read_and_validate_supplement_image
  -> create_supplement_analysis_intake
  -> optional OCRAdapter.extract_text
  -> optional parse_supplement_analysis_ocr_text

POST /api/v1/supplements/analyses/{analysis_id}/ocr-text
  -> require OCR_IMAGE_PROCESSING consent
  -> normalize OCR text
  -> HMAC hash OCR text
  -> parse_supplement_analysis_ocr_text
  -> return requires_confirmation preview
```

`NoopOCRAdapter`는 외부 provider 호출 없이 빈 OCR 결과를 반환하는 테스트/비활성 환경용 provider다. 실제 OCR provider를 추가할 때는 `OCRAdapter.extract_text` 계약을 구현하고, provider별 공식 API 문서를 확인한 뒤 별도 adapter 파일로 추가해야 한다.

## 연결되지 않은 항목

- 외부 OCR provider adapter
- OCR result cache
- OCR provider fallback chain
- OCR confidence normalization beyond adapter result validation
- raw image object storage

## 후속 구현 기준

외부 OCR provider는 `docs/Nutrition-docs/35-google-vision-ocr-provider-implementation-plan.md`와 `docs/Nutrition-docs/36-post-p1-execution-plan.md` 기준으로 Google Vision MVP부터 착수한다. 기본값은 `OCR_PRIMARY_PROVIDER=none`, `ALLOW_EXTERNAL_OCR=false`이며, `EXTERNAL_OCR_PROCESSING` 동의가 없으면 외부 OCR을 호출하지 않는다.

3-tier OCR 확장은 Google Vision MVP가 통과된 뒤 `docs/Nutrition-docs/33-three-tier-ocr-pipeline-implementation-guide.md`를 기준으로 진행한다. YOLO ROI는 OCR 입력 crop 후보로만 사용하고, Ollama vision assist는 OCR empty 또는 low-confidence fallback으로만 호출한다.

## 구현 시 주의사항

- raw OCR text는 DB에 저장하지 않는다.
- OCR text는 parser 호출 전 normalization과 HMAC hash 경로를 거쳐야 한다.
- 민감정보가 포함된 이미지는 외부 provider로 전송하기 전에 별도 승인 gate와 문서화가 필요하다.
- provider adapter 구현 전에는 provider의 최신 공식 API 문서를 반드시 확인하고 URL을 PR 설명과 문서에 남긴다.

## 검증 포인트

- `tests/unit/services/test_supplement_image_analysis.py`
- `tests/unit/services/test_supplement_intake.py`
- `tests/integration/api/test_supplement_ocr_text_api.py`
- `POST /api/v1/supplements/analyze`의 `403 consent_required`, `413`, `415`, `202` 경로
- `POST /api/v1/supplements/analyses/{analysis_id}/ocr-text`의 `200`, `403`, `404`, `409`, `422`, `502` 경로
