# 2026-06-02 OCR/YOLO 섹션 ROI 검증 및 남은 차단점

> 작성 기준: 2026-06-02
> 대상 브랜치: `docs/docs-2026-05-31-backend-ocr-security`

---

## 1. Git 기준

- Git root: `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid`
- Push remote: `origin`
- Push URL: `https://github.com/Lemon-Aid-KDT/Lemon-sin.git`
- 개인 remote `personal`은 이번 작업에서 사용하지 않는다.

---

## 2. 커밋 포함 대상

이번 커밋 포함 대상:

- `backend/Nutrition-backend/src/config.py`
- `backend/pyproject.toml`
- `backend/Nutrition-backend/src/services/supplement_image_analysis.py`
- `backend/Nutrition-backend/src/services/supplement_parser.py`
- `backend/Nutrition-backend/src/vision/taxonomy.py`
- `backend/Nutrition-backend/tests/unit/test_config.py`
- `backend/Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py`
- `backend/Nutrition-backend/tests/unit/services/test_supplement_parser_declaration.py`
- `backend/Nutrition-backend/tests/unit/vision/test_yolo_detector.py`
- `outputs/todo-list/2026-06-02/README.md`
- `outputs/todo-list/2026-06-02/2026-06-02-ocr-yolo-section-roi-implementation-summary.md`
- `outputs/todo-list/2026-06-02/2026-06-02-ocr-yolo-section-roi-verification.md`

명시적 제외 대상:

- `.env`, `.env.local`, `.vercel/.env.*.local`
- raw OCR/provider payload
- 원본 이미지 데이터셋
- 앱 실행 중 생성된 `.DS_Store`
- 현재 변경과 무관한 untracked 산출물

---

## 3. 실행한 검증

### Backend unit test

```bash
cd backend
.venv/bin/python -m pytest --no-cov \
  Nutrition-backend/tests/unit/test_config.py \
  Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py \
  Nutrition-backend/tests/unit/services/test_supplement_parser_declaration.py \
  Nutrition-backend/tests/unit/vision/test_yolo_detector.py
```

결과:

```text
106 passed
```

### Backend lint

```bash
cd backend
.venv/bin/python -m ruff check \
  Nutrition-backend/src/services/supplement_image_analysis.py \
  Nutrition-backend/src/services/supplement_parser.py \
  Nutrition-backend/src/vision/taxonomy.py \
  Nutrition-backend/src/config.py \
  Nutrition-backend/tests/unit/test_config.py \
  Nutrition-backend/tests/unit/services/test_supplement_image_analysis.py \
  Nutrition-backend/tests/unit/services/test_supplement_parser_declaration.py \
  Nutrition-backend/tests/unit/vision/test_yolo_detector.py
```

결과:

```text
All checks passed!
```

### Related regression

```bash
cd backend
.venv/bin/python -m pytest --no-cov \
  Nutrition-backend/tests/unit/vision/test_preprocessing.py \
  Nutrition-backend/tests/unit/llm/test_ollama_vision_assist.py
```

결과:

```text
14 passed
```

### Parser 직접 재현

검증 내용:

- `1회 제공량(26g)` 계열은 성분 후보 0개
- `비타민 C 26g`은 성분 후보 1개

결과:

```text
1회 제공량 계열: []
비타민 C 26g: display_name=비타민 C, amount=26, unit=g
```

### Diff/secret check

```bash
git diff --check
detect-secrets scan <changed tracked files>
```

결과:

```text
git diff --check: pass
detect-secrets: results {}
```

---

## 4. 실제 YOLO runtime 검증 상태

실제 Ultralytics runtime smoke는 완료했다.

확인한 현재 상태:

- backend `.venv`에 `setuptools`, `wheel`, `torch`, `ultralytics`, `opencv-python` 설치 완료
- import smoke 결과: `torch 2.12.0`, `ultralytics 8.4.60`, `cv2 4.13.0`
- 공식 YOLO26 모델명 `yolo26n.pt` 로드 및 blank image inference 성공
- 기존 food YOLO `.pt` weight 로딩 성공, class count 50 확인
- repo 안에서 영양제 섹션 detector로 보이는 `.pt` weight를 찾지 못함
- 확인된 `.pt` weight는 음식 YOLO 실험 weight뿐임

`backend`에서 `.venv/bin/python -m pip install '.[vision]'`은 최초에 의존성 설치 전 packaging 단계에서 실패했다.

```text
Multiple top-level packages discovered in a flat-layout: ['alembic', 'ai_agent_chat'].
```

원인은 `backend/pyproject.toml`에 setuptools package discovery 설정이 없어 `backend` 루트의 여러 top-level 폴더가 자동 탐색된 것이었다. `Nutrition-backend/src` 아래 `src*` 패키지만 찾도록 설정한 뒤 다음 검증을 통과했다.

```text
.venv/bin/python -m pip install --dry-run --no-deps --no-build-isolation '.[vision]'
Would install lemon-healthcare-backend-0.1.0
```

```text
.venv/bin/python -m pip install '.[vision]'
Successfully installed ... torch-2.12.0 ... ultralytics-8.4.60 ...
```

공식 문서 기준:

- Ultralytics YOLO26 model usage: <https://docs.ultralytics.com/models/yolo26/>
- Ultralytics Predict mode: <https://docs.ultralytics.com/modes/predict/>

주의: `yolo26n.pt`는 COCO pretrained 모델이므로 영양제 `precautions`, `supplement_facts`, `intake_method` 섹션을 자동으로 검출한다고 볼 수 없다. 실제 주의사항 OCR 개선 완료 판정에는 custom supplement section `.pt` 모델이 필요하다.

---

## 5. 다음 작업

- 영양제 섹션 custom YOLO weight 위치 확정
- `VISION_YOLO_MODEL_PATH`에 해당 weight 연결
- `precautions`, `intake_method`, `supplement_facts` class가 실제로 감지되는지 이미지 smoke test 실행
- 감지된 ROI가 OCR crop으로 들어가고 결과 화면 주의사항 카드에 반영되는지 Android/iOS에서 확인
- packaging 문제가 반복되면 `backend/pyproject.toml`의 setuptools discovery 설정을 별도 커밋으로 정리
