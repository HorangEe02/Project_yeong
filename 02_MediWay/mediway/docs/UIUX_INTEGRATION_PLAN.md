# UIUX 시안 통합 적용 계획

> **상태**: 브레인스토밍·계획 (2026-04-23)
> **목적**: `uiux/web_page_uiux/` + `uiux/mobile_uiux/` 폴더 내 디자인 시안을 현재 구현(P1-P4)과 통합하여 일관된 시각 언어 확립.
> **타깃 착수**: PR #4 merge 이후 별도 phase (**P4.U** — UIUX Alignment)
> **참조**: 시안 HTML/PNG는 `/Volumes/…/05_mediway/uiux/`

---

## 1. 배경

- 사용자가 PlusUltra 업데이트용 UI 시안을 `uiux/web_page_uiux/`(16개)와 `uiux/mobile_uiux/`(17개)에 배포
- 각 폴더는 `code.html` + `screen.png` 쌍 (총 33쌍 이상)
- 현재 코드는 기능 완결되어 있으나, 시안이 제시하는 **시각적 톤·레이아웃·Senior Mode 표현**과 편차 존재
- 코드·시안 모두 존재하는 지금이 **일관성 확립의 마지노선** — 이후 phase 추가 시 기준 없이 디자인이 분기할 위험

---

## 2. 확인된 시안 (중점 7개)

시간 제약상 PlusUltra SaaS 계열 + 환자 메인 + 선택 페이지를 먼저 분석했다. 나머지 시안은 §10에 후속 검토 항목으로 명시.

| # | 경로 | 유형 | 대응 현재 컴포넌트 |
|---|---|---|---|
| 1 | `web_page_uiux/mediway_plus_ultra_saas_1/` | 표준 환자 데스크톱 대시보드 | `HomeTab` + `HospitalHomePage` (데스크톱 배치) |
| 2 | `web_page_uiux/mediway_plus_ultra_saas_2/` | **Senior Mode 홈 (데스크톱)** | `SeniorHome` |
| 3 | `web_page_uiux/mediway_plus_ultra_saas_3/` | Outpatient Hub (사이드바 + 캘린더) | `AppointmentsTab` + 의료진용 재활용 |
| 4 | `mobile_uiux/mediway_plus_ultra_saas_1/` | 환자 모바일 홈 | `HomeTab` 모바일 |
| 5 | `mobile_uiux/mediway_plus_ultra_saas_2/` | **Senior Mode 모바일 홈** | `SeniorHome` 모바일 |
| 6 | `mobile_uiux/mediway_plus_ultra_saas_3/` | 의료진 Appointments 콘솔 | `StaffQueuePage` (도입 가능), `AppointmentsTab` 일반 |
| 7 | `web_page_uiux/mediway_user_main/` | 병원 선택 허브 | `SelectHospitalPage` |

---

## 3. 시안 요약 관찰

### 시안 1 — Web 표준 환자 대시보드
- **레이아웃**: 상단 nav bar + 좌측 Today's Schedule (1.5컬럼) + 우측 **Real-time Queue 블록 카드** (0.5컬럼)
- **핵심 요소**:
  - 큰 개인 인사말 `"Good morning, Sarah"` (blue 강조 이름)
  - Info 배너 ("New Outpatient Registration Process" → CTA)
  - Real-time Queue: **파란 배경**, 큰 숫자 `3 PEOPLE AHEAD`, 예상 대기 `~12 mins`
  - 하단 **Quick Actions 4개**: Appt · Wayfinding · Queue · Emergency (아이콘 원형 + 라벨)
  - 우측 하단 Recent Results (Blood Panel, Chest X-Ray)

### 시안 2 — Web Senior Mode 홈
- **Senior Mode 뱃지** 상단 로고 옆 명시
- "Hello, Maria" 큰 인사 + "What would you like to do today?" + NEXT VISIT 소카드
- **4 큰 정사각형 타일 그리드 (2×2)**:
  - Book a Visit / Find My Way / My Turn (뱃지 3) / Doctor at Home
- 하단 **풀폭 빨간 EMERGENCY HELP** CTA ("Call staff immediately")
- 정보 표시 0, **액션 중심 UX**

### 시안 3 — Web Outpatient Hub
- 좌측 사이드바 (Today's Schedule / Real-time Queue / Patient Records / Analytics / Emergency Entry)
- 중앙 Weekly Schedule 캘린더 (요일 column에 appointment chip)
- 하단 Upcoming Appointments 카드 리스트
- 우측 New Appointment 폼 (Department select, Preferred Date, Time Preference pill)

### 시안 4 — Mobile 환자 홈
- 헤더 "MediWay Sanctuary" + 병원명
- pill 형 탭 바 (Home/Outpatient/Inpatient)
- Real-time Queue 대형 카드
- Today's Schedule 리스트
- Quick Actions 세로 리스트 (Book Appointment, Wayfinding)
- 빨간 Emergency Info 카드
- **하단 탭 바** (Home · Schedule · Alerts · Profile)

### 시안 5 — Mobile Senior Mode
- "Good Morning, Robert. How can we help you today?"
- **2×2 큰 타일**: Book a Visit / Find My Way / My Turn / Doctor at Home
- Upcoming Appointment 작은 카드
- **큰 빨간 EMERGENCY HELP 버튼**

### 시안 6 — Mobile 의료진 Appointments
- "Appointments" + "Manage your upcoming schedule and patient flow"
- + New Appointment primary CTA
- Weekly Schedule (요일 column pill)
- Upcoming Today 리스트 (시간·환자명·의사·부서)
- 하단 탭: Queue · Schedule · Seniors · Data

### 시안 7 — Web 병원 선택 허브
- "MediWay Healthcare" 큰 제목 + "Your digital sanctuary for comprehensive medical care"
- Select Hospital 카드 (검색 + 4개 병원 리스트)
- 선택 후 "Enter Portal" primary CTA

---

## 4. 현재 구현 vs 시안 Gap 분석

### 4.1 HomeTab / StandardHome (환자 데스크톱)
| 요소 | 현재 | 시안 1 |
|---|---|---|
| 레이아웃 | 1컬럼 `WidgetSlot` 2-3 row 자동 | **2컬럼** (좌 1.5 일정 + 우 0.5 Queue) |
| 개인 인사 | 없음 | "Good morning, {firstName}" blue 강조 |
| Real-time Queue 강조 | 단일 위젯, tone 기본 | **파란 배경** 카드, 큰 숫자 |
| Quick Actions | 없음 (탭으로 대체) | **원형 아이콘 4개** (하단 row) |
| Recent Results | 없음 | 우측 하단 리스트 |
| Info 배너 | 없음 | 상단 배너 (CTA 포함) |

### 4.2 SeniorHome (핵심 변동 포인트)
| 요소 | 현재 (C2) | 시안 2/5 |
|---|---|---|
| 접근 방식 | **정보 표시 중심** (위젯 3개 축소) | **액션 중심** (4 큰 타일) |
| 타일 구성 | Today Schedule·WaitQueue·Emergency 위젯 | Book a Visit / Find My Way / **My Turn** / Doctor at Home |
| 인사 | "오늘도 건강하세요" 한줄 | "Hello, {name}" + 한줄 질문 + NEXT VISIT 서브 |
| Senior Mode 뱃지 | CSS class 주입만 | **상단 UI 뱃지 명시** |
| Emergency | 위젯 형태 | 하단 **풀폭 빨간 CTA** |
| 위젯 수 | 3개 + Greeting | 4 타일 + 소 인사 + 하단 CTA |

**핵심 변경**: SeniorHome을 **"오늘 해야 할 일"** 중심 dashboard에서 **"한 번 탭으로 원하는 흐름 진입"** 중심 런처로 재설계.

### 4.3 AppointmentsTab (외래)
| 요소 | 현재 | 시안 3 |
|---|---|---|
| 레이아웃 | 1컬럼 리스트 + 새 예약 폼 | Weekly calendar + 우측 New Appointment 폼 |
| 캘린더 | 없음 (datetime-local input만) | 주간 표 (요일 × 시간대) |
| 예약 카드 | 간결 row | 좌측 색 bar + 카드형 |

### 4.4 StaffQueuePage (의료진)
| 요소 | 현재 (C4) | 시안 6 |
|---|---|---|
| 페이지 제목 | "대기 환자 호출 콘솔" | "Appointments" hub |
| 주간 스케줄 | 없음 | 요일 chip |
| 환자 리스트 | 현재 대기열 중심 | Upcoming Today 시간순 리스트 |
| 하단 탭 | 없음 (단일 페이지) | Queue / Schedule / Seniors / Data |

### 4.5 SelectHospitalPage (병원 선택)
- 시안과 구조는 유사할 것으로 추정 (P1에서 구현). 실 스크린샷 비교 필요.
- 시안 특징: 중앙 카드 + 검색 + "Enter Portal" primary CTA + "Need help finding your hospital?" 하단 링크

---

## 5. 디자인 토큰 관찰 (시안 전반)

| 영역 | 관찰 값 | 현재 Tailwind 토큰 대응 |
|---|---|---|
| Primary 색 | 짙은 파랑 `#0B4EBA` 또는 `#0A5ECF` 계열 | `primary` — 현재 `#004e9f` (근접) |
| Queue 강조 배경 | 딥 블루 그라디언트 | 신규 `primary-dark` 또는 유틸리티 |
| 카드 | 흰 배경 + `rounded-xl` + 1px `outline-variant` 테두리 + soft ambient shadow | 현재 구현과 동일 ✅ |
| 텍스트 주 | near-black `#1a1a1a` | `on-surface` ✅ |
| 텍스트 보조 | gray-600 | `on-surface-variant` ✅ |
| 빨강 (응급) | saturated red | `error` ✅ |
| Senior 뱃지 | light blue pill (`bg-primary/10 text-primary`) | 신규 추가 |
| Quick Action 아이콘 원 | `bg-primary/10` 원 + primary 아이콘 | 신규 패턴 |
| 간격 | `gap-6` (24px) 기본, senior `gap-8` | P4 C1에서 이미 senior 확대 ✅ |

**결론**: Tailwind 토큰은 대부분 호환. `primary` 색만 `#004e9f` → `#0A5ECF` 근처로 톤 조정 검토.

---

## 6. 적용 우선순위 매트릭스

| 우선도 | 컴포넌트 | 이유 |
|---|---|---|
| 🟢 **High** | SeniorHome (4 타일 재설계) | 사용자 체감 변화 큼, v2 MOAT 관련, 시안 명확 |
| 🟢 **High** | HomeTab 데스크톱 2컬럼 + Quick Actions | 데스크톱 사용자 첫인상, 현재는 밋밋 |
| 🟡 **Med** | Real-time Queue 카드 스타일 (딥블루) | WaitQueueWidget 강조로 P3 기능 부각 |
| 🟡 **Med** | 개인 인사말 + Info 배너 | 친근감, 마케팅 채널 |
| 🟡 **Med** | Senior Mode 뱃지 UI | 모드 인지성 상승 |
| 🟠 **Low** | AppointmentsTab 주간 캘린더 | 기능 등가이나 UX 개선. 구현 부담 |
| 🟠 **Low** | SelectHospitalPage 시안 정렬 | 이미 기능 완성, 마이너 polish |
| 🟠 **Low** | StaffQueuePage 탭 네비 | 구조 변경 큼, staff UX는 별 논의 필요 |

---

## 7. 컴포넌트별 세부 적용 계획

### 7.1 🟢 SeniorHome 4 타일 재설계 (U1)

**현재**: `TodayScheduleWidget · WaitQueueWidget · EmergencyCtaWidget` + Greeting
**목표**: 시안 2/5의 4 타일 런처 + NEXT VISIT 서브 카드 + 하단 빨간 CTA

**새 구조**:
```tsx
<main>
  <SeniorHeader />                     {/* 로고 + "Senior Mode" 뱃지 */}
  <SeniorGreetingCard />                {/* 큰 Hello + 질문 + NEXT VISIT 서브 */}
  <SeniorTileGrid>                      {/* 2×2 타일 */}
    <SeniorTile icon="calendar" label="병원 예약하기" to="?tab=appointments" />
    <SeniorTile icon="map" label="길 안내" to="?tab=guide" />
    <SeniorTile icon="ticket" label="내 순번 보기" badge={queueNumber} to="?tab=home&focus=queue" />
    <SeniorTile icon="video" label="집에서 진료" to={telemedUrl} disabled={!hospital.telemed} />
  </SeniorTileGrid>
  <SeniorEmergencyCTA />                {/* 풀폭 빨간 버튼 */}
</main>
```

**결정 필요**:
- "Doctor at Home" (비대면 진료) 타일 — 현재 MediWay에 비대면 기능 없음 → **P5 또는 placeholder** 처리 필요
- My Turn 뱃지는 실시간 순번 (subscribeMyEntries 재활용)

**파일**:
- `src/components/hospital/tabs/SeniorHome.tsx` (개편, +100 lines 대체)
- `src/components/hospital/senior/SeniorTile.tsx` (신규)
- `src/components/hospital/senior/SeniorEmergencyCTA.tsx` (신규, EmergencyCtaWidget 래퍼)
- `src/components/hospital/senior/SeniorGreetingCard.tsx` (신규, 기존 SeniorGreeting 확장)
- `src/i18n/senior.json` 보강 ("Doctor at Home" 문구 등)
- 단위 테스트 업데이트

**리스크**: My Turn 뱃지 배지가 실제 큐 데이터에 묶여야 함 → `useMyWaitQueue` 훅으로 분리 권장

### 7.2 🟢 HomeTab 데스크톱 2컬럼 + Quick Actions (U2)

**현재**: 1컬럼 `WidgetSlot` 3-4개
**목표**: lg 이상에서 2컬럼 + Quick Actions 4개 + Recent Results (Stub)

**새 구조** (standard 모드):
```tsx
<main>
  <HomeGreeting name={firstName} />           {/* "Good morning" */}
  <HomeInfoBanner />                          {/* 옵션, 공지 있을 때만 */}
  <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
    <section>
      <TodayScheduleWidget />
      {aiTriage && <SymptomTriageWidget />}
    </section>
    <aside>
      <WaitQueueWidget />                     {/* 딥블루 강조 스킨 */}
      <RecentResultsStub />                   {/* P5 결과 공개 전 placeholder */}
    </aside>
  </div>
  <QuickActionRow />                          {/* 4 원형 아이콘 */}
</main>
```

**파일**:
- `src/components/hospital/tabs/HomeTab.tsx` (분기 유지, Standard 내부만 재구성)
- `src/components/hospital/widgets/WaitQueueWidget.tsx` (variant prop 추가 — "prominent" 스타일)
- `src/components/hospital/home/HomeGreeting.tsx` (신규)
- `src/components/hospital/home/QuickActionRow.tsx` (신규)
- `src/components/hospital/home/RecentResultsStub.tsx` (신규, P5 진입 전 stub)

**리스크**: `WidgetSlot`의 MAX=4 제약과 충돌 → Standard 모드는 WidgetSlot 대신 명시적 grid 사용

### 7.3 🟡 Real-time Queue 강조 스킨 (U3)

WaitQueueWidget에 `variant='prominent'` 추가 → 딥블루 배경 + 숫자 큰 표기 + Est. Wait Time.

현재 있는 `status === 'called'` 강조는 유지, variant는 시각적 톤 차이.

### 7.4 🟡 개인 인사말 + Info 배너 (U4)

- `HomeGreeting`에 UserProfile displayName (또는 email prefix) 사용
- 시간대별 인사 ("Good morning" / "Good afternoon" / "Good evening")
- Info 배너는 `/hospitals/{hid}/announcements` 최신 1건 활용 (이미 P2 구현됨)

### 7.5 🟡 Senior Mode 뱃지 UI (U5)

`HospitalHomePage` 상단 헤더(존재하지 않음? 확인 필요) 또는 `SeniorHeader`에 pill 형 뱃지.
```tsx
{senior && (
  <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
    Senior Mode
  </span>
)}
```

### 7.6 🟠 AppointmentsTab 주간 캘린더 (U6)

별도 phase. 현재 기능 등가이므로 긴급도 낮음.

### 7.7 🟠 SelectHospitalPage (U7)

시안과 현재 코드 교차 확인 후 마이너 polish.

### 7.8 🟠 StaffQueuePage 구조 재검토 (U8)

시안 6은 **일반 appointments hub** 느낌. StaffQueuePage와 직접 매핑 불확실. 별도 의료진 UX 논의 필요.

---

## 8. 작업 순서 제안 — P4.U 브랜치

**전제**: 현재 P4 PR #4가 먼저 merge 되어야 함.

**브랜치**: `mediway/plusultra/p4.u` (develop에서 분기)

**커밋 단위 제안**:
| # | 커밋 | 우선 |
|---|---|---|
| U1 | SeniorHome 4 타일 재설계 + SeniorTile 컴포넌트 | 🟢 |
| U2 | HomeTab 데스크톱 2컬럼 + HomeGreeting + Info 배너 | 🟢 |
| U3 | WaitQueueWidget `variant='prominent'` 스킨 | 🟡 |
| U4 | QuickActionRow + RecentResultsStub | 🟡 |
| U5 | Senior Mode 뱃지 + 모바일 레이아웃 회귀 | 🟡 |
| U6 | AppointmentsTab 주간 캘린더 | 🟠 |
| U7 | SelectHospitalPage polish + 로고·카피 정렬 | 🟠 |
| U8 | StaffQueuePage UX 재검토 (ADR 논의) | 🟠 |
| U9 | 통합 QA + preview channel | — |

**소요**: 1-2주 (U1-U5 1주 집중, U6-U8은 선택)

---

## 9. 리스크 & 주의

| 리스크 | 완화 |
|---|---|
| 시안 색·폰트와 Tailwind 토큰 미스매치 | `tailwind.config.js`의 `primary` 값 조정 후 시각 회귀 스크린샷 검토 |
| SeniorHome 액션 중심 전환 후 기존 정보 표시 기대가 사라짐 | 사용자 연구 3명 직접 피드백 필수 (PLAN_P4 §10) |
| "Doctor at Home" 타일은 기능 부재 | **P5 telemed 이전엔 disabled + "곧 공개" 라벨** |
| WidgetSlot MAX=4 원칙 위배 가능 | Standard 모드는 WidgetSlot 대신 명시적 grid 사용 (이미 방향성 결정됨) |
| 기존 테스트 깨짐 (SeniorHome 구조 변경) | 테스트 함께 업데이트 — 아이콘 aria-label 기반 선택자 |
| 모바일/데스크톱 레이아웃 분기 복잡도 | Tailwind breakpoint `lg:` 책임지게 하고 별도 컴포넌트 분기는 최소화 |

---

## 10. 미확인 시안 (후속 검토)

아래 시안들은 이번 브레인스토밍에서 미분석 — P4.U 착수 전 또는 중간에 추가 리뷰 필요.

### web_page_uiux
- `mediway`, `mediway_1`, `mediway_2` — 기본 번호 시안
- `mediway_3d_1`, `mediway_3d_2` — 3D 지도 (P5 지도 확장 시 참고)
- `mediway_admin` — 관리자 콘솔 (AdminDashboardPage 등과 대조)
- `mediway_clinical` — 임상/의료진 (StaffQueuePage 재설계 논의)
- `mediway_select` — 별도 병원 선택 시안 (mediway_user_main과 별도인지 확인)
- `mediway_staff_v2_1`, `mediway_staff_v2_2` — 의료진 v2 (StaffPage / StaffQueuePage)
- `mediway_v2` — v2 기본

### mobile_uiux
- `mediway`, `mediway_1~4` — 기본 시리즈 (`mediway_4`는 Phase 4 관련 여지)
- `mediway_3d_1/2` — 3D 지도 모바일
- `mediway_admin`, `mediway_clinical`, `mediway_select`
- `mediway_qr` — QR 스캐너 (PatientPage 내부 QR UX 대조)
- `mediway_staff_1/2` — 모바일 의료진

---

## 11. 공통 디자인 시스템 초안 (P4.U 착수 시 확정)

### 11.1 색상 토큰 조정 (tailwind.config.js)
- `primary`: `#004e9f` → `#0B4EBA` (시안 더 짙은 파랑 근사)
- `primary-dark` 신규: `#083D94` (Queue 카드 그라디언트 배경용)
- `primary-container`: `#E6EFFF` (senior 뱃지·Quick Action 배경)

### 11.2 타이포 스케일
- `text-display` (신규): 2.25rem / line-height 1.2 (인사말용)
- 나머지 Tailwind 기본 유지

### 11.3 공통 컴포넌트 신규
- `SeniorTile` — 큰 아이콘·라벨·부설명·badge·disabled 지원
- `QuickAction` — 원형 아이콘 + 라벨 (홈 하단)
- `HomeGreeting` — 시간대·이름 기반 인사
- `InfoBanner` — 공지·배너

---

## 12. 다음 결정 포인트

1. **시안 색(`#0B4EBA` 계열) vs 현재(`#004e9f`) 채택 여부** — 사용자 승인 필요
2. **"Doctor at Home" 타일을 Senior에 포함할지** — 비대면은 v2 **Drop**이므로 대체 타일 후보 결정 필요 (예: "가족 연락", "검사 결과")
3. **P4.U 착수 타이밍** — P4 PR #4 merge 후 즉시 vs P3 Track 2 먼저
4. **미확인 시안 검토 범위** — 33개 전부 vs 핵심만

---

## 13. 결정 사항 (2026-04-23 사용자 확정)

§12의 4가지 결정 포인트에 대해 권장안을 그대로 채택.

| # | 결정 | 이행 |
|---|---|---|
| ① | **primary 색 `#0B4EBA` 채택** | tailwind.config 기본값 변경 + RTDB `hospitals/demo/profile/themeColor` 동기화 |
| ② | **"가족 연락" 대체 타일 (placeholder)** | P4.U U1에서 disabled "곧 공개" 라벨, P4 가족 대리(C6-C10) merge 후 활성화 |
| ③ | **P4.U 즉시 착수** | P4 PR #4 merge 직후 `mediway/plusultra/p4.u` 분기 |
| ④ | **핵심 시안 5개 추가 분석** | §14 결과 (clinical 1건 read 실패, 보류) |

---

## 14. 추가 분석된 시안 (2026-04-23)

§10 후속 검토 항목 중 5개를 분석. 결과를 P4.U 작업 단위(U7~U12)로 반영.

### 14.1 web `mediway_staff_v2_1` — 의료진 동선 전송 콘솔 ("Patient Flow")
- 좌측 환자 식별(QR 카메라 + 수동 토큰), 우측 동선 템플릿 + 커스텀 경로 빌더 + "환자 기기로 동선 전송하기" primary CTA
- 하단 식별된 환자 카드(이름·생년월일)
- **현재 매핑**: `StaffPage` + `StaffDashboard`
- **U8 재정의**: P3 C4 `StaffQueuePage`와 결합 — 환자 식별 후 동선 + 호출 통합 콘솔

### 14.2 web `mediway_staff_v2_2` — 의료진 종합 대시보드
- 상단 KPI 3카드(PENDING/IN PROGRESS/COMPLETED) + 오늘 방문자 카드
- 좌측 실시간 환자 대기·동선 테이블 + 진행률 bar
- 우측 시스템 로그(검사 결과 자동 연동·예약 알림·로그인·보안 업데이트)
- **현재 매핑**: 신규 `StaffOverviewPage` (또는 `/h/:slug/staff` 진입점 재구성)
- **U12 신규 제안**: 의료진 메인 진입을 **Overview → Patient Flow → Queue** 3단계로 재배열

### 14.3 mobile `mediway_qr` — 환자 QR 디스플레이
- 환자 정보 카드 + 큰 QR 코드 + "이 QR 코드를 간호사에게 보여주세요"
- 보안 안내(3분 갱신·밝기 권장) + "진료실 위치 확인하기" CTA
- 하단 탭(홈·가이드·편의시설·내 건강)
- **현재 매핑**: `PatientPage` QR 디스플레이 부분
- **U9 신규**: QR 화면을 **풀스크린 모달 또는 별도 라우트**로 분리 + 보안 안내 표준화

### 14.4 mobile `mediway_4` — 모바일 편의시설/길안내
- 검색 바 + 카테고리 4 chip(CAFE·ATM·DINING·PHARMACY)
- Parking Location 카드(Level 02 Zone B-14 + Get Directions CTA)
- Current Location + 지도 + Nearby Services 리스트
- 하단 탭(HOME·PULSE·GUIDE·FACILITY)
- **현재 매핑**: `GuideTab` 모바일 변형 + P3 C12 주차 어댑터 시각화
- **U10 신규**: GuideTab에 **카테고리 chip 필터** + **주차 위치 카드**(P3 parking adapter 호출 결과 표시)

### 14.5 web `mediway_select` — 표준 환자 홈 변형 (Proxy Payment 포함)
- 폴더명은 select지만 실제 내용은 **표준 환자 데스크톱 홈의 또 다른 변형**
- "Good morning, {name}" + Today's Schedule + 안내문 + Quick Actions 4(Find a Doctor·Book Appt·Timetable·Parking Info)
- **Proxy Payment 강조 카드**(파란 배경) "Pay bills for a family member"
- **U11 신규**: Proxy Payment 카드는 P3 Track 2 C9(대리결제) + P4 가족 대리(MOAT) 결합 영역으로 placeholder 구현 후 두 PR merge 시점에 활성화

### 14.6 미확인 잔여
- `web_page_uiux/mediway_clinical/screen.png` — 파일 read 반복 실패(네이밍 또는 권한 이슈). P4.U 착수 시 macOS Finder 등으로 직접 검토 후 추가 반영.

---

## 15. 색 마이그레이션 작업 노트 (결정 ① 이행)

### 15.1 변경 대상
- `tailwind.config.js`의 `theme.extend.colors.primary`
- `src/index.css`의 `:root { --color-primary: ... }` 기본값
- RTDB `/hospital_index/demo/themeColor`(있다면) + `/hospitals/demo/profile/themeColor`

### 15.2 단계
1. `tailwind.config.js` `primary: "#004e9f"` → `"#0B4EBA"`
2. `index.css`의 `--color-primary` 기본값 동시 변경
3. `firebase database:set` 또는 Console로 demo 병원 themeColor 업데이트
4. 빌드 후 시각 회귀 스크린샷(홈·외래·응급 CTA 등 primary 사용처 5곳)
5. 화이트라벨 다른 병원(smch)은 `themeColor` 그대로 유지 — 검증 필요

### 15.3 리스크
- primary와 함께 파생색(`primary-container`, `primary-light`)도 톤 매칭 필요. 현재 0066/3b82 패턴에서 한 톤 다 어둡게 조정.
- 화이트라벨 시스템이 `applyHospitalTheme()`으로 dynamic override하므로 default 변경은 첫 paint와 데모 환경에만 영향.

---

## 16. 참조

- 시안 경로: `/Volumes/Corsair EX300U Media/00_work_out/01_complete/me/05_mediway/uiux/`
- 현재 코드: `mediway/plusultra/p4 @ 50e35d6`
- PR #4 대기: https://github.com/HorangEe02/Project_yeong/pull/4
- 선행 문서: `docs/PLAN_P1.md`, `PLAN_P2.md`, `PLAN_P3.md`, `PLAN_P4.md`

---

_작성일: 2026-04-23 · 분석 시안 7개 + 후속 검토 대기 26개_
