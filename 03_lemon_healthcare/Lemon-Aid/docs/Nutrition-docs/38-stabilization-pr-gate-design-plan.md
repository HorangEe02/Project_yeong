# 38. Stabilization PR Gate 상세 설계 및 구현 플랜

> 작성일: 2026-05-15
> 상태: 구현 완료
> 대상: root `.github/PULL_REQUEST_TEMPLATE.md`, project-local `03_lemon_healthcare/.github/PULL_REQUEST_TEMPLATE.md`, `docs/23`, `docs/Nutrition-docs/dev-guides/30`

---

## 1. 목표

P1 이후 AI/OCR/YOLO/학습 기능이 기존 backend 기준선을 깨지 않도록 PR 작성 단계에서 반드시 확인해야 할 gate를 명확하게 만든다. 이 gate는 테스트를 대체하지 않고, PR 작성자가 검증 결과와 sign-off 근거를 빠뜨리지 않도록 하는 사람 중심의 merge 전 점검 장치다.

강화할 항목은 다섯 가지다.

1. KDRIs validator 통과 확인
2. JWT/OIDC production-path test 통과 확인
3. 만성질환 우선순위 문구에 금지 표현이 없는지 확인
4. feature flag를 `true`로 바꿀 때 sign-off 문서 요구
5. raw image/raw OCR text 저장 금지 확인

---

## 2. 현재 상태 확인

현재 repository root는 `/Users/yeong/99_me/00_github`이고 Lemon Healthcare 프로젝트는 `03_lemon_healthcare` 하위에 있다.

구현 전 확인 결과:

- root `.github/PULL_REQUEST_TEMPLATE.md`는 없다.
- project-local `03_lemon_healthcare/.github/PULL_REQUEST_TEMPLATE.md`는 존재하며 P1 안정화 게이트 초안이 들어 있다.
- GitHub 공식 문서 기준 PR template은 repository root, `docs`, 또는 root `.github`에 있어야 자동으로 PR body에 적용된다.
- 따라서 project-local template만으로는 GitHub PR 작성 화면에 자동 적용된다고 볼 수 없다.

설계 결론:

- 실제 GitHub PR에 자동 적용하려면 root `.github/PULL_REQUEST_TEMPLATE.md`를 추가해야 한다.
- Lemon Healthcare 전용 세부 gate는 root template 안에서 "해당 시" 섹션으로 둔다.
- project-local template은 팀 문서/하위 프로젝트 reference로 유지하되, root template과 같은 gate 문구를 유지한다.

구현 결과:

- root `.github/PULL_REQUEST_TEMPLATE.md`를 추가했다.
- project-local `03_lemon_healthcare/.github/PULL_REQUEST_TEMPLATE.md`의 P1 gate 문구를 root template과 동기화했다.
- P1 gate는 Lemon Healthcare 관련 변경에만 적용되도록 "해당 시" 조건을 명시했다.

---

## 3. 브레인스토밍 결과

### 선택지 A: project-local template만 강화

장점:

- 현재 파일만 수정하면 된다.
- Lemon Healthcare 하위 프로젝트 안에서 문맥이 가장 명확하다.

단점:

- GitHub가 자동으로 PR body에 넣어주는 위치가 아니다.
- 실제 PR 작성자가 템플릿을 보지 못할 수 있다.

판단:

- 단독으로는 부족하다. reference 용도로는 유지하되, 실제 gate는 root template에 둔다.

### 선택지 B: root default PR template 추가

장점:

- GitHub PR 생성 시 자동으로 노출된다.
- 팀원이 별도 query parameter를 쓰지 않아도 같은 checklist를 본다.
- P1 안정화 gate가 누락될 가능성이 가장 낮다.

단점:

- 이 repository에 Lemon Healthcare 외 다른 프로젝트도 있으면 template이 넓게 보인다.
- 너무 많은 항목을 넣으면 PR 작성자가 형식적으로 체크할 수 있다.

판단:

- 이번 목표에 가장 적합하다. 단, Lemon Healthcare 전용 항목은 "해당 시" 조건을 명확히 달아 다른 프로젝트 PR의 부담을 줄인다.

### 선택지 C: root `.github/PULL_REQUEST_TEMPLATE/lemon_healthcare.md` 다중 템플릿

장점:

- Lemon Healthcare 전용 template을 분리할 수 있다.
- 다른 프로젝트와 template 충돌을 줄일 수 있다.

단점:

- 작성자가 `template` query parameter 또는 GitHub UI 선택 흐름을 알아야 한다.
- 기본 PR 생성 흐름에서는 누락될 수 있다.

판단:

- 후속 개선 후보로 둔다. 지금은 default template이 더 안전하다.

### 선택지 D: PR body lint action으로 체크박스 강제

장점:

- 사람이 checklist를 지우거나 비워도 CI에서 잡을 수 있다.
- sign-off 문서 링크 같은 필수 입력을 자동 검증할 수 있다.

단점:

- 별도 GitHub Action 또는 script가 필요하다.
- PR body permission, fork PR, bot PR 예외 처리가 필요하다.
- 이번 요구 범위보다 구현 복잡도가 크다.

판단:

- 이번 PR gate 1차 구현 범위에서는 제외한다. 템플릿 정착 후 반복 누락이 보이면 자동화한다.

---

## 4. 최종 설계

### 4.1 Template 위치

실제 GitHub 적용 대상:

- `.github/PULL_REQUEST_TEMPLATE.md`

하위 프로젝트 reference:

- `03_lemon_healthcare/.github/PULL_REQUEST_TEMPLATE.md`

규칙:

- root template은 모든 PR에 자동 노출되는 기본 template이다.
- Lemon Healthcare P1 gate는 "해당 시" 섹션으로 작성한다.
- project-local template에는 동일한 gate 문구를 유지해 하위 프로젝트만 보는 팀원도 같은 기준을 확인할 수 있게 한다.

### 4.2 Gate 적용 조건

다음 파일 또는 기능을 건드리면 P1 안정화 게이트를 적용한다.

| 변경 영역 | gate 적용 여부 | 이유 |
| --- | --- | --- |
| `backend/**` | 적용 | runtime/API/test 기준선 영향 |
| `data/nutrition_reference/kdris/**` | 적용 | KDRIs 분석 기준 영향 |
| `data/nutrition_reference/nutrient/**` | 적용 | 만성질환 우선순위, nutrient reference 영향 |
| `config/**` | 적용 | feature flag/readiness 영향 |
| AI/OCR/YOLO/학습 관련 코드 | 적용 | default-off, consent, raw data policy 영향 |
| docs-only | 조건부 | 사용자 노출 문구, 금지 표현, sign-off 문서 변경 시 적용 |

### 4.3 Checklist 설계

root template에는 다음 섹션을 넣는다.

```markdown
## 🧱 Lemon Healthcare P1 안정화 게이트 (해당 시)

<!-- 03_lemon_healthcare/yeong-Lemon-Aid의 backend/data/config/AI/OCR/YOLO/학습 변경이면 확인 -->

- [ ] KDRIs/nutrition_reference/config 변경 시 `python scripts/validate_kdris_dataset.py --require-approved` 통과
- [ ] JWT/OIDC/security 변경 시 production-path 테스트 통과
- [ ] 만성질환 우선순위 또는 사용자 노출 문구 변경 시 금지 표현 테스트 통과
- [ ] feature flag를 `true`로 바꾼 경우 sign-off 문서 링크와 production guard 테스트 포함
- [ ] OCR/LLM/이미지 변경 시 raw image/raw OCR text 저장 금지 확인
```

세부 기준:

- KDRIs validator는 CI hardening의 `KDRIs dataset gate`와 같은 command를 사용한다.
- JWT/OIDC 변경은 unit test만이 아니라 production 설정 경로를 통과하는 테스트 결과를 요구한다.
- 만성질환 우선순위 문구는 "진단", "치료", "처방", "복용량 변경", "완치", "보장" 같은 금지 표현을 포함하면 안 된다.
- feature flag `true` 변경은 sign-off 문서 링크 없이는 merge하지 않는다.
- OCR/LLM/이미지 변경은 DB, object storage, log, audit event에 raw image/raw OCR text가 남지 않는지 확인한다.

### 4.4 Sign-off 문서 기준

feature flag를 `true`로 바꾸는 PR은 다음 중 하나를 PR body에 링크해야 한다.

- `docs/**` 아래 sign-off 문서
- `outputs/todo-list/**` 아래 팀 공유 sign-off 기록
- 이슈 또는 PR comment로 남긴 reviewer approval record

sign-off 문서에 포함할 최소 항목:

- 켤 feature flag 이름
- 기본값을 `true`로 바꾸는 이유
- 통과한 테스트 명령
- production guard 결과
- raw data 저장 정책 영향
- reviewer 또는 승인자

### 4.5 Raw data 저장 금지 확인 범위

OCR/LLM/이미지 변경 PR은 다음 저장 위치를 확인한다.

- DB model과 migration
- service layer
- API response schema
- audit event metadata
- application log
- object storage 또는 temp file
- test fixture와 sample artifact

원칙:

- raw image bytes는 기본 저장하지 않는다.
- raw OCR text는 DB에 저장하지 않고 HMAC hash 또는 user-confirmed structured preview만 남긴다.
- raw model response는 저장하지 않는다.

---

## 5. 상세 구현 플랜

### Step 1. root PR template 생성

상태: 완료.

변경 파일:

- `.github/PULL_REQUEST_TEMPLATE.md`

작업:

- 기존 project-local template의 공통 섹션을 root template에 반영한다.
- Lemon Healthcare P1 안정화 게이트를 "해당 시" 섹션으로 추가한다.
- Conventional Commits 안내를 유지한다.

완료 기준:

- GitHub PR 생성 화면에서 template이 자동으로 보일 수 있는 위치에 있다.
- 다른 프로젝트 PR에도 과도한 부담이 되지 않도록 Lemon Healthcare gate 조건이 명시되어 있다.

### Step 2. project-local template 동기화

상태: 완료.

변경 파일:

- `03_lemon_healthcare/.github/PULL_REQUEST_TEMPLATE.md`

작업:

- root template과 같은 P1 gate 문구를 유지한다.
- "외부 OCR provider" 항목은 raw data 저장 금지와 consent gate 항목에 통합하거나 하위 항목으로 둔다.

완료 기준:

- root template과 project-local template의 P1 gate 의미가 충돌하지 않는다.

### Step 3. 문서 연결

상태: 완료.

변경 파일:

- `docs/Nutrition-docs/23-p1-stabilization-plan.md`
- `docs/Nutrition-docs/36-post-p1-execution-plan.md`
- `docs/Nutrition-docs/dev-guides/30-post-p1-execution-checklist.md`

작업:

- Stabilization PR gate 상세 설계 문서 링크를 추가한다.
- CI hardening과 PR gate의 역할을 분리해 설명한다.

완료 기준:

- CI는 자동 검증 기준, PR gate는 작성자/리뷰어 확인 기준으로 구분된다.

### Step 4. 검증

상태: 완료.

repo root에서 실행:

```bash
git diff --check
```

문서 trailing whitespace 확인:

```bash
rg -n "[[:blank:]]$" .github/PULL_REQUEST_TEMPLATE.md 03_lemon_healthcare/.github/PULL_REQUEST_TEMPLATE.md 03_lemon_healthcare/yeong-Lemon-Aid/docs/Nutrition-docs/38-stabilization-pr-gate-design-plan.md
```

template 위치 확인:

```bash
test -f .github/PULL_REQUEST_TEMPLATE.md
```

---

## 6. PR reviewer 운영 기준

리뷰어는 다음 기준으로 checklist를 본다.

| 체크 항목 | reviewer 확인 방식 |
| --- | --- |
| KDRIs validator | PR body 또는 CI log에서 command 통과 확인 |
| JWT/OIDC production-path | security test 파일과 CI/로컬 결과 확인 |
| 만성질환 문구 금지 표현 | user-facing text diff와 금지 표현 테스트 확인 |
| feature flag `true` | sign-off 문서 링크와 production guard test 확인 |
| raw image/raw OCR text | DB/model/service/audit/log diff와 관련 테스트 확인 |

체크박스가 비어 있어도 변경 범위에 해당하지 않으면 reviewer가 "해당 없음" comment를 남기고 진행할 수 있다. 단, feature flag `true`, raw data 저장, JWT/OIDC production path 변경은 "해당 없음" 처리하지 않는다.

---

## 7. 공식 문서 근거

- GitHub pull request template creation: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository
- GitHub issue and pull request templates overview: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates
