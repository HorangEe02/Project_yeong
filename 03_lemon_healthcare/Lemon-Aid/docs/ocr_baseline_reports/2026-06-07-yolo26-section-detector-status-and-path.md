# 갭 #1 — YOLO26 섹션 검출기: 상태, 약지도 평가 결과, 실제 경로

작성: 2026-06-07. 평가 결론(`2026-06-07-pipeline-implementation-evaluation.md`)의 최우선 갭 #1 대응.

## 현 상태
- 런타임 추론 코드·6섹션 분류체계·bbox→crop→OCR 핸드오프·클래스계약·오프라인 데이터셋/게이트 스크립트는 **존재**.
- 그러나 **학습 가중치 없음**, **섹션 bbox 주석 없음(205건 미작성)**, **기본 OFF**, 의존성은 generic `ultralytics>=8.1` → 현재 섹션 검출 **미작동**.

## 시도: CLOVA-박스 약지도(weak-supervision) — 평가 후 **부적합 판정**
`build_crawling_yolo_section_dataset.py`(신규)로 크롤링 `상세페이지` 이미지에서 CLOVA 필드 박스를 한국어 키워드/패턴으로 섹션 분류 → YOLO 라벨 자동 생성을 시도. 진단 결과(6제품·이미지당 최대6, **박스 2,050개**):

| 지표 | 값 |
|---|---|
| 미분류(unclassified) | **1,916 (93%)** |
| ingredient_amounts | 124 |
| supplement_facts | 8 |
| precautions | 2 |
| intake_method / allergen_warning / product_identity / functional_claims | **0** |

→ **결론:** 상세페이지는 대부분 마케팅 그래픽이라 라인단위 키워드 분류가 거의 안 잡히고(93% 미분류), 비-amount 섹션(섭취방법/주의/알레르기)은 사실상 0건. **약지도로는 다중-섹션 YOLO 검출기 학습 불가**(거의 단일클래스 노이즈). 이 데이터셋은 **생성하지 않음**(저품질 + CLOVA 비용 낭비 방지). 빌더 스크립트는 실험/진단용으로만 보존.

## 실제 경로 (권장) — 기존 주석 체인 + A100 학습
1. **섹션 bbox 주석(205건)**: 기존 파이프라인 사용 — `build_supplement_yolo_annotation_review_bundle.py` → (운영자가 Label Studio에서 6섹션 bbox 드로잉) → `fetch_label_studio_yolo_annotations.py` → `convert_label_studio_yolo_annotations.py` → `extract_supplement_yolo_reviewed_annotations.py` → `preflight_supplement_yolo_annotation_decisions.py --require-all-reviewed` → `promote_supplement_yolo_annotation_template.py`.
2. **데이터셋 materialize/validate/gate**: `materialize_supplement_section_yolo_dataset.py` → `validate_supplement_section_yolo_dataset.py --require-files` → `gate_supplement_yolo_section_dataset.py`(통과 = `ready_for_section_yolo_training_dataset`).
3. **A100 YOLO26 학습**(GPU):
   ```bash
   pip install "ultralytics>=8.1"   # 또는 YOLO26 공식 패키지
   yolo detect train data=<dataset.yaml> model=yolo26n.pt imgsz=1024 epochs=100 batch=16 device=0
   ```
   - 클래스: product_identity, supplement_facts, ingredient_amounts, precautions, allergen_warning, intake_method (+ other_ingredients, functional_claims) — `learning.retraining.SUPPLEMENT_SECTION_CLASS_NAMES` 순서.
   - 학습 후 `best.pt`를 서버에 배치 → `vision_classifier_model` 지정 + `enable_vision_classifier=True` + `ocr_roi_preprocessing_policy=crop_before_primary`로 런타임 활성화. 클래스계약(`ultralytics_runner._validate_model_class_contract`) 통과 필요.

## 대안(주석 공수 절감, 향후)
- **헤더-앵커 약지도**: 라인 키워드가 아니라 섹션 **헤더**(예 "섭취방법/복용방법", "주의사항", "알레르기 정보", "영양정보") 박스를 앵커로 검출 후 헤더~다음 헤더까지를 섹션 영역으로 묶기. (현 라인단위 분류보다 영역 품질↑) — 구현 시 재평가 권장.
- 합성/공개 라벨 데이터 혼합.

## 갭 #1 처리 요약
- 이 머신에서 achievable: 약지도 접근 **구현+실증평가**(부적합 확인), 실제 경로/런북 문서화.
- 남은 블로커(설계상 사람·GPU 필수): 205 섹션 bbox 주석 + A100 학습. → 운영자 주석 + GPU 단계.
