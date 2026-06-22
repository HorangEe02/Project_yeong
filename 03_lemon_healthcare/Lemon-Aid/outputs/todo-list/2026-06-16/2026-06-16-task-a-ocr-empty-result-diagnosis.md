# 작업 A 진단 — 영양제 OCR 빈-결과/지연 (2026-06-16)

> 결론: **라이브 OCR 파이프라인이 PaddleOCR-primary로 플립된 상태이고, 사용자가 재학습해 마운트한 Paddle 인식 모델이 추론 중 네이티브 SIGSEGV(세그폴트)로 백엔드 워커를 크래시**시킨다. 그래서 영양제 분석이 결과 없이 실패(빈-결과)하고, 크래시→Docker 재시작 사이클이 지연을 가중한다. 근본원인·수정은 전적으로 사용자 foreign WIP(Paddle 재학습/통합) 영역이라 코드 미수정 — **진단·권고만**.

## 1. 증상 (사용자 보고 + 실측)
- 앱 영양제 분석 → "성분 후보가 비어 있어 다시 확인이 필요해요"(빈 추출) + 느림(~54s).
- 핸드오프(2026-06-16, OCR/figma)는 이 시점 라이브를 **CLOVA-only(Paddle off)**로 기록했으나 — **그 사이 라이브가 바뀜**(아래).

## 2. 라이브 파이프라인 실측 (`docker exec lemon-aid-backend-1 env`)
핸드오프/메모리와 **정반대로 플립됨**:
- `OCR_PRIMARY_PROVIDER=paddleocr` (핸드오프=clova)
- `ENABLE_LOCAL_OCR=true` (핸드오프=false)
- `OCR_SECONDARY_MERGE_POLICY=low_confidence` (신규 secondary-merge 단계 활성)
- `LOCAL_OCR_TEXT_RECOGNITION_MODEL_DIR=/app/models/paddleocr-rec` + `..._SECONDARY_..._DIR=/app/models/paddleocr-rec-secondary`
- `LOCAL_OCR_TEXT_DET_UNCLIP_RATIO=2.5`, `LOCAL_OCR_MODEL_PROFILE=server_detection`, `LOCAL_OCR_TEXT_DET_LIMIT_SIDE_LEN=3072`
- `ENABLE_CLOVA_OCR=true`, `ENABLE_MULTIMODAL_VERIFICATION=false`, `MULTIMODAL_OCR_ASSIST_POLICY=disabled`
- `OLLAMA_MODEL=qwen3.5:9b`(파서), `OLLAMA_VISION_MODEL=gemma4:e4b`
- Paddle 모델 마운트 확인: `/app/models/paddleocr-rec/{inference.json,inference.pdiparams(8.1MB),inference.yml}` — **2026-06-16 04:49 생성(오늘, 사용자 재학습 익스포트, PIR inference.json 포맷)**.

## 3. 재현 (실측)
- 테스트 이미지: `outputs/generated/supplement-learning/2026-06-04/operator-review/images/review-pii/review-ocr-gt-01578fd0972a0899adbf.jpg` (NOW 블리스터 실 영양제 사진).
- ⚠️ 원본 3024×4032=12.2M픽셀 > 백엔드 12M 한도 → **HTTP 413** `payload_too_large`(모바일은 업로드 전 다운스케일). 1200×1600으로 리사이즈 후 재시도.
- `POST /api/v1/supplements/analyze -F image=@...` → **HTTP 000(연결 끊김) · 32.5s**.
- 백엔드 로그에 PaddleOCR **C++ 세그폴트 스택**:
  ```
  paddle::AnalysisPredictor::ZeroCopyRun(bool)
   → NaiveExecutor::RunInterpreterCore → PirInterpreter::Run → ... → PhiKernelInstruction::Run
   → phi::ConvKernel<float, CPUContext> → phi::funcs::Im2ColFunctor<...>
  FatalError: `Segmentation fault` is detected by the operating system.
  SIGSEGV received by PID 1
  ```
- `docker inspect`: **`1 restarts`, started 07:35:17Z** (세그폴트 07:34 → 컨테이너 죽음 → Docker 재시작). 직후 `/health` 200(healthy).
- 최근 로그에 **SIGSEGV/AnalysisPredictor 크래시 3회** = 재현성 있음(일회성/이미지 특정 아님 — Paddle conv 커널 런타임 크래시라 이미지 내용 무관, analyze가 Paddle를 타면 크래시).

## 4. 근본원인
PaddleOCR 인식 추론(`AnalysisPredictor::ZeroCopyRun`)이 **conv/Im2Col 단계에서 네이티브 SIGSEGV**로 죽는다. PID 1(uvicorn) 크래시 → Docker restart. 요청은 결과 없이 끊김 → 앱은 "빈-결과". 핸드오프 §2.2의 "깨끗한 성분표 = 정상 추출(Magnesium Citrate)"은 **CLOVA-primary 시절** 결과 — Paddle 플립이 회귀를 만들었다.
- 전형적 원인 후보(Paddle 도메인): 익스포트 모델 vs 런타임 Paddle **버전/포맷(PIR) 불일치**, 모델 아키텍처/전처리 mismatch, 손상된 export, CPU 명령셋(AVX 등) 이슈.
- **네이티브 세그폴트라 Python try/except의 CLOVA 폴백이 못 잡음** → 프로세스째 죽음.

## 5. 권고 (전부 foreign/ops 영역 — 코드 미수정)
1. **즉시 언블록(ops)**: `OCR_PRIMARY_PROVIDER=clova`(+필요시 `ENABLE_LOCAL_OCR=false`)로 되돌려 CLOVA 경로 사용(핸드오프 실측상 정상 추출). 단 `docker-compose.yml`은 사용자 WIP라 사용자가 결정.
2. **Paddle 모델/런타임 수정(사용자 도메인)**: 익스포트 모델을 **요청 경로 밖 standalone PaddleOCR predict**로 로드·추론해 세그폴트 재현/격리; Paddle 버전 vs export 포맷(PIR inference.json) 정합 확인; 필요시 재export.
3. **Paddle 격리(아키텍처 완화)**: Paddle predict를 **별도 서브프로세스/워커**로 분리하면 SIGSEGV가 API 워커를 죽이지 않아 CLOVA 폴백이 가능. 단 service/factory 계층(foreign WIP) 수정 필요.

## 6. 지연(~54s) 메모
- 주범 후보: Paddle 모델 로드 + **세그폴트→재시작 사이클** + Ollama 파서(qwen3.5:9b) **외장 Corsair 드라이브 로드**([[ocr-analyze-latency-and-docker-caveat]]). CLOVA 복귀해도 Ollama 외장 로드 지연은 잔존 → `OLLAMA_MODELS` 내장 디스크 이전/사전워밍업 권고(ops).

## 7. 비고
- 백엔드 12M 픽셀 한도(`payload_too_large`)는 정상 가드 — 모바일 다운스케일 전제.
- 이 진단은 **코드 변경 0**(전부 foreign Paddle/ops). 모바일 빈-결과 UI("성분 후보가 비어 있어요")는 합당한 empty-state, 모바일 버그 아님.
