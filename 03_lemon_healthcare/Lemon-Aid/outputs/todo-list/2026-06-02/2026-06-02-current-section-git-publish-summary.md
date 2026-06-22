# 2026-06-02 현재 섹션 작업 및 GitHub 푸시 요약

> 작성 기준: 2026-06-02
> 대상 repo: `Lemon-Aid-KDT/Lemon-sin`
> 대상 branch: `docs/docs-2026-05-31-backend-ocr-security`

---

## 1. 완료한 작업

### OCR/YOLO 섹션 ROI 보강

- 영양제 라벨 OCR에서 `supplement_facts`, `precautions`, `intake_method`, `ingredients` 섹션을 더 명확히 구분하도록 layout anchor를 보강했다.
- 단수 `Warning`, `Allergy Information`, `Contains <allergen>` 계열 문구가 주의사항 후보로 누락되지 않도록 처리했다.
- `1회 제공량(26g)`, `Serving Size`, `Amount Per Serving` 계열 문구가 성분 후보로 잘못 들어오는 회귀 케이스를 추가했다.
- LLM parser가 주의사항을 놓쳐도 OCR layout evidence가 있으면 structured `precautions` 배열로 승격하는 경로를 보강했다.

### Ollama/Gemma 검증 및 설명 context

- Ollama/Gemma vision 검증은 OCR 텍스트와 이미지/ROI를 직접 대조하는 structured verification 계약으로 정리했다.
- 분석 미리보기 설명에 사용자 건강 프로필 context를 opt-in으로 연결했다.
- 분석 미리보기 설명에 사용자 질환/복약 DB context를 opt-in으로 연결했다.
- 민감 건강정보는 동의가 있을 때만 sanitized bucket으로 요약하며, raw 질환명/약명/용량/빈도는 LLM prompt와 audit output에 넣지 않는다.

### GitHub 푸시 상태

- 현재 작업 branch는 `docs/docs-2026-05-31-backend-ocr-security`다.
- push 대상 remote는 `origin`이며 URL은 `https://github.com/Lemon-Aid-KDT/Lemon-sin.git`이다.
- 개인 remote `personal`은 이번 작업에서 사용하지 않는다.
- 기존 완료 commit:
  - `e2cae66 feat(supplements): include medical context in analysis explanations`
  - `53941e8 fix(ocr): detect allergen warning ROI anchors`

---

## 2. 현재 확인한 blocker

### Custom supplement YOLO26 detector 미확인

- 현재 repo에서 확인된 `.pt` 가중치는 음식 YOLO 실험 가중치인 `runs/food_yolo/.../weights/best.pt`뿐이다.
- Ultralytics 기본 `yolo26*.yaml` 설정은 package 내부 모델 config이며, 영양제 성분표/주의사항/섭취방법 bbox를 학습한 custom detector가 아니다.
- 따라서 현재 상태를 "YOLO26으로 영양제 라벨 bbox 검출 완료"라고 말하면 안 된다.

### 다음 작업 필요

- 영양제 섹션 detector dataset contract를 명시한다.
- class name이 `supplement_facts`, `precautions`, `intake_method`, `ingredients` 등 허용 섹션으로 normalize되는지 readiness guard를 추가한다.
- default COCO model 또는 food model을 영양제 섹션 detector로 오인하지 않도록 backend runtime에서 명확한 warning/failed 상태를 반환한다.
- 실제 custom `.pt`가 준비되면 fixture 이미지 기준 bbox 품질, crop OCR, Ollama/Gemma vision verification까지 연결해 smoke test를 진행한다.

---

## 3. 적용 규칙

- raw OCR, provider payload, local image path, object URI, secret은 문서/API 응답/저장 모델에 포함하지 않는다.
- 사용자 건강정보는 동의 gate를 통과한 sanitized summary bucket만 LLM 설명에 사용한다.
- Git 작업 전에는 항상 실제 Git root와 remote를 확인한다.
- commit message는 Conventional Commits 형식으로 작성하고, 본문에 변경 이유와 검증 범위를 남긴다.
- 이번 문서 커밋은 보고서/인덱스 파일만 stage하고, 기존 untracked 데이터/프론트엔드/모바일 asset 산출물은 stage하지 않는다.

---

## 4. 참고 공식 문서

- Ultralytics YOLO26: <https://docs.ultralytics.com/models/yolo26/>
- Ultralytics Predict mode: <https://docs.ultralytics.com/modes/predict/>
- Ultralytics Train mode: <https://docs.ultralytics.com/modes/train/>
- Ollama structured outputs: <https://docs.ollama.com/capabilities/structured-outputs>
- Ollama generate API: <https://docs.ollama.com/api/generate>
