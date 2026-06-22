# Lemon Healthcare 팀 공유 보고서 - 2026-05-13 작업 내용 정리

## 한 줄 요약

오늘은 기존 백엔드 API를 깨지 않으면서, 보충제 이미지/OCR 분석, 로컬 Ollama LLM 파싱, 학습 데이터 준비, Hall-lite 체중 예측, YOLO 기반 ROI 보조 기능을 독립 모듈로 확장했습니다. 이후 GitHub Actions에서 발생한 품질 검사와 DB smoke 실패까지 원인 확인 후 수정했고, 팀 브랜치 `team/yeong-tech`에 push하여 현재 backend 관련 check가 성공한 상태입니다.

## 최종 브랜치 상태

- 팀 저장소: https://github.com/Lemon-Aid-KDT/Lemon-sin/tree/yeong-tech
- 최종 팀 브랜치 head: `1b722cfe61d7a7142fcf39fd3bd12a93799b28fd`
- 팀 브랜치 주요 커밋:
  - `14e663d feat(lemon): publish backend AI pipeline implementation`
  - `1b722cf fix(ci): repair backend quality and db smoke`
- GitHub Actions 최종 결과:
  - `Backend quality - Python 3.13`: success
  - `Backend DB smoke`: success

## 오늘 작업 목적

- 기존 API와 테스트를 기준선으로 유지한 상태에서 AI 기능을 안전하게 얹는 구조를 만들기
- 이미지 분석을 바로 자동 등록하지 않고, `OCR/text -> 구조화된 보충제 파싱 -> 사용자 확인` 흐름으로 설계하기
- 로컬 LLM(Ollama)을 기본 방향으로 잡아 민감한 건강 데이터가 외부 LLM으로 나가지 않도록 하기
- YOLO는 제품명/성분을 읽는 주 모델이 아니라, 병/라벨/블리스터 영역을 찾는 보조 도구로 제한하기
- PostgreSQL/Alembic 기반 CI smoke를 통과시켜 팀 브랜치가 계속 검증 가능한 상태가 되게 하기

## 구현 범위 요약

### 1. GitHub 협업 규칙과 Python 3.13 기준 정리

- 팀 협업 문서와 GitHub 템플릿을 Python 3.13 기준으로 맞췄습니다.
- 이슈 템플릿, PR 템플릿, CODEOWNERS, backend CI 설정을 정리했습니다.
- 불필요한 trailing whitespace를 제거해 `git diff --check`를 통과하도록 했습니다.

### 2. PostgreSQL 전환 안정화

- 설정 검증에서 SQLite 계열 URL을 거부하고 `postgresql+asyncpg://` 형식을 기준으로 삼았습니다.
- Alembic migration smoke를 실제 PostgreSQL 16 컨테이너에서 검증했습니다.
- DB smoke 실패 원인이었던 Alembic revision id 길이 문제를 해결했습니다.

### 3. 보충제 OCR/Text 분석 흐름

- FastAPI 업로드/분석 흐름을 보충제 이미지 intake와 연결했습니다.
- OCR adapter 인터페이스, 전처리 모듈, noop provider, OCR 텍스트 파싱 요청/응답 schema를 분리했습니다.
- 분석 결과는 바로 확정하지 않고 preview로 저장한 뒤 사용자 확인 단계에서 등록하도록 설계했습니다.

### 4. Ollama 로컬 LLM 파서 안정화

- `OllamaSupplementParser`를 중심으로 structured output/schema 검증을 강제했습니다.
- LLM 응답을 그대로 신뢰하지 않고 Pydantic schema, confidence, nutrient code 검증을 거치게 했습니다.
- 외부 base URL은 기본적으로 차단하여 privacy-first 방향을 유지했습니다.

### 5. 이미지 학습 파이프라인 준비

- `learning/` 모듈에 consent gate, embedding/vector store/retention 기본 구조를 추가했습니다.
- 실제 학습 데이터 저장은 기능 플래그와 사용자 동의가 모두 충족될 때만 가능하도록 설계했습니다.
- 현재는 학습 파이프라인이 기본 false 상태입니다.

### 6. Hall-lite 체중 예측 모델

- 기존 `/api/v1/predictions/weight` API 호환성을 유지했습니다.
- `body_composition`, `hall`, `selector` 모듈을 추가해 Hall-lite 경로를 독립적으로 구성했습니다.
- 기존 7단계 정적 모델 fallback을 테스트로 고정했습니다.
- 내부 단위는 kJ 기반으로 유지하고, kcal 변환은 명시적으로 처리했습니다.

### 7. 멀티모달 Ollama와 YOLO 실험 구조

- 멀티모달 Ollama는 OCR 실패/저신뢰 시 보조 후보 추출 역할로 제한했습니다.
- YOLO는 병/라벨/블리스터 ROI 탐지 보조로만 사용하도록 `vision/` 모듈을 분리했습니다.
- YOLO를 제품명/성분 추출 주 경로로 쓰지 않도록 테스트와 문서에 명시했습니다.

### 8. 문서와 파일 구조 정리

- `docs/20`부터 `docs/30`까지 구현 플랜과 현재 구조 설명 문서를 추가했습니다.
- `docs/Nutrition-docs/21-backend-file-structure-guide.md`에 수정된 파일 구조와 각 모듈의 역할을 정리했습니다.
- 예전 설계 문서는 `docs/Nutrition-docs/previous-version/`으로 이동해 현재 문서와 혼동되지 않게 했습니다.
- `pr2/pr3` placeholder는 삭제했습니다.

## CI 실패와 해결 과정

첫 push 후 GitHub Actions에서 3개 check가 실패했습니다.

- `Backend quality - Python 3.11`
- `Backend quality - Python 3.13`
- `Backend DB smoke`

원인은 다음과 같이 확인했습니다.

1. `Backend quality`는 Black formatting 문제였습니다. `hall.py`, `selector.py`, `taxonomy.py`가 `black --check`에서 실패했습니다.
2. Python 3.11 check는 프로젝트 기준이 Python 3.13으로 바뀌었는데 기존 canonical workflow가 아직 3.11/3.13 matrix였기 때문에 생성됐습니다.
3. `Backend DB smoke`는 Alembic 기본 `alembic_version.version_num` 길이가 32자인데, `0003_create_privacy_consent_audit` revision id가 33자라 PostgreSQL에서 `StringDataRightTruncationError`가 발생한 문제였습니다.

해결 내용은 다음과 같습니다.

- Black formatting 적용
- canonical backend workflow를 Python 3.13 단일 matrix로 정리
- 중복으로 들어간 `ci-backend.yml`, `ci-docs.yml`, `ci-mobile.yml` 제거
- Alembic revision id를 `0003_privacy_consent_audit`로 축약
- `0004` migration의 `down_revision`도 함께 갱신

## 검증 결과

로컬에서 다음 검증을 통과했습니다.

- `black --check src tests alembic`
- `ruff check src tests alembic`
- `ruff check src alembic --select S`
- `mypy src`
- `pytest`: `267 passed, 1 skipped`
- `pip-audit -r requirements.txt`: no known vulnerabilities
- PostgreSQL 16 컨테이너 기준:
  - `alembic upgrade head`
  - `alembic check`
  - `pytest tests/integration/db/test_db_session.py --no-cov`

GitHub Actions도 최종 commit `1b722cf` 기준 backend check 2개가 모두 success로 확인됐습니다.

## 팀원이 알아야 할 주의사항

- AI/이미지/학습 관련 기능 플래그는 기본 false입니다. 즉, 이번 작업은 구조와 안전장치를 먼저 넣은 것이고 운영에서 자동 활성화되는 형태가 아닙니다.
- OCR/LLM 결과는 사용자가 확인하기 전까지 확정 데이터로 보지 않습니다.
- YOLO는 텍스트 이해 모델이 아닙니다. 라벨 영역을 찾는 보조 도구로만 사용해야 합니다.
- Alembic revision id 변경은 아직 migration이 정상 적용되지 못한 팀 브랜치 CI 단계에서 잡은 문제입니다. 이미 외부 DB에 예전 긴 revision id가 기록된 환경이 있다면 별도 stamp/마이그레이션 대응이 필요합니다.
- `assets/mascot`, `outputs`, `회의록`, `00_plusultra` 등 로컬 산출물은 이번 커밋/푸시 대상에서 제외했습니다.

## 다음 작업 제안

1. 실제 OCR provider adapter를 하나 선택해 `POST /api/v1/supplements/analyze`에서 OCR+parse preview가 한 번에 동작하도록 연결합니다.
2. Ollama 로컬 모델 설치/미설치 상태별 운영 가이드를 추가합니다.
3. Hall-lite 결과를 프론트/모바일에서 어떻게 표시할지 UX 문구를 정리합니다.
4. 학습 데이터 저장은 동의/익명화/보관기간 정책 리뷰 후에만 활성화합니다.
5. `team/yeong-tech` 기준으로 팀원 리뷰 후 main 병합 전략을 정합니다.

## 공식 문서 참고

- FastAPI file uploads: https://fastapi.tiangolo.com/tutorial/request-files/
- Ollama API: https://docs.ollama.com/api
- Ollama structured outputs: https://docs.ollama.com/capabilities/structured-outputs
- Ultralytics YOLO docs: https://docs.ultralytics.com/
- YOLOv8 models: https://docs.ultralytics.com/models/yolov8/
- GitHub Actions workflow syntax: https://docs.github.com/actions/reference/workflows-and-actions/workflow-syntax
- actions/setup-python: https://github.com/actions/setup-python
- Alembic offline SQL/version table example: https://alembic.sqlalchemy.org/en/latest/offline.html
