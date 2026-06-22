# 44. P1-1 BarcodeAdapter + 식약처 OpenAPI 상세 설계 및 구현 플랜

작성일: 2026-05-16
범위: `01_HANDOFF.md`의 P1-1, BarcodeAdapter, 식약처 건강기능식품 OpenAPI, supplement preview/product matching 연계

## 1. 현재 상태 확인

`01_HANDOFF.md`는 P1-1을 "BarcodeAdapter + 식약처 OpenAPI 클라이언트"로 정의한다. 핵심 의도는 바코드 또는 QR을 먼저 식별하고, 공식 제품 정보가 확인되면 OCR 결과를 확정 근거가 아니라 검증 보조로 낮추는 것이다.

현재 코드 기준으로 이미 존재하는 기반은 다음과 같다.

| 영역 | 현재 구현 | 설계 판단 |
| --- | --- | --- |
| 이미지 intake | `POST /api/v1/supplements/analyze`가 이미지 검증, preview 저장, OCR adapter 호출, OCR text parser 연결을 담당한다. | 바코드 스캔도 같은 preview 흐름에 붙일 수 있다. 다만 이미지 bytes를 읽는 조건에 barcode adapter를 추가해야 한다. |
| OCR fail-closed | `OCR_PRIMARY_PROVIDER=none`, `ALLOW_EXTERNAL_OCR=false` 기본값과 provider factory가 있다. | 바코드도 동일하게 adapter 미설정 시 no-op으로 degrade한다. |
| 제품 reference DB | `SupplementProduct`, `SupplementProductIngredient` 모델이 있고 `source_provider`, `source_product_id`, `source_payload`, `source_manifest_version`을 가진다. | 식약처 row를 sanitized payload로 저장하거나 preview 후보로만 반환할 수 있다. |
| 제품 매칭 | `match_supplement_product()`가 제품명, 제조사, 성분 overlap으로 conservative match를 수행한다. | 바코드/품목제조번호 exact match를 별도 우선순위로 추가하되, 일반 EAN/UPC는 공식 lookup 근거 없이는 자동 확정하지 않는다. |
| preview 저장 | `SupplementAnalysisRun.parsed_snapshot`, `match_snapshot`이 JSONB다. | 1차 구현은 schema migration 없이 barcode lookup snapshot을 JSONB에 저장할 수 있다. barcode alias 테이블은 후속 migration으로 분리한다. |
| 설정 | `Settings.mfds_api_key: SecretStr | None`가 이미 존재한다. | API key는 이 필드를 재사용하고 timeout/retry/base URL만 최소 추가한다. |
| FoodQR 설정 | 아직 `FOODQR_SERVICE_KEY` 또는 공공데이터포털 전용 service key 설정이 없다. | 일반 EAN/UPC/GTIN 바코드 조회는 FoodQR `brcd_no`로 분리하고, 식품안전나라 `MFDS_API_KEY`와 다른 설정으로 관리한다. |
| Redis | `redis_url` 설정은 있지만 cache adapter 구현은 없다. | P1-1 첫 구현은 in-process/client-level bounded cache 또는 DB snapshot만 사용하고, Redis L2는 별도 후속으로 분리한다. |

핵심 결론:

- P1-1을 바로 "바코드만 찍으면 식약처 제품 확정"으로 구현하면 안 된다.
- 현재 공식 문서로 확인한 식약처 `C003` 건강기능식품 품목제조신고 API는 `PRDLST_REPORT_NO`, `PRDLST_NM`, `BSSH_NM` 등으로 조회할 수 있지만 일반 EAN/UPC 바코드 조회 파라미터는 확인되지 않았다.
- 2026-05-16 추가 조사에서 공공데이터포털 FoodQR `getFoodQrProdList01`의 `brcd_no` 요청 파라미터가 확인됐다. 따라서 일반 EAN/UPC/GTIN은 `C003`가 아니라 FoodQR로 조회한다.
- MVP는 `BarcodeAdapter`가 디코딩한 값을 정규화한 뒤 `FoodQrClient.lookup_by_barcode()`를 먼저 시도하고, FoodQR 결과의 제품명/유효기간/버전 정보와 `C003` 품목제조번호 또는 OCR 후보가 연결될 때 official candidate로 승격한다.
- FoodQR 결과도 사용자 확인 전에는 확정 저장하지 않는다. `C003`와 FoodQR 또는 OCR이 충돌하면 `review_required`로 둔다.

## 2. 공식 문서 확인 근거

아래 문서는 2026-05-16 기준으로 확인했다. 문서에서 확인되지 않은 endpoint, 필드, 정확도, 매칭률은 설계에 넣지 않는다.

| 주제 | 공식 문서에서 확인한 내용 | 설계 반영 |
| --- | --- | --- |
| 식약처 건강기능식품 품목제조신고 원재료 API | 공공데이터포털의 `식품의약품안전처_건강기능식품 품목제조신고(원재료)`는 JSON+XML LINK API이며, 건강기능식품 품목제조신고 정보와 원재료 포함 정보를 제공한다. URL: <https://www.data.go.kr/data/15061756/openapi.do?recommendDataYn=Y> | 식약처 제품 후보의 1차 source는 `C003`으로 둔다. |
| 식품안전나라 `C003` 상세 | `C003` 요청은 `http://openapi.foodsafetykorea.go.kr/api/keyId/serviceId/dataType/startIdx/endIdx` 패턴을 사용하고, 선택 파라미터로 `CHNG_DT`, `PRDLST_REPORT_NO`, `PRMS_DT`, `PRDLST_NM`, `BSSH_NM`, `LCNS_NO`가 확인된다. 출력항목에는 `LCNS_NO`, `BSSH_NM`, `PRDLST_REPORT_NO`, `PRDLST_NM`, `NTK_MTHD`, `PRIMARY_FNCLTY`, `IFTKN_ATNT_MATR_CN`, `RAWMTRL_NM` 등이 있다. URL: <https://www.foodsafetykorea.go.kr/api/openApiInfo.do?menu_grp=MENU_GRP31&menu_no=661&show_cnt=10&start_idx=1&svc_no=C003> | exact lookup은 `PRDLST_REPORT_NO`일 때만 자동 후보 score 1.0을 허용한다. 제품명/업소명 조회는 후보 제시만 한다. |
| 식품안전나라 OpenAPI 공통 요청/오류 | 식품안전나라 데이터활용서비스는 `keyId`, `serviceId`, `dataType`, `startIdx`, `endIdx` 요청 인자를 요구하고, `ERROR-336`은 1회 최대 1000건 초과, `INFO-200`은 해당 데이터 없음, `INFO-300`은 호출건수 초과를 의미한다. URL: <https://www.foodsafetykorea.go.kr/api/openApiAplcInfo.do> | 클라이언트는 page size를 1000 이하로 제한하고, message code를 typed error/status로 매핑한다. |
| 건강기능식품 영양DB | `I0760`은 건강기능식품 영양DB로, 원료명/분류 정보와 `HELT_ITM_GRP_NM` 선택 조회를 제공한다. URL: <https://www.foodsafetykorea.go.kr/api/openApiInfo.do?menu_grp=MENU_GRP31&menu_no=661&show_cnt=10&start_idx=1&svc_no=I0760> | 원료명 표준화/보강은 제품 식별이 아니라 ingredient enrichment로 분리한다. |
| 푸드QR 정보 서비스 | 공공데이터포털의 `식품의약품안전처_푸드QR 정보 서비스`는 REST API이며 푸드QR 목록정보, 품목제조정보, 식품표시정보, 원재료정보, 영양표시정보 등 11종 정보를 제공한다고 설명한다. URL: <https://www.data.go.kr/data/15143798/openapi.do> | FoodQR은 일반 바코드 조회 provider로 승격한다. |
| FoodQR 목록정보 endpoint | 공공데이터포털 영문 상세 페이지에서 `http://apis.data.go.kr/1471000/FoodQrInfoService01/getFoodQrProdList01`, `serviceKey`, `pageNo`, `numOfRows`, `type`, `prdt_nm`, `brcd_no`, `ver_info`, `vld_bgng_ymd`, `vld_end_ymd`가 확인된다. URL: <https://www.data.go.kr/en/data/15143798/openapi.do> | `FoodQrClient.lookup_by_barcode()`의 1차 구현 대상이다. `brcd_no` exact lookup을 generic EAN/UPC/GTIN 조회 경로로 사용한다. |
| zxing-cpp Python binding | `zxing-cpp` 3.0.0은 Python binding을 제공하고, 공식 예시에서 `zxingcpp.read_barcodes(img)`로 바코드들을 읽어 `text`, `format`, `content_type`, `position`을 확인한다. URL: <https://pypi.org/project/zxing-cpp/> | 서버-side image decoder 후보는 `zxing-cpp`로 둔다. optional dependency로 설치하고 미설치 시 no-op adapter로 둔다. |

### 확인 한계

I cannot find the official documentation for this specific query. 즉, 일반 EAN/UPC/GTIN 바코드 값을 식약처 `C003` 건강기능식품 품목제조신고 API에 직접 넣어 제품을 조회하는 공식 파라미터는 확인하지 못했다.

다만 FoodQR 목록정보 API에서는 `brcd_no`가 확인됐으므로, P1-1 MVP의 generic barcode lookup은 FoodQR로 수행한다. 아직 확인이 필요한 부분은 FoodQR의 세부 response field 전체와 건강기능식품 `C003` 품목제조번호까지 안정적으로 연결되는지 여부다. 이 부분은 `FOODQR_SERVICE_KEY` 기반 live smoke 또는 Swagger UI export로 보강한다.

## 3. 설계 원칙

1. 공식 데이터만 제품 identity의 강한 근거로 사용한다. OCR, VLM, fuzzy match는 후보 생성 또는 검증 보조다.
2. 바코드 디코딩과 식약처 조회를 분리한다. 디코딩 성공은 제품 매칭 성공이 아니다.
3. 일반 barcode value는 privacy 관점에서 제품 식별자일 수 있으므로 raw value를 로그에 남기지 않는다. audit에는 존재 여부, format, hash 또는 prefix-free status만 남긴다.
4. 식품안전나라 `MFDS_API_KEY`와 공공데이터포털 `FOODQR_SERVICE_KEY`는 분리한다. 한쪽 key가 없어도 나머지 provider 또는 수동 입력 흐름은 계속 동작해야 한다.
5. raw image와 raw OCR text 저장 금지 원칙을 유지한다. barcode lookup snapshot도 sanitized field만 저장한다.
6. 사용자가 확인하기 전에는 섭취량, 성분, 제품명을 확정 데이터로 저장하지 않는다.
7. Redis L2 cache는 현재 코드 기반에 cache client가 없으므로, P1-1 첫 PR에 무리하게 넣지 않는다. API 안정화 뒤 별도 PR로 추가한다.
8. 모든 클래스와 주요 함수에는 Google Style docstring을 작성하고, 복잡한 매칭 판단에는 왜 해당 기준을 택했는지 설명하는 주석만 남긴다.

## 4. 브레인스토밍 결과

### 4.1 모듈 위치

검토안:

1. `src/vision/barcode_base.py`를 추가한다.
   - 장점: `01_HANDOFF.md`의 파일명과 일치한다.
   - 단점: 현재 `src/vision/base.py`는 "라벨 영역 검출만 담당"한다고 명시되어 있어 barcode identity와 섞이면 경계가 흐려진다.
2. `src/barcode/` 패키지를 새로 둔다.
   - 장점: 바코드/QR 디코딩, 정규화, provider factory를 OCR/ROI와 분리할 수 있다.
   - 단점: 핸드오프의 파일명과 다르다.
3. 모바일에서만 바코드를 읽고 백엔드는 text만 받는다.
   - 장점: 서버 image decoder dependency가 줄어든다.
   - 단점: P1-1의 `BarcodeAdapter` 서버 경계가 사라지고, 모바일 구현 상태에 의존한다.

결정: 2번을 채택한다. `src/barcode/`를 새 패키지로 만들고, 필요하면 `src/vision`에는 import alias를 두지 않는다. 현재 `VisionAdapter`는 ROI 전용으로 유지한다.

### 4.2 Decoder 선택

검토안:

1. `zxing-cpp`
   - 장점: 1D barcode와 QR을 모두 다루는 Python binding이 있고, 공식 예시가 단순하다.
   - 단점: native wheel/빌드 환경 이슈가 있을 수 있으므로 기본 dependency로 넣으면 CI 리스크가 있다.
2. `pyzbar`
   - 장점: 오래된 barcode wrapper 생태계가 있다.
   - 단점: system `zbar` 의존성 때문에 macOS/Linux CI에서 설치 리스크가 크다.
3. 직접 OpenCV 휴리스틱
   - 장점: dependency 제어 가능.
   - 단점: decoding 자체를 직접 구현하면 정확도와 유지보수 리스크가 커진다.

결정: `zxing-cpp`를 optional extra로 둔다. 기본 backend install에서는 `DisabledBarcodeAdapter`만 사용하고, barcode scan smoke는 `pip install ".[barcode]"` 또는 별도 requirements로 opt-in한다.

### 4.3 식약처 API 사용 방식

검토안:

1. `C003`만 사용한다.
   - 장점: 건강기능식품 품목제조신고 product-level 정보에 바로 맞는다.
   - 단점: 일반 barcode direct lookup은 없다.
2. `C003` + `I0760`을 사용한다.
   - 장점: product lookup과 ingredient normalization을 분리할 수 있다.
   - 단점: P1-1 범위가 커질 수 있다.
3. FoodQR REST까지 바로 붙인다.
   - 장점: 공식 `brcd_no` 파라미터가 있어 일반 바코드 조회에 가장 직접적으로 맞는다.
   - 단점: response body의 상세 field와 건강기능식품 품목제조번호 연결 여부는 실제 key 기반 smoke로 확인해야 한다.

결정: 첫 PR에서 `FoodQrClient`와 `MfdsOpenAPIClient`를 함께 scaffold한다. 우선순위는 `FoodQR brcd_no exact lookup` → `C003 PRDLST_REPORT_NO exact lookup` → `C003 product/business name candidate search`다. `I0760`은 product identity가 아니라 ingredient enrichment로 분리한다.

### 4.4 API surface

검토안:

1. `POST /api/v1/supplements/analyze`에 optional `barcode_text`, `barcode_format` form field를 추가한다.
   - 장점: 기존 모바일 capture/upload 흐름에 바로 붙는다.
   - 단점: 바코드만 먼저 스캔해 제품 후보를 보여주는 UX에는 부족하다.
2. `POST /api/v1/supplements/barcode/lookup`을 추가한다.
   - 장점: 모바일에서 카메라로 barcode만 먼저 읽고 제품 후보를 빠르게 보여줄 수 있다.
   - 단점: 새 route, OpenAPI contract, rate limit, audit이 추가된다.
3. 이미지에서 서버가 barcode를 자동 디코딩하고 별도 field는 받지 않는다.
   - 장점: 클라이언트 구현이 단순하다.
   - 단점: 서버-side decoder dependency가 필요하고, 모바일 native scanner의 장점을 못 쓴다.

결정: 1번과 2번을 모두 지원하되 순서를 나눈다.

- Phase R1: `analyze`의 optional `barcode_text`/`barcode_format`으로 시작한다.
- Phase R2: `POST /api/v1/supplements/barcode/lookup` standalone route를 추가한다.
- Phase R3: optional server image decoder를 `analyze` 흐름에 붙인다.

### 4.5 자동 매칭 정책

자동 확정 허용:

- FoodQR `brcd_no` exact lookup이 정확히 1건을 반환하고, 응답 제품명이 OCR/사용자 입력 제품명과 충돌하지 않는다.
- QR 또는 barcode payload에서 공식 `PRDLST_REPORT_NO`가 추출되고, `C003` 조회가 정확히 1건을 반환한다.
- 기존 local reference DB에 검증된 `identifier_type + identifier_value` alias가 있고, alias source가 `mfds_foodqr_verified` 또는 `user_confirmed_verified`다.

자동 확정 금지:

- FoodQR key가 없어서 일반 EAN/UPC를 공식 조회하지 못한 경우
- 제품명 fuzzy search만 성공한 경우
- `C003` 결과가 여러 건인 경우
- FoodQR 결과와 `C003` 또는 OCR 제품명이 충돌하는 경우
- 제조사/제품명이 OCR 추정값과 충돌하는 경우
- 식약처 API 오류 또는 quota 초과로 조회 실패한 경우

후보 제시:

- `C003` 제품명/업소명 조회 결과는 `matched_product_candidates`로만 제공한다.
- score가 높아도 사용자가 확인하기 전 `matched_product_id`를 확정하지 않는다.

## 5. 데이터 모델 설계

### 5.1 Preview JSONB snapshot

첫 구현에서는 migration 없이 기존 `SupplementAnalysisRun` JSONB를 활용한다.

`parsed_snapshot` 추가 field:

```json
{
  "barcode": {
    "status": "foodqr_lookup_pending_or_skipped",
    "decoded": [
      {
        "format": "EAN13",
        "value_hash": "sha256:...",
        "normalized_value": "8801234567890",
        "raw_value_stored": false,
        "position": {"x": 10, "y": 20, "width": 120, "height": 40}
      }
    ],
    "official_lookup_key": null,
    "warnings": ["Official barcode lookup is not configured or returned no data."]
  }
}
```

`match_snapshot` 추가 field:

```json
{
  "barcode_lookup": {
    "provider": "mfds_c003",
    "status": "matched_report_no",
    "source_id": "mfds:C003:20070017035202",
    "source_manifest_version": "mfds-c003-live",
    "matched_at": "2026-05-16T00:00:00Z",
    "raw_payload_stored": false
  },
  "matched_product_candidates": []
}
```

주의:

- raw barcode value 저장 여부는 구현 시 팀 리뷰로 결정한다. 기본 설계는 raw log 금지, preview snapshot에는 사용자가 확인해야 하는 product identifier로서 normalized value만 저장 가능하되 audit log에는 저장하지 않는다.
- raw 식약처 payload 전체를 저장하지 않고, 필요한 field만 allowlist로 보관한다.

### 5.2 후속 migration: `supplement_product_identifiers`

barcode alias를 안정적으로 재사용하려면 `0007_create_supplement_product_identifiers` migration을 별도 PR로 둔다.

주요 필드:

| 필드 | 설명 |
| --- | --- |
| `id` | UUID primary key |
| `product_id` | `supplement_products.id` FK |
| `identifier_type` | `ean13`, `upca`, `qr_url`, `foodqr_id`, `prdlst_report_no` |
| `identifier_value_hash` | lookup/audit용 hash |
| `identifier_value_encrypted` | 필요 시만 암호화 저장. 기본 PR에서는 생략 가능 |
| `source_provider` | `mfds_c003`, `foodqr`, `user_confirmed` |
| `verification_status` | `verified`, `candidate`, `rejected` |
| `source_payload` | sanitized source metadata |
| `verified_at` | 확인 시각 |
| `created_at`, `updated_at` | lifecycle |

제약:

- `(identifier_type, identifier_value_hash, source_provider)` unique constraint
- `verification_status IN ('verified', 'candidate', 'rejected')`
- `identifier_type` allowlist check
- raw barcode는 기본 DB column에 평문 저장하지 않는다.

## 6. Backend 컴포넌트 설계

### 6.1 `src/barcode/base.py`

주요 타입:

- `BarcodeImageInput`: validated image bytes, MIME, width, height
- `BarcodeCandidate`: format, text, position, confidence optional
- `BarcodeScanResult`: provider, candidates, warnings
- `BarcodeAdapter`: `async scan(image: BarcodeImageInput) -> BarcodeScanResult`
- `BarcodeError`: decoder failure

요구사항:

- provider는 raw image를 저장하지 않는다.
- format은 bounded string allowlist로 정규화한다.
- candidate가 여러 개면 QR, DataMatrix, EAN13, UPCA 순서로 lookup 우선순위를 둔다.

### 6.2 `src/barcode/normalization.py`

책임:

- full-width digit, whitespace, hyphen 제거
- EAN-13/UPC-A check digit 검증
- QR URL에서 query parameter 후보 추출
- `PRDLST_REPORT_NO` 패턴 추출
- `BarcodeIdentifier` typed result 반환

주의:

- check digit 검증 실패는 decoder 실패가 아니라 `invalid_identifier` status다.
- QR URL 내부 key 이름은 공식 FoodQR Swagger 확인 전까지 allowlist를 좁게 유지한다.

### 6.3 `src/barcode/providers/zxing.py`

책임:

- optional `zxingcpp` lazy import
- `zxingcpp.read_barcodes(...)` 호출
- decoded candidate를 `BarcodeCandidate`로 변환
- dependency 미설치 시 `BarcodeError`가 아니라 factory 단계에서 disabled adapter 반환

테스트:

- 실제 zxing dependency 없이 monkeypatch fake decoder로 unit test한다.
- optional smoke만 실제 QR/EAN fixture image를 사용한다.

### 6.4 `src/nutrition/mfds_client.py`

주요 타입:

- `MfdsOpenAPIClient`
- `MfdsProductRow`
- `MfdsIngredientRow`
- `MfdsOpenAPIError`
- `MfdsNoData`
- `MfdsQuotaExceeded`
- `MfdsAuthenticationError`

메서드:

- `get_product_by_report_no(report_no: str) -> list[MfdsProductRow]`
- `search_products(product_name: str | None, business_name: str | None, limit: int = 10) -> list[MfdsProductRow]`
- `search_ingredient_group(name: str, limit: int = 10) -> list[MfdsIngredientRow]`

요청 규칙:

- `serviceId`는 `C003` 또는 `I0760`으로 고정한다.
- `dataType`은 `json`으로 고정한다.
- `startIdx/endIdx`는 1부터 시작하며 1000건 이하로 제한한다.
- message code를 typed exception/status로 변환한다.
- timeout/retry는 settings에서 읽는다.

### 6.5 `src/nutrition/foodqr_client.py`

주요 타입:

- `FoodQrClient`
- `FoodQrProductRow`
- `FoodQrLookupResult`
- `FoodQrOpenAPIError`
- `FoodQrNoData`
- `FoodQrQuotaExceeded`
- `FoodQrAuthenticationError`

메서드:

- `lookup_by_barcode(barcode: str, *, version: str | None = None) -> FoodQrLookupResult`
- `search_products(product_name: str, limit: int = 10) -> FoodQrLookupResult`

요청 규칙:

- base URL은 `http://apis.data.go.kr/1471000/FoodQrInfoService01`로 둔다.
- 첫 구현 endpoint는 `/getFoodQrProdList01`만 사용한다.
- `serviceKey`는 공공데이터포털 발급 key이며 URL-encoded 값을 그대로 받을 수 있게 한다.
- `type=json`, `pageNo=1`, `numOfRows<=100`을 기본값으로 둔다.
- 일반 barcode lookup은 `brcd_no=<normalized barcode>`로 수행한다.
- response body의 상세 field는 live smoke 또는 Swagger UI export 확인 전까지 allowlist를 좁게 둔다.

### 6.6 `src/services/supplement_identity.py`

책임:

- barcode candidates와 식약처 rows를 제품 후보로 변환한다.
- FoodQR `brcd_no` exact match와 `C003` `PRDLST_REPORT_NO` exact match를 strong official candidate로 표시한다.
- 일반 barcode가 FoodQR에서도 조회되지 않거나 fuzzy result만 있는 경우 user confirmation required로 표시한다.
- 기존 `MatchedSupplementCandidate`와 호환되도록 `source_id`, `product_name`, `manufacturer`, `match_score`를 만든다.

출력:

- `SupplementIdentityResolution`
  - `status`
  - `decoded_identifiers`
  - `official_lookup_key`
  - `matched_product_candidates`
  - `warnings`
  - `source_manifest_version`

provider 우선순위:

1. `FoodQrClient.lookup_by_barcode()` — 일반 EAN/UPC/GTIN의 1차 공식 조회.
2. `MfdsOpenAPIClient.get_product_by_report_no()` — QR payload 또는 OCR에서 품목제조번호가 확인된 경우.
3. `MfdsOpenAPIClient.search_products()` — 제품명/제조사 후보 검색. 자동 확정 금지.
4. local verified identifier table — 후속 migration 이후 verified alias만 자동 match 후보.

### 6.7 Factory와 settings

추가 settings:

- `barcode_scan_provider: Literal["none", "zxing_cpp"] = "none"`
- `enable_barcode_scan: bool = False`
- `enable_barcode_lookup: bool = False`
- `mfds_openapi_base_url: str = "http://openapi.foodsafetykorea.go.kr/api"`
- `mfds_openapi_timeout_seconds: int = 10`
- `mfds_openapi_max_retries: int = 2`
- `mfds_openapi_page_size: int = 100`
- `foodqr_service_key: SecretStr | None = None`
- `foodqr_base_url: str = "http://apis.data.go.kr/1471000/FoodQrInfoService01"`
- `foodqr_product_list_path: str = "/getFoodQrProdList01"`
- `foodqr_product_manufacturing_path: str | None = None`
- `foodqr_timeout_seconds: int = 10`
- `foodqr_max_retries: int = 2`
- `foodqr_num_of_rows: int = 10`

기본값:

- `enable_barcode_scan=false`
- `enable_barcode_lookup=false`
- `barcode_scan_provider=none`
- `mfds_api_key=None`
- `foodqr_service_key=None`

production guard:

- barcode scan은 로컬 이미지 처리이므로 외부 전송 동의가 필요하지 않다.
- FoodQR/C003 호출은 제품 identifier lookup이며 OCR 이미지 전송이 아니지만, 사용자 행동과 연결되므로 audit event는 남긴다.
- `FOODQR_SERVICE_KEY`가 없으면 generic barcode lookup은 no-op으로 degrade한다.
- `MFDS_API_KEY`가 없으면 C003/I0760 lookup은 no-op으로 degrade한다.
- production에서 `enable_barcode_lookup=true`이면 최소 하나의 official lookup key가 있어야 한다.
- FoodQR production 사용 전에는 공공데이터포털 운영계정/활용사례 심의 상태를 확인한다.

## 7. API 계약 설계

### 7.1 `POST /api/v1/supplements/analyze`

추가 form field:

- `barcode_text: str | None = Form(default=None, max_length=512)`
- `barcode_format: str | None = Form(default=None, max_length=40)`

동작:

1. image intake를 기존처럼 수행한다.
2. `barcode_text`가 있으면 image decoder보다 우선한다.
3. `barcode_text`가 없고 `enable_barcode_scan=true`이면 서버 image decoder를 시도한다.
4. normalized EAN/UPC/GTIN이면 `FoodQrClient.lookup_by_barcode()`를 먼저 호출한다.
5. QR payload 또는 OCR/parser 결과에서 `PRDLST_REPORT_NO`가 있으면 `MfdsOpenAPIClient.get_product_by_report_no()`를 호출한다.
6. FoodQR/C003/OCR 후보가 충돌하지 않으면 official candidate로 표시하고, 충돌하면 `review_required` warning을 남긴다.
7. 결과를 preview의 `parsed_snapshot["barcode"]`, `match_snapshot["barcode_lookup"]`, `matched_product_candidates`에 반영한다.

OpenAPI:

- `x-contract-status`는 기존 `p1_2_intake_ready`에서 `p1_1_barcode_identity_preview` 또는 새 상수로 보강한다.
- 응답 schema에 `barcode_lookup` field를 추가할지, 기존 `warnings`/`matched_product_candidates`만 사용할지는 구현 PR에서 결정한다. 권장은 새 field 추가다.

### 7.2 `POST /api/v1/supplements/barcode/lookup`

Phase R2에서 추가한다.

Request:

```json
{
  "barcode_text": "8801234567890",
  "barcode_format": "EAN13",
  "client_request_id": "optional-idempotency-key"
}
```

Response:

```json
{
  "status": "official_candidate_found",
  "decoded_identifiers": [
    {"format": "EAN13", "normalized_value": "8801234567890"}
  ],
  "barcode_lookup": {
    "provider": "foodqr",
    "lookup_key": "brcd_no",
    "raw_payload_stored": false
  },
  "matched_product_candidates": [
    {
      "source_id": "foodqr:8801234567890",
      "product_name": "FoodQR product name",
      "manufacturer": null,
      "match_score": 1.0
    }
  ],
  "warnings": [],
  "source_manifest_version": "foodqr-live"
}
```

권한:

- `supplement:write` scope
- OCR image consent는 필요하지 않다.
- response는 저장 확정이 아니라 lookup preview다.

## 8. 실패/오류 처리

| 상황 | API 동작 | 사용자 메시지 |
| --- | --- | --- |
| barcode decoder 미설치 | 기존 analyze 계속 진행, warning 추가 | "Barcode scan is unavailable. Continue with OCR or manual entry." |
| barcode 미검출 | 기존 analyze 계속 진행 | 별도 오류 없음 |
| EAN/UPC 검출 + FoodQR key 없음 | product candidate 자동 확정 없음 | "Barcode was read, but official barcode lookup is not configured." |
| EAN/UPC 검출 + FoodQR 0건 | product candidate 없음 | "No official FoodQR product was found for this barcode." |
| EAN/UPC 검출 + FoodQR 1건 | official candidate, user confirmation required | "Official product candidate found. Please confirm before saving." |
| EAN/UPC 검출 + FoodQR 다건 | candidate list, review required | "Multiple official candidates found. Please review manually." |
| `PRDLST_REPORT_NO` 검출 + 1건 조회 | candidate score 1.0 | "Official product candidate found. Please confirm before saving." |
| `PRDLST_REPORT_NO` 조회 0건 | candidate 없음 | "No official MFDS product was found for this identifier." |
| `PRDLST_REPORT_NO` 조회 다건 | candidate list, review required | "Multiple official candidates found. Please review manually." |
| FoodQR와 C003 제품명 충돌 | candidate list, review required | "Official sources disagree. Please review manually." |
| API key 없음 | lookup skipped | "Official product lookup is not configured." |
| quota 초과 | lookup skipped, retry 안내 없음 | "Official product lookup is temporarily unavailable." |
| FoodQR/C003 5xx/timeout | lookup skipped | "Official product lookup is temporarily unavailable." |

## 9. 테스트 계획

### 9.1 Unit tests

- `tests/unit/barcode/test_normalization.py`
  - EAN-13 check digit valid/invalid
  - UPC-A normalization
  - QR URL에서 report number 추출
  - raw unsupported text 처리
- `tests/unit/barcode/test_zxing_adapter.py`
  - fake decoder 결과 변환
  - empty result
  - decoder exception safe wrapping
- `tests/unit/nutrition/test_mfds_client.py`
  - `C003` URL/path/query assembly
  - `PRDLST_REPORT_NO` 조회
  - `INFO-000`, `INFO-200`, `INFO-300`, `ERROR-336`, invalid key mapping
  - raw payload allowlist
- `tests/unit/nutrition/test_foodqr_client.py`
  - `getFoodQrProdList01` URL/query assembly
  - `serviceKey`, `type=json`, `brcd_no`, `pageNo`, `numOfRows` mapping
  - no-data, quota, auth, invalid response mapping
  - raw payload allowlist
- `tests/unit/services/test_supplement_identity.py`
  - FoodQR barcode exact match
  - exact report number strong match
  - generic EAN without FoodQR key is unsupported
  - FoodQR/C003 conflict routes to manual review
  - fuzzy product search candidate-only
  - multi-result review required

### 9.2 Integration/API tests

- `tests/integration/api/test_supplement_barcode_lookup_api.py`
  - no `FOODQR_SERVICE_KEY` and no `MFDS_API_KEY`이면 no-op response
  - fake FoodQR client exact barcode match
  - fake MFDS client exact match
  - generic EAN with FoodQR no-data returns warning and no auto match
  - OpenAPI schema contains barcode lookup request/response examples
- `tests/integration/api/test_supplement_analyze_barcode.py`
  - `POST /supplements/analyze` with `barcode_text` stores barcode snapshot
  - image-only path still works when barcode disabled
  - idempotency conflict behavior remains image-hash based

### 9.3 Optional smoke

- `FOODQR_SERVICE_KEY` 또는 `MFDS_API_KEY`가 있는 로컬 환경에서만 실행한다.
- 실제 API smoke는 공개/동의 sample barcode 1건과 공개 sample `PRDLST_REPORT_NO` 1건만 사용한다.
- CI 기본 job에는 live call을 넣지 않는다.
- smoke output에는 key, raw barcode, raw API payload를 출력하지 않는다.

### 9.4 추가 데이터 설계

구현 전에 필요한 데이터는 "실제 제품 DB"가 아니라 provider contract와 충돌 케이스를 검증할 최소 fixture다.

파일 후보:

- `data/nutrition_reference/barcode/fixtures/barcode_identity_cases.example.jsonl`
- `data/nutrition_reference/barcode/fixtures/foodqr_response.allowlisted.example.json`
- `data/nutrition_reference/barcode/fixtures/mfds_c003_response.allowlisted.example.json`

`barcode_identity_cases.example.jsonl` 권장 schema:

```json
{
  "fixture_id": "barcode-case-001",
  "source_rights": "public_or_team_consent",
  "barcode_text": "08801007325224",
  "barcode_format": "EAN13",
  "expected_foodqr": {
    "status": "single_match",
    "product_name": "official product name",
    "manufacturer": null,
    "valid_from": "20241209",
    "valid_to": "99991231"
  },
  "expected_mfds": {
    "prdlst_report_no": null,
    "product_name": null,
    "business_name": null
  },
  "expected_resolution": "official_candidate_found",
  "notes": "No raw package image or user identifier."
}
```

수집 기준:

- 건강기능식품 또는 식품 라벨의 공개/팀 동의 barcode 5-10건을 우선 수집한다.
- 각 barcode에 대해 FoodQR 조회 가능 여부, 제품명, 제조사/업소명, `PRDLST_REPORT_NO` 노출 여부를 수동 검수한다.
- FoodQR와 `C003`가 동시에 매칭되는 사례 1건, FoodQR만 매칭되는 사례 1건, 둘 다 매칭되지 않는 사례 1건, 다건/충돌 사례 1건을 포함한다.
- raw package image는 저장하지 않는다. 이미지가 필요하면 synthetic barcode image 또는 명시 동의 fixture만 사용한다.
- live API 응답은 allowlist field만 fixture로 저장하고, `serviceKey`, full URL query, raw payload 전체를 저장하지 않는다.

구현 전 확인할 실제 값:

- `FOODQR_SERVICE_KEY`: 공공데이터포털 FoodQR 정보 서비스 활용신청 후 발급.
- `MFDS_API_KEY`: 식품안전나라 데이터활용서비스 인증키.
- FoodQR `brcd_no` response에서 제품명 field 이름.
- FoodQR response에 `PRDLST_REPORT_NO` 또는 C003 연결 가능한 field가 있는지 여부.
- FoodQR `numOfRows` 상한과 quota error payload 형태.

## 10. 구현 순서

### Phase P1-1-R0. 보정 계약 확정

목표: `C003`와 FoodQR의 역할을 분리하고 key/data 요구사항을 확정한다.

작업:

- `docs/Nutrition-docs/44-p1-1-barcode-mfds-openapi-design-plan.md`를 리뷰 기준 문서로 사용한다.
- `01_HANDOFF.md`의 P1-1 파일명과 현재 코드 구조 차이를 이 문서에서 설명한다.
- `C003`에는 generic barcode 파라미터가 없고, FoodQR에는 `brcd_no`가 있음을 명시한다.
- `MFDS_API_KEY`와 `FOODQR_SERVICE_KEY`를 분리한다.

완료 기준:

- 문서에 공식 근거 URL과 확인 한계가 들어 있다.
- generic barcode lookup이 FoodQR provider로 이동했다.
- FoodQR response 상세 field는 live smoke로 확인한다는 gate가 명시되어 있다.

### Phase P1-1-R1. Settings/env scaffold

목표: provider key와 runtime toggle을 fail-closed 기본값으로 추가한다.

작업:

- `src/config.py`
  - `enable_barcode_lookup`
  - `foodqr_service_key`
  - `foodqr_base_url`
  - `foodqr_product_list_path`
  - `foodqr_product_manufacturing_path`
  - `foodqr_timeout_seconds`
  - `foodqr_max_retries`
  - `foodqr_num_of_rows`
  - `mfds_openapi_*`
- `backend/.env.example`
  - `FOODQR_SERVICE_KEY=`
  - `ENABLE_BARCODE_LOOKUP=false`
  - `ENABLE_BARCODE_SCAN=false`
- `docs/Nutrition-docs/dev-guides/00-setup-environment.md`
  - 두 key 발급처와 용도 분리 문서화

완료 기준:

- 기본값에서는 외부 FoodQR/C003 lookup이 실행되지 않는다.
- `Settings` unit test가 empty env를 안전하게 통과한다.
- secret 값은 로그와 test assertion에 출력하지 않는다.

### Phase P1-1-R2. Barcode domain scaffold

목표: 외부 API/live decoder 없이도 unit test 가능한 순수 계약을 만든다.

작업:

- `src/barcode/base.py`
- `src/barcode/normalization.py`
- `src/barcode/factory.py`
- `tests/unit/barcode/*`

완료 기준:

- optional dependency 없이 unit tests 통과
- EAN/UPC check digit, QR payload, `PRDLST_REPORT_NO` 추출 테스트 통과
- raw barcode audit hash helper가 원문을 로그에 남기지 않는다.

### Phase P1-1-R3. FoodQR client scaffold

목표: 일반 바코드 official lookup provider를 fake-client test로 먼저 고정한다.

작업:

- `src/nutrition/foodqr_client.py`
- `tests/unit/nutrition/test_foodqr_client.py`
- `tests/integration/mfds/test_foodqr_live_smoke.py`는 `RUN_FOODQR_LIVE_SMOKE=1`일 때만 실행

완료 기준:

- `FOODQR_SERVICE_KEY=None` 경로가 no-op/fail-closed
- `brcd_no` query assembly가 contract test로 고정된다.
- no-data/quota/auth/server error가 typed status로 매핑된다.
- allowlisted response fixture 외 raw payload를 저장하지 않는다.

### Phase P1-1-R4. MFDS C003/I0760 client scaffold

목표: 품목제조번호와 제품명/업소명 후보 조회를 barcode lookup과 분리한다.

작업:

- `src/nutrition/mfds_client.py`
- `tests/unit/nutrition/test_mfds_client.py`
- `tests/integration/mfds/test_mfds_live_smoke.py`는 `RUN_MFDS_LIVE_SMOKE=1`일 때만 실행

완료 기준:

- `MFDS_API_KEY=None` 경로가 no-op/fail-closed
- `C003` `PRDLST_REPORT_NO` query assembly가 contract test로 고정된다.
- `I0760`은 ingredient enrichment method로만 노출된다.
- 식품안전나라 message code mapping test가 통과한다.

### Phase P1-1-R5. Supplement identity resolver

목표: barcode/MFDS 결과를 기존 preview candidate 형식으로 변환한다.

작업:

- `src/services/supplement_identity.py`
- `src/models/schemas/supplement.py`에 barcode lookup response schema 추가
- `tests/unit/services/test_supplement_identity.py`

완료 기준:

- FoodQR `brcd_no` 1건 match는 official candidate로 표시된다.
- exact `PRDLST_REPORT_NO`는 official candidate로 표시된다.
- FoodQR/C003/OCR 충돌은 manual review로 라우팅된다.
- FoodQR key가 없을 때 generic EAN/UPC는 unsupported warning으로 degrade한다.
- fuzzy product name search는 candidate-only

### Phase P1-1-R6. Standalone barcode lookup route

목표: 모바일이 이미지 업로드 전 barcode-first UX를 구현할 수 있게 한다.

작업:

- `POST /api/v1/supplements/barcode/lookup`
- OpenAPI examples
- rate limit/audit event
- mobile README 또는 API guide에 호출 순서 추가
- `tests/integration/api/test_supplement_barcode_lookup_api.py`

완료 기준:

- OCR consent 없이 lookup 가능
- response는 preview/candidate-only임이 OpenAPI에 드러난다.
- FoodQR exact match, C003 exact match, no-key, no-data, conflict case가 contract test에 고정된다.

### Phase P1-1-R7. Analyze flow 통합

목표: 기존 `/supplements/analyze` preview에 barcode lookup 결과를 붙인다.

작업:

- `src/services/supplement_image_analysis.py`
  - adapter bundle에 barcode adapter 추가
  - image bytes read condition에 barcode scan 추가
  - barcode lookup snapshot 저장
- `src/services/supplement_intake.py`
  - preview serialization이 barcode snapshot을 잃지 않도록 보강
- `src/api/v1/supplements.py`
  - optional `barcode_text`, `barcode_format` form field
  - sanitized audit event 추가
- integration tests 추가

완료 기준:

- barcode disabled 기본 analyze smoke 기존과 동일
- `barcode_text`가 있으면 image decoder 없이 FoodQR/MFDS lookup path test 가능
- raw barcode/API payload가 audit event에 저장되지 않는다.

### Phase P1-1-R8. Optional zxing-cpp adapter

목표: 서버-side image barcode scan을 opt-in으로 제공한다.

작업:

- `backend/pyproject.toml` optional dependency `barcode = ["zxing-cpp>=3.0"]`
- `src/barcode/providers/zxing.py`
- synthetic QR/EAN fixture image test
- optional local smoke command 문서화

완료 기준:

- 기본 CI는 zxing 없이 통과
- barcode extra 설치 환경에서 fixture image scan smoke 통과
- decoder 실패가 analyze 전체 실패로 전파되지 않는다.

### Phase P1-1-R9. Verified identifier table

목표: 공식 또는 사용자 확인으로 검증된 barcode alias를 재사용한다.

작업:

- Alembic `0007_create_supplement_product_identifiers`
- `SupplementProductIdentifier` ORM
- `src/services/supplement_identifier_store.py`
- confirmation 시 user-confirmed alias를 `candidate` 또는 `verified`로 저장하는 정책

완료 기준:

- raw barcode 평문 저장 여부가 보안 리뷰에서 결정되어 있다.
- verified alias만 자동 product match에 사용된다.
- user deletion/all-data deletion 정책에 identifier association이 포함된다.

### Phase P1-1-R10. FoodQR 상세 endpoint 확장

목표: `getFoodQrProdList01` 이후 품목제조정보, 원재료, 영양표시정보 endpoint를 필요한 만큼만 연결한다.

작업:

- FoodQR Swagger UI 또는 live response로 11개 상세 endpoint의 request/response field 확인
- `src/nutrition/foodqr_client.py` method 확장
- QR token/URL parser allowlist 확정
- fixture/live smoke

완료 기준:

- 공식 명세 URL과 field mapping이 문서화되어 있다.
- QR code를 일반 URL scraping으로 처리하지 않는다.
- FoodQR 결과도 user confirmation 전에는 확정 저장하지 않는다.

## 11. 검증 명령

구현 PR별 기본 검증:

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/python -m pytest Nutrition-backend/tests/unit/barcode Nutrition-backend/tests/unit/nutrition/test_foodqr_client.py Nutrition-backend/tests/unit/nutrition/test_mfds_client.py -q --no-cov
.venv/bin/python -m pytest Nutrition-backend/tests/unit/services/test_supplement_barcode_lookup.py -q --no-cov
.venv/bin/python -m pytest Nutrition-backend/tests/integration/api/test_supplement_barcode_lookup_api.py -q --no-cov
.venv/bin/python -m ruff check Nutrition-backend/src Nutrition-backend/tests
.venv/bin/python -m black --check Nutrition-backend/src Nutrition-backend/tests
git diff --check
```

실제 FoodQR/C003 smoke는 opt-in:

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend
FOODQR_SERVICE_KEY=... RUN_FOODQR_LIVE_SMOKE=1 .venv/bin/python -m pytest Nutrition-backend/tests/integration/mfds/test_foodqr_live_smoke.py -q --no-cov
MFDS_API_KEY=... RUN_MFDS_LIVE_SMOKE=1 .venv/bin/python -m pytest Nutrition-backend/tests/integration/mfds/test_mfds_live_smoke.py -q --no-cov
```

주의:

- live smoke는 key와 raw payload를 출력하지 않는다.
- CI 기본 job에는 live smoke를 넣지 않는다.
- 실제 바코드 fixture에는 공개/합성/동의 샘플만 사용한다.

## 12. 권장 커밋 단위

1. `docs(nutrition): align barcode design with FoodQR lookup`
   - 이유: FoodQR `brcd_no` 확인으로 기존 C003-only barcode lookup 전제를 바로잡기 위함.
2. `feat(barcode): add fail-closed barcode adapter contract`
   - 이유: 서버-side decoder와 모바일-provided barcode를 같은 계약으로 다루기 위함.
3. `feat(nutrition): add FoodQR barcode lookup client`
   - 이유: 일반 EAN/UPC/GTIN 바코드를 공식 `brcd_no` 조회 경로로 처리하기 위함.
4. `feat(nutrition): add MFDS C003 client for supplement products`
   - 이유: 품목제조번호와 제품명/업소명 후보 조회를 barcode lookup과 분리하기 위함.
5. `feat(supplements): attach barcode lookup to supplement preview`
   - 이유: 사용자 확인 전 preview 단계에서 공식 후보와 OCR 후보를 함께 검토하게 하기 위함.
6. `feat(api): add supplement barcode lookup endpoint`
   - 이유: 모바일 barcode-first UX를 이미지 업로드와 분리해서 빠르게 구현하기 위함.
7. `feat(db): persist verified supplement product identifiers`
   - 이유: 공식 또는 사용자 확인으로 검증된 barcode alias만 재사용해 잘못된 자동 매칭을 방지하기 위함.

## 13. 구현 착수 전 체크리스트

- [x] `MFDS_API_KEY` 발급/등록 방식 확인
- [x] `FOODQR_SERVICE_KEY` 발급/등록 방식 확인
- [x] `C003` 접근 권한 live smoke 확인: 현재 key/scope에서는 C003가 `NON_JSON_PROVIDER_ERROR`를 반환하고, 같은 key로 I0760은 `INFO-000`을 반환한다.
- [x] FoodQR `getFoodQrProdList01` live response에서 제품명 field와 barcode/version/유효기간 field 확인
- [x] FoodQR `brcd_no` exact lookup 테스트 작성
- [x] FoodQR key 없음 또는 no-data 시 generic EAN/UPC degrade 테스트 작성
- [x] C003 generic barcode direct lookup 금지 정책 구현: C003는 FoodQR row의 `report_no`가 있을 때만 보강 조회한다.
- [x] raw barcode/raw API payload 로그 금지 테스트 작성
- [x] 공개/합성/동의 barcode fixture 5-10건 수집: FoodQR 공개 API 기반 10건 수집 완료
- [ ] zxing optional dependency 설치 범위 결정
- [x] standalone barcode lookup route의 consent/scope 정책 리뷰: `supplement:write` scope만 요구하고 OCR consent는 요구하지 않는다. 결과는 후보/검토 전용이다.
- [x] `0007` identifier table 추가: C003/FoodQR 권한 해소 후 검증된 identifier를 저장할 DB 기반을 먼저 마련한다.

## 14. 2026-05-16 구현 및 live smoke 결과

구현 파일:

- `src/nutrition/foodqr_client.py`
- `src/nutrition/mfds_client.py`
- `scripts/evaluate_barcode_identity.py`
- `tests/unit/nutrition/test_foodqr_client.py`
- `tests/unit/nutrition/test_mfds_client.py`
- `tests/integration/mfds/test_foodqr_live_smoke.py`
- `tests/integration/mfds/test_mfds_live_smoke.py`
- `tests/unit/scripts/test_evaluate_barcode_identity.py`

redacted live smoke 결과:

| Provider | Status | Code | Items | 판단 |
| --- | --- | --- | --- | --- |
| FoodQR `getFoodQrProdList01` | `not_found` | `None` | 0 | 키/endpoint는 동작했지만 기본 smoke barcode는 매칭되지 않았다. 제품 field 확정에는 실제 동의 barcode가 필요하다. |
| MFDS `C003` | `provider_error` | `NON_JSON_PROVIDER_ERROR` | 0 | 현재 `MFDS_API_KEY` 또는 서비스 신청 범위로는 C003가 JSON이 아닌 인증키 오류 HTML을 반환했다. C003 서비스 접근 권한 확인이 필요하다. |
| MFDS `I0760` | `matched` | `INFO-000` | 100 | 같은 MFDS key로 I0760 접근은 확인됐다. |

2026-05-16 추가 권한 확인:

| Check | Status | Code | Items | 판단 |
| --- | --- | --- | --- | --- |
| MFDS `C003` first page | `provider_error` | `NON_JSON_PROVIDER_ERROR` | 0 | 필터 없이 첫 페이지를 호출해도 JSON이 아닌 provider error가 반환됐다. |
| MFDS `C003` `PRDLST_REPORT_NO` path param | `provider_error` | `NON_JSON_PROVIDER_ERROR` | 0 | 공식 문서의 선택 인자를 query string이 아니라 path suffix로 보정해도 현재 key/scope에서는 접근되지 않았다. |
| MFDS `I0760` first page | `matched` | `INFO-000` | 100 | key 자체가 완전히 무효인 상황은 아니며, C003 서비스별 신청/권한 범위 이슈로 보는 것이 현재 관측과 맞다. |

FoodQR 공개 barcode fixture:

- 수집 파일: `data/nutrition_reference/barcode/fixtures/barcode_identity_cases.foodqr-public.2026-05-16.jsonl`
- 평가 리포트: `output/evaluations/barcode-identity/2026-05-16/foodqr-public/barcode-identity-evaluation.md`
- 수집 범위: 공공데이터포털 FoodQR 공개 API row에서 `BRCD_NO`, `PRDT_NM`, `ENTP_NM`, `VER_INFO`, `VLD_BGNG_YMD`, `VLD_END_YMD`만 allowlist로 저장
- 검증 방식: 공개 목록에서 얻은 barcode를 다시 `brcd_no` exact lookup으로 조회한 observation만 저장
- 관측 결과: 10건 모두 FoodQR status `matched`; 단일 행 반환 3건, 복수 행 반환 7건, 최대 6행 반환
- 제한: 수집된 FoodQR 목록 row에는 `PRDLST_REPORT_NO`가 없어서 C003 연결 observation은 생성되지 않았다.
- 정책 영향: `brcd_no` exact lookup만으로 자동 제품 확정하지 않고, FoodQR version/유효기간/사용자 확인 또는 C003 report number 연결을 추가로 요구한다.

fixture 평가 산출물:

- `output/evaluations/barcode-identity/2026-05-16/barcode-live-smoke-observations.jsonl`
- `output/evaluations/barcode-identity/2026-05-16/barcode-identity-evaluation.json`
- `output/evaluations/barcode-identity/2026-05-16/barcode-identity-evaluation.md`
- `output/evaluations/barcode-identity/2026-05-16/foodqr-public/barcode-identity-evaluation.json`
- `output/evaluations/barcode-identity/2026-05-16/foodqr-public/barcode-identity-evaluation.md`

주의:

- 위 결과는 provider wiring smoke이며 제품 매칭 정확도, 식약처 커버리지, OCR 대비 개선율이 아니다.
- FoodQR field mapping은 공개 10건에서 최소 목록 field까지 확인됐다. 상세 제조/원재료/영양 endpoint field mapping은 별도 smoke가 필요하다.
- C003는 일반 barcode lookup provider로 쓰지 않고, 권한 확인 후 `PRDLST_REPORT_NO` exact lookup으로만 사용한다.

## 15. 2026-05-16 fail-closed + FoodQR 중심 구현 결과

이번 구현은 서버-side barcode image decoder 없이도 모바일 스캐너가 전달한 barcode text를 공식 후보 조회에 사용할 수 있게 만드는 범위다. 제품 자동 확정, verified identifier DB 저장, zxing-cpp decoder는 포함하지 않았다.

구현 파일:

- `src/barcode/base.py`: `BarcodeAdapter`, `BarcodeImageInput`, `BarcodeScanResult`, `DisabledBarcodeAdapter` 계약
- `src/barcode/normalization.py`: EAN-8, UPC-A, EAN-13, GTIN-14 정규화, QR URL의 `brcd_no` 추출, check digit 검증, audit용 hash
- `src/services/supplement_barcode_lookup.py`: FoodQR-first lookup service, C003 report number 보강 조회, preview snapshot attach
- `src/models/schemas/supplement.py`: `SupplementBarcodeLookupRequest`, `SupplementBarcodeLookupResponse`, barcode candidate/observation schema, `SupplementAnalysisPreview.barcode_lookup`
- `src/api/v1/supplements.py`: `POST /api/v1/supplements/barcode/lookup`, `/supplements/analyze` optional `barcode_text`/`barcode_format`
- `tests/unit/barcode/test_normalization.py`
- `tests/unit/services/test_supplement_barcode_lookup.py`
- `tests/integration/api/test_supplement_barcode_lookup_api.py`
- `tests/integration/api/test_supplement_intake_api.py`

API 계약:

- `POST /api/v1/supplements/barcode/lookup`
  - request: `{ "barcode_text": "...", "barcode_format": "GTIN_14" }`
  - auth: `supplement:write`
  - OCR image consent: 필요 없음
  - response: `review_required`, `not_found`, `not_configured`, `provider_error`
  - invalid barcode checksum/format: HTTP 422
  - raw barcode는 audit metadata에 저장하지 않고 `barcode_hash`만 저장한다.
- `POST /api/v1/supplements/analyze`
  - optional form fields: `barcode_text`, `barcode_format`
  - barcode result는 `parsed_snapshot.barcode_lookup`, `match_snapshot.barcode_lookup`, `matched_product_candidates`에 후보로만 붙는다.
  - image intake/OCR preview와 동일하게 사용자 확인 전 최종 supplement record로 저장하지 않는다.

fail-closed 정책:

- `ENABLE_BARCODE_LOOKUP=false`이면 provider를 호출하지 않고 `not_configured`로 반환한다.
- FoodQR transport/provider 오류는 `provider_error`로 반환하고 raw provider body를 저장하지 않는다.
- FoodQR `matched` 결과도 항상 `review_required`다.
- 동일 barcode가 복수 FoodQR row/version을 반환할 수 있으므로 `auto_confirmed=false`를 고정한다.
- C003는 barcode direct lookup에 사용하지 않는다. FoodQR row가 `report_no`를 제공할 때만 보강 조회하며, C003 provider error는 FoodQR 후보를 막지 않는다.

검증:

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/python -m pytest Nutrition-backend/tests/unit/barcode/test_normalization.py Nutrition-backend/tests/unit/services/test_supplement_barcode_lookup.py Nutrition-backend/tests/integration/api/test_supplement_barcode_lookup_api.py -q --no-cov
.venv/bin/python -m pytest Nutrition-backend/tests/integration/api/test_supplement_intake_api.py -q --no-cov
```

현재 제한:

- C003 live 접근 권한은 여전히 별도 해결이 필요하다.
- FoodQR 상세 제조/원재료/영양 endpoint는 아직 연결하지 않았다.
- barcode image decoder는 `DisabledBarcodeAdapter`만 구현했다. 서버 이미지 디코딩은 zxing-cpp optional 범위로 후속 처리한다.
- 정확도, 커버리지, OCR 대비 개선율은 아직 주장하지 않는다.

## 16. 2026-05-16 C003 blocker 해소 준비 구현 결과

권장 구현 순서에 따라 C003 live 성공을 전제로 한 기능을 바로 켜지 않고, blocker를 재현 가능하게 진단하고 권한 해소 후 확장할 수 있는 기반을 먼저 추가했다.

구현 파일:

- `scripts/diagnose_mfds_c003_access.py`: C003 sample, C003 first page, C003 `PRDLST_REPORT_NO`, I0760 first page를 redacted JSON으로 진단한다.
- `src/nutrition/mfds_client.py`: JSON이 아닌 식품안전나라 provider 오류를 `INFO-100`, `INFO-300`, `INFO-400`, `ERROR-310`, `NON_JSON_PROVIDER_ERROR`로 분류한다.
- `src/nutrition/foodqr_client.py`: FoodQR 품목제조정보 상세 조회는 `FOODQR_PRODUCT_MANUFACTURING_PATH`가 설정된 경우에만 opt-in으로 호출한다.
- `src/config.py`, `backend/.env.example`: `FOODQR_PRODUCT_MANUFACTURING_PATH`를 빈 기본값으로 추가했다. 공식 Swagger/detail path 확인 전에는 비활성이다.
- `src/models/db/supplement.py`, `alembic/versions/0007_create_supplement_product_identifiers.py`: 검증된 바코드/QR/품목제조번호 identifier를 저장할 `supplement_product_identifiers` 테이블을 추가했다.
- `data/nutrition_reference/barcode/fixtures/c003_contract_cases.example.jsonl`: C003 contract fixture 형식 예시를 추가했다. live evidence가 아니며 권한 확인 후 교체한다.

운영 판단:

- C003 `sample` 경로는 식품안전나라 문서의 공개 sample key로 서비스 자체/파싱 계약을 확인하는 용도다.
- 실제 key 기반 C003 조회가 `INFO-400`이면 서비스 신청/권한 범위 문제로 분류하고, `INFO-100`이면 키 종류 또는 값 문제로 분류한다.
- FoodQR 상세 path는 공공데이터포털 화면에서 `getFoodQrProdList01` 외 실제 endpoint path를 확인하지 못한 상태이므로 하드코딩하지 않는다.
- `supplement_product_identifiers`는 raw barcode 평문을 기본 저장하지 않고 `identifier_value_hash`와 선택적 암호화 필드 중심으로 설계했다.

redacted live 진단 결과:

| Check | Status | Code | Items | 판단 |
| --- | --- | --- | --- | --- |
| C003 sample first page | `matched` | `INFO-000` | 5 | 공개 sample key로 C003 서비스와 parser 계약은 정상 확인됐다. |
| C003 actual key first page | `provider_error` | `INFO-100` | 0 | 현재 입력된 key는 C003 실제 호출에서 거절된다. 키 종류/값/신청 범위 재확인이 필요하다. |
| C003 actual key `PRDLST_REPORT_NO` | `provider_error` | `INFO-100` | 0 | 품목제조보고번호 path도 같은 키 오류로 막힌다. |
| I0760 actual key first page | `matched` | `INFO-000` | 100 | 동일 환경에서 I0760은 정상이라 MFDS 전체 연동 장애가 아니다. |

산출물:

- `output/evaluations/barcode-identity/2026-05-16/mfds-c003-access-diagnosis.json`

추가 blocker 처리 방안:

- C003 권한: 식품안전나라 인증키 관리에서 C003 서비스 신청/승인 여부를 확인하고, 승인 뒤 `scripts/diagnose_mfds_c003_access.py` 결과가 `INFO-000`인지 확인한다.
- FoodQR 상세 endpoint: 공공데이터포털 PC Swagger 명세 또는 공식 다운로드 명세에서 endpoint path를 확인한 뒤 `FOODQR_PRODUCT_MANUFACTURING_PATH`에 설정한다.
- 실제 정확도/커버리지: 공개/팀 동의 barcode 5-10건을 C003까지 연결되는 fixture로 교체한 뒤 `scripts/evaluate_barcode_identity.py`로만 주장한다.
