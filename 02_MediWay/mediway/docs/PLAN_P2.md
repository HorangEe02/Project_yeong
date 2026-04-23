# Phase 2 구현 계획 — 대시보드 셸 + 상단 탭 + 고령자 모드 (v2 기준)

> **상태**: 계획 (2026-04-23)
> **브랜치**: `mediway/plusultra/p2` (착수 시 `mediway/develop`에서 분기)
> **타깃 병합지**: `mediway/develop`
> **기반**: P1 완료 (`mediway/develop @ 3eec2a2`)
> **예상 기간**: 3주 (1인 풀타임)
> **참조**: `GUIDE_v2/plusultra_v2.md §Phase 2` + `GUIDE_v2/PlusUltra#2.md` (v2 덮어쓰기 블록 확인)

---

## 0. 목표

P1에서 마련한 Multi-Tenant 기반 위에 **병원 대시보드 셸**을 얹는다. 환자가 로그인하면 보이는 첫 화면을 **6개 탭 + 홈 위젯 3개** 구조로 확립하여 **후속 Phase(P3 편의 · P4 접근성 · P5 고급)의 기능이 들어갈 슬롯**을 제공한다.

### 성공의 정의 (v2 기준)

1. 로그인 환자가 `/h/{slug}/patient`에 진입하면 6개 탭(홈·외래·입원·검진·안내·더보기) 셸이 렌더된다
2. **홈 위젯 정확히 3개 (+1 선택)** — `오늘 일정 · 대기 순번 플레이스홀더 · 응급실 CTA`
3. 탭 URL 영속 (`?tab=home`) — 새로고침/공유에 강함
4. 기존 안내/QR/지도 기능이 "안내" 탭 내부로 손상 없이 흡수
5. **고령자 모드 토글**이 "더보기" 탭에서 작동 (CSS custom property + `.ui-senior` root class 인프라 완성). 본격 고령자 UI 완성은 P4지만 P2에서 토글·전환·일관성 유지가 가능해야 함
6. Hospital features flag에 따라 탭이 동적 on/off (예: `appointments:false` 면 외래 탭 숨김)

---

## 1. 스코프

### IN (v2 반영)

| 영역 | 내용 |
|---|---|
| 라우팅 | `/h/:slug/patient/home?tab=…` 중첩 구조, URL 영속 |
| 셸 | `HospitalHomePage` (탭 컨테이너) + 6 Tab 컴포넌트 |
| 홈 탭 | 위젯 3개 상한, 빈 상태 명료화 |
| 외래 탭 MVP | 진료 시간표·예약 생성·내 예약 목록·취소 (실시간 대기·결제는 P3) |
| 입원/검진 탭 | 스켈레톤만 (feature flag로 노출, 내용은 "준비 중") |
| 안내 탭 | 기존 `PatientPage` + `PatientMapBrowseView` + `PatientDashboard` 흡수 |
| 더보기 탭 | 내 정보 · 병원 스위처 · 알림 설정 · **고령자 모드 토글** · 로그아웃 |
| 고령자 모드 | 토글 + CSS class 주입 + 간단 scale (폰트 1.2배). 완성은 P4 |
| Feature flag | `hospital.features.*` 기반 탭 가시성 |
| 세션 보존 | 탭 전환 시 QR/길찾기 세션 유지 (Mount all + visibility toggle) |

### OUT (후속)

- 실시간 대기 순번·처방전·결제·알림톡 → P3
- 고령자 모드 전용 "단순 홈" 레이아웃 → P4
- TTS·가족 대리·OAuth 확장 → P4
- 검사결과·메시지·문진·PHR → P5

### v2에서 특별히 반영할 사항

| 항목 | v2 규정 | 구현 |
|---|---|---|
| 홈 위젯 수 | **최대 3개 + 병원 선택 슬롯 1개** | Array 상한 검증, 컴파일 오류 대신 런타임 warn |
| 고령자 모드 시작 시점 | **P2부터** 토글 작동 | 토글 UI + 상태 저장 + CSS 주입 인프라 |
| 응급실 CTA | 홈 위젯 1개로 **고정** | 홈 탭 상단 또는 하단 고정 배치, 확인 모달 필요 (119 오발신 방지) |
| MyChart 반면교사 | "기능 과다" 회피 | 추가 위젯 욕구 → "더보기"로 리다이렉트 |

---

## 2. 선행 조건 체크리스트

- [x] P1 merge to `develop` 완료 (`3eec2a2`)
- [x] `/hospitals/demo/*` 데이터 존재
- [x] HospitalContext/HospitalGate 작동
- [x] `/h/:slug/*` 라우트 트리 준비
- [ ] 로컬 개발 환경 확인 (`npm install` + `.env.local` + `npm run dev`)
- [ ] `/h/demo/patient` 진입 시 기존 PatientPage 내용 보임 (현재 상태)

---

## 3. 작업 순서 — 10개 논리 단위 (Commit 단위)

### Commit 1 — Tab 시스템 기반 (Foundation)

**파일**
- `src/types/tabs.ts` (신규) — `TabId`, `TabDef`, `TAB_DEFS`
- `src/hooks/useTabState.ts` (신규) — URL ?tab= 동기화 훅 (`useSearchParams` 기반)
- `src/components/hospital/HospitalTabs.tsx` (신규) — 탭 네비 컴포넌트 (모바일 scroll + 데스크탑 horizontal)

**검증**
- 단위 테스트 4+개 (tab 전환·URL sync·feature flag 필터·overflow)

**리스크**: 낮음 (격리된 UI·훅)

---

### Commit 2 — HospitalHomePage 셸

**파일**
- `src/pages/HospitalHomePage.tsx` (신규) — 탭 컨테이너 (Mount all + visibility toggle)
- `src/App.tsx` — `/h/:slug/patient/home` 라우트 추가 (기존 `patient` 보존)
- `src/components/hospital/EmptyTabFallback.tsx` — feature flag off 시 fallback

**검증**
- 탭 전환해도 useEffect cleanup 안 일어남 확인
- Error Boundary 탭별 격리 단위 테스트

**리스크**: 중간 (세션 보존 패턴 + 탭 다수 마운트 성능)

---

### Commit 3 — 홈 탭 위젯 기반 (3개 상한)

**파일**
- `src/components/hospital/tabs/HomeTab.tsx` (신규)
- `src/components/hospital/widgets/TodayScheduleWidget.tsx` — P2는 placeholder (appointments 없으면 "오늘 일정 없음")
- `src/components/hospital/widgets/WaitQueueWidget.tsx` — placeholder ("곧 공개")
- `src/components/hospital/widgets/EmergencyCtaWidget.tsx` — 🚨 red CTA + 확인 모달 1단계 → 응급실 POI로 길찾기 시작
- `src/components/hospital/widgets/WidgetSlot.tsx` — slot 정의, 런타임 수 검증 (>4 warn)

**검증**
- 단위 테스트: 3개 필수 + 1개 선택 슬롯, 응급 모달 오탭 방지

**리스크**: 낮음

---

### Commit 4 — 외래 탭 MVP (예약 생성/취소)

**파일**
- `src/components/hospital/tabs/AppointmentsTab.tsx` (신규)
- `src/services/appointments.ts` (신규) — `createAppointment`, `listMyAppointments`, `cancelAppointment`, `subscribeMyAppointments`
- `src/types/appointment.ts` (신규) — `Appointment`, `AppointmentStatus`
- RTDB 경로: `/hospitals/{hid}/appointments/{apptId}` + `/hospitals/{hid}/appointments_by_patient/{uid}/{apptId}`
- 보안 규칙 확장: `database.rules.json` 해당 경로 추가

**검증**
- React Hook Form + Zod 폼 유효성
- 예약 리스트 realtime subscription
- rules 단위 테스트 추가 (`scripts/test-rules.mjs` 시나리오 추가)

**리스크**: 중간 (rules 재배포 = 3단계 배포 오케스트레이션 재필요)

---

### Commit 5 — 입원·검진 탭 스켈레톤

**파일**
- `src/components/hospital/tabs/InpatientTab.tsx` (신규 · 준비 중 UI)
- `src/components/hospital/tabs/CheckupTab.tsx` (신규 · 준비 중 UI)

**검증**
- feature flag off 시 "탭 버튼" 자체가 HospitalTabs에서 숨겨짐 확인

**리스크**: 낮음 (content 없음)

---

### Commit 6 — 안내 탭 (PatientPage 흡수)

**파일**
- `src/components/hospital/tabs/GuideTab.tsx` (신규) — 기존 `PatientPage.tsx` 내용 이관
- 기존 `PatientPage.tsx` — 그대로 유지 (레거시 `/patient` 호환)
- `src/pages/PatientPage.tsx`에 있던 지도·QR 로직을 `GuideTab`에서 import

**검증**
- 안내 탭 내부에서 QR 스캔 → 세션 시작 → 탭 전환 시 세션 유지
- 기존 `/patient` URL도 동일 작동 (regression)

**리스크**: 높음 (QR/세션/지도가 얽혀 있음, 세션 보존)

---

### Commit 7 — 더보기 탭 + 고령자 모드 토글

**파일**
- `src/components/hospital/tabs/MoreTab.tsx` (신규)
- `src/services/userPreferences.ts` (신규) — `updatePreferences` (RTDB users/{uid}/preferences)
- `src/hooks/useSeniorMode.ts` (신규) — toggle + CSS class 주입
- `src/styles/senior.css` (신규) — `.ui-senior` 에 `html { font-size: 1.2em }` 등 기본 scale
- `src/index.css` — `@import './styles/senior.css'` 또는 직접 룰 추가

**검증**
- 토글 on → root `<html>`에 `.ui-senior` class 부여
- 토글 off → class 제거
- 새로고침 후 preferences.largeUi 값으로 자동 복원
- 기존 디자인 시스템이 `.ui-senior` 하에서도 레이아웃 깨지지 않음 (스샷 검토)

**리스크**: 중간 (CSS variable/em 스케일링이 Tailwind 현재 구조와 어떻게 공존하는지 확인 필요)

---

### Commit 8 — Feature flag 탭 가시성

**파일**
- `src/hooks/useHospital.ts` — 이미 있는 `useHospitalFeature` 활용
- `src/components/hospital/HospitalTabs.tsx` — features flag 기반 NAV 필터
- `src/components/hospital/HospitalHomePage.tsx` — 현재 탭이 off 되면 `home`으로 리다이렉트

**검증**
- demo 병원에 `features.appointments=false` 직접 RTDB 쓰기 → 외래 탭 사라짐 즉시 확인
- 현재 외래 탭 보고 있다가 off 되면 홈으로 이동

**리스크**: 낮음 (기반 이미 P1에)

---

### Commit 9 — 세션·상태 보존 통합 테스트

**파일**
- `public/e2e-tab-session.html` (신규) — 탭 전환 중 QR 세션·길찾기·예약 생성 상태 유지 검증

**검증**
- 외래 탭에서 예약 폼 작성 중 → 안내 탭으로 갔다가 돌아오면 입력 유지
- 안내 탭 QR 스캔 시작 → 홈으로 이동 후 돌아오면 세션 그대로

**리스크**: 중간 (Mount all 패턴이 다른 브라우저에서 잘 작동하는지)

---

### Commit 10 — 고령자 모드 초기 스케일·접근성

**파일**
- `src/styles/senior.css` 확장 — 폰트·버튼·입력창·간격 스케일
- `src/components/hospital/widgets/*` — `.ui-senior` 하에서도 깨지지 않는 방어 CSS
- 스크린샷 리뷰 (로컬 dev)
- 키보드 네비 Tab order 확인

**검증**
- Lighthouse Accessibility 점수 (P2 완료 기준 90+)
- aria-label 주요 버튼
- prefers-reduced-motion 대응 (애니메이션 최소화 경로)

**리스크**: 중간 (WCAG 실사용 검증은 P4에 본격)

---

## 4. 데이터 모델 (v2 확장)

### 4.1 `/hospitals/{hid}/appointments/{apptId}` (신규)

```typescript
interface Appointment {
  id: string;
  hospitalId: string;
  patientUid: string;
  department: string;
  staffUid?: string;          // 의료진 지정 (옵션)
  scheduledAt: number;
  durationMin: number;
  status: 'scheduled' | 'cancelled' | 'completed';
  notes?: string;
  createdAt: number;
  updatedAt: number;
}
```

### 4.2 `/hospitals/{hid}/appointments_by_patient/{uid}/{apptId}` (index)

환자별 빠른 조회용 역인덱스. 값은 `true` 또는 `{ scheduledAt }` 메타.

### 4.3 `/users/{uid}/preferences`

P1에서 타입 예약 → P2에서 실제 사용:

```typescript
interface UserPreferences {
  largeUi?: boolean;       // ← P2에서 활성
  notificationChannels?: ('push' | 'sms' | 'email' | 'alimtalk')[];  // P3
  language?: 'ko' | 'en' | 'zh' | 'ja';   // P5
}
```

---

## 5. 보안 규칙 확장 (Commit 4)

```json
{
  "hospitals": {
    "$hospitalId": {
      "appointments": {
        "$apptId": {
          ".read": "auth != null && (auth.token.role === 'platformAdmin' || (auth.token.hospitalId === $hospitalId && (data.child('patientUid').val() === auth.uid || auth.token.role === 'staff' || auth.token.role === 'admin')))",
          ".write": "auth != null && (auth.token.role === 'platformAdmin' || (auth.token.hospitalId === $hospitalId && (newData.child('patientUid').val() === auth.uid || auth.token.role === 'staff' || auth.token.role === 'admin')))",
          "patientUid": { ".validate": "newData.isString()" },
          "hospitalId":  { ".validate": "newData.val() === $hospitalId" },
          "status":      { ".validate": "newData.val() === 'scheduled' || newData.val() === 'cancelled' || newData.val() === 'completed'" }
        }
      },
      "appointments_by_patient": {
        "$uid": {
          ".read":  "auth != null && ($uid === auth.uid || auth.token.role === 'platformAdmin' || (auth.token.hospitalId === $hospitalId && (auth.token.role === 'staff' || auth.token.role === 'admin')))",
          ".write": "auth != null && ($uid === auth.uid || auth.token.role === 'platformAdmin' || (auth.token.hospitalId === $hospitalId && (auth.token.role === 'staff' || auth.token.role === 'admin')))"
        }
      }
    }
  }
}
```

패턴은 P1 `visit_plans`와 동일 — claim hospitalId와 path $hospitalId 일치 선행.

---

## 6. 테스트 전략

### 단위 테스트 (vitest)
- `useTabState` URL sync
- `HospitalTabs` feature flag 필터
- `HomeTab` 위젯 수 상한
- `useSeniorMode` toggle + preferences persist
- `appointments` service CRUD

### E2E 페이지
- `public/e2e-appointments.html` — 예약 생성/취소/교차 병원 차단
- `public/e2e-tab-session.html` — 탭 전환 중 상태 보존

### Emulator 규칙 테스트
- `scripts/test-rules.mjs` 확장 — appointments 시나리오 5개 추가

### 수동 QA
- [ ] `/h/demo/patient/home?tab=appointments` → 외래 탭 진입
- [ ] 새로고침 시 탭 유지
- [ ] features.appointments=false 시 탭 숨김 + redirect
- [ ] 고령자 모드 토글 → root class 주입 → 새로고침 후 유지
- [ ] QR 스캔 중 다른 탭 이동 → 돌아와도 세션 유지
- [ ] 레거시 `/patient` 접속 → 기존 UX 그대로

---

## 7. 리스크 레지스터

| 리스크 | 확률 | 영향 | 완화 |
|---|---|---|---|
| 탭 Mount all로 메모리 폭증 | 중 | 중 | 무거운 탭(map)은 lazy hydrate + `React.Suspense` |
| 고령자 모드 CSS가 Tailwind token과 충돌 | 중 | 중 | `em` 기반 + 변수 래핑. 스샷 리뷰 필수 |
| 예약 규칙 오배포로 기존 기능 영향 | 낮 | 높 | P1과 동일 게이트: Emulator test → dry data seed → deploy |
| QR 세션이 탭 전환 시 끊김 | 중 | 높 | "안내 탭"은 항상 mount, visibility 토글만 |
| 응급 버튼 오탭 119 발신 | 낮 | 크리티컬 | 확인 모달 1단계 필수, tel:119 전 클릭 두 번 요구 |
| URL `?tab=` 상태가 deep link 깨뜨림 | 낮 | 중 | 기본값 'home' fallback, invalid 시 redirect |

---

## 8. 배포 전략 (P1 순서 준수)

1. **Commit 1-3** (탭 시스템 + 홈 위젯) — 기존 rules 변경 없음, hosting만 배포
2. **Commit 4** (외래 탭 MVP) — rules 확장 → Emulator 11+5개 시나리오 통과 필수 → rules 배포 → 호스팅 배포
3. **Commit 5-8** (나머지 탭/더보기/flag) — hosting 만 배포
4. **Commit 9-10** (세션·접근성 최종) — 전체 회귀 확인 후 merge

---

## 9. 완료 기준

- [ ] 6개 탭 렌더 + URL 영속
- [ ] 홈 위젯 정확히 3개 (+1 선택)
- [ ] 외래 탭 예약 생성/취소 성공
- [ ] 안내 탭에 기존 지도/QR 기능 100% 흡수 + 레거시 `/patient` 회귀 없음
- [ ] 더보기 탭 고령자 모드 토글 → 서버 persist → 새로고침 유지
- [ ] features flag 기반 탭 동적 on/off
- [ ] 탭 전환 시 세션 유지
- [ ] `npx tsc --noEmit` + `npm run build` 통과
- [ ] 단위 테스트 20+개 신규 통과
- [ ] Emulator rules 테스트 16+개 통과
- [ ] E2E 페이지 수동 검증 통과
- [ ] PR 생성 → `mediway/develop` 병합

---

## 10. 일정 (Day-level)

| Day | 작업 |
|---|---|
| 1-2 | Commit 1-2 (탭 시스템 + 셸) |
| 3 | Commit 3 (홈 탭 위젯 3개) |
| 4-5 | Commit 4 (외래 MVP + rules) |
| 6 | Commit 5 (입원/검진 스켈레톤) |
| 7-8 | Commit 6 (안내 탭 PatientPage 흡수) — ★ 집중 |
| 9 | Commit 7 (더보기 + 고령자 모드 토글) |
| 10 | Commit 8 (feature flag) |
| 11 | Commit 9 (세션 보존 통합 테스트) |
| 12 | Commit 10 (접근성·스케일) |
| 13 | 수동 QA + rules 배포 |
| 14 | 호스팅 배포 + PR |

---

## 11. v2 차분 체크리스트 (구현 전 재확인)

- [ ] 홈 위젯 상한 3개 (+1) — v1 `PlusUltra#2.md §4.3`이 "4-5개 자유"라고 하지만 v2가 오버라이드
- [ ] 고령자 모드 토글 **P2에서** 시작 — v1은 P4 전용
- [ ] 응급실 CTA는 홈 위젯 중 1개로 — v1 P4 F10을 P2로 당김
- [ ] MyChart 반면교사: 추가 위젯 욕구는 "더보기"로
- [ ] `/hospitals/{hid}/appointments` 새 subtree는 P1 패턴 그대로 (hospitalId 선행)

---

## 12. 참조 문서

- `GUIDE_v2/plusultra_v2.md` §"Phase 2" (실행 기준)
- `GUIDE_v2/PlusUltra#2.md` (v1 상세 가이드 + 상단 v2 블록)
- `mediway/docs/PLAN_P1.md` (완료, 구조 레퍼런스)
- P1 PR #1 (https://github.com/HorangEe02/Project_yeong/pull/1)

---

_작성일: 2026-04-23_
