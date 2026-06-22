# 2026-06-21 WIP Cluster Commits and Housekeeping

## 기준

- Repo: `Lemon-Aid` / 작성일: `2026-06-21 KST`
- 주제: 누적 WIP를 검증 후 클러스터별 커밋 + 절대금지 바이너리 gitignore + ops/docs 선택 커밋
- 사용자 지시: "서비스 진행+피드백 위해 WIP 완성·커밋" → "권장사항대로, 절대 올리면 안되는 것은 절대 미커밋, 선택 커밋만"

## 오늘 완료한 작업

- [x] WIP 4 클러스터 검증(빌드/테스트/lint) 후 개별 커밋·양 리모트:
  - `486250f5` declaration 멀티라인 원재료 파서 (57 tests)
  - `ea1afd4a` 모바일 식단·영양제 관리 화면 + 배선 (435 tests; 신규 화면 import 동봉)
  - `2da9b57e` PaddleOCR 적응형 eval/데이터셋 도구 (58 tests; per-file ruff ignore)
  - `3d8a2e46` 음식 40-class 영양 + **마이그레이션 multiple-heads 수정**(0046_merge down_revision → 실제 head)
- [x] 절대금지 바이너리 gitignore:
  - `a9f05193` `data/Simulator Screenshot/`(373M) + `data/food_images/20*/`(44M) → `git add` footprint 418M→1.3M
  - `8fac4a85` `backend/food_image_analysis/`(food_classifier 핸드오프 중복본) 보존+제외
- [x] 선택 커밋:
  - `e0f985df` compose 서비스 env 핀(KDRIs 2025·one-shot fusion·OCR 튜닝; 시크릿 없음)
  - `24302590` OCR 성분recall 0.85/0.90 재설계 보고서 2개(docs)

## 결정 / 처리 원칙

- 절대 미커밋: `.env`(시크릿), 대용량 바이너리(스크린샷·food_images·모델 *.pdiparams/*.pt/*.zip — 일부는 이미 gitignore), `food_classifier` 중복본
- `food_classifier`: 라이브 정본 `Food-backend/src/classifier`가 실제 로드되는 중복본 → **삭제 안 함**, gitignore로 보존+제외
- `outputs/`는 통째 gitignore 금지(362 추적 중) — 모델 graph/manifest·작업로그는 사용자 도메인이라 미터치

## 상태

- 워킹트리 tracked-modified = 0 (정리 완료)
- 남은 untracked(비-ignored) = `outputs/generated/supplement-learning/*` + `outputs/todo-list/*`(사용자 추적 도메인)
