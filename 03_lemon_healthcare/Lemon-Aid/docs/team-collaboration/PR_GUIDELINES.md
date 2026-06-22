# 🔀 Pull Request 가이드라인

> 모든 코드 변경은 PR을 통해 `develop`으로 머지됩니다. 직접 push는 금지(보호 규칙으로 차단).

---

## 1. PR 제목

[`COMMIT_CONVENTION.md`](./COMMIT_CONVENTION.md)의 커밋 메시지와 **동일한 형식**을 사용합니다.

```
<type>(<scope>): <subject>
```

**OK**

- `feat(mobile): 메인 대시보드 5탭 셸 + LADS 디자인 시스템`
- `fix(ocr): naver-chronic-0001 스냅샷 미스매치 해결`
- `chore(infra): Python 3.13 호환 의존성 상향`

**NG**

- `Update dashboard` (type/scope 없음)
- `WIP: working on mobile` (WIP은 Draft PR로)
- `여러 변경사항` (subject가 모호)

---

## 2. PR 본문 템플릿

`.github/PULL_REQUEST_TEMPLATE.md`에 다음을 둡니다:

```markdown
## 📌 요약 (Why)
<!-- 무엇을, 왜 변경했는지 1-3줄 -->

## 🔧 변경사항 (What)
<!-- 핵심 변경을 bullet로 -->
-
-
-

## 🧪 테스트 (How verified)
<!-- 어떻게 확인했나 -->
- [ ] 단위 테스트 추가/통과
- [ ] 통합 테스트 통과 (`pytest tests/integration/`)
- [ ] 로컬 수동 검증 (시나리오/스크린샷 첨부)

## 📸 스크린샷 / 로그 (UI · OCR · 모바일)
<!-- 해당 시 -->

## ✅ 체크리스트
- [ ] PR 제목이 Conventional Commits 형식
- [ ] 브런치 이름이 `<type>/<scope>-<주제>` 형식
- [ ] `develop` 최신 변경을 rebase로 동기화함
- [ ] pre-commit 모든 hook 통과
- [ ] CI 모든 체크 green
- [ ] 관련 문서 업데이트 (PROJECT_GUIDE.md, docs/*)
- [ ] 비밀키·.env·대용량 파일 없음
- [ ] 의존성 변경 시 `requirements.txt` / `pubspec.yaml` 반영

## 🔗 관련
<!-- Closes #N / Refs #N / 관련 PR -->
Closes #
```

---

## 3. PR 크기 가이드

| 변경 줄 수(추가+삭제) | 권장 여부 | 비고 |
|----------------------|----------|------|
| ≤ 200 | ✅ 이상적 | 빠른 리뷰, 낮은 충돌 |
| 200–500 | ⚠️ 허용 | 분할 가능성 검토 |
| 500–1000 | 🛑 분할 권장 | 리뷰어 부담 큼, 사유 PR 본문에 기재 |
| > 1000 | ❌ 분할 필수 | 예외: 자동 생성 코드, 픽스처, 마이그레이션 |

**큰 PR을 쪼개는 패턴**
1. `chore`: 빌드/도구 (먼저 머지)
2. `refactor`: 구조 변경 (동작 불변)
3. `feat`: 새 기능
4. `test`: 테스트 강화
5. `docs`: 문서

---

## 4. 리뷰 절차

```
[PR 생성] → [CI 자동 실행] → [리뷰어 1명 지정] → [리뷰 + 수정] → [Approve + Squash Merge] → [브런치 자동 삭제]
```

**리뷰어 지정 규칙**
- 본인 영역 외 최소 1명에게 요청 (예: `feat(backend)`이면 mobile/ai 영역 팀원 1명)
- `feat(infra)` / `chore(infra)` 는 메인테이너 필수 리뷰
- 24시간 안에 첫 응답을 받지 못하면 다른 리뷰어 추가 또는 Slack `#dev` 핑

**작성자 책임**
- CI 빨간색 = 작성자가 먼저 고치고 리뷰 요청
- 리뷰 코멘트는 **모두 해결(resolved)** 후 머지
- 머지 직전 `develop` 최신화 (rebase)

**리뷰어 책임**
- 24시간 이내 첫 코멘트
- LGTM만 남기지 말고 의도 확인 1-2개 질문
- [`CODE_REVIEW_CHECKLIST.md`](./CODE_REVIEW_CHECKLIST.md) 항목 점검

---

## 5. 머지 방식

| 대상 | 방식 | 이유 |
|------|------|------|
| `feat/*` `fix/*` `chore/*` … → `develop` | **Squash and Merge** | develop 히스토리를 깔끔히 유지 (PR 1개 = 커밋 1개) |
| `develop` → `main` | **Merge commit (no-ff)** | 릴리스 단위로 묶음 추적 |
| `hotfix/*` → `main` | **Merge commit** | 긴급 수정 흔적 보존 |
| `hotfix/*` → `develop` | **Cherry-pick** | 동일 변경을 develop에도 |

**Squash 시 자동 생성되는 커밋 메시지 점검**
- 제목 = PR 제목 (그대로 두기)
- 본문 = PR 설명 핵심 옮기기, 자동 커밋 리스트는 제거

---

## 6. Draft PR

- **언제** — 작업 중간에 피드백을 받고 싶을 때, CI를 미리 돌리고 싶을 때
- **표시** — GitHub에서 "Draft" 상태로 생성
- **머지 불가** — Draft 상태에서는 머지 버튼 비활성
- **준비 완료 시** — "Ready for review" 클릭 → 정식 PR

---

## 7. 자가 머지 금지

- ❌ 본인이 작성한 PR을 본인이 Approve / Merge 할 수 없음
- ❌ "급해서" 셀프 머지하는 것 금지 (보호 규칙으로 차단)
- ✅ 정말 급하면 `hotfix/*` 절차로 + 사후 회고 기록

---

## 8. 이슈 ↔ PR 연결

- 새 작업은 **이슈 먼저 생성** (기능 명세·DoD 정리)
- 이슈 번호를 브런치/PR/커밋에 인용
  ```
  브런치: feat/mobile-dashboard-#42
  PR 제목: feat(mobile): 대시보드 5탭 셸 추가
  PR 본문: Closes #42
  ```
- PR 머지 시 이슈 자동 종료

---

## 9. PR 라벨 (권장)

| 라벨 | 의미 |
|------|------|
| `area: mobile` `area: backend` `area: ai` `area: ocr` `area: db` `area: auth` `area: ux` `area: infra` `area: docs` | 영역 표시 |
| `size: XS/S/M/L/XL` | 변경 크기 |
| `priority: P0/P1/P2` | 우선순위 |
| `needs-design` | 디자인 결정 필요 |
| `blocked` | 다른 PR/이슈에 의존 |
| `breaking` | 호환 깨짐 |

---

## 10. 자주 만나는 상황

### 🔴 CI 실패
1. 실패한 job 클릭 → 로그 확인
2. 로컬에서 같은 명령 재현 (`pre-commit run --all-files`, `pytest`)
3. 고친 뒤 같은 브런치에 push (PR 자동 갱신)

### 🔴 develop과 충돌
[`MERGE_AND_CONFLICT.md`](./MERGE_AND_CONFLICT.md) 참조

### 🔴 리뷰가 너무 오래 걸림
- 24시간 안 답이 없으면 다른 리뷰어 추가
- 그래도 안 되면 데일리 스탠드업에서 공개 요청

### 🔴 의존성 PR(다른 PR 머지 후에 머지)
- PR 본문에 `Depends on #N` 명시
- `blocked` 라벨

---

## 관련 문서

- [`COMMIT_CONVENTION.md`](./COMMIT_CONVENTION.md) — 제목 형식
- [`CODE_REVIEW_CHECKLIST.md`](./CODE_REVIEW_CHECKLIST.md) — 리뷰 항목
- [`DEVELOP_WORKFLOW.md`](./DEVELOP_WORKFLOW.md) — 전체 흐름
