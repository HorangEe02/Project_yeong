# 📐 CAD Vision v5.6

**AI 기반 산업 도면 검색 및 분류 시스템**
Engineering Drawing Retrieval & Classification System powered by Open-Source Multimodal LLM

---

## 기 (起) — 왜 만들었는가

### 제조 현장의 문제

자동차 산업을 비롯한 제조업에서는 완성차 1대에 **약 2만~3만 개의 부품**이 사용되고, 각 부품마다 최소 1장 이상의 기술 도면이 존재한다. OEM(완성차 제조사)과 Tier 1~3 협력사를 포함하면 하나의 차종에 관련된 도면은 **수십만 건**에 달한다.

| 구분 | 규모 |
|---|---|
| 완성차 1개 차종 부품 수 | 20,000 ~ 30,000개 |
| 차종당 관련 도면 수 | 50,000 ~ 100,000건 |
| OEM 전체 관리 도면 수 | 수백만 건 이상 |

이 도면들은 대부분 **파일 서버의 폴더 구조**에 저장되어 있고, 검색 수단은 파일명이나 폴더명에 의존한다. 엔지니어가 필요한 도면을 찾기 위해 **평균 30분~2시간**을 소비하며, 신규 입사자의 경우 도면 분류 체계를 이해하는 데만 **수개월**이 걸린다. 숙련 엔지니어가 퇴직하면 "어떤 도면이 어디에 쓰이는지"에 대한 암묵적 지식이 함께 사라진다.

### 해결하고자 한 것

> "도면을 텍스트로 검색할 수 있으면 어떨까?"

이 질문에서 프로젝트가 시작되었다. 목표는 명확했다:

1. **자연어로 도면을 검색**할 수 있는 시스템 ("M8 볼트" → 관련 도면 즉시 반환)
2. **AI가 도면을 분석**하여 부품명·재질·규격을 자동 추출
3. **비개발자도 실행**할 수 있는 Docker 기반 배포
4. **오픈소스만으로** 구현 (API 비용 없이 로컬에서 완전 동작)

| 지표 | AS-IS | TO-BE | 개선율 |
|---|---|---|---|
| 도면 검색 소요 시간 | 30분 ~ 2시간 | 1분 이내 | ~95% |
| 도면 분류 | 수작업 의존 | 자동 분류 + 검증 | 일관성 확보 |
| 신규 인력 적응 기간 | 3~6개월 | 즉시 활용 가능 | 대폭 단축 |

---

## 승 (承) — 어떻게 만들었는가

### 전체 아키텍처

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         CAD Vision v5.6                                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐   ┌──────────────┐   ┌─────────────────────────┐  │
│  │  Streamlit UI     │   │  Ollama LLM   │   │  ChromaDB               │  │
│  │  Engineering      │──▶│  Qwen3.5:9b   │   │  벡터 DB 3채널          │  │
│  │  Terminal Theme   │   │  (RAM 자동선택)│   │  Image+Text+GNN         │  │
│  │  :8501            │   └──────┬───────┘   └────────┬──────────────┘  │
│  └──────┬───────────┘          │                      │                 │
│         │                      │                      │                 │
│  ┌──────▼──────────────────────▼──────────────────────▼──────────────┐  │
│  │              v5.4 통합 엔진 (Integration Layer)                    │  │
│  │  ┌─────────────┐ ┌───────────────┐ ┌───────────────────────────┐  │  │
│  │  │ CAD Router  │ │Unified Search │ │ VLM Orchestrator          │  │  │
│  │  │ 8포맷 라우팅│ │ 4채널 통합    │ │ LLM 4작업 통합            │  │  │
│  │  │ PNG/DXF/DWG │ │ text+image+   │ │ describe+classify+        │  │  │
│  │  │ STEP/IGES/  │ │ gnn+part_no   │ │ extract_meta+bom          │  │  │
│  │  │ STL         │ │               │ │                           │  │  │
│  │  └─────────────┘ └───────────────┘ └───────────────────────────┘  │  │
│  │  ┌──────────────────┐ ┌──────────────────────────────────────┐    │  │
│  │  │Comparison Engine │ │ Universal Renderer                    │    │  │
│  │  │ 4모드 비교       │ │ thumbnail/full/interactive            │    │  │
│  │  │ DXF/치수/시각/   │ │ + base64 data URI (Drawing Viewer)   │    │  │
│  │  │ 메타데이터       │ │                                      │    │  │
│  │  └──────────────────┘ └──────────────────────────────────────┘    │  │
│  ├───────────────────────────────────────────────────────────────────┤  │
│  │                    Python ML Pipeline                              │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────────┐   │  │
│  │  │ OpenCLIP │ │ E5-small │ │PaddleOCR │ │ YOLO-cls v2        │   │  │
│  │  │ViT-L/14 │ │ 384차원  │ │ Korean   │ │ 81카테고리          │   │  │
│  │  │ 768차원  │ │ 다국어   │ │ 텍스트   │ │ 정확도 93.87%       │   │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────────────┘   │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────────────────────┐  │  │
│  │  │ YOLO-det │ │GNN (GIN) │ │ DXF Reranker + ko_en_dict       │  │  │
│  │  │ 영역탐지 │ │DXF 구조  │ │ 한/영 동의어 + 구조 리랭킹      │  │  │
│  │  │ mAP=0.55 │ │R@5=0.765 │ │                                  │  │  │
│  │  └──────────┘ └──────────┘ └──────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 기술 스택

| 구분 | 기술 | 역할 |
|---|---|---|
| 멀티모달 LLM | Ollama + Gemma 4 / Qwen3.5 (RAM+설치 모델 자동선택) | 도면 분석, 설명 생성, Q&A (Settings에서 수동 전환 가능) |
| 이미지 임베딩 | OpenCLIP ViT-L/14 | 도면 이미지 → 768차원 벡터 (datacomp_xl_s13b_b90k) |
| 텍스트 임베딩 | intfloat/multilingual-e5-small | OCR 텍스트 → 384차원 벡터 |
| GNN 임베딩 | GIN Encoder (자체 학습) | DXF 구조 → 256차원 벡터 (R@5=0.765) |
| OCR | PaddleOCR (Korean) | 도면 내 부품번호, 치수, 재질 추출 |
| 도면 분류 | YOLO-cls v2 (자체 학습) | 81 카테고리 자동 분류 (정확도 93.87%) |
| 객체 탐지 | YOLO-det (자체 학습) | 표제란, 부품표, 치수 영역 탐지 (mAP50=0.552) |
| CAD 포맷 | CAD Router (8포맷) | PNG/JPG/DXF/DWG/STEP/IGES/STL + 비지원 포맷 안내 |
| 벡터 DB | ChromaDB (3채널) | image 61,475 + text 68,649 + gnn 61,451건 |
| 프론트엔드 (Legacy) | Streamlit (Engineering Terminal) | 7페이지 + 6개 컴포넌트 (다크 테마, 블루프린트 그리드) |
| 프론트엔드 (v5.5) | Next.js 16 + React 19 + Tailwind v4 | 다크/라이트 모드, Settings 패널, 3D 뷰어 (Three.js) |
| 컨테이너 | Docker + docker-compose | 2-서비스 배포 (app + ollama, ChromaDB 임베디드) |
| 테스트 | pytest | **540+** 테스트 케이스 |

### 개발 여정 (Phase A → K)

#### Phase A: 환경 구축 및 코드 정비

Python 3.11 + PyTorch + CLIP + PaddleOCR 등 ML 환경을 세팅하고, Ollama 서버에 qwen3-vl:8b 모델을 올렸다. 초기 코드의 보안 취약점(경로 탐색, 프롬프트 인젝션)을 점검하고 수정했다.

#### Phase B: 대량 데이터 파이프라인

MiSUMi 산업표준 부품 DXF 61,451건과 유닛 베어링 DWG 463건을 PNG로 변환하고, CLIP 이미지 임베딩 + PaddleOCR 텍스트 임베딩을 생성하여 ChromaDB에 등록했다. 총 **61,473건**, DB 크기 **441MB**.

```
MiSUMi_industrial_parts/     58 카테고리, 61,012건
├── Shafts/                  샤프트 (회전축)
├── Linear_Bushings/         리니어 부싱
├── Gears/                   기어
├── Springs/                 스프링
├── Brackets/                브라켓
└── ... (총 58 카테고리)

Unit_bearing/                15 카테고리, 461건
├── UCP/                     필로우 블록 베어링
├── UCF/                     4볼트 플랜지형
└── ... (총 15 카테고리)
```

#### Phase C: 모델 및 성능 최적화

VLM 5개 모델(qwen3-vl, qwen3.5, translategemma, glm-ocr, glm-4.7-flash)을 비교 평가하고, 142개 Ground Truth 쿼리로 검색 성능을 정량 측정했다. 하이브리드 검색 가중치를 Grid Search로 튜닝하여 최적 비율을 도출했다.

#### Phase D: 에러 핸들링 및 테스트

17개 CRITICAL 보안/안정성 갭을 수정하고, **120개 pytest 테스트**를 작성하여 전 모듈을 커버했다:
- 임베딩 (CLIP, SentenceTransformer)
- LLM (Ollama API, 프롬프트 인젝션 방어, 500 에러 재시도)
- OCR (텍스트 추출, 패턴 매칭)
- 파이프라인 (등록, 검색, 분석)
- 보안 (경로 탐색, 입력 검증)
- 벡터 DB (CRUD, 하이브리드 검색)

또한 Ollama VLM 호출 시 발생하는 500 에러에 대해 **자동 재시도 + 상세 에러 진단** 로직을 추가했다:
- 일시적 500 에러(모델 로딩 중, 메모리 부족 등) 시 최대 2회 재시도 (3초, 6초 대기)
- Ollama 에러 응답 본문에서 실제 원인(OOM, model not found 등)을 추출하여 사용자에게 표시
- 모델 미설치 시 `/api/tags` 조회 후 설치 안내 메시지 제공
- Streamlit UI에서 에러 유형별(연결 실패, 모델 미설치, 타임아웃, 500) 해결 가이드 표시

#### Phase E: Streamlit UI

4페이지 웹 인터페이스를 "CAD Vision" 브랜딩으로 구축했다:
- 📊 **대시보드** — 등록 현황, 벡터 DB 통계, Ollama 상태
- 📁 **도면 등록** — 단건/일괄 업로드
- 🔍 **도면 검색** — 자연어 검색 + 결과 시각화
- 🤖 **도면 분석** — AI 설명 생성, 분류, Q&A

#### Phase F: Docker 컨테이너 배포

비개발자도 실행할 수 있도록 Docker 기반 배포 환경을 구축했다:
- ML 모델 프리로드 (빌드 시 CLIP/E5/PaddleOCR 다운로드)
- 원클릭 실행 스크립트 (`docker-start.sh`)
- Ollama 모델 자동 pull + 헬스체크 + 브라우저 자동 열기
- `pydantic_settings.BaseSettings`를 통한 환경변수 자동 주입으로 Docker/로컬 설정 분리
- 외부 도면 경로 매핑 (`DRAWING_PATH_REMAP_FROM/TO`)으로 호스트↔컨테이너 경로 호환

#### Phase G: 외장 드라이브 이동

맥 내장 저장공간 절약을 위해 프로젝트 전체를 외장 드라이브로 이동했다:
- 이동 전 영향 분석 → 모든 경로가 상대 경로이므로 **코드 수정 없이** 이동 가능 확인
- Docker 컨테이너 중지 → 파일 복사 (84개 파일, 442MB) → 새 경로에서 Docker 재시작
- Ollama 모델(named volume)은 Docker 자체 저장소에 있어 프로젝트 이동에 영향 없음
- 외부 도면 이미지 마운트, 경로 매핑 등 기존 설정 그대로 동작 확인

#### Phase H: YOLOv8 도면 분류 + 객체 탐지 + PaddleOCR

VLM 단일 모델의 분류 한계(정확도 33%)를 극복하기 위해 YOLO 기반 전용 모델을 학습시켰다:

- **YOLOv8-cls** (이미지 분류): 73 카테고리(MiSUMi 56 + 베어링 14 + 기타 3) 학습 → **정확도 96.6%** (Top-1), Top-5 99.4%
- **YOLOv8-det** (객체 탐지): 표제란(title_block), 부품표(parts_table), 치수 영역(dimension_area) 자동 탐지 → **mAP50=0.552**
- **PaddleOCR 3.4.0**: EasyOCR 대신 도입, 한/영/일 다국어 OCR + 부품번호·재질·치수 패턴 자동 추출
- SHA256 모델 무결성 검증, 디바이스 자동 선택(MPS/CUDA/CPU)
- 테스트: 229개 → **298개** 통과

#### Phase I: YOLO-Ollama 컨텍스트 주입 (Phase 4)

YOLO/OCR이 추출한 구조화 데이터를 Ollama LLM 프롬프트에 자동 주입하여 분석 품질을 대폭 개선했다:

- **AnalysisContext**: YOLO 분류, 탐지 영역, OCR 부품번호·재질·치수를 구조화하여 LLM 프롬프트에 `=== PRE-EXTRACTED FACTS ===` 블록으로 삽입
- **HallucinationDetector**: LLM 응답을 OCR/YOLO 사실과 4개 필드(부품번호, 재질, 카테고리, 치수)에서 대조 검증. 재질 별칭(SUS304=SS304=AISI 304) 지원
- **텍스트 전용 모드**: 충분한 컨텍스트가 있으면 이미지 인코딩을 건너뛰어 응답 시간 60-90초 → **20초 이내**로 단축
- `describe_drawing()`, `classify_drawing()`, `answer_question()`, `generate_metadata()` 모두 context 파라미터 지원 (하위 호환 유지)

#### Phase J: 보안 강화

프로덕션 배포를 위한 포괄적 보안 강화를 수행했다:

- **모델 무결성**: YOLOv8-cls/det 모델 파일 SHA256 해시 검증
- **SSRF 방어**: Ollama URL 스키마 제한(http/https), 내부 네트워크 주소 차단, 포트 범위 검증
- **LLM 레이트 리미팅**: 분당 최대 30회 호출 제한 (토큰 버킷 알고리즘)
- **프롬프트 인젝션 방어**: 18개 정규식 패턴으로 도면 분석 시 시스템 프롬프트 조작 시도 차단
- **OCR 텍스트 살균**: 셸 인젝션·경로 탐색·null byte 제거
- **의존성 핀닝**: 모든 패키지 상한 버전 명시 (supply chain 공격 방어)
- **Docker 비루트 실행**: `appuser` (UID 1000) 권한으로 실행
- **로그 보안**: 50MB 회전 + 7일 보관 (loguru)
- 보안 테스트 **60개** 추가 → 총 **358개** 통과

#### Phase L: ML 학습용 공학 도면 데이터셋 구축

CLIP Fine-tuning 및 도면 분류 모델 일반화를 위해 외부 공개 소스에서 자동차/기계 부품 공학 도면을 대규모로 수집했다. 9개 소스에서 **72,730장**, **34GB** 규모의 데이터셋을 구축했다:

- **USPTO PPUBS 특허 도면**: 3,254 PNG (14개 IPC 코드, Public Domain)
- **미군 기술 매뉴얼 도면**: 5,825 PNG (Archive.org TM 9 시리즈, Public Domain)
- **Kaggle Airbag CAD**: 60,000 PNG (합성 에어백 도면, CC BY 4.0)
- **GrabCAD 커뮤니티**: 799 JPG (15개 부품 카테고리)
- **합성 도면 (향상)**: 1,332 PNG (다중 뷰 + 타이틀 블록 + 스캔 효과 시뮬레이션)
- 기타: Google Patents(510), Kaggle 2D(7), 기본 합성(1,000), Wikimedia CC(3)

수집 도구/스크립트: `drawing-datasets/` 디렉토리, 상세 현황: `drawing-datasets/DATASET_SUMMARY.json`

#### Phase K: Docker 빌드 안정화

Docker 환경에서 발생한 빌드/런타임 이슈를 해결했다:

- **CLIP 빌드 실패**: pip 26+에서 setuptools 82가 `pkg_resources`를 제거하여 CLIP 설치 불가 → `setuptools<81` + `--no-build-isolation`으로 분리 빌드
- **ChromaDB 버전 불일치**: 호스트(1.5.1) vs 컨테이너(0.6.3) 데이터 호환 불가 → `chromadb>=1.0.0,<2.0.0`으로 제약조건 변경하여 해결
- 61,473건 레코드 + 경로 리매핑 정상 동작 확인

---

## 전 (轉) — 부딪힌 벽과 극복

### 시행착오 1: CLIP은 도면을 이해하지 못했다

처음에는 CLIP 이미지 임베딩이 검색의 핵심이 될 것이라 기대했다. "비슷한 형상의 도면은 비슷한 벡터를 가질 것"이라는 가설이었다.

**현실은 달랐다.** CLIP은 자연 사진(ImageNet) 분포로 학습된 모델이다. DXF에서 변환된 **흑백 선화 도면**은 CLIP이 학습한 세계와 완전히 다른 도메인이었다. 모든 도면이 "검은 선 + 흰 배경"이라는 유사한 시각적 특성을 가지기 때문에, CLIP 임베딩으로는 샤프트와 기어를 구분할 수 없었다.

**Grid Search 가중치 튜닝 (142쿼리, 11개 조합)**으로 확인한 결과:

| 이미지 가중치 | 텍스트 가중치 | MRR | Recall@10 |
|---|---|---|---|
| **0.0** | **1.0** | **0.2634** | **0.3028** |
| 0.5 | 0.5 | 0.2634 | 0.3028 |
| 1.0 | 0.0 | 0.0528 | 0.0775 |

**텍스트 전용(image=0.0)이 최적**이라는 결론을 얻었다. 이미지 가중치를 높일수록 오히려 성능이 하락했다.

> 교훈: 범용 모델을 도메인에 바로 적용하면 안 된다. CLIP Fine-tuning이나 도면 특화 임베딩 모델이 필요하다.

### 시행착오 2: OCR 텍스트의 한계

텍스트 검색이 이미지보다 낫다고 해도, 성능 자체는 기대에 미치지 못했다.

**원인 분석:** DXF→PNG 변환 도면에서 PaddleOCR이 추출하는 텍스트는 **부품명이 아닌 치수·기호** 위주였다:

```
사용자 쿼리:  "shaft"  (샤프트를 찾고 싶다)
OCR 추출 텍스트: "M5  82  F8  PSFCG20-82-F8-P8-M5  φ20"
```

"shaft"와 "M5, 82, F8" 사이에는 **의미적 연결이 전혀 없다**. SentenceTransformer가 아무리 좋아도, 입력 텍스트 자체가 부품의 정체성을 담고 있지 않으면 검색이 작동하지 않았다.

| 지표 | 목표 | 실제 측정값 | 상태 |
|---|---|---|---|
| Recall@5 | 0.80 | 0.146 | ❌ |
| Recall@10 | 0.90 | 0.303 | ❌ |
| MRR | 0.70 | 0.263 | ❌ |
| 검색 응답 시간 | 3초 이내 | **0.104초** | ✅ |

**속도는 목표의 29배나 빨랐지만, 정확도는 목표에 크게 미달했다.**

> 교훈: 검색 품질은 임베딩 모델이 아니라 **입력 텍스트의 품질**에 의해 결정된다. OCR만으로는 부족하다. VLM이 도면을 "설명"하는 텍스트를 생성해야 한다.

### 시행착오 3: 단일 VLM의 한계

qwen3-vl:8b는 도면을 매우 상세하게 분석할 수 있었지만, **1회 추론에 63.5초**가 걸렸다. 61,473건 전체에 VLM 설명을 생성하면 약 45일이 소요되는 셈이다.

5개 VLM을 비교한 결과, 각 모델의 장단점이 명확했다:

| 모델 | 속도 | 분석 품질 | 한국어 | 용도 |
|---|---|---|---|---|
| glm-ocr | < 1초 | 텍스트만 | — | 고속 OCR |
| translategemma | 2~9초 | 중간 | 안정 | 배치 분류 |
| qwen3-vl:8b | 63초 | 최상 | 불안정 | 상세 분석 |
| qwen3.5:9b | 58~89초 | 상 | 안정 | 교차 검증 |

> 교훈: 단일 모델로 속도·정확도·한국어 품질을 동시에 만족시킬 수 없다. **역할별 분담**이 답이다.

### 시행착오 4: pip 26과 Debian Trixie

Docker 빌드 과정에서 두 가지 환경 호환 문제를 만났다:
- `openai-clip` 패키지가 pip 26의 엄격한 메타데이터 검증에서 실패 → `clip @` 으로 패키지명 수정
- `libgl1-mesa-glx`가 Debian Trixie에서 제거됨 → `libgl1`으로 대체

> 교훈: Docker 이미지의 OS 버전과 패키지 매니저 버전에 따라 의존성 설치 방법이 달라질 수 있다. 빌드 테스트는 필수다.

### 시행착오 5: Docker 환경의 경로·네트워크 불일치

Docker 컨테이너 배포 후 두 가지 런타임 문제가 발생했다:

**Ollama 연결 실패**: `DrawingPipeline` 생성자에 `ollama_url`이 하드코딩(`localhost:11434`)되어, Docker 내부 네트워크(`ollama:11434`)에 접근하지 못했다. `config.settings`를 통해 환경변수를 주입하도록 수정했다.

**이미지 표시 불가**: 도면 등록 시 저장된 파일 경로가 호스트의 절대 경로(예: `/Volumes/ExtDrive/...`)여서, 컨테이너 내부에서 `Path.exists()` 실패. 3단계 경로 해결 전략(`_resolve_file_path()`)을 구현했다:
1. 원본 경로 그대로 시도
2. `DRAWING_PATH_REMAP_FROM/TO` 접두사 치환
3. 파일명으로 upload_dir 내 재귀 검색 (캐싱)

> 교훈: 로컬 개발 환경과 컨테이너 환경의 파일시스템·네트워크 차이를 반드시 고려해야 한다. 설정을 하드코딩하지 말고, 환경변수로 주입하는 패턴이 필수다.

### 시행착오 6: 외장 드라이브로 프로젝트 이동

맥 내장 저장공간이 부족하여 프로젝트 전체(442MB)를 외장 드라이브로 이동해야 했다. 이동 전에 **코드에 하드코딩된 프로젝트 경로가 있는지** 전수 조사를 실시했다.

**분석 결과**: 소스 코드(.py, .yml, .sh, .toml) 전체를 grep한 결과, 프로젝트 자체 경로를 참조하는 하드코딩은 **0건**이었다. `docker-compose.yml`의 볼륨 마운트는 상대 경로(`./data`, `./.streamlit`)를 사용하고, records.json의 절대 경로는 도면 이미지 데이터를 가리키므로(프로젝트 위치와 무관) 이동에 영향이 없었다.

**결론**: 코드 수정 0건으로 이동 완료. Docker 이미지는 Docker 자체 저장소에 있고, Ollama 모델은 named volume에 저장되어 프로젝트 이동과 무관했다.

> 교훈: 프로젝트 내부에서 **자기 자신의 절대 경로를 참조하지 않는 설계**가 이식성(portability)을 보장한다. 상대 경로 + 환경변수 패턴의 실제 효과를 확인한 사례다.

---

## 결 (結) — 무엇을 만들었는가

### 최종 결과물

**CAD Vision v4.0** — AI 기반 산업 도면 검색 및 분류 시스템

```
docker-compose (2 서비스)
┌───────────────────────────┐     ┌────────────────────────┐
│  app (cad-vision-app)      │────▶│  ollama                │
│  Streamlit :8501           │     │  (cad-vision-ollama)   │
│  Python 3.11 + ML Models   │     │  Qwen3.5:9b (6.6GB)   │
│  CLIP + E5 + PaddleOCR     │     │  :11434                │
└──────────┬────────────────┘     └────────────┬───────────┘
           │                                    │
    ./data/ (bind mount)              ollama_data (named volume)
    ├── sample_drawings/  61,473건    └── models/
    └── vector_store/     441MB
```

### 핵심 기능

| 기능 | 설명 |
|---|---|
| 📊 **대시보드** | 등록 도면 현황, 카테고리 분포, Ollama 연결 상태 |
| 📁 **도면 등록** | 단건 업로드 + 폴더 일괄 등록 (OCR → 임베딩 → DB 자동화) |
| 🔍 **도면 검색** | 자연어 텍스트로 의미 기반 검색, 유사도 순 결과 |
| 🤖 **도면 분석** | VLM이 도면을 읽고 부품 정보 추출, Q&A 대화 |

### 정량적 성과

| 항목 | 수치 |
|---|---|
| 등록 도면 수 | **68,649건** (81 카테고리) |
| 벡터 DB | **3채널** — Image 61,475 + Text 68,649 + GNN 61,451건 |
| 검색 채널 | Image(OpenCLIP 768d) + Text(E5 384d) + GNN(GIN 256d) |
| GNN 구조 검색 | **R@5=0.765** (DXF 그래프 유사도, 54,722 DXF 학습) |
| 검색 응답 시간 | **0.104초** (목표 3초의 29배) |
| 도면 분류 정확도 | **93.87%** (YOLO-cls v2, 81 카테고리 Top-1) |
| 객체 탐지 성능 | **mAP50=0.552** (YOLO-det, 표제란/부품표/치수) |
| LLM | **Qwen3.5** (RAM 자동선택: 27b/9b/4b) |
| LLM 분석 시간 | **<20초** (텍스트 전용 모드) |
| DXF 지원 | DXF 업로드 → PNG 자동 변환 + 구조 검색 |
| 테스트 케이스 | **540+** |
| 보안 테스트 | **60개** (SSRF, 프롬프트 인젝션, 레이트 리미팅 등) |
| ML 학습 데이터셋 | **72,730장** (9개 소스, 34GB) |

### 프로젝트 구조

```
drawing-llm/
├── app/
│   └── streamlit_app.py          # Streamlit 4페이지 UI (CAD Vision 테마)
├── core/
│   ├── embeddings.py             # OpenCLIP ViT-L/14 + E5 임베딩 엔진
│   ├── vector_store.py           # ChromaDB 3채널 (이미지/텍스트/GNN)
│   ├── gnn.py                    # GIN Encoder + DXFGraphBuilder (DXF 구조 임베딩)
│   ├── dxf_renderer.py           # DXF → PNG 렌더링 + 메타데이터 추출
│   ├── llm.py                    # Ollama Qwen3.5 + AnalysisContext + HallucinationDetector
│   ├── ocr.py                    # PaddleOCR 한국어 OCR (부품번호/재질/치수 패턴)
│   ├── classifier.py             # YOLO-cls v2 도면 분류기 (81 카테고리, 93.87%)
│   ├── detector.py               # YOLO-det 객체 탐지기 (표제란/부품표/치수)
│   ├── pipeline.py               # 등록/검색/분석 파이프라인 (3채널 + DXF)
│   ├── evaluation.py             # IR 지표 평가 (Recall, MRR, mAP)
│   ├── weight_tuner.py           # 하이브리드 검색 가중치 Grid Search
│   └── benchmark.py              # 성능 벤치마크 (YOLO/OCR/LLM 속도, 메모리)
├── config/
│   └── settings.py               # pydantic_settings 기반 환경 설정 (보안 + 경로 매핑)
├── models/
│   ├── yolo_cls_v2_best.pt       # YOLO-cls v2 학습 모델 (81 카테고리, 93.87%)
│   ├── yolo_det_best.pt          # YOLO-det 학습 모델 (영역 탐지)
│   └── gnn_encoder.pt            # GIN Encoder (DXF 구조 임베딩, R@5=0.765)
├── data/
│   ├── sample_drawings/          # 도면 이미지 (61,473건)
│   ├── vector_store/             # ChromaDB 영속 데이터 (3채널: image+text+gnn)
│   ├── category_keywords.json    # 카테고리별 검색 키워드
│   ├── metadata/                 # 평가/튜닝 결과 JSON
│   └── ground_truth_misumi.json  # 142개 평가 쿼리
├── tests/                        # pytest 540+ 테스트
│   ├── test_embeddings.py        # 임베딩 테스트
│   ├── test_llm.py               # LLM 기본 테스트
│   ├── test_llm_context.py       # 컨텍스트 주입 + 환각 검증 테스트
│   ├── test_classifier.py        # YOLOv8-cls 분류기 테스트
│   ├── test_detector.py          # YOLOv8-det 탐지기 테스트
│   ├── test_ocr.py               # OCR 테스트
│   ├── test_pipeline.py          # 파이프라인 통합 테스트
│   ├── test_security.py          # 보안 테스트 (SSRF, 인젝션, 레이트리밋)
│   └── test_vector_store.py      # 벡터 DB 테스트
├── scripts/
│   ├── docker-start.sh           # 비개발자용 원클릭 실행
│   └── preload_models.py         # Docker 빌드 시 모델 프리로드
├── docs/
│   ├── GUIDE_DEVELOPER.md        # 개발자 가이드
│   └── GUIDE_USER.md             # 사용자 가이드 (비개발자)
├── Dockerfile                    # Python 앱 이미지 (비루트 사용자)
├── docker-compose.yml            # app + ollama 오케스트레이션
├── .streamlit/config.toml        # CAD Vision 다크 테마
├── requirements.txt              # Python 의존성 (버전 상한 핀닝)
└── PROJECT_SPEC.md               # 상세 기능 명세서
```

### 빠른 시작

#### Docker (권장 — 비개발자 포함)

```bash
# 프로젝트 폴더로 이동 (외장 드라이브 경로)
cd <저장소 클론 경로>/01_CAD/app

# 원클릭 실행 (Docker Desktop 필요)
./docker-start.sh

# 브라우저가 자동으로 http://localhost:8501 에 열립니다
```

**스크립트가 자동으로 수행하는 작업:**
1. Docker 실행 상태 확인
2. 데이터 디렉토리 생성
3. 컨테이너 빌드 및 시작 (`docker compose up -d --build`)
4. AI 모델(Qwen3.5, RAM 기반 자동 선택) 확인, 미설치 시 자동 다운로드 (~6.6GB)
5. 앱 헬스체크 후 브라우저 자동 오픈

**관리 명령어:**

```bash
docker compose down              # 종료
docker compose logs -f           # 로그 확인
docker compose restart           # 재시작
docker compose restart ollama    # Ollama만 재시작 (분석 오류 시)
```

> **외장 드라이브 필수**: 프로젝트가 외장 드라이브에 저장되어 있으므로,
> **드라이브가 연결된 상태**에서만 실행 가능합니다.

> **외부 도면 이미지 사용**: 도면 이미지가 프로젝트 외부에 있는 경우,
> `docker-compose.yml`에서 볼륨 마운트와 `DRAWING_PATH_REMAP_FROM/TO` 환경변수를 설정하세요.
> 상세 방법은 [개발자 가이드](./docs/GUIDE_DEVELOPER.md#4-6-외부-도면-이미지-마운트)를 참조하세요.

#### 로컬 개발

```bash
# 프로젝트 폴더로 이동
cd <저장소 클론 경로>/01_CAD/app

# 가상환경 + 의존성
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Ollama 서버 + 모델
ollama serve &
ollama pull qwen3.5:9b

# 앱 실행
streamlit run app/streamlit_app.py

# 테스트 실행
pytest tests/ -v                    # 전체 540+ 테스트
pytest tests/test_llm.py -v         # LLM 기본 테스트
pytest tests/test_llm_context.py -v # 컨텍스트 주입 + 환각 검증
pytest tests/test_classifier.py -v  # YOLOv8-cls 분류기
pytest tests/test_security.py -v    # 보안 테스트
```

### 도면 처리 파이프라인

```
[등록 — PNG/JPG]
도면 이미지 ──┬──→ PaddleOCR ──→ 텍스트 추출 ──→ E5 임베딩 ──→ ChromaDB (텍스트, 0.6)
              ├──→ OpenCLIP ViT-L/14 ──→ 768d 임베딩 ──→ ChromaDB (이미지, 0.1)
              ├──→ YOLO-cls v2 ──→ 81 카테고리 자동 분류 (93.87%)
              └──→ YOLO-det ──→ 표제란/부품표/치수 영역 탐지

[등록 — DXF]
DXF 파일 ──┬──→ DXFRenderer ──→ PNG 변환 + 메타데이터 추출 ──→ 위 PNG 파이프라인
           └──→ DXFGraphBuilder ──→ GIN Encoder ──→ 256d 임베딩 ──→ ChromaDB (GNN, 0.3)

[검색 — 3채널 하이브리드]
사용자 쿼리 ──→ E5 임베딩 ──→ 텍스트 검색 (0.6) ──┐
              ──→ OpenCLIP ──→ 이미지 검색 (0.1) ──┼──→ 가중합 → 유사도 순 결과
DXF 업로드  ──→ GIN Encoder ──→ GNN 검색 (0.3)  ──┘

[분석 — v5.1: 카테고리 특화 프롬프트 + YOLO 교정]
도면 업로드 ──→ YOLO-cls/det + OCR ──→ AnalysisContext ──→ CategoryPrompt (15종) ──→ Qwen3.5
              ──→ DXF면 자동 PNG 렌더링 + 메타데이터 추출     ──→ YOLO 교정 지시문 주입
                                                             ──→ HallucinationDetector 검증

[v5.0 아키텍처 — FastAPI + Streamlit 분리]
                     ┌─ Streamlit UI (8501) ─┐
사용자 ── 브라우저 ──→│  APIClient             │──→ FastAPI (8000) ──→ Pipeline
                     └──────────────────────┘         ↕
                                                  ChromaDB (8100)
```

---

## 남은 과제와 전망

#### Phase M: ML 모델 재학습 + OCR 개선 + 메타데이터 갱신

데이터셋 72,730장을 81 카테고리로 재구성하고 전체 ML 파이프라인을 업그레이드했다:

- **YOLOv8-cls v2**: 73→81 카테고리 확장, Test Top-1=93.87%, Top-5=98.04% (best epoch 70/90)
- **CLIP Fine-tuning**: 도면 특화 학습으로 Recall@5 i2t=73.2%, t2i=94.7% 달성
- **OCR 3-전략 개선**: (1) 파일명 부품번호 추출, (2) 암배경 반전, (3) 카테고리-재질 매핑(75종)
- **메타데이터 일괄 갱신**: 68,647건 records.json — 부품번호 60,456건, 재질 60,721건 보강

#### Phase N: v4.0 대규모 업그레이드 (4단계)

전체 ML 스택을 최신 모델로 교체하고, GNN 구조 검색 + DXF 네이티브 지원을 추가했다:

**Phase 1 — YOLO26 + Qwen3.5 (RAM 자동 선택)**
- ultralytics >=8.4.0 (YOLO26 호환), 코드 내 "YOLOv8" → 버전 무관 "YOLO" 명칭 전환
- `_auto_select_ollama_model()`: psutil로 RAM 확인 → >=48GB→27b, >=16GB→9b, <16GB→4b
- 사이드바에 활성 Ollama 모델명 표시

**Phase 2 — OpenCLIP ViT-L/14 (512→768-dim)**
- CLIP ViT-B/32 → OpenCLIP ViT-L/14 (datacomp_xl_s13b_b90k) 업그레이드
- 이미지 임베딩 차원: 512 → 768 (표현력 향상)
- ChromaDB image 컬렉션 재생성 (61,475건)

**Phase 3 — GNN 구조 검색 (DXF → Graph → GIN Encoder)**
- `DXFGraphBuilder`: DXF 엔티티 → PyG 그래프 (14-dim 노드 피처, k-NN+geometric 엣지)
- `GINEncoder`: 4-layer GIN + BatchNorm → 256-dim L2-normalized 임베딩
- SupCon Loss 학습: 54,722 DXF, 72 카테고리, **R@1=0.614, R@5=0.765, R@10=0.827**
- ChromaDB 3채널 하이브리드 검색: Image(0.1) + Text(0.6) + GNN(0.3)

**Phase 4 — DXF 네이티브 지원**
- `DXFRenderer`: ezdxf + matplotlib로 DXF → PNG 렌더링 + 메타데이터 추출
- 파이프라인: DXF 업로드 → 자동 PNG 변환 → 기존 등록/검색 플로우 연결
- Streamlit: DXF 업로더 + DXF 구조 검색 탭 추가

#### Phase O: v5.0~v5.3 — API/인프라/UX 대규모 업그레이드

Streamlit 모놀리스를 **FastAPI + Streamlit 분리 아키텍처**로 전환하고, 검색·분석·도구의 UX를 대폭 개선했다:

**v5.0 — FastAPI REST API + Docker Compose 분리** (Phase 1~5)
- **FastAPI 라우터 분리**: drawings, analysis, tools, feedback, health, stats → 6개 독립 라우터
- **REST API 25+ 엔드포인트**: 등록, 4종 검색(텍스트/이미지/DXF/부품번호), 분석, BOM, 치수비교, DXF비교, SSE 스트리밍
- **API Client + Streamlit 전환**: `APIClient` 클래스로 REST 호출, `is_api_mode()` 자동 감지
- **Docker Compose**: `cad-api(8000)` + `cad-ui(8501)` + `cad-chromadb(8100)` 3-컨테이너
- **테스트 확장**: 412 → 688 tests (라우터별 전용 테스트 59건 + 통합 18건)

**v5.1 — 버그 수정 + 검색/분석 품질 개선**
- BOM 추출 `_base_url` 속성명 오류 수정
- DXF 비교 `matched_count` 속성명 오류 수정
- DXF 검색 결과 이미지 미표시 → `_render_dxf_thumbnail()` PNG 폴백 추가
- **한/영 동의어 사전** (`ko_en_dict.py`): 140+ 부품/소재/가공 용어 매핑, 자동 쿼리 확장
- **DXF 도면 분석 지원**: DXF 업로드 → PNG 렌더링 + 메타데이터 추출 → LLM 프롬프트 주입
- **카테고리 특화 프롬프트** (`category_prompts.py`): 15개 부품 유형별 분석 지시문
- **YOLO 교정 지시문**: 높은 신뢰도 시 LLM이 분류 결과를 존중하도록 강제

**v5.2 — 도구/검색 UI 개선**
- BOM 추출: 카테고리별 도면 선택 드롭박스 추가
- DXF 비교: 양쪽 DXF 렌더링 이미지 나란히 표시
- 검색: 파일 형식 필터 (PNG/JPG/DXF) 멀티셀렉트
- 이미지 검색: DXF 업로드 지원 (자동 PNG 변환)
- DXF 구조 검색: 업로드 DXF 미리보기 + 메타데이터 표시

**v5.3 — DXF 검색 정확도 + 치수 비교 UX**
- **DXF 리랭커** (`dxf_reranker.py`): 엔티티 분포 코사인 유사도 + 개수 비율 + 종횡비 보정 → 오탐 대폭 감소
- 치수 비교: 좌/우 독립 카테고리 필터 + 양쪽 도면 이미지 나란히 표시

### 현재 한계 및 개선 방향

| 개선 항목 | 현재 | 방법 | 기대 효과 |
|---|---|---|---|
| 탐지 모델 | mAP50=0.552 | 학습 데이터 증강 | mAP50 → 0.70+ |
| 데이터 규모 | 68,649건 | 증분 임베딩 | 신규 등록 즉시 반영 |
| LLM 정확도 | 범용 프롬프트 | 파인튜닝 (HF + MLX) | 부품 분석 정확도 향상 |
| 한글 검색 | 동의어 사전 | E5 Fine-tuning (한국어 CAD 코퍼스) | Recall@5 향상 |

### 이 프로젝트에서 배운 것

1. **범용 AI 모델은 만능이 아니다** — CLIP은 도면을 구분 못하고, VLM 단독 분류는 33% → YOLO 전용 모델(93.87%, 81카테고리)로 극복. CLIP Fine-tuning으로 카테고리 R@5=94.7% 달성
2. **데이터 품질이 모델 성능을 결정한다** — 아무리 좋은 임베딩 모델을 써도, 입력 텍스트가 "M5 φ20"이면 "shaft"를 찾을 수 없다
3. **정량적 측정 없이는 개선할 수 없다** — Grid Search, Ground Truth, IR 지표(MRR, Recall, Precision), 환각 검증으로 가설을 검증해야 한다
4. **단일 모델의 한계는 시스템 설계로 극복한다** — YOLO(분류) + OCR(텍스트) + VLM(분석) 파이프라인으로 역할 분담
5. **보안은 후순위가 아니다** — SSRF, 프롬프트 인젝션, 모델 무결성, 레이트 리미팅을 초기부터 고려해야 한다
6. **Docker 빌드 재현성은 핀닝에서 온다** — pip 26/setuptools 82 업데이트로 CLIP 빌드 실패, ChromaDB 0.6→1.x 데이터 호환 문제 등 경험

---

## 문서

| 문서 | 대상 | 내용 |
|---|---|---|
| [PROJECT_SPEC.md](./PROJECT_SPEC.md) | 기획/개발 | 문제 정의, 기능 명세, 로드맵, 성능 평가 |
| [docs/GUIDE_DEVELOPER.md](./docs/GUIDE_DEVELOPER.md) | 개발자 | 로컬/Docker 환경, 모듈 상세, 테스트, 트러블슈팅 |
| [docs/GUIDE_USER.md](./docs/GUIDE_USER.md) | 비개발자 | Docker Desktop 설치, 원클릭 실행, 화면 사용법, FAQ |

## 라이선스

MIT License

---

*Developed by Yeong | 2026 — v5.6 (FastAPI REST API + Docker Compose 2-서비스 + 한/영 동의어 + 카테고리 특화 프롬프트 + DXF 리랭커 + 540+ tests)*
