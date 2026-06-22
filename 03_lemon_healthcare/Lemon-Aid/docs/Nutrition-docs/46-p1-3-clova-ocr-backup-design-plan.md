# 46. P1-3 NAVER CLOVA OCR Backup Adapter 상세 설계 및 구현 플랜

작성일: 2026-05-16
범위: `01_HANDOFF.md` P1-3, NAVER Cloud CLOVA OCR backup adapter, Google Vision 호환 `OCRResult` 정규화, CLOVA Domain/API Gateway 준비

## 1. 현재 상태 요약

요구사항에는 `backend/src/ocr/clova.py`의 `ClovaOCR(OCRAdapter)` 신규 구현으로 적혀 있지만, 현재 repo의 실제 backend 경로는 `backend/Nutrition-backend/src`이며 CLOVA provider는 이미 아래 위치에 있다.

- `backend/Nutrition-backend/src/ocr/providers/clova.py`
- `backend/Nutrition-backend/tests/unit/ocr/test_clova_provider.py`
- `backend/Nutrition-backend/src/ocr/factory.py`
- `backend/Nutrition-backend/src/services/supplement_image_analysis.py`
- `backend/Nutrition-backend/src/config.py`
- `backend/.env.example`

따라서 P1-3는 "무에서 신규 provider 추가"가 아니라 **기존 `ClovaOCRAdapter`를 Google Vision과 동일한 layout-aware `OCRResult` 계약으로 확장하고, CLOVA 운영 준비 항목을 명확히 하는 작업**이다.

| 요구사항 | 현재 구현 | 차이 |
| --- | --- | --- |
| `ClovaOCR(OCRAdapter)` | `ClovaOCRAdapter(OCRAdapter)` 존재 | handoff 호환 alias `src/ocr/clova.py` 또는 `ClovaOCR = ClovaOCRAdapter` 필요 |
| httpx async REST 호출 | `httpx.AsyncClient` 또는 injected client 사용 | 충족 |
| `X-OCR-SECRET` header | 구현됨 | 충족, secret log 금지 유지 |
| response 정규화 | `fields[].inferText`, `inferConfidence`를 flat `OCRResult(text, provider, confidence)`로 반환 | `OCRResult.pages` layout 구조, boundingPoly, lineBreak, table cells 정규화 필요 |
| Google Vision과 동일 DTO | P1-2에서 `OCRResult.pages` 추가됨 | CLOVA adapter가 아직 pages를 채우지 않음 |
| backup routing | P1-2에서 CLOVA가 secondary fallback 첫 후보가 되도록 factory 보정됨 | CLOVA 결과 품질/빈 결과/에러 degrade 정책 테스트 보강 필요 |
| live smoke | 없음 | `RUN_CLOVA_OCR_LIVE_SMOKE=1` opt-in smoke 필요 |

## 2. 공식 문서 및 웹 조사 요약

구현 기준은 공식 문서다. 사용자 참고 블로그는 콘솔 사용 흐름을 이해하는 보조 자료로만 사용하고, API 필드명/보안 요구사항은 NAVER Cloud 공식 문서를 기준으로 한다.

| 주제 | 확인 내용 | 설계 반영 |
| --- | --- | --- |
| CLOVA API URL | CLOVA OCR API URL은 "CLOVA OCR 빌더에서 생성된 API Gateway의 고유 Invoke URL"이다. URL: <https://api-gov.ncloud-docs.com/docs/ai-application-service-ocr> | `CLOVA_OCR_API_URL`은 외부 구매 도메인이 아니라 APIGW Invoke URL로 취급한다. adapter가 임의 path를 붙이지 않는다. |
| 요청 header | `X-OCR-SECRET`는 NAVER Cloud Platform Domain에서 API Gateway 연동 시 생성한 Client Secret이다. URL: <https://api-gov.ncloud-docs.com/docs/ai-application-service-ocr> | `CLOVA_OCR_SECRET`는 backend secret으로만 관리한다. 모바일/프론트에 절대 노출하지 않는다. |
| 공통 에러 | 401은 Secret 검증 실패, 0022는 request domain invalid, 0023/0025는 호출 제한 관련 에러로 문서화되어 있다. URL: <https://api-gov.ncloud-docs.com/docs/ai-application-service-ocr> | provider error는 secret/body/image를 포함하지 않는 sanitized `OCRError`로 매핑한다. |
| CLOVA Domain | 공식 사용 가이드는 OCR API 제어 전에 NAVER Cloud CLOVA OCR 콘솔에서 도메인을 생성하고, 고유 InvokeURL을 API Gateway와 연동하도록 설명한다. URL: <https://guide-gov.ncloud-docs.com/docs/clovaocr-example01> | "도메인 필요"는 일반 DNS 도메인 구매가 아니라 NCP 콘솔의 OCR Domain 생성 필요로 해석한다. |
| API Gateway | Domain 가이드는 OCR InvokeURL을 API Gateway Endpoint에 연결한 뒤 외부 연동한다고 설명하고, API Gateway 이용 신청 시 별도 요금이 발생할 수 있다고 안내한다. URL: <https://guide.ncloud-docs.com/docs/ja/clovaocr-domain> | CLOVA는 기본 OFF이며 vendor/security/cost review gate 뒤에서만 켠다. |
| General OCR response | General OCR 문서는 `fields[].inferText`, `fields[].inferConfidence`, `fields[].boundingPoly.vertices`, `lineBreak`, `tables[].cells[]`, `cellWords[]` 등을 제공한다고 설명한다. URL: <https://api.ncloud-docs.com/docs/en/ai-application-service-ocr-ocr> | `fields`와 가능하면 `tables`를 `OCRPage/OCRBlock/OCRParagraph/OCRWord`로 정규화한다. |
| Firebase Hosting | Firebase Hosting은 프로젝트별 `web.app`, `firebaseapp.com` subdomain을 무료 제공하고 SSL을 기본 제공한다. URL: <https://firebase.google.com/docs/hosting/quickstart> | 프론트 데모/정적 사이트 호스팅에는 가능하지만 CLOVA OCR Domain/API Gateway 대체 수단은 아니다. |
| Firebase App Hosting custom domain | Firebase App Hosting custom domain은 DNS record와 SSL 인증서 설정을 다룬다. URL: <https://firebase.google.com/docs/app-hosting/custom-domain> | 자체 도메인 연결은 가능하지만 CLOVA OCR 호출에는 필요 없다. backend secret proxy로 쓰려면 별도 배포/비용/보안 검토 필요. |
| 무료 hosting subdomain | GitHub Pages는 `github.io`, Cloudflare Pages는 `pages.dev`, Vercel은 `vercel.app`, Netlify는 `netlify.app` 기본 subdomain을 제공한다. URL: <https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages>, <https://developers.cloudflare.com/pages/configuration/preview-deployments/>, <https://vercel.com/docs/domains/working-with-domains>, <https://docs.netlify.com/manage/domains/domains-fundamentals/understand-domains/> | 무료 subdomain은 데모 UI 공개용으로만 검토한다. CLOVA secret을 넣는 backend endpoint로 직접 쓰면 안 된다. |
| 무료 DDNS/subdomain | No-IP는 무료 Dynamic DNS hostname, DuckDNS는 무료 Dynamic DNS를 제공한다고 공식 사이트에서 설명한다. URL: <https://www.noip.com/free>, <https://www.duckdns.org/> | 로컬 서버 임시 노출에는 가능하지만 의료/식별 이미지 OCR 실험에는 권장하지 않는다. CLOVA 호출은 outbound라 DDNS가 필요 없다. |

확인 한계:

- I cannot find the official documentation that requires a user-owned public DNS domain, Firebase domain, or custom domain to call CLOVA General OCR. 공식 문서는 NAVER Cloud 콘솔의 CLOVA OCR Domain과 API Gateway Invoke URL을 요구한다.
- I cannot find the official documentation that Firebase Hosting/App Hosting can replace NAVER Cloud CLOVA OCR Domain or issue `X-OCR-SECRET`. Firebase는 호스팅/앱 배포 도구이지 CLOVA OCR credential 발급 수단이 아니다.
- CLOVA가 영양제 성분표에서 Google Vision보다 정확하다는 공식/fixture 근거는 아직 없다. 정확도, 커버리지, 개선율은 fixture report 전까지 주장하지 않는다.

## 3. “도메인 필요” 해석

이번 설계에서 "도메인"은 세 가지 의미가 섞이지 않게 분리한다.

| 용어 | 의미 | P1-3 필요 여부 |
| --- | --- | --- |
| CLOVA OCR Domain | NAVER Cloud CLOVA OCR 콘솔에서 만드는 OCR 서비스 리소스. Domain ID/name/code, OCR Invoke URL, Secret Key 발급과 연결됨 | 필요 |
| API Gateway Invoke URL | CLOVA OCR Domain을 API Gateway에 연동해서 외부 앱이 호출하는 URL | 필요 |
| DNS domain/custom domain | `example.com`, `app.web.app`, `*.pages.dev` 같은 웹 주소 | CLOVA API 호출에는 불필요 |

결론:

- Firebase를 써서 무료 `web.app` 주소를 받아도 CLOVA OCR Domain을 대체할 수 없다.
- CLOVA 호출은 backend가 NAVER Cloud APIGW Invoke URL로 outbound POST를 보내는 구조다.
- 모바일/프론트가 CLOVA에 직접 호출하면 `X-OCR-SECRET`가 노출되므로 금지한다.
- 무료 도메인/서브도메인은 데모 페이지 공개, staging preview, 팀 공유용으로만 의미가 있다.

## 4. 설계 결정

### 4.1 파일 경로와 클래스명

권장 구현은 기존 provider package 구조를 따른다.

- 주 구현: `backend/Nutrition-backend/src/ocr/providers/clova.py`
- 호환 export: `backend/Nutrition-backend/src/ocr/clova.py`

호환 alias는 아래 형태로 둔다.

```python
from src.ocr.providers.clova import ClovaOCRAdapter

ClovaOCR = ClovaOCRAdapter
```

repo 내부 import는 `src.ocr.providers.clova.ClovaOCRAdapter`를 유지한다. handoff나 외부 테스트가 `src.ocr.clova.ClovaOCR`를 기대할 때만 alias가 역할을 한다.

### 4.2 provider 역할

CLOVA는 primary가 아니라 backup이다.

1. Google Vision primary가 OCR text를 못 만들거나 confidence가 `Settings.ocr_confidence_threshold`보다 낮다.
2. `ENABLE_CLOVA_OCR=true`, `ALLOW_EXTERNAL_OCR=true`, `EXTERNAL_OCR_PROCESSING` consent가 모두 충족된다.
3. `CLOVA_OCR_API_URL`, `CLOVA_OCR_SECRET`가 존재한다.
4. CLOVA가 non-empty text를 반환하면 parser input provider를 `clova_ocr`로 남긴다.
5. CLOVA 실패/빈 text면 기존 primary OCR 결과 또는 수동 입력 흐름으로 degrade한다.

자동 병합은 하지 않는다. Google/CLOVA text가 다르면 하나를 자동 합성하지 않고, 선택된 provider 하나의 결과만 parser로 넘긴다.

### 4.3 request 설계

기본은 General OCR JSON request다.

```json
{
  "version": "V2",
  "requestId": "<uuid>",
  "timestamp": 1710000000000,
  "images": [
    {
      "format": "png",
      "name": "supplement_label",
      "data": "<base64-image>"
    }
  ]
}
```

정책:

- `format`: `image/jpeg -> jpg`, `image/png -> png`, `image/webp -> png`로 현재 정책 유지. WebP는 내부 validate 후 fallback format을 png로 두되, 실제 CLOVA가 WebP data를 받아들이는지 live smoke 전에는 성공을 주장하지 않는다.
- `url` request는 사용하지 않는다. 이미지 URL 공개/보관이 필요해지므로 P1-3 범위에서는 `data`만 사용한다.
- `requestId`는 UUID, `timestamp`는 ms epoch.
- `Content-Type: application/json`, `X-OCR-SECRET` header만 추가한다.
- timeout은 Google Vision timeout 재사용을 멈추고 `clova_ocr_timeout_seconds`로 분리하는 것을 권장한다.

### 4.4 response 정규화

P1-2 이후 표준 OCR DTO는 `OCRResult(text, provider, confidence, pages)`다. CLOVA도 이 DTO를 채운다.

#### fields 정규화

CLOVA General OCR의 `images[0].fields[]`를 순서대로 읽는다.

- `inferText` -> `OCRWord.text`
- `inferConfidence` -> `OCRWord.confidence`
- `boundingPoly.vertices` -> `OCRWord.bounding_box`
- `lineBreak=true` -> paragraph text 조립 시 줄바꿈
- `type=CHECKBOX`는 영양제 라벨 텍스트 parser의 primary source로 쓰지 않고, text가 있으면 일반 field와 동일하게 candidate로만 둔다.

Google Vision과 완전히 같은 page/block/paragraph 원천 구조가 없으므로, CLOVA fields는 아래 synthetic hierarchy로 정규화한다.

```text
OCRPage
  OCRBlock(block_type="TEXT")
    OCRParagraph
      OCRWord(field 0)
      OCRWord(field 1)
      ...
```

이 synthetic 구조는 provider raw response를 저장하지 않고 runtime parser input으로만 사용한다. `block_type`은 `"TEXT"`로 둔다.

#### tables 정규화

영양제 성분표는 표 형태가 많으므로 `tables[].cells[].cellTextLines[].cellWords[]`가 있으면 fields 뒤에 별도 block으로 추가한다.

```text
OCRPage
  OCRBlock(block_type="TEXT")
  OCRBlock(block_type="TABLE")
```

테이블 cell text는 자동 영양성분 계산 근거로 바로 쓰지 않고 parser 후보 텍스트로만 전달한다. 표 구조를 영양성분 row/column으로 해석하는 일은 Layout Parser 후속 작업으로 분리한다.

#### confidence aggregation

- 우선순위: word confidence 평균
- 없으면 cell/field container confidence 평균
- 없으면 `None`
- 0~1 범위 밖의 값은 버리고, 임의 confidence를 만들지 않는다.

#### empty result

HTTP/provider 성공이지만 readable text가 없는 경우는 `OCRError`가 아니라 `OCRResult(text="", provider="clova_ocr", confidence=..., pages=())` 반환을 권장한다. 그러면 orchestration이 "fallback 실패"와 "provider 성공 but text 없음"을 구분할 수 있고, 현재 service는 empty text fallback을 채택하지 않는다.

### 4.5 설정 설계

현재 설정:

```dotenv
ENABLE_CLOVA_OCR=false
CLOVA_OCR_API_URL=
CLOVA_OCR_SECRET=
```

권장 보정:

```dotenv
ENABLE_CLOVA_OCR=false
CLOVA_OCR_API_URL=
CLOVA_OCR_SECRET=
CLOVA_OCR_TIMEOUT_SECONDS=15
CLOVA_OCR_MAX_RETRIES=1
```

`CLOVA_OCR_API_URL` 설명을 `.env.example`에 명확히 적는다.

- 값: NAVER Cloud CLOVA OCR Domain에서 API Gateway 자동 연동 후 복사한 APIGW Invoke URL
- 아님: Firebase domain, GitHub Pages domain, 구매 DNS domain

production validator:

- `ENABLE_CLOVA_OCR=true`이면 `ALLOW_EXTERNAL_OCR=true` 필수
- `CLOVA_OCR_API_URL`, `CLOVA_OCR_SECRET` 필수
- production에서는 vendor/security sign-off 없이는 `ENABLE_CLOVA_OCR=true` 차단을 유지한다.

### 4.6 Firebase / 무료 도메인 활용 여부

| 후보 | 무료 주소 | CLOVA OCR Domain 대체 | 권장 용도 |
| --- | --- | --- | --- |
| Firebase Hosting | `*.web.app`, `*.firebaseapp.com` | 불가 | 모바일/웹 데모 프론트, 정적 랜딩, preview |
| Firebase App Hosting | custom domain 연결 가능 | 불가 | 서버 렌더링 앱 배포 후보. CLOVA secret proxy로 쓰려면 별도 보안 설계 필요 |
| GitHub Pages | `*.github.io` | 불가 | 공개 정적 문서/데모 |
| Cloudflare Pages | `*.pages.dev` | 불가 | 정적/프론트 preview, PR preview |
| Vercel | `*.vercel.app` | 불가 | 프론트/Next.js demo |
| Netlify | `*.netlify.app` | 불가 | 정적/프론트 demo |
| DuckDNS / No-IP | free DDNS hostname | 불가 | 로컬 서버 임시 노출. OCR secret 처리에는 비권장 |
| EU.org | `*.eu.org` 계열 무료 delegation | 불가 | 장기 무료 주소 실험. 승인/신뢰성 리스크 때문에 healthcare OCR demo 기본값으로 비권장 |
| Freenom | 무료 TLD 주장 | 불가 | 신뢰성/운영 지속성 리스크로 권장하지 않음 |

결론:

- CLOVA OCR을 쓰려면 무료 웹 도메인이 아니라 NAVER Cloud CLOVA OCR Domain + API Gateway Invoke URL + Secret Key가 필요하다.
- Firebase는 frontend demo hosting으로는 쓸 수 있다.
- Firebase Functions/App Hosting/Cloud Run을 backend proxy로 쓰는 방안은 가능하지만, 현재 FastAPI backend가 이미 있으므로 P1-3의 최소 구현에는 불필요하다.
- OCR secret은 어떤 경우에도 Flutter/Firebase client bundle에 넣지 않는다.

## 5. 구현 상세 플랜

### R1. CLOVA adapter 호환 alias 추가

파일:

- `backend/Nutrition-backend/src/ocr/clova.py`
- `backend/Nutrition-backend/tests/unit/ocr/test_clova_provider.py`

작업:

- `ClovaOCR = ClovaOCRAdapter` alias 추가
- `from src.ocr.clova import ClovaOCR` smoke test 추가

완료 기준:

- handoff 경로를 기대하는 import가 통과
- provider 로직 중복 없음

### R2. CLOVA response layout parser 구현

파일:

- `backend/Nutrition-backend/src/ocr/providers/clova.py`
- `backend/Nutrition-backend/tests/unit/ocr/test_clova_provider.py`

작업:

- `_parse_clova_response(payload, image)`로 image metadata를 받을 수 있게 변경
- `fields[].boundingPoly.vertices`를 `OCRBoundingPoly`로 변환
- `fields[]`를 synthetic `OCRPage -> OCRBlock(TEXT) -> OCRParagraph -> OCRWord`로 변환
- `lineBreak` 기반 text 조립
- `tables[].cells[].cellTextLines[].cellWords[]`가 있으면 `OCRBlock(TABLE)`로 추가
- readable text가 없어도 provider 성공이면 empty `OCRResult`로 반환

완료 기준:

- mock response에서 text, confidence, page/block/word, bounding box 검증
- `lineBreak=true`가 `OCRResult.text` 줄바꿈에 반영
- empty fields는 `OCRResult(text="", provider="clova_ocr", confidence=None, pages=())`

### R3. CLOVA 전용 timeout/retry 설정 보정

파일:

- `backend/Nutrition-backend/src/config.py`
- `backend/.env.example`
- `backend/Nutrition-backend/tests/unit/test_config.py`

작업:

- `clova_ocr_timeout_seconds: int = Field(default=15, ge=1, le=60)`
- `clova_ocr_max_retries: int = Field(default=1, ge=0, le=3)`
- `.env.example` 주석에 APIGW Invoke URL 의미 명시
- 기존 `google_vision_timeout_seconds` 재사용 제거

완료 기준:

- default/env override/validation tests 통과
- secret 값은 테스트 fixture 외 출력 금지

### R4. error mapping과 fail-closed 강화

파일:

- `backend/Nutrition-backend/src/ocr/providers/clova.py`
- `backend/Nutrition-backend/tests/unit/ocr/test_clova_provider.py`

작업:

- HTTP 401/400/429/5xx를 sanitized `OCRError`로 매핑
- CLOVA 공통 에러 payload가 있으면 code만 남기고 request/image/secret 미노출
- transient status는 `clova_ocr_max_retries`만큼 retry
- provider `inferResult`가 `SUCCESS`가 아니면 sanitized failure

완료 기준:

- error message에 `X-OCR-SECRET`, base64 image, raw request body가 없음
- retry test는 transient만 재시도하고 validation/secret 실패는 재시도하지 않음

### R5. service fallback 계약 테스트 보강

파일:

- `backend/Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py`
- 필요 시 `backend/Nutrition-backend/tests/integration/api/test_supplement_analyze_google_vision.py`

작업:

- Google Vision confidence `< OCR_CONFIDENCE_THRESHOLD`이면 CLOVA fake adapter가 호출됨
- CLOVA non-empty text면 `ocr_provider=clova_ocr`로 parser input이 바뀜
- CLOVA empty text면 primary result 유지
- CLOVA `OCRError`면 primary result 유지
- consent/gate가 없으면 호출되지 않음

완료 기준:

- fallback path가 "자동 병합"이 아니라 "단일 provider 채택"임을 테스트로 고정

### R6. live smoke opt-in 추가

파일:

- `backend/Nutrition-backend/tests/integration/ocr/test_clova_smoke.py`
- 필요 시 `backend/scripts/smoke_clova_ocr.py`

작업:

- 기본 skip
- `RUN_CLOVA_OCR_LIVE_SMOKE=1`
- `CLOVA_OCR_API_URL`, `CLOVA_OCR_SECRET`, local test image path가 있을 때만 실행
- 출력은 provider, confidence presence, page/word count, elapsed ms 정도만
- raw OCR text, raw image, raw response 저장 금지

완료 기준:

- API key/secret 없이 CI 통과
- live smoke 결과는 redacted summary만 남김

### R7. docs 보정

파일:

- `docs/Nutrition-docs/33-three-tier-ocr-pipeline-implementation-guide.md`
- `docs/Nutrition-docs/35-google-vision-ocr-provider-implementation-plan.md`
- `docs/Nutrition-docs/40-ocr-3-tier-expansion-design-plan.md`
- 이 문서

작업:

- CLOVA backup이 "도메인 구매 필요"가 아니라 "NCP CLOVA OCR Domain 생성 필요"임을 명시
- Firebase/free domain은 frontend demo hosting 용도와 OCR Domain 대체 불가로 분리
- CLOVA 정확도/개선율 주장은 fixture 전까지 금지
- `CLOVA_OCR_API_URL`가 APIGW Invoke URL이라는 설명 추가

완료 기준:

- stale "CLOVA 미구현" 표현이 현재 코드와 충돌하지 않음
- 공식 문서 URL 유지

## 6. 테스트 계획

### Unit

- `tests/unit/ocr/test_clova_provider.py`
  - request shape: `version=V2`, `requestId`, `timestamp`, `images[].data`
  - header: `X-OCR-SECRET`, `Content-Type`
  - `fields[]` -> text/confidence/pages/word bounding box
  - `lineBreak` text 조립
  - `tables[]` -> table block 정규화
  - empty success -> empty `OCRResult`
  - HTTP/provider error sanitize
  - timeout/retry
- `tests/unit/ocr/test_ocr_factory.py`
  - `ENABLE_CLOVA_OCR=true`이면 fallback tuple에 CLOVA 포함
  - CLOVA가 P1-2 confidence fallback에서 first fallback인지 확인
- `tests/unit/services/test_supplement_image_analysis.py`
  - low-confidence primary -> CLOVA 호출
  - CLOVA empty/error -> primary 유지
  - custom `OCR_CONFIDENCE_THRESHOLD`가 fallback 호출 여부를 바꿈
- `tests/unit/test_config.py`
  - CLOVA timeout/retry default/env/bounds
  - production fail-closed validation

### Integration

- `tests/integration/api/test_supplement_analyze_google_vision.py` 또는 신규 `test_supplement_analyze_clova_fallback.py`
  - fake Google low confidence + fake CLOVA success
  - raw OCR text 미저장
  - audit metadata secret 미노출
  - external OCR consent 없으면 CLOVA 호출 금지

### Live smoke

기본 CI에는 넣지 않는다.

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend
RUN_CLOVA_OCR_LIVE_SMOKE=1 .venv/bin/python -m pytest Nutrition-backend/tests/integration/ocr/test_clova_smoke.py -q --no-cov
```

저장 금지:

- `CLOVA_OCR_SECRET`
- base64 image
- raw provider response
- raw OCR text

## 7. 검증 명령

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/python -m pytest Nutrition-backend/tests/unit/ocr/test_clova_provider.py Nutrition-backend/tests/unit/ocr/test_ocr_factory.py Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py Nutrition-backend/tests/unit/test_config.py -q --no-cov
.venv/bin/python -m pytest Nutrition-backend/tests/integration/api/test_supplement_analyze_google_vision.py -q --no-cov
.venv/bin/python -m ruff check Nutrition-backend/src/ocr Nutrition-backend/src/services/supplement_image_analysis.py Nutrition-backend/tests/unit/ocr Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py
.venv/bin/python -m black --check Nutrition-backend/src/ocr Nutrition-backend/src/services/supplement_image_analysis.py Nutrition-backend/tests/unit/ocr Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py
git diff --check
```

## 8. 구현 체크리스트

- [x] 현재 CLOVA provider 파일 위치 확인
- [x] CLOVA OCR API URL/`X-OCR-SECRET` 공식 문서 확인
- [x] CLOVA Domain이 일반 DNS domain이 아니라 NCP OCR Domain 리소스임을 확인
- [x] Firebase/free subdomain이 CLOVA OCR Domain을 대체할 수 없음을 확인
- [x] 현재 adapter가 flat `OCRResult`만 반환한다는 차이 확인
- [x] `src/ocr/clova.py` 호환 alias 추가
- [x] CLOVA `fields[]`를 `OCRResult.pages`로 정규화
- [x] CLOVA `tables[]` optional 정규화
- [x] CLOVA 전용 timeout/retry settings 추가
- [x] empty success / provider error / secret sanitize 테스트 보강
- [x] live smoke opt-in test 추가
- [x] docs/33, docs/35, docs/40 stale 표현 보정

## 8.1 구현 결과 요약

2026-05-16 구현 결과:

- `backend/Nutrition-backend/src/ocr/providers/clova.py`
  - `fields[]`를 synthetic `OCRPage -> OCRBlock(TEXT) -> OCRParagraph -> OCRWord`로 정규화한다.
  - `tables[]`가 있으면 `OCRBlock(TABLE)`로 추가한다.
  - `boundingPoly.vertices`, `lineBreak`, 0~1 범위 confidence만 반영한다.
  - provider success but empty text는 empty `OCRResult`로 반환한다.
  - HTTP transient status는 `CLOVA_OCR_MAX_RETRIES`만큼 재시도하고, error message는 status/code만 남긴다.
- `backend/Nutrition-backend/src/ocr/clova.py`
  - handoff 호환용 `ClovaOCR = ClovaOCRAdapter` alias를 제공한다.
- `backend/Nutrition-backend/src/config.py`, `backend/.env.example`
  - `CLOVA_OCR_TIMEOUT_SECONDS=15`, `CLOVA_OCR_MAX_RETRIES=1`를 추가했다.
  - `CLOVA_OCR_API_URL`이 Firebase/custom DNS가 아니라 NCP CLOVA OCR API Gateway Invoke URL임을 명시했다.
- `backend/Nutrition-backend/tests/integration/ocr/test_clova_smoke.py`
  - `RUN_CLOVA_OCR_LIVE_SMOKE=1` opt-in live smoke를 추가했다.

검증 결과:

```bash
.venv/bin/python -m ruff check Nutrition-backend/src/ocr/providers/clova.py Nutrition-backend/src/ocr/clova.py Nutrition-backend/src/config.py Nutrition-backend/tests/unit/ocr/test_clova_provider.py Nutrition-backend/tests/unit/ocr/test_ocr_factory.py Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py Nutrition-backend/tests/unit/test_config.py Nutrition-backend/tests/integration/ocr/test_clova_smoke.py
# All checks passed

.venv/bin/python -m pytest Nutrition-backend/tests/unit/ocr/test_clova_provider.py Nutrition-backend/tests/unit/ocr/test_ocr_factory.py Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py Nutrition-backend/tests/unit/test_config.py -q --no-cov
# 87 passed

.venv/bin/python -m pytest Nutrition-backend/tests/unit/ocr -q --no-cov
# 31 passed

.venv/bin/python -m pytest Nutrition-backend/tests/integration/ocr/test_clova_smoke.py -q --no-cov
# 1 skipped unless RUN_CLOVA_OCR_LIVE_SMOKE=1
```

## 9. 권장 구현 순서

1. `src/ocr/clova.py` alias를 추가해 handoff import path를 맞춘다.
2. `ClovaOCRAdapter.extract_text()`가 `_parse_clova_response(payload, image)`를 호출하도록 바꾼다.
3. `fields[]` 기반 `OCRResult.pages` 정규화를 먼저 구현한다.
4. `lineBreak`, bounding box, confidence aggregation 테스트를 추가한다.
5. `tables[]` table block 정규화를 추가한다.
6. `clova_ocr_timeout_seconds`, `clova_ocr_max_retries`를 설정/환경변수/테스트에 추가한다.
7. provider error sanitize와 retry policy를 보강한다.
8. image-analysis fallback integration test를 보강한다.
9. live smoke는 opt-in으로만 추가한다.
10. docs 상태를 구현 결과에 맞게 보정한다.

## 10. 권장 커밋 단위

1. `docs(ocr): design CLOVA OCR backup adapter hardening`
   - Why: CLOVA Domain/API Gateway 준비와 무료 도메인 오해를 정리해 구현 범위를 고정한다.
2. `feat(ocr): expose CLOVA OCR compatibility alias`
   - Why: handoff import path와 현재 provider package 구조를 동시에 지원한다.
3. `feat(ocr): normalize CLOVA OCR layout into OCRResult`
   - Why: Google Vision과 CLOVA fallback이 같은 layout-aware parser 계약을 사용하게 한다.
4. `feat(config): add CLOVA OCR timeout and retry settings`
   - Why: Google Vision 설정 재사용을 끊고 backup provider 장애 반경을 제한한다.
5. `test(ocr): cover CLOVA fallback routing and live smoke gate`
   - Why: external OCR secret 없이 CI는 재현 가능하게 유지하고, 실제 호출은 명시 opt-in으로 검증한다.
