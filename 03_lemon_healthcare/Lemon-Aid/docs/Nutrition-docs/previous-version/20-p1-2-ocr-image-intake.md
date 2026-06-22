# 20. P1-2 OCR Image Intake

> 상태: 구현 완료(단일 이미지) + 다중 이미지 확장 계획 | 기준일: 2026-05-12 | 범위: 영양제 라벨 이미지 intake, preview row 저장, batch intake 후보 계약

## 1. 목적

P1-2는 실제 OCR/LLM 추출을 수행하는 단계가 아니다. 모바일 앱이 업로드한 영양제 라벨 이미지를 백엔드가 안전하게 받아 검증하고, OCR/LLM 후속 처리를 위한 preview row를 `supplement_analysis_runs`에 저장하는 경계를 구현한다.

## 2. 구현 범위

- `POST /api/v1/supplements/analyze`의 P1-0 stub 제거
- `supplement:write` scope 유지
- `ocr_image_processing` 동의 확인
- `multipart/form-data` 이미지 intake
- JPEG, PNG, WebP magic bytes 검증
- 선언된 `content_type`과 실제 magic bytes 일치 확인
- byte size와 pixel count 제한
- Pillow 구조 검증
- 이미지 SHA-256 계산
- `supplement_analysis_runs` row 저장
- idempotency key 재시도 처리
- 성공/차단/검증 실패 audit event 기록

## 3. 제외 범위

- 실제 OCR 텍스트 추출
- LLM 구조화 파싱
- 식약처/영양제 reference DB 매칭
- 원본 이미지 저장
- EXIF, 파일명, OCR 원문 저장

## 4. 저장 데이터

| 컬럼 | 저장값 |
|---|---|
| `owner_subject` | 인증된 `iss::sub` 기반 owner key |
| `client_request_id` | 선택 idempotency key |
| `status` | `requires_confirmation` |
| `image_sha256` | 업로드 이미지 bytes SHA-256 |
| `image_mime_type` | 검증된 MIME type |
| `image_size_bytes` | 업로드 byte size |
| `ocr_provider` | `intake-only` |
| `ocr_text_hash` | `NULL` |
| `parsed_snapshot` | 원문 없는 intake metadata, 빈 후보 목록 |
| `match_snapshot` | 빈 매칭 후보 목록 |
| `algorithm_version` | `supplement-intake-v1.0.0` |
| `source_manifest_version` | `NULL` |
| `expires_at` | 설정 기반 preview TTL |

## 5. 보안 결정

- 원본 이미지 bytes는 메모리 검증 후 저장하지 않는다.
- 원본 파일명은 신뢰하지 않고 저장하지 않는다.
- API 응답에는 `image_sha256`, intake metadata, 파일명, OCR 원문을 노출하지 않는다.
- `client_request_id`가 같은 요청은 같은 이미지 hash일 때만 기존 row를 반환한다.
- 같은 `client_request_id`로 다른 이미지 bytes를 보내면 `409 idempotency_conflict`를 반환한다.
- content type spoofing은 `415 unsupported_media_type`으로 차단한다.
- byte limit 또는 pixel limit 초과는 `413 payload_too_large`로 차단한다.
- 깨진 이미지 구조는 `422 invalid_image`로 차단한다.

## 6. 설정값

| 설정 | 기본값 | 목적 |
|---|---:|---|
| `SUPPLEMENT_IMAGE_MAX_BYTES` | 5 MiB | 업로드 byte size 제한 |
| `SUPPLEMENT_IMAGE_MAX_PIXELS` | 12,000,000 | decoded pixel count 제한 |
| `SUPPLEMENT_PREVIEW_TTL_MINUTES` | 30 | 사용자 확인 전 preview 유효 시간 |

## 7. 구현 파일

- API: `backend/src/api/v1/supplements.py`
- Service: `backend/src/services/supplement_intake.py`
- Settings: `backend/src/config.py`
- Tests: `backend/tests/unit/services/test_supplement_intake.py`, `backend/tests/integration/api/test_supplement_intake_api.py`

## 8. 후속 단계

1. P1-3에서 Ollama Structured Outputs parser를 붙이고 `ocr_text_hash`와 `parsed_snapshot` 저장 구조를 구현한다.
2. P1-3b에서 실제 OCR adapter가 P1-3 parser service를 호출하도록 연결한다.
3. P1-4에서 사용자 확인 후 `user_supplements`와 `user_supplement_ingredients`로 승격한다.
4. 운영 전 object storage 저장 여부를 별도 동의와 retention policy로 다시 결정한다.
5. P1-7b/P1-8에서 다중 이미지 batch intake를 별도 endpoint로 추가한다.

## 9. 다중 이미지 intake 전환 계획

현재 구현은 단일 이미지 endpoint인 `POST /api/v1/supplements/analyze`를 기준으로 한다. 다중 이미지 지원은 기존 endpoint를 깨지 않기 위해 새 endpoint 후보 `POST /api/v1/supplements/analyze-batch`로 분리한다.

### 9.1 API 후보

| 항목 | 후보 값 |
|---|---|
| Endpoint | `POST /api/v1/supplements/analyze-batch` |
| Content-Type | `multipart/form-data` |
| File field | `files: list[UploadFile]` |
| Form fields | `client_batch_id`, `metadata_json` |
| Max files | `6` |
| Per-file limit | 기존 `SUPPLEMENT_IMAGE_MAX_BYTES`, `SUPPLEMENT_IMAGE_MAX_PIXELS` 유지 |
| Batch total limit | `SUPPLEMENT_IMAGE_BATCH_MAX_BYTES=20 MiB` |
| 동의 | `ocr_image_processing` 활성 동의 필수 |

`metadata_json`은 `client_image_id`, `image_role`, `sort_order`를 파일 순서와 매칭한다. form-data는 JSON body와 동시에 사용할 수 없으므로 JSON metadata는 form field 문자열로 전달하고 서버에서 Pydantic schema로 재검증한다.

### 9.2 이미지 역할

| `image_role` | 용도 |
|---|---|
| `front_label` | 제품명/브랜드 후보 |
| `supplement_facts` | 영양성분표 후보 |
| `ingredients` | 원재료/기능성 원료 후보 |
| `directions` | 섭취 방법 후보 |
| `warning` | 주의 문구 후보 |
| `barcode` | P2+ 제품 식별 후보 |
| `other` | 미분류 보조 이미지 |

### 9.3 저장 원칙

- 원본 이미지 bytes는 저장하지 않는다.
- 원본 파일명과 EXIF는 저장하지 않는다.
- 파일별 SHA-256, MIME, size, pixel dimensions, role, validation status만 snapshot에 남긴다.
- `supplement_analysis_runs`를 batch 대표 row로 사용할지, `supplement_analysis_images` child table을 추가할지는 P1-7b/P1-8 DB 설계에서 결정한다.
- 일부 파일만 실패하면 전체 작업을 버리지 않고 item별 status로 반환하는 partial success를 우선 후보로 둔다.

### 9.4 응답 후보

```json
{
  "analysis_batch_id": "uuid",
  "client_batch_id": "mobile-generated-id",
  "status": "requires_confirmation",
  "items": [
    {
      "client_image_id": "front-1",
      "image_role": "front_label",
      "status": "accepted",
      "warnings": []
    }
  ],
  "preview": {
    "product_name_candidates": [],
    "ingredient_candidates": [],
    "requires_user_confirmation": true
  }
}
```

## 10. 참고한 공식 문서/보안 기준

- FastAPI Request Files: https://fastapi.tiangolo.com/tutorial/request-files/
- Starlette Request Files: https://www.starlette.io/requests/#request-files
- OWASP File Upload Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
- Pillow Image module: https://pillow.readthedocs.io/en/stable/reference/Image.html
- Python hashlib: https://docs.python.org/3/library/hashlib.html
- Google Cloud Vision `images:annotate`: https://cloud.google.com/vision/docs/reference/rest/v1/images/annotate
- Google Cloud Vision batch annotation: https://cloud.google.com/vision/docs/batch
