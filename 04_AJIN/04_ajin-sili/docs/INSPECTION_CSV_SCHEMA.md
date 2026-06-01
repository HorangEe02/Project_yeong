# 점검 이력 (inspection_logs) CSV 업로드 스키마 — v4.3

운영팀이 점검 이력을 백엔드에 업로드할 때 사용하는 표준 CSV 형식입니다. `POST /api/equipment/inspection/upload-csv` 또는 `make ingest-inspection FILE=...` 으로 적재합니다.

---

## 1. 파일 요구사항

| 항목 | 값 |
|---|---|
| 확장자 | `.csv` (UTF-8) 또는 `.xlsx` (첫 시트) |
| 인코딩 | **UTF-8 with BOM** (Excel 호환). UTF-8 only 도 수용 |
| 구분자 | 콤마 `,` |
| 최대 행 수 | 10,000 (한 번에) — 초과 시 분할 |
| 헤더 | 1행 필수, 한국어 별칭 허용 (아래 매핑 참조) |

---

## 2. 컬럼 정의

### 필수 컬럼 (5)

| 컬럼명 | 한국어 별칭 | 타입 | 검증 |
|---|---|---|---|
| `equipment_id` | 설비ID, 설비코드 | string (≤30) | 공백·null 거부. 영문·숫자·하이픈만 권장 |
| `template_code` | 템플릿코드, 점검유형 | string | `checklist_templates.template_name` 또는 향후 `code` 컬럼 매칭 |
| `inspection_date` | 점검일, 점검일자 | ISO 8601 `YYYY-MM-DD` | 미래 날짜 거부 (`> today` → error) |
| `inspector` | 검사자, 점검자 | string (≤30) | 공백 trim 후 적재. 빈 문자열 거부 |
| `overall_status` | 결과, 종합판정 | enum | `PASS` / `WARN` / `FAIL` 만 허용 (대소문자 무관) |

### 선택 컬럼 (3)

| 컬럼명 | 한국어 별칭 | 타입 | 기본값 |
|---|---|---|---|
| `equipment_name` | 설비명 | string (≤100) | template 의 equipment_type 추론 |
| `results_json` | 항목별결과 | JSON string | `[]` (빈 배열 = 항목 결과 미상) |
| `note` | 비고, 메모 | string (≤500) | 빈 문자열 |

### 자동 채움 (CSV에 없어도 됨)

- `created_at` — 적재 시 서버 시간
- `source` — `csv_upload` (CLI 시) 또는 endpoint 호출자 username

---

## 3. results_json 상세 schema

각 점검 항목별 PASS/FAIL/점수를 표현합니다.

```json
[
  {"item_no": 1, "passed": true, "score": 92, "comment": ""},
  {"item_no": 2, "passed": true, "score": 88, "comment": ""},
  {"item_no": 3, "passed": false, "score": 55, "comment": "유압 누유 발견"}
]
```

| 필드 | 타입 | 필수 | 비고 |
|---|---|---|---|
| `item_no` | int | ✅ | 1부터 시작, 템플릿 항목 순번 |
| `passed` | bool | ✅ | true/false |
| `score` | int | 선택 | 0-100. 누락 시 passed 에 따라 100/0 |
| `comment` | string | 선택 | ≤200 |

JSON 파싱 실패 시 해당 row 는 error queue 로 분기.

---

## 4. template_code 매핑

현재 시드된 6 템플릿:

| `template_code` | template_id (DB) | 설비 유형 |
|---|---|---|
| `프레스 일상점검` | 1 | 프레스 |
| `프레스 월간 정기점검` | 2 | 프레스 |
| `용접기 일상점검` | 3 | 용접기 |
| `용접기 주간점검` | 4 | 용접기 |
| `로봇 일상점검` | 5 | 로봇 |
| `로봇 월간 정기점검` | 6 | 로봇 |

추후 추가 시 `inspection_db.checklist_templates` 테이블 참조. 매칭 실패 시 해당 row error.

---

## 5. 멱등성 (중복 처리)

자연키: **(equipment_id, template_id, inspection_date, inspector)**.

| 시나리오 | 동작 |
|---|---|
| 신규 자연키 | INSERT (rows_inserted++) |
| 동일 자연키 + 동일 results_json | SKIP (rows_skipped++) — DB 무변동 |
| 동일 자연키 + 다른 results_json/note | UPDATE (rows_updated++) — 최신값 승, source 라벨도 갱신 |

ingest_log 테이블 (`inspection_ingest_log`) 에 매 업로드 한 행 기록 — total/inserted/skipped/error 카운트.

---

## 6. 표준 CSV 예시

```csv
equipment_id,equipment_name,template_code,inspection_date,inspector,overall_status,results_json,note
PR-101,프레스 #1 (경산 본사),프레스 일상점검,2026-05-12,김민수,PASS,"[{""item_no"":1,""passed"":true,""score"":92,""comment"":""""}]",
PR-101,프레스 #1 (경산 본사),프레스 일상점검,2026-05-13,박지훈,WARN,"[{""item_no"":1,""passed"":true,""score"":85},{""item_no"":2,""passed"":false,""score"":60,""comment"":""유압 누유""}]",유압 누유 점검 필요
WD-201,용접 #3 (경산 2공장),용접기 일상점검,2026-05-12,이정연,PASS,"[]",
```

Excel 사용 시 **저장 형식: CSV UTF-8(쉼표로 구분)(*.csv)** 선택 + 큰따옴표 자동 이스케이프 활용.

---

## 7. 한국어 별칭 자동 매핑

업로드 모듈이 헤더를 자동 정규화합니다. 예시:

| 사용자 헤더 | 매핑 결과 |
|---|---|
| `설비ID`, `설비코드`, `Equipment ID` | `equipment_id` |
| `점검일`, `점검일자` | `inspection_date` |
| `검사자`, `점검자` | `inspector` |
| `결과`, `종합판정` | `overall_status` |
| `비고`, `메모`, `Remark` | `note` |

별칭 외 헤더는 무시. 필수 컬럼 누락 시 첫 행 검증에서 즉시 실패 (HTTP 422).

---

## 8. dry-run 모드

`POST /api/equipment/inspection/upload-csv?dry_run=true` 또는 CLI `--dry-run` 으로 적재 없이 검증만 수행. 응답에 `IngestResult` (rows_total/inserted/skipped/updated/error + 첫 50 에러 행 payload).

대량 업로드 전 권장 흐름:
1. `dry_run=true` 로 1차 검증 → 에러 row 확인
2. CSV 수정
3. `dry_run=false` 로 실 적재

---

## 9. 에러 코드

| 코드 | 의미 | 해결 |
|---|---|---|
| `MISSING_COLUMN` | 필수 컬럼 누락 | 헤더에 누락 컬럼 추가 |
| `INVALID_DATE` | 날짜 파싱 실패 또는 미래 날짜 | `YYYY-MM-DD` 형식 + 오늘 이하 |
| `INVALID_STATUS` | overall_status enum 미일치 | PASS/WARN/FAIL 중 선택 |
| `UNKNOWN_TEMPLATE` | template_code 매칭 실패 | 표 4 참조 |
| `INVALID_JSON` | results_json 파싱 실패 | JSON 구문·schema 확인 |
| `INSPECTOR_EMPTY` | 검사자 공백 | 비어있지 않은 값 |
| `EQUIPMENT_ID_EMPTY` | 설비 ID 공백 | 비어있지 않은 값 |

에러 row 는 error_payload 에 `{row, error_code, error_msg, raw_payload}` 형식으로 첫 50건 보존.

---

## 10. 운영팀 제출 절차

1. 운영팀: 일별/주별 xlsx 작성
2. 사전 검증: `--dry-run` 실행 → 에러 0 확인
3. 적재: dropzone 업로드 또는 CLI 실행
4. ingest_log 확인: 대시보드 또는 `GET /api/equipment/inspection/ingest-log/recent`
5. 모니터링: 일일 리포트 (Slack #compliance-ops, 매일 05:00 KST)

---

작성: 2026-05-12 · v4.3 inspection ETL Phase 1.1
