# Local ↔ Production Sync Gaps — 분석 보고서

> **작성일**: 2026-04-24 (Phase A-2 / Phase B-1·B-2 완료 시점 업데이트)
> **분석 근거**: Firebase Hosting REST API로 다운로드한 production bundle
> - `assets_index-BGK9Zs9J.js` (1.13MB minified) — 번들 grep 으로 `sg`/`cg`/`lg`/`ug`/`BS`/`dg` 시그니처 + appointments 이중 경로 schema 복원
> - `e2e-hospital-isolation.html`, `e2e-tab-session.html`, `e2e-wait-queue.html` (기능 스펙 노출됨)
> - `e2e-visit-plan.html` (local과 동일)

## 0-A. Phase B-1 & B-2 진행 요약 (완료 2026-04-24)

Local에 prod 기능 이식 완료 — E2E HTML · useFcmToken · HospitalHomePage · WaitQueueWidget ·
StaffQueuePage · AppointmentsTab · ChatbotWidget · MoreTab 고령자 모드. 117 vitest pass.

**Phase B-3 남은 TODO (주석만 남기고 실구현은 별도 sprint)**:
- **item 9**: VisitPlanPage 흰 화면 — `src/pages/account/VisitPlanPage.tsx:1` 주석 참고
- ~~**item 10**: Hospital slug routing 전체 개편~~ → ✅ **2026-04-26 완료**
  설계: `docs/B-3_ITEM10_HOSPITAL_SLUG_ROUTING.md`
  6 커밋 (`94077e5` → `5e5f6cc` + 본 docs 커밋)
  HospitalShell + HospitalContext + LegacyHospitalRedirect + nested `/h/:slug/{patient,staff}/...`
  hosting 재배포는 §7 체크리스트로 별도 승인 단계.

**주의**: e2e-hospital-isolation.html 시나리오 #7 이 platformAdmin 로 실행될 때
`hospitals/demo/profile/themeColor` 를 `#deadbe` 로 덮어쓰는 부작용이 있음.
증상: 전체 환자 UI primary 색상이 연분홍으로 렌더. 발견 시 RTDB PUT 으로
`#004e9f` 재복구 필요 (본 세션에서 2회 발생 → 2회 복구).

---

## 0. 결론 요약

**Local source는 P1 마무리 수준**, **Production은 P3 C1-C5 착수 수준**. 격차 매우 큼.
- 🚨 **내가 삭제한 orphan function 2개는 실제 P3 운영 중 기능이었음** (복구 불가, 재작성 필요)
- 🚨 **Commit 8 rules가 production schema와 불일치** — 교차 병원 wait_queue 읽기 취약
- Local source 복구는 single-sprint 범위 아님 — 여러 스프린트로 분할 필요

## 1. 🚨 Critical — 이미 발생한 incident (제가 일으킴)

### 1.1 `triageSymptoms` function 삭제 (asia-northeast3)
- **용도**: AI 증상 triage (F19) — 증상 텍스트 → 진료과 3개 추천 + 신뢰도 + "진단 아님" disclaimer
- **증거**: `e2e-wait-queue.html` 시나리오 E가 이 함수의 동작을 구체 기술
- **데이터**: `/triage_usage/{uid}/{epochHour}=<count>` + `/triage_audit` (RTDB에 남아있음)
- **상태**: 🔴 현재 production에서 호출 불가. 사용자는 "AI 진료과 추천" 기능이 작동 안 함을 경험할 것
- **복구**: source 없음 → plusultra_v2 §3.6 + e2e-wait-queue.html §E 스펙 기반 재작성 필요 (~3-5일)

### 1.2 `onQueueCall` function 삭제 (us-central1)
- **용도**: 의료진 "다음 환자 호출" 트리거 → 환자 FCM push 발송 (F1)
- **증거**: `e2e-wait-queue.html` 시나리오 B가 이 함수의 동작을 상세 기술
- **연관 스키마**: `/user_fcm_tokens/{uid}/*` (FCM 토큰 저장)
- **상태**: 🔴 의료진 call next 시 환자 푸시 알림 미발송. 대기열 UI는 이상 없지만 push가 사라짐
- **복구**: source 없음 → plusultra_v2 §3.1 + e2e-wait-queue.html §B + 데이터 트리거 설계 재작성 필요 (~2일)

### 1.3 RTDB Rules v2 — hospitals 하위 wait_queue 노출
- **Production 기대**: `/hospitals/demo/wait_queue/내과/<date>.json` cross-hospital read → 401 (e2e-hospital-isolation 시나리오 D, e2e-wait-queue 시나리오 D)
- **Commit 8.1 배포 현실**: `"hospitals": { ".read": true }` → 전체 readable
- **영향**: smch hospital 계정이 demo hospital의 wait_queue·visit_plans 모두 조회 가능 (tenant isolation 깨짐)
- **복구**: rules 즉시 tightening 필요 (Phase E의 T1-1과 연계)

## 2. Schema 불일치

| 경로 | Local rules/code 가정 | Production 실제 |
|---|---|---|
| visit_plans | `/visit_plans/{uid}` (root, 레거시) | `/hospitals/{hid}/visit_plans/{uid}` 신규 + `/visit_plans/{uid}` 레거시 **병행** |
| wait_queue | `/wait_queue/{hid}/{dept}/{date}/...` | `/hospitals/{hid}/wait_queue/{dept}/{date}/...` (hospitals 하위) |
| appointments | 미존재 | `/hospitals/{hid}/appointments_by_patient/{uid}` + `/hospitals/{hid}/appointments/{id}` |
| triage | `/triage_usage/{uid}` (orphan) | `/triage_usage/{uid}/{hour}` + `/triage_audit` |
| FCM tokens | 없음 | `/user_fcm_tokens/{uid}/*` |
| profile field | `hospitalId` | `primaryHospitalId` 실존 (buildClaimsFromProfile fallback 은 이미 대응) |

## 3. 페이지·라우트 구조

### Production의 Route 체계
```
/h/{slug}/patient/home?tab=home|appointments|inpatient|checkup|guide|more
/h/{slug}/staff/queue
/h/{slug}/staff/...
```

### Local의 Route 체계 (App.tsx)
```
/patient, /patient/:sessionId
/staff
/admin, /admin/users, /admin/hospitals(new), /admin/...
```

→ **완전히 다른 라우팅 전략**. Production은 hospital slug 기반 multi-tenant 라우팅, Local은 role 기반 flat.

## 4. 신규 컴포넌트 · 기능 (Local 미존재)

### P2 (탭 셸 + 고령자 모드 인프라)
- **HospitalHomePage** — 6탭 (홈/외래/입원/건강검진/안내/더보기)
  - Mount-all + `hidden` 전략으로 탭 전환 중 state 보존
  - URL `?tab=*` 동기화 + 브라우저 뒤로가기 대응
- **AppointmentsTab** — `/hospitals/{hid}/appointments` 목록 + `+ 새 예약` 폼
- **GuideTab** — 지도 렌더 + POI 클릭 + zoom/pan 상태 유지
- **MoreTab** — 고령자 모드 토글 (RTDB persist)
- **고령자 모드** — CSS variable + `.ui-senior` root class 동적 전환 (플러스울트라 P2 §2.3)

### P3 (대기열 + AI Triage + FCM)
- **WaitQueueWidget** (home) — 순번 · 대기 중 · 호출됨 강조 · 진료 중
- **StaffQueuePage** (`/h/{hid}/staff/queue`)
  - 부서·날짜 자동 선택
  - "다음 환자 호출" / "진료 시작" / "완료" 버튼
  - 대기열 카드 그리드
- **TriageWidget** (home) — 증상 입력 → 진료과 추천 3개 + 신뢰도 + disclaimer
- **useFcmToken** hook — HomeTab 진입 시 알림 권한 요청 + `/user_fcm_tokens/{uid}` 저장

### Admin (Production에 있을 가능성 높음)
- **AdminHospitalDetailPage**: 내가 local에 새로 만든 버전 ≠ production 원본 (정확도 불명)
- **AdminHospitalsPage**: 내가 local에 새로 만든 버전 ≠ production 원본
- **+ 신규 병원 flow**: create Cloud Function + UI — local 없음

### Firebase Hosting auto-config
Production 모든 E2E가 `/__/firebase/init.json`에서 config를 fetch. Local dev에선 `.env.local` 기반. **Hosting 전용 기능이라 local에선 테스트 불가.**

## 5. 우선순위 복구 계획

### 🔴 Tier 0 (즉시)
| # | 작업 | 상태 |
|---|---|---|
| 1 | **Rules tightening** — `hospitals/{hid}/wait_queue`·`visit_plans` 에 명시적 `.read` 추가해 cross-tenant 차단 | ✅ T1-1 / T1-2 (2026-04-25) |
| 2 | **`onQueueCall` 함수 재작성** — e2e-wait-queue.html §B 스펙 기반 | ✅ F5b `7bf536c` (dispatcher 통합 형태로 재작성) |
| 3 | **`triageSymptoms` 함수 재작성** — AI 진료과 추천 복구 | ⏳ 별도 sprint (시나리오 E 의 Local 부재) |

### 🟠 Tier 1
| # | 작업 | 상태 |
|---|---|---|
| 4 | **P2 탭 셸 재구현** — HospitalHomePage + 6탭 + 고령자 모드 토글 | ✅ T0-1 B-1/B-2 (2026-04-24) |
| 5 | **P3 WaitQueueWidget + StaffQueuePage** | ✅ T0-1 B-2 + F1 (2026-04-26) |
| 6 | **P3 Appointments CRUD (RTDB + UI)** | ✅ T0-1 B-2 (2026-04-24) |
| 7 | **hospital-slug route 체계 전환** (`/h/{slug}/...`) | ✅ B-3.10 (2026-04-26) |
| 8 | **P3 F1 wait queue UI prod-parity 통합** — features 가드 + slug 일원화 + StaffSubNav + empty CTA + e2e 시나리오 A-D smoke | ✅ F1 (2026-04-26) — 설계: `docs/F1_WAIT_QUEUE_UI_INTEGRATION.md`, 7 커밋 (`3174225` → `b36936b` + 본 docs) |

### 🟡 Tier 2 (리서치 필요)
- Production이 정확히 어떤 auth flow·role gate 쓰는지 분석 (minified 해독 난이도 ↑)
- 역엔지니어링 어려운 부분은 본 문서에 TODO로 남기고, production을 source-of-truth로 인정

## 6. 투명성 — 내가 놓친 추정

Commit 8 rules design 시 나는 다음을 **몰랐음**:
1. `/hospitals/{hid}/wait_queue/*` 경로가 production에 실존
2. `/hospitals/{hid}/visit_plans/{uid}` 네스티드 path 실존
3. `/triage_*` 경로 실존
4. `/user_fcm_tokens/*` 경로 실존
5. `triageSymptoms`·`onQueueCall`이 실제 기능이었음 (orphan이라 판단하고 삭제)
6. production route가 `/h/{slug}/...` 체계

**교훈**: 외부 저장소(git 미추적) 상태에서 production과 local 격차를 가정 없이 신뢰한 건 실책. T0-2 deploy checklist의 §1.1 "Local/Production 동기화 검사"가 이번 사건의 결정적 예방책.

## 7. 즉시 조치 권장

사용자에게 아래 2가지를 즉시 공지 필요:
1. **AI 증상 triage + 대기열 FCM push 현재 작동 안 함** (내가 삭제) — 2-5일 내 복구 예정
2. **cross-tenant wait_queue 노출 가능성** — rules tightening 전까지 demo 단일 테넌트라 실질 영향은 제한적이지만 빠르게 닫아야 함

사용자 의사 확인 후:
- (A) 즉시 rules tightening + 함수 2개 재작성 sprint 착수
- (B) 본 gap 문서만 보존하고 기존 기술 부채 정리(T1-2, T1-3, T1-4) 먼저 진행
- (C) 다른 우선순위 (예: Hosting 롤백 상태 유지하고 local source 고립 관리)
