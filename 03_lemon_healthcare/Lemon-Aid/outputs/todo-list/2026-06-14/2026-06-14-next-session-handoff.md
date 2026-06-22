# Lemon-Aid 다음 세션 핸드오프 프롬프트 (2026-06-14)

> 새 세션 시작 시 이 파일을 그대로 붙여넣어 이어서 작업한다. 아래는 환경·규칙·잔여 작업이다.

---

## 0. 한 줄 요약

PR#4 임포트 이후 OCR 트랙 + Supabase Auth 백엔드 + RLS Stage-1 + 모바일 Auth 1·2단계를 완료했다(12커밋, 양 리모트 푸시). 남은 큰 줄기는 **모바일 Auth 3단계(supabase_flutter, 라이브 게이트)**, **RLS Stage-2 활성화(인프라 게이트)**, **섹션 검출기 학습(운영자+A100 게이트)**, Health Connect, 알림 센터다.

## 1. 환경

- **리포 경로(외장 SSD)**: `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid`. 모든 작업물·커밋은 이 경로에 둔다(`/tmp` 등 임시 경로 지양 — 사용자 명시).
- **브랜치**: `feat/ai-agent-chat-import`. **리모트 2개에 모두 푸시**: `origin`(Lemon-Aid-KDT/Lemon-sin) + `personal`(HorangEe02/Project_yeong). main 아님.
- **백엔드**: `backend/.venv/bin/python`(3.13). 테스트 `cd backend && .venv/bin/python -m pytest Nutrition-backend/tests/unit -q`. lemon_ai_agent는 `backend/ai_agent_chat/src` PYTHONPATH 필요(conftest가 처리). alembic head = 0043.
- **모바일**: Flutter 3.41.9. `cd mobile && flutter analyze` + `flutter test`. 패키지명 `lemon_aid_mobile`.
- **A100**: `ssh -i ~/.ssh/lemon_a100_ed25519 -p 8875 lemon-aid@155.230.153.222`(Windows, PowerShell `-ExecutionPolicy Bypass` 필수, cmd 인용 문제 시 EncodedCommand). b32 체크포인트 보존: `G:\lemon-aid\paddleocr_rec_work\PaddleOCR\output\supplement_rec_..._b32_..._20260611\best_accuracy.pdparams`.
- **자동 메모리**: `~/.claude/projects/.../memory/`(MEMORY.md + ai-agent-chatbot-import-state.md)에 누적 상태가 있다 — 세션 시작 시 자동 로드됨.

## 2. 적용 중인 규칙 (반드시 준수)

- **수치·결과 추정 금지** — 확인값(로그/출력)만 보고.
- **private image / raw OCR text / provider payload / secret / owner hash** 결과물·커밋 금지. 집계·해시·카운트만.
- **원격(A100 155.230.153.222) 실행·사적 데이터 전송은 사용자 승인 후**.
- **원본 dataset(`rec_dataset\v2`) 불가침**(sanitized 사본만).
- **사용자 요청 없이 commit/push 금지**. 커밋 시 Conventional Commits + 본문에 "왜" + `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- **framework 파라미터 변경 시 공식 문서 확인 + URL 주석**(예: PaddleOCR det thresh, Supabase JWT).
- **PR#4 보호 — 덮어쓰기/되돌리기 금지**: alembic 전체(특히 0023a/b/c·0041), `ollama.py`, `ai_agent.py` LLM 가드, `app_health_analysis.py` commit 패턴. 필요 시 **신규 마이그레이션(0044+)만**.
- **의료법**: 금칙어(진단/처방/치료/효능) 금지 + 신뢰도 % 미노출 + 권고 화면 면책(`MedicalDisclaimer`) 필수.
- **모바일 UI**: `design_tokens_v2`만(legacy `LemonColors`/`utils/tokens.dart` 금지). 한국어 **해요체**. 시니어 최소치(본문 15px+ `AppText.body`, 버튼 52px+ `AppPrimaryButton`(기본 54), 터치 48px+).
- **백엔드 공백 필드 날조 금지** — 없는 엔드포인트/요청필드 만들지 말 것. 로컬 전용은 LocalPrefs로, 옵션 라벨은 권위 출처(예 design system `onboarding.jsx`) 사용.
- **`.mcp.json` 미커밋 작업트리 편집은 커밋하지 말 것** — `:-weipsloxntjzcqjvzjax` 기본값이 박혀 `test_supabase_local_config`를 깨뜨림(이건 사용자 편집, 손대지 않음).
- **TDD + 별도 리뷰 레인**: 작성과 리뷰를 분리, 같은 컨텍스트에서 self-approve 금지(보안/품질은 reviewer/verifier 또는 적대적 워크플로우). 완료 주장 전 테스트 통과 + 증거 확보.
- **무관 실패 2건은 기존 상태**(내 변경 무관): `test_supabase_local_config`(.mcp.json 미커밋 편집), 서브셋 실행 시 커버리지 게이트 77%(통합 미실행 아티팩트).

## 3. 이번 세션 완료 (전부 양 리모트 푸시)

| 커밋 | 내용 |
|---|---|
| `892bceaa` | PaddleOCR DB 검출 임계 3종 런타임 배선 |
| `56022a1f` | 전용 섹션 검출기 배선(vision_classifier 슬롯 재사용 — 별도 표면 추가 안 함) |
| `020a35d4` | b32 holdout 평가(macro 0.6049/micro 0.614) + 배선 결정 기록 |
| `d6072dd8` | 섹션 검출기 학습 게이트 런북 |
| `56259838` | det thresh 스윕 §7(승자 box_thresh=0.4, within-sweep +0.0098) |
| `bc8bb515` | .env.example `LOCAL_OCR_TEXT_DET_BOX_THRESH=0.4` 권고 |
| `17f59eb0` | Supabase Auth JWT 검증(ADR 39) — `src/security/supabase_auth.py` + 회귀 18 |
| `3f4ac3ab` | RLS Stage-1 seam `get_rls_context_session` + 롤아웃 문서 |
| `f22e3d42` | 모바일 1단계 한국어 동의 게이트 시트 |
| `f1a24d48` | 모바일 2단계 프로필/신체 위저드 → /health/profile-snapshots |
| `f67f92cd` | 모바일 2단계 목적/관심사 로컬(LocalPrefs) |
| `16e25ee9` | 모바일 2단계 온보딩 3-slide + 첫 실행 라우팅 |

## 4. 잔여 작업 (우선순위·게이트 명시)

1. **모바일 Auth 3단계** — `supabase_flutter` 소셜(카카오/Apple/Google)+이메일 로그인/가입/이메일 인증(send/verify)/비밀번호 복구/계정 충돌(409). **게이트: 라이브 Supabase 프로젝트 URL/anon key + 소셜 프로바이더 키(팀 액션)**. 시안: 가이드 01 §3단계(frames 151:2/198:10/264-266/949:24-88). `token_session.dart`의 dev 토큰 페이스트를 Supabase SDK 토큰 소스로 교체(다운스트림 재사용). 백엔드는 검증만(신규 /auth/* 없음, ADR 39).
2. **Supabase Auth 백엔드 활성화(ops/config)** — Supabase 프로젝트를 **비대칭 서명 키(RS256/ES256)로 전환**(기본 HS256은 prod 거부) + `AUTH_MODE=jwt` + `SUPABASE_PROJECT_REF`로 JWT_*(.env Supabase 프로파일 참조) + docs/17 §9 게이트 #2 승인.
3. **RLS Stage-2 활성화(인프라 게이트)** — `lemon_app` 역할 비번 설정(아웃오브밴드) → **격리 통합 테스트**(live PG + lemon_app 역할로 교차 사용자 격리 검증, 현재 미구현) → `DATABASE_URL`을 lemon_app로 → 0023c FORCE 적용 → 라우트 점진 채택(`get_async_session`→`get_rls_context_session`). 권위: `outputs/todo-list/2026-06-13/2026-06-13-rls-activation-rollout.md`.
4. **섹션 검출기 학습(운영자+A100 게이트)** — `yolo_section_annotation` **205건 운영자 bbox 주석(사적 이미지, 내가 못 함)** + 라벨 보강(plan 최소치) → materialize/validate/gate → **재학습(yolov8s 먼저, 300ep no-early 금지)** → promotion 게이트(mAP50≥0.70 등) → `VISION_CLASSIFIER_MODEL` 지정 + 게이트 #2. 권위: `outputs/todo-list/2026-06-13/2026-06-13-section-detector-training-gate-runbook.md`. (2026-06-09 모델은 mAP50 0.235·ROI-first 0.5119<full 0.6002라 잠정 배선 비추.)
5. **det thresh box_thresh=0.4 채택 결정**(팀) — 코드 기본값 하드변경 대신 .env 권고로 둠.
6. **Health Connect**(Android, P1-6) · **알림 센터**(가이드 08 제외분).

## 5. 관찰·잔여 정리 후보 (긴급 아님)

- 챗 액션 칩 raw snake_case · 결정론 코칭 영어 문구 — 백엔드/문구 검토 후보.
- dev DB에 테스트로 등록한 영양제(분류없음·비타민B 컴플렉스·ZMA 등) 잔존 — 필요 시 정리.
- `set_request_rls_context` 채택 라우트는 요청 트랜잭션 의존(자체 begin/commit 금지) — Stage-2 라우트 교체 시 주의.
- 모바일 온보딩 추가 시 `_pumpReadyShell` 같은 full-app 하네스는 `onboardingSeen` 시드 필요(안 그러면 스플래시가 /onboarding로 빠짐).

---

## 다음 세션 시작 프롬프트(복붙용)

> Lemon-Aid 작업을 이어서 진행해줘. 환경·규칙·잔여 작업은 `outputs/todo-list/2026-06-14/2026-06-14-next-session-handoff.md`에 있다. 브랜치 feat/ai-agent-chat-import, 커밋·푸시는 양 리모트(origin+personal). 규칙(수치 추정 금지·사적이미지/secret 커밋 금지·A100 원격 승인 후·PR#4 alembic 불가침·의료 금칙어·design_tokens_v2·백엔드 공백 날조 금지·미커밋 .mcp.json 커밋 금지·TDD+별도 리뷰) 준수. 우선순위는 [여기에 1~6 중 택일 지시]. 사적 이미지/라이브 Supabase/소셜 키/A100는 게이트이니 막히면 보고하고 가능한 코드/문서 작업부터.
