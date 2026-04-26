# Phase H — 환자 Visit 정보 (외래/입원 admission) 도입

> **작성일**: 2026-04-26
> **목표**: 환자 정보 카드의 하드코딩 placeholder 를 RTDB-backed 동적 visit 정보로 교체.
> **범위**: 데이터 모델 + RTDB rules + service + hook + QRDisplay + admin 등록 페이지.
> **선행**: 본 sprint 직전 동선 전송 PERMISSION_DENIED + redirect 회복 (commit `d16675c`).

---

## 0. 컨텍스트

| 항목 | 현재 | 목표 |
|------|------|------|
| 환자 정보 카드 (QRDisplay) | 하드코딩 "MediWay 데모 환자 / Zone A-1" | 로그인 환자의 실제 visit 정보 동적 표시 |
| Visit type 구분 | 없음 | 외래/입원/검진/응급 4종 |
| 위치 정보 (zone/병동) | 없음 | RTDB 에 zone/ward/room/bed 저장 |
| Staff/admin 의 visit 등록 | 없음 | admin 페이지에서 visit 생성/관리 |

> **용어**: "visit" = 환자의 1회 방문 record. 기존 `/visit_plans` (waypoints 진료 동선) 와 별개 개념.
> RTDB path: `/hospitals/{hid}/visits/{visitId}` 신설 (기존 `visit_plans` 와 충돌 회피).

## 1. 현재 상태 + 갭 분석

| Layer | 현재 | 갭 |
|-------|------|-----|
| 데이터 | RTDB `/users/{uid}` 에 displayName + hospitalId 만 | visit type, status, location 없음 |
| RTDB rules | visits path 부재 | 신규 rules 필요 |
| Types | `Visit` type 없음 (visit-plan, session 만 있음) | 신규 type 정의 |
| Service | visit CRUD/subscribe 없음 | 신규 service 모듈 |
| Hook | `useActiveVisit` 없음 | 신규 hook |
| UI | QRDisplay 환자 정보 카드 정적 | 동적 바인딩 |
| Admin | visit 등록 UI 없음 | 신규 페이지 또는 dialog |

## 2. 데이터 모델 (`src/types/visit.ts`)

```ts
export type VisitType = 'outpatient' | 'inpatient' | 'checkup' | 'emergency';

export type VisitStatus =
  | 'scheduled'    // 예약됨 (방문 전)
  | 'checked-in'   // 접수 완료
  | 'in-progress'  // 진료 중 / 입원 중
  | 'completed'    // 종료
  | 'cancelled';   // 취소

export interface Visit {
  visitId: string;          // RTDB key
  patientUid: string;
  hospitalId: string;       // slug
  type: VisitType;
  status: VisitStatus;

  // 위치 — type 별 의미 분기
  zone: string;             // 외래: 대기실 zone (예: "Zone A-1"), 검진/응급: 구역명
  ward?: string;            // 입원만: 병동 (예: "3W")
  room?: string;            // 입원만: 병실 호수 (예: "302")
  bed?: string;             // 입원만: 침대 (예: "A")

  // 메타
  department?: string;      // ER / IM / GS / PED ... (외래/응급 시 강하게 권장)
  displayName?: string;     // 환자명 cache (조회 빈번 → /users join 회피)
  scheduledFor?: number;    // 예약 시각 (ms)
  checkedInAt?: number;
  completedAt?: number;
  createdAt: number;
  updatedAt: number;
  createdBy: string;        // admin/staff uid
  notes?: string;           // 자유 메모 (max 500)
}
```

**Zod schema** 동일 구조 + validation:
- `zone`: required, max 50
- `ward/room/bed`: type='inpatient' 일 때만 required (cross-field validate)
- `department`: type='outpatient'|'emergency' 일 때 required
- `notes`: optional max 500

## 3. RTDB Rules (`database.rules.json`)

```json
"visits": {
  ".read": "auth != null && auth.token.role === 'platformAdmin'",
  "$hospitalId": {
    ".read": "auth != null && (auth.token.role === 'platformAdmin' || ((auth.token.role === 'staff' || auth.token.role === 'admin') && auth.token.hospitalId === $hospitalId))",
    ".indexOn": ["patientUid", "status", "type", "scheduledFor"],
    "$visitId": {
      ".read": "auth != null && (data.child('patientUid').val() === auth.uid || ((auth.token.role === 'staff' || auth.token.role === 'admin') && auth.token.hospitalId === $hospitalId) || auth.token.role === 'platformAdmin')",
      ".write": "auth != null && ((auth.token.role === 'admin' && auth.token.hospitalId === $hospitalId) || auth.token.role === 'platformAdmin')",
      ".validate": "newData.hasChildren(['patientUid', 'hospitalId', 'type', 'status', 'zone', 'createdAt'])"
    }
  }
}
```

핵심:
- 환자 본인만 자기 visit read (`data.child('patientUid').val() === auth.uid`)
- 같은 병원 staff/admin 도 read
- write 는 admin/platformAdmin 만 (환자/staff 는 read-only)
- patientUid + status + type + scheduledFor 인덱스

> **RTDB schema 0 → 1 migration 안전**: 기존 환자 visit 없는 상태 → fallback UI ("진료 정보 없음") 표시.

## 4. Service 레이어 (`src/services/visit.ts`)

```ts
export async function createVisit(slug: string, visit: Omit<Visit, 'visitId' | 'createdAt' | 'updatedAt'>): Promise<string>
export async function updateVisit(slug: string, visitId: string, partial: Partial<Visit>): Promise<void>
export async function updateVisitStatus(slug: string, visitId: string, status: VisitStatus): Promise<void>
export async function deleteVisit(slug: string, visitId: string): Promise<void>  // admin only

// 구독
export function subscribeActiveVisit(slug: string, patientUid: string, cb: (v: Visit | null) => void): Unsubscribe
// "active" = status in ['checked-in', 'in-progress']. 없으면 null.

// 조회
export async function listVisitsByPatient(slug: string, patientUid: string, opts?: { limit?: number }): Promise<Visit[]>
export async function listVisitsByDepartment(slug: string, dept: string, dateMs: number): Promise<Visit[]>
```

## 5. Hook (`src/hooks/useActiveVisit.ts`)

```ts
export function useActiveVisit(slug: string | null, patientUid: string | null): {
  visit: Visit | null;
  loading: boolean;
};
```
- patientUid 없으면 `{ visit: null, loading: false }`
- 마운트 시 `subscribeActiveVisit` → 자동 cleanup

## 6. UI 컴포넌트 변경

### 6.1 QRDisplay (`src/components/patient/QRDisplay.tsx`)
- 하드코딩 환자 정보 카드 → useActiveVisit 사용
- visit 분기 표시:
  - **outpatient**: `외래 / {department} / {zone}`
  - **inpatient**: `입원 / {ward}-{room}-{bed}` (zone 은 ward 로 대체)
  - **checkup**: `검진 / {zone}`
  - **emergency**: `응급 / ER / {zone}`
  - **null**: `진료 정보 없음 — 안내 데스크에 문의해주세요`
- 환자 displayName: `visit.displayName ?? useAuthStore().profile?.displayName ?? '환자'`

### 6.2 신규 — `AdminVisitsPage` 또는 `AdminVisitRegistrationDialog`
- admin 페이지 (`/h/{slug}/admin/visits`) 또는 기존 admin 페이지의 dialog
- 폼 필드:
  - patient (uid 선택 또는 이메일 검색)
  - type (radio 4종)
  - department (type 별 conditional)
  - zone / ward / room / bed (type 별 conditional)
  - scheduledFor (datetime)
  - notes
- 제출 → `createVisit` + audit log

### 6.3 (옵션, 본 sprint 비범위) Staff visit 콘솔
- Staff 가 오늘 active visit 리스트 보고 status 갱신
- 다음 sprint 로 분리 권장

## 7. 외래/입원 구분 정책

| Type | 위치 필수 필드 | 의미 |
|------|----------------|------|
| outpatient | zone + department | 외래 진료 — 대기실 zone + 진료과 |
| inpatient | ward + room (+ optional bed) | 입원 — 병동/병실/(침대) |
| checkup | zone | 건강검진 — 검진실 구역 |
| emergency | zone (+ department='ER') | 응급실 — ER 내 zone |

표시 우선순위: ward+room > zone (입원이면 zone 무시)

## 8. 단계별 Commit 계획 (Phase H.1 ~ H.7)

| # | Commit | 내용 | 파일 | 테스트 |
|---|--------|------|------|--------|
| H.1 | `feat(visit.types)` | Visit/VisitType/VisitStatus type + Zod schema | `src/types/visit.ts` + `src/types/__tests__/visit.test.ts` | Zod schema 8 케이스 (type 별 conditional required) |
| H.2 | `feat(visit.rules)` | RTDB rules `/visits` 추가 + deploy | `database.rules.json` | 수동 (RTDB simulator) |
| H.3 | `feat(visit.service)` | createVisit/updateVisit/subscribeActiveVisit + audit | `src/services/visit.ts` + `__tests__/visit.test.ts` | 12 케이스 (CRUD + active filter) |
| H.4 | `feat(visit.hook)` | useActiveVisit hook | `src/hooks/useActiveVisit.ts` + test | 4 케이스 (null/loading/loaded/error) |
| H.5 | `feat(qrdisplay.dynamic)` | QRDisplay 환자 정보 카드 동적 | `src/components/patient/QRDisplay.tsx` + test | 5 케이스 (4 type + null fallback) |
| H.6 | `feat(admin.visits)` | AdminVisitsPage + 등록 dialog | `src/pages/AdminVisitsPage.tsx` + components + test | 8 케이스 (form validation + submit) |
| H.7 | `docs(H) + 시드 데이터` | PHASE_H docs 갱신 + demo 시드 | `docs/PHASE_H_VISITS.md` + `scripts/seed-visits.ts` | — |

**총 commit ~7건, 테스트 ~37 케이스 추가** (335 → ~372)

## 9. 테스트 전략

### 단위
- Zod schema validation (type 별 필수 필드)
- Service CRUD + subscribe lifecycle
- Hook 의 null → loaded transition
- QRDisplay 분기별 렌더링

### 통합 (시나리오)
- A. admin 이 outpatient visit 등록 → 환자 LIVE QRDisplay 즉시 반영
- B. admin 이 inpatient 등록 → ward/room 표시
- C. visit 없음 → fallback 메시지
- D. 환자가 다른 환자 visit read 시도 → PERMISSION_DENIED (rules 검증)
- E. status 변경 (checked-in → in-progress) → UI 자동 갱신

## 10. 시드 데이터 / 마이그레이션

### 시드 (`scripts/seed-visits.ts`)
- catlife9029 (platformAdmin) 본인 outpatient visit 1건 — Zone A-1, IM
- staff-er@demo (가짜 환자 매핑) inpatient visit 1건 — 3W-302-A
- p0107044@gmail.com (환자) checkup visit 1건 — 검진실

### 마이그레이션
- 0 → 1 migration 안전 (기존 visits 없음)
- visit 없는 환자 → fallback UI 자동
- 별도 backfill 불필요

## 11. 본 sprint 비범위 (다음 sprints)

| 항목 | 우선순위 | 다음 sprint |
|------|----------|-------------|
| Staff visit 콘솔 (오늘의 환자 리스트 + status 갱신) | P1 | Phase I |
| 환자 visit history 페이지 | P2 | Phase I |
| Visit ↔ wait_queue 연동 (visit 등록 시 자동 wait_queue 등록) | P2 | Phase I |
| Visit ↔ session 연동 (현 active visit 의 zone 으로 동선 자동 계산) | P2 | Phase I |
| Visit notification (예약 시각 30분 전 push) | P3 | Phase J |
| Multi-bed inpatient (병상 변경 history) | P3 | Phase J |
| `/visits` cron TTL 정리 (status='completed' 90일 후 archive) | P3 | Phase J |

## 12. 위험 + 완화

| 위험 | 확률 | 영향 | 완화 |
|------|------|------|------|
| RTDB rules 수정 시 기존 환자 read 오류 | 낮음 | 중 | rules simulator 로 사전 검증 + 새 path 만 추가 (기존 변경 없음) |
| QRDisplay 회귀 (기존 시연용 카드 사라짐) | 중 | 낮음 | visit null 시 시연 친화 fallback 메시지 |
| visit.displayName cache stale (환자 displayName 바뀜) | 낮음 | 낮음 | refresh 함수 또는 visit 갱신 시 동기화 (별도 sprint) |
| admin 가 visit 등록 안 하면 환자 카드 영원히 fallback | 중 | 낮음 | admin 화면에 "오늘 등록된 visit 없음" 안내 + onboarding tooltip |
| FCM token 등 기존 path 와 권한 충돌 | 매우 낮음 | 중 | rules path 분리 — 충돌 가능성 0 |

## 13. 예상 소요

| Phase | 시간 |
|-------|------|
| H.1 — types + Zod | 30분 |
| H.2 — rules + deploy | 20분 |
| H.3 — service + tests | 60분 |
| H.4 — hook + tests | 20분 |
| H.5 — QRDisplay + tests + LIVE 검증 | 60분 |
| H.6 — admin page + tests | 90분 |
| H.7 — docs + 시드 + 통합 smoke | 40분 |
| **총** | **~5.5 시간 (1 sprint)** |

> Phase I (staff console + visit ↔ session 연동) 는 별도 1-2 sprint 추가.

---

## 진행 로그 (작업 시작 시 갱신)

| Phase | 상태 | Commit | 비고 |
|-------|------|--------|------|
| H.1 | ✅ done | (작업 중) | Visit type + 4 type guards + VISIT_TYPE_REQUIRED_FIELDS + isActiveStatus, vitest 19/19 pass |
| H.2 | ✅ done | (작업 중) | `/visits/{hid}/{visitId}` rules 추가 + deploy released, validate 강화 (type/status enum, zone len, hospitalId match) |
| H.3 | ✅ done | (작업 중) | createVisit/updateVisit/updateVisitStatus/deleteVisit + subscribeActiveVisit + listVisitsByPatient/Department + 4 visit.* AuditAction, vitest 14/14 pass |
| H.4 | ✅ done | (작업 중) | useActiveVisit hook (subscribe + cleanup), vitest 7/7 pass |
| H.5 | ✅ done | (작업 중) | QRDisplay 환자 정보 카드 동적 visit 바인딩 + 9 테스트, LIVE `index-OGIVtuQo.js` 배포 |
| H.6 | ✅ done | (작업 중) | AdminVisitsPage + nested route `/h/:slug/admin/visits` + 10 테스트, LIVE `index-8V4XKXmY.js` 배포 |
| H.7 | ✅ done | (작업 중) | manual seed 가이드 + Sprint Summary 섹션 + 진행 로그 마무리 |

---

## Sprint Summary (Phase H 종합)

### 결과
- **commit 7건** (H.1~H.7) 모두 push, 누적 vitest **354 → 394** (+40 케이스)
- **LIVE 배포 2회**:
  - H.5 hosting `index-OGIVtuQo.js` — QRDisplay 동적 바인딩
  - H.6 hosting `index-8V4XKXmY.js` + `index-BHCQsgut.css` — AdminVisitsPage
- **RTDB rules 1회 deploy** — `/visits/{hid}/{visitId}` path 신설

### 신규 파일
| 파일 | 역할 |
|------|------|
| `src/types/visit.ts` | Visit type + 4 type guards + form 메타 |
| `src/types/__tests__/visit.test.ts` | 19 케이스 |
| `src/services/visit.ts` | CRUD + active subscribe + listing + audit |
| `src/services/__tests__/visit.test.ts` | 14 케이스 |
| `src/hooks/useActiveVisit.ts` | 환자 active visit 실시간 구독 hook |
| `src/hooks/__tests__/useActiveVisit.test.ts` | 7 케이스 |
| `src/components/patient/__tests__/QRDisplay.test.tsx` | 9 케이스 |
| `src/pages/AdminVisitsPage.tsx` | admin 등록 폼 |
| `src/pages/__tests__/AdminVisitsPage.test.tsx` | 10 케이스 |
| `docs/PHASE_H_VISITS.md` | 본 문서 |

### 수정 파일
- `database.rules.json` — `/visits` 블록 추가 (audit_logs_v2 패턴)
- `src/types/admin.ts` — visit.* AuditAction 4건 추가
- `src/components/patient/QRDisplay.tsx` — 하드코딩 제거 → useActiveVisit 동적
- `src/App.tsx` — `/h/:slug/admin/visits` 라우트 등록 (ProtectedRoute requireRole=admin)
- `docs/HOSTING_DEPLOY_LOG.md` — H.2/H.5/H.6 entry 추가

### LIVE 검증 결과 (2026-04-26)
| 검증 | 결과 |
|------|------|
| QRDisplay 환자 정보 카드 — visit null fallback | ✅ "{displayName}" + "진료 정보 없음 — 안내 데스크에 문의해주세요" |
| 하드코딩 "MediWay 데모 환자 / Zone A-1" 제거 | ✅ 더 이상 표시 안 됨 |
| AdminVisitsPage 라우트 진입 | ✅ `/h/demo/admin/visits` (admin 권한) |
| visit 등록 폼 type 분기 | ✅ outpatient/inpatient/checkup/emergency conditional 필드 |

---

## Manual Seed 가이드

자동 seed script 는 본 sprint 비범위. LIVE 에서 admin/platformAdmin 계정으로 직접 등록 권장.

### 시드 시나리오 1 — 본인 외래 visit (catlife9029 platformAdmin)
1. `catlife9029@gmail.com` 으로 로그인
2. URL: `https://mediway-demo.web.app/h/demo/admin/visits`
3. 폼 입력:
   - 방문 유형: **외래**
   - 환자 uid: `S5gU1edQKeQ1w02th37Q8hQYowI2` (catlife9029 본인)
   - 환자 이름: `박준영`
   - 진료과: `내과`
   - 구역: `Zone A-1`
4. 「visit 등록」 클릭 → success 메시지 확인
5. **검증**: `/h/demo/patient/home?tab=guide` → 「내 QR 코드 발급」 → 환자 정보 카드에 "박준영 외래 · 내과 / Zone A-1" 표시 (status='scheduled' 라 active 아님 → fallback)
6. 추가 확인: status 를 'checked-in' 으로 변경하려면 RTDB console 직접 수정 (별도 sprint 의 status 변경 UI 도입 전까지)

### 시드 시나리오 2 — 입원 visit (다른 환자)
1. 동일 admin 페이지 진입
2. 폼 입력:
   - 방문 유형: **입원**
   - 환자 uid: `<inpatient 시연 uid>` (별도 환자 계정)
   - 병동: `3W` / 병실: `302` / 침대: `A`
   - 메모: "Phase H 시연용 입원 visit"
3. 등록 → 환자 측 (해당 uid 로 로그인) 카드에 "입원 · 3W-302-A" 표시 검증

### 시드 시나리오 3 — 응급 visit
1. 방문 유형: **응급**, 진료과: `ER`, 구역: `ER 분류실`

### Status 변경 (active → 표시) — 임시 가이드
현재 admin form 에서는 status='scheduled' 만 등록 가능. `checked-in` 또는 `in-progress` 로 변경해야 환자 카드에 visit 정보 표시.

옵션:
- (단기) Firebase Console → Realtime Database → `/visits/demo/{visitId}/status` 직접 수정 → `"checked-in"`
- (장기) Phase I 에서 status 변경 UI (staff/admin 콘솔) 추가 예정

---

## 본 sprint 종료 — 다음 sprint 후보 (Phase I)

| 우선순위 | 작업 |
|----------|------|
| P1 | Visit status 변경 UI (admin/staff 콘솔) — checked-in / in-progress / completed / cancelled 토글 |
| P1 | Staff visit 콘솔 — 오늘의 active visit 리스트 + 부서 필터 |
| P2 | Visit ↔ session 자동 연동 — staff 동선 발송 시 visit.zone 으로 동선 자동 계산 |
| P2 | Visit ↔ wait_queue 연동 — visit 등록 시 자동 wait_queue 등록 |
| P2 | 환자 visit history 페이지 (`/h/{slug}/patient/history`) |
| P3 | Visit notification — 예약 30분 전 push |
| P3 | `/visits` cron TTL — completed 90일 후 archive |
| P3 | 환자 검색 (admin form 의 patientUid 자동 완성) |
| P3 | admin nav 링크 — `/h/{slug}/admin/visits` 진입 메뉴 노출 |
