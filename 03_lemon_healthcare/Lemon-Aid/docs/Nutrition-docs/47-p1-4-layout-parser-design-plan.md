# 47. P1-4 Layout Parser 상세 설계 및 구현 플랜

작성일: 2026-05-16
범위: `01_HANDOFF.md` P1-4, OCR 좌표 기반 행/열 그룹핑, 섹션 앵커 기반 영양제 라벨 layout 구조화
상태: 상세 구현 완료, targeted unit/quality gate 통과

## 1. 현재 상태 요약

요구사항에는 `backend/src/parsing/layout_parser.py` 신규 구현으로 적혀 있지만, 현재 repo의 실제 backend source root는 `backend/Nutrition-backend/src`다. 따라서 구현 경로는 아래처럼 맞춘다.

- 주 구현: `backend/Nutrition-backend/src/parsing/layout_parser.py`
- schema: `backend/Nutrition-backend/src/models/schemas/label_layout.py`
- tests: `backend/Nutrition-backend/tests/unit/parsing/test_layout_parser.py`
- fixture helper 또는 mock factory: `backend/Nutrition-backend/tests/unit/parsing/conftest.py` 또는 test module 내부 helper

현재 P1-2/P1-3 구현으로 OCR provider는 이미 공통 layout DTO를 반환할 수 있다.

- `backend/Nutrition-backend/src/ocr/base.py`
  - `OCRResult.pages`
  - `OCRPage.blocks`
  - `OCRBlock.paragraphs`
  - `OCRParagraph.words`
  - `OCRWord.bounding_box`
- Google Vision adapter는 `fullTextAnnotation.pages[].blocks[].paragraphs[].words[]`를 `OCRResult.pages`로 정규화한다.
- CLOVA adapter는 `fields[]`와 optional `tables[]`를 synthetic `OCRResult.pages`로 정규화한다.

따라서 P1-4는 OCR 호출 기능이 아니라 **이미 추출된 단어 좌표를 순수 휴리스틱으로 행/열/섹션 구조로 재배열하는 deterministic parser**다.

## 2. 공식 문서 기반 전제

| 주제 | 확인 내용 | 설계 반영 |
| --- | --- | --- |
| Google Vision layout hierarchy | Google Cloud Vision `fullTextAnnotation`은 Page -> Block -> Paragraph -> Word -> Symbol 계층 구조와 bounding box/confidence를 제공한다. URL: <https://cloud.google.com/vision/docs/fulltext-annotations>, <https://cloud.google.com/vision/docs/reference/rest/v1p2beta1/images/annotate> | Layout Parser 입력은 provider raw JSON이 아니라 repo의 `OCRResult.pages`로 제한한다. provider별 raw shape 의존을 금지한다. |
| Google Vision dense OCR | Cloud Vision OCR 문서는 JSON에 page/block/paragraph/word/break 정보가 포함될 수 있음을 설명한다. URL: <https://cloud.google.com/vision/docs/ocr> | word box를 기본 단위로 쓰고, block/paragraph는 보조 grouping hint로만 사용한다. |
| CLOVA General OCR layout fields | CLOVA General OCR은 `fields[].inferText`, `inferConfidence`, `boundingPoly`, `lineBreak`, `tables[].cells[]`, `cellTextLines`, `cellWords` 계열 응답을 제공한다. URL: <https://api.ncloud-docs.com/docs/en/ai-application-service-ocr-ocr> | CLOVA도 `OCRResult.pages`에 이미 정규화된 word/table block을 제공한다고 보고, parser는 `block_type=TABLE`을 우선 table hint로 활용한다. |
| Pydantic model | Pydantic v2의 `BaseModel`은 annotated fields 기반 schema/validation 모델이고, `model_dump()`로 dict 직렬화가 가능하다. URL: <https://docs.pydantic.dev/latest/concepts/models/>, <https://docs.pydantic.dev/latest/concepts/serialization/> | 출력 DTO는 `LabelLayout` Pydantic model로 두고, API/DB/fixture report가 같은 schema를 재사용하게 한다. |

확인 한계:

- 이 단계에서는 “행/열 복원 정확도”를 주장하지 않는다. 정확도는 좌표 fixture와 실제 라벨 fixture 평가 리포트가 생긴 뒤에만 말할 수 있다.
- Google Vision과 CLOVA의 좌표 원점, 회전 보정, normalized vertex 혼재는 provider별 smoke/fixture 전까지 완전한 동일성을 가정하지 않는다. parser는 입력 좌표를 그대로 사용하고, out-of-range/invalid box는 warning으로 남긴다.

## 3. 브레인스토밍 정리

### 3.1 왜 Layout Parser가 필요한가

현재 LLM parser는 OCR text를 줄 단위 문자열로 받아 `ingredient_candidates`를 뽑는다. 하지만 영양제 라벨은 아래 형태가 많다.

- 표 형태: `영양성분 | 함량 | %영양성분기준치`
- 섹션 형태: `섭취방법`, `섭취 시 주의사항`, `원재료명`
- 멀티컬럼 형태: 왼쪽은 기능정보, 오른쪽은 섭취량/주의사항
- OCR 문자열 순서가 시각적 행/열 순서와 다를 수 있음

Layout Parser는 LLM 앞단에서 “시각적 셀 배열”을 만들어 다음 작업의 근거를 강화한다. 다만 P1-4에서는 구조 추정까지만 하고, 성분량/복용량/의학적 판단은 하지 않는다.

### 3.2 선택지 비교

| 선택지 | 장점 | 리스크 | 결정 |
| --- | --- | --- | --- |
| A. OCR text line만 regex로 파싱 | 빠르고 단순 | 열 위치가 사라져 표 복원이 불가능 | 제외 |
| B. provider의 block/paragraph만 신뢰 | 구현 쉬움 | Google/CLOVA/Paddle 간 block 의미가 다름 | 보조 hint로만 사용 |
| C. word box 기반 y-band/x-band 휴리스틱 | provider 중립, fixture test 가능 | 회전/곡면/원근왜곡에는 취약 | 채택 |
| D. LayoutLM/Donut 같은 모델 도입 | 복잡한 문서 layout에 강함 | 학습/추론/개인정보/운영비용 증가 | P1-4 범위 제외 |
| E. LLM에게 이미지/텍스트로 table 복원 | 빠른 prototype | hallucination 및 재현성 리스크 | 제외 |

결론: P1-4는 **모델 없는 word box 휴리스틱**으로 시작한다.

## 4. 설계 결정

### 4.1 입력 계약

함수 시그니처:

```python
def parse_label_layout(
    ocr_result: OCRResult,
    *,
    options: LayoutParserOptions | None = None,
) -> LabelLayout:
    ...
```

입력 정책:

- `OCRResult.pages`가 없으면 `LabelLayout(sections=[], warnings=["layout_unavailable"])`로 반환한다.
- `OCRWord.bounding_box`가 없는 word는 row/column 복원에서 제외하고 warning count로 남긴다.
- word text가 blank이면 제외한다.
- provider별 raw JSON은 받지 않는다.
- 이미지 bytes, API key, raw provider response는 받거나 저장하지 않는다.

### 4.2 출력 Pydantic schema

파일: `backend/Nutrition-backend/src/models/schemas/label_layout.py`

권장 model:

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SectionType = Literal[
    "daily_intake",
    "nutrition_function_info",
    "intake_method",
    "precautions",
    "ingredients",
    "functionality",
    "unknown",
]


class LabelBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(ge=0)
    left: float
    top: float
    right: float
    bottom: float


class LabelCell(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    row_index: int = Field(ge=0)
    column_index: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=500)
    bounding_box: LabelBox
    confidence: float | None = Field(default=None, ge=0, le=1)
    word_count: int = Field(ge=1)


class LabelSection(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    section_type: SectionType
    anchor_text: str | None = Field(default=None, max_length=120)
    anchor_box: LabelBox | None = None
    rows: list[list[LabelCell]] = Field(default_factory=list)


class LabelLayout(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: str = Field(min_length=1, max_length=64)
    page_count: int = Field(ge=0)
    sections: list[LabelSection] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list, max_length=50)
```

출력 원칙:

- `sections[].rows[row][column]` 배열이 “섹션별 셀 배열”의 표준 출력이다.
- rows/cells는 모두 시각적 순서, 즉 `top -> left` 순서다.
- `unknown` section은 앵커가 없지만 행/열 복원은 가능한 잔여 영역에만 사용한다.
- confidence는 cell 내부 word confidence 평균이다. 없으면 `None`; 임의 confidence를 만들지 않는다.
- raw OCR text 전체를 다시 저장하지 않는다. cell text는 layout 구조의 최소 필요한 파생 결과로 취급한다.

### 4.3 앵커 키워드

기본 keyword map:

```python
SECTION_KEYWORDS = {
    "daily_intake": ("일일섭취량", "1일섭취량", "일일 섭취량", "섭취량"),
    "nutrition_function_info": ("영양·기능정보", "영양 기능정보", "영양정보", "기능정보"),
    "intake_method": ("섭취방법", "섭취 방법", "복용방법", "복용 방법"),
    "precautions": ("섭취 시 주의사항", "섭취시 주의사항", "주의사항", "주의"),
    "ingredients": ("원재료명", "원료명", "원재료"),
    "functionality": ("기능성", "기능성 내용", "기능성분"),
}
```

정규화:

- 공백 제거 비교: `섭취 시 주의사항` == `섭취시주의사항`
- punctuation 일부 제거: `영양·기능정보` == `영양기능정보`
- 대소문자는 `casefold()` 처리
- fuzzy matching은 P1-4 기본값에서 제외한다. 오탐을 줄이기 위해 exact normalized contains부터 시작한다.

### 4.4 좌표 정규화

내부 working DTO:

```python
@dataclass(frozen=True)
class LayoutWord:
    page_index: int
    text: str
    left: float
    top: float
    right: float
    bottom: float
    center_x: float
    center_y: float
    width: float
    height: float
    confidence: float | None
```

box 계산:

- `left = min(vertex.x)`
- `right = max(vertex.x)`
- `top = min(vertex.y)`
- `bottom = max(vertex.y)`
- `width = right - left`
- `height = bottom - top`

invalid word 제외 조건:

- vertex 2개 미만
- `right <= left` 또는 `bottom <= top`
- text blank

좌표 스케일:

- Google Vision은 대체로 pixel coordinate다.
- CLOVA는 현재 adapter가 provider vertex 값을 그대로 보존한다.
- normalized coordinate가 섞인 경우에도 parser는 상대 band grouping만 사용하므로 동작 가능하지만, page width/height와 scale mismatch가 감지되면 warning을 남긴다.

### 4.5 y-band row grouping

목표: 같은 시각적 행에 있는 words를 하나의 row로 묶는다.

기본 옵션:

```python
class LayoutParserOptions(BaseModel):
    row_y_tolerance_ratio: float = Field(default=0.60, ge=0.1, le=2.0)
    column_gap_ratio: float = Field(default=1.80, ge=0.5, le=8.0)
    min_anchor_overlap_ratio: float = Field(default=0.30, ge=0.0, le=1.0)
    max_section_gap_rows: int = Field(default=80, ge=1, le=500)
```

row grouping algorithm:

1. page별 words를 `(center_y, left)`로 정렬한다.
2. median word height를 계산한다.
3. row tolerance = `median_height * row_y_tolerance_ratio`.
4. 각 word를 기존 row 중 `abs(word.center_y - row.center_y) <= tolerance`인 row에 넣는다.
5. 해당 row의 center_y는 row words의 weighted/average center_y로 갱신한다.
6. row 내부 words는 `left` 기준 정렬한다.
7. row bbox와 confidence 평균을 계산한다.

실패 방지:

- median height가 없으면 default tolerance를 8 px equivalent로 둔다.
- 기울어진 라벨은 완전히 해결하지 않는다. 같은 행인데 y 차이가 큰 fixture가 나오면 P1-5에서 deskew/ROI preprocessing으로 넘긴다.

### 4.6 x-band column grouping

목표: 한 row 안에서 시각적으로 분리된 셀을 만든다.

cell split algorithm:

1. row words를 `left` 기준 정렬한다.
2. consecutive word gap = `next.left - current.right`.
3. row median word width 또는 median character width를 계산한다.
4. gap threshold = `median_word_width * column_gap_ratio`.
5. gap이 threshold보다 크면 새 cell 시작.
6. cell text는 내부 words를 space join한다.

column index assignment:

- section 내 모든 cell의 `left/right/center_x`를 모아 x-band를 만든다.
- 첫 row의 cell 개수만 신뢰하지 않는다. header가 single-cell일 수 있기 때문이다.
- x-band merge 기준: center_x 차이가 median cell width의 0.6배 이하이면 같은 column.
- column band는 left 순으로 정렬해서 index를 부여한다.
- row마다 cell을 가장 가까운 column band에 할당한다.

주의:

- P1-4는 rowspan/colspan을 명시적으로 계산하지 않는다.
- header처럼 넓은 single cell은 `column_index=0`으로 두고, 후속 parser가 anchor/header로 해석하게 한다.

### 4.7 섹션 분할

섹션 anchor 탐색:

1. row text normalized value에서 keyword map을 검색한다.
2. match된 row를 anchor row로 기록한다.
3. anchor row의 첫 matching cell 또는 row bbox를 `anchor_box`로 기록한다.
4. 다음 anchor row 직전까지를 현재 section 영역으로 본다.

섹션 우선순위:

1. 위에서 아래로 anchor 순서 유지
2. 같은 row에 여러 anchor가 있으면 더 긴 keyword match 우선
3. 같은 keyword가 반복되면 두 번째부터는 같은 section의 continuation 후보로 처리하되, y-gap이 크면 별도 section으로 허용

잔여 row 처리:

- 첫 anchor 위의 rows는 `unknown`으로 둘 수 있지만, 기본은 버리지 않고 `unknown` section에 넣는다.
- anchor가 하나도 없으면 모든 rows를 하나의 `unknown` section으로 반환한다.
- 빈 OCR layout이면 `sections=[]`, warning만 반환한다.

### 4.8 LLM parser와의 관계

P1-4에서는 기존 `parse_supplement_analysis_ocr_text()` 호출 경로를 바꾸지 않는다.

권장 후속 통합:

1. OCR 결과 수신
2. `parse_label_layout(ocr_result)` 실행
3. 기존 raw normalized OCR text는 지금처럼 hash만 저장하고 parser input으로 사용
4. layout 결과는 preview snapshot의 `parser_metadata.layout_summary` 또는 별도 field로 sanitized 저장 검토
5. LLM prompt에는 P1-5 이후 `layout sections`를 선택적으로 넣는다

P1-4 구현만으로는 user-facing 기능을 바꾸지 않는다. 목표는 deterministic layout artifact와 테스트 기반을 먼저 확보하는 것이다.

## 5. 구현 상세 플랜

### R1. schema 추가

파일:

- `backend/Nutrition-backend/src/models/schemas/label_layout.py`
- `backend/Nutrition-backend/src/models/schemas/__init__.py`는 현재 export 정책을 확인한 뒤 필요할 때만 수정

작업:

- `LabelBox`
- `LabelCell`
- `LabelSection`
- `LabelLayout`
- `LayoutParserOptions`
- `SectionType`

완료 기준:

- Pydantic validation으로 empty text, negative row/column index, invalid confidence를 차단한다.
- schema는 provider raw response와 secret/image bytes를 포함하지 않는다.

### R2. parsing package 생성

파일:

- `backend/Nutrition-backend/src/parsing/__init__.py`
- `backend/Nutrition-backend/src/parsing/layout_parser.py`

작업:

- public function `parse_label_layout()`
- internal dataclass `LayoutWord`, `LayoutRow`, `LayoutCellCandidate`
- `flatten_ocr_words()`
- `group_words_into_rows()`
- `split_row_into_cells()`
- `assign_columns()`
- `detect_section_anchors()`
- `build_label_layout()`

완료 기준:

- OCR provider별 import 없이 `OCRResult`만 의존한다.
- no network, no image bytes, no LLM.

### R3. row/column grouping 구현

파일:

- `backend/Nutrition-backend/src/parsing/layout_parser.py`

작업:

- bounding box 계산
- y-band row grouping
- x-gap cell splitting
- section-local x-band column assignment
- warnings 수집

완료 기준:

- mock OCR fixture에서 2열 nutrition table을 row/cell 순서대로 복원한다.
- 약간의 y jitter가 있어도 같은 행으로 묶는다.
- 큰 x gap은 새 cell로 분리한다.

### R4. keyword anchor sectioning 구현

파일:

- `backend/Nutrition-backend/src/parsing/layout_parser.py`

작업:

- keyword normalization
- anchor row detection
- section slicing
- `unknown` fallback

완료 기준:

- `"영양·기능정보"` 아래 table rows가 `nutrition_function_info` section으로 들어간다.
- `"섭취 시 주의사항"`과 `"섭취시 주의사항"`을 같은 anchor로 인식한다.
- anchor가 없으면 `unknown` section으로 전체 rows를 보존한다.

### R5. unit tests 추가

파일:

- `backend/Nutrition-backend/tests/unit/parsing/test_layout_parser.py`

테스트 fixture:

1. Google-like OCRResult
   - page -> block -> paragraph -> words
   - 3행 x 3열 영양성분표
   - y jitter 포함
2. CLOVA-like synthetic OCRResult
   - `block_type="TABLE"` 포함
   - `원재료명`, `섭취방법`, `섭취 시 주의사항` anchor 포함
3. missing bbox OCRResult
   - warning 및 empty/unknown behavior 확인

핵심 테스트:

- row grouping: 같은 y-band words가 같은 row
- column grouping: x gap 기준 cell 분리
- section anchor: keyword별 section type 분류
- unknown fallback: anchor 없는 rows 보존
- confidence: cell confidence 평균, 없으면 None
- validation: `LabelLayout.model_dump()`가 JSON-friendly shape

### R6. docs/dev guide 보정

파일:

- `docs/Nutrition-docs/33-three-tier-ocr-pipeline-implementation-guide.md`
- `docs/Nutrition-docs/40-ocr-3-tier-expansion-design-plan.md`
- `docs/Nutrition-docs/47-p1-4-layout-parser-design-plan.md`

작업:

- Layout Parser는 accuracy claim이 아니라 deterministic preprocessing이라고 명시
- fixture 평가 전 정확도/개선율 주장 금지
- P1-5 이후 LLM parser prompt 통합 후보로 분리

## 6. 테스트 계획

### Unit

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/python -m pytest Nutrition-backend/tests/unit/parsing/test_layout_parser.py -q --no-cov
```

테스트 matrix:

| 케이스 | 기대 결과 |
| --- | --- |
| 3행 x 3열 mock table | `sections[0].rows`가 3개 row, 각 row 3개 cell |
| y jitter 4 px | 같은 row 유지 |
| 큰 x gap | cell 분리 |
| `영양·기능정보` anchor | `section_type="nutrition_function_info"` |
| `섭취시 주의사항` anchor | `section_type="precautions"` |
| bbox 없는 words | warning 포함, 해당 words 제외 |
| anchor 없음 | `unknown` section |
| empty `OCRResult.pages` | `sections=[]`, `layout_unavailable` warning |

### Quality gate

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/python -m ruff check Nutrition-backend/src/parsing Nutrition-backend/src/models/schemas/label_layout.py Nutrition-backend/tests/unit/parsing
.venv/bin/python -m black --check Nutrition-backend/src/parsing Nutrition-backend/src/models/schemas/label_layout.py Nutrition-backend/tests/unit/parsing
.venv/bin/python -m pytest Nutrition-backend/tests/unit/parsing/test_layout_parser.py Nutrition-backend/tests/unit/ocr -q --no-cov
git diff --check
```

### Regression scope

P1-4는 OCR provider 호출과 DB write path를 바꾸지 않으므로 전체 API regression은 필수는 아니다. 단, 후속 통합에서 `supplement_image_analysis`가 layout result를 snapshot에 넣는 순간 아래를 추가한다.

```bash
.venv/bin/python -m pytest Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py -q --no-cov
```

## 7. 리스크와 대응

| 리스크 | 영향 | 대응 |
| --- | --- | --- |
| 회전/기울어진 이미지 | y-band row grouping 실패 | P1-4에서는 warning, P1-5에서 deskew/ROI preprocessing 검토 |
| 원근 왜곡/곡면 병 | row/column box가 휘어짐 | fixture report에서 실패 케이스 수집 |
| provider별 좌표 scale 차이 | threshold 튜닝 실패 | median height/width 기반 relative threshold 사용 |
| anchor OCR 오탈자 | section split 누락 | exact normalized match부터 시작, fixture 기반 synonym만 추가 |
| 멀티컬럼 문서 | row 순서가 좌우 column을 섞을 수 있음 | page-wide x-band cluster를 후속 개선 후보로 둠 |
| header colspan | column index가 단순화됨 | P1-4는 colspan 계산 제외, 후속 table semantics에서 처리 |

## 8. 완료 기준

- [x] `LabelLayout` Pydantic schema가 추가된다.
- [x] `parse_label_layout(OCRResult)`가 no-network/no-LLM으로 동작한다.
- [x] y-band row grouping과 x-gap cell splitting이 구현된다.
- [x] 지정 keyword anchor 6종을 section으로 분류한다.
- [x] 좌표 fixture test에서 행/열 복원이 통과한다.
- [x] bbox missing/empty layout degraded behavior가 warning으로 고정된다.
- [x] 기존 OCR provider unit tests가 계속 통과한다.
- [x] 정확도/개선율 주장을 추가하지 않는다.

### 8.1 구현 결과

추가 파일:

- `backend/Nutrition-backend/src/models/schemas/label_layout.py`
- `backend/Nutrition-backend/src/parsing/__init__.py`
- `backend/Nutrition-backend/src/parsing/layout_parser.py`
- `backend/Nutrition-backend/tests/unit/parsing/test_layout_parser.py`

구현 내용:

- `LabelBox`, `LabelCell`, `LabelSection`, `LabelLayout`, `LayoutParserOptions` Pydantic schema를 추가했다.
- `parse_label_layout()`가 `OCRResult.pages`만 입력으로 받아 OCR word bounding box를 flatten한다.
- bbox가 없거나 invalid인 word는 제외하고 warning code로 남긴다.
- y-band row grouping은 median word height 기반 tolerance를 사용한다.
- x-gap cell splitting은 median word width 기반 threshold를 사용한다.
- `일일섭취량`, `영양·기능정보`, `섭취방법`, `섭취 시 주의사항`, `원재료명`, `기능성` anchor를 normalized exact contains 방식으로 분류한다.
- anchor가 없으면 `unknown` section으로 row/cell을 보존한다.
- empty layout은 `layout_unavailable`, 좌표 word 없음은 `layout_words_unavailable` warning으로 고정한다.

검증 결과:

```bash
cd /Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend
.venv/bin/python -m ruff check Nutrition-backend/src/models/schemas/label_layout.py Nutrition-backend/src/parsing Nutrition-backend/tests/unit/parsing
# All checks passed

.venv/bin/python -m pytest Nutrition-backend/tests/unit/parsing/test_layout_parser.py -q --no-cov
# 5 passed
```

## 9. 권장 구현 순서

1. `models/schemas/label_layout.py`에 Pydantic 출력 모델을 먼저 추가한다.
2. `src/parsing` package와 `parse_label_layout()` 빈 골격을 만든다.
3. OCRResult -> LayoutWord flattening과 invalid bbox warning을 구현한다.
4. y-band row grouping을 구현하고 단일 행/다중 행 테스트를 붙인다.
5. x-gap cell splitting과 section-local column assignment를 구현한다.
6. keyword anchor sectioning을 구현한다.
7. Google-like/CLOVA-like mock OCRResult fixture 테스트를 추가한다.
8. docs/33, docs/40에 Layout Parser 구현 상태를 반영한다.
9. ruff/black/targeted pytest를 통과시킨다.

## 10. 권장 커밋 단위

1. `docs(ocr): design coordinate-based label layout parser`
   - Why: OCR provider 출력과 LLM parser 사이의 deterministic layout 계약을 먼저 고정한다.
2. `feat(parsing): add label layout schema`
   - Why: 행/열/섹션 결과를 API와 테스트가 공유할 수 있는 검증 가능한 DTO로 만든다.
3. `feat(parsing): group OCR words into label sections`
   - Why: OCR 좌표를 행/열/섹션 구조로 복원해 후속 parser의 근거를 강화한다.
4. `test(parsing): cover coordinate fixtures for layout parser`
   - Why: 모델 없는 휴리스틱의 동작 범위를 fixture로 고정하고 정확도 주장을 방지한다.
