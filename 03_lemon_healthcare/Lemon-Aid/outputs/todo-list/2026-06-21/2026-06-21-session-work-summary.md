# 2026-06-21 Session Work Summary

## 기준

- Repo: `Lemon-Aid`
- 작성일: `2026-06-21 KST`
- 브랜치: `fix/mobile-theme-and-watch-label`
- 리모트: `origin`(Lemon-Aid-KDT/Lemon-sin) + `personal`(HorangEe02/Project_yeong) — 전 커밋 양 리모트 푸시
- 주제: 영양제 분석 품질 수정 + 챗봇 LLM-WIKI RAG 재설계 + WIP 정리/하우스키핑 + 데모 영상/모바일 빌드

## 오늘 완료한 작업 (커밋 순)

- [x] `db6965e8` perf(ollama): gemma 모델 요청 간 상주(keep_alive)
- [x] `c99fcf3b` / `b97ce1a4` raw OCR 텍스트 저장 게이트 + 전용 동의(RAW_OCR_TEXT_RETENTION)
- [x] `fa7862e8` 성분명 한글(영문) 현지화(결정적 EN→KO 사전)
- [x] `a21b691b` 멀티이미지 단일제품 융합 + OCR 비성분 노이즈 필터
- [x] `486250f5` declaration 멀티라인 원재료명 파서
- [x] `ea1afd4a` 모바일 식단·영양제 관리 화면 + 배선
- [x] `2da9b57e` PaddleOCR 적응형 eval/데이터셋 도구
- [x] `3d8a2e46` 음식 40-class 영양 이미지분석 + 마이그레이션 multiple-heads 수정
- [x] `a9f05193` / `e0f985df` / `24302590` / `8fac4a85` 하우스키핑(스크린샷·food-image gitignore / compose env 핀 / OCR docs / food_classifier gitignore)
- [x] `9dc85387` 영양제 파서 2버그: Ubiquinol 빈결과 구제 + 아연 멀티컬럼 중복 제거
- [x] `3cacded1` 섭취 주의사항 한국어 번역 안정화
- [x] `4efcf8fa` / `9b4e644d` / `367b26bf` 챗봇 LLM-WIKI RAG 재설계 + 배포 설정 + grant SQL
- [x] 데모 영상 2종 편집(<1분, <2분) + GIF
- [x] iPhone 17 Pro(iOS 26.5) + Pixel 10 Pro 빌드·설치·실행

## 상세 문서 (같은 폴더)

- `2026-06-21-supplement-analysis-quality-fixes.md` — 성분명 한글화·융합·파서 2버그·번역
- `2026-06-21-chatbot-llm-wiki-rag-redesign.md` — 챗봇 RAG 재설계(가장 큰 작업)
- `2026-06-21-wip-cluster-commits-and-housekeeping.md` — WIP 4클러스터 + gitignore/compose/docs
- `2026-06-21-demo-video-and-mobile-builds.md` — 데모 영상/GIF + iOS/Android 빌드

## 검증 / 품질

- 백엔드 다회 재빌드(`docker compose build backend`) + `--force-recreate`, health 200, 라이브 검증 완료
- 적대 리뷰(code-reviewer opus) 2건 **APPROVE** — 파서 fix(2 MEDIUM 닫음), 챗봇 RAG(2 MEDIUM 닫음)
- 전체 단위 테스트: 신규 실패 0 (기존 41건 pre-existing debt = chronic_disease_matrix / nutrition comprehensive / ocr_live_manifest / alembic_setup / ollama_parser, 내 변경과 무관 — stash-test로 확인). ruff/black 클린

## 잔여 / 후속 (선택)

- 챗봇 검색 품질: overview성 질문은 질병별 문서가 cosine 더 높아 general 폴백 가능 → hybrid 모드/top-k 확대/re-rank 튜닝 여지
- `lemon_app`의 `GRANT USAGE ON SCHEMA extensions`: DB 볼륨 리셋 후 재적용 필요(스크립트 `backend/scripts/db_poc/grant_lemon_app_extensions_usage.sql` 커밋됨)
- `food_classifier` tool dir: 보존(gitignore) — 라이브 정본은 `Food-backend/src/classifier`
- OCR garbage 파편(Men/Vitamin 등 3+자): 기존 conservative filter 미포착(별개 잔여)
