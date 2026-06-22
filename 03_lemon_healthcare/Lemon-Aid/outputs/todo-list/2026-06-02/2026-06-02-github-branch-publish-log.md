# 2026-06-02 GitHub 브랜치 커밋 및 푸시 기록

> 작성 기준: 2026-06-02
> 대상 repo: `Lemon-Aid-KDT/Lemon-sin`
> 대상 branch: `docs/docs-2026-05-31-backend-ocr-security`

---

## 1. Repo 확인

```text
Git root: /Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid
origin: https://github.com/Lemon-Aid-KDT/Lemon-sin.git
personal: https://github.com/HorangEe02/Project_yeong.git
```

이번 작업은 team remote인 `origin`만 사용한다. `personal` remote는 사용하지 않는다.

---

## 2. 현재 브랜치에 이미 push된 핵심 commit

- `e2cae66 feat(supplements): include medical context in analysis explanations`
- `53941e8 fix(ocr): detect allergen warning ROI anchors`
- `3c597b5 docs(todo): record current section publish state`
- `c6d5a94 fix(vision): require supplement YOLO section labels`
- `58cdd93 feat(vision): add supplement section YOLO dataset contract`
- `00e2c6d feat(vision): export supplement section YOLO annotations`
- `683a474 feat(vision): materialize supplement section YOLO dataset`

---

## 3. 이번 문서 커밋 대상

포함:

- `outputs/todo-list/2026-06-02/README.md`
- `outputs/todo-list/2026-06-02/2026-06-02-current-ocr-yolo-training-pipeline-handoff.md`
- `outputs/todo-list/2026-06-02/2026-06-02-github-branch-publish-log.md`

제외:

- untracked crawling/sample image directory
- frontend public/tech generated assets
- mobile app icon/uiux generated assets
- unrelated `.DS_Store`
- raw OCR/provider payload/source path가 들어갈 수 있는 산출물

---

## 4. 커밋 메시지 규칙

Conventional Commits 형식을 유지한다.

예정 커밋:

```text
docs(todo): record OCR YOLO training pipeline handoff
```

본문에는 `Why:`, `Constraint:`, `Tested:`, `Co-authored-by:`를 남겨 다음 작업자가 문서 목적과 검증 범위를 바로 확인할 수 있게 한다.

---

## 5. 푸시 전 검증 기준

```bash
git diff --check
git diff --cached --check
detect-secrets scan --all-files
git status --short --branch
```

문서 커밋은 code path를 바꾸지 않으므로 backend/mobile test 재실행 대신 이전 materializer 검증 결과와 diff hygiene/secret scan을 기준으로 한다.
