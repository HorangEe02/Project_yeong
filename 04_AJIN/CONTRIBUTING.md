# 기여 가이드

## 브랜치 전략 — GitHub Flow

- `main` — 안정 버전 (production deploy 대상). **직접 push 금지**, PR + 리뷰 + CI 통과 후만 merge.
- `feature/<short-desc>` — 새 기능 개발
- `bugfix/<issue#>-<short>` — 버그 수정
- `hotfix/<short>` — 긴급 main 패치 (예외)
- `docs/<short>` — 문서만
- `refactor/<short>` — 리팩터
- `chore/<short>` — 의존성 업데이트, 환경 정비 등

브랜치 명은 영어 소문자 + 하이픈. 예:
- `feature/llm-router-primary-toggle`
- `bugfix/123-ollama-header-missing`
- `docs/architecture-diagram-update`

## 커밋 컨벤션 — Conventional Commits

```
<type>(<scope>): <subject>

<body — 한국어 OK>

<footer>
```

### Type
- `feat` — 새 기능
- `fix` — 버그 수정
- `docs` — 문서만 변경
- `style` — 코드 의미 변경 없는 포맷팅
- `refactor` — 기능 변경 없는 구조 개선
- `perf` — 성능 개선
- `test` — 테스트 추가/수정
- `build` — 빌드 시스템 (Dockerfile, requirements 등)
- `ci` — GitHub Actions
- `chore` — 기타 (의존성, 설정)
- `revert` — 이전 commit 되돌림

### 예시
```
feat(llm-router): add LLM_ROUTER_PRIMARY toggle for ollama/gemini priority

기본 chain 이 항상 Gemini 1순위였던 문제. 환경변수 LLM_ROUTER_PRIMARY=ollama
설정 시 자가 호스팅 Ollama 가 1순위, fallback 으로 Gemini. Cloud Run env 1줄 변경으로
즉시 토글 가능.

Closes #42
```

```
fix(ollama-provider): attach X-AJIN-Secret header to /api/chat httpx call

Caddy reverse proxy 가 secret 검증으로 403 반환했음. OllamaProvider 의
4개 httpx 호출(/api/version, /api/chat stream/non-stream, /api/embeddings)
모두 self._headers 부착하도록 수정.
```

- `subject` 는 영어 권장 (50자 이내, 명령형)
- `body` 한국어 OK (왜 이 변경이 필요한지 설명)
- 관련 이슈 닫으려면 `Closes #N`, 참조만이면 `Refs #N`

## PR 규칙

1. PR 제목: `<type>: <subject>` (commit 메시지 형식)
2. 본문: `.github/PULL_REQUEST_TEMPLATE.md` 사용 — 변경 내용·관련 이슈·테스트·스크린샷
3. **main merge 조건**:
   - ✅ CI 통과 (frontend lint+build, backend lint, Docker build)
   - ✅ 1명 이상 review approval
   - ✅ linear history (rebase 권장)
   - ✅ Conflict 해결 완료
4. **Squash merge** 권장 (히스토리 깔끔)
5. PR 크기 제한: 1,000 라인 미만 권장. 큰 변경은 여러 PR 로 분할.

### Draft PR
작업 중인 PR 은 `Draft` 로 열어 동료 의견을 받습니다. 완료 후 `Ready for review`.

## Code Review 가이드

### Reviewer
- 24h 이내 1차 review (LGTM 또는 changes requested)
- 코드 정확성·읽기 쉬움·테스트 적절성 우선
- nitpick 은 `nit:` 접두사로 표시

### Author
- review comment 모두 응답 (수용/반박/추가논의)
- force-push 후 `force-push 했음` 댓글로 알림 (review 추적성)

## 로컬 개발 검증 (PR 생성 전)

```bash
# 1. Frontend
cd frontend
npm run lint
npm run build

# 2. Backend
source .venv/bin/activate
ruff check .
black --check .
# pytest (tests 가 있는 모듈만)

# 3. Docker build (선택)
docker build --target slim -t ajin-backend:test .
```

## main 브랜치 보호 규칙 (settings)

다음이 GitHub Settings → Branches → main 에 적용되어 있어야 합니다:

- ✅ Require pull request before merging
- ✅ Require approvals (1)
- ✅ Require status checks to pass:
  - `frontend-lint-build`
  - `backend-lint`
  - `docker-build`
- ✅ Require linear history
- ✅ Block force pushes
- ✅ Block deletions

설정 검증 (관리자):
```bash
gh api repos/HorangEe02/Project_yeong/branches/main/protection
```

## CODEOWNERS

`.github/CODEOWNERS` 가 영역별 자동 reviewer 를 지정합니다. PR 생성 시 자동으로 reviewer 가 할당되니 별도 수동 지정 불요.

## 보안

secret 노출 의심 시 PR 생성 전 [`SECURITY.md`](SECURITY.md) 절차로 즉시 보고. 절대 GitHub Issue 에 평문 유출 X.
