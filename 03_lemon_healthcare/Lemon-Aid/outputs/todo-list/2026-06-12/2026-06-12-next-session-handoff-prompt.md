# 다음 세션 이어가기 프롬프트 (2026-06-12 작성)

> 아래 블록을 다음 세션의 첫 메시지로 그대로 붙여넣으면 됩니다.

---

Lemon-Aid 프로젝트 작업을 이어서 진행해줘. 아래는 직전 세션까지의 정확한 상태다.

## 저장소 / 환경
- 로컬 루트: `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid` (경로 공백 — 셸에서 항상 따옴표. 작업 전 `git rev-parse --show-toplevel`로 루트 확인)
- 브랜치: `feat/ai-agent-chat-import` · 리모트: `origin`=팀(Lemon-Aid-KDT/Lemon-sin, PR 대상 develop), `personal`=개인(HorangEe02/Project_yeong)
- 팀원 브랜치 스냅샷(읽기 전용): `../external/Lemon-sin-ai-agent-branch` (두 저장소는 무관 히스토리 — merge 금지, 경로 단위 checkout만)
- 빌드 타깃: Pixel 10 Pro(Android 17, AVD `Pixel_10_Pro` — 에뮬레이터 실행 시 `ANDROID_SDK_ROOT=~/Library/Android/sdk` 필수) / iPhone 17 Pro(iOS 26.5, 시뮬레이터 UDID `7B2E1A72-B3C9-4102-8E3C-0009CCBFB4FB` — 주의: 구 기록의 `71FB0384…`는 iOS **26.3** 런타임 기기. 동명 iPhone 17 Pro가 26.3/26.4/26.5 런타임에 각각 존재하므로 이름이 아닌 UDID로 지정할 것)
- dev 스택: `docker compose up -d db backend` (db=pgvector pg16, backend는 127.0.0.1:8000, AUTH_MODE=disabled). **DB는 alembic 0042까지 적용 완료** 상태. 컨테이너에 Ollama 없음 → LLM 경로는 결정론 폴백(코칭 응답 ~18초 지연 정상)

## 완료된 것 (전부 검증·커밋됨)
1. **팀원 챗봇 백엔드 통합**: lemon_ai_agent 패키지 + 16파일 클로저 + 6파일 병합 + 마이그레이션 0030~0041(FORCE RLS) + 라우트 `/ai-agent/chat`·`/daily-coaching` (18678f35~fe706716)
2. **구현 가이드 10편**: `mobile/uiux/implementation-guides/00~09` — figma 85프레임·백엔드 67라우트 전수 검증 기반 (78b8a0a0)
3. **가이드 09**: 복약/식사기록/알림 라우트 임포트(ecb97a0a) + 점수 영속화 옵트인 `persist_daily_health_score` 플래그+0042(599cb4f1)
4. **가이드 02·03·04·05·07·08 전부 구현**: 홈 실데이터+복약 카드(2c12bbb3)+캘린더/잠금/딥링크/영속(8b92af3f), 오늘의 기록/음식검색 폴백/지연삭제(320c4262), 설정 서브화면 4종+건강 프로필+복약 알림(cad8fafd, HC 제외), 카메라 후보선택/섭취량/2슬롯/오버레이(fb5f31a0), 성분 상세(efc95168), 챗 스냅샷 인라인(d61fe52c)
5. **E2E 스모크 (직전 세션)**: 마이그레이션 0029→0042 라이브 첫 적용 성공, RLS 정책 7건 DB 확인, API 풀 사이클 전 그린(동의/대시보드 health_score/복약/챗 안전 경계/챗 승인 루프 2단계+DB 영속/데일리 코칭 findings 실계산/음식 카탈로그/리마인더). **실거주 버그 3건 발견·수정**: 0042 제약명 naming convention 이중 접두사 + 챗 영속 트랜잭션 충돌 500(c2a86240), Flutter 코칭 페이로드 키 불일치(4ffa671c). iOS 통합 테스트 통과(시뮬레이터 빌드·실행·렌더)
- 품질 상태: Flutter `flutter analyze` 0건 · 테스트 353개 전통과 / 백엔드 pytest 허용 실패 2건(사용자 WIP: .mcp.json supabase 테스트, OCR readiness)만 / iOS 디버그 빌드 검증 완료

## 즉시 할 일 (우선순위)
1. **미푸시 커밋 2개 푸시**: `c2a86240`, `4ffa671c` → `git push origin feat/ai-agent-chat-import && git push personal feat/ai-agent-chat-import` (사용자 확인 후)
2. **Android 통합 테스트 마감**: `flutter test integration_test/app_smoke_test.dart -d emulator-5556`이 "No application found for TargetPlatform.android_arm64"로 실패 — build.gradle.kts의 flavor(dev/staging/prod) 미지정이 유력 원인. `--flavor dev` 지정(+필요시 `-PLEMON_ANDROID_APPLICATION_ID`)으로 재시도
3. **실기기 UI 워크스루**: API 레벨은 전부 그린이나 UI 레벨 풀 사이클(촬영→후보 선택→저장→홈→캘린더→설정→챗 승인 루프) 미수행 — 양 플랫폼에서 `flutter run --dart-define=LEMON_API_BASE_URL=...`(iOS는 기본 127.0.0.1, Android는 기본 10.0.2.2)로 수행
4. ~~**가이드 06 추이 차트**~~ ✅ 완료(2026-06-12): 결정 #7 채택 — 플래그 기본 true(compose), 목록 응답 score/measured_date/label 보강, `_TrendChartCard`(CustomPainter) 구현. 7일치 미만 잠금 유지
5. **P2 트랙**: 가이드 01 인증 — ✅ **Supabase Auth 채택**(ADR: `docs/Integration-docs/39-auth-backend-adr-supabase-auth.md`; 착수 시 Supabase 프로젝트/소셜 키 발급 필요). Health Connect(별도 결정), 알림 센터는 미결
6. (별도 트랙) **A100 PaddleOCR**: 조기종료 감시자 2개(patience 10) 가동 중 — b16 조기종료 시 lr1e4 자동 기동. 상태 확인: `ssh -i ~/.ssh/lemon_a100_ed25519 -p 8875 lemon-aid@155.230.153.222 'powershell -NoProfile -ExecutionPolicy Bypass -File G:\lemon-aid\paddleocr_rec_work\a100_compact_status_check.ps1'` (Bypass 플래그 없으면 원격 실행 정책이 스크립트 차단). 종료 후 작업: best 회수(b16/b32 비교)→structured eval(full/section/ROI)→승격 게이트(field_match≥0.85, ned≥0.90)

## 적용 중인 규칙 (위반 금지)
**협업/품질**: 수치·결과 추정 금지(로그/출력 확인값만 보고) · framework 파라미터 변경 시 공식 문서 확인+URL 주석 · private image/raw OCR/provider payload/secret/owner hash 결과물·커밋 금지 · 원격(155.230.153.222) 업로드/실행은 사용자 승인 후 · 원본 dataset(`rec_dataset\v2`) 불가침(sanitized 사본만) · Conventional Commits + 본문에 "왜" · **사용자 요청 없이 commit/push 금지** · remote/branch 혼동 금지 · 주요 함수 Google/NumPy docstring · 복잡 로직 주석은 "왜" 중심
**프로젝트**: 의료법 금칙어(진단/처방/치료/효능) 금지+신규 문구 테스트 가드 · 신뢰도 % 직접 노출 금지(등급 칩) · 분석/권고 화면 면책 푸터(`lib/widgets/common/medical_disclaimer.dart`) · 디자인 토큰 design_tokens_v2만(hex 단독 금지) · ApiClient 경로 `/api/v1` 접두사 제거 · 403 consent_required→1회 동의 후 재시도 패턴 · 시니어 최소치(본문 15px+/버튼 52px+) · 백엔드 신규 PII 테이블 0041 RLS 패턴 · 검증 게이트: `flutter analyze` 0건+테스트 전통과(현 353), 백엔드 `backend/.venv/bin/python -m pytest Nutrition-backend/tests -q -o addopts=""` 허용 실패 2건뿐, `release_security_config_test` 통과(main 설정 cleartext 금지 — debug 오버레이만)
**구현 방식**: 화면 작업은 해당 가이드(`mobile/uiux/implementation-guides/0X-*.md`)의 ④ 체크리스트를 권위로 따르고, "백엔드 공백" 명시 항목은 임의 구현 금지

## 참조 문서
- 가이드 세트: `mobile/uiux/implementation-guides/00-overview-and-conventions.md` (인덱스·매트릭스·권장 순서)
- 직전 상태: `outputs/todo-list/2026-06-11/` 4편 + 이 파일
- 점수 산정·보류 결정: `2026-06-11-daily-health-score-decisions.md`
- figma 프레임 ID: `mobile/uiux/figma/_frames_index.md`
