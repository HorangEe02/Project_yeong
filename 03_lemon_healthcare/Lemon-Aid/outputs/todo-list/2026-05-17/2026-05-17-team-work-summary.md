# Lemon Healthcare 팀 공유 보고서 - 2026-05-17 작업 내용 정리

## 한 줄 요약

오늘 작업은 영양제 라벨 OCR을 실제 모바일 환경과 실제 라벨 데이터셋 기준으로 테스트할 수 있게 만든 작업이다. 서버 쪽에서는 Google Vision, PaddleOCR, ROI/촬영 품질, parser/domain correction, governance 기준을 정리하고 구현 기반을 넓혔고, 화면 쪽에서는 카메라 촬영, 여러 이미지 업로드, 모델 1/모델 2 비교, ngrok 기반 iPhone 테스트 경로를 만들었다. 이후 PaddleOCR을 기본 OCR provider로 전환하고, 로컬 `PaddleOCR-main` source checkout을 학습/검증용으로 연결했으며, 실제 naver 라벨 데이터셋에서 300장 private fine-tuning annotation queue를 생성했다.

## 기준 정보

- 작업 대상일: 2026-05-17
- 로컬 프로젝트 경로: `/Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid`
- 보고서 저장 경로: `/Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/outputs/todo-list/2026-05-17`
- 주요 backend 경로: `/Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend/Nutrition-backend`
- OCR 테스트 UI 경로: `/Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/firebase-ocr-test`
- PaddleOCR source checkout: `/Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/PaddleOCR-main`
- PaddleOCR private queue: `/Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/backend/data/private/paddleocr_finetuning/2026-05-17`
- 현재 작업 상태: 변경 파일과 신규 파일이 작업 트리에 남아 있으므로, 커밋 전 포함 범위 선별이 필요하다.

## 공식 문서 기준

오늘 설계와 구현은 아래 공식 문서를 기준으로 삼았다.

- Google Vision OCR: https://cloud.google.com/vision/docs/ocr
- PaddleOCR GitHub: https://github.com/PaddlePaddle/PaddleOCR
- PaddleOCR OCR pipeline: https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/OCR.html
- PaddleOCR OCR dataset docs: https://www.paddleocr.ai/latest/en/datasets/ocr_datasets.html
- PaddleOCR text detection: https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_detection.html
- PaddleOCR text recognition: https://www.paddleocr.ai/latest/en/version3.x/module_usage/text_recognition.html
- Ultralytics detection datasets/train/predict: https://docs.ultralytics.com/datasets/detect/, https://docs.ultralytics.com/modes/train/, https://docs.ultralytics.com/modes/predict/
- OpenCV thresholding/geometric transforms: https://docs.opencv.org/4.x/d7/d4d/tutorial_py_thresholding.html, https://docs.opencv.org/4.x/da/d6e/tutorial_py_geometric_transformations.html
- FastAPI file upload/CORS: https://fastapi.tiangolo.com/tutorial/request-files/, https://fastapi.tiangolo.com/tutorial/cors/
- ngrok HTTP endpoints/free plan: https://ngrok.com/docs/http/, https://ngrok.com/docs/pricing-limits/free-plan-limits
- MDN getUserMedia/mixed content: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia, https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Mixed_content
- Pydantic validators: https://docs.pydantic.dev/latest/concepts/validators/

명시적 한계: 보충제 라벨 전용 blur/glare/minimum text size 임계값, 또는 한국어+영어 영양제 라벨에 대한 PaddleOCR 공식 정확도 기준은 확인하지 못했다. 따라서 현재 threshold와 promotion gate는 공식 성능 claim이 아니라 내부 fixture, no-regression, 팀 리뷰 기준으로 보정해야 한다.

## 오늘 작업의 목표

영양제 라벨 이미지는 사용자의 스마트폰, 조명, 촬영 거리, 제품 형태에 따라 OCR 실패 양상이 크게 달라진다. 단순히 이미지를 업로드하고 OCR 텍스트를 받는 수준으로는 실제 서비스 테스트가 어렵다.

오늘 목표는 다음 네 가지였다.

1. Google Vision과 PaddleOCR을 비교할 수 있는 테스트 흐름을 만든다.
2. 한 장뿐 아니라 여러 장의 제품 라벨 이미지를 촬영/첨부해 테스트할 수 있게 한다.
3. iPhone에서 카메라가 보이지 않거나, `127.0.0.1` API 호출이 실패하는 문제를 해결한다.
4. 위험 상황별 대응안을 문서와 runtime action contract로 연결할 수 있게 정리한다.
5. 기본 OCR provider를 Google Vision이 아니라 PaddleOCR local primary로 바꾸고, Google Vision은 명시적 외부 OCR opt-in 비교 provider로 유지한다.
6. 로컬 `PaddleOCR-main` source checkout을 repo에 커밋하지 않는 학습/검증용 도구로 연결하고, 실제 라벨 데이터셋에서 300장 private annotation queue를 만든다.

## 구현 및 수정한 내용

### 1. 보충제 라벨 이미지 위험 상황 브레인스토밍 문서화

`Brand-New-update/2026-05-17-supplement-label-image-risk-brainstorm.md`를 기준으로, 실제 사용자가 올릴 수 있는 이미지 문제를 정리했다.

대표 문제 상황:

- 한 이미지에 여러 제품이 같이 찍힘
- 표지 라벨만 있고 Supplement Facts 표가 없음
- 흔들림, 초점 불량, 반사, 저조도, 낮은 대비
- 글자가 너무 작거나 표가 일부 잘림
- 원통형 병의 곡률과 기울어짐
- barcode는 보이지만 OCR 제품명과 충돌
- 쇼핑몰 스크린샷, 식품 라벨, 의약품, 처방전/검사표 유입

대응 방향:

- 성분/함량/단위가 확인되지 않으면 생성하지 않는다.
- cover-only는 identity-only preview로 분리한다.
- multi-product는 자동 병합하지 않고 제품 영역 선택을 요구한다.
- blur/glare/low-light는 hard block이 아니라 retake/review action으로 반환한다.
- 처방전/검사표/의약품 의심 흐름은 supplement analyze가 아니라 regulated intake 또는 별도 review로 분리한다.

### 2. Plan A: PaddleOCR local OCR 및 layout normalization

PaddleOCR을 단순 fallback 텍스트 추출기가 아니라 layout metadata를 보존하는 local OCR provider로 올리는 계획을 작성하고 구현 기준을 정리했다.

핵심 기준:

- 기존 `OCRResult`, `OCRPage`, `OCRWord` 계약은 유지한다.
- PaddleOCR 3.x 결과의 `rec_texts`, `rec_scores`, `rec_polys`, `dt_polys`를 provider 내부에서 정규화한다.
- polygon 우선순위는 `rec_polys -> dt_polys -> 없음`으로 둔다.
- line-level polygon을 임의 word/column으로 쪼개지 않는다.
- layout normalization이 실패해도 text/confidence가 있으면 OCR 자체는 실패로 보지 않고 flat result로 degrade한다.
- 실제 PaddleOCR import/model smoke는 `/readiness`가 아니라 별도 probe script에서만 수행한다.

팀이 알아야 할 의미:

- PaddleOCR은 이제 영양제 OCR의 local primary provider 기본값이다.
- Google Vision은 live seed와 비교를 위한 명시적 외부 OCR opt-in provider로 남긴다.
- `/ready`에는 vendor live call을 넣지 않고, PaddleOCR 실제 import/predict 확인은 별도 probe script로만 수행한다.

### 3. Plan B: ROI 및 촬영 품질 학습

OCR 전에 이미지가 분석 가능한지, 어느 영역을 OCR해야 하는지 판단하는 layer를 설계했다.

핵심 구성:

- `ImageQualityReport`
- quality reason code: `blurred_text`, `glare_or_reflection`, `low_light`, `low_contrast`, `too_small_text`, `partial_table`, `cover_only`, `multi_product`, `roi_not_found`
- deterministic quality analyzer: brightness, contrast, blur proxy, glare proxy, ROI area ratio
- consent-gated ROI dataset exporter
- product/barcode/hash/session disjoint split validator
- YOLO ROI 학습은 manifest/export/split validator 이후에만 진행

팀이 알아야 할 의미:

- v1은 새 모델 학습보다 deterministic report와 manifest 기반을 우선한다.
- 품질 경고는 추천 입력 확정이 아니라 사용자 행동 안내와 review warning으로 사용한다.

### 4. Plan C: PaddleOCR fine-tuning

PaddleOCR 기본 모델이 보충제 라벨의 한영 혼합 텍스트, 숫자, 단위, 작은 표 글자를 반복적으로 틀릴 경우를 대비해 fine-tuning 데이터셋과 runbook 기준을 작성했다.

핵심 기준:

- v1은 recognition-first fine-tuning을 기본으로 한다.
- 학습 label은 사람이 확인한 transcript만 사용한다.
- bootstrap OCR 결과만 있는 sample은 train label로 쓰지 않고 `needs_human_review`로 둔다.
- raw image, raw OCR text, provider raw payload, EXIF/GPS, filename, user id는 manifest에 저장하지 않는다.
- model promotion은 frozen test split에서 `numeric exact`, `unit exact`, `line exact`, `parser success`, `field exact` 기준으로 판단한다.

팀이 알아야 할 의미:

- 성능 개선 주장은 fixture와 checksum이 있는 경우에만 가능하다.
- v1 fine-tuning 준비 범위는 detection+recognition 모두를 열어두되, 자동 OCR 결과를 학습 정답으로 승격하지 않는다.
- detection/recognition label은 사람이 검수한 `human_verified=true` box/transcript만 export와 학습에 사용할 수 있다.

### 5. PaddleOCR local primary 전환

PaddleOCR을 Google Vision보다 앞선 기본 OCR provider로 전환했다.

핵심 변경:

- `OCR_PRIMARY_PROVIDER` 기본값을 `paddleocr`로 변경했다.
- `ENABLE_LOCAL_OCR` 기본값을 `true`로 변경했다.
- `build_supplement_ocr_adapter()`가 PaddleOCR primary adapter를 직접 만들도록 보강했다.
- PaddleOCR이 primary일 때 같은 adapter가 fallback에도 중복 등록되지 않게 했다.
- Google Vision은 `ocr_provider=google_vision` 명시 요청과 `ALLOW_EXTERNAL_OCR=true` 조건에서만 사용한다.
- production validator는 PaddleOCR primary를 허용하되, Google Vision production 사용은 계속 ADC/service account 기준으로 제한한다.

검증 의미:

- 모델 2 PaddleOCR 선택지는 더 이상 단순 UI placeholder가 아니다.
- 실제 predict smoke에서 `paddleocr_local` provider가 text와 layout을 반환하는 것을 확인했다.
- Google Vision과 CLOVA는 외부 OCR 동의와 credential opt-in 없이는 실행되지 않는다.

### 6. PaddleOCR-main source checkout 적용

`PaddleOCR-main`은 우리 repo runtime 코드에 import하지 않고, 학습/검증용 source dir로만 사용한다.

확인한 로컬 source:

- source path: `/Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/PaddleOCR-main`
- source size: 약 `144M`
- zip size: 약 `112M`
- 필수 entrypoint: `tools/train.py`, `tools/eval.py`, `tools/export_model.py`
- detection config: `configs/det/PP-OCRv5/PP-OCRv5_server_det.yml`
- recognition config: `configs/rec/PP-OCRv5/multi_language/korean_PP-OCRv5_mobile_rec.yml`

보호 조치:

- `.gitignore`에 `/PaddleOCR-main/`, `/PaddleOCR-main.zip`, `backend/data/private/`를 추가했다.
- `git status --short --ignored`에서 PaddleOCR source, zip, private queue가 `!!` ignored로 확인됐다.
- runtime은 설치된 `paddleocr` package만 사용하고, `PaddleOCR-main` 내부 module을 import하지 않는다.

### 7. PaddleOCR training dry-run runner 보강

`scripts/train_paddleocr_finetuned_models.py`를 로컬 `PaddleOCR-main` source checkout에 맞게 보강했다.

변경 내용:

- 기본 detection/recognition model config는 glob 추정이 아니라 공식 상대 경로로 먼저 검증한다.
- source checkout에 `tools/train.py`, `tools/eval.py`, `tools/export_model.py`가 없으면 fail-fast한다.
- Local Mac CPU 기준 dry-run command에 다음 override를 넣는다.
  - `Global.use_gpu=False`
  - `Global.distributed=False`
  - detection batch size `1`, worker `0`
  - recognition batch size `4`, worker `0`
- dry-run은 train/eval/export command만 출력하고 실제 학습 subprocess를 시작하지 않는다.

실제 확인:

- `--paddleocr-source-dir ../PaddleOCR-main` dry-run에서 detection/recognition config가 정확히 resolve됐다.
- output command에는 CPU override가 포함됐다.
- 실제 train/eval/export는 실행하지 않았다.

### 8. 실제 naver 라벨 데이터셋 300장 private annotation queue 생성

외부 원본 데이터셋을 읽기 전용으로 스캔해 PaddleOCR fine-tuning 검수용 queue를 만들었다.

입력:

- `/Volumes/Corsair EX300U Media/00_work_out/00_data_set/pr/downloads_tampermonkey/lemon-aid/_inbox/tampermonkey/naver`

출력:

- `backend/data/private/paddleocr_finetuning/2026-05-17/annotation_queue.json`
- `backend/data/private/paddleocr_finetuning/2026-05-17/public_report.json`
- `backend/data/private/paddleocr_finetuning/2026-05-17/annotation_queue.html`
- `backend/data/private/paddleocr_finetuning/2026-05-17/images/`

생성 결과:

| 항목 | 값 |
| --- | ---: |
| selected image count | 300 |
| source kind | `detail` 300 |
| product group count | 144 |
| train split | 238 |
| val split | 33 |
| test split | 29 |
| scanner files seen | 2002 |
| unsupported MIME | 26 |
| GIF excluded | 6 |
| too small excluded | 97 |
| duplicate SHA excluded | 373 |
| eligible candidates before selection | 1500 |

redaction 확인:

- 원본 절대경로 저장 안 함
- 원본 파일명 저장 안 함
- raw OCR text 저장 안 함
- provider raw payload 저장 안 함
- API credential 저장 안 함
- image bytes를 JSON에 저장 안 함

실행 중 발견한 문제와 수정:

- 일부 초대형 상세 이미지가 PIL `DecompressionBombError`를 발생시켰다.
- 이를 decode 실패로 방치하지 않고 `too_large` 이미지로 안전하게 제외하도록 수정했다.
- 106G 전체 스캔을 매번 끝까지 하지 않도록 `상세페이지` 우선 조기 후보 수집을 추가했다.

### 9. Plan D: Parser/domain correction learning

OCR이나 LLM parser를 바로 재학습하기 전에, 사용자가 확정한 수정 결과를 deterministic correction rule로 축적하는 방향을 설계했다.

핵심 구성:

- `ParserCorrectionEvent`
- `DomainCorrectionCandidate`
- `DomainCorrectionRule`
- versioned artifact manifest
- correction type: `ingredient_alias`, `unit_normalization`, `amount_parse`, `ocr_confusion`, `row_association`, `section_anchor`, `nutrient_code_selection`

원칙:

- `UserSupplementCreate.user_confirmed=True` 이후의 확정값만 학습 이벤트가 된다.
- fuzzy match는 자동 적용하지 않고 suggestion/review 상태로 둔다.
- approved rule만 runtime apply 가능하다.
- amount가 없으면 만들지 않는다. unit만 보인다고 amount를 추정하지 않는다.

팀이 알아야 할 의미:

- 이 기능은 없는 성분/함량을 생성하는 모델이 아니다.
- parser 정확도 개선을 위한 검수된 rule layer다.

### 10. Plan E: 평가, 개인정보, 배포 거버넌스

Plan A-D가 각자 구현되어도 같은 기준으로 평가와 배포 판단을 하도록 공통 governance layer를 설계했다.

핵심 구성:

- `GovernanceGateReport`
- `ArtifactProvenance`
- `RedactedEvaluationReport`
- `PromotionDecision`
- `ConsentRetentionPolicySnapshot`
- release readiness CLI/script

원칙:

- `/readiness`는 configuration-only로 빠르게 유지한다.
- heavy provider smoke, benchmark, artifact checksum 검증은 별도 CLI 또는 CI job에서 수행한다.
- raw image, raw OCR text, raw provider payload, filename, user id는 report에 저장하지 않는다.
- promotion 조건은 primary metric 개선, non-regression, safety metric 0, raw leak 0으로 둔다.

### 11. Supplement analyze action contract 보완 방향

이미지 위험 상황을 단순 warning string이 아니라 사용자 행동으로 연결하기 위해 preview 응답에 구조화된 action contract를 추가하는 방향으로 정리했다.

주요 field:

- `analysis_scope`
- `action_required`
- `detected_product_regions`
- `selected_region_id`
- `missing_required_sections`
- `image_role`
- `multi_image_group_id`
- `identity_conflict`

적용 방향:

- `multi_product`는 제품 영역 선택 필요
- `cover_only`는 identity-only preview
- `partial_table`은 누락 섹션 표시와 추정 금지
- `roi_not_found`는 원본 OCR fallback과 review warning
- `blurred_text`, `glare_or_reflection`, `low_light`, `low_contrast`, `too_small_text`는 retake UX로 연결

### 12. Firebase OCR 테스트 UI 제작 및 보완

초기에는 Firebase Hosting 기반으로 정적 OCR 테스트 UI를 만들었다.

UI 기능:

- 카메라 촬영
- 이미지 첨부
- 여러 장 이미지 선택
- 요청 ID 입력
- barcode 값/형식 입력
- OCR 동의 및 외부 OCR 동의 요청
- 결과 탭에서 status, action, scope, OCR provider, 추출 텍스트, product, quality report, ingredients, warnings, raw JSON 확인
- 모델 1: Google Vision
- 모델 2: PaddleOCR
- 두 모델 비교: 같은 이미지에 두 provider 요청을 순차 실행

초기 문제:

- iPhone에서 카메라 시작 후 placeholder만 남고 video preview가 보이지 않았다.
- Firebase HTTPS 페이지에서 `http://127.0.0.1:8000/api/v1`을 호출해 mixed content와 localhost 해석 문제가 발생했다.

수정:

- `video.srcObject` 설정 후 `video.play()`를 명시 호출하도록 보완했다.
- `hidden` attribute 의존 대신 `.is-camera-active` class 기반으로 placeholder/video 표시를 제어했다.
- `capture="environment"`를 추가해 iOS native camera fallback을 제공했다.
- 실패 시 결과 탭으로 이동해 API 주소, 원인, 다음 조치를 표시하도록 했다.
- `/api/v1/readiness`가 아니라 backend root의 `/ready`를 호출하도록 수정했다.

### 13. ngrok 기반 모바일 테스트 경로 구현

Firebase Hosting만으로는 iPhone에서 로컬 backend를 직접 호출할 수 없기 때문에, ngrok 기반 테스트 경로를 추가했다.

처음 설계:

- frontend 정적 서버: `127.0.0.1:5199`
- backend FastAPI: `127.0.0.1:8000`
- frontend ngrok URL과 backend ngrok URL을 각각 생성

실제 확인된 문제:

- 현재 ngrok 계정/config에서는 두 번째 endpoint 생성 시 `ERR_NGROK_334`가 발생했다.
- 같은 development domain이 이미 사용 중이라 frontend/backend를 별도 터널로 동시에 열 수 없었다.

해결:

- `firebase-ocr-test/dev_ngrok_gateway.py`를 추가했다.
- 하나의 local gateway가 정적 UI를 서빙하고, `/api`, `/ready`, `/health`, `/docs` 계열 요청은 local FastAPI backend로 프록시한다.
- ngrok은 gateway 포트 `5199` 하나만 공개한다.
- UI가 ngrok HTTPS origin에서 열리면 API 기본 주소를 자동으로 `현재 origin + /api/v1`로 잡도록 했다.
- 기존 localStorage에 저장된 `127.0.0.1` API 주소가 있으면 ngrok origin에서는 자동으로 교체하도록 했다.
- API fetch에는 `ngrok-skip-browser-warning: 1` header를 자동 추가한다.
- backend CORS 허용 header에도 `ngrok-skip-browser-warning`을 추가했다.

현재 모바일 테스트 URL:

- UI: `https://phasic-cammy-chorial.ngrok-free.dev`
- API 기본 주소: `https://phasic-cammy-chorial.ngrok-free.dev/api/v1`

주의: ngrok 무료/dev URL은 실행 상태와 계정 설정에 따라 바뀔 수 있다. 다음 실행 때 URL이 바뀌면 README runbook 기준으로 다시 확인해야 한다.

## 현재 실행 중인 테스트 프로세스

보고서 작성 시점 기준으로 아래 프로세스가 실행 중이다.

| 용도 | 주소 | PID |
| --- | --- | ---: |
| FastAPI backend | `127.0.0.1:8000` | `53139` |
| local ngrok gateway | `127.0.0.1:5199` | `66753` |
| ngrok inspector | `127.0.0.1:4040` | `48132` |

테스트가 끝나면 공개 노출을 닫기 위해 아래처럼 종료한다.

```bash
kill 66753 53139 48132
```

## 검증 결과

오늘 확인한 검증 결과는 다음과 같다.

| 검증 | 명령 또는 확인 내용 | 결과 |
| --- | --- | --- |
| UI JavaScript 문법 | `node --check yeong-Lemon-Aid/firebase-ocr-test/public/app.js` | pass |
| Python lint | `ruff check yeong-Lemon-Aid/firebase-ocr-test/dev_ngrok_gateway.py ...` | pass |
| Python lint - PaddleOCR queue/runner | `ruff check scripts/train_paddleocr_finetuned_models.py scripts/prepare_paddleocr_finetuning_queue.py ...` | pass |
| Python format | `black -W 1 --check` 대상 파일 개별 실행 | pass |
| Python format - PaddleOCR queue/runner | `black --check scripts/train_paddleocr_finetuned_models.py scripts/prepare_paddleocr_finetuning_queue.py ...` | pass |
| Type check | `mypy yeong-Lemon-Aid/firebase-ocr-test/dev_ngrok_gateway.py yeong-Lemon-Aid/backend/Nutrition-backend/src/main.py` | pass |
| Security middleware unit test | `pytest -o addopts='' yeong-Lemon-Aid/backend/Nutrition-backend/tests/unit/test_security_middleware.py -q` | `10 passed` |
| Diff whitespace | `git diff --check -- ...` | pass |
| OCR/learning/scripts/config acceptance | `./.venv/bin/python -m pytest Nutrition-backend/tests/unit/ocr Nutrition-backend/tests/unit/learning Nutrition-backend/tests/unit/scripts Nutrition-backend/tests/unit/test_config.py -q --no-cov` | `207 passed` |
| PaddleOCR runtime probe | `./.venv/bin/python scripts/probe_paddleocr_runtime.py --image-path Nutrition-backend/tests/fixtures/supplement_labels/images/ko_dense_table_001.png` | `ok=true`, `text_line_count=14`, `layout_available=true` |
| PaddleOCR-main dry-run | `./.venv/bin/python scripts/train_paddleocr_finetuned_models.py --paddleocr-source-dir ../PaddleOCR-main --dataset-dir /private/tmp/lemon-paddleocr-dryrun-dataset --dry-run` | source/config resolve pass, training not started |
| 300장 private queue 생성 | `./.venv/bin/python scripts/prepare_paddleocr_finetuning_queue.py --source-root "<naver>" --output-dir data/private/paddleocr_finetuning/2026-05-17 --max-source-images 300` | `selected_image_count=300` |
| ngrok readiness | `GET https://phasic-cammy-chorial.ngrok-free.dev/ready` | `200` |
| analyze route reachability | `POST https://phasic-cammy-chorial.ngrok-free.dev/api/v1/supplements/analyze` without image | expected `422 missing image` |
| remote UI JS 확인 | ngrok `app.js`에서 `runtimeDefaultApiBaseUrl`, `ngrok-skip-browser-warning` 확인 | pass |

초기 ngrok 테스트 시점의 `/ready` 상태:

- overall: `degraded`
- `google_vision_ocr`: `ready`
- `local_ocr`: `not_configured`
- `clova_ocr`: `not_configured`
- `rate_limit`: `ready`
- `auth`: `development_auth_disabled`

해석:

- 모델 1 Google Vision 테스트는 현재 설정상 가능하다.
- 당시 모델 2 PaddleOCR 테스트는 UI에는 선택지가 있지만 backend runtime이 아직 켜져 있지 않아 실패 안내가 나오는 상태였다.
- `AUTH_MODE=disabled`는 임시 공개 테스트용이며 운영 배포 설정이 아니다.

이후 업데이트:

- 코드 기본값은 `OCR_PRIMARY_PROVIDER=paddleocr`, `ENABLE_LOCAL_OCR=true`로 바뀌었다.
- PaddleOCR runtime probe는 local fixture 기준 성공했다.
- 단, 현재 실행 중인 backend 프로세스가 예전 env로 떠 있으면 `/ready` 출력은 재시작 전까지 이전 상태를 보여줄 수 있다.

## 주요 변경 파일 묶음

### OCR 테스트 UI 및 ngrok

- `firebase-ocr-test/public/index.html`
- `firebase-ocr-test/public/styles.css`
- `firebase-ocr-test/public/app.js`
- `firebase-ocr-test/README.md`
- `firebase-ocr-test/dev_ngrok_gateway.py`
- `firebase-ocr-test/firebase.json`
- `firebase-ocr-test/.firebaserc`

### Backend runtime/security/readiness

- `backend/Nutrition-backend/src/main.py`
- `backend/Nutrition-backend/src/config.py`
- `backend/Nutrition-backend/src/services/readiness.py`
- `backend/Nutrition-backend/src/models/schemas/readiness.py`
- `backend/Nutrition-backend/src/middleware/rate_limit.py`
- `backend/.env.example`
- `backend/Nutrition-backend/tests/unit/test_security_middleware.py`
- `backend/Nutrition-backend/tests/unit/test_config.py`

### OCR provider/layout/parser

- `backend/Nutrition-backend/src/ocr/providers/google_vision.py`
- `backend/Nutrition-backend/src/ocr/providers/paddle.py`
- `backend/Nutrition-backend/src/ocr/factory.py`
- `backend/Nutrition-backend/src/ocr/base.py`
- `backend/Nutrition-backend/src/parsing/`
- `backend/Nutrition-backend/src/models/schemas/label_layout.py`
- `backend/Nutrition-backend/src/models/schemas/supplement_layout_context.py`
- `backend/Nutrition-backend/src/services/supplement_layout_context.py`

### 이미지 품질, ROI, 학습 manifest

- `backend/Nutrition-backend/src/models/schemas/image_quality.py`
- `backend/Nutrition-backend/src/services/supplement_image_quality.py`
- `backend/Nutrition-backend/src/services/supplement_image_risk_actions.py`
- `backend/Nutrition-backend/src/learning/roi_manifest.py`
- `backend/Nutrition-backend/src/models/schemas/paddleocr_finetuning.py`
- `backend/Nutrition-backend/src/learning/paddleocr_finetuning.py`
- `backend/scripts/prepare_paddleocr_finetuning_queue.py`
- `backend/scripts/serve_paddleocr_annotation_queue.py`
- `backend/scripts/export_paddleocr_finetuning_dataset.py`
- `backend/scripts/train_paddleocr_finetuned_models.py`
- `backend/scripts/probe_paddleocr_runtime.py`
- `backend/data/private/paddleocr_finetuning/2026-05-17/` (gitignored private artifact, 커밋 금지)

### PaddleOCR source 적용 보호

- `.gitignore`
- `PaddleOCR-main/` (gitignored external source checkout, 커밋 금지)
- `PaddleOCR-main.zip` (gitignored archive, 커밋 금지)

### Parser/domain correction 및 governance

- `backend/Nutrition-backend/src/models/schemas/parser_domain_correction.py`
- `backend/Nutrition-backend/src/services/parser_domain_correction.py`
- `backend/Nutrition-backend/src/services/nutrient_code_matcher.py`
- `backend/Nutrition-backend/src/models/schemas/governance.py`
- `backend/Nutrition-backend/src/services/governance.py`
- `backend/scripts/evaluate_release_governance.py`
- `backend/scripts/evaluate_domain_correction_rules.py`

### 오늘 작성한 설계 문서

- `Brand-New-update/2026-05-17-supplement-label-image-risk-brainstorm.md`
- `Brand-New-update/2026-05-17-plan-a-paddleocr-local-layout-normalization-detail-plan.md`
- `Brand-New-update/2026-05-17-plan-b-roi-image-quality-learning-implementation.md`
- `Brand-New-update/2026-05-17-plan-c-paddleocr-finetuning-detail-plan.md`
- `Brand-New-update/2026-05-17-plan-d-parser-domain-correction-learning-detail-plan.md`
- `Brand-New-update/2026-05-17-plan-e-cross-cutting-governance-detail-plan.md`
- `Brand-New-update/2026-05-17-paddleocr-learning-accuracy-design-plan.md`

## 팀이 알아야 할 현재 상태

### 완료에 가까운 것

- 모바일 카메라 preview는 iPhone에서 보이도록 수정했다.
- 여러 이미지 업로드와 촬영 이미지 누적 UI가 들어갔다.
- 모델 1 Google Vision, 모델 2 PaddleOCR, 두 모델 비교 선택 UI가 들어갔다.
- Firebase/localhost 실패 원인을 UI가 설명하도록 바꿨다.
- ngrok 하나로 UI와 backend API를 같이 테스트하는 gateway를 만들었다.
- Google Vision provider는 readiness 기준 `ready` 상태다.
- `/ready`와 `/api/v1/supplements/analyze` 라우트가 ngrok을 통해 backend까지 도달하는 것을 확인했다.
- PaddleOCR local primary 기본값 전환이 코드와 테스트에 반영됐다.
- PaddleOCR 실제 import/predict probe가 fixture 이미지 기준 성공했다.
- `PaddleOCR-main` source checkout은 학습 runner dry-run에서 det/rec config resolve까지 확인됐다.
- 실제 naver 라벨 데이터셋에서 300장 private annotation queue가 생성됐다.
- private queue와 PaddleOCR source/zip은 `.gitignore`로 커밋 대상에서 제외했다.

### 아직 남은 것

- 현재 떠 있는 backend 프로세스가 오래된 env를 사용 중이면 PaddleOCR 기본값 반영을 위해 재시작이 필요하다.
- 실제 영양제 라벨 이미지로 Google Vision end-to-end 추출 성공 여부를 한 번 더 확인해야 한다.
- 여러 이미지는 현재 비교/반복 요청 테스트 중심이며, 여러 장을 하나의 제품 분석으로 병합하는 backend merge 정책은 별도 구현/검증이 필요하다.
- ROI 영역 선택 UI는 action contract와 연결할 다음 단계가 남아 있다.
- 300장 queue는 아직 annotation queue 상태이며, 사람 검수된 `human_verified=true` box/transcript가 필요하다.
- human-verified manifest가 생긴 뒤에만 PaddleOCR detection/recognition export와 실제 학습 dry-run 이후 train/eval/export를 진행한다.
- Firebase live 배포 대신 ngrok 임시 테스트로 전환했으므로, 운영 공유용 배포는 Cloud Run 또는 정식 HTTPS backend가 필요하다.
- 현재 공개 테스트는 `AUTH_MODE=disabled`이므로 테스트 종료 후 ngrok/backend를 반드시 내려야 한다.

## 다음 작업 제안

1. iPhone에서 현재 ngrok URL로 실제 영양제 라벨 이미지를 촬영해 모델 1 Google Vision 결과를 확인한다.
2. backend를 재시작한 뒤 모델 2 PaddleOCR이 실제 API 요청에서도 `paddleocr_local` 결과 또는 명확한 OCR error를 반환하는지 확인한다.
3. 300장 private queue에서 우선 20~30장만 사람 검수해 `verified_manifest.json`를 만들고 export dry-run을 실행한다.
4. 같은 이미지 세트로 모델 1과 모델 2를 비교하고, 결과 report에는 raw image/raw OCR full text를 저장하지 않는다.
5. `image_quality_report`와 `action_required`를 모바일 UI에서 retake/add-photo/select-region 상태로 더 명확히 렌더링한다.
6. 여러 장 라벨 이미지를 `front_label`, `supplement_facts`, `ingredients`, `precautions`, `barcode` 역할로 묶는 multi-image group 정책을 backend에 연결한다.
7. 커밋 전에는 오늘 생성된 planning docs, backend 구현, 테스트 UI 파일, PaddleOCR queue/runner 구현을 서로 다른 commit scope로 나누는 것이 좋다.

## 커밋 메시지 제안

아직 바로 커밋하지 않았지만, 커밋할 경우 아래처럼 나누는 것이 좋다.

```text
docs(ocr): add supplement label OCR risk and model governance plans

Explain the Plan A-E design decisions for PaddleOCR, ROI quality, fine-tuning,
parser correction, and release governance so the team can review implementation
scope without mixing runtime changes into planning artifacts.
```

```text
feat(ocr-ui): add mobile OCR test UI with model comparison

Provide a lightweight browser UI for camera capture, multi-image upload, Google
Vision versus PaddleOCR selection, and readable OCR result inspection so mobile
testing can happen before the full app flow is ready.
```

```text
fix(ocr-ui): support ngrok mobile backend testing

Avoid iPhone localhost and mixed-content failures by serving the UI and proxying
FastAPI through a single ngrok HTTPS origin, while preserving explicit error
messages for invalid API settings.
```

```text
feat(ocr): make PaddleOCR the local primary provider

Use PaddleOCR as the default supplement-label OCR provider while keeping Google
Vision behind explicit external OCR opt-in, so local OCR can be tested without
sending label images to a vendor by default.
```

```text
feat(data): prepare private PaddleOCR fine-tuning queue

Scan the consented naver label dataset into a gitignored 300-image annotation
queue with redacted metadata only, so human-verified detection and recognition
labels can be collected before any model training.
```
