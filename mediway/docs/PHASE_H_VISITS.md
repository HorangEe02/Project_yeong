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
| H.3 | pending | — | — |
| H.4 | pending | — | — |
| H.5 | pending | — | — |
| H.6 | pending | — | — |
| H.7 | pending | — | — |
