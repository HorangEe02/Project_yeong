# CAD 도면 AI 학습 데이터 파이프라인 - 프로젝트 가이드

## 1. 프로젝트 개요

자동차/산업 부품 도면(DXF)을 AI가 이해할 수 있도록 가공하는 파이프라인.
DXF 파일 읽기 → 이미지 변환 → 특성 추출 → YOLO 라벨 생성 → 벡터 DB 등록 → VLM 분석까지의 전체 워크플로우를 구현한다.

---

## 2. 디렉토리 구조

```
CAD/
├── main/drawing-llm/          ← 핵심 프로젝트 (DrawingLLM)
│   ├── core/
│   │   ├── llm.py             ← Ollama VLM 인터페이스 (qwen3-vl)
│   │   ├── vector_store.py    ← ChromaDB 벡터 DB (이미지+텍스트 하이브리드)
│   │   ├── embeddings.py      ← CLIP(이미지) + E5(텍스트) 임베딩 (비대칭 prefix)
│   │   ├── ocr.py             ← PaddleOCR + EasyOCR 이중화
│   │   ├── pipeline.py        ← 등록/검색/분석 오케스트레이터
│   │   ├── evaluation.py      ← 검색 정확도 평가 (ground_truth 기반)
│   │   ├── benchmark.py       ← 성능 벤치마크 (등록/검색 속도 측정)
│   │   └── weight_tuner.py    ← 하이브리드 검색 가중치 최적화
│   ├── app/
│   │   └── streamlit_app.py   ← 웹 UI (대시보드, 등록, 검색, 분석)
│   ├── tests/                  ← pytest 테스트 (118개, Phase D-2)
│   │   ├── conftest.py         ← 공통 mock fixtures
│   │   ├── test_ocr.py         ← OCR 순수 함수 테스트
│   │   ├── test_security.py    ← 보안/입력 검증 테스트
│   │   ├── test_embeddings.py  ← E5 prefix/디바이스 테스트
│   │   ├── test_vector_store.py ← VectorStore CRUD 테스트
│   │   ├── test_pipeline.py    ← Pipeline 통합 테스트
│   │   └── test_llm.py         ← LLM 인터페이스 테스트
│   └── config/
│       └── settings.py        ← 환경 설정
│
├── cad_me/
│   └── cad_crawling_pipeline.py  ← 데이터 파이프라인 (DXF→PNG→YOLO→증강)
│
├── qwen3/
│   ├── llm.py                 ← 멀티모델 LLM (qwen3-vl, glm-4.7 등)
│   └── settings.py
│
├── data/
│   ├── MiSUMi_data/           ← MiSUMi 산업부품 DXF (58카테고리, 61,451파일)
│   ├── MiSUMi_png/            ← MiSUMi PNG 변환 결과 (B-1에서 생성)
│   ├── Unit_bearing_data/     ← 유닛 베어링 DWG (15카테고리, 463파일)
│   ├── Unit_bearing_dxf/      ← 베어링 DXF 변환 결과 (461파일, B-3에서 생성)
│   ├── Unit_bearing_png/      ← 베어링 PNG 변환 결과 (461파일, B-3에서 생성)
│   ├── cad_pipeline/
│   │   ├── misumi_labels/     ← YOLO 라벨 (B-2에서 생성)
│   │   └── misumi_dataset/    ← train/val/test 분할 데이터셋
│   └── drawing-llm-with-data/ ← DrawingLLM 샘플 데이터
│
├── B1_MiSUMi_대량등록/         ← Phase B-1: DXF→PNG→ChromaDB 배치 파이프라인
│   ├── convert_dxf_to_png.py  ← DXF→PNG 배치 변환 (resume, 멀티프로세스)
│   ├── register_to_chromadb.py ← PNG→ChromaDB 배치 등록 (CLIP+OCR)
│   └── check_progress.py      ← 카테고리별 진행 상황 대시보드
│
├── B2_YOLO_학습/               ← Phase B-2: YOLO 학습 데이터셋 구축
│   ├── generate_yolo_labels.py ← 58클래스 YOLO 라벨 자동 생성
│   ├── prepare_dataset.py      ← Stratified train/val/test 분할
│   ├── train_yolo.py           ← YOLOv8n 학습 (MPS GPU)
│   ├── analyze_overfitting.py  ← 과적합 분석 + 시각화
│   ├── evaluate_test.py        ← Test set 평가 (best.pt)
│   └── misumi_class_map.json   ← 58개 클래스 매핑
│
├── B3_Unit_bearing/            ← Phase B-3: DWG→DXF→PNG 파이프라인
│   └── convert_dwg_to_dxf.py  ← ODA File Converter 기반 DWG 변환
│
├── C1_VLM_비교/                 ← Phase C-1: VLM 모델 비교
│   ├── compare_vlm.py          ← VLM 모델 비교 스크립트
│   └── results/                ← 비교 결과 JSON
│
├── C3_VLM_텍스트강화/            ← Phase C-3: 텍스트 임베딩 강화
│   ├── enhance_text_embeddings.py ← VLM 카테고리 설명 생성 + 재임베딩
│   ├── generate_keywords.py     ← 72카테고리 한영 키워드 매핑
│   ├── test_e5_model.py         ← E5 vs MiniLM 임베딩 모델 비교
│   ├── upgrade_to_e5.py         ← E5 모델 전체 재임베딩 스크립트
│   ├── run_full_evaluation.py   ← Ground Truth 전체 평가
│   ├── run_weight_tuning.py     ← E5 적용 후 가중치 재튜닝
│   └── results/                 ← 비교/평가 결과 JSON
│
├── runs/misumi_yolo/           ← YOLO 학습 결과
│   ├── train/                  ← 100 epoch 학습 (완료)
│   │   ├── weights/            ← best.pt, last.pt, epoch*.pt
│   │   ├── results.csv         ← epoch별 메트릭
│   │   └── overfitting_analysis.png ← 과적합 분석 그래프
│   ├── test_eval/              ← Test set 평가 결과
│   └── train_5ep_backup/       ← 5 epoch 테스트 백업
│
├── yolo_epoch_runner.sh         ← YOLO 1-epoch-per-run Runner (외부 드라이브용, 구버전)
├── yolo_epoch_runner_local.sh   ← YOLO 1-epoch-per-run Runner (로컬 경로용, 현재 사용 중)
├── yolo_watchdog.sh            ← YOLO 학습 자동 재시작 Watchdog (구버전)
├── yolo_runner_local.log       ← Epoch Runner 상태 로그
├── yolo_watchdog.log           ← Watchdog 상태 로그 (구버전)
│
├── P0_GrabCAD/                ← Phase 0: GrabCAD 데이터 수집 스크립트
├── P1_배치 등록.../            ← Phase 1: 배치 등록, 검색 테스트, 평가 메트릭
├── P2_성능 벤치마크.../        ← Phase 2: 임베딩 가중치 튜닝, 벤치마크
└── PROJECT_GUIDE.md           ← 이 문서
```

---

## 3. 환경 설정

### conda 환경

```bash
conda activate ml     # Python 3.13.11
```

### 주요 패키지 버전

| 패키지 | 버전 | 용도 |
|---|---|---|
| torch | 2.10.0 | 딥러닝 프레임워크 |
| streamlit | 1.53.0 | 웹 UI |
| ezdxf | 1.4.3 | DXF 파일 파싱 |
| chromadb | 1.5.1 | 벡터 데이터베이스 |
| sentence-transformers | 5.2.3 | 텍스트 임베딩 |
| albumentations | 2.0.8 | 데이터 증강 |
| opencv (cv2) | 4.12.0 | 이미지 처리 |
| clip | 1.0 | CLIP 이미지 임베딩 (OpenAI) |
| easyocr | 1.7.2 | OCR 폴백 엔진 |
| ultralytics | 8.4.15 | YOLOv8 학습/추론 |
| pydantic-settings | 2.13.1 | 환경 설정 관리 |
| httpx | 0.28.1 | Ollama API 호출 |
| loguru | 0.7.3 | 로깅 |

### Ollama (로컬 LLM)

```bash
ollama serve                    # 서버 시작 (별도 터미널)
ollama list                     # 설치된 모델 확인
```

설치된 모델 (2026-03-06 기준):

| 모델 | 크기 | 유형 | 용도 |
|---|---|---|---|
| **qwen3.5:9b** | 6.1GB | VLM (Vision) | 메인 도면 분석 (설명, Q&A) |
| **qwen3.5:9b** | 6.6GB | VLM (Vision 내장) | 보조 분석, 한국어 설명 |
| **translategemma** | 3.3GB | VLM (Gemma3 Vision) | 경량 고속 분류/요약, 번역 |
| **translategemma:12b** | 8.1GB | VLM (Gemma3 Vision) | 정밀 분류/요약 (대형 버전) |
| **glm-ocr** | 2.2GB | Vision OCR 전용 | 도면 텍스트 고속 추출 |
| glm-4.7-flash | 19.0GB | 텍스트 전용 | Vision 미지원 (TIMEOUT) |
| deepseek-r1:8b | 5.2GB | 텍스트 전용 | 추론/코딩 |
| qwen3.5:4b | 3.4GB | 텍스트 전용 (소형) | 경량 텍스트 처리 |

---

## 4. 지금까지 완료한 작업

### 4-1. 데이터 정리 및 통합

- [x] 중복 zip 파일 삭제, 빈 폴더 정리, `.DS_Store` 제거
- [x] 8,000+ 파일 zip 해제 (Shift-JIS 일본어 파일명 포함)
- [x] 모든 데이터를 `data/` 폴더로 통합
- [x] MiSUMi 58카테고리 61,432개 DXF 파일 정상 확인

### 4-2. 보안 취약점 수정

**`app/streamlit_app.py`**
- [x] 파일 업로드 경로 탐색 공격 방어 (`_sanitize_filename()`)
- [x] 배치 디렉토리 경로 검증 (`_validate_batch_path()`)
- [x] 임시 파일을 시스템 temp 디렉토리 + UUID로 변경

**`core/llm.py`**
- [x] 프롬프트 인젝션 방어 (`_sanitize_user_input()`)
- [x] 이미지 파일 확장자 화이트리스트 (png, jpg, jpeg, tiff, bmp, webp)
- [x] 이미지 파일 크기 제한 (최대 50MB)
- [x] thinking 모델(qwen3) 대응: `num_predict` 8192 + thinking fallback

### 4-3. 버그 수정

**`core/vector_store.py`**
- [x] `.tolist()` 호출 시 Python list와 numpy ndarray 모두 지원
- [x] 빈 metadata `{}` 전달 시 ChromaDB 에러 방어

**`cad_crawling_pipeline.py`**
- [x] 중복 DXF 파싱 제거 (`get_drawing_bounds`에 `df=` 파라미터 추가)
- [x] `Config.BASE_DIR` 경로를 프로젝트 루트 기준으로 변경
- [x] albumentations deprecated 파라미터 수정 (`value`→`fill`, `var_limit`→`std_range`)

### 4-4. 환경 구성

- [x] conda `ml` 환경에 누락 패키지 설치 (loguru, chromadb, sentence-transformers)
- [x] 추가 패키지 설치: clip (OpenAI), easyocr, pydantic-settings
- [x] OpenCV 동적 라이브러리 체인 수정 (openjpeg, krb5)
- [x] OpenMP 중복 라이브러리 경고 해결 (conda activate/deactivate 스크립트로 `KMP_DUPLICATE_LIB_OK=TRUE` 자동 설정)

### 4-5. 검증 테스트 결과

| 테스트 | 결과 |
|---|---|
| streamlit 보안 유틸리티 | PASS |
| LLM 프롬프트 인젝션 방어 | PASS |
| 모듈 임포트 (6개 클래스) | PASS |
| VectorStore CRUD + 하이브리드 검색 | PASS |
| cad_crawling_pipeline demo 모드 | PASS |
| MiSUMi 58카테고리 DXF 읽기 | 58/58 PASS |
| DXF→PNG 변환 | 10/10 PASS |
| YOLO 라벨 생성 | 5/5 PASS |
| 데이터 증강 (albumentations) | PASS |
| Ollama VLM 텍스트+이미지 | PASS |

### 4-6. Phase A 완료 (단기 작업)

#### A-1. OpenMP 중복 라이브러리 경고 해결 ✅

- [x] conda activate/deactivate 스크립트 생성
  - `/opt/anaconda3/envs/ml/etc/conda/activate.d/omp_fix.sh` → `export KMP_DUPLICATE_LIB_OK=TRUE`
  - `/opt/anaconda3/envs/ml/etc/conda/deactivate.d/omp_fix.sh` → `unset KMP_DUPLICATE_LIB_OK`
- [x] `conda activate ml` 시 자동 적용 확인

#### A-2. Streamlit 웹 UI 실행 확인 ✅

- [x] 누락 패키지 설치: clip, easyocr, pydantic-settings
- [x] Ollama 모델명 통일: `llava:7b` → `qwen3.5:9b` (`settings.py`, `pipeline.py`)
- [x] DrawingPipeline 전체 초기화 테스트 PASS
- [x] Streamlit 앱 실행 확인 (HTTP 200 OK)

#### A-3. P0/P1/P2 스크립트 호환성 수정 ✅

- [x] 7개 스크립트 `BASE_DIR` 수정: `Path(__file__).parent.parent` → `Path(__file__).parent.parent / "main" / "drawing-llm"`
- [x] `verify_p0.py` 모델명 수정: `llava:7b` → `qwen3.5:9b`, thinking 모델 응답 처리 추가
- [x] 3개 모듈 `core/`로 복사: `evaluation.py`, `benchmark.py`, `weight_tuner.py`
- [x] P0 검증: 9/10 통과 (경고 1건: 샘플 데이터 미등록 — 정상)
- [x] P1/P2 전체 스크립트 구문 검사 + 모듈 임포트: ALL PASS

### 4-7. Phase B 스크립트 구현 (데이터 파이프라인 확장)

#### B-1. MiSUMi 대량 등록 파이프라인 ✅ (DXF→PNG + ChromaDB 등록 전체 완료)

3개 스크립트 작성 및 전체 실행:

- [x] `B1_MiSUMi_대량등록/convert_dxf_to_png.py` — DXF→PNG 배치 변환
  - ezdxf + matplotlib 렌더링 (DPI 150, figsize 8×8)
  - resume 지원 (기존 PNG 자동 스킵), 멀티프로세스 (`--workers N`)
- [x] `B1_MiSUMi_대량등록/register_to_chromadb.py` — PNG→ChromaDB 등록
  - CLIP 이미지 임베딩 + EasyOCR 텍스트 추출 → ChromaDB 등록
  - resume 지원, 100건마다 자동 저장, use_llm=False (속도 우선)
- [x] `B1_MiSUMi_대량등록/check_progress.py` — 카테고리별 진행 상황 대시보드

**DXF→PNG 실행 결과 (2026-02-24):**

| 항목 | 값 |
|---|---|
| 전체 DXF | 61,451개 |
| 성공 | 61,380개 (99.88%) |
| 실패 | 71개 (손상된 DXF: MODEL_SPACE 누락 47건, 부동소수점 오류 20건, 기타 4건) |
| 소요 시간 | 77.4분 (workers=4) |
| 속도 | 카테고리별 1~35 file/s (DXF 복잡도 의존) |

**ChromaDB 등록 결과 (2026-02-26 완료):**

| 항목 | 값 |
|---|---|
| 등록 성공 | **61,473개** (MiSUMi 61,012 + 베어링 461) |
| 등록 실패 | **0건** |
| 소요 시간 | 총 ~31시간 (3회 실행, crash 복구 포함) |
| 평균 속도 | 1.73초/파일 |
| DB 크기 | 436MB (`main/drawing-llm/data/vector_store/`) |

ChromaDB 컬렉션:

| 컬렉션 | 문서 수 |
|---------|---------|
| `drawings_image` | 61,473 (CLIP 이미지 임베딩) |
| `drawings_text` | 61,012 (OCR 텍스트 임베딩) |

> **참고:** 등록 중 프로세스 crash로 SQLite DB가 손상되었으나, `sqlite3 .recover` 명령으로 데이터 손실 없이 복구 후 재개 완료.

```bash
# 실행 방법
python B1_MiSUMi_대량등록/convert_dxf_to_png.py --workers 4
python B1_MiSUMi_대량등록/register_to_chromadb.py
python B1_MiSUMi_대량등록/check_progress.py
```

#### B-2. YOLO 학습 데이터셋 구축 ✅ (데이터셋 완료, 100 epoch 학습 진행 중)

- [x] `B2_YOLO_학습/generate_yolo_labels.py` — YOLO 라벨 자동 생성
  - 58개 MiSUMi 클래스 자동 매핑 (`misumi_class_map.json`)
  - DXF 기하 분석 + PNG 기반 bbox 추출 (폴백)
  - **전체 실행: 61,380/61,380 성공 (100%)**
- [x] `B2_YOLO_학습/prepare_dataset.py` — Stratified train/val/test 분할
  - 80/10/10 비율, 클래스별 균형 유지
  - **전체 실행: train 45,768 / val 6,069 / test 6,182**
- [x] `B2_YOLO_학습/train_yolo.py` — ultralytics YOLOv8n 학습
  - MPS 디바이스 (Apple Silicon), early stopping (patience=20)
  - resume 지원, 매 epoch 체크포인트 (save_period=1)
  - MPS 메모리 정리 콜백 (`_mps_cleanup_callback`): epoch마다 `torch.mps.empty_cache()` + `gc.collect()`

**5 Epoch 테스트 결과 (2026-02-25):**

| Epoch | mAP@50 | mAP@50-95 | Precision | Recall | cls_loss |
|-------|--------|-----------|-----------|--------|----------|
| 1 | 0.168 | 0.164 | 0.580 | 0.188 | 3.500 |
| 2 | 0.268 | 0.266 | 0.576 | 0.264 | 2.082 |
| 3 | 0.581 | 0.580 | 0.704 | 0.527 | 1.407 |
| 4 | 0.680 | 0.678 | 0.750 | 0.620 | 0.982 |
| **5** | **0.710** | **0.709** | **0.773** | **0.630** | **0.728** |

- 5 epoch 테스트 백업: `runs/misumi_yolo/train_5ep_backup/`

**100 Epoch 본격 학습 (2026-02-26~03-06, ✅ 완료):**

| Epoch | mAP@50 | mAP@50-95 | Precision | Recall | cls_loss |
|-------|--------|-----------|-----------|--------|----------|
| 1 | 0.281 | 0.267 | 0.567 | 0.289 | 3.0963 |
| 5 | 0.625 | 0.618 | 0.773 | 0.546 | 1.3542 |
| 10 | 0.756 | 0.751 | 0.776 | 0.699 | 0.8899 |
| 20 | 0.812 | 0.808 | 0.771 | 0.766 | 0.6189 |
| 30 | 0.813 | 0.808 | 0.772 | 0.764 | 0.5600 |
| 40 | 0.812 | 0.808 | 0.763 | 0.767 | 0.5165 |
| 50 | 0.814 | 0.810 | 0.774 | 0.761 | 0.4742 |
| 64 | 0.813 | 0.809 | 0.766 | 0.765 | 0.4119 |
| 80 | 0.807 | 0.804 | 0.753 | 0.770 | 0.3439 |
| 90 | 0.805 | 0.801 | 0.711 | 0.809 | 0.3080 |
| 95 | 0.820 | 0.817 | 0.739 | 0.812 | 0.3590 |
| **99** | **0.825** | **0.822** | **0.742** | **0.819** | **0.3364** |
| 100 | 0.825 | 0.822 | 0.742 | 0.819 | 0.3372 |

- 모델: yolov8n.pt (3M params, 8.3 GFLOPs)
- 설정: batch=8, imgsz=640, patience=20, save_period=1, workers=0
- 결과 저장: `runs/misumi_yolo/train/`
- **best.pt 최종 성능: mAP@50=0.825, mAP@50-95=0.822 (epoch 99)**
- epoch당 소요 시간: ~51분 (학습 ~43분 + val ~8분)
- **성능 추이:** epoch 50까지 급상승(0.814) → epoch 80~90 일시 하락(0.805) → epoch 95~100 재상승(0.825). 후반부에 Recall이 0.76→0.82로 크게 개선되며 최종 best 갱신

> **MPS 메모리 누수 대응:** Apple M4 Pro 24GB에서 MPS 디바이스로 장시간 학습 시 메모리 누수 발생 (RSS 7GB+, 스왑 20GB+). 2 epoch 이상 연속 실행 시 스왑 폭증으로 속도가 3~8시간/epoch까지 저하됨. `yolo_epoch_runner_local.sh`로 **1 epoch마다 프로세스 kill → 60초 메모리 회복 → resume** 방식으로 항상 정상 속도(~53분/epoch)를 유지한다.

> **경로 마이그레이션 (2026-03-03):** 학습 초기에는 외부 드라이브(`<EXTERNAL_DRIVE>/...`)에서 진행했으나, 드라이브 미연결 상태에서 학습 재개를 위해 로컬 경로(`~/00_work_out/CAD/`)로 마이그레이션 완료. `dataset_misumi.yaml`과 `last.pt` 체크포인트 내부 경로를 모두 패치함.

```bash
# 실행 방법
python B2_YOLO_학습/generate_yolo_labels.py --no-dxf   # PNG 기반 라벨 (빠름)
python B2_YOLO_학습/prepare_dataset.py --copy            # 데이터셋 분할
python B2_YOLO_학습/train_yolo.py --epochs 100           # 본격 학습
python B2_YOLO_학습/train_yolo.py --resume --epochs 100  # crash 후 이어서 학습
```

#### B-3. Unit_bearing DWG 통합 ✅ (전체 실행 완료)

- [x] `B3_Unit_bearing/convert_dwg_to_dxf.py` — DWG→DXF→PNG→ChromaDB 파이프라인
  - ODA File Converter 기반 (DWG는 바이너리 포맷, ezdxf 불가)
  - 463개 DWG (15개 카테고리: UCP, UCF, UCFL, UKFL, UCFC, UKFC 등)
  - 서브커맨드: `dwg2dxf`, `dxf2png`, `register`, `all`

**실행 결과 (2026-02-24):**

| 단계 | 결과 | 소요 시간 |
|---|---|---|
| DWG→DXF (ODA) | 461/463 성공 (99.6%) | 2.8분 |
| DXF→PNG (ezdxf+matplotlib) | 461/461 성공 (100%) | ~1.5분 |
| ChromaDB 등록 (CLIP+OCR) | 461/461 성공 (100%) | ~8.5분 |

- 실패 2건: UCF207.DWG, UCF209.DWG (ODA 출력 없음 — 원본 파일 손상 추정)
- 벡터 스토어: 이미지 임베딩 61,473건 (MiSUMi 61,012 + 베어링 461)
- 15개 베어링 카테고리 전체 등록: UCP(78), SN(53), UCF(55), UCFL(37), UCT(38) 등

---

## 5. 앞으로 해야 할 작업

---

### Phase B 실행 (대량 데이터 처리) — ✅ 전체 완료

#### 완료된 항목

| 단계 | 상태 | 결과 |
|---|---|---|
| B-1 DXF→PNG | ✅ 완료 | 61,380/61,451 (99.88%), 77분 |
| B-1 ChromaDB 등록 | ✅ 완료 | **61,473건**, 실패 0, DB 436MB |
| B-2 YOLO 라벨 | ✅ 완료 | 61,380/61,380 (100%) |
| B-2 데이터셋 분할 | ✅ 완료 | train 45,768 / val 6,069 / test 6,182 |
| B-2 YOLO 5 epoch 테스트 | ✅ 완료 | mAP@50=0.710, best.pt 5.9MB |
| B-3 전체 파이프라인 | ✅ 완료 | DWG→DXF→PNG→ChromaDB 461파일 |

#### 완료

| 단계 | 상태 | 비고 |
|---|---|---|
| B-2 YOLO 100 epoch 학습 | ✅ 완료 | 100/100 epoch (best mAP@50=0.825 @epoch99), 2026-03-06 03:08 완료 |

---

### Phase C: 모델 & 성능 최적화 — C-1~C-3 완료

#### YOLO 과적합 분석 ✅ (2026-03-06)

epoch 50~90 구간의 성능 정체가 과적합인지 분석.

**분석 결과:**
- **Train vs Val Loss Gap**: Box loss gap이 ep50(0.012) → ep90(0.024)으로 소폭 증가 — 경미한 과적합 조짐
- **close_mosaic 효과**: epoch 91에서 train loss 급감(0.088→0.045)은 YOLOv8의 `close_mosaic=10` 정상 동작 (mosaic 증강 비활성화)
- **Test Set 평가**: mAP@50=**0.836** > Val mAP@50=0.825 → **과적합 없음, 일반화 양호**

| 세트 | mAP@50 | mAP@50-95 | Precision | Recall |
|---|---|---|---|---|
| Val (epoch 99) | 0.825 | 0.822 | 0.742 | 0.819 |
| **Test** | **0.836** | **0.833** | **0.798** | **0.788** |

**Test Set Per-class AP@50 (Top/Bottom 5):**

| Top 5 | AP@50 | Bottom 5 | AP@50 |
|---|---|---|---|
| Set_Collars | 0.995 | Pipe_Frames | 0.348 |
| Holders_for_Shaft | 0.995 | Cover_Panels | 0.405 |
| Inspections | 0.995 | Pulls | 0.475 |
| Heaters | 0.995 | Washers | 0.510 |
| Conveyors | 0.995 | Angles | 0.547 |

결론: **심각한 과적합 없음.** epoch 50~90 정체는 mosaic 증강 환경에서의 정상적인 학습 plateau이며, close_mosaic 비활성화 후 성능 재상승.

스크립트: `B2_YOLO_학습/analyze_overfitting.py`, `B2_YOLO_학습/evaluate_test.py`
시각화: `runs/misumi_yolo/train/overfitting_analysis.png`

#### C-1. VLM 모델 비교 평가 ✅ (2026-03-06)

Ollama에 설치된 VLM 모델들의 도면 이미지 분석 성능을 비교. MiSUMi 도면(Shafts, Gears, Couplings, Springs, Brackets) + 베어링(UCP) 총 6개 카테고리 × 3개 태스크(영문 설명, 분류, 한국어 설명) 테스트.

**1차 비교 (6이미지 × 3태스크):**

| 모델 | Vision | Describe 속도 | Classify 정확도 | Korean 품질 |
|---|---|---|---|---|
| **qwen3.5:9b** | ✅ | 97.2s/img | 2/6 (33%) | 일부 누락(0 chars) |
| glm-4.7-flash | ❌ TIMEOUT | N/A | N/A | N/A |

**2차 추가 모델 테스트 (glm-ocr, qwen3.5, translategemma):**

신규 설치한 3개 모델의 Vision 지원 여부를 `model_info`의 `vision.*` 아키텍처 존재 여부와 실제 이미지 추론 테스트로 판별.

| 모델 | 크기 | Vision | 역할 | Classify | Korean | 속도 |
|---|---|---|---|---|---|---|
| **qwen3.5:9b** | 6.1GB | ✅ VL 전용 | 도면 분석 (메인) | 2/6 (33%) | 상세하나 빈응답 가능 | 63.5s/task |
| **qwen3.5:9b** | 6.6GB | ✅ 내장 | 도면 분석 (보조) | △ (thinking 모델) | ✅ 고품질 | 58~89s |
| **translategemma** | 3.3GB | ✅ Gemma3 | 경량 분석 + 번역 | △ (1/2) | ✅ 자연스러움 | ⚡ 2~9s |
| **glm-ocr** | 2.2GB | ✅ OCR 전용 | 도면 텍스트 추출 | ❌ (텍스트만 반환) | ❌ (텍스트만 반환) | ⚡ 0.3~7s |
| glm-4.7-flash | 19.0GB | ❌ | 사용 불가 | N/A | N/A | TIMEOUT |
| deepseek-r1:8b | 5.2GB | ❌ | 텍스트 전용 | N/A | N/A | N/A |

**모델별 상세 분석:**

**qwen3.5:9b (메인 VLM)**
- 도면 설명이 가장 상세 (평균 4,878 chars). 치수, 특징, 용도까지 체계적 분석
- Thinking 모델 특성으로 `num_predict` 부족 시 빈 응답 → 최소 4096 이상 설정 필요
- 분류 정확도 낮음: DXF→PNG 도면의 시각적 특성이 부족하여 Shafts→screw, Gears→shaft 등 오분류

**qwen3.5:9b (보조 VLM)**
- `qwen35.vision.*` 아키텍처 내장으로 Vision 지원 확인 (model_info에서 image_token_id, vision.block_count 등 존재)
- 한국어 품질이 우수: 부품 종류/특징/용도를 항목별로 체계적 분석
- Thinking 모델이라 num_predict=512에서는 빈 응답, 2048+ 필요
- qwen3-vl과 유사 수준이나 속도가 약간 느림

**translategemma (경량 고속 VLM)**
- Gemma3 기반 (`gemma3.vision.*` + `mm.tokens_per_image=256`), 번역 특화이면서 Vision도 지원
- **속도가 압도적**: 2~9초/task (qwen3-vl 대비 10~30배 빠름)
- 한국어 응답이 자연스럽고 구조적 (부품 종류/특징을 항목별 정리)
- 분류는 혼재 (Gears→gear ✅, Shafts→Other ❌)
- **12b 버전(8.1GB)**도 설치되어 있어 정확도 향상 가능

**glm-ocr (OCR 전문)**
- `glmocr.vision.*` 아키텍처로 이미지 입력은 처리하나, **텍스트 추출만 수행** (도면 내 문자열 나열)
- "도면을 분석해주세요" → "M5, M4, M6, PSFCG20-82-F8-P8-M5" (치수/모델번호만 반환)
- 도면 "이해/분석" 불가. 하지만 **OCR 보조 도구로서 EasyOCR보다 빠르고 정확할 가능성**
- 현재 ChromaDB 등록 시 EasyOCR로 텍스트를 추출하는데, glm-ocr로 대체하면 텍스트 임베딩 품질 향상 기대

**향후 VLM 활용 계획:**

```
┌──────────────────────────────────────────────────────────────┐
│  도면 분석 파이프라인 VLM 역할 분담 (계획)                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. OCR 텍스트 추출 ─── glm-ocr (2.2GB, <1s)                │
│     → 도면 내 치수/모델번호/주기사항 고속 추출                    │
│     → EasyOCR 대체 또는 보조로 사용                             │
│                                                              │
│  2. 빠른 분류/요약 ─── translategemma (3.3GB, 2~9s)          │
│     → 대량 도면 배치 처리 시 1차 분류                            │
│     → 실시간 검색 결과 미리보기 설명 생성                         │
│                                                              │
│  3. 상세 도면 분석 ─── qwen3.5:9b (6.1GB, ~60s)            │
│     → 개별 도면 상세 분석, Q&A 대화                             │
│     → 가장 정확한 설명 생성 (포트폴리오 시연용)                    │
│                                                              │
│  4. 교차 검증 ─── qwen3.5:9b (6.6GB, ~70s)                  │
│     → qwen3-vl과 다른 아키텍처로 교차 검증                       │
│     → 한국어 품질이 좋아 한국어 설명 생성에 우선 활용               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**이 접근법을 선택한 이유:**
1. **단일 모델 한계 극복**: qwen3.5:9b만으로는 속도(63.5s/task), 분류 정확도(33%), 한국어 빈응답 문제가 있음
2. **역할 분담으로 효율화**: OCR(glm-ocr) → 1차 분류(translategemma) → 상세 분석(qwen3-vl) 파이프라인 구성 시, 6만건 배치 처리가 현실적 시간 내 가능
3. **비용 최소화**: 모든 모델이 Ollama 로컬 실행으로 API 비용 없음. M4 Pro 24GB에서 3.3~6.6GB 모델 교대 로드 가능
4. **검색 성능 개선 기대**: 현재 OCR(EasyOCR)이 추출하는 텍스트가 치수/기호 위주라 검색 성능이 낮음(Recall@5=0.146). glm-ocr + translategemma로 의미 있는 텍스트(부품 설명)를 생성하여 텍스트 임베딩 품질 향상 가능

스크립트: `C1_VLM_비교/compare_vlm.py`
결과: `C1_VLM_비교/results/vlm_comparison_20260306_101452.json`

#### C-2. 임베딩 가중치 튜닝 ✅ (2026-03-06)

MiSUMi 58개 + 베어링 15개 카테고리에 대한 Ground Truth (142개 쿼리)로 하이브리드 검색 가중치 최적화.

**1차 Grid Search (MiniLM 모델, C-3 이전):**

| Image Weight | Text Weight | MRR | Recall@5 | Composite |
|---|---|---|---|---|
| 0.0 | **1.0** | **0.263** | **0.146** | **0.223** |
| 0.5 | 0.5 | 0.263 | 0.146 | 0.223 |
| 0.7 | 0.3 | 0.202 | 0.131 | 0.165 |
| 1.0 | 0.0 | 0.060 | 0.047 | 0.048 |

**2차 Grid Search (E5 모델 적용 후, C-3 이후):**

| Image Weight | Text Weight | MRR | Recall@5 | Recall@10 | Composite |
|---|---|---|---|---|---|
| 0.0 | **1.0** | **0.742** | **0.372** | **0.747** | **0.629** |
| 0.1~0.7 | 0.3~0.9 | 0.742 | 0.372 | 0.747 | 0.629 |
| 0.8 | 0.2 | 0.072 | 0.057 | 0.113 | 0.058 |
| 1.0 | 0.0 | 0.061 | 0.050 | 0.106 | 0.051 |

**최적 가중치: image=0.0, text=1.0** (텍스트 전용이 최적, E5 적용 전후 동일)

- `config/settings.py` 업데이트 완료 (image_weight: 0.5→**0.0**, text_weight: 0.5→**1.0**)
- E5 모델은 I:0.0~0.7 구간에서 성능이 동일 (텍스트가 압도적으로 지배)
- I:0.8 이상에서 급격한 성능 하락 → CLIP 이미지 임베딩 품질이 텍스트 대비 낮음
- 카테고리별: Casters만 이미지 가중치(I:1.0)가 유리, 나머지 72개 카테고리는 텍스트 전용 최적

**E5 적용 전후 비교:**

| 메트릭 | MiniLM (1차) | E5-small (2차) | 개선 |
|---|---|---|---|
| MRR | 0.263 | **0.742** | +182% ✅ |
| Recall@5 | 0.146 | **0.372** | +155% |
| Recall@10 | N/A | **0.747** | - |
| Composite | 0.223 | **0.629** | +182% |

Ground Truth: `main/drawing-llm/data/ground_truth_misumi.json` (142쿼리)
튜닝 결과: `C3_VLM_텍스트강화/results/e5_weight_tuning.json`

#### C-3. 텍스트 임베딩 강화 ✅ (2026-03-06)

검색 성능의 병목이 텍스트 임베딩 품질임을 확인하고, 임베딩 모델 교체 + 키워드 강화로 대폭 개선.

**문제 진단:**
- `paraphrase-multilingual-MiniLM-L12-v2` 모델의 한국어 처리 능력이 부족
- 저장된 텍스트가 OCR 치수/기호 위주로 의미 있는 검색어와 매칭 실패
- 한국어 Recall@5 ≈ 0 (사실상 한국어 검색 불가)

**실패한 접근 (3가지 전략):**

| 전략 | 방법 | Recall@5 | 결과 |
|---|---|---|---|
| Strategy 1 | VLM 긴 설명 + OCR | 0.100 | ❌ 악화 |
| Strategy 2 | 키워드 전용 (OCR 제거) | 0.100 | ❌ 악화 |
| Strategy 3 | 키워드 + OCR | 0.200 | ❌ 악화 |
| 원본 | `f"{ocr_text} {category}"` | 0.400 (샘플) | 기준선 |

→ **결론: MiniLM 모델 자체가 한계.** 키워드/설명 품질이 아닌 임베딩 모델이 병목.

**해결: E5 모델 교체**

`intfloat/multilingual-e5-small` 선택 이유:
1. 기존과 동일 384차원 → ChromaDB 컬렉션 재생성 불필요
2. 비대칭 prefix 시스템 (`passage:` / `query:`) → retrieval 전용 설계
3. 다국어(한/영/일) 성능이 MiniLM 대비 대폭 우수

**모델 비교 테스트 (20개 쿼리, 6개 카테고리):**

| 구성 | MiniLM | E5 (no prefix) | E5 + prefix | E5 + prefix + keywords |
|---|---|---|---|---|
| Top-1 정확도 | 85% | 100% | 100% | **100%** |
| 영문 | 90% | 100% | 100% | 100% |
| 한국어 | 80% | 100% | 100% | 100% |

**전체 재임베딩:**
- 61,473건 E5 모델 + 키워드 강화 + "passage:" prefix로 재임베딩
- 키워드 매핑: 72개 카테고리 한영 키워드 (`generate_keywords.py`)
- 저장 텍스트 형식: `"passage: {keywords} {ocr_text}"`
- 소요 시간: 62초 (MiniLM 대비 동급)

**전체 평가 결과 (142쿼리):**

| 메트릭 | MiniLM (Before) | E5-small (After) | 목표 | 달성 |
|---|---|---|---|---|
| MRR | 0.263 | **0.735** | ≥ 0.70 | ✅ |
| Recall@5 | 0.146 | **0.369** | ≥ 0.80 | ❌ |
| Recall@10 | N/A | **0.739** | ≥ 0.90 | ❌ |
| Precision@5 | N/A | **0.730** | - | - |
| 영문 MRR | N/A | 0.681 | - | - |
| 한국어 MRR | N/A | **0.789** | - | - |
| 영문 Recall@5 | ~0.29 | 0.343 | - | - |
| 한국어 Recall@5 | ~0 | **0.394** | - | - |
| 평균 응답 시간 | N/A | 0.101s | - | - |

**실패 쿼리 분석 (37개/142):**
- 대부분 Top-5가 단일 오답 카테고리로 집중 (키워드 유사도가 높은 다른 카테고리에 매칭)
- 예: "gear spur helical bevel" → Timing_Pulleys (5/5), "bracket mounting plate" → Holders_for_Shaft (5/5)
- Recall@10에서는 0.739로 크게 개선 → 올바른 카테고리가 6~10위에 존재
- 원인: 카테고리당 수백~수천건의 동일 키워드가 검색 결과를 독점하는 "키워드 그룹핑 효과"

**파이프라인 코드 업데이트:**
- `core/embeddings.py`: TextEmbedder 클래스 전면 개편 (E5 prefix 자동 적용, `embed()` = query, `embed_passage()` = passage)
- `config/settings.py`: `text_embedding_model = "intfloat/multilingual-e5-small"`
- `core/pipeline.py`: 도면 등록 시 `embed_passage()` 사용

**향후 개선 방향:**
- Recall@5 목표(0.80) 미달 → 카테고리 다양성 보장 로직 (Top-K에서 동일 카테고리 제한)
- E5-base (768-dim) 모델로 업그레이드 시 discriminative power 향상 기대
- 실패 37개 카테고리의 키워드 정밀 조정

스크립트: `C3_VLM_텍스트강화/` 디렉토리 전체
평가 결과: `C3_VLM_텍스트강화/results/e5_evaluation_full.json`

#### C-4. GrabCAD 데이터 확보 (미착수)

`P0_GrabCAD/`에 수집 스크립트가 준비되어 있다. 실제 산업 도면 데이터를 추가 확보하면 모델 일반화 성능이 향상된다.

---

### Phase D: 프로덕션 준비 (D-1, D-2 완료)

#### D-1. 에러 핸들링 강화 ✅

5개 core 파일에 17개 CRITICAL 에러 핸들링 추가 완료:

| 파일 | 추가 항목 |
|---|---|
| `streamlit_app.py` | LLM 호출 3곳 try/except, 파일 업로드 에러, 배치 등록 에러, `[오류]` 소프트에러 감지 |
| `vector_store.py` | ChromaDB 초기화 에러, upsert 실패 처리, 검색 쿼리 에러→빈 결과, 하이브리드 검색 graceful degradation, `except: pass` 안티패턴 제거, reset 에러 |
| `pipeline.py` | `_save_records()` 원자적 쓰기 (임시파일→rename), `shutil.copy2()` 파일 복사 에러 |
| `embeddings.py` | CLIP/E5 모델 로딩 RuntimeError catch, GPU OOM 자동 CPU 폴백, 배치 OOM 개별 처리 폴백 |
| `llm.py` | `response.json()` 파싱 에러, 이미지 파일 읽기 OSError (동기+비동기 모두) |

#### D-2. 테스트 코드 정식화 ✅

pytest 기반 테스트 인프라 구축 + **118개 테스트 전체 통과** (1.30초):

```
tests/                      118 tests, 0 failures
├── conftest.py             공통 fixtures (mock embedder/VS/LLM, 샘플 이미지)
├── test_ocr.py             부품번호/치수/재질 추출 순수 함수 (~31개)
├── test_security.py        파일명 새니타이징, 경로 검증, 프롬프트 인젝션 방어 (~28개)
├── test_embeddings.py      E5 prefix 로직, 디바이스 선택, mock 통합 (~15개)
├── test_vector_store.py    CRUD, 검색, 하이브리드, 에러 핸들링 (~18개)
├── test_pipeline.py        등록, 배치, 원자적 쓰기, 통계 (~9개)
└── test_llm.py             생성, 인코딩, 헬스체크, 분류, Q&A (~16개)
```

실행: `cd main/drawing-llm && python -m pytest tests/ -v`

#### D-3. Docker 패키징 (미착수)

Ollama + ChromaDB + Streamlit을 docker-compose로 묶어 배포 환경 구성.
> **블로커:** macOS MPS GPU는 Docker 컨테이너에서 사용 불가. CUDA 서버 또는 CPU 전용으로 구성 필요.

---

### Phase E: ML 학습용 공학 도면 데이터셋 구축 — ✅ 완료 (2026-03-08)

DrawingLLM의 도면 분류/분석 성능 향상을 위해 외부 공개 데이터 소스에서 자동차/기계 부품 공학 도면을 대규모로 수집. `drawing-datasets/` 디렉토리에 9개 소스, **72,730장** 이미지, **34GB** 규모의 학습 데이터셋 구축.

#### E-1. USPTO PPUBS 특허 도면 수집 ✅

`drawing-datasets/patents/collect_uspto_ppubs.py` — USPTO PPUBS 특허 도면 수집

| 항목 | 값 |
|---|---|
| 수집 이미지 | **3,254 PNG** |
| IPC 코드 | 14개 (B60B~B60T, F16B~F16L) |
| 용량 | 2.7GB (patents/ 전체) |
| 라이선스 | Public Domain |

**IPC 코드별 상세:**

| IPC 코드 | 부품 유형 | 이미지 수 |
|---|---|---|
| B60B | 차륜/캐스터 | 228 |
| B60C | 타이어 | 79 |
| B60D | 연결장치 | 71 |
| B60G | 서스펜션 | 280 |
| B60K | 동력전달 | 220 |
| B60R | 부속품 | 128 |
| B60T | 브레이크 | 390 |
| F16B | 볼트/너트 | 192 |
| F16C | 베어링 | 797 |
| F16D | 클러치 | 223 |
| F16H | 기어 | 338 |
| F16J | 피스톤 | 61 |
| F16K | 밸브 | 160 |
| F16L | 파이프 | 87 |

#### E-2. Google Patents 도면 수집 ✅

`drawing-datasets/patents/collect_google_patents.py` — Google Patents에서 수집

- 510 PNG 이미지, 27MB
- 라이선스: Public Domain

#### E-3. GrabCAD 커뮤니티 도면 수집 ✅

`drawing-datasets/grabcad/collect_grabcad.py` — 15개 카테고리, **799 JPG**, 111MB

| 카테고리 | 수 | 카테고리 | 수 |
|---|---|---|---|
| bearing | 97 | brake_caliper | 100 |
| bolt_nut_fastener | 55 | disc_brake | 100 |
| engine_valve | 78 | gear_transmission | 52 |
| pipe_fitting | 60 | piston_cylinder | 71 |
| wheel_hub | 100 | differential | 43 |
| shaft_coupling | 23 | suspension | 10 |
| clutch | 7 | turbocharger | 2 |
| spring_mechanical | 1 | | |

라이선스: GrabCAD Community (비상업적 사용 주의)

#### E-4. Kaggle 데이터셋 수집 ✅

`drawing-datasets/kaggle/collect_kaggle.py`

| 데이터셋 | 이미지 | 포맷 | 라이선스 |
|---|---|---|---|
| 2D Engineering Drawings | 7 JPG | 실제 산업용 스캔 도면 | CC0 Public Domain |
| Airbag CAD Drawing | **60,000 PNG** | 에어백 합성 CAD 도면 | CC BY 4.0 |

#### E-5. 미군 기술 매뉴얼 도면 추출 ✅

`drawing-datasets/archive_org/collect_military_tm.py` — Archive.org TM 9 시리즈

| 항목 | 값 |
|---|---|
| 원본 PDF | 30개 (TM 9 시리즈) |
| 추출 이미지 | **5,825 PNG** |
| 용량 | 3.1GB |
| 라이선스 | Public Domain (17 U.S.C. §105) |
| 내용 | 부품 도면, 분해도, 조립도, 일부 텍스트 위주 페이지(부품 목록표) 포함 |

#### E-6. 합성 공학 도면 생성 ✅

**기본 합성 도면** (`drawing-datasets/synthetic/generate_drawings.py`):
- 1,000 PNG, 59MB, 6개 부품 유형 (shaft, flange, housing, bracket, valve, gear), 3개 스타일

**향상된 합성 도면** (`drawing-datasets/synthetic/generate_enhanced.py`):
- **1,332 PNG**, **25GB** (200 DPI, 8~12MB/장)
- 8개 부품 유형: adapter(100), housing(100), shaft_assembly(100), flange_coupling(108), valve_body(260), bracket_mount(218), pulley(200), cover_plate(200)
- 특징: 다중 뷰 레이아웃(정면/측면/평면/단면), 완전한 타이틀 블록, 스캔 효과 시뮬레이션(blueprint/aged/photocopy/clean_scan), 치수선, 공차, 표면 거칠기 기호, 단면 해칭, 숨겨진 선, 중심선

#### E-7. DeepPatent2 메타데이터 분석 ✅

`drawing-datasets/deeppatent2/collect_deeppatent2.py`

- 원본 데이터셋: 314GB (1.4M 특허 × 2개 페이지)
- 분석 결과: 자동차/기계 IPC 코드 해당 항목 **735K건** 식별
- 실제 다운로드: 미수행 (용량 부담). 메타데이터 분석만 완료

#### E-8. Wikimedia Commons CC 이미지 수집 ✅

`drawing-datasets/google_images/collect_cc_drawings.py`

- 3장 (JPG/PNG), 20MB
- 라이선스: Creative Commons (개별 파일별 확인 필요)

#### 데이터셋 종합 현황

| 데이터셋 | 이미지 수 | 포맷 | 용량 | 라이선스 |
|---|---|---|---|---|
| USPTO PPUBS | 3,254 | PNG | 2.7GB | Public Domain |
| Google Patents | 510 | PNG | 27MB | Public Domain |
| GrabCAD | 799 | JPG | 111MB | Community |
| Kaggle 2D | 7 | JPG | 20MB | CC0 |
| Kaggle Airbag | 60,000 | PNG | 2.2GB | CC BY 4.0 |
| Military TMs | 5,825 | PNG | 3.1GB | Public Domain |
| Synthetic (기본) | 1,000 | PNG | 59MB | 자체 생성 |
| Synthetic (향상) | 1,332 | PNG | 25GB | 자체 생성 |
| Wikimedia CC | 3 | JPG/PNG | 20MB | CC |
| **합계** | **72,730** | — | **~34GB** | — |

라이선스별 분류: Public Domain 9,589장 / CC 60,003장 / 자체 생성 2,332장 / Community 799장

상세 현황: `drawing-datasets/DATASET_SUMMARY.json`

---

## 6. 빠른 실행 가이드

```bash
# 1) 환경 활성화 (KMP_DUPLICATE_LIB_OK=TRUE 자동 설정됨)
conda activate ml

# 2) Ollama 서버 시작 (별도 터미널)
ollama serve

# 3) 데모 파이프라인 실행
cd ~/00_work_out/CAD
python cad_me/cad_crawling_pipeline.py --mode demo

# 4) Streamlit 웹 UI
cd ~/00_work_out/CAD/main/drawing-llm
streamlit run app/streamlit_app.py

# 5) VLM 도면 분석 (CLI)
python -c "
import sys; sys.path.insert(0, '.')
from core.llm import DrawingLLM
llm = DrawingLLM(model='qwen3.5:9b', timeout=180.0)
print(llm.describe_drawing('도면이미지.png'))
"

# 6) MiSUMi 대량 처리 (Phase B)
python B1_MiSUMi_대량등록/convert_dxf_to_png.py --workers 4   # DXF→PNG
python B1_MiSUMi_대량등록/register_to_chromadb.py              # ChromaDB 등록
python B2_YOLO_학습/generate_yolo_labels.py                    # YOLO 라벨
python B2_YOLO_학습/prepare_dataset.py                         # 데이터셋 분할
python B2_YOLO_학습/train_yolo.py --epochs 100                 # YOLO 학습
```

---

## 7. 수정된 파일 목록

| 파일 | 수정 내용 |
|---|---|
| `main/drawing-llm/app/streamlit_app.py` | 보안: 파일명 새니타이징, 배치 경로 검증, 안전한 임시 파일 |
| `main/drawing-llm/core/llm.py` | 보안: 프롬프트 인젝션 방어, 이미지 검증. 기능: thinking 모델 대응, num_predict 증가 |
| `main/drawing-llm/core/vector_store.py` | 버그: list/ndarray 호환, 빈 metadata 방어 |
| `cad_me/cad_crawling_pipeline.py` | 버그: 중복 파싱 제거, 경로 수정. 호환: albumentations API 업데이트 |
| `main/drawing-llm/config/settings.py` | 모델명 변경: llava:7b → qwen3.5:9b |
| `main/drawing-llm/core/pipeline.py` | 모델명 변경: llava:7b → qwen3.5:9b |
| `main/drawing-llm/core/evaluation.py` | P1에서 core/로 복사 (검색 평가 모듈) |
| `main/drawing-llm/core/benchmark.py` | P2에서 core/로 복사 (벤치마크 모듈) |
| `main/drawing-llm/core/weight_tuner.py` | P2에서 core/로 복사 (가중치 튜닝 모듈) |
| `P0_GrabCAD/verify_p0.py` | BASE_DIR 수정, 모델명 변경, thinking 모델 응답 처리 |
| `P1_.../batch_register.py` | BASE_DIR 수정 |
| `P1_.../search_test.py` | BASE_DIR 수정 |
| `P1_.../run_evaluation.py` | BASE_DIR 수정 |
| `P2_.../run_benchmark.py` | BASE_DIR 수정 |
| `P2_.../run_weight_tuning.py` | BASE_DIR 수정 |
| conda activate/deactivate 스크립트 | 신규: OpenMP 경고 자동 해결 |
| `B1_MiSUMi_대량등록/convert_dxf_to_png.py` | 신규: DXF→PNG 배치 변환 (resume, 멀티프로세스) |
| `B1_MiSUMi_대량등록/register_to_chromadb.py` | 신규: PNG→ChromaDB 배치 등록 (CLIP+OCR) |
| `B1_MiSUMi_대량등록/check_progress.py` | 신규: 카테고리별 진행 상황 대시보드 |
| `B2_YOLO_학습/generate_yolo_labels.py` | 신규: 58클래스 YOLO 라벨 자동 생성 (DXF/PNG 기반) |
| `B2_YOLO_학습/prepare_dataset.py` | 신규: Stratified train/val/test 분할 + YAML 생성 |
| `B2_YOLO_학습/train_yolo.py` | 신규: YOLOv8n 학습 스크립트 (MPS GPU) |
| `B2_YOLO_학습/misumi_class_map.json` | 신규: 58개 MiSUMi 클래스 매핑 |
| `B3_Unit_bearing/convert_dwg_to_dxf.py` | 신규: DWG→DXF→PNG→ChromaDB 파이프라인 (ODA 기반) |
| `B2_YOLO_학습/train_yolo.py` | 수정: resume 로직 개선, MPS 메모리 정리 콜백 추가, save_period=1 |
| `yolo_watchdog.sh` | 신규: YOLO 학습 자동 재시작 Watchdog (v1, 구버전) |
| `yolo_epoch_runner.sh` | 신규: 1-epoch-per-run Runner (v2, 외부 드라이브 경로) |
| `yolo_epoch_runner_local.sh` | 신규: 1-epoch-per-run Runner (v3, 로컬 경로, 현재 사용 중) |
| `monitor_tasks.sh` | 신규: 백그라운드 작업 상태 모니터링 스크립트 |
| `data/cad_pipeline/misumi_dataset/dataset_misumi.yaml` | 수정: 외부 드라이브 → 로컬 경로 마이그레이션 |
| `B2_YOLO_학습/analyze_overfitting.py` | 신규: 과적합 분석 + 시각화 (Phase C) |
| `B2_YOLO_학습/evaluate_test.py` | 신규: Test set 평가 스크립트 (Phase C) |
| `C1_VLM_비교/compare_vlm.py` | 신규: VLM 모델 비교 스크립트 (Phase C-1) |
| `main/drawing-llm/data/ground_truth_misumi.json` | 신규: MiSUMi 58+베어링 15 카테고리 Ground Truth (142쿼리) |
| `main/drawing-llm/config/settings.py` | 수정: 최적 가중치 적용 (image=0.0, text=1.0), E5 모델명 변경 |
| `main/drawing-llm/core/vector_store.py` | 수정: metadata None 체크 추가 (line 231) |
| `main/drawing-llm/core/embeddings.py` | 수정: TextEmbedder E5 prefix 지원 (embed/embed_passage/embed_batch) |
| `main/drawing-llm/core/pipeline.py` | 수정: 도면 등록 시 embed_passage() 사용 |
| `C3_VLM_텍스트강화/enhance_text_embeddings.py` | 신규→수정: VLM 설명 생성 + 재임베딩 + 복원 기능 |
| `C3_VLM_텍스트강화/generate_keywords.py` | 신규: 72카테고리 한영 키워드 매핑 |
| `C3_VLM_텍스트강화/test_e5_model.py` | 신규: E5 vs MiniLM 임베딩 모델 비교 테스트 |
| `C3_VLM_텍스트강화/upgrade_to_e5.py` | 신규: E5 모델 전체 재임베딩 (61K건) |
| `C3_VLM_텍스트강화/run_full_evaluation.py` | 신규: Ground Truth 전체 평가 (142쿼리) |
| `C3_VLM_텍스트강화/run_weight_tuning.py` | 신규: E5 적용 후 가중치 재튜닝 |
| `main/drawing-llm/app/streamlit_app.py` | D-1: LLM 호출 에러 핸들링, 배치 등록 에러 처리 |
| `main/drawing-llm/core/vector_store.py` | D-1: ChromaDB 초기화/검색/삭제 에러 핸들링, graceful degradation |
| `main/drawing-llm/core/pipeline.py` | D-1: 원자적 레코드 저장, 파일 복사 에러 처리 |
| `main/drawing-llm/core/embeddings.py` | D-1: GPU OOM 방어, 모델 로딩 에러 확장 |
| `main/drawing-llm/core/llm.py` | D-1: JSON 파싱 에러, 이미지 읽기 에러 (동기+비동기) |
| `main/drawing-llm/requirements.txt` | D-2: pytest>=7.0.0 추가 |
| `main/drawing-llm/pytest.ini` | D-2: 신규 - pytest 설정 |
| `main/drawing-llm/tests/conftest.py` | D-2: 신규 - 공통 mock fixtures |
| `main/drawing-llm/tests/test_ocr.py` | D-2: 신규 - OCR 순수 함수 테스트 (31개) |
| `main/drawing-llm/tests/test_security.py` | D-2: 신규 - 보안/입력 검증 테스트 (28개) |
| `main/drawing-llm/tests/test_embeddings.py` | D-2: 신규 - E5 prefix/디바이스 테스트 (15개) |
| `main/drawing-llm/tests/test_vector_store.py` | D-2: 신규 - VectorStore CRUD/에러 테스트 (18개) |
| `main/drawing-llm/tests/test_pipeline.py` | D-2: 신규 - Pipeline 등록/배치 테스트 (9개) |
| `main/drawing-llm/tests/test_llm.py` | D-2: 신규 - LLM 인터페이스 테스트 (16개) |

---

## 8. 알려진 이슈 및 해결 방법

### macOS MPS 메모리 누수 (YOLO 학습)

**증상:** Apple M4 Pro 24GB에서 MPS 디바이스로 YOLOv8 장시간 학습 시, RSS 메모리가 지속 증가 (3GB → 7.5GB+), 스왑이 20GB까지 팽창. 2 epoch 이상 연속 실행 시 속도가 ~53분/epoch에서 3~8시간/epoch까지 급격히 저하.

**원인:** PyTorch MPS 백엔드의 메모리 관리 이슈 (MPS는 Metal Performance Shaders 기반, GPU 메모리와 시스템 메모리를 공유). `torch.mps.empty_cache()` 콜백만으로는 불충분.

**대응 (Epoch Runner 방식):**
1. `yolo_epoch_runner_local.sh`로 **1 epoch마다 프로세스 kill → 60초 메모리 회복 → resume**
2. `save_period=1`로 매 epoch 체크포인트 저장 (kill 대비)
3. 매 resume 시 체크포인트 패치 (batch=8, workers=0, save_period=1 강제)
4. 연속 실패 10회 시 자동 중단, 타임아웃 1.5시간/epoch
5. YOLO 학습과 ChromaDB CLIP 등록은 **동시 실행 금지** (MPS GPU 경합)

**Runner 변천사:**
- v1 `yolo_watchdog.sh`: crash 감지 후 resume (2~3 epoch마다 crash, 느림)
- v2 `yolo_epoch_runner.sh`: 1 epoch/run 강제 kill (외부 드라이브 경로)
- v3 `yolo_epoch_runner_local.sh`: 로컬 경로 + 체크포인트 경로 자동 패치 (현재 사용 중)

### ChromaDB SQLite 손상 복구

**증상:** 프로세스 비정상 종료 시 `chroma.sqlite3` 파일이 손상 ("database disk image is malformed").

**복구 방법:**
```bash
cd main/drawing-llm/data/vector_store
cp chroma.sqlite3 chroma.sqlite3.corrupted
sqlite3 chroma.sqlite3.corrupted ".recover" | sqlite3 chroma_recovered.sqlite3
mv chroma_recovered.sqlite3 chroma.sqlite3
# 이후 register_to_chromadb.py 재실행 (resume 자동)
```

---

### Phase F: ML 모델 재학습 및 성능 개선 — ✅ 완료 (2026-03-10~11)

#### F-1. 데이터셋 전처리 ✅

외부 수집 데이터(72,730장)를 기존 MiSUMi+베어링 데이터와 통합하여 전처리 데이터셋 구축.

- **통합 카테고리**: 73 → **81 카테고리** (8개 신규: Powertrain, Suspension, Tires 등)
- **전처리 결과**: `drawing-datasets/preprocessed_dataset/`
  - train: 49,337 / val: 6,142 / test: 6,232
- Kaggle Airbag: 60,000 → 1,000 언더샘플링 (클래스 불균형 방지)
- USPTO 고해상도: max 2,000px로 리사이즈

#### F-2. YOLOv8-cls v2 학습 ✅

| 항목 | v1 | v2 |
|---|---|---|
| 카테고리 수 | 73 | **81** |
| Top-1 Accuracy | 96.6% | **93.87%** |
| Top-5 Accuracy | 99.4% | **98.04%** |
| Best Epoch | — | 70/90 (early stop) |
| 학습 시간 | — | 15.7시간 |
| 모델 파일 | `yolo_cls_best.pt` | `yolo_cls_v2_best.pt` (10MB) |
| 학습 설정 | — | MuSGD, imgsz=224, batch=64, workers=0 |

- v1 모델은 `yolo_cls_best.pt`로 보존 (하위 호환)
- Run: `drawing-llm/runs/classify/train_v2_81cls_r2/`

#### F-3. CLIP Fine-tuning ✅

도면 특화 CLIP 모델을 학습하여 이미지 임베딩 품질 개선.

| 항목 | Pre-trained | Fine-tuned | 개선 |
|---|---|---|---|
| i2t R@1 | 0.2% | **3.3%** | 16.5x |
| i2t R@5 | 0.75% | **13.4%** | 17.9x |
| t2i R@5 | 0.9% | **12.7%** | 14.1x |
| i2t R@10 | 1.6% | **22.2%** | 13.9x |
| Category R@5 (i2t) | — | **73.2%** | — |
| Category R@5 (t2i) | — | **94.7%** | — |

- **Best epoch 4** (val_loss=4.315), image tower frozen이 최적
- Unfreezing 시 severe overfitting 발생 (epoch 19에서 중단)
- 모델: `drawing-llm/models/clip_finetuned.pt` (577MB)
- **하이브리드 검색 가중치 변경**: image=0.0, text=1.0 → **image=0.15, text=0.85**
  - CLIP fine-tuning으로 이미지 임베딩이 유의미해져 이미지 가중치 부여 가능

스크립트: `drawing-datasets/training/train_clip.py`
평가: `drawing-datasets/training/evaluate_models.py`

#### F-4. OCR 인식 개선 ✅ (3-전략 적용)

기존 OCR이 부품번호·재질을 잘 인식하지 못하는 문제를 3가지 전략으로 개선:

**전략 B: 파일명 기반 부품번호 추출**
- `core/ocr.py`에 `extract_part_number_from_filename()` 추가
- UUID 접두사(`8자리hex_`) 자동 제거, 최소 3자 이상
- OCR이 부품번호를 못 찾을 때 2차 폴백으로 동작

**전략 E-1: 어두운 배경 도면 전처리**
- `core/ocr.py`에 `_preprocess_invert_if_dark()` 추가
- 평균 밝기 < 128이면 `cv2.bitwise_not()` + Otsu 이진화 적용
- 특허 도면 등 어두운 배경에서 OCR 정확도 향상

**전략 C-1: 카테고리 기반 재질 추론**
- `core/pipeline.py`에 `CATEGORY_MATERIAL_MAP` (75개 카테고리→재질 매핑) 추가
- OCR이 재질을 못 찾을 때 YOLO 분류 카테고리에서 추론
- 예: Shafts → ["S45C", "SUS304"], Gears → ["SCM415", "S45C"]

#### F-5. 메타데이터 일괄 갱신 ✅

68,647건 기존 레코드를 OCR 재실행 없이 1초 내에 메타데이터 보강:

| 항목 | Before | After |
|---|---|---|
| 총 레코드 수 | 68,647 | 68,647 |
| 빈 부품번호 | 60,458건 | **2건** (파일명 3자 미만) |
| 빈 재질 | 66,237건 | **5,516건** (Misc 등 매핑 없는 카테고리) |
| 보강된 부품번호 | — | **+60,456건** (파일명 추출) |
| 보강된 재질 | — | **+60,721건** (카테고리 추론) |

- 백업: `records.json.bak`
- 방식: 파일명→부품번호, 카테고리→재질 매핑 (OCR 재실행 불필요)

#### 코드 변경 사항

| 파일 | 변경 내용 |
|---|---|
| `config/settings.py` | `yolo_cls_model_path` → v2, `clip_finetuned_path` 추가, `image_weight=0.15` |
| `core/embeddings.py` | `finetuned_path` 파라미터로 fine-tuned CLIP 로드 지원 |
| `core/pipeline.py` | `clip_finetuned_path` 전달, `CATEGORY_MATERIAL_MAP` 추가, step 2.8/2.9 추가 |
| `core/ocr.py` | `_preprocess_invert_if_dark()`, `extract_part_number_from_filename()` 추가 |
| `app/streamlit_app.py` | `clip_finetuned_path` 전달 |
| `data/vector_store/records.json` | 68,647건 메타데이터 보강 (부품번호+재질) |

---

*마지막 업데이트: 2026-03-19 (Phase N 완료: v4.0 — YOLO26 + Qwen3.5 자동선택 + OpenCLIP ViT-L/14 768d + GNN R@5=0.765 + DXF 네이티브 + 3채널 하이브리드 검색 + 412 tests)*
