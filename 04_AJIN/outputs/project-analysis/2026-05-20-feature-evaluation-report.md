# AJIN AI Assistant 기능별 종합 분석 보고서

- 작성 시각: 2026-05-20 16:11 KST
- 기준 worktree: 현재 dirty worktree 그대로 평가
- 기준 환경: Supabase release env는 `.env.supabase.local` 주입, secret 값 미기록
- 평가 범위: Feature A-F, Supabase/Firebase cutover gate, route smoke, build/docs/security gate
- 점수 성격: release readiness 정성 점수. 성능 벤치마크나 운영 KPI가 아니다.

## 1. Executive Summary

현재 프로젝트는 A/B/C/E/F 기능의 핵심 구현과 자동 release gate가 상당 부분 갖춰져 있다. Supabase 전환 gate와 frontend build, OpenAPI docs, route smoke는 통과했다. 다만 Firebase 완전 제거와 운영 release 후보 판단에서는 Feature D 법규 모니터링이 명확한 blocker다. 공식 출처 live probe와 crawler citation/source policy가 strict gate에서 실패했다.

전체 판정은 **부분 release 가능, Firebase 완전 제거는 Feature D blocker 해소 전 보류**다. Feature A/B/C/E/F는 대부분 `warn` 상태이며, 이는 기능 미구현보다는 운영 signoff, demo/default 계정 제거, 실제 현장 PLC bridge 연결, synthetic/demo index 정리 같은 release 전 정리 항목이다.

| 영역 | 구현 상태 | 최신 gate | 정성 점수 | 판정 |
|---|---:|---:|---:|---|
| Feature A 검색·조직도 | 구현 완료에 가까움 | warn | 85/100 | 부분 완료 |
| Feature B 문서 작성 | 구현 완료에 가까움 | warn | 88/100 | 부분 완료 |
| Feature C AI 업무 도우미 | 구현 완료에 가까움 | warn | 86/100 | 부분 완료 |
| Feature D 법규 모니터링 | 핵심 구현됨, release blocker 존재 | fail | 60/100 | 차단 |
| Feature E 인사·관리 | 운영 hardening 진행됨 | warn | 82/100 | 운영 검증 필요 |
| Feature F 설비·SPC | 구현 완료에 가까움 | warn | 88/100 | 부분 완료 |
| 공통 platform/Supabase | cutover gate 통과 | pass/skip 일부 | 90/100 | 운영 검증 필요 |

## 2. 최신 검증 결과

| Gate | 결과 | 근거 |
|---|---:|---|
| `make openapi-docs-check` | pass | OpenAPI docs are current |
| `npm run build` | pass | Vite production build 성공 |
| `make feature-a-consistency-check` | warn | Supabase env 주입 기준 pass=5 warn=1 fail=0 |
| `make feature-b-release-check` | warn | pass=3 warn=1 fail=0 |
| `make feature-c-release-check` | warn | pass=4 warn=2 fail=0 |
| `make feature-d-release-check` | fail | pass=3 fail=2 |
| `make feature-e-release-check` | warn | cookie/CSRF pass, default/demo 계정 warn |
| `make feature-f-release-check` | warn | pass=4 warn=1 fail=0 |
| `make release-security-check` | pass | Supabase env 주입 기준 pass=2 fail=0 skip=2 |
| `make supabase-release-check` | pass | Supabase verifier 22 pass, dry-run up-to-date, advisor no issues |
| 최종 route smoke | pass | 14/14 route pass |

주의: Feature A는 Supabase env 미주입 상태에서 Postgres mirror 검사가 `RuntimeError`로 실패했다. release 기준에서는 `.env.supabase.local` 주입 후 재실행한 결과를 최종 판정으로 사용한다.

## 3. 기능별 분석 및 평가

### Feature A - 검색·조직도

| 항목 | 내용 |
|---|---|
| 목적 | 직원, 문서, 도면, 조직 정보를 빠르게 찾고 command palette/검색 API로 업무 진입 시간을 줄인다. |
| Endpoint | `search=9`, `employee=5`, `directory=1` |
| 구현된 기능 | hybrid search, employee DB, directory tree, command palette, drawing/vision query 계열, SQLite FTS5/Chroma/Postgres mirror 검증 스크립트 |
| 검증 | `feature-a-consistency-check`: pass=5 warn=1 fail=0 |
| 판정 | 부분 완료 |

평가:
- real active 직원 4명은 SQLite, FTS5, Postgres mirror, 문서 Chroma/BM25에서 release 기준을 충족한다.
- Chroma employee collection에 non-real-active profile 329건이 남아 있다. 현재 정책상 blocker는 아니지만 운영 검색 품질과 데이터 lineage 관점에서는 정리가 필요하다.
- Supabase env 없이 gate를 실행하면 Postgres mirror 검사에 실패한다. release owner는 Feature A gate를 Supabase env 주입 상태로 실행해야 한다.

다음 작업:
- Chroma employee index에서 synthetic/demo profile 분리 또는 data_class filter를 runtime 검색 경로에 명확히 적용.
- Feature A gate 실행 문서에 `.env.supabase.local` 주입 조건을 추가.
- Postgres primary 전환 후 SQLite/Chroma/Postgres sync source-of-truth를 재정의.

### Feature B - 문서 작성

| 항목 | 내용 |
|---|---|
| 목적 | 8D, ECN, 메일, 보고서 초안과 HWP/HWPX/DOCX/PDF/export 자동화로 문서 작성 비용을 줄인다. |
| Endpoint | `draft=27` |
| 구현된 기능 | LLM streaming, template rendering, quality score, versioning, mail send guard, storage attachment ownership, HWP/HWPX/DOCX/PDF export |
| 검증 | `feature-b-release-check`: pass=3 warn=1 fail=0 |
| 판정 | 부분 완료 |

평가:
- Storage ownership smoke는 owner/admin allow, other-user deny, missing object deny를 통과했다.
- Mail guard는 승인 전 발송 차단, 외부 수신자 ack, self-approval 차단, rate-limit 차단이 통과했다.
- 우선순위 template 8종은 strict sample context로 render된다.
- 남은 warn은 8D/ECN/OEM mail/weekly report의 business-owner signoff 미완료다.

다음 작업:
- 실제 업무 owner가 template 문구와 export 결과물을 검수하고 signoff artifact를 남긴다.
- mock mail mode에서 real adapter 전환 전 SMTP credential/승인 흐름을 staging에서 별도 검증.
- 첨부/다운로드 권한은 현재 gate를 유지하고, Cloud Run tag smoke에도 다운로드 동선을 주기적으로 포함.

### Feature C - AI 업무 도우미

| 항목 | 내용 |
|---|---|
| 목적 | 온보딩, SOP, 퀴즈, 업무 시나리오, 비전/문서 입력을 통해 부서별 업무 지원을 제공한다. |
| Endpoint | `onboarding=31`, `scenarios=5`, `feature-flags=3` |
| 구현된 기능 | chat SSE, quick questions, SOP/quiz, gamification, scenarios/favorites, vision/document extractors, LLM fallback/circuit/metrics, department RBAC, feature flags |
| 검증 | `feature-c-release-check`: pass=4 warn=2 fail=0 |
| 판정 | 부분 완료 |

평가:
- release 기본 경로는 `LLM_ROUTER_PRIMARY=ollama`이며 paid/external LLM primary와 compare-mode doubling은 차단되어 있다.
- LLM fallback, circuit breaker, metrics, generation route fail-closed posture가 통과했다.
- Feature C flag rollout과 부서 RBAC baseline은 통과했다.
- 남은 warn은 `기술연구소` quick question coverage와 부서별 콘텐츠 business-owner signoff 미완료다.

다음 작업:
- 기술연구소 quick questions를 보강하거나 의도적으로 제외했다는 signoff를 남긴다.
- SOP/quiz/collaboration scenario의 현업 검수 결과를 `--content-signoff` 입력으로 연결.
- Gemini key가 존재하더라도 release primary가 Ollama로 유지되는지 CI/env에서 재검증.

### Feature D - 법규 모니터링

| 항목 | 내용 |
|---|---|
| 목적 | 법규 변경 감지, RAG, 알림, 승인/학습 흐름, Slack/SMS/mail adapter 기반 notification 운영을 제공한다. |
| Endpoint | `compliance=19`, `notifications=6` |
| 구현된 기능 | D1 change feed/alarms/crawlers/scheduler/digest/notification outbox, D2-D5 feature flag gating, adapter posture, staggered Celery schedule |
| 검증 | `feature-d-release-check`: pass=3 fail=2 |
| 판정 | 차단 |

평가:
- Endpoint surface, D2-D5 default off posture, notification scheduler/outbox는 통과했다.
- official source live probe가 실패했다. 실패 항목은 APQP HTTP 400, MSDS HTTP 403, OEM quality HTTP 400, EV battery HTTP 403, `LAW_GO_KR_OC` 미설정, `CUSTOMS_API_KEY` 미설정이다.
- citation/source policy도 실패했다. `source_type` 누락, citation URL 누락, curated/live reason 누락 계열이 남아 있다.
- 네트워크 sandbox 문제는 재실행으로 분리했다. 네트워크 허용 상태에서도 동일하게 strict blocker가 남았다.

다음 작업:
- `LAW_GO_KR_OC`, `CUSTOMS_API_KEY`를 release secret으로 준비하고 secret-safe로 verifier에 주입.
- HTTP 400/403 source는 요청 방식, User-Agent, endpoint URL, API guide 기준을 재검토.
- `data/crawled/*.json` 산출물에 `source_type`, `source`, `crawled_at`, `reference_url/url`, failure reason을 표준화.
- Feature D가 fail인 동안 Firebase 완전 제거 또는 Supabase cutover 완료 후보 판정을 보류.

### Feature E - 인사·관리

| 항목 | 내용 |
|---|---|
| 목적 | 사용자, 권한, 보안, IdP, 시스템 관리를 운영 인증 기준에 맞게 제공한다. |
| Endpoint | `auth=12`, `idp=5`, `admin=48`, `admin-scenarios=9` |
| 구현된 기능 | HttpOnly cookie auth, CSRF cookie/header, refresh rotation, logout, bearer 예외 gate, RBAC, TOTP, LDAP/OIDC/SAML stub, audit/security monitor, permissions workflow |
| 검증 | `feature-e-release-check`: warn |
| 판정 | 운영 검증 필요 |

평가:
- 74-operation endpoint surface, cookie/CSRF wiring, frontend token posture가 통과했다.
- local 환경은 production이 아니므로 `AJIN_JWT_SECRET`, `SESSION_STORE=redis`, `REDIS_URL` 검사는 advisory로 처리됐다.
- local auth.db에 active default/demo 계정 `HR-0001`, `QA-0001`, `SYS-0001`이 남아 있어 warn이다. production에서는 blocker로 봐야 한다.

다음 작업:
- production env에서 `AJIN_JWT_SECRET`, Redis session store, Secret Manager mapping을 실제 service JSON으로 검증.
- 기본/demo 계정 비활성화 gate를 배포 전 필수로 실행.
- bearer auth는 smoke/admin automation 예외로만 유지하고 브라우저 기본 경로는 cookie-only로 고정.

### Feature F - 설비·SPC

| 항목 | 내용 |
|---|---|
| 목적 | 현장 설비, SPC, 금형, PLC ingest, 점검, live alarm을 통합해 공정 이상 감지와 현장 대응을 지원한다. |
| Endpoint | `equipment=19`, `live-alarms=2` |
| 구현된 기능 | PWA field mode, inspection upload/submit/offline queue, SPC/Nelson rules, mold lifecycle, PLC Redis stream ingest, live alarm persistence, department+level RBAC |
| 검증 | `feature-f-release-check`: pass=4 warn=1 fail=0 |
| 판정 | 부분 완료 |

평가:
- PLC stream payload 계약, simulator batch path, `live_events.insert_alarm(domain="equipment")` persistence가 통과했다.
- `/equipment/field`는 직접 제출, offline enqueue, pending count, flush wiring이 통과했다.
- Feature F endpoint는 생산/품질/자동화/금형/안전 부서 + role level 기준 RBAC로 강화됐다.
- 실제 OPC-UA/field PLC bridge 연결은 기본 release gate에서 warn이다. `--require-live-plc` 환경에서는 blocker로 승격된다.

다음 작업:
- 현장 Redis/PLC adapter 환경에서 `--require-live-plc`로 active lane, last message age, alarm persistence를 검증.
- offline queue는 submit 저장/재전송 범위이므로 full service worker offline app shell은 별도 backlog로 유지.
- 현장 부서/role matrix를 운영 계정으로 재확인.

## 4. 공통 Release Platform 평가

### Supabase/Firebase Cutover

- `make supabase-release-check`는 `.env.supabase.local` 주입 상태에서 통과했다.
- Supabase verifier는 22 pass, 0 warn, 0 fail이다.
- `supabase db push --dry-run --linked`는 remote database up-to-date를 반환했다.
- `supabase db advisors --linked --type security --level warn`은 `No issues found`를 반환했다.
- Firebase writes/read fallback은 Supabase verifier 기준 false로 확인됐다.

판정: Supabase cutover gate 자체는 통과. 단, Feature D blocker가 남아 있으므로 제품 release 후보 판정은 보류.

### 운영 보안 Guard

- `make release-security-check`는 Supabase env 주입 기준 통과했다.
- Frontend artifact 476개에서 backend-only Supabase secret marker 노출은 발견되지 않았다.
- Supabase RLS/Data API guard는 통과했다.
- Cloud Run secret mapping과 admin health secret-safe 검사는 service JSON/admin health JSON이 없어서 skip됐다.
- 기존 final route smoke에서는 admin/system 화면과 주요 routes가 pass였지만, release-security verifier의 두 skip은 최신 JSON 증적이 없다는 의미다.

판정: secret exposure/RLS는 pass, Cloud Run runtime mapping과 admin health는 최신 입력 artifact를 넣어 재검증 필요.

### Browser Route Smoke

- 기존 최종 smoke 기준 14/14 routes pass.
- `/login`, `/`, `/search`, `/draft`, `/chat`, `/onboarding`, `/compliance`, `/equipment`, `/management?cat=system`, `/equipment/field` 모두 5xx/blank/console error 없이 통과.
- `/compliance/search`, `/compliance/glossary`는 D2 disabled 기준 `/compliance`로 redirect되어 pass.
- `/admin`, `/hr`는 `/management` alias redirect로 pass.

판정: 화면 routing smoke는 release owner 기준 pass.

## 5. 우선순위 권고

### 즉시 Blocker

1. Feature D official source live probe 실패 해소.
2. Feature D crawler output citation/source policy 표준화.
3. production 배포 후보에서 default/demo 계정 활성 여부를 blocker로 승격하고 제거.

### Release 전 Warning

1. Feature A Chroma non-real-active profile 정리 또는 runtime filter 확정.
2. Feature B 문서 template business-owner signoff.
3. Feature C quick question coverage와 SOP/quiz/scenario signoff.
4. Feature F 실제 OPC-UA bridge 현장 검수.
5. Cloud Run service JSON과 admin health JSON을 release-security verifier에 입력해 skip 2개 해소.

### 운영 Backlog

1. Feature A Postgres primary 전환 후 search index source-of-truth 재정의.
2. Feature B real SMTP adapter staging runbook과 감사 로그 운영 점검.
3. Feature C paid LLM 사용 시 cost budget, compare-mode 승인 절차, 장애 fallback drill.
4. Feature D D2-D5 기능을 단계별 allow run으로 확대 검증.
5. Feature F full offline/service worker cache와 실제 설비 adapter 관측 dashboard.

## 6. 결론

AJIN 프로젝트는 기능 A-F 대부분이 “프로토타입” 수준을 넘어 release gate와 운영 보안 기준을 갖춘 상태다. Supabase 전환과 Firebase fallback off 기준은 통과했고, 최종 route smoke도 통과했다. 그러나 Feature D는 현재 strict release blocker이며, 공식 출처 live 검증과 citation/source policy를 해결하기 전에는 Firebase 완전 제거 또는 production cutover 완료 후보로 보기 어렵다.

다음 release owner 작업은 Feature D blocker 해소, default/demo 계정 production 제거, Cloud Run/admin health 최신 JSON을 포함한 security verifier 재실행이다. 이 세 항목이 닫히면 A/B/C/E/F의 warn은 운영 signoff와 현장 검수 성격으로 관리 가능하다.

## 7. 근거 Artifact

- `outputs/feature-a-consistency/2026-05-20-feature-a-consistency.md`
- `outputs/feature-b-verification/2026-05-20-feature-b-release.md`
- `outputs/feature-c-verification/2026-05-20-feature-c-release.md`
- `outputs/feature-d-verification/2026-05-20-feature-d-release.md`
- `outputs/feature-e-verification/2026-05-20-feature-e-release.md`
- `outputs/feature-f-verification/2026-05-20-feature-f-release.md`
- `outputs/supabase-verification/2026-05-20-release-security-check.md`
- `outputs/supabase-verification/2026-05-20-final-route-smoke.md`
- `docs/openapi.json`
- `docs/API.md`
