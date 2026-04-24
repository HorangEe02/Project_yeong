# PlusUltra #2 — 대시보드 셸 + 상단 탭 상세 구현 가이드

> **Phase 2 기능 설명서 + 구현 가이드라인**
> 범위: 병원 메인 대시보드 구조·상단 탭 네비게이션·홈/외래/안내/더보기 기본 기능·기존 PatientPage의 안내 탭 흡수
> 예상 기간: 2~3주 (1인 풀타임, UIUX 포함 ≈ 15일)
> 선행 요건: **Phase 1 완료** — HospitalContext·라우팅·테마 주입·인증 claim이 정상 작동해야 함

---

## 목차

- [起 — 왜 지금 대시보드인가](#起--왜-지금-대시보드인가)
- [承 — 설계 원칙과 기술 선택](#承--설계-원칙과-기술-선택)
- [轉 — 세부 구현 설계](#轉--세부-구현-설계)
  - [1. 탭 구조 및 노출 조건](#1-탭-구조-및-노출-조건)
  - [2. 라우팅과 URL 상태](#2-라우팅과-url-상태)
  - [3. 탭 네비게이션 UI](#3-탭-네비게이션-ui)
  - [4. 홈 탭 (대시보드)](#4-홈-탭-대시보드)
  - [5. 외래 탭 (MVP)](#5-외래-탭-mvp)
  - [6. 안내 탭 (기존 PatientPage 흡수)](#6-안내-탭-기존-patientpage-흡수)
  - [7. 더보기 탭 (스켈레톤)](#7-더보기-탭-스켈레톤)
  - [8. 세션·상태 보존 전략](#8-세션상태-보존-전략)
  - [9. 데이터 스키마 확장](#9-데이터-스키마-확장)
  - [10. 보안 규칙 확장](#10-보안-규칙-확장)
- [結 — 완료 기준·검증 전략·Next](#結--완료-기준검증-전략next)
- [UIUX 가이드라인](#uiux-가이드라인)
- [부록](#부록)

---

## 📌 v2 업데이트 (2026-04-22)

> **이 파일은 PlusUltra v1 상세 가이드입니다.** v2 기준 문서 `GUIDE_v2/plusultra_v2.md` §Phase 2가 최종 실행 기준이며, 충돌 시 **v2가 우선**합니다.

### Phase 2 v2 조정사항

| # | 조정 | v1 대비 | 영향 섹션 |
|---|---|---|---|
| 1 | 🔻 **홈 탭 위젯 최대 3개 (+1 선택)** | v1은 4-5개 자유 구성 | §4. 홈 탭 (대시보드) — 위젯 설계 반드시 축소 |
| 2 | 🆕 **고령자 모드 토글 인프라를 P2에서 시작** | v1은 P4 전용 | §7. 더보기 탭 — "고령자 모드 토글" 스켈레톤 필수 포함 / CSS custom property + `.ui-senior` root class 인프라를 P2부터 구축 |
| 3 | 🔻 **홈 기본 위젯 3개 고정**: 오늘 일정 · 대기 순번 · 응급실 CTA | v1은 자유 선택 | §4.3 위젯 목록 재설계 |
| 4 | 🔸 **간단 모드를 기본값으로** | v1 미언급 | 모든 신규 컴포넌트는 `.ui-senior` 클래스 하에서도 레이아웃이 깨지지 않도록 설계 |
| 5 | 🔸 **응급실 CTA를 홈 고정** | v1의 P4 F10이 P2 홈 위젯에서 태어남 | §4 위젯 1개를 "응급 바로가기"로 확보 |

### MyChart 반면교사

v1도 MyChart의 "기능 과다" 불만을 인용하나, 위젯 수 상한을 지정하지 않음. **v2는 3개 상한을 명시적 규칙**으로 못박아 구조적으로 회피.

### 적용 원칙

- 탭 구조(6탭) · URL 영속 · 세션 보존 · Error Boundary 전략: **v1 원안 준수**
- 홈 위젯 수·고령자 모드 토글 인프라: **v2 기준 반영**
- 의심 시 `GUIDE_v2/plusultra_v2.md` §"Phase 2" 및 §"부록 D. v1→v2 Diff 체크리스트" 확인

---

## 起 — 왜 지금 대시보드인가

### Phase 1의 한계
P1이 끝난 시점에 MediWay는 **"여러 병원을 지원하는 QR 길찾기 앱"**이다. 환자가 로그인하면 사실상 지도·QR만 보인다. 경쟁 앱들(삼성서울병원·똑닥·MyChart)은 이미 **"환자 포털"**로 진화했다 — 일정·예약·결과·결제·알림이 한 홈 화면에 모여 있다. 현재 상태로는 **"병원 앱"이라 부르기에 부족**하다.

### 시장 기대치
- 삼성서울병원앱: 일정 알림·접수·대기·위치·결제·서류 발급 — **만족도 1위**
- 똑닥: 실시간 대기 순번이 핵심 사용자 후킹
- MyChart: "너무 많은 기능" 이라는 불만 = 역설적으로 기능 풍부
- 사용자는 앱을 열면 **"오늘 나에게 해당되는 것"**이 1초 안에 보이길 기대

### Phase 2의 미션
단순 기능 추가가 아니라 **"앱 정보 아키텍처의 뼈대"** 확립:
1. **탭 구조**로 기능 영역 분리 — 나중에 수십 개 기능이 추가되어도 구조가 깨지지 않아야 함
2. **홈 대시보드**로 개인화 표면 제공 — 사용자마다 다른 위젯
3. **기존 안내 기능을 탭의 일부로 편입** — MediWay 핵심 차별화(QR·길찾기)를 자연스럽게 흡수
4. **탭 전환 시 세션 유지** — QR 스캔 중에 다른 탭 보다 돌아와도 진행 상태 보존

### Phase 2의 4대 가치
1. **정보 아키텍처** — 6개 탭 · URL 영속 · 모바일/웹 이원화
2. **개인화** — 로그인 사용자·소속 병원에 맞는 홈 위젯
3. **기능 확장 슬롯** — 입원/건강검진은 플래그, P3에 실내용으로 채움
4. **기존 가치 보존** — 안내(QR·지도)가 그대로 1급 시민으로 남음

---

## 承 — 설계 원칙과 기술 선택

### 원칙 7계명
1. **Tab은 URL을 가진다** — 새로고침·공유·뒤로가기에 강해야 함
2. **Tab 간 독립** — 한 탭의 에러가 다른 탭을 깨뜨리지 않음 (Error Boundary)
3. **Hospital features flag 기반** — 기능 미사용 병원에서 탭이 사라져야 함
4. **모바일·웹 동일 IA** — 6개 탭은 어느 플랫폼에서도 동일 이름·순서
5. **홈은 Assembler, 위젯은 Leaf** — 위젯은 독립 컴포넌트 + 독립 데이터 fetch
6. **세션 보존 최우선** — QR/길찾기 세션은 탭 전환으로 죽지 않음
7. **데이터 fetching은 구독 우선** — RTDB `onValue`로 실시간. 폴링 지양

### 기술 스택 선택 근거

| 영역 | 선택 | 대안 | 이유 |
|---|---|---|---|
| Tab State | `useSearchParams` | Zustand, Context, cookie | URL-first 원칙. P0에서 환자 페이지 mode 토글에 이미 적용 성공 |
| Data Fetching | Firebase RTDB `onValue` | REST `get`, TanStack Query | 이미 RTDB 스택. 실시간 대기·공지에 필수 |
| Tab Layout | **Mount all + visibility toggle** | Conditional mount, `React.lazy` | P0에서 지도·QR 동시 마운트 패턴 검증됨. 세션 유지 | 
| Error Boundary | `react-error-boundary` | 수동 try/catch | 선언적 + fallback UI 지원 |
| Form (예약) | React Hook Form + Zod | 수동 useState | 복잡도 증가 대비 |
| Date/Time | `date-fns` (ko locale) | Day.js | Tree-shaking 우수, 이미 많은 프로젝트 사용 |
| 데이터 캐시 (선택) | SWR | TanStack Query | 가볍고 RTDB subscribe와 궁합 |

### 필요 선행 지식

| 분야 | 깊이 | 핵심 |
|---|---|---|
| Phase 1 산출물 전반 | 완전 이해 | HospitalContext / Hospital features flag / 라우팅 구조 |
| React Router v6 nested routes + Outlet | 실무 | 탭 안에서 nested sub-route |
| React Error Boundary | 실무 | 탭별 격리 |
| RHF + Zod | 실무 | 예약 폼 유효성 |
| RTDB onValue·off·single-path subscription | 실무 | 위젯 독립 구독 |
| ICS/타임존 처리 (date-fns-tz) | 기본 | `Asia/Seoul` 고정 가정 |
| Lighthouse Accessibility | 기본 | 탭 키보드 네비 |

### 위험 조기 식별
- **탭 overflow on mobile**: 6개 탭 이상 노출 시 모바일 폭 부족 → overflow dropdown 패턴 (`AdminLayout` D옵션 방식 재활용)
- **Feature flag 변경 시 현재 탭 증발**: 예) 건강검진 탭 보던 중 병원이 기능 off → 홈으로 자동 리다이렉트
- **세션 보존 vs 메모리 사용**: 모든 탭 항상 마운트 = 메모리 비용. 위젯은 독립 unmount 가능
- **예약 충돌/중복**: 클라이언트 submission 중복 방지 (`isSubmitting`) + 서버측 중복 체크

---

## 轉 — 세부 구현 설계

### 1. 탭 구조 및 노출 조건

#### 1.1 탭 카탈로그

| ID | 아이콘 | 라벨 | 노출 조건 | P2 구현 범위 |
|---|---|---|---|---|
| `home` | `Home` | 홈 | 항상 | **전체** 위젯 |
| `outpatient` | `Hospital` | 외래 | `hospital.features.appointments === true` | **MVP** (예약/취소/시간표) |
| `inpatient` | `Bed` | 입원 | `features.inpatient` && 현재 입원 | **Skeleton만** (P3 채움) |
| `checkup` | `ClipboardHeart` | 건강검진 | `features.checkup` | **Skeleton만** (P3 채움) |
| `guide` | `Map` | 안내 | 항상 | **기존 PatientPage 흡수** |
| `more` | `Grid2x2` | 더보기 | 항상 | **Skeleton** (설정·로그아웃 등 일부) |

#### 1.2 노출 조건 유틸

```ts
// src/services/tabs.ts
import { HospitalProfile } from '@/types/hospital';
import { UserProfile } from '@/types/auth';
import { InpatientStatus } from '@/types/inpatient';

export type TabId = 'home' | 'outpatient' | 'inpatient' | 'checkup' | 'guide' | 'more';

export interface TabDef {
  id: TabId;
  label: string;
  icon: LucideIcon;
  path: string;
}

export function getVisibleTabs(
  hospital: HospitalProfile,
  user: UserProfile,
  inpatientStatus?: InpatientStatus | null,
): TabDef[] {
  const tabs: TabDef[] = [HOME_TAB];
  if (hospital.features.appointments) tabs.push(OUTPATIENT_TAB);
  if (hospital.features.inpatient && inpatientStatus?.active) tabs.push(INPATIENT_TAB);
  if (hospital.features.checkup) tabs.push(CHECKUP_TAB);
  tabs.push(GUIDE_TAB, MORE_TAB);
  return tabs;
}
```

- 이유: 탭 목록을 single source of truth로. UI·라우팅·가드가 전부 이 함수 참조

### 2. 라우팅과 URL 상태

#### 2.1 라우트 맵 (P1에서 확장)
```
/h/:slug/patient                    — 기본 진입 → /home redirect
/h/:slug/patient/home               — 홈 탭
/h/:slug/patient/outpatient         — 외래 탭 (기본 서브: 내 예약)
/h/:slug/patient/outpatient/book    — 예약 생성
/h/:slug/patient/outpatient/schedule — 시간표
/h/:slug/patient/inpatient          — 입원 탭 (skeleton)
/h/:slug/patient/checkup            — 건강검진 탭 (skeleton)
/h/:slug/patient/guide              — 안내 (mode=browse|guide 유지)
/h/:slug/patient/guide/:sessionId   — 세션 QR 링크 (legacy 호환)
/h/:slug/patient/more               — 더보기
/h/:slug/patient/more/settings      — 설정
```

#### 2.2 Router 구성 (React Router v6)

```tsx
<Route path="/h/:slug/patient" element={<HospitalShell />}>
  <Route index element={<Navigate to="home" replace />} />
  <Route path="home" element={<HomeTab />} />
  <Route path="outpatient/*" element={<OutpatientTab />} />
  <Route path="inpatient" element={<InpatientTab />} />
  <Route path="checkup" element={<CheckupTab />} />
  <Route path="guide/*" element={<GuideTab />} />
  <Route path="more/*" element={<MoreTab />} />
</Route>
```

- `HospitalShell`이 상단 헤더·탭바를 렌더하고 `<Outlet />`으로 자식 탭 표시

#### 2.3 탭 내 sub-state는 URL 쿼리

외래: `?view=list|book|schedule`, 안내: `?mode=browse|guide`. P0에 이미 있는 패턴 계승.

#### 2.4 Deep link 보호
- URL 직접 입력 시 `hospital.features` 미지원이면 `/home`으로 fallback + toast "이 기능은 병원에서 제공하지 않습니다"
- 사용자가 탭 요건을 잃으면(예: 입원 해제) 다음 네비게이션에서 자동 리다이렉트

### 3. 탭 네비게이션 UI

#### 3.1 공통 TabBar 컴포넌트

```tsx
// src/components/hospital/HospitalTabs.tsx
interface Props {
  tabs: TabDef[];
  currentId: TabId;
}

export function HospitalTabs({ tabs, currentId }: Props) { /* ... */ }
```

- 모바일: 가로 스크롤 + overflow 드롭다운 fallback
- 웹: sticky 상단 탭 (header 하단)
- 키보드: ←/→ 화살표 키로 탭 이동 (`role="tablist"`, `role="tab"`)

#### 3.2 모바일 패턴

- 6개까지는 한 줄, 7개 이상은 **5개 + "⋯"** 드롭다운
- 스크롤 시 현재 탭 중앙 정렬 (`scrollIntoView({ block: 'nearest', inline: 'center' })`)
- BottomNav와 중복 아님: 탭바는 기능 전환, BottomNav는 섹션 전환 — **P2에서는 BottomNav 제거**하고 상단 탭으로 통일 (mediway_user_main 목업 참조)

#### 3.3 웹 패턴

- `sticky top-0 z-40 bg-surface/80 backdrop-blur`
- 탭 간 간격 `gap-8`, 각 탭 `pb-4 border-b-2 border-transparent`, 활성 시 `border-primary text-primary`
- 스크롤 시 헤더 shrink 효과는 **P4로 연기**

### 4. 홈 탭 (대시보드)

#### 4.1 위젯 카탈로그 (P2 범위)

| 위젯 | 데이터 소스 | P2 구현 | 설명 |
|---|---|---|---|
| GreetingHeader | user.displayName + time | ✅ | "Good morning, Alex." |
| TodayScheduleWidget | `/hospitals/{id}/appointments/{uid}` | ✅ | 오늘 예약·검사 카드 |
| QuickActionsWidget | 정적 | ✅ | 4개 CTA: 예약·길찾기·대기·응급실 |
| AnnouncementBanner | `/hospitals/{id}/announcements` | ✅ | 최신 1건 dismissable |
| WaitQueueWidget | `/wait_queue/{id}/...` | ⏳ **Placeholder만** | "현재 대기 없음" — P3에서 실시간 채움 |
| ProxyPaymentCTA | 정적 배너 | ✅ (비활성 + "곧 출시") | P3에서 결제 연동 |
| NearbyServicesWidget (웹 전용) | POIs filtered | 선택 구현 | 사이드바로 |

#### 4.2 위젯 설계 원칙

1. **독립 컴포넌트 + 독립 구독** — 위젯 하나 실패해도 다른 위젯 생존
2. **Skeleton fallback** — 로딩 중에는 각 위젯이 자체 skeleton 렌더
3. **빈 상태** — 데이터 없을 때 문구·아이콘 필수. 빈 카드 금지
4. **우선순위 기반 노출** — 모바일은 세로 순서(Greeting → Proxy → Schedule → Quick → Announcement), 웹은 2컬럼(좌: 일정/공지, 우: Quick + Nearby)

#### 4.3 TodayScheduleWidget 구현 세부

```tsx
function TodayScheduleWidget() {
  const { hospital } = useHospital();
  const user = useAuthStore(s => s.user);
  const [appts, setAppts] = useState<Appointment[] | null>(null);

  useEffect(() => {
    if (!hospital || !user) return;
    const today = startOfDay(new Date()).getTime();
    const tomorrow = today + 86400_000;
    const apptRef = query(
      ref(db, `hospitals/${hospital.id}/appointments/${user.uid}`),
      orderByChild('startAt'),
      startAt(today),
      endAt(tomorrow),
    );
    return onValue(apptRef, snap => {
      const list: Appointment[] = [];
      snap.forEach(child => { list.push({ ...child.val(), id: child.key }); return false; });
      setAppts(list);
    });
  }, [hospital?.id, user?.uid]);

  if (appts === null) return <ScheduleSkeleton />;
  if (appts.length === 0) return <EmptySchedule />;
  return <ScheduleList items={appts} />;
}
```

- 이유: 날짜 범위 쿼리 + 실시간. 추가 예약 발생 시 즉시 반영

### 5. 외래 탭 (MVP)

#### 5.1 서브 뷰

- **내 예약 목록** (`?view=list`, 기본) — 다가오는 예약 + 과거 이력
- **예약 생성** (`?view=book`) — 부서 → 의료진 → 날짜/시간 → 확정
- **시간표** (`?view=schedule`) — 부서별 의료진 근무 주간 뷰

#### 5.2 데이터 모델

```ts
// /hospitals/{id}/schedules/{doctorId}/{weekKey}
interface DoctorWeekSchedule {
  doctorId: string;
  weekOf: string;              // "2026-W17"
  slots: Array<{
    start: number;            // epoch
    end: number;
    capacity: number;
    booked: number;
  }>;
}

// /hospitals/{id}/appointments/{uid}/{apptId}
interface Appointment {
  id: string;
  doctorId: string;
  departmentId: string;
  startAt: number;
  endAt: number;
  status: 'scheduled' | 'checked-in' | 'completed' | 'cancelled';
  createdAt: number;
}
```

#### 5.3 예약 생성 플로우

1. 부서 선택 (`departments`에서 조회)
2. 의료진 선택 (부서 필터)
3. 주간 캘린더에서 가용 슬롯 선택
4. 확인 모달 → 제출

서버측 유효성 (Cloud Function `createAppointment`):
- 슬롯 `booked < capacity` 확인
- 동일 사용자 같은 시간 중복 금지
- 슬롯 `booked++` 원자 업데이트 (`runTransaction`)

```ts
// functions/src/appointments/create.ts
export const createAppointment = onCall({ region: 'asia-northeast3' }, async (req) => {
  const { hospitalId, doctorId, weekKey, slotIndex } = req.data;
  const uid = req.auth?.uid;
  if (!uid) throw new HttpsError('unauthenticated', '로그인이 필요합니다');
  // ...transaction로 booked 증가 + /appointments 생성
});
```

#### 5.4 취소 플로우
- 24시간 이전까지만 취소 가능 (정책)
- `slot.booked--` 복원

### 6. 안내 탭 (기존 PatientPage 흡수)

#### 6.1 이관 전략

현재 `src/pages/PatientPage.tsx` + `PatientMapBrowseView.tsx` + `PatientDashboard.tsx`를:

1. `PatientPage` → **삭제** (기능은 탭 안으로)
2. `PatientDashboard` → `src/components/hospital/guide/PatientGuideSection.tsx`로 이동. QR 발급·세션 수신 로직 100% 보존
3. `PatientMapBrowseView` → `src/components/hospital/guide/MapBrowseSection.tsx`로 이동
4. `GuideTab`: 두 섹션을 `?mode=browse|guide`에 따라 visibility 토글 (P0 패턴 계승)

#### 6.2 legacy 라우트 호환

- `/patient/:sessionId` (구 QR 링크) → **`/h/:slug/patient/guide/:sessionId`로 리다이렉트**
- 세션에서 hospitalId 읽어서 slug 매핑 (P1 리다이렉트 로직 확장)

#### 6.3 안내 탭 내부 sub-tab UI 재사용

기존 "지도 보기 / QR 안내" 필 탭은 그대로 유지. 단 상위에 병원 대시보드 탭이 있으므로 시각적 계층을 구분:
- 상위: 6개 대시보드 탭 (primary 활성 border)
- 하위: 지도/QR 2개 sub-tab (필 스타일, 작은 사이즈)

### 7. 더보기 탭 (스켈레톤)

#### 7.1 P2 포함 항목
- 내 정보 (이름·이메일·전화)
- 병원 스위처 (`hospitalIds` 2개 이상 시 노출)
- 알림 설정 (placeholder)
- 고령자 모드 토글 (placeholder, P4 실제 동작)
- 로그아웃

#### 7.2 P3+에서 추가될 슬롯
- 결제/간편결제, 대리결제
- 서류 발급
- 가족 연결
- 개인정보 설정

UI는 iOS 설정 앱 같은 세로 리스트 (No-Line Rule로 surface 구분).

### 8. 세션·상태 보존 전략

#### 8.1 문제
탭 전환 시 `<GuideTab />` 언마운트 → QR 세션 구독 끊김 → 환자가 길찾기 중 "홈" 탭 보고 돌아오면 경로 사라짐.

#### 8.2 해결: Shell-level mount + visibility toggle

```tsx
// HospitalShell.tsx
<div className={showHome ? 'block' : 'hidden'}><HomeTab /></div>
<div className={showGuide ? 'block' : 'hidden'}><GuideTab /></div>
```

- 모든 탭이 항상 마운트
- `currentTabId` state로 visibility만 제어
- Guide 탭은 특히 세션 구독 유지

#### 8.3 메모리 고려
- 이미지·지도 SVG 캐시는 유지 (메모리 부담 낮음)
- 고비용 쿼리(실시간 `onValue`)는 탭별 **활성 시에만 구독** — visibility 감지 훅으로 토글

```tsx
// src/hooks/useTabActive.ts
export function useTabActive(tabId: TabId): boolean {
  const { tab } = useCurrentTab();
  return tab === tabId;
}

// 위젯에서
const active = useTabActive('home');
useEffect(() => {
  if (!active) return;
  const unsub = onValue(...);
  return () => unsub();
}, [active]);
```

- 이유: 활성 탭만 구독 → 비용 효율 + 재진입 시 즉시 최신화

### 9. 데이터 스키마 확장

#### 9.1 신규 경로
```
/hospitals/{hospitalId}/
  appointments/{uid}/{apptId}     — 예약
  schedules/{doctorId}/{weekKey}  — 의료진 근무표
  departments/{deptId}            — (P1 스키마 재활용)
  announcements/{annId}           — (P1 스키마 재활용)
```

#### 9.2 사용자 확장
```ts
interface UserProfile {
  // 기존 P1
  // P2 추가
  preferences?: {
    dashboardOrder?: string[];  // 사용자 정의 위젯 순서 (향후)
    notifications?: {...};
    largeUi?: boolean;          // 고령자 모드 (P4)
  };
}
```

#### 9.3 인덱스
- `appointments/{uid}` 하위에 `.indexOn: ["startAt"]` — 날짜 쿼리 성능
- `schedules/{doctorId}` 하위에 `.indexOn: ["weekOf"]`

### 10. 보안 규칙 확장

```jsonc
{
  "rules": {
    "hospitals": {
      "$hospitalId": {
        "appointments": {
          "$uid": {
            ".indexOn": ["startAt"],
            ".read":  "auth.uid === $uid || auth.token.hospitalRoles[$hospitalId] in ['staff','admin']",
            ".write": "auth.uid === $uid || auth.token.hospitalRoles[$hospitalId] in ['staff','admin']",
            "$apptId": {
              "doctorId":   { ".validate": "newData.isString()" },
              "startAt":    { ".validate": "newData.isNumber() && newData.val() > now" },
              "endAt":      { ".validate": "newData.isNumber() && newData.val() > data.child('startAt').val()" },
              "status":     { ".validate": "newData.val() in ['scheduled','checked-in','completed','cancelled']" }
            }
          }
        },
        "schedules": {
          ".read": "auth != null && auth.token.hospitals[$hospitalId] === true",
          "$doctorId": {
            ".write": "auth.token.hospitalRoles[$hospitalId] in ['staff','admin']",
            ".indexOn": ["weekOf"]
          }
        }
      }
    }
  }
}
```

- 원칙: 예약은 본인 + 병원 staff/admin만 읽기/쓰기. `startAt > now` validate로 과거 예약 차단.

---

## 結 — 완료 기준·검증 전략·Next

### 완료 기준 (세부화)

#### 기능 기준
- [ ] `/h/:slug/patient`로 진입 시 `/home`으로 자동 리다이렉트
- [ ] 6개 탭 전환이 URL 변경 + 새로고침 보존
- [ ] `hospital.features.appointments=false`인 병원에서 외래 탭 미노출
- [ ] 외래 탭에서 예약 생성 → 홈 "오늘 일정"에 즉시 반영 (같은 날인 경우)
- [ ] 예약 취소 → 슬롯 `booked` 복원
- [ ] 24시간 이내 예약 취소 차단 (서버 검증)
- [ ] 안내 탭에서 기존 지도/QR 전 기능 동작 (지도 보기·QR 세션·POI 상세·경로 안내)
- [ ] QR 세션 진행 중 "홈" 탭 전환 후 "안내" 복귀 → 세션 유지
- [ ] legacy `/patient/:sessionId` 링크 접속 시 `/h/{slug}/patient/guide/:sessionId`로 리다이렉트

#### 성능 기준
- [ ] 홈 탭 FCP < 1.5s (lab 기준, Fast 3G 시뮬)
- [ ] 탭 전환 인터랙션 < 100ms (visibility toggle이므로 리렌더만)
- [ ] 비활성 탭의 RTDB 구독이 해제됨 (DevTools Network 탭에서 WebSocket 메시지 감소 확인)

#### 격리 기준
- [ ] 병원 A 환자가 병원 B의 `/hospitals/B/appointments/*` 읽기 시도 → 401
- [ ] Staff가 소속 외 병원의 예약 쓰기 → 401

#### 품질 기준
- [ ] tsc·eslint·build 통과
- [ ] Lighthouse Accessibility 95+
- [ ] 탭 키보드 네비 (←/→) 동작 확인

### 검증 전략

1. **자동**
   - E2E: Playwright — 6개 탭 순차 클릭 + URL 일치 + 콘텐츠 렌더 확인
   - 예약 생성/취소 테스트: 중복·시간 범위·취소 시간 제한
   - RTDB 규칙 E2E: `public/e2e-appointments.html` 신규 작성
2. **수동 시나리오**
   - A. 환자 신규 가입 → 외래 예약 생성 → 홈에 반영 → 취소 → 복원 확인
   - B. 두 병원 가입 → 병원 스위처로 전환 → 각자의 탭/예약 분리 확인
   - C. QR 스캔 → 길안내 중 "홈" 탭 → "안내" 복귀 → 경로 유지
   - D. 병원 features.inpatient=false → 입원 탭 미노출. features 활성화 후 실시간 탭 등장
3. **모니터링**
   - Sentry 도입 시점 (P2 후반 권장)

### 롤백 계획
- Feature flag `VITE_P2_DASHBOARD=true` 도입. false 시 기존 `/patient/*` 경로 유지
- git 브랜치 `phase/p2-dashboard` 기반 작업, main 보호

### Next (Phase 3 진입 조건)
1. 완료 기준 100% 통과
2. 파일럿 병원 1곳에서 최소 5명 사용자 테스트 완료
3. P3 시작 시 `PlusUltra#3.md`로 이어받아 **실시간 대기·결제·알림톡·처방 전송** 구현

---

## UIUX 가이드라인

본 절은 `uiux/` 폴더의 자산을 Phase 2 신규 화면에 정확히 녹여 넣기 위한 가이드다. Phase 1의 UIUX 섹션(설계 원칙·모바일/웹 경계)을 전제로, Phase 2 특유 요소만 다룬다.

### U1. 참조 자산 매핑 (P2 대상)

| 경로 | 대응 P2 화면 |
|---|---|
| `mobile_uiux/mediway_user_main/code.html` | **홈 탭 (모바일)** — 이 레이아웃이 P2 홈 탭의 기준 |
| `web_page_uiux/mediway_user_main/code.html` | **홈 탭 (웹)** — 2컬럼 bento |
| `web_page_uiux/mediway_user_main/code.html` 의 TopAppBar | **상단 탭바 (웹)** — Home/Outpatient/Inpatient/Check-up/Guidance 실제 탭 구조 정답지 |
| `mobile_uiux/mediway_user_main/code.html` 의 BottomNavBar | **모바일 탭 대체안 참고** — P2에서는 상단 탭으로 통일하지만, 대안 참고 |
| `mobile_uiux/mediway_qr/` · `web_page_uiux/mediway_3d_1/` | **안내 탭 (지도/QR)** — 기존 구현 계승 |
| `mobile_uiux/mediway/`, `mediway_1`, `mediway_2`, `mediway_3`, `mediway_4` | 다양한 홈/외래 변형 — bento/list 패턴 영감 |
| `mobile_uiux/mediway_staff_1`, `mediway_staff_2` | 의료진용 예약/시간표 화면 (P2 외래 탭 의료진 측 참고) |
| `web_page_uiux/mediway_v2/`, `mediway_staff_v2_*` | 리디자인 변형 참고 |

### U2. 모바일 vs 웹 — 대시보드 정답 레이아웃

#### 홈 탭 (모바일) — `mediway_user_main` 모바일 기준

```
┌────────────────────────────────────┐
│ ← MediWay · {병원명}          👤 │  h-16, fixed, backdrop-blur
├────────────────────────────────────┤
│                                    │
│  DASHBOARD                         │  label uppercase tracking-wider
│  Good morning, {이름}님.           │  text-3xl font-semibold
│                                    │
│  ┌──────────────────────────────┐ │  ← Proxy Payment CTA (gradient)
│  │ 💳 Proxy Payment           > │ │     from-primary to-primary-container
│  │    Settle invoices instantly │ │     rounded-xl shadow-primary/10
│  └──────────────────────────────┘ │
│                                    │
│  Today's Schedule                  │
│  ┌──────────────────────────────┐ │
│  │ ▌ ❤ Cardiology       2:00 PM │ │  좌 1px primary stripe
│  │   Dr. Sarah Jenkins          │ │  on surface-container-lowest
│  │   📍 Room 302, West Wing     │ │
│  └──────────────────────────────┘ │
│                                    │
│  Quick Actions                     │
│  ┌───────┬───────┐                │
│  │ 🔍    │ 📅    │ 2×2 grid       │
│  │ Find  │ Book  │                │
│  ├───────┼───────┤                │
│  │ 📊    │ 🅿     │                │
│  │ Time  │ Park  │                │
│  └───────┴───────┘                │
│                                    │
│  📢 오늘 병원 공지 (dismissable)  │
└────────────────────────────────────┘
   (P2: 하단 탭바 없음 — 상단 탭으로 통일)
```

- 상단은 **고정 TopAppBar** (병원 헤더)
- Schedule 카드는 `absolute left:0 w-1 h-full bg-primary`로 컬러 스트라이프
- Quick Actions는 2×2 정사각, 아이콘 중앙 정렬
- Proxy Payment(P3용)는 비활성·placeholder. "곧 출시" 배지 부착

#### 홈 탭 (웹) — `mediway_user_main` 웹 기준

```
┌─────────────────────────────────────────────────────────────────────┐
│ logo {병원명}   Home  Outpatient  Inpatient  Check-up  Guidance  🔔 👤│  sticky
├─────────────────────────────────────────────────────────────────────┤
│ max-w-7xl mx-auto px-8 py-12                                         │
│                                                                      │
│  Good morning, {이름}님.                                              │
│  Here is your care overview for today at {병원명}.                    │
│                                                                      │
│  ┌─── col-span-7 ─────────────────┐ ┌─── col-span-5 ──────────┐    │
│  │ Today's Schedule               │ │ Quick Actions (2x2)    │    │
│  │ ┌────────────────────────────┐ │ │ ┌─────┬─────┐          │    │
│  │ │ 📅 Cardiology Outpatient   │ │ │ │ 🔍  │ 📅  │          │    │
│  │ │    2:00 PM — 2:30 PM       │ │ │ ├─────┼─────┤          │    │
│  │ │    Dr. Sarah · Main B-3F   │ │ │ │ 📊  │ 🅿   │          │    │
│  │ │           [View Details →] │ │ │ └─────┴─────┘          │    │
│  │ └────────────────────────────┘ │ │                        │    │
│  │ ℹ 15분 전 도착을 권장합니다    │ │ Proxy Payment (col-2)  │    │
│  │                                │ │ [gradient wide CTA]    │    │
│  └────────────────────────────────┘ └────────────────────────┘    │
│                                                                      │
│  📢 공지 배너 (full-width)                                            │
└─────────────────────────────────────────────────────────────────────┘
```

- **상단 탭이 sticky** — 실제 P2의 대시보드 탭은 `Home/Outpatient/Inpatient/Check-up/Guidance`로 영문 레이블 목업과 일치하되 한국어 `홈/외래/입원/건강검진/안내`로 번역
- 2컬럼 그리드 `lg:grid-cols-12` (좌 7, 우 5)
- Today's Schedule 카드는 모바일 대비 크게, 그라디언트 배경 원형 장식
- Quick Actions는 **아이콘 좌상단 + 제목·서브텍스트 좌측 정렬** (모바일의 중앙 정렬과 다름)

### U3. 상단 탭바 — 구체 구현

#### 모바일 (`< md`)

- **공간 제약**: 폭 375px에서 6개 탭 + 여백 부담. 아이콘-only + 탭 기본 라벨 축약
- `overflow-x-auto` + `scroll-snap-type: x mandatory`
- **현재 탭 중앙 정렬** — `scrollIntoView({ inline: 'center' })`
- 활성 탭: `bg-primary/10 text-primary rounded-full px-4 py-1.5`
- 비활성: `text-on-surface-variant`
- **대안**: 6개 초과 시 `...` 드롭다운 (`AdminLayout.tsx` D옵션 패턴)

```tsx
<nav className="sticky top-16 z-40 flex gap-1 overflow-x-auto bg-surface/80 backdrop-blur px-4 py-2">
  {tabs.map(t => <TabPill ... />)}
</nav>
```

#### 웹 (`md+`)

- **수평 탭**, header의 일부로 통합 가능
- `sticky top-0 z-40`
- 활성: `text-primary border-b-2 border-primary pb-1 font-bold`
- 비활성: `text-slate-500 hover:text-primary`
- `gap-8` 사이 간격

### U4. 홈 위젯 세부 UIUX

#### U4.1 TodayScheduleWidget

| 축 | 모바일 | 웹 |
|---|---|---|
| 배경 | `surface-container-lowest` | 동일 + gradient circle 장식 우상단 |
| 폭 | 전체 폭 | 좌 col-span-7 |
| 좌측 스트라이프 | `absolute left-0 w-1 h-full bg-primary` | 원형 아이콘 (`bg-surface-container-high p-4 rounded-full text-primary`) |
| CTA | 카드 자체가 탭 가능 (세부 페이지로) | 오른쪽 "View Details →" gradient 버튼 |
| 빈 상태 | "오늘 일정이 없습니다." + 🎉 | 동일 문구 + "내일 일정 보기" 링크 |
| Loading | Skeleton: 회색 박스 3개 | 동일 |

#### U4.2 QuickActionsWidget

| 축 | 모바일 | 웹 |
|---|---|---|
| 그리드 | `grid-cols-2` 정사각 | `grid-cols-2` 직사각 |
| 정렬 | **중앙** (아이콘 크게, 라벨 아래) | **좌측** (아이콘 좌상단 원형 배지, 제목·서브텍스트 좌) |
| 아이콘 배경 | `bg-secondary-fixed text-on-secondary-fixed-variant rounded-full` | `bg-primary/10 text-primary rounded-full p-3` |
| 크기 | `p-4` | `p-6` |
| Hover | `active:scale-[0.98]` | `hover:bg-surface-container-low group-hover:scale-110` |
| 액션 4개 | 예약·길찾기·대기·응급실 | 동일. 응급실은 다른 원색 |

#### U4.3 ProxyPayment CTA

- 모바일: 홈 상단 **큰 배너** (Schedule 위). P3 활성화 전까지는 비활성 상태 "Payment coming soon"
- 웹: Quick Actions 그리드의 `col-span-2` 가로 배너
- 공통: `bg-gradient-to-r from-primary to-primary-container`, `text-on-primary`, `rounded-xl shadow-lg shadow-primary/10`

#### U4.4 AnnouncementBanner

- 자리: 홈 탭 하단 (또는 헤더 바로 아래 slim bar 옵션)
- `surface-container-low` 배경, `text-on-surface-variant`, `info` 아이콘
- Dismissable: X 버튼으로 닫기. localStorage에 `dismissed:{annId}` 저장
- 긴급 공지 시 `bg-error-container/40 text-on-error-container` 변형

### U5. 외래 탭 UIUX

#### U5.1 내 예약 목록

- 카드 리스트, 각 카드는 TodayScheduleWidget과 유사 스타일
- 상단 필터 bar: `전체 / 예정 / 완료 / 취소` 4개 필 탭 (FloorSelector 스타일)
- 빈 상태: "아직 예약이 없어요" + "예약하기" gradient CTA

#### U5.2 예약 생성 (Wizard)

- 3단계: 부서 → 의료진 → 시간
- 모바일: full-screen 각 단계 (back 버튼으로 이전)
- 웹: 3-step progress bar + 단일 페이지 내 전환
- 부서·의료진 카드는 로고/사진 + 이름 + 전공
- 시간 슬롯: 주간 그리드 (요일 × 시간 30분 단위). 매진 슬롯은 `opacity-40 cursor-not-allowed`
- 확인 모달: **Glassmorphism** — `bg-surface/80 backdrop-blur-xl`, `mediway_clinical/DESIGN.md`의 "Vitality Glass Modal"

#### U5.3 시간표

- 부서 선택 → 해당 주 의료진 × 시간 grid
- 모바일: 가로 스크롤 (시간은 고정 좌측, 의료진 가로)
- 웹: 전체 그리드 한눈에

### U6. 안내 탭 UIUX

Phase 1 말 구조 그대로 계승. 변경점만:

- 상단 대시보드 탭의 `안내` 활성 표시
- 하위 sub-tab(지도/QR)은 안내 탭 내부 상단 (필 스타일)
- 지도 및 QR 섹션은 기존과 동일
- POI 상세 카드·길찾기 UI는 P1에서 이미 구축된 버전 유지

### U7. 더보기 탭 UIUX

- 모바일: 세로 리스트 (iOS 설정 앱 패턴)
- 항목별: 아이콘 + 라벨 + 우측 chevron
- 섹션 구분: `text-xs uppercase tracking-wider` 라벨 + 가벼운 `surface-container-low` 배경 없음(No-Line Rule)
- 로그아웃은 맨 아래 `text-error`
- 웹: 모바일과 동일 레이아웃을 `max-w-2xl mx-auto`로 중앙 정렬

### U8. 빈 상태·로딩·에러

| 상태 | 모바일 | 웹 |
|---|---|---|
| Loading | Skeleton 블록 (3-4개) | 동일 |
| Empty | 64px 아이콘 + 제목 + 부제 + CTA | 더 큰 아이콘 + 여백 |
| Error | Toast (하단) + 재시도 버튼 | Inline error card |
| No access | "이 기능은 {병원명}에서 제공하지 않습니다" + "홈으로" | 동일 |

### U9. 모바일/웹 구현 분기 원칙

- 탭 내 위젯은 하나의 파일에서 `md:` prefix로 분기
- 구조가 본질적으로 다른 영역(예: 예약 Wizard의 full-screen vs progress bar)은 **두 개의 서브컴포넌트** 파일로 분리
- 공통 props·타입은 상위 탭 컴포넌트가 보유

```tsx
// src/components/hospital/outpatient/BookFlow.tsx
import { BookFlowMobile } from './BookFlow.mobile';
import { BookFlowDesktop } from './BookFlow.desktop';

export function BookFlow(props: BookFlowProps) {
  const isDesktop = useMediaQuery('(min-width: 768px)');
  return isDesktop ? <BookFlowDesktop {...props} /> : <BookFlowMobile {...props} />;
}
```

### U10. 접근성 — 탭 + 대시보드

- `role="tablist"` + `role="tab"` + `aria-controls`·`aria-selected`
- 좌우 화살표 키 네비 지원
- 탭 전환 시 `<Outlet>` 영역에 포커스 이동 (`autoFocus` or ref)
- Quick Actions 버튼 `aria-label` 명시
- 색상 대비: Quick Actions의 primary/10 배경 위의 primary 텍스트 4.5:1 확인

### U11. 피해야 할 함정

1. **모바일에서 BottomNav와 상단 탭 둘 다 노출** — 충돌. P2에서는 **상단 탭으로 통일**
2. **탭을 `display:none`으로만 토글** — DOM은 존재, 구독 유지 → 메모리 부담. 비활성 탭 구독은 `useTabActive` 훅으로 해제
3. **탭 순서 고정 안 하기** — 모바일 overflow 때 들쭉날쭉. 순서는 정의부에서 단 1곳만
4. **features flag 변경 시 URL 유효성 미검사** — 사용자가 지금 보던 탭이 갑자기 없어지면 빈 화면
5. **홈 위젯 전역 상태 공유** — 위젯 간 커플링 위험. 각 위젯 독립 구독·독립 에러
6. **Schedule 카드를 wide하게 밀착시키기** — No-Line Rule 위반 쉬움. surface 토큰 경계 유지
7. **예약 폼을 단일 페이지에 모두 넣기** — 모바일 높이 부족. 3-step으로 분할

### U12. 구현 체크리스트 — UIUX 관점

- [ ] **홈 탭** (`mediway_user_main` 모바일/웹)과 80%+ 일치
- [ ] **상단 탭바** 모바일 가로 스크롤 + 웹 sticky 분기 정상
- [ ] **Today's Schedule** 카드 좌측 primary 스트라이프 (모바일)·원형 아이콘 + gradient 장식 (웹)
- [ ] **Quick Actions** 모바일 중앙 정렬·웹 좌측 정렬
- [ ] **Proxy Payment CTA** gradient + primary shadow
- [ ] **안내 탭** 기존 지도/QR 기능 시각 회귀 없음
- [ ] **예약 Wizard** 3-step, glassmorphism 확인 모달
- [ ] **빈 상태** 모든 탭에서 아이콘·문구·CTA 배치
- [ ] **No-Line Rule** 준수: `grep -R "border border-" src/components/hospital`로 감사
- [ ] **Lighthouse Accessibility** 모바일·데스크탑 95+

### U13. 작업 견적 (UIUX 포함)

| 작업 | 소요 |
|---|---|
| 탭 구조·라우팅·features flag | 1.5일 |
| HospitalTabs 컴포넌트 (모바일/웹) | 1.5일 |
| HomeTab 셸 + 위젯 4종 (TodaySchedule·QuickActions·Proxy·Announcement) | 2.5일 |
| OutpatientTab MVP (목록·예약 Wizard·시간표) | 3.0일 |
| GuideTab (PatientPage 이관 + legacy 리다이렉트) | 1.5일 |
| MoreTab 스켈레톤 | 0.5일 |
| useTabActive 훅 + 탭 visibility 로직 | 0.5일 |
| 스키마·규칙·Functions (예약 생성/취소) | 1.5일 |
| E2E 테스트 페이지 (`public/e2e-appointments.html`) | 0.5일 |
| UIUX 통합 QA (Lighthouse·키보드·No-Line 감사) | 1.0일 |
| 회귀 테스트 및 버그 픽스 | 1.0일 |
| **합계** | **14.5일 (≈ 3주)** |

---

## 부록

### 부록 A. 의사결정 레지스터

| ID | 결정 | 대안 | 근거 |
|---|---|---|---|
| D1 | 모바일 상단 탭으로 통일 (BottomNav 제거) | BottomNav 유지 | 웹과 정보 아키텍처 일치, 공통 컴포넌트 재사용 |
| D2 | 모든 탭 항상 mount + visibility toggle | 조건부 unmount | QR 세션 유지 최우선 |
| D3 | 탭 활성 여부에 따라 구독 토글 | 상시 구독 | 메모리·RTDB 비용 절감 |
| D4 | 안내 탭에 기존 PatientPage 흡수 | 별도 `/patient` 유지 | IA 단순화, legacy는 리다이렉트로 보존 |
| D5 | 예약 3-step Wizard | 단일 페이지 폼 | 모바일 높이 부족, 단계별 검증 유리 |
| D6 | 입원·건강검진은 P2에서 Skeleton만 | 전체 구현 | 실제 기능은 P3에서 시간표·결과 등과 함께 |
| D7 | 공지는 `/hospitals/{id}/announcements` 단일 트리 | 사용자별 타깃팅 | P2는 broadcast 단계, 타깃팅은 P5 |

### 부록 B. 파일 생성·수정 체크리스트

**신규**
- `src/pages/hospital/HospitalShell.tsx` — 헤더 + 탭바 + Outlet
- `src/components/hospital/HospitalTabs.tsx`
- `src/components/hospital/HomeTab.tsx`
- `src/components/hospital/home/TodayScheduleWidget.tsx`
- `src/components/hospital/home/QuickActionsWidget.tsx`
- `src/components/hospital/home/ProxyPaymentCTA.tsx`
- `src/components/hospital/home/AnnouncementBanner.tsx`
- `src/components/hospital/home/WaitQueuePlaceholder.tsx`
- `src/components/hospital/OutpatientTab.tsx`
- `src/components/hospital/outpatient/AppointmentList.tsx`
- `src/components/hospital/outpatient/BookFlow.tsx` (+ `.mobile.tsx`, `.desktop.tsx`)
- `src/components/hospital/outpatient/ScheduleView.tsx`
- `src/components/hospital/GuideTab.tsx` (기존 PatientPage 흡수)
- `src/components/hospital/guide/PatientGuideSection.tsx` (이관)
- `src/components/hospital/guide/MapBrowseSection.tsx` (이관)
- `src/components/hospital/InpatientTab.tsx` (skeleton)
- `src/components/hospital/CheckupTab.tsx` (skeleton)
- `src/components/hospital/MoreTab.tsx`
- `src/hooks/useTabActive.ts`
- `src/hooks/useCurrentTab.ts`
- `src/services/appointments.ts`
- `src/services/announcements.ts`
- `src/services/tabs.ts`
- `functions/src/appointments/create.ts`
- `functions/src/appointments/cancel.ts`
- `public/e2e-appointments.html`

**수정**
- `src/App.tsx` — 라우팅 확장 (`/h/:slug/patient/*` 중첩)
- `src/pages/PatientPage.tsx` — **삭제** (기능은 GuideTab으로)
- `src/components/patient/PatientDashboard.tsx` — `guide/PatientGuideSection.tsx`로 이동
- `src/components/patient/PatientMapBrowseView.tsx` — `guide/MapBrowseSection.tsx`로 이동
- `database.rules.json` — appointments·schedules 규칙 추가
- `src/types/auth.ts` — `preferences` 필드
- `src/types/hospital.ts` — 필요 시 확장

### 부록 C. Phase 관계 다이어그램 (텍스트)

```
 Phase 1  (완료)                Phase 2 (본 문서)             Phase 3 (다음)
 ──────────────                 ───────────────               ───────────
 HospitalContext  ────────────> HospitalShell
 인증·claim  ───────────────────> Tab auth guards
 라우팅 /h/:slug  ──────────────> /h/:slug/patient/*
 화이트라벨 테마                   탭바 테마 반영
                                 OutpatientTab MVP  ───────> WaitQueue(real-time)
                                 AnnouncementBanner ───────> PushKit 연동
                                 ProxyPaymentCTA(비활성) ──> 결제 PG 연결
 기존 QR·지도  ───── 안내 탭 흡수 ──> GuideTab
```

### 부록 D. 학습 리소스

- React Router v6 nested routes: https://reactrouter.com/en/main/start/concepts
- React Hook Form + Zod: https://react-hook-form.com/get-started, https://zod.dev
- date-fns-tz: https://date-fns.org
- Firebase RTDB transactions: https://firebase.google.com/docs/database/web/read-and-write#save_data_as_transactions
- WAI-ARIA Tabs pattern: https://www.w3.org/WAI/ARIA/apg/patterns/tabs/

---

_작성일: 2026-04-22_
_대상 Phase: #2 — 대시보드 셸 + 상단 탭_
_선행: `PlusUltra#1.md` (Multi-Tenant 기반)_
_이어지는 문서: `PlusUltra#3.md` (실시간 대기 · 결제 · 알림 · 처방)_
_UIUX 참조: `uiux/mobile_uiux/mediway_user_main/`, `uiux/web_page_uiux/mediway_user_main/`, `uiux/*/mediway_clinical/DESIGN.md`_
