# Phase I — Visit 운영 + 통합 sprint 군

> **작성일**: 2026-04-26
> **선행**: Phase H 완료 (visit 데이터 모델 + admin 등록 + 환자 표시 흐름).
> **방식**: 6개 sub-phase 으로 분할. 독립 sprint 단위.

---

## 0. Phase I 개관 + 의존 그래프

| Sub-phase | 우선순위 | 예상 소요 | 의존 |
|-----------|----------|-----------|------|
| **I.1** Visit status 변경 UI | P1 | ~3h | Phase H |
| **I.2** Staff visit 콘솔 | P1 | ~5h | I.1 |
| **I.3** Visit ↔ session/queue 자동 연동 | P2 | ~4h | I.1, I.2 |
| **I.4** 환자 visit history | P2 | ~3h | Phase H |
| **I.5** UX 보강 (admin nav, 환자 검색) | P3 | ~2h | I.2 |
| **I.6** Notification + cron archive | P3 | ~6h | I.1 |

```
Phase H (완료)
  ├─ I.1 status UI ─┬─ I.2 staff console ─┬─ I.3 session/queue 연동
  │                  │                      └─ I.5 UX 보강
  │                  └─ I.6 notification + cron
  └─ I.4 환자 history
```

추천 진행 순서: **I.1 → I.2 → I.4 → I.5 → I.3 → I.6** (운영 즉시 가치 우선, 자동화 후순위).
총 예상 소요: **~23h** (3-5 sprint 분할 권장).

---

## 1. Phase I.1 — Visit Status 변경 UI (P1, ~3h)

### Goal
Admin (그리고 향후 staff) 가 visit status 를 `scheduled → checked-in → in-progress → completed/cancelled` 토글 가능. 현재 한계 (manual Firebase Console 수정 의존) 해소.

### 변경 영역
- `src/services/visit.ts` — `subscribeRecentVisits(slug, limit, cb)` 추가
- `src/pages/AdminVisitsPage.tsx` — 등록 폼 아래에 **"최근 등록 visit 리스트"** 섹션 + status 변경 dropdown
- `updateVisitStatus` 는 이미 H.3 에서 구현 — UI 만 추가

### Commit 분할
| # | Commit | 내용 |
|---|--------|------|
| I.1.1 | `feat(visit.service.recent)` | `subscribeRecentVisits(slug, limit, cb)` — orderByChild('createdAt') + limitToLast(N), 5 케이스 |
| I.1.2 | `feat(admin.visits.list)` | AdminVisitsPage 하단 리스트 + status badge + 변경 dropdown, 6 케이스 |
| I.1.3 | `docs(I.1) + LIVE deploy` | HOSTING_DEPLOY_LOG, build + deploy |

### 테스트 추가 예상
~11 케이스 (vitest 405)

### 위험
- 리스트 무한 증가 → limit=20 default + load-more 버튼 (별도 sprint)
- 다중 admin 동시 status 변경 race → optional transaction (필요 시 별도 sprint)

---

## 2. Phase I.2 — Staff Visit 콘솔 (P1, ~5h)

### Goal
Staff 가 본인 부서의 **오늘 active visit 리스트** 를 보고 status 토글. Admin 의존성 ↓.

### 변경 영역
- 신규 `src/pages/StaffVisitsPage.tsx` — `/h/{slug}/staff/visits`
- `StaffSubNav` 에 "환자 진료" 탭 추가 (4탭화)
- RTDB rules — staff status-only write 허용
  - 옵션 A: child-level rule (status 만 변경 가능)
  - 옵션 B: callable function 우회
  - **추천 A** — latency ↓, function 비용 ↓

### RTDB rules 변경 예시
```json
"$visitId": {
  ".write": "auth != null && (
    auth.token.role === 'platformAdmin' ||
    (auth.token.role === 'admin' && auth.token.hospitalId === $hospitalId) ||
    (auth.token.role === 'staff' && auth.token.hospitalId === $hospitalId &&
     data.exists() && newData.exists() &&
     newData.child('patientUid').val() === data.child('patientUid').val() &&
     newData.child('hospitalId').val() === data.child('hospitalId').val() &&
     newData.child('type').val() === data.child('type').val() &&
     newData.child('zone').val() === data.child('zone').val()
    )
  )"
}
```
> 복잡도 ↑. 대안: `visit_status_log` path + onValue trigger function (1단계 indirection).

### 서비스 / Hook
- `subscribeActiveVisitsByDepartment(slug, dept, dateMs, cb)` — 부서별 오늘 active 실시간
- `useStaffActiveVisits(dept, dateMs)` hook

### Commit 분할
| # | Commit | 내용 |
|---|--------|------|
| I.2.1 | `feat(visit.rules.staff_status)` | RTDB rules — staff status-only write 허용 + simulator 검증 |
| I.2.2 | `feat(visit.service.byDept)` | subscribeActiveVisitsByDepartment + 8 케이스 |
| I.2.3 | `feat(visit.hook.staff)` | useStaffActiveVisits + 5 케이스 |
| I.2.4 | `feat(staff.visits.page)` | StaffVisitsPage + 라우트 + StaffSubNav 확장 + 10 케이스 |
| I.2.5 | `docs(I.2) + LIVE deploy` | |

### 테스트 추가 예상
~23 케이스 (vitest 428)

### 위험
- staff 의 `profile.department` 누락 → 부서 필터 fail. Phase H 검증 시 staff-er@demo 등 이미 OK
- staff RTDB rules 정밀도 — 별도 security review 권장
- 다중 active visit 정렬 정책 (createdAt asc/desc)

---

## 3. Phase I.3 — Visit ↔ Session/Queue 자동 연동 (P2, ~4h)

### Goal
- **Visit ↔ Session**: staff 동선 발송 시 visit.zone 을 첫 waypoint 로 자동 매핑
- **Visit ↔ Wait_queue**: visit 등록 시 자동 wait_queue 등록 (외래/응급)

### 변경 영역
- `src/components/staff/StaffDashboard.tsx` — useActiveVisit 호출, visit.zone → POI 매핑
- `src/services/waitQueue.ts` — `enqueueOnVisitCreate(visit)` helper
- `src/services/visit.ts` createVisit 에 `{ autoEnqueue: true }` 옵션
- POI 매핑 — `visit.zone` 문자열 → POI ID lookup table

### 위험
- POI ID 매핑 휴리스틱 어려움 — Zone naming convention 정립 필요
- 자동 enqueue 시 중복 (이미 wait_queue 에 있는 환자)

### Commit 분할
| # | Commit | 내용 |
|---|--------|------|
| I.3.1 | `feat(visit.zone_mapping)` | POI ↔ zone lookup helper + 8 케이스 |
| I.3.2 | `feat(staff.visit_aware)` | StaffDashboard 가 visit.zone 인식 + 자동 첫 waypoint, 6 케이스 |
| I.3.3 | `feat(visit.autoEnqueue)` | 외래/응급 visit 등록 시 wait_queue 자동 등록 (옵션 플래그) + 5 케이스 |
| I.3.4 | `docs(I.3) + LIVE deploy` | |

### 테스트 추가 예상
~19 케이스

---

## 4. Phase I.4 — 환자 Visit History 페이지 (P2, ~3h)

### Goal
환자가 자기 과거 visit 기록 조회.

### 변경 영역
- 신규 `src/pages/PatientHistoryPage.tsx` — `/h/{slug}/patient/history`
- HospitalHomePage "더보기" 탭에 "방문 이력" 링크 추가
- service: `useVisitHistory(slug, patientUid, opts)` hook
- 표시: 카드 리스트 (date / type badge / department / status / notes preview)

### Commit 분할
| # | Commit | 내용 |
|---|--------|------|
| I.4.1 | `feat(visit.hook.history)` | useVisitHistory hook + 4 케이스 |
| I.4.2 | `feat(patient.history.page)` | PatientHistoryPage + 라우트 + 7 케이스 |
| I.4.3 | `feat(home.more.history_link)` | "더보기" 탭에 진입 링크 + 3 케이스 |
| I.4.4 | `docs(I.4) + LIVE deploy` | |

### 테스트 추가 예상
~14 케이스

### 위험
- 1000+ visit history → 페이지네이션 (별도 sprint)

---

## 5. Phase I.5 — UX 보강 (P3, ~2h)

### Goal
- Admin nav 에 "환자 visit 등록" 링크 노출
- AdminVisitsPage 의 patientUid 입력 → 환자 검색 자동 완성

### 변경 영역
- `src/pages/admin/AdminDashboardPage.tsx` 또는 nav 컴포넌트 — visit 진입 링크
- `searchUsers(query)` service (이미 admin 페이지에 있을 가능성 — 우선 점검)
- 검색 dropdown UI

### Commit 분할
| # | Commit | 내용 |
|---|--------|------|
| I.5.1 | `feat(admin.nav.visits_link)` | 진입 메뉴 + 3 케이스 |
| I.5.2 | `feat(admin.visits.patient_search)` | uid 입력 → 검색 dropdown + 7 케이스 |
| I.5.3 | `docs(I.5) + LIVE deploy` | |

### 테스트 추가 예상
~10 케이스

---

## 6. Phase I.6 — Notification + Cron Archive (P3, ~6h)

### Goal
- Visit 예약 30분 전 FCM push
- status='completed' visit 90일 후 자동 archive (`/visits_archive/{hid}/...`)

### 변경 영역 (functions/ 측)
- `functions/src/visits/visitReminderScheduler.ts` — 5분 단위 cron, 30분 ± 5분 범위 검색 → FCM
- `functions/src/visits/visitArchiveScheduler.ts` — 일 1회 cron, completed > 90일 → archive 이동 + 원본 삭제
- `firebase.json` — scheduled function 등록 (이미 onSchedule 사용 중 — 같은 패턴)

### Commit 분할
| # | Commit | 내용 |
|---|--------|------|
| I.6.1 | `feat(visit.reminder)` | visitReminderScheduler + FCM dispatcher 통합 + 8 케이스 (functions vitest) |
| I.6.2 | `feat(visit.archive)` | visitArchiveScheduler + RTDB rules `/visits_archive` 추가 + 6 케이스 |
| I.6.3 | `docs(I.6) + LIVE deploy` | functions deploy + RTDB rules deploy |

### 테스트 추가 예상
~14 케이스 (functions vitest)

### 위험
- Notification spam — patient FCM token 미등록 → silent drop
- Archive 중 partial fail → transaction 또는 atomic move

---

## 7. 진행 로그

| Phase | 상태 | Commit | 비고 |
|-------|------|--------|------|
| I.1.1 | pending | — | service `subscribeRecentVisits` |
| I.1.2 | pending | — | AdminVisitsPage 리스트 + status 변경 |
| I.1.3 | pending | — | docs + LIVE deploy |
| I.2.1 ~ I.2.5 | pending | — | Staff console |
| I.3.1 ~ I.3.4 | pending | — | session/queue 연동 |
| I.4.1 ~ I.4.4 | pending | — | patient history |
| I.5.1 ~ I.5.3 | pending | — | UX 보강 |
| I.6.1 ~ I.6.3 | pending | — | notification + archive |
