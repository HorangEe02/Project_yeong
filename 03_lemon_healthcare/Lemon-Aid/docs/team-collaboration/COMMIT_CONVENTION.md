# ✍️ 커밋 메시지 컨벤션 (Conventional Commits)

> 모든 커밋은 **Conventional Commits 1.0** 형식을 따릅니다. 자동화(changelog·세맨틱 버전)와 가독성을 위해 필수입니다.

---

## 1. 기본 형식

```
<type>(<scope>): <subject>

<body (선택)>

<footer (선택)>
```

- **type** — 변경의 종류 (영문 소문자, 아래 목록 참조)
- **scope** — 변경 영역 ([`BRANCH_STRATEGY.md`의 영역 목록](./BRANCH_STRATEGY.md#2-영역scope-표준-목록)과 동일)
- **subject** — 한글 또는 영문, **명령형** ("추가", "수정" / "add", "fix"), **마침표 없음**, 50자 이내
- **body** — 변경 이유·배경 (왜 변경했는지). 72자에서 줄바꿈
- **footer** — `BREAKING CHANGE:`, `Closes #123`, `Refs #45`

---

## 2. type 목록

| type | 언제 사용 | 예시 |
|------|-----------|------|
| `feat` | 새 기능 추가 | `feat(mobile): 메인 대시보드 5탭 셸 추가` |
| `fix` | 버그 수정 | `fix(ocr): naver-chronic-0001 스냅샷 미스매치 해결` |
| `docs` | 문서만 변경 | `docs(team): develop 워크플로우 가이드 추가` |
| `style` | 포매팅·세미콜론 등 동작 영향 없는 변경 | `style(backend): black 포매팅 적용` |
| `refactor` | 동작 동일, 구조 개선 | `refactor(backend): supplement service 분리` |
| `perf` | 성능 개선 | `perf(ocr): PaddleOCR 배치 처리 적용` |
| `test` | 테스트 추가/수정 | `test(backend): meal compliance 통합 테스트 추가` |
| `chore` | 빌드·도구·의존성 | `chore(infra): Python 3.13 호환 의존성 상향` |
| `ci` | CI 설정 변경 | `ci(infra): sync-guide 워크플로 setup-python 3.13` |
| `build` | 빌드 시스템·외부 의존성 | `build(mobile): pubspec.yaml dio 5.4 상향` |
| `revert` | 이전 커밋 되돌리기 | `revert(ocr): textline_orientation 기본값 복구` |
| `data` | 데이터셋·픽스처 추가/변경 | `data(ocr-eval): 16개 만성질환 픽스처 추가` |
| `ops` | 운영·배포·모니터링 | `ops(ocr): 스테이징 vision api_key 모드 경고` |

> 기존 브런치에서 이미 `feat(ai)`, `chore(repo)`, `data(ocr-eval)`, `ops(lemon-backend)` 같은 형태를 사용 중입니다 — 이 컨벤션은 그 패턴과 호환됩니다.

---

## 3. subject 작성 규칙

✅ **권장 (한글 명령형, 마침표 없음)**

```
feat(mobile): 회원가입 플로우와 LADS 디자인 시스템 추가
fix(backend): 이메일 중복 검사 Redis rate-limit 누락 수정
docs(team): develop 머지 규칙과 PR 템플릿 정리
```

✅ **권장 (영문, lower case, 마침표 없음)**

```
feat(ai): add tool-use coaching agent skeleton
fix(ocr): correct CER calculation for korean chars
chore(deps): bump fastapi to 0.115
```

❌ **금지**

```
mobile dashboard update.                 ← type/scope 없음, 마침표
[mobile] 대시보드 업데이트했음             ← 옛 패턴 (대괄호), 과거형
Feat(Mobile): Update                     ← 대문자
feat: 수정함                              ← 너무 모호
WIP                                       ← WIP 커밋은 PR 머지 전에 fixup
```

---

## 4. body 작성 가이드

**언제 body를 쓰나?**
- 변경 이유가 코드만 봐서는 명확하지 않을 때
- 트레이드오프·대안을 기록해야 할 때
- 관련 이슈/PR을 인용해야 할 때

**좋은 body**

```
feat(ocr): LLM-aware evaluation + ko/en CER/WER + chronic grouping

기존 Tier-0/1 평가는 영어 메트릭만 사용하여 한글 라벨 정확도를
과대평가하는 문제가 있었음. 이번 변경으로:
- 한/영 CER/WER을 분리 측정
- 만성질환 카테고리별 그룹 메트릭 추가
- LLM 출력 검증을 위한 chronic_disease_matrix 통합

평가 결과는 outputs/generated/ocr-eval/ 아래 자동 갱신.

Closes #142
Refs PR #150
```

---

## 5. footer 사용

| footer | 의미 | 예 |
|--------|------|----|
| `Closes #N` | 이슈 자동 종료 | `Closes #142` |
| `Refs #N` | 참고만 (종료 X) | `Refs #99` |
| `BREAKING CHANGE: ...` | 호환 깨짐 알림 (major bump 트리거) | `BREAKING CHANGE: /v1/supplements 응답 스키마 변경` |
| `Co-Authored-By: ...` | 공동 작성자 | `Co-Authored-By: ParkSungHoon <bell@example.com>` |
| `Reviewed-by: ...` | (선택) 사전 리뷰어 명시 | — |

---

## 6. Squash 머지 시 커밋 메시지

PR을 Squash and Merge할 때 생성되는 단일 커밋은:

- **제목** = PR 제목 (Conventional Commits 형식)
- **본문** = PR 설명의 핵심 (자동 생성된 commit 리스트는 제거)

예시:

```
feat(mobile): Flutter ↔ backend OCR 5카드 종합분석 (#42)

- POST /supplements/analyze/comprehensive 연결
- 5장 카드 UI (영양/만성/상호작용/주의/추천)
- iOS 빌드 검증 완료

Closes #38
Closes #41
```

---

## 7. 자동 검증

로컬에서 `commit-msg` hook이 형식을 검증합니다. 설치는 [`LOCAL_SETUP.md`](./LOCAL_SETUP.md) 참고.

검증 실패 예:

```
$ git commit -m "fix stuff"
✖  type 누락 — '<type>(<scope>): <subject>' 형식이어야 합니다.
   허용 type: feat, fix, docs, style, refactor, perf, test, chore, ci, build, revert, data, ops
   예: feat(mobile): 대시보드 5탭 셸 추가
```

---

## 8. 치트시트

```
feat   = 기능 추가      fix   = 버그 수정     docs  = 문서
refactor = 구조 개선     test  = 테스트         chore = 도구/빌드
perf   = 성능            ci    = CI 설정        style = 포매팅
data   = 데이터/픽스처    ops   = 운영/배포     build = 빌드 시스템

scope: mobile · backend · ai · ocr · db · auth · ux · infra · docs · team · test · data
```

---

## 관련 문서

- [`BRANCH_STRATEGY.md`](./BRANCH_STRATEGY.md) — 영역 목록
- [`PR_GUIDELINES.md`](./PR_GUIDELINES.md) — PR 제목도 같은 형식
- [`LOCAL_SETUP.md`](./LOCAL_SETUP.md) — commit-msg hook 설치
