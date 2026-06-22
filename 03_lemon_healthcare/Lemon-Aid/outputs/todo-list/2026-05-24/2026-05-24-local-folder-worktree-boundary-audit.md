# Local Folder / Git Worktree Boundary Audit - 2026-05-24

## 확인 범위

- 로컬 기준 경로: `/Users/yeong/99_me/00_github/03_lemon_healthcare`
- 팀 GitHub export worktree: `/private/tmp/lemon-team-ocr-tampermonkey-category-labeling`
- 개인 GitHub monorepo worktree: `/private/tmp/lemon-ocr-tampermonkey-category-labeling`

## 결론

현재 `/Users/yeong/99_me/00_github/03_lemon_healthcare/Lemon-Aid`는 팀 GitHub 작업용 git checkout이 아니다.
이 폴더는 상위 repo `/Users/yeong/99_me/00_github` 안의 untracked local copy이며, `.env`와 `.env` backup이 들어 있고 일부 source tree가 빠져 있다.

따라서 팀 GitHub에 커밋/푸시되는 파일 기준은 다음 worktree가 authoritative이다.

```text
/private/tmp/lemon-team-ocr-tampermonkey-category-labeling
```

팀 GitHub root-layout은 `backend/`, `data/`, `docs/`, `mobile/`, `outputs/`가 repo root에 바로 있는 구조다.
개인 GitHub monorepo worktree는 같은 파일이 `03_lemon_healthcare/Lemon-Aid/...` 아래에 있다.

## pr2 / pr3 / yeong-Vision-Nutrition 확인

`pr2`, `pr3`, `yeong-Vision-Nutrition`은 새로 생성된 git worktree가 아니다.
현재 상위 repo `feat/ajin-project-refinement`의 tracked path로 존재한다.

확인 결과:

| 경로 | 상태 | 크기 | 비고 |
| --- | --- | ---: | --- |
| `03_lemon_healthcare/pr2` | tracked | 4 KB | placeholder `README.md` only |
| `03_lemon_healthcare/pr3` | tracked | 4 KB | placeholder `README.md` only |
| `03_lemon_healthcare/yeong-Vision-Nutrition` | tracked | 2.7 MB | legacy project snapshot |
| `03_lemon_healthcare/Lemon-Aid` | untracked | 9.1 GB | local copy, secrets/env/backups 포함 |

`pr2`/`pr3`는 commit `3f8bb811`에서 placeholder로 추가되었다.
`yeong-Vision-Nutrition`은 commit `792f96c3` 이력에 포함되어 있다.

## 삭제 가능 여부

- `pr2`, `pr3`, `yeong-Vision-Nutrition`
  - 물리적으로 삭제는 가능하지만, 현재 상위 repo에서는 tracked deletion이 된다.
  - 삭제하려면 `Project_yeong` 쪽 정리 PR/커밋으로 처리해야 한다.
  - Lemon-sin 팀 GitHub 작업과는 별개라 이번 OCR 팀 브랜치에 포함하지 않는다.
- `Lemon-Aid`
  - untracked local copy라 팀 GitHub 커밋 기준으로는 사용하지 않는다.
  - `.env`, `.env.backup-*`, `backend/.env`가 있으므로 삭제/이동 전 백업 정책을 먼저 정해야 한다.
  - 현재 상태에서는 이 폴더에서 git add/commit을 수행하지 않는다.

## 보안/유출 리스크

- `/Users/.../Lemon-Aid`에는 `.env`, `.env.backup-20260522-105854`, `.env.backup-prequote-20260522-111924`, `backend/.env`가 존재한다.
- 해당 폴더는 상위 repo에서 untracked라 실수로 `git add 03_lemon_healthcare/Lemon-Aid`를 하면 대량 파일과 secret 후보가 섞일 수 있다.
- 팀 GitHub export worktree에는 `.env` 파일이 없고, root-layout 파일만 커밋 대상으로 사용한다.

## 운영 방침

1. 팀 GitHub에는 `/private/tmp/lemon-team-ocr-tampermonkey-category-labeling` root-layout만 사용한다.
2. 개인 GitHub monorepo에는 `/private/tmp/lemon-ocr-tampermonkey-category-labeling/03_lemon_healthcare/Lemon-Aid` 경로만 사용한다.
3. `/Users/.../03_lemon_healthcare/Lemon-Aid`는 사용자가 명시 승인하기 전까지 삭제/이동하지 않는다.
4. 기본 경로를 `/Users/.../03_lemon_healthcare/Lemon-Aid`로 다시 쓰려면 먼저 현재 local copy를 `_archive/`로 이동하고, clean git worktree를 같은 경로에 다시 생성한다.
