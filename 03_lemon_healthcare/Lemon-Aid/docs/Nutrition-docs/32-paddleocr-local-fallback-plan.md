# 32. PaddleOCR 로컬 OCR 대안 도입 플랜

> **문서 정보**
> 버전: v1.0 | 작성일: 2026-05-13 | 상태: 제안(브레인스토밍 + 도입 명세) | 작성자: yeong-tech

---

## 0. 한 줄 요약

CLOVA OCR 의 사용량 기반 과금(이미지당 ~50원, 월 1만 콜 = ~50만원)이 학생 프로젝트 예산을 초과할 위험이 크므로, **CLOVA 백업을 로컬 오픈소스 PaddleOCR 어댑터로 대체**하는 방안을 채택한다. Google Cloud Vision(주력)은 유지하되, 폴백 경로를 "API → 무료 로컬 모델" 로 전환해 운영비 0원·환자 정보 외부 전송 0건을 동시에 달성한다.

---

## 1. 문제 정의 — CLOVA OCR 의 비용 부담

### 1.1 현재 설계의 비용 구조

기존 [docs/09 §5.2](./09-data-catalog.md), [docs/27](./27-ot-s2b-google-vision-ocr-review-plan.md), [docs/11 §745](./11-detailed-feature-implementation-plan.md) 는 OCR 폴백을 다음과 같이 정의한다:

- 주력: Google Cloud Vision (월 1,000건 무료, 이후 1,000건당 $1.5)
- 폴백: Naver CLOVA OCR (월 1,000건 무료, 이후 General OCR 기준 호출당 약 ₩40~50)

### 1.2 운영 시나리오별 비용 추산(2026.05 기준)

| 사용자 수 | 월 OCR 호출 추산 | Google Vision | CLOVA(폴백률 30%) | 월 총비용 |
| --- | --- | --- | --- | --- |
| 베타 50명(Phase 4) | ~500건 | 무료 | 무료 | **0원** |
| 정식 출시 1,000명 | ~10,000건 | $13.5 ≈ ₩18,000 | ₩135,000 | **약 ₩150,000** |
| 1만 활성 사용자 | ~100,000건 | $148.5 ≈ ₩200,000 | ₩1,350,000 | **약 ₩1,550,000/월** |
| 5만 사용자(Year 2) | ~500,000건 | ~₩1,000,000 | ~₩6,750,000 | **약 ₩7,750,000/월** |

> CLOVA 가 전체 비용의 약 87% 를 차지. Google Vision 은 자체 무료 ladder + 비교적 저렴한 단가로 통제 가능하지만 CLOVA 는 정식 출시 시 급증.

### 1.3 학생 프로젝트 컨텍스트

- 10주 학생 PoC 단계는 베타 50명 수준이라 CLOVA 무료 quota 안에 머무름 → 단기 문제 없음.
- **그러나 docs/22 인수인계 시점에 발주처가 CLOVA 단가 그대로 운영하면 곧바로 월 100만원+ 운영비가 발생** → 발주처 인수 거부 또는 단가 재협상 부담.
- Google Vision 단독 폴백이 없는 상태(현재 `ocr/providers/noop.py` 만 구현) → CLOVA 미사용 시 운영 가능한 폴백 0건.

---

## 2. 대안 후보 비교

PaddleOCR 외에도 검토해야 할 로컬·오픈소스 후보를 함께 비교한다.

### 2.1 후보 비교표

| 후보 | 라이선스 | 정확도(한글 영양제 라벨 추정) | 응답시간(M4 Pro) | 운영비 | 의존성 크기 | 환자 데이터 |
| --- | --- | --- | --- | --- | --- | --- |
| **PaddleOCR** | Apache 2.0 | **85~90%** (`ko_PP-OCRv4` 모델) | ~300~600ms | **0원** | paddlepaddle ~500MB + paddleocr ~200MB | 로컬 처리 |
| Tesseract 5 | Apache 2.0 | 70~80% (한글 LSTM) | ~200~400ms | 0원 | ~50MB | 로컬 처리 |
| EasyOCR | Apache 2.0 | 80~85% (한·영) | ~500~1,200ms | 0원 | torch ~2GB + easyocr ~200MB | 로컬 처리 |
| docTR (Mindee) | Apache 2.0 | 75~85% (영문 강세) | ~400~800ms | 0원 | pytorch + ~300MB | 로컬 처리 |
| CLOVA OCR(현행 백업) | 상용 | 90~95%(한글 특화) | ~600ms(API) | 호출당 ~₩40~50 | ~0(클라이언트만) | 외부 송출 |
| Google Vision(주력 유지) | 상용 | 88~93%(한글 양호) | ~700ms(API) | 1k 호출 무료 후 $1.5/1k | ~0(클라이언트만) | 외부 송출 |

### 2.2 PaddleOCR 추천 근거

1. **한글 정확도가 오픈소스 1위 그룹**: 2024년 PP-OCRv4 모델이 한·중·일 라벨에서 90%+ 정확도 보고(Baidu 공식 벤치마크). EasyOCR(85%)·Tesseract(75%)보다 안정적.
2. **CPU 추론 가능**: 학생 팀 MacBook M4 Pro 24GB 환경에서 GPU 없이 평균 ~400ms 응답(텍스트 라인 ≤20 기준). CLOVA API 응답 대비 ±10% 수준.
3. **양자화 모델 지원**: `PP-OCRv4 mobile` 변종은 ~10MB 로 컨테이너 부담 최소.
4. **언어 모델 교체 자유**: 한국어 외 영어·중국어 라벨도 동일 어댑터로 처리 → 글로벌 확장 시 (docs/03 §5 Year 3) 추가 비용 없음.
5. **Apache 2.0**: 상업 사용·재배포 자유, 발주처 인수 후 자체 패치 가능.
6. **오프라인 동작**: 인터넷 차단 환경에서도 동작 → 의료기관 내 폐쇄망 운영(docs/17 §6) 시 강점.

### 2.3 PaddleOCR 한계·리스크

| 리스크 | 영향 | 완화책 |
| --- | --- | --- |
| 의존성 크기 ~700MB | Docker 이미지 비대화 | 별도 `[ocr-local]` extras 로 분리, Phase 게이트 통과 시에만 설치 |
| GPU 없으면 응답시간 1초 초과 가능 | SLA(6초) 압박 | 영양제 라벨 최대 2048px 다운스케일 + 라인 수 ≤30 cap |
| 한글 라벨 중 손글씨·왜곡 라벨 정확도 ↓ | 영양제 라벨 자체는 인쇄체라 영향 미미 | 신뢰도 < 0.75 시 사용자 확인 화면으로 escalation |
| Paddle 의존 충돌(numpy/torch 버전) | 다른 모듈 호환성 | uv/poetry 의존성 해소 + CI matrix 테스트 |
| 신규 컴플라이언스 검토 필요 | 발주처 도입 승인 지연 | Apache 2.0 + 로컬 처리 → 외부 전송 0 → 의외로 승인 간단 (docs/17 §7 부합) |

---

## 3. 3-Lens 브레인스토밍

### 3.1 Lens 1 — Gap (현재 설계의 갭)

- [Gap-1] **CLOVA 비용 가시화 부재**: docs/09·11·27 어디에도 월간 호출량 vs CLOVA 비용 시뮬레이션 없음. 학생 팀이 인수 후 발주처가 부담할 비용을 모르고 설계.
- [Gap-2] **단일 폴백 전제**: docs/27 §103 의 `supplement_ocr_provider: Literal["none", "clova_general", "google_vision"]` 가 CLOVA 또는 Google 둘 중 하나만 활성화 가정 → "두 클라우드 OCR 모두 비용 부담" 시나리오 미고려.
- [Gap-3] **로컬 OCR 부재**: `src/ocr/providers/` 에 `noop.py` 만 존재 → CLOVA 비활성화 시 폴백 경로 0.
- [Gap-4] **컴플라이언스 우위 미활용**: 로컬 OCR 은 docs/17 §6 의 "환자 정보 외부 전송 0" 요건과 정확히 일치하나, 현재 설계는 클라우드 OCR 전송을 가정.

### 3.2 Lens 2 — Perspective (다관점 평가)

- **단순성(학생 10주)**: PaddleOCR 도입은 ① `pip install paddleocr paddlepaddle` 추가 ② `ocr/providers/paddle.py` 어댑터 60~80줄 작성 ③ Settings + .env + production validator 2~3줄. 1~2일 작업으로 완료 가능. 학생 일정 부담 낮음.
- **안전성(만성질환자·의료법)**: 로컬 처리이므로 docs/17 §3 동의 매트릭스에서 "분석용 임시 처리" 카테고리만으로 충분 → 별도 동의 토글 불요. 의료법·개인정보 리스크 모두 ↓.
- **확장성(post-MVP)**: 한국어 외 언어 라벨, 의료기관 폐쇄망, 인수인계 후 발주처 자체 운영 — 세 시나리오에서 모두 우위. 단점: 정확도 90% 수준에서 정체될 가능성(상용 90~95%와 -3~5%p 격차).

### 3.3 Lens 3 — Competitive (경쟁·대안 매핑)

- **vs 필라이즈**: 필라이즈는 폐쇄형 OCR(추정 자체 모델) — 본 프로젝트가 Google Vision + PaddleOCR 이중 채널을 운영하면 정확도·비용 동시 우위.
- **vs CalZen / Cronometer**: 글로벌 앱은 대부분 클라우드 OCR(AWS Textract, Google Vision) 단일 의존 → 본 프로젝트의 "로컬 폴백 + 환자 데이터 외부 전송 0" 포지셔닝은 의료기관 협업 시 차별점.
- **오픈소스 생태계**: PaddleOCR 은 GitHub 41k+ stars(2026.05 기준 추정), 한국어 모델·블로그 자료 풍부. 학습 곡선 낮음. EasyOCR(20k stars)도 후보이나 정확도·속도 모두 PaddleOCR 우세.

---

## 4. 도입 결정

### 4.1 채택 안

- **주력**: Google Cloud Vision API (현재 설계 유지)
- **폴백 1**: PaddleOCR 로컬 모델 (`ko_PP-OCRv4`) — **CLOVA 대체**
- **폴백 2**: CLOVA OCR (보존, 단 기본 비활성화)
- **No-op**: `noop.py` (intake-only 환경 유지)

운영자가 환경 변수로 폴백 우선순위를 선택. `enable_clova_ocr=false` 가 기본값(비용 보호) → CLOVA 는 발주처가 명시적으로 켤 때만 사용.

### 4.2 트래픽 라우팅 규칙

```
이미지 업로드
    ↓
Google Vision 호출 (월 1k 무료 quota 활용)
    ↓
신뢰도 ≥ 0.85? — Yes → 결과 반환
    ↓ No
PaddleOCR 로컬 호출 (무료, ~400ms)
    ↓
두 결과 신뢰도 가중 평균 ≥ 0.75? — Yes → 결과 반환
    ↓ No
`enable_clova_ocr=true` ? — Yes → CLOVA 호출 (운영자 명시 활성화 시)
    ↓ No
사용자 수정 화면으로 escalation (텍스트 직접 입력)
```

### 4.3 비용 시나리오 재추산

| 사용자 수 | 월 호출 | Google Vision | PaddleOCR | CLOVA | 월 총비용 |
| --- | --- | --- | --- | --- | --- |
| 정식 출시 1,000명 | ~10,000건 | ₩18,000 | 0원 | 0원(OFF) | **₩18,000** |
| 1만 사용자 | ~100,000건 | ₩200,000 | 0원 | 0원(OFF) | **₩200,000** |
| 5만 사용자(Year 2) | ~500,000건 | ₩1,000,000 | 0원 | 0원(OFF) | **₩1,000,000** |

기존 대비 **약 87% 비용 절감** (5만 사용자 기준 월 ₩6,750,000 절감).

---

## 5. 구현 명세

### 5.1 신규 어댑터 — `src/ocr/providers/paddle.py`

```python
"""PaddleOCR local OCR provider for cost-free Korean supplement label fallback."""

from __future__ import annotations

from dataclasses import dataclass

from src.config import Settings
from src.ocr.base import OCRAdapter, OCRError, OCRImageInput, OCRResult

PADDLE_OCR_PROVIDER = "paddle_ocr_local"


@dataclass
class PaddleOCRAdapter(OCRAdapter):
    """Local PaddleOCR adapter for cost-free Korean label extraction.

    Activation requires `enable_local_ocr=true` and the optional dependency
    extras installed via `pip install ".[ocr-local]"`.

    Attributes:
        settings: Runtime settings carrying the model tag and language.
    """

    settings: Settings

    async def extract_text(self, image: OCRImageInput) -> OCRResult:
        """Run PaddleOCR locally and return the joined text.

        Args:
            image: Validated image payload.

        Returns:
            OCRResult with provider="paddle_ocr_local".

        Raises:
            OCRError: When the PaddleOCR runtime fails or returns nothing.
        """
        if not self.settings.enable_local_ocr:
            raise OCRError("PaddleOCR is disabled by ENABLE_LOCAL_OCR=false.")
        try:
            from paddleocr import PaddleOCR  # local import — extras-gated
        except ImportError as exc:
            raise OCRError(
                "PaddleOCR is not installed. Run `pip install .[ocr-local]`."
            ) from exc
        engine = _resolve_engine(self.settings)
        lines = engine.ocr(image.image_bytes, cls=True)
        text, confidence = _flatten_lines(lines)
        return OCRResult(text=text, provider=PADDLE_OCR_PROVIDER, confidence=confidence)
```

세부 구현: `_resolve_engine` 은 `lru_cache` 로 모델 1회 로드, `_flatten_lines` 는 라인별 confidence 평균 산출 + 텍스트 줄바꿈 정규화.

### 5.2 의존성 — `backend/pyproject.toml`

기존 `[project.optional-dependencies]` 에 한 그룹 추가:

```toml
[project.optional-dependencies]
# ... 기존 vision / learning ...

# Phase 2: 로컬 OCR 폴백 (CLOVA 대체). pip install .[ocr-local]
ocr-local = [
    "paddleocr>=2.7",
    "paddlepaddle>=2.6",
]
```

CI 기본 빌드에서 제외 → MVP 일정 영향 없음. 운영 환경에서 `enable_local_ocr=true` 일 때만 설치.

### 5.3 Settings 확장 — `src/config.py`

`feature_*` 블록과 Phase 게이트 사이에 추가:

```python
# OCR 폴백 정책
enable_local_ocr: bool = Field(
    default=True,
    description="PaddleOCR 로컬 폴백 활성화. 학생 환경·정식 출시 모두 권장 ON.",
)
local_ocr_model: str = Field(default="ko_PP-OCRv4_mobile")
local_ocr_language: str = Field(default="korean")
local_ocr_confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)

enable_clova_ocr: bool = Field(
    default=False,
    description="CLOVA OCR 폴백 활성화. 비용 부담 큼. 발주처 명시 승인 시에만 ON.",
)
```

`validate_production_security` 에 가드 추가:

```python
(
    self.enable_clova_ocr and not self.clova_ocr_api_url,
    "ENABLE_CLOVA_OCR=true requires CLOVA_OCR_API_URL.",
),
(
    not self.enable_local_ocr and not self.enable_clova_ocr,
    "At least one OCR fallback (LOCAL or CLOVA) must be enabled in production.",
),
```

### 5.4 `.env.example` 보강

```env
# OCR 폴백 정책 (docs/32)
ENABLE_LOCAL_OCR=true              # PaddleOCR 로컬 폴백 (기본 ON, 무료)
LOCAL_OCR_MODEL=ko_PP-OCRv4_mobile
LOCAL_OCR_LANGUAGE=korean
LOCAL_OCR_CONFIDENCE_THRESHOLD=0.75

ENABLE_CLOVA_OCR=false             # CLOVA 비용 부담으로 기본 OFF (docs/32 §1.2)
```

### 5.5 라우팅 변경 — `src/services/supplement_image_analysis.py`

기존 단일 OCR adapter 호출을 폴백 체인으로 확장:

```python
async def _run_ocr_chain(
    settings: Settings,
    primary: OCRAdapter,
    local: OCRAdapter | None,
    clova: OCRAdapter | None,
    image: OCRImageInput,
) -> OCRResult:
    primary_result = await primary.extract_text(image)
    if primary_result.confidence and primary_result.confidence >= 0.85:
        return primary_result

    if local is not None and settings.enable_local_ocr:
        local_result = await local.extract_text(image)
        if local_result.confidence and local_result.confidence >= settings.local_ocr_confidence_threshold:
            return local_result

    if clova is not None and settings.enable_clova_ocr:
        return await clova.extract_text(image)

    return primary_result  # escalate to user review with primary's low-confidence output
```

호출처는 FastAPI Depends 로 `OCRAdapter` 3개를 주입받고 위 헬퍼에 위임한다.

### 5.6 테스트

신규 `tests/unit/ocr/providers/test_paddle.py`:

- `enable_local_ocr=False` 면 `OCRError` 즉시 발생
- 의존성 미설치 시 `OCRError("PaddleOCR is not installed...")` 발생
- 모킹된 `PaddleOCR.ocr` 출력에서 텍스트·신뢰도 정규화
- 한글·영문·숫자 혼합 라벨 샘플 5개에 대해 텍스트 추출 안정성
- `_flatten_lines` 가 빈 응답·이미지 디코드 실패 시 빈 결과(빈 텍스트, 신뢰도 0.0) 반환

라우팅 통합 테스트 (`tests/integration/test_ocr_fallback_chain.py`):

- 시나리오 A: primary 신뢰도 0.9 → primary 결과 반환
- 시나리오 B: primary 0.6 + local 0.85 → local 결과 반환
- 시나리오 C: primary 0.5 + local 0.6 + `enable_clova_ocr=False` → primary low-confidence escalation
- 시나리오 D: 모든 폴백 비활성 + production 환경 → ValueError(`At least one OCR fallback...`)

### 5.7 운영 매뉴얼 갱신

- [docs/Nutrition-docs/dev-guides/26-operations-manual.md](./dev-guides/26-operations-manual.md) 에 PaddleOCR 모델 캐시 디렉터리(`~/.paddleocr/`) 백업·갱신 SOP 추가
- [docs/Nutrition-docs/dev-guides/27-incident-runbook.md](./dev-guides/27-incident-runbook.md) 에 R009 "PaddleOCR runtime 충돌(numpy/torch 버전)" 런북 추가
- [docs/Nutrition-docs/06-tech-stack.md](./06-tech-stack.md) §2.3 extras 블록에 `ocr-local` 항목 명시
- [docs/Nutrition-docs/09-data-catalog.md](./09-data-catalog.md) §5.2 CLOVA 항목 옆에 "기본 비활성. 로컬 PaddleOCR 우선" 한 줄 추가

---

## 6. 컴플라이언스 평가

[docs/10 §6.3](./10-compliance-checklist.md), [docs/17 §7](./17-image-collection-consent-plan.md) 기준:

| 항목 | 클라우드 OCR(현행) | PaddleOCR 로컬(제안) |
| --- | --- | --- |
| 환자 이미지 외부 전송 | O(Google·CLOVA) | **X(로컬만)** |
| docs/17 §3 동의 매트릭스 | 1) 분석용 임시 처리 + 외부 송출 동의 필요 | **1) 분석용 임시 처리만** |
| 데이터 잔류 위험(외부 서버) | 클라우드 사업자 보관 정책 의존 | **X** |
| 의료기관 폐쇄망 운영 | 불가(인터넷 필요) | **가능** |
| 라이선스 | 상용 약관 준수 | **Apache 2.0** |
| 의료기기법 회피(docs/15 §3) | 동등 | 동등 |
| 비용 책임 | 발주처 | **0원** |

→ 컴플라이언스 측면에서도 PaddleOCR 이 명백히 우위. 도입 즉시 docs/17 §3 의 "분석용 임시 처리(자동 삭제, 동의 불요)" 카테고리만으로 충분.

---

## 7. 구현 일정

| 단계 | 작업 | 소요 | 의존성 |
| --- | --- | --- | --- |
| 1 | `paddle.py` 어댑터 + 단위 테스트 | 0.5일 | — |
| 2 | Settings + .env + validator 가드 | 0.25일 | 1 |
| 3 | 라우팅 체인 + 통합 테스트 | 0.5일 | 1, 2 |
| 4 | 운영 매뉴얼·런북·docs/06·09 갱신 | 0.25일 | 1~3 |
| 5 | 라벨 100장 PoC 정확도 비교(Google vs Paddle vs CLOVA) | 1일 | 1~3 |
| 6 | 발주처 리뷰 + 인수인계 게이트 | 0.5일 | 5 |
| **합계** | **약 3일** | | |

Phase 2(OCR MVP) 안에 충분히 처리 가능.

---

## 8. 발주처 리뷰 게이트(컴플라이언스 트랙)

본 변경은 docs/17 §8 의 발주처 리뷰 게이트와 별개이지만, 인수인계 시 다음 자료를 첨부한다:

1. **§1.2 비용 시나리오 재추산** — 5만 사용자 기준 월 ₩6,750,000 절감 근거
2. **§5.6 라벨 100장 PoC 결과** — Google·Paddle·CLOVA 정확도/응답시간/실패 사례
3. **§6 컴플라이언스 평가** — 환자 정보 외부 전송 0 명시
4. **라이선스 사본** — Apache 2.0 LICENSE 파일 (`backend/third_party_licenses/paddleocr.txt` 추가)

---

## 9. 잔여 리스크와 모니터링

| 리스크 | 모니터링 지표 | 임계값 | 대응 |
| --- | --- | --- | --- |
| PaddleOCR 정확도 저하(특정 영양제 라벨군) | 사용자 수정율 | > 30% | 모델 fine-tuning 또는 CLOVA 일시 활성화 |
| 응답시간 증가(GPU 미사용 환경) | P95 OCR latency | > 1,500ms | `local_ocr_model` 을 `mobile` 변종으로 다운그레이드 |
| 의존성 충돌(numpy/paddle/torch) | CI 빌드 실패율 | > 5% | 의존성 lock + 별도 Docker 이미지 분리 |
| Paddle 모델 라이선스 변경 | 분기 라이선스 점검 | 정책 변경 | EasyOCR 으로 대체 어댑터 추가 |

[docs/Nutrition-docs/dev-guides/26-operations-manual.md](./dev-guides/26-operations-manual.md) 의 월간 운영 사이클에 위 4개 지표 점검 항목을 추가한다.

---

## 10. 변경 이력

| 날짜 | 변경 내용 | 작성자 |
| --- | --- | --- |
| 2026-05-13 | 최초 작성. CLOVA 비용 분석 + PaddleOCR 도입 결정 + 구현 명세. | yeong-tech |

## 11. 관련 문서

- [docs/Nutrition-docs/06-tech-stack.md](./06-tech-stack.md) §2.3 — extras 블록
- [docs/Nutrition-docs/09-data-catalog.md](./09-data-catalog.md) §5.2 — CLOVA OCR 백업 정의
- [docs/Nutrition-docs/11-detailed-feature-implementation-plan.md](./11-detailed-feature-implementation-plan.md) §745 — OCR 정확도 리스크
- [docs/Nutrition-docs/17-image-collection-consent-plan.md](./17-image-collection-consent-plan.md) §3·§7 — 이미지 동의 매트릭스, 의료기기법 회피
- [docs/Nutrition-docs/25-ocr-text-supplement-analysis-plan.md](./25-ocr-text-supplement-analysis-plan.md) — OCR/텍스트 분석 흐름
- [docs/Nutrition-docs/27-ot-s2b-google-vision-ocr-review-plan.md](./27-ot-s2b-google-vision-ocr-review-plan.md) — Google Vision 폴백 라우팅
- [docs/Nutrition-docs/31-backend-feature-specifications.md](./31-backend-feature-specifications.md) §4 — OCR 모듈 현행 명세
