# Lemon Healthcare 팀 공유 보고서 - 2026-05-15 작업 내용 정리

## 한 줄 요약

오늘 작업은 `yeong-Lemon-Aid`를 팀 통합용 프로젝트 루트로 정리하고, Nutrition 담당 구현물·문서·데이터 구조를 팀 브랜치에서 바로 확인할 수 있도록 재구성한 작업이다. 핵심은 폴더명 변경이 아니라, 팀원별 담당 파트를 같은 구조 안에서 작업하고 나중에 충돌 없이 통합할 수 있게 기준 구조를 확정한 것이다.

## 기준 정보

- 작업 대상일: 2026-05-15
- 로컬 프로젝트 경로: `/Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid`
- 보고서 저장 경로: `/Users/yeong/99_me/00_github/03_lemon_healthcare/yeong-Lemon-Aid/outputs/todo-list/2026-05-15`
- 팀 GitHub 저장소: `Lemon-Aid-KDT/Lemon-sin`
- 반영 브랜치: `yeong-tech`
- 팀 브랜치 최신 커밋: `ea1ffb9 docs(readme): align project overview with current workspace`
- 이전 전체 구조 반영 커밋: `2851a23 chore(yeong-tech): publish curated Lemon Aid workspace`

## 오늘 작업의 목표

프로젝트가 개인 작업 폴더처럼 보이면 팀원이 합류했을 때 각자 어디에 코드를 넣어야 하는지, 어떤 문서를 공통으로 봐야 하는지, 어떤 파일을 GitHub에 올리면 안 되는지 판단하기 어렵다.

따라서 오늘 목표는 다음 세 가지였다.

1. 팀 프로젝트용 루트 이름과 하위 구조를 정리한다.
2. Nutrition 담당 구현물은 별도 파트 폴더로 모으되, 공통 문서와 통합 문서는 팀 루트에 남긴다.
3. 팀 GitHub `yeong-tech` 브랜치에는 공유 가능한 파일만 선별해서 커밋·푸시한다.

## 구현 및 수정한 내용

### 1. 프로젝트 루트 이름과 산출물 위치 정리

기존에는 `Nutrition-Vision`, `yeong-Vision-Nutrition`처럼 Nutrition 담당 기능 중심의 이름이 남아 있었다. 오늘은 이를 팀 프로젝트 이름에 맞춰 `yeong-Lemon-Aid` 기준으로 정리했다.

정리한 대표 경로:

- `yeong-Lemon-Aid/`
- `yeong-Lemon-Aid/assets/mascot/`
- `yeong-Lemon-Aid/records/meetings/`
- `yeong-Lemon-Aid/outputs/reports/`
- `yeong-Lemon-Aid/outputs/generated/`
- `yeong-Lemon-Aid/outputs/todo-list/`

이렇게 결정한 이유:

- Nutrition 구현물만 보이는 이름보다 팀 전체 프로젝트명인 Lemon Aid를 루트로 쓰는 편이 통합 단계에서 자연스럽다.
- 마스코트, 회의록, 발표 산출물, 보고서가 코드 바깥에 흩어져 있으면 팀원이 최신 자료 위치를 찾기 어렵다.
- 제품 코드, 문서, 회의 기록, 산출물을 하나의 프로젝트 루트 아래 두면 GitHub에 올릴 파일과 제외할 파일을 선별하기 쉽다.

### 2. `docs/` 공통 문서와 `docs/Nutrition-docs/` 담당 문서 분리

문서 폴더는 공통 문서와 Nutrition 담당 상세 문서를 분리했다.

공통 문서로 유지한 파일:

- `docs/01-project-overview.md`
- `docs/03-project-intent.md`
- `docs/05-github-guidelines.md`
- `docs/06-tech-stack.md`
- `docs/10-compliance-checklist.md`
- `docs/Integration-docs/01-ci-pr-integration-operations.md`

Nutrition 담당 상세 문서:

- `docs/Nutrition-docs/`
- `docs/Nutrition-docs/dev-guides/`
- `docs/Nutrition-docs/templates/`
- `docs/Nutrition-docs/previous-version/`
- `docs/Nutrition-docs/pdf/`

Food/Chat 담당 문서 위치:

- `docs/Food-docs/README.md`
- `docs/Chat-docs/README.md`

이렇게 결정한 이유:

- `docs/` 루트에는 팀 전체가 공통으로 봐야 하는 최소 문서만 남기는 것이 좋다.
- Nutrition 세부 구현 문서 30개 이상을 공통 루트에 두면 Food, Chat, Design 담당자가 필요한 정보를 찾기 어렵다.
- `Nutrition-docs`로 모아두면 Yeong 담당 기술 문서와 팀 공통 문서의 책임 경계가 명확해진다.

### 3. `05-github-guidelines.md` 협업 규칙 재정의

`docs/05-github-guidelines.md`는 오늘 가장 중요한 협업 기준 문서로 다시 정리했다.

반영한 내용:

- 현재 `yeong-Lemon-Aid` 기준 폴더 트리
- `backend/Nutrition-backend`, `backend/food_image_analysis`, `backend/ai_agent_chat` 분리 기준
- `frontend/`, `mobile/uiux/`, `mobile/flutter_app/` 기준 구조
- `data/supplement_images`, `data/food_images`, `data/nutrition_reference` 데이터 구조
- 팀 브랜치 규칙
- 커밋, PR, CI, Secret 관리 기준

브랜치 규칙은 첨부된 GitHub 브랜치 현황을 기준으로 기능별 임시 브랜치보다 팀원-파트 고정 브랜치 방식으로 정리했다.

현재 기준 브랜치:

| 브랜치 | 담당 범위 |
| --- | --- |
| `changmin-aiagent` | AI agent chat |
| `changmin-plan` | 기획·일정·문서 플랜 |
| `taedong-design` | UI/UX, frontend, mobile, assets |
| `yeong-tech` | Nutrition 기술 구현 |
| `jongpil-tech` | 기술 구현 보조 및 담당 기능 |
| `sunghoon-database` | DB, migration, data structure |

이렇게 결정한 이유:

- 현재 팀은 이미 팀원 이름과 담당 파트가 붙은 브랜치를 사용하고 있다.
- 실제 운영 방식과 문서 규칙이 다르면 팀원이 문서를 보고도 잘못된 브랜치를 만들 수 있다.
- 각자 파트를 맡아 작업한 뒤 통합하는 프로젝트에서는 브랜치명이 담당 범위를 바로 드러내는 편이 충돌 관리에 유리하다.

### 4. Backend 구조를 담당 기능별로 분리

Backend는 하나의 폴더에 모든 기능을 넣지 않고, 담당 기능별 폴더를 만들었다.

현재 구조:

- `backend/Nutrition-backend/`
- `backend/food_image_analysis/`
- `backend/ai_agent_chat/`
- `backend/alembic/`
- `backend/scripts/`
- `backend/requirements.txt`
- `backend/requirements-dev.txt`
- `backend/pyproject.toml`

`Nutrition-backend/`에는 현재 실제 구현이 가장 많이 들어 있다.

대표 기능:

- FastAPI API 라우터
- 영양제 OCR intake
- OCR provider adapter
- Ollama 기반 parser
- KDRIs 2025 조회
- 부족 영양소 분석
- 체중 예측
- 개인정보/동의
- regulated OCR intake
- learning/vector DB 골격
- unit/integration tests

`food_image_analysis/`와 `ai_agent_chat/`은 아직 실제 런타임 구현 전 단계이며, `src/`와 `tests/`가 있는 skeleton 상태다.

이렇게 결정한 이유:

- 팀원별 담당 기능이 다르므로 backend 안에서도 책임 경계를 나눠야 한다.
- Nutrition 구현이 이미 크기 때문에 같은 `src/` 아래 Food/Chat을 섞으면 소유권과 테스트 범위가 흐려진다.
- `pyproject.toml`, `alembic`, `scripts`는 아직 공통 설정이므로 backend root에 두는 편이 중복을 줄인다.

### 5. `supplement_analysis`를 `Nutrition-backend` 기준으로 정리

사용자가 요청한 방향에 맞춰 Nutrition 담당 백엔드는 `Nutrition-backend` 이름을 기준으로 정리했다.

반영한 기준:

- Nutrition 런타임은 `backend/Nutrition-backend/src/`
- Nutrition 테스트는 `backend/Nutrition-backend/tests/`
- Food/Chat은 별도 skeleton 폴더
- 공통 검증 설정은 `backend/pyproject.toml`
- 공통 migration은 `backend/alembic/`

이렇게 결정한 이유:

- `supplement_analysis`는 기능 일부만 표현하는 이름이다.
- 현재 Nutrition 담당 범위는 보충제 OCR뿐 아니라 KDRIs, 영양 분석, 체중 예측, 개인정보 동의, regulated intake까지 포함한다.
- 따라서 더 넓은 책임을 표현하는 `Nutrition-backend`가 팀 공유 구조에 맞다.

### 6. 데이터 폴더를 `food_images`, `supplement_images`, `nutrition_reference`로 정리

이미지 데이터는 음식과 영양제를 분리하고, 공식 기준 데이터는 별도 reference로 뺐다.

현재 구조:

- `data/food_images/`
- `data/supplement_images/`
- `data/nutrition_reference/`

이미지 데이터 공통 하위 구조:

- `raw/`
- `interim/`
- `processed/`
- `splits/`
- `manifests/`
- `quarantine/`
- `scripts/`

영양제 이미지 데이터는 다음 흐름을 고려해 구조화했다.

1. 영양제 또는 보충제 이미지인지 판별
2. 라벨 영역과 OCR 후보 생성
3. 한글/영어 텍스트 추출 가능성 판단
4. 성분명, 함량, 섭취 방법 후보 추출
5. ambiguous, duplicate, low quality는 quarantine으로 격리

음식 이미지 데이터는 다음 흐름을 고려했다.

1. 한식, 양식, 중식, 일식, 기타 분류
2. 메인, 국, 반찬, 디저트 등 식사 구성 분류
3. 된장찌개, 김치국처럼 실제 음식명 매핑
4. train, val, test split과 taxonomy를 manifest로 관리

이렇게 결정한 이유:

- 원본, 중간 산출물, 학습 입력, split 결과를 섞으면 데이터 누수 위험이 커진다.
- 이미지 파일명과 폴더명만으로 계층을 관리하면 나중에 클래스명이 바뀔 때 이동 비용이 커진다.
- taxonomy와 classes를 manifest로 두면 모델 학습, 검수, 통계 산출에서 같은 기준을 재사용할 수 있다.
- KDRIs, MFDS, nutrient code는 음식과 영양제 모두에서 재사용하므로 `nutrition_reference`로 분리하는 것이 맞다.

### 7. Frontend와 Mobile 작업 위치 생성

팀 통합을 위해 frontend와 mobile 위치를 만들었다.

현재 상태:

- `frontend/README.md`
- `frontend/public/`
- `frontend/src/`
- `frontend/tests/`
- `mobile/README.md`
- `mobile/uiux/`
- `mobile/flutter_app/`

주의할 점:

- 현재 `frontend`와 `mobile`은 실제 앱 구현 완료 상태가 아니라 작업 위치를 확정한 상태다.
- Flutter/Xcode 실제 구현은 `mobile/flutter_app/` 아래에서 이어가는 것이 맞다.
- UI/UX 산출물은 `mobile/uiux/` 아래에서 관리하는 기준이다.

이렇게 결정한 이유:

- 디자인, 모바일, 웹, 백엔드를 같은 backend 폴더 안에 섞으면 팀원이 작업 위치를 혼동한다.
- Flutter/Xcode 프로젝트는 생성 파일이 많기 때문에 처음부터 전용 폴더를 두는 편이 충돌을 줄인다.
- UI/UX 산출물과 실제 앱 코드는 수명주기가 다르므로 분리하는 것이 좋다.

### 8. 최상위 README 최신화

팀 브랜치 최상위 `README.md`는 오래된 플랫폼 소개 문구를 현재 구현 상태 기준으로 다시 작성했다.

수정한 내용:

- 최종 수정일을 2026-05-15로 갱신
- Python 3.13, FastAPI/Pydantic v2, Ollama local LLM, OCR fail-closed 기준 반영
- Nutrition backend가 실제 구현 중심이라는 점 명시
- Food image analysis, AI agent chat, frontend, mobile은 구조 준비 상태라고 구분
- `backend/Nutrition-backend`, `data/supplement_images`, `data/food_images`, `docs/Nutrition-docs` 기준 폴더 트리 반영
- `.env`, raw data, cache, coverage, PDF/ZIP/Office 원본을 Git에 올리지 않는 기준 명시
- 팀 브랜치 규칙과 담당 범위 표 반영

이렇게 결정한 이유:

- 기존 README에는 Python 3.11, Docker Compose, TimescaleDB, CI badge 등 현재 브랜치와 맞지 않는 설명이 남아 있었다.
- 팀원이 GitHub 첫 화면에서 보는 문서가 실제 파일 구조와 다르면 onboarding 비용이 커진다.
- 현재는 완성 서비스가 아니라 팀 통합을 위한 작업 공간이므로, 구현 완료/구조 준비/후속 구현을 분리해 쓰는 것이 정확하다.

### 9. 로컬 `.env` 업데이트와 비밀정보 제외

로컬 `.env`에는 DB, JWT, Redis, Google OAuth 관련 환경변수를 추가했다. 단, 이 값은 로컬 실행용이며 GitHub 커밋 대상에서 제외했다.

보고서에 실제 값을 쓰지 않는 이유:

- `.env`에는 비밀정보 또는 비밀정보가 될 수 있는 값이 들어간다.
- 팀 공유 문서에 실제 키값을 적으면 GitHub, PDF, 메신저를 통해 재노출될 수 있다.
- `.env.example`에는 변수 이름과 빈 값 또는 예시값만 두고, 실제 값은 각자 로컬에서 관리하는 것이 안전하다.

## GitHub 반영 내용

오늘 팀 GitHub에는 임시 clone을 사용해 반영했다.

### 1차 반영

- 커밋: `2851a23 chore(yeong-tech): publish curated Lemon Aid workspace`
- 내용: 로컬 `yeong-Lemon-Aid` 기준의 선별된 workspace를 팀 `yeong-tech` 브랜치에 반영
- 방식: 백업 브랜치 생성 후 기존 remote tree 삭제, 선별 복사, 검증, 커밋, 푸시

### 2차 반영

- 커밋: `ea1ffb9 docs(readme): align project overview with current workspace`
- 내용: 최상위 `README.md`를 현재 프로젝트 구조와 구현 상태에 맞게 재작성
- 푸시 대상: `Lemon-Aid-KDT/Lemon-sin`의 `yeong-tech`
- 원격 확인: `refs/heads/yeong-tech`가 `ea1ffb95d3b92978479ce0451e00edff58344774`로 갱신됨

임시 clone 방식을 사용한 이유:

- 현재 로컬 상위 Git 작업 트리는 많은 삭제/이동/신규 파일이 섞인 dirty 상태였다.
- 그 상태에서 직접 `git add -A`를 하면 원치 않는 cache, raw data, API key, PDF, ZIP, `.DS_Store`가 섞일 수 있었다.
- 임시 clone에서 작업하면 팀 브랜치에 올릴 파일만 명확하게 선별할 수 있고, 기존 원격 상태도 백업할 수 있다.

## 검증 결과

팀 브랜치 반영 전에 다음 검증을 수행했다.

| 구분 | 검증 내용 | 결과 |
| --- | --- | --- |
| JSON 설정 | `implementation-readiness.settings.json`, `service-segmentation.settings.json` parse | 통과 |
| KDRIs 데이터 | `validate_kdris_dataset.py` | 1,795 rows 통과 |
| Formatting | `black --check .` | 통과 |
| Lint | `ruff check .` | 통과 |
| Type check | 핵심 backend mypy | 통과 |
| Test | `pytest -q --no-cov` | `390 passed, 2 skipped` |
| Git diff | `git diff --cached --check` | 통과 |
| README 링크 | README 내부 문서 링크 존재 확인 | 통과 |
| README stale keyword | 오래된 README 키워드 스캔 | 통과 |
| publish tree scan | `.env`, cache, pycache, `.DS_Store`, api-key, htmlcov 포함 여부 확인 | 커밋 tree 기준 발견 없음 |

주의:

- `gh auth status`는 토큰 invalid로 실패했다.
- 이번 요청 범위는 PR 생성이 아니라 커밋·푸시였으므로, Git push로 브랜치 반영을 완료했다.
- PR이 필요하면 GitHub 인증을 다시 설정한 뒤 별도 생성해야 한다.

## 오늘 발생한 문제와 해결 방법

### 문제 1. 로컬 작업 트리가 너무 복잡했다

증상:

- 상위 Git 기준으로 기존 `yeong-Vision-Nutrition` 삭제, 새 `yeong-Lemon-Aid` 추가, `.github` 변경, 출력물, 캐시, 산출물이 함께 보였다.
- 이 상태에서 직접 커밋하면 의도하지 않은 파일이 들어갈 위험이 컸다.

해결:

- 팀 저장소를 임시 clone으로 따로 준비했다.
- 기존 `yeong-tech`를 백업 브랜치로 보존했다.
- 공유 가능한 파일만 선별 복사했다.
- 검증 후 팀 브랜치에 푸시했다.

결정 이유:

- dirty worktree에서 직접 force 정리하는 것보다 임시 clone이 안전하다.
- 원격 백업 브랜치가 있으면 잘못 푸시했을 때 되돌릴 기준점이 남는다.

### 문제 2. Nutrition 담당 폴더와 팀 공통 폴더의 경계가 불명확했다

증상:

- 처음에는 `docs`의 대부분 문서가 `Nutrition-docs`로 이동했고, 공통 문서가 무엇인지 혼동이 생겼다.
- backend도 `Nutrition-backend`로 강제 이동할지, 공통 backend root에 둘지 판단이 필요했다.

해결:

- 공통 문서는 `docs/` 루트에 복원 또는 유지했다.
- Nutrition 상세 문서는 `docs/Nutrition-docs/`로 분리했다.
- 실제 Nutrition 런타임은 `backend/Nutrition-backend/`로 이동했다.
- Food/Chat은 별도 skeleton을 만들었다.

결정 이유:

- 팀 공통 문서는 누구나 바로 확인해야 하므로 루트에 있어야 한다.
- Nutrition 상세 문서는 분량이 많고 담당 범위가 명확하므로 별도 폴더가 맞다.
- backend는 팀원별 기능 소유권을 반영해야 하므로 기능별 하위 폴더가 필요하다.

### 문제 3. 데이터 폴더가 영양제 데이터와 공식 reference 데이터로 섞여 보였다

증상:

- `data` 안의 일부 폴더가 영양제 이미지 데이터인지, KDRIs/MFDS 기준 데이터인지 구분하기 어려웠다.

해결:

- 영양제 이미지는 `data/supplement_images/`로 모았다.
- 음식 이미지는 `data/food_images/`로 분리했다.
- KDRIs, MFDS, nutrient code는 `data/nutrition_reference/`로 분리했다.

결정 이유:

- 이미지 데이터와 공식 기준 데이터는 생성·검수·사용 방식이 다르다.
- 음식과 영양제 이미지는 모델 분류 체계가 다르므로 같은 폴더에 두면 taxonomy가 복잡해진다.
- 공식 reference는 Food와 Nutrition 기능 모두에서 재사용 가능하므로 공통 reference가 맞다.

### 문제 4. README가 현재 구현 상태와 맞지 않았다

증상:

- README가 완성형 플랫폼처럼 보였고, 실제 구조 준비 상태와 구현 완료 상태가 섞여 있었다.
- Python 버전, CI, Docker Compose, 외부 OCR 기본값 등 일부 설명이 현재 브랜치와 맞지 않았다.

해결:

- README를 현재 파일 구조와 검증 결과 기준으로 재작성했다.
- 구현 완료, 구조 준비, 후속 구현을 표로 구분했다.
- Git에 올리지 않는 항목과 팀 브랜치 규칙을 명시했다.

결정 이유:

- 팀원이 가장 먼저 보는 문서가 README다.
- README가 최신 상태를 반영해야 불필요한 질문과 잘못된 setup을 줄일 수 있다.

### 문제 5. 최상위 README가 로컬 상위 Git에서는 untracked로 보였다

증상:

- 로컬 경로의 `yeong-Lemon-Aid/README.md`는 수정 완료됐지만, 상위 Git 기준으로는 `??` 상태였다.

해결:

- 로컬 dirty repo에서 직접 stage하지 않았다.
- 임시 clone의 tracked root `README.md`에 복사한 뒤 README 단일 파일만 커밋했다.

결정 이유:

- 상위 repo에서 `yeong-Lemon-Aid/` 전체가 untracked였기 때문에, 직접 stage하면 범위가 과해질 수 있었다.
- 임시 clone에서는 README 단일 변경만 명확하게 diff로 확인할 수 있었다.

### 문제 6. GitHub CLI 인증은 실패했지만 push는 가능했다

증상:

- `gh auth status`에서 기본 계정 token invalid가 확인됐다.

해결:

- PR 생성은 진행하지 않았다.
- 이미 Git remote push 권한은 동작했으므로 `git push team HEAD:yeong-tech`로 반영했다.

결정 이유:

- 사용자 요청은 PR 생성이 아니라 팀 브랜치 커밋 및 푸시였다.
- 인증이 필요한 GitHub CLI 작업과 Git push 작업을 분리해 처리하는 것이 맞다.

## 팀원이 확인해야 할 파일

우선 확인 파일:

- `README.md`
- `docs/05-github-guidelines.md`
- `docs/README.md`
- `backend/README.md`
- `backend/Nutrition-backend/README.md`
- `data/food_images/README.md`
- `data/supplement_images/README.md`
- `docs/Integration-docs/01-ci-pr-integration-operations.md`

Nutrition 담당 구현 확인 파일:

- `backend/Nutrition-backend/src/main.py`
- `backend/Nutrition-backend/src/config.py`
- `backend/Nutrition-backend/src/services/supplement_image_analysis.py`
- `backend/Nutrition-backend/src/ocr/factory.py`
- `backend/Nutrition-backend/src/regulated/ocr_intake.py`
- `backend/Nutrition-backend/tests/`

데이터 구조 확인 파일:

- `data/supplement_images/manifests/taxonomy.json`
- `data/supplement_images/manifests/classes.json`
- `data/food_images/manifests/taxonomy.json`
- `data/food_images/manifests/classes.json`
- `data/nutrition_reference/kdris/kdris_2025.csv`

오늘 작성한 정리 산출물:

- `outputs/todo-list/2026-05-15/2026-05-15-local-path-file-inventory.md`
- `outputs/todo-list/2026-05-15/2026-05-15-docs-folder-inventory.md`
- `outputs/todo-list/2026-05-15/2026-05-15-team-work-summary.md`

## Git에 올리지 말아야 할 항목

아래 항목은 팀 공유에는 필요하지만 Git 커밋 대상은 아니다.

- `.env`
- 실제 API key 또는 credential
- `api-key/` 내부 민감 자료
- `.venv/`
- `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`
- `__pycache__/`, `*.pyc`
- `htmlcov/`, `.coverage`
- `.DS_Store`
- 원본 이미지 데이터
- 대용량 PDF, ZIP, Office 원본 자료
- 모델 weight/checkpoint

## 다음 작업 제안

1. 팀원이 `yeong-tech` 브랜치의 최신 README와 `docs/05-github-guidelines.md`를 먼저 확인한다.
2. 각자 담당 브랜치에서 동일한 폴더 구조를 기준으로 작업한다.
3. Food 담당자는 `backend/food_image_analysis/`, `data/food_images/`, `docs/Food-docs/`를 기준으로 시작한다.
4. Chat 담당자는 `backend/ai_agent_chat/`, `docs/Chat-docs/`를 기준으로 시작한다.
5. Design/Mobile 담당자는 `frontend/`, `mobile/uiux/`, `mobile/flutter_app/`, `assets/`를 기준으로 시작한다.
6. DB 담당자는 `backend/alembic/`, `backend/scripts/`, `data/`, `config/`를 기준으로 확인한다.
7. PR 생성 전에는 `.env`, cache, raw data, PDF/ZIP/Office 원본이 섞이지 않았는지 반드시 확인한다.
8. `gh auth`를 다시 설정해 GitHub CLI 기반 PR 생성도 가능하게 만든다.

## 현재 결론

오늘의 핵심 성과는 프로젝트를 “개인 Nutrition 작업 폴더”에서 “팀원별 파트를 통합할 수 있는 Lemon Aid 작업 공간”으로 바꾼 것이다.

코드 구현 자체는 Nutrition backend가 가장 앞서 있고, Food/Chat/Frontend/Mobile은 작업 위치와 구조를 먼저 마련한 상태다. 따라서 다음 단계는 각 담당자가 자기 브랜치에서 이 구조를 기준으로 실제 기능 구현을 붙이고, `develop` 또는 팀 통합 브랜치로 PR을 보내는 흐름을 만드는 것이다.
