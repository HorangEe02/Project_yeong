# 영양제/보충제 라벨 이미지 실패 상황 브레인스토밍 및 기술 대응안

- 작성일: 2026-05-17
- 작성 위치: `yeong-Lemon-Aid/Brand-New-update`
- 목적: 사용자가 스마트폰으로 영양제/보충제 사진을 촬영할 때 발생할 수 있는 실패 상황을 사전에 정리하고, 각 상황별 탐지 신호와 기술 대응안을 설계한다.
- 범위: 이미지 입력, 모바일 UX, OCR 전처리, 바코드/제품 식별, 레이아웃 파싱, 사용자 확인 흐름.
- 비범위: OCR/검출 모델 성능 수치 주장, 의료적 복용량 변경 판단, 실제 제품 효능 검증.

## 1. 현재 구현 맥락 기준

현재 Lemon Aid의 영양제/보충제 이미지 분석 흐름은 다음 방향을 전제로 한다.

1. 이미지는 원본 그대로 자동 신뢰하지 않고, OCR/레이아웃/파서 결과를 `사용자 확인 전 후보값`으로 취급한다.
2. OCR 결과는 provider raw JSON을 직접 소비하기보다 표준화된 OCR DTO, 레이아웃 파서, sectioned parser input을 거쳐 후속 파서로 넘기는 방향이 맞다.
3. 성분명, 함유량, 단위, 섭취 기준, 주의 문구는 근거 박스 또는 원문 evidence와 함께 제시해야 한다.
4. 저신뢰 결과는 기본 선택하지 않고 사용자 검토 상태로 둔다.
5. 처방전, 검사표, 의약품 라벨 등 규제 민감 문서는 intake-only로 취급하고, 직접적인 복용량 변경 안내는 차단한다.

따라서 이번 문서의 핵심은 "어떤 이미지 상황에서 OCR/파서가 틀릴 수 있는가"를 먼저 분해한 뒤, 자동 추론을 늘리기보다 `탐지 -> 사용자 보정 -> 제한된 파싱 -> 근거 기반 확인`으로 안전하게 처리하는 것이다.

## 2. 공식 문서로 확인한 기술 근거

아래 문서는 실제 구현 단계에서 API 파라미터와 입력/출력 형태를 다시 확인해야 하는 1차 근거다.

- Google Cloud Vision OCR: `TEXT_DETECTION`과 `DOCUMENT_TEXT_DETECTION`을 구분하며, `DOCUMENT_TEXT_DETECTION`은 page, block, paragraph, word 등 dense text 구조를 제공한다.  
  https://cloud.google.com/vision/docs/ocr
- Google Cloud Vision Feature reference: OCR feature 타입 확인용.  
  https://cloud.google.com/vision/docs/reference/rest/v1/Feature
- FastAPI file upload: 이미지 업로드 endpoint는 `UploadFile`/multipart 처리 기준을 따른다.  
  https://fastapi.tiangolo.com/tutorial/request-files/
- Dart `http.MultipartRequest`: Flutter 클라이언트에서 multipart 업로드를 구현할 때 참고한다.  
  https://pub.dev/documentation/http/latest/http/MultipartRequest-class.html
- Flutter `image_picker`: Android에서 Activity가 종료되어 이미지 선택 결과가 유실될 수 있으므로 `retrieveLostData()` 처리가 필요하다.  
  https://pub.dev/packages/image_picker
- Google ML Kit Barcode Scanning: 모바일 바코드 스캔, 여러 barcode 후보 반환, focus/resolution guideline, auto-zoom 옵션 검토에 사용한다.  
  https://developers.google.com/ml-kit/vision/barcode-scanning/android
- OpenCV thresholding: 조명 불균일, 노이즈 이미지의 이진화/적응형 threshold 후보 검토에 사용한다.  
  https://docs.opencv.org/4.x/d7/d4d/tutorial_py_thresholding.html
- OpenCV geometric transformations: 회전, perspective transform, resize, warp 처리를 검토할 때 사용한다.  
  https://docs.opencv.org/4.x/da/d6e/tutorial_py_geometric_transformations.html

확인 한계:

- 스마트폰 이미지의 blur, glare, crop, 라벨 곡률에 대해 모든 제품군에 통용되는 공식 권장 임계값은 확인하지 못했다.
- 따라서 blur score, OCR confidence cutoff, 최소 글자 높이 같은 수치 기준은 공식값처럼 고정하면 안 되고, 우리 fixture와 실제 사용자 이미지로 보정해야 한다.
- 이 문서는 성능 수치를 만들지 않는다. 모든 정확도/재현율은 추후 평가 데이터셋을 만든 뒤 별도 측정해야 한다.

## 3. 공통 처리 원칙

1. 한 이미지에 여러 제품이 있으면 성분을 합치지 않는다. 먼저 제품 단위 ROI를 분리하거나 사용자에게 하나를 선택하게 한다.
2. 표지 라벨만 보이면 제품명/브랜드 후보까지만 처리하고, 성분표 분석은 추가 촬영 요청으로 전환한다.
3. OCR이 읽지 못한 성분과 함유량은 LLM이 채우지 않는다. 누락은 누락으로 표시한다.
4. 바코드가 있더라도 최종 제품 식별은 사용자 확인을 거친다. 바코드 DB와 라벨 OCR이 충돌하면 자동 확정하지 않는다.
5. 원본 이미지는 장기 보관하지 않는 방향을 유지한다. 필요한 경우 해시, crop 좌표, quality report, evidence text만 제한적으로 저장한다.
6. 규제 민감 문서 또는 의약품으로 보이면 보충제 분석 플로우에서 분리하고, 의료 조언이 아니라 intake/확인 요청으로 제한한다.
7. 자동 수정보다 재촬영 안내가 안전한 경우가 많다. 특히 흐림, 잘림, 반사, 작은 글씨는 전처리보다 retake UX가 우선이다.

## 4. 문제 상황별 브레인스토밍 및 대응안

### 4.1 한 이미지에 여러 영양제/보충제가 함께 찍힌 경우

발생 양상:

- 사용자가 식탁 위 여러 병을 한 번에 촬영한다.
- 약통, 박스, 파우치가 겹쳐 있고 일부 성분표만 보인다.
- 제품 A의 표지명과 제품 B의 성분표가 같은 사진 안에 함께 존재한다.

위험:

- OCR 텍스트 클러스터가 섞여 제품 A의 이름에 제품 B의 함유량을 붙일 수 있다.
- 파서가 여러 제품의 성분을 하나의 제품 성분표로 병합할 수 있다.
- 같은 성분명이 제품별로 중복되어 dosage 계산과 중복 섭취 위험 평가가 왜곡된다.

탐지 신호:

- 바코드 후보가 2개 이상 감지된다.
- 텍스트 클러스터가 이미지 좌우 또는 상하에 명확히 분리된다.
- `Supplement Facts`, `영양·기능정보`, `섭취량`, `원재료명` 같은 section anchor가 여러 영역에서 반복된다.
- OCR bounding box의 x/y 분포가 둘 이상의 독립 label region을 만든다.

기술 대응:

- 모바일에서 먼저 "한 제품만 화면에 크게 맞춰 촬영" 가이드를 띄우되, 실패 시 자동 차단하지 말고 제품 영역 선택 UI를 제공한다.
- 서버에서 `detected_product_regions[]`를 생성하고, 사용자가 선택한 ROI만 OCR/파서에 넘긴다.
- batch 분석을 지원하더라도 각 제품별 `analysis_id`를 분리하고, 성분/함유량은 절대 자동 병합하지 않는다.
- 여러 제품을 동시에 분석하려면 `multi_image_group_id` 또는 `batch_id`로 묶되, 각 제품은 독립 snapshot으로 저장한다.

검증 데이터:

- 2개 병이 나란히 있는 이미지
- 3개 제품이 겹친 이미지
- 표지는 A, 성분표는 B가 더 잘 보이는 이미지
- 같은 브랜드의 용량만 다른 제품 2개가 같이 찍힌 이미지

### 4.2 표지 라벨만 보이고 성분표가 없는 경우

발생 양상:

- 제품 전면의 브랜드명, 제품명, 마케팅 문구만 보인다.
- `고함량`, `면역`, `피로`, `관절` 같은 문구는 있지만 실제 함유량 표가 없다.
- 건강기능식품 마크 또는 주요 기능성 원료명만 보이고 상세 성분표가 없다.

위험:

- 제품명만으로 성분과 함유량을 추정하면 환각 위험이 크다.
- 같은 제품군 안에서도 함량, 정제 수, 리뉴얼 버전이 다를 수 있다.
- 사용자가 성분 분석이 완료된 것으로 오해할 수 있다.

탐지 신호:

- 제품명/브랜드 후보는 있으나 nutrition table anchor가 없다.
- 단위 패턴 `mg`, `ug`, `mcg`, `IU`, `%`, `kcal` 등이 거의 없다.
- 표 형태 row/column 구조가 감지되지 않는다.

기술 대응:

- 분석 상태를 `needs_additional_label_image`로 전환한다.
- 제품명/브랜드/바코드 후보만 "제품 식별 후보"로 저장하고, 성분 후보는 비워 둔다.
- UX에서 "성분표 또는 영양·기능정보 면을 추가 촬영해 주세요"를 명확히 요청한다.
- 바코드 조회가 성공하더라도 사용자에게 "라벨 성분표와 일치하는지 확인" 단계를 요구한다.

검증 데이터:

- 정면 표지 라벨만 있는 이미지
- 박스 전면만 보이는 이미지
- 광고 문구가 성분명처럼 보이는 이미지

### 4.3 흐림, 초점 실패, 손떨림

발생 양상:

- 작은 글씨가 뭉개져 OCR이 단위를 잘못 읽는다.
- `100 mg`가 `1000 mg`, `10 mg`, `l00 mg`처럼 잘못 읽힌다.
- 세로 획이 많은 한글 성분명이 서로 붙어 보인다.

위험:

- 성분명보다 함량 오류가 더 치명적이다.
- 단위가 잘못 읽히면 위험도 평가가 크게 틀어진다.
- LLM 후처리가 문맥상 그럴듯한 값을 생성할 수 있다.

탐지 신호:

- OCR confidence가 낮거나 word bounding box가 비정상적으로 적다.
- 같은 row 안에서 숫자와 단위가 분리되지 않는다.
- 작은 텍스트 영역의 edge density 또는 sharpness score가 낮다.
- `mg`, `mcg`, `IU`, `%` 같은 단위 토큰이 깨져 있다.

기술 대응:

- 모바일 preview 단계에서 흐림 의심 시 재촬영을 권장한다.
- 서버에서 `ImageQualityReport.blur_level`과 `retake_reasons=["blurred_text"]`를 생성한다.
- OCR 결과가 있더라도 함량/단위 필드는 `low_confidence`로 표시하고 기본 선택 해제한다.
- 흐림 보정 필터를 적용하더라도 원문 evidence와 보정본 OCR 결과를 구분한다.
- 임계값은 공식값이 아니라 fixture 기반으로 정한다.

검증 데이터:

- 일부러 초점을 빗나가게 한 성분표
- 모션 블러 이미지
- 원본은 보이지만 작은 글씨만 흐린 이미지

### 4.4 반사, 번쩍임, 비닐/유광 라벨

발생 양상:

- 플래시 또는 조명 반사가 성분표 일부를 가린다.
- 병 표면의 비닐 포장 때문에 특정 column이 하얗게 날아간다.
- 검은색 병, 은색 라벨, 금박 라벨에서 글자 대비가 낮다.

위험:

- 특정 성분 row가 통째로 누락된다.
- `% 영양성분기준치` column만 사라져 파서가 단위를 오인할 수 있다.
- 반사 영역의 글자를 LLM이 주변 패턴으로 보완하려 할 수 있다.

탐지 신호:

- 과도하게 밝은 saturation 영역이 text box와 겹친다.
- OCR word가 table 중간에서 끊기고 좌우 row 연결이 불안정하다.
- 같은 table의 row 수가 비정상적으로 적다.

기술 대응:

- 모바일 UX에서 플래시 끄기, 병을 살짝 기울이기, 확산광 사용을 안내한다.
- 서버는 `retake_reasons=["glare_or_reflection"]`을 반환한다.
- 반사 영역이 핵심 row를 가리면 자동 추론하지 않고 "해당 영역 재촬영"을 요청한다.
- 전처리로 highlight mask나 contrast enhancement를 검토할 수 있으나, critical field가 가려진 경우 retake가 우선이다.

검증 데이터:

- 흰 반사가 table 중앙을 가린 이미지
- 유광 파우치 이미지
- 어두운 병에 작은 흰 글씨가 있는 이미지

### 4.5 원통형 병 라벨, 곡률, perspective 왜곡

발생 양상:

- 원통형 병의 좌우 글자가 휘어져 있다.
- 성분표가 사다리꼴로 찍히거나, 라벨이 기울어진다.
- table column이 실제로는 평행하지만 이미지에서는 휘거나 좁아진다.

위험:

- y-band row grouping이 틀어져 서로 다른 row가 합쳐질 수 있다.
- x-gap 기반 cell splitting이 column을 잘못 나눌 수 있다.
- 함량과 단위가 옆 row의 성분명에 붙을 수 있다.

탐지 신호:

- text baseline angle이 영역별로 다르다.
- bounding box가 table 전체에서 일정한 행/열 격자를 만들지 못한다.
- table corner가 이미지 안에서 사다리꼴 또는 곡면 형태로 나타난다.

기술 대응:

- 모바일에서 crop/rotate 도구를 제공하고, 가능한 경우 라벨 면을 정면으로 맞추도록 안내한다.
- 사각 성분표가 보이면 OpenCV `getPerspectiveTransform`/`warpPerspective` 계열 처리를 후보로 검토한다.
- 곡률이 큰 원통 라벨은 자동 보정 실패 가능성이 높으므로, 추가 촬영 또는 수동 확인 흐름을 우선한다.
- 레이아웃 파서는 보정 전/후 좌표계를 명확히 분리해야 한다.

검증 데이터:

- 원통 병을 정면/측면/45도에서 찍은 이미지
- 테이블이 사다리꼴로 왜곡된 이미지
- 라벨이 일부만 말려 있는 이미지

### 4.6 조명 부족, 노이즈, JPEG 압축

발생 양상:

- 어두운 실내에서 촬영해 배경 노이즈가 많다.
- 메신저로 전달된 이미지가 압축되어 작은 글씨가 깨진다.
- 저가형 스마트폰 또는 오래된 기기에서 OCR 가능한 해상도가 부족하다.

위험:

- 한글 획이 깨져 성분명이 다른 단어로 인식된다.
- 숫자와 소수점이 사라진다.
- 같은 파일이라도 전처리 결과에 따라 OCR 결과가 크게 달라질 수 있다.

탐지 신호:

- 평균 밝기 또는 local contrast가 낮다.
- OCR word density가 낮고, 단위 패턴이 희소하다.
- 이미지 EXIF/해상도 또는 파일 크기 대비 text box 크기가 작다.

기술 대응:

- 모바일에서 촬영 직후 "밝은 곳에서 다시 촬영" 안내를 제공한다.
- 서버에서 adaptive thresholding, denoise, contrast enhancement를 후보 전처리로 평가한다.
- 전처리별 OCR 결과를 무조건 합치지 말고, 가장 신뢰도 높은 결과와 evidence를 보존한다.
- 압축 이미지 입력은 `quality_warning`을 띄우고 사용자 확인을 강화한다.

검증 데이터:

- 어두운 조명 이미지
- 강한 JPEG 압축 이미지
- 작은 글씨가 압축 artifact로 깨진 이미지

### 4.7 글씨가 너무 작거나 해상도가 낮은 경우

발생 양상:

- 제품 전체를 멀리서 찍어 성분표가 이미지의 10% 미만을 차지한다.
- 디지털 줌으로 확대했지만 실제 글자 픽셀 수가 부족하다.
- 캡처 이미지 또는 썸네일을 업로드한다.

위험:

- 성분명은 일부 읽히지만 함량 column이 누락된다.
- `µg`, `mg`, `g`, `IU` 단위가 서로 혼동된다.
- OCR provider가 임의의 단어 조각만 반환할 수 있다.

탐지 신호:

- OCR word bounding box 높이가 너무 작다.
- 성분표 ROI의 pixel area가 전체 이미지 대비 작다.
- table anchor는 있으나 row/column 구조가 불충분하다.

기술 대응:

- 모바일에서 성분표 ROI를 확대해 촬영하도록 유도한다.
- 최소 해상도와 최소 text height 기준을 fixture 기반으로 정한다.
- 기준 미달이면 자동 파싱을 중단하고 `retake_recommended=true`로 반환한다.
- 사용자에게 "제품 전체 사진"과 "성분표 확대 사진"을 분리해서 받는 multi-image 흐름을 제공한다.

검증 데이터:

- 제품 전체는 선명하지만 성분표가 작은 이미지
- 저해상도 screenshot
- 성분표가 이미지 모서리에 작게 있는 이미지

### 4.8 성분표 일부가 잘렸거나 손가락/그림자에 가린 경우

발생 양상:

- 표의 왼쪽 성분명 column 또는 오른쪽 함량 column이 잘려 있다.
- 손가락이 table 일부를 가린다.
- 병을 잡은 그림자가 성분표 위에 걸친다.

위험:

- 남은 column만 보고 성분명과 함량을 잘못 연결한다.
- `1일 섭취량`, `총 내용량`, `1회 제공량` 같은 기준 행이 빠질 수 있다.
- 누락된 row를 자동 보완하면 잘못된 성분표가 생성된다.

탐지 신호:

- table bounding box가 이미지 edge에 닿아 있다.
- row 시작 또는 끝 column의 OCR box가 반복적으로 누락된다.
- essential section anchor가 있으나 section completion score가 낮다.

기술 대응:

- table이 이미지 edge에 닿으면 "표 전체가 보이도록 다시 촬영"을 요청한다.
- 가림이 부분적이면 해당 row를 `missing_or_occluded`로 표시한다.
- multi-shot stitching은 추후 과제로 두고, 초기에는 "추가 사진 업로드"를 우선한다.
- parser는 missing row를 생성하지 않는다.

검증 데이터:

- 왼쪽 column crop 이미지
- 오른쪽 함량 crop 이미지
- 손가락/그림자 가림 이미지

### 4.9 한국어/영어 혼합, 여러 단위, % 기준치 혼재

발생 양상:

- `Vitamin D 25 µg (1,000 IU)`, `비타민D 25 ug`, `100%`가 같은 row에 섞인다.
- 한국어 성분명과 영어 원료명이 병기된다.
- 1정당, 1회 섭취량당, 1일 섭취량당 기준이 다르다.

위험:

- 단위 변환을 무리하게 적용하면 잘못된 함량이 된다.
- `% 영양성분기준치`를 실제 함량으로 오인할 수 있다.
- 동일 성분 alias 매칭이 실패하거나 중복 성분으로 저장될 수 있다.

탐지 신호:

- 한 row에 숫자/단위/% 패턴이 2개 이상 존재한다.
- 괄호 안 병기값이 있다.
- `1일 섭취량`, `per serving`, `daily value`, `%DV` anchor가 함께 나타난다.

기술 대응:

- 원문 단위와 정규화 단위를 분리 저장한다.
- 변환 규칙이 확정되지 않은 단위는 자동 변환하지 않고 원문 표시한다.
- `%` 값은 별도 field로 분리하고 amount로 저장하지 않는다.
- 성분 alias 매칭은 `original_name`, `normalized_name`, `evidence_text`를 함께 유지한다.

검증 데이터:

- 한영 병기 제품
- IU와 µg가 함께 표기된 제품
- `%DV`와 mg가 같은 row에 있는 제품

### 4.10 바코드가 없거나, 제품명/OCR과 바코드 DB가 충돌하는 경우

발생 양상:

- 수입 제품, 해외 직구 제품, 리뉴얼 제품은 국내 DB에 없을 수 있다.
- 바코드가 찍혔지만 OCR 제품명과 조회 결과 제품명이 다르다.
- 한 이미지에 여러 바코드가 있다.

위험:

- 바코드만으로 제품을 확정하면 잘못된 제품 snapshot이 만들어질 수 있다.
- 리뉴얼 전후 성분이 다를 수 있다.
- 바코드가 외부 박스와 내부 병에서 다를 수 있다.

탐지 신호:

- barcode result count가 0 또는 2 이상이다.
- barcode lookup product name과 OCR product name의 similarity가 낮다.
- 바코드 ROI와 성분표 ROI가 서로 다른 제품 region에 속한다.

기술 대응:

- 모바일에서 바코드 스캔을 먼저 시도하고, 실패 시 이미지 OCR 흐름으로 fallback한다.
- barcode result와 OCR label identity를 비교해 `identity_conflict`를 생성한다.
- 충돌이 있으면 사용자에게 제품 선택/확인을 요구한다.
- barcode DB 조회 결과는 성분표 OCR을 대체하지 않고 보조 identity evidence로만 사용한다.

검증 데이터:

- 바코드 없는 제품
- 바코드 2개가 보이는 이미지
- OCR 제품명과 DB 제품명이 다른 이미지

### 4.11 주의사항/원재료/알레르기 문구가 다른 면에 있는 경우

발생 양상:

- 전면에는 제품명, 후면에는 성분표, 측면에는 주의사항이 있다.
- 병 라벨이 좁아 한 장의 사진에 모든 정보가 들어가지 않는다.
- 알레르기 또는 섭취 주의 문구가 작은 글씨로 별도 위치에 있다.

위험:

- 성분표 분석은 되었지만 주의사항이 누락될 수 있다.
- 사용자는 분석이 완전하다고 오해할 수 있다.
- 개인 맞춤 위험 평가에서 알레르기/주의 문구가 빠진다.

탐지 신호:

- 성분표는 감지되지만 `주의`, `섭취 시 주의사항`, `알레르기`, `임산부`, `질환` anchor가 없다.
- 제품 전면/후면 role이 불완전하다.

기술 대응:

- multi-image package를 도입해 `front`, `facts`, `caution`, `barcode` 역할을 분리한다.
- 필수 역할이 없으면 `missing_required_sections`에 기록한다.
- 주의사항 누락 시 개인 위험 평가 결과를 제한하거나 "주의 문구 추가 확인 필요"로 표시한다.
- 같은 제품에 속하는 여러 사진은 barcode/product name으로 묶고, 충돌 시 사용자 확인을 요구한다.

검증 데이터:

- 성분표만 있고 주의사항 없는 이미지
- 주의사항만 있는 측면 이미지
- 전면/후면/측면 3장 package

### 4.12 보충제가 아닌 의약품, 처방전, 검사표, 음식 라벨이 업로드된 경우

발생 양상:

- 사용자가 일반의약품 상자, 처방전, 병원 검사표를 업로드한다.
- 건강기능식품이 아니라 일반 식품 영양성분표가 업로드된다.
- 약 봉투 또는 복약 안내문이 포함된다.

위험:

- 보충제 파서가 의약품 용법/용량을 보충제 섭취량처럼 처리할 수 있다.
- 직접 복용량 변경 조언으로 이어질 위험이 있다.
- 민감 의료정보 저장/처리 범위가 달라진다.

탐지 신호:

- `전문의약품`, `일반의약품`, `처방`, `용법`, `용량`, `검사결과`, 병원명 anchor가 감지된다.
- 보충제 성분표 anchor보다 의료 문서 anchor가 강하다.

기술 대응:

- 문서 유형 분류 gate를 추가한다.
- 의약품/처방전/검사표는 보충제 분석 pipeline에서 분리하고 intake-only 상태로 둔다.
- 직접 복용량 변경, 중단, 증량, 감량 안내는 차단한다.
- 사용자가 의료 전문가에게 확인해야 하는 문서임을 UI에서 명시한다.

검증 데이터:

- 일반의약품 박스
- 처방전
- 검사표
- 일반 식품 영양성분표

### 4.13 온라인 쇼핑몰 스크린샷 또는 편집 이미지

발생 양상:

- 제품 상세페이지 screenshot을 업로드한다.
- 성분표가 확대 캡처되어 있지만 실제 제품 사진이 아니다.
- 여러 제품 상세페이지가 한 이미지에 이어 붙어 있다.

위험:

- 실제 사용자가 보유한 제품과 이미지 속 제품이 다를 수 있다.
- 리뉴얼 전후 상세페이지가 혼재될 수 있다.
- screenshot은 해상도/압축/잘림이 많아 OCR 오류가 늘 수 있다.

탐지 신호:

- 스크린샷 UI 요소, 가격, 장바구니, 리뷰, 쇼핑몰 메뉴가 보인다.
- EXIF가 없거나 이미지 비율이 긴 세로 페이지 형태다. 단, EXIF 유무는 신뢰할 수 있는 단독 판정 기준이 아니다.

기술 대응:

- screenshot은 `source_type=screenshot_or_catalog`로 표시하고 사용자 확인을 강화한다.
- 제품 식별과 성분 후보는 가능하더라도 "실물 라벨 확인 필요" 상태로 둔다.
- 긴 상세페이지 이미지는 section crop 후 분석하되, 여러 제품이 섞인 경우 자동 병합하지 않는다.

검증 데이터:

- 쇼핑몰 상세페이지 screenshot
- 제품 비교표 screenshot
- 긴 세로 이미지

### 4.14 중복 업로드, 재시도, Android lost data

발생 양상:

- 네트워크 실패 후 같은 이미지를 여러 번 업로드한다.
- Android에서 이미지 선택 중 앱 프로세스가 종료되어 결과가 늦게 복구된다.
- 사용자가 같은 제품을 전면/후면으로 찍었는데 시스템이 중복 제품으로 판단한다.

위험:

- 같은 분석이 여러 번 저장된다.
- 사용자가 확인하지 않은 이전 preview가 최신 결과처럼 보일 수 있다.
- multi-image package와 duplicate image가 혼동될 수 있다.

탐지 신호:

- image hash가 동일하다.
- client_request_id가 재사용된다.
- 촬영 시간/파일명/해시가 매우 유사하다.

기술 대응:

- `client_request_id`와 image hash 기반 idempotency를 유지한다.
- Flutter `image_picker`의 `retrieveLostData()` 흐름에서 복구된 파일도 동일한 preview pipeline으로 태운다.
- multi-image package는 image role을 명시하고, 단순 중복은 사용자에게 병합/무시 옵션을 제공한다.

검증 데이터:

- 같은 이미지 연속 업로드
- lost data 복구 후 업로드
- 전면/후면 이미지가 같은 제품으로 묶이는 케이스

### 4.15 너무 큰 파일, HEIC/WebP, 비표준 이미지 포맷

발생 양상:

- 최신 iPhone HEIC 이미지가 업로드된다.
- 고해상도 원본이 너무 커서 업로드/처리 시간이 길다.
- WebP, panorama, PDF screenshot 등이 들어온다.

위험:

- 서버 처리 시간이 길어져 timeout이 발생한다.
- OCR provider가 해당 포맷을 직접 지원하지 않을 수 있다.
- 무리한 resize로 작은 글씨가 더 안 보일 수 있다.

탐지 신호:

- MIME type 또는 magic bytes가 허용 목록 밖이다.
- 이미지 pixel count/file size가 상한을 넘는다.
- aspect ratio가 지나치게 길다.

기술 대응:

- 모바일에서 업로드 전 파일 크기와 해상도 제한을 적용하되, 성분표 글자 가독성을 해치지 않는 수준에서만 압축한다.
- 서버에서 허용 MIME type, 최대 파일 크기, 최대 pixel count를 명시한다.
- 포맷 변환이 필요한 경우 변환 성공/실패를 quality report에 남긴다.
- 처리 실패 시 "지원하지 않는 이미지 형식"과 "다시 촬영/변환" 안내를 분리한다.

검증 데이터:

- HEIC
- 매우 큰 JPEG
- 긴 panorama
- WebP screenshot

## 5. 제안하는 데이터 계약

이미지 분석 preview 응답에 다음 필드를 추가하는 방향을 검토한다.

```json
{
  "image_quality": {
    "retake_recommended": true,
    "retake_reasons": ["blurred_text", "glare_or_reflection"],
    "warnings": ["small_text", "partial_table"],
    "source_type": "camera_photo",
    "quality_evidence": [
      {
        "type": "ocr_density",
        "message": "성분표 영역의 OCR 단어 수가 부족합니다."
      }
    ]
  },
  "detected_product_regions": [
    {
      "region_id": "region_1",
      "bbox": [120, 80, 880, 1460],
      "region_type": "supplement_label",
      "identity_candidates": ["제품명 후보"],
      "barcode_candidates": ["8800000000000"]
    }
  ],
  "selected_region_id": "region_1",
  "analysis_scope": "single_product_region",
  "missing_required_sections": ["caution"],
  "multi_image_group_id": "group_20260517_001",
  "image_role": "facts"
}
```

설계 원칙:

- `retake_reasons`는 사람이 이해할 수 있는 UI 문구로 매핑 가능한 enum이어야 한다.
- `quality_evidence`는 원본 이미지 전체를 저장하지 않고도 왜 재촬영을 요구했는지 설명할 수 있어야 한다.
- `detected_product_regions`는 제품별 분석 분리를 위한 구조이며, 성분 후보 병합을 위한 구조가 아니다.
- `analysis_scope`는 `full_image`, `single_product_region`, `multi_image_package`, `identity_only` 같은 명시적 값을 가져야 한다.

## 6. 단계별 구현 우선순위

### Phase A. 모바일 입력 품질 gate

목표:

- 업로드 전에 사용자에게 가장 큰 실패 요인을 줄이도록 안내한다.

구현 후보:

- 촬영 직후 preview 화면에서 "성분표가 화면 대부분을 차지하는지" 확인 체크.
- Android `image_picker` lost data 복구 처리 유지.
- 바코드가 보이면 ML Kit barcode scan을 먼저 시도.
- 사용자가 제품 전체 사진과 성분표 확대 사진을 구분해 업로드할 수 있게 image role 선택 제공.

성공 기준:

- 표지 라벨만 있는 이미지는 성분 분석으로 바로 넘어가지 않는다.
- 흐림/잘림/반사가 명확한 사진은 재촬영 안내가 뜬다.
- 바코드와 성분표 사진이 같은 제품인지 사용자 확인 단계가 있다.

### Phase B. 서버 이미지 품질 분석기

목표:

- OCR/파서 전에 이미지 자체의 위험 신호를 구조화한다.

구현 후보:

- `ImageQualityReport` schema 추가.
- blur, glare, small text, partial table, multi-product, unsupported format reason code 추가.
- OCR provider confidence, word density, bounding box distribution을 결합하되, 공식 임계값처럼 고정하지 않고 fixture 기반 threshold로 관리.

성공 기준:

- quality issue가 preview 응답에 명시적으로 들어간다.
- low-confidence field는 기본 선택 해제된다.
- quality issue가 있어도 시스템이 임의로 성분을 만들어내지 않는다.

### Phase C. 제품 ROI 분리와 사용자 선택

목표:

- 여러 제품이 한 이미지에 있을 때 제품 단위로 분석을 분리한다.

구현 후보:

- OCR bounding box clustering과 barcode bbox를 이용한 heuristic region proposal.
- 필요 시 객체 검출/segmentation 모델을 별도 검토하되, 성능 수치 없이 PoC fixture로 먼저 비교.
- 사용자 crop/region selection UI.

성공 기준:

- 여러 제품이 있는 이미지에서 성분 후보가 하나로 병합되지 않는다.
- 사용자가 선택한 region만 layout parser로 전달된다.
- barcode region과 OCR label region이 충돌하면 자동 확정하지 않는다.

### Phase D. multi-image package

목표:

- 한 제품의 전면, 성분표, 주의사항, 바코드를 여러 사진으로 안전하게 묶는다.

구현 후보:

- `image_role`: `front`, `facts`, `caution`, `barcode`, `other`.
- `multi_image_group_id`로 같은 제품 분석 묶음 구성.
- 각 이미지별 OCR evidence를 유지하고, 최종 snapshot에는 사용자 확인된 필드만 반영.

성공 기준:

- 전면 사진만으로 성분표 분석 완료 상태가 되지 않는다.
- 주의사항 누락 시 개인 위험 평가를 제한한다.
- 이미지 간 제품 identity 충돌이 있으면 사용자 확인을 요구한다.

### Phase E. fixture와 평가 체계 확장

목표:

- 실제 실패 상황을 테스트 데이터로 고정하고, 추후 개선이 회귀를 만들지 않도록 한다.

구현 후보:

- `tests/fixtures/supplement_images/quality_cases/` 또는 별도 fixture manifest.
- 각 fixture에 `expected_retake_reasons`, `expected_missing_sections`, `expected_region_count`를 기록.
- 실제 제품 성분값을 테스트할 때는 공개 가능한 샘플 또는 합성 데이터를 명확히 구분한다.

성공 기준:

- multi-product, cover-only, blur, glare, partial crop, low-resolution, non-supplement 케이스가 최소 1개 이상 존재한다.
- 성능 수치를 보고할 때는 fixture 규모와 데이터 출처를 함께 표기한다.
- dummy/synthetic 데이터는 문서와 fixture manifest에 명시한다.

## 7. 상황별 처리 매트릭스

| 상황 | 자동 분석 가능 여부 | 사용자 액션 | 서버 상태 | 저장/반영 원칙 |
| --- | --- | --- | --- | --- |
| 단일 제품, 선명한 성분표 | 가능 | 확인 후 저장 | `preview_ready` | evidence 기반 후보만 저장 |
| 여러 제품 | 제한 | 제품 영역 선택 | `needs_product_region_selection` | 제품별 snapshot 분리 |
| 표지 라벨만 있음 | 성분 분석 불가 | 성분표 추가 촬영 | `needs_additional_label_image` | identity 후보만 저장 |
| 흐림/초점 실패 | 제한 | 재촬영 권장 | `retake_recommended` | low-confidence 기본 해제 |
| 반사/가림 | 제한 | 재촬영 또는 추가 촬영 | `retake_recommended` | 가려진 row 생성 금지 |
| 일부 crop | 제한 | 표 전체 재촬영 | `partial_table_detected` | 누락 필드 유지 |
| 바코드/OCR 충돌 | 제한 | 제품 확인 | `identity_conflict` | 자동 확정 금지 |
| 의약품/처방전 | 보충제 분석 불가 | 별도 intake 확인 | `regulated_intake_only` | 복용량 변경 안내 차단 |
| screenshot | 제한 | 실물 라벨 확인 | `source_low_trust` | 제품/성분 확정 전 확인 |
| unsupported format | 불가 | 재촬영/변환 | `unsupported_image_format` | 분석 결과 생성 금지 |

## 8. 테스트 케이스 초안

### 단위 테스트

- `test_image_quality_blur_returns_retake_reason`
- `test_cover_only_image_does_not_create_ingredient_candidates`
- `test_multi_product_regions_are_not_merged`
- `test_barcode_ocr_identity_conflict_requires_confirmation`
- `test_regulated_document_routes_to_intake_only`
- `test_partial_table_marks_missing_sections`

### 통합 테스트

- `POST /api/v1/supplements/analyze-image`에 cover-only 이미지를 넣었을 때 `needs_additional_label_image` 반환.
- multi-product 이미지에서 `detected_product_regions`가 2개 이상 반환되고, selected region 없이는 final save 불가.
- low-confidence 함량 후보는 preview에서 unchecked 상태로 반환.
- 의약품/처방전 anchor가 강한 이미지에서 supplement snapshot 생성 차단.

### 모바일 QA

- Android에서 camera intent 후 앱 재시작 시 `retrieveLostData()`로 복구된 파일이 preview queue에 들어가는지 확인.
- 바코드 스캔 성공 후 성분표 촬영으로 이어지는지 확인.
- 재촬영 안내가 실제 촬영 화면으로 자연스럽게 돌아가는지 확인.
- 여러 이미지 package에서 image role 변경이 가능한지 확인.

## 9. 운영 및 데이터 정책

1. 원본 이미지는 기본적으로 장기 저장하지 않는다.
2. 디버깅용 저장이 필요한 경우 사용자 동의, 보관 기간, 마스킹 정책이 먼저 정해져야 한다.
3. OCR full text는 민감정보가 섞일 수 있으므로 최소화하고, 필요한 evidence snippet만 저장한다.
4. 제품 분석 결과는 "사용자가 확인한 라벨 기반 후보"임을 UI에서 분명히 한다.
5. 의료적 해석, 복용량 변경, 질병 치료 판단은 서비스 범위 밖으로 둔다.

## 10. 다음 액션 제안

1. `ImageQualityReport`와 `retake_reasons` enum을 설계 문서 또는 schema에 추가한다.
2. 모바일 preview에서 `front/facts/caution/barcode` image role을 받는 UX를 먼저 만든다.
3. 서버에서 cover-only, multi-product, blur, partial crop을 감지하는 heuristic quality gate를 추가한다.
4. 실제 사용자 이미지가 없으면 합성 또는 공개 샘플 fixture를 만들되, dummy/synthetic 여부를 명시한다.
5. OCR/파서 평가 리포트에는 데이터셋 크기, fixture 종류, 실패 유형별 결과를 함께 표기한다.

## 11. 최종 정리

가장 중요한 설계 판단은 "사진이 나쁘면 더 똑똑하게 상상해서 채우는 것"이 아니라 "사진 상태를 진단하고, 제품 단위를 분리하고, 사용자가 확인 가능한 후보만 만드는 것"이다. 특히 여러 제품이 한 이미지에 있거나 표지 라벨만 있는 경우는 OCR 성능 문제가 아니라 입력 범위 정의 문제이므로, parser 이전에 ROI 선택과 추가 촬영 흐름을 반드시 둬야 한다.

이 문서의 기술 제안은 구현 후보이며, 특정 threshold나 성능 수치는 공식값으로 확정하지 않았다. 실제 적용 전에는 fixture 기반 평가와 사용자 확인 UX 검증이 필요하다.
