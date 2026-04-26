# P3 F1 — Wait Queue UI 통합 / Prod-Parity 이식 설계

> 작성일: 2026-04-26 (B-3.10 직후)
> 전제 핸드오프: [HANDOFF_2026-04-25](./HANDOFF_2026-04-25.md) §6 priority "🔵 P3 F1 wait queue UI 통합"
> 선행: B-3.10 hospital slug routing 완료 (HospitalShell + HospitalContext)
> 목표: prod e2e (`public/e2e-wait-queue.html`) 가 기대하는 동작을 local source 가 충실히 만족
> 범위: 본 문서는 **설계 + commit 단위 계획**. 실제 구현은 사용자 승인 후 step-by-step.

---

## 0. 목적

prod e2e-wait-queue.html 시나리오 A~D 를 local source 로도 그대로 통과시키는 것.
시나리오 E (AI Triage) 는 `triageSymptoms` function 이 삭제된 상태라 별도 sprint 로 분리.

| 시나리오 | 핵심 기대 | 본 sprint 다룸? |
|----------|-----------|----------------|
| A 접수 → 순번 표시 | 환자 [접수] 클릭 → 홈 위젯 즉시 순번 표시 | ✅ 검증 + UX 보강 |
| B Call Next → 알림 | staff [다음 환자 호출] → 환자 위젯 강조 + FCM | ✅ 통합 검증 |
| C 진료 시작 → 완료 | staff [진료 시작]/[완료] → 환자 위젯 갱신 | ✅ 검증 |
| D 교차 병원 격리 | smch 계정이 demo wait_queue read → 401 | ✅ rule-level (이미 통과 추정) 회귀 보장 |
| E AI Triage | features.aiTriage=true → 위젯 노출 | ⛔ 별도 sprint (function 부재) |

---

## 1. 현재 ↔ Prod 기대 차이 (4가지)

### 차이 ① — Hospital features 무시
**현재**: HospitalHomePage 의 6 탭 (`home/appointments/inpatient/checkup/guide/more`) + HomeTab 의 `<WaitQueueWidget/>` + `<ChatbotWidget/>` 를 **무조건 마운트**.
**Prod 기대**: e2e §A "features.appointments=true 전제" / §E "features.aiTriage=true 설정 시 노출".

**증거**:
- `AdminHospitalDetailPage` 가 9개 feature key (appointments / inpatient / checkup / payment / prescription / aiTriage / familyDelegation / healthRecords / parking) 를 admin 이 토글
- `functions/src/chatbot/context.ts` 가 `profile.features` 를 chatbot 에 주입
- prod 번들은 HospitalProfile.features 로 UI 분기 (역엔지니어링 §3.3 staffQueue 분기)

**가공**: HospitalShell 가 이미 profile (with features) 을 로드하고 HospitalContext 에 주입. 자식들이 `useHospital().profile.features` 를 읽어 분기하면 됨. 자료 추가 없음.

### 차이 ② — WaitQueueWidget 가 `profile.hospitalId` 사용
**현재**: `const hospitalId = profile?.hospitalId ?? null;` — 사용자의 home hospital 만 구독.
**Prod 기대**: 환자가 `/h/{slug}/patient/home` 진입 → 그 **URL 슬러그** 의 wait queue 구독 (멀티 병원 방문 시 home != 현재 방문 병원 분리).

**현재 부작용**: profile.hospitalId='demo' 인 환자가 `/h/smch/patient/home` 에서도 demo 의 wait queue 를 보게 됨 (B-3.10 cross-tenant 가드가 차단하긴 함, 그러나 platformAdmin 우회 시 잘못된 데이터).

**가공**: `useHospital().slug` 으로 교체. cross-tenant 는 Shell 가드가 이미 차단.

### 차이 ③ — Staff 콘솔 발견성 부족
**현재**: `/h/{slug}/staff` → StaffPage (StaffDashboard "동선 전송") / `/h/{slug}/staff/queue` → StaffQueuePage. **두 페이지 사이 내부 링크 0** — staff 가 둘 다 접근하려면 URL 직접 입력 또는 bookmark.
**Prod 기대**: e2e §B "의료진: /h/demo/staff/queue 진입" — staff 가 자연스럽게 도달할 수 있어야 함.

**가공**: 두 페이지 상단에 공통 sub-navigation (탭 형태) 추가 — 「동선 전송」/「대기열 콘솔」.

### 차이 ④ — WaitQueueWidget empty state UX 막다름
**현재**: 활성 엔트리 0 일 때 "오늘 접수된 진료가 없습니다" — CTA 없음.
**Prod 기대**: e2e §A "+ 새 예약 → 접수 → 위젯 갱신" — 사용자가 다음 step (외래 탭) 을 발견할 수 있어야 함.

**가공**: empty state 에 "외래 탭에서 예약 후 접수하면 순번이 표시됩니다 →" CTA 링크 (`?tab=appointments`).

---

## 2. 추가/변경 파일 목록

### 신규
| 파일 | 역할 |
|------|------|
| `src/contexts/HospitalContext.tsx` (확장) | `useHospitalFeatures()` 추가 — features merged with FEATURE_DEFAULTS |
| `src/components/staff/StaffSubNav.tsx` | 두 페이지 상단 공통 sub-nav (대시보드 ↔ 대기열) |
| `src/components/staff/__tests__/StaffSubNav.test.tsx` | 활성 탭 표시 + 링크 검증 |
| `src/contexts/__tests__/useHospitalFeatures.test.tsx` | features merge + defaults |
| `src/__tests__/waitQueueIntegration.test.tsx` | 시나리오 A/B/C/D 단대단 통합 smoke |

### 변경
| 파일 | 변경 |
|------|------|
| `src/components/patient/WaitQueueWidget.tsx` | `useHospital().slug` 사용 + features.appointments 가드 + empty-state CTA |
| `src/components/patient/tabs/HomeTab.tsx` | `features.appointments` 에 따라 WaitQueueWidget 마운트 / `features.aiTriage` placeholder 마운트(현 단계는 disabled 안내만) |
| `src/pages/HospitalHomePage.tsx` | TAB_ORDER 를 features 에 맞게 필터 (appointments/inpatient/checkup) + active tab 비활성화 시 home 으로 fallback |
| `src/components/patient/tabs/AppointmentsTab.tsx` | `useHospital().slug` 사용 (currently `profile.hospitalId`) |
| `src/pages/StaffPage.tsx` | 상단에 `<StaffSubNav/>` + 사이드바의 mock stat 카드 → "대기열 요약" (queue stats 실제값) |
| `src/pages/StaffQueuePage.tsx` | 상단에 `<StaffSubNav/>` + `useHospital().slug` 사용 + 부서 정렬 KSt 정렬 점검 |

### 변경 안 함 (의도적)
- `services/waitQueue.ts` — 이미 prod parity 충실. 재변경 시 회귀 위험.
- `functions/src/wait_queue/onQueueCall.ts` — F5b 에서 dispatcher 통합 완료. 회귀 없음.
- `triageSymptoms` 재작성 — LOCAL_SYNC_GAPS §1.1 별도 sprint.
- 부서 목록 RTDB 동기화 — schema 미정. 하드코딩 유지.

---

## 3. 설계 — Hospital features 모델

### 3.1 Defaults
RTDB `hospitals/{slug}/profile/features/{key}` 가 누락되어도 안전하게 동작하도록 default 정의:

```ts
export const FEATURE_DEFAULTS: Record<string, boolean> = {
  appointments: true,    // 외래 (wait queue + AppointmentsTab)
  inpatient: false,
  checkup: false,
  payment: false,
  prescription: false,
  aiTriage: false,
  familyDelegation: false,
  healthRecords: false,
  parking: false,
  chatbot: true,         // ChatbotWidget — admin UI 에는 없지만 default on
};
```

이유: prod 번들의 demo 병원이 `appointments=true, aiTriage=false` 상태에서 정상 동작. default on 으로 두면 features 누락 RTDB 도 안전.

### 3.2 Hook
```ts
// src/contexts/HospitalContext.tsx 에 추가
export function useHospitalFeatures(): Readonly<Record<string, boolean>> {
  const { profile } = useHospital();
  // RTDB 값 + defaults 병합. RTDB 가 명시한 값이 defaults 를 덮어쓴다.
  return { ...FEATURE_DEFAULTS, ...(profile.features ?? {}) };
}
export function useFeature(key: string): boolean {
  return useHospitalFeatures()[key] ?? false;
}
```

### 3.3 사용 예
```tsx
const features = useHospitalFeatures();
if (!features.appointments) return null;
// or
const aiTriageOn = useFeature('aiTriage');
```

---

## 4. 설계 — Staff sub-navigation

### 4.1 컴포넌트
```
<StaffSubNav active="dashboard|queue" />
└── 두 개 NavLink:
    [동선 전송 - /h/{slug}/staff]   [대기열 콘솔 - /h/{slug}/staff/queue]
└── 활성 탭은 primary 색 + 배경, 비활성은 surface-container
```

### 4.2 마운트 위치
- StaffPage 상단 (h1 헤더 위)
- StaffQueuePage 상단 (h1 헤더 위)

### 4.3 비범위 (논의 후 결정)
- StaffShell 까지 만들어 두 페이지 공통 레이아웃 통합 (선택지 A) vs 단순 컴포넌트만 추가 (선택지 B)
- **본 sprint 는 B 채택** — 가벼운 변경, 회귀 위험 최소

---

## 5. 설계 — Patient widget UX 보강

### 5.1 WaitQueueWidget empty state CTA
```
┌──────────────────────────────────────────┐
│ 오늘 접수된 진료가 없어요.               │
│                                          │
│ ➜ 외래 탭에서 예약 후 [접수] 누르면      │
│   여기에 순번이 실시간으로 표시됩니다.    │
│                                          │
│ [외래 탭으로 이동 →]                     │
└──────────────────────────────────────────┘
```
- 버튼 클릭 → `setSearchParams({ tab: 'appointments' }, { replace: true })`
- HospitalHomePage 의 query 동기화로 자연스러운 탭 전환

### 5.2 features.appointments=false 시 위젯 자체 비표시
- HomeTab 가 conditional render — null 반환

### 5.3 hospitalId 소스 변경
- before: `profile?.hospitalId` (사용자 home)
- after: `useHospital().slug` (URL 의 현 hospital)
- cross-tenant 검증은 HospitalShell 가 이미 담당

---

## 6. Commit 단위 계획

각 commit 은 빌드 통과 + 회귀 0 보장. 각 단계 끝에 vitest+tsc+build 실행.

### Commit 1 — `feat(F1.1a): useHospitalFeatures + FEATURE_DEFAULTS`
- 변경: `src/contexts/HospitalContext.tsx`
- 신규: `src/contexts/__tests__/useHospitalFeatures.test.tsx`
- 검증: 12+ unit test (default merge / RTDB override / unknown key=false)
- LIVE 영향: 0

### Commit 2 — `feat(F1.1b): HospitalHomePage tab visibility from features`
- 변경: `src/pages/HospitalHomePage.tsx`, `src/components/patient/tabs/types.ts` (TAB_ORDER 에 feature key 매핑)
- 검증: 단위 + UI 토글 케이스
- LIVE 영향: 0
- 호환성: features 미설정 RTDB → defaults 적용 → 기존 6 탭 노출 (회귀 없음)

### Commit 3 — `feat(F1.1c): WaitQueueWidget hospital-aware + features-gated + empty CTA`
- 변경: `src/components/patient/WaitQueueWidget.tsx`, `src/components/patient/tabs/HomeTab.tsx`
- 검증: 단위 + UI render 매트릭스
- LIVE 영향: 0

### Commit 4 — `feat(F1.1d): AppointmentsTab uses useHospital().slug`
- 변경: `src/components/patient/tabs/AppointmentsTab.tsx`
- 검증: 기존 테스트 그린 + 추가 hospital-aware 테스트
- LIVE 영향: 0

### Commit 5 — `feat(F1.2): StaffSubNav + Staff/StaffQueue 통합 헤더`
- 신규: `src/components/staff/StaffSubNav.tsx` + 테스트
- 변경: `src/pages/StaffPage.tsx`, `src/pages/StaffQueuePage.tsx`
- 검증: 활성 탭 + 링크 + 시각 회귀 (manual screenshot)
- LIVE 영향: 0

### Commit 6 — `test(F1.3): wait queue 시나리오 A-D 통합 smoke`
- 신규: `src/__tests__/waitQueueIntegration.test.tsx`
- 검증: 시나리오 A, B, C, D 의 핵심 단계를 mock 으로 재현
- LIVE 영향: 0

### Commit 7 — `docs(F1): wait queue UI 통합 완료 + 추적`
- 변경: 본 문서 §10 추적 갱신
- 변경: `docs/HANDOFF_*.md` 또는 신규 핸드오프
- 변경: `docs/LOCAL_SYNC_GAPS.md` § 5 Tier 1 의 F1 항목 → ✅ 완료
- LIVE 영향: 0

### (옵션) Commit 8 — hosting preview redeploy
- 사용자 승인 시: `firebase hosting:channel:deploy preview-b310 --expires 7d` 재배포 (B-3.10 + F1 결합)
- 시각 검증 후 본 배포 단계 별도 승인

---

## 7. 테스트 전략

### 단위
| 컴포넌트 | 케이스 |
|----------|--------|
| `useHospitalFeatures` | (a) RTDB 미설정 → defaults, (b) RTDB partial → 부분 override, (c) RTDB 와 defaults 충돌 → RTDB 우선, (d) 알 수 없는 key → false 반환 |
| `HospitalHomePage` tab visibility | (a) all features on → 6 탭, (b) appointments=false → 5 탭, (c) inpatient=false&checkup=false → 4 탭, (d) active tab 이 비활성 → 'home' fallback |
| `WaitQueueWidget` features-gated | (a) appointments=true + 데이터 → 카드, (b) appointments=false → null, (c) empty + appointments=true → CTA, (d) CTA 클릭 → ?tab=appointments |
| `StaffSubNav` | (a) /staff 활성, (b) /staff/queue 활성, (c) 다른 슬러그에서 잘 동작 |

### 통합 (시나리오 A-D)
- A: AppointmentsTab 에서 [접수] 가상 클릭 → checkInToQueue mock → WaitQueueWidget 순번 N 표시
- B: subscribeMyWaitQueue mock callback 으로 status='called' 푸시 → 위젯 ring + "진료실로 이동" 문구
- C: status='in-progress' → "진료 중" / status='completed' → "오늘 접수된 진료가 없습니다"
- D: cross-tenant 차단은 HospitalShell 테스트로 이미 커버 — 본 sprint 는 회귀 보장만

### 회귀 (변경 없음 보장)
- B-3.10 nested 라우팅 17 + 162 단위 그대로 그린
- waitQueue.ts 27 unit test 그대로 그린

---

## 8. 리스크 / 비범위

| 리스크 | 가능성 | 영향 | 완화 |
|--------|--------|------|------|
| features 미설정 RTDB → 기존 demo 병원이 일부 탭 사라짐 | 중 | 회귀 (UI 결손) | FEATURE_DEFAULTS 의 appointments=true 등으로 default on 처리 |
| profile.hospitalId 사용처 (다른 컴포넌트) 회귀 | 낮음 | 위젯이 잘못된 hospital 구독 | F1 변경은 WaitQueueWidget + AppointmentsTab 만. 그 외는 범위 외 |
| useHospital() 가 없는 라우트(/account, /admin) 에서 import 하면 throw | 낮음 | 빌드 통과해도 런타임 에러 | useHospital() 호출은 nested 자식만 |
| 시나리오 E (AI Triage) 부재로 prod 번들과 시각 차이 | 중 | UX 차이 | features.aiTriage=false 인 demo 에선 영향 없음. 본 sprint 비범위 |
| StaffSubNav 가 admin 페이지 (`/admin/...`) 에 잘못 표시 | 낮음 | UI 혼란 | StaffPage / StaffQueuePage 에만 마운트, admin 비건드림 |
| Header 칩 (의료진/환자) 와 sub-nav 시각적 중복 | 낮음 | 시각 노이즈 | sub-nav 는 페이지 내부에 두므로 헤더와 분리 |

### 비범위
- triageSymptoms 함수 재작성
- 부서 목록 RTDB 동기화 (`/hospitals/{hid}/departments`)
- 호출 취소 / 재호출 / skip / 환자측 self-cancel
- `/staff` 의 sidebar mock data → 실제 stat 으로 치환 (선택사항이지만 sprint 부풀림)
- 다중 부서 동시 접수 시 위젯에 모두 표시 (현재 primary 1건만 — prod 동일)

---

## 9. 합의 요청 항목

사용자 승인 필요:

1. **Sub-nav 디자인**: §4.1 의 단순 두-탭 형태 OK? (StaffShell wrapper 만드는 안은 비범위로 제외)
2. **Feature defaults**: §3.1 의 default 매트릭스 OK? (특히 `chatbot=true`, `appointments=true` default on)
3. **WaitQueueWidget hospitalId 소스**: profile.hospitalId → `useHospital().slug` 로 교체 OK?
4. **시나리오 E (AI Triage) 별도 sprint**: 본 sprint 비범위로 분리 OK?
5. **commit 분할**: 6 feat/test commit + 1 docs commit OK?
6. **Sidebar mock 카드 처리**: StaffPage 사이드바의 가상 stat 카드는 본 sprint 에서 손대지 않음. 동의?

승인되면 commit 1 부터 순차 작업.

---

## 10. 진행 추적

| # | Commit | 상태 | 결과 요약 |
|---|--------|------|-----------|
| 1 | `3174225` | ✅ 완료 | `FEATURE_DEFAULTS` + `useHospitalFeatures()` + `useFeature()` + 13 unit test |
| 2 | `fc4650c` | ✅ 완료 | TabSpec.feature 매핑 / `visibleTabs` / `ensureVisibleTab` + HospitalHomePage tab 가시성 (10 unit test 추가) |
| 3 | `b230db5` | ✅ 완료 | WaitQueueWidget — useHospital().slug + features.appointments 가드 + empty CTA + error 우선 분기 (15 unit test) |
| 4 | `bcd9f15` | ✅ 완료 | AppointmentsTab — useHospital().slug + dead branch / null guard 정리 |
| 5 | `ad4c5d6` | ✅ 완료 | StaffSubNav + Staff/StaffQueue 통합 헤더 + StaffQueuePage slug 일원화 (6 unit test) |
| 6 | `b36936b` | ✅ 완료 | wait queue 시나리오 A-D 통합 smoke (6 케이스) — broadcastPatient() 다중 구독자 mock |
| 7 | (이 commit) | ✅ 완료 | 본 문서 progress 갱신 + LOCAL_SYNC_GAPS Tier 1 정리 |

### 최종 메트릭

- **6 feat/test commit + 1 docs commit = 7 커밋**
- **vitest**: 172 → 222 passed (+50: 13 features hook + 10 tab visibility + 15 widget + 6 staff sub-nav + 6 integration)
- **tsc 0 errors**, **vite build 성공**
- **LIVE 영향 0** — hosting 재배포는 별도 승인

### Prod-parity 도달 항목

| e2e 시나리오 | local 가능? | 자동 검증? |
|-------------|------------|-----------|
| A 접수 → 위젯 순번 표시 | ✅ | `waitQueueIntegration.test` Scenario A |
| B Call Next → 환자 위젯 강조 | ✅ | Scenario B |
| C 진료 시작/완료 전이 | ✅ | Scenario C |
| D 교차 병원 격리 | ✅ (HospitalShell) | `HospitalShell.test` cross-tenant 매트릭스 + Scenario D 회귀 |
| E AI Triage | ⛔ 별도 sprint | `triageSymptoms` 함수 부재 (LOCAL_SYNC_GAPS §1.1) |

### 남은 작업 (별도 sprint)

- 시나리오 E — `triageSymptoms` 함수 재작성 + AI Triage Widget UI
- 부서 목록 RTDB 동기화 (`/hospitals/{slug}/departments`)
- 호출 취소 / 재호출 / skip / 환자 self-cancel
- StaffPage sidebar mock 카드 → 실제 stat 으로 치환
- 다중 부서 동시 접수 시 위젯에 모두 표시 (현재 primary 1건)
- (옵션) hosting `preview-b310` 채널 재배포 (B-3.10 + F1 결합)
