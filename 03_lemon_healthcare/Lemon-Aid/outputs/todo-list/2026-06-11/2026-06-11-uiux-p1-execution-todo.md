# 2026-06-11 UI/UX 통합 — P1/P2 실행 체크리스트

> 전체 설계: `mobile/uiux/2026-06-10-uiux-redesign-endpoint-integration-plan.md`
> P0는 완료(세션 요약 참조). 아래는 남은 단계. 검증 규칙: 각 항목 완료 시 `flutter analyze` 0건 + `flutter test` 전체 통과(현재 170개 기준) / 백엔드는 `backend/.venv/bin/python -m pytest Nutrition-backend/tests -q -o addopts=""` (허용 실패 = 사용자 WIP 2건뿐).

---

## P0 완료 확인 (2026-06-11 기준 ✅)
- [x] 토큰 단일화 + 4색 브랜드 테마 (`eb11363c`)
- [x] 챗 레몬봇 실연동 — /ai-agent/chat (`10cbc199`)
- [x] 홈 실데이터 + health_score (`4fab30d6`, 백엔드 `b43b9bfd`)
- [x] 분석결과 C + comprehensive 5카드 (`f6400e09`)
- [x] 점수 탭 → 오늘의 분석 + daily-coaching (`88c3ef4b`)
- [x] 상태/모달 템플릿 (`547713b1`) / Android cleartext 디버그 픽스 + iOS 한국어 권한 (`784687ce`)

## P0 잔여 (시작 전 필수)
- [ ] **E2E 스모크** — `alembic upgrade head` 첫 실행(0030~0041) → uvicorn → 에뮬/시뮬 풀 사이클(촬영→분석→저장→홈 점수→챗→오늘의 분석). *플랫폼: Pixel 10 Pro(Android 17) + iPhone 17 Pro(iOS 26.5)*
- [ ] dev 스택용 LLM 선택 기동(선택) — Ollama `gemma4:e4b` 또는 SGLang; 미기동 시 결정론 답변으로 데모

## P1 — 흐름 완성
- [ ] **P1-1 복약 라우트 임포트** — 팀원 워크트리에서 `src/api/v1/user_medications.py`/`food_records.py`/`notifications.py` + 의존 스키마/예시 선별 임포트, router 등록, 테스트 동반. ⚠️ 백엔드 통합 때와 동일하게 로컬 슈퍼셋 보존 원칙
- [ ] **P1-2 홈 복약 카드 실연동** — user_medications GET/POST + 복용 체크 서버 동기화(현재 세션 메모리 TODO(persist) 교체), 상호작용 카드 '약 미등록' → 실제 약 기준 점검
- [ ] **P1-3 캘린더 + 오늘의 기록** — 월 그리드 기록 점(GET /meals 날짜 범위 + /supplements), 일자 상세 행 → 기록 상세(figma 05-⑥, 12-⑤). 현재 placeholder 라우트(`/shell/home/calendar`) 교체
- [ ] **P1-4 설정 서브화면** — 프로필 편집(profile-snapshots POST), 건강 프로필 만성질환 칩(medical-records POST/confirm), 알림 설정 토글, 약관·정책, 회원 탈퇴(data-deletion-requests) (figma 15보드, 05-⑦)
- [ ] **P1-5 복약 알림(로컬)** — flutter_local_notifications + 시간 휠 바텀시트(16-①) + 요일 반복(10-④); shared_preferences 추가 시 테마/체크 상태 TODO(persist) 일괄 해소
- [ ] **P1-6 Health Connect(Android 먼저)** — health 패키지 + 매니페스트 권한 + 연동 화면(10-①) + `POST /health/sync` → 활동 서브점수가 실걸음수 사용, HR 분 동기화 시 v2 보정 실활성화
- [ ] **P1-7 음식 후보 선택 UI** — food_candidates 일치 등급 칩 + 섭취량 칩/스테퍼(06-②, 16-④) → confirm payload portion 반영, 0건/저신뢰 → 직접 입력 검색(GET /meals/foods)
- [ ] **P1-8 추이 차트 잠금 해제(선행: 점수 영속)** — 보류 결정 #7 채택 시 AnalysisType.DAILY_HEALTH_SCORE + 저장 → 오늘의 분석 4주 추이 실데이터

## P2 — 인증·확장
- [ ] auth 백엔드 결정(Supabase Auth 우선 검토) → figma 01/02/13 보드(소셜/이메일 인증/9단계 가입/계정 충돌)
- [ ] 가입 위저드 선반영 가능분 — 약관 동의 시트를 동의 게이트 UI로(영문 ConsentGateScreen 교체), 신체 정보→profile-snapshots
- [ ] 알림 센터 서버화 / 처방전·검사지 OCR 화면(feature flag) / (보류) 리워드
- [ ] 온보딩 3장 + 촬영 가이드 모달 '다시 보지 않기' (08보드)

## 회귀 가드 (모든 배치 공통)
- [ ] 의료법 금칙어(진단/처방/치료/효능) — 신규 사용자 문구 추가 시 테스트에 부재 assert 동반
- [ ] release_security_config_test 통과 유지 (main 네트워크 설정에 cleartext 예외 금지 — debug 오버레이만)
- [ ] 신뢰도 % 직접 노출 금지(등급 칩) — SoT §7
- [ ] 면책 푸터 — 모든 분석/권고 화면 하단
