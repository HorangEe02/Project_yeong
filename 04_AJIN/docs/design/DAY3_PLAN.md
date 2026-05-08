# Day 3 상세 작업 계획 — 공통 컴포넌트 라이브러리 구축

> **Phase**: 2 (공통 컴포넌트)
> **목표 일수**: 1 (6시간)
> **선행 조건**: Day 2 완료 (Firebase 통합 + Mock + Login/Dashboard 폴리싱)
> **작성일**: 2026-04-27
> **관련 문서**: [FINAL_17DAY_PLAN.md](FINAL_17DAY_PLAN.md), [WEB_DESIGN_SPECIFICATION.md](WEB_DESIGN_SPECIFICATION.md)

---

## 목차

1. [Day 3 전체 목표](#1-day-3-전체-목표)
2. [Day 2 마감 시점 진단](#2-day-2-마감-시점-진단)
3. [컴포넌트 목록 (16개)](#3-컴포넌트-목록-16개)
4. [페이지별 사용 매핑](#4-페이지별-사용-매핑)
5. [우선순위 분류](#5-우선순위-분류)
6. [Day 3 시간 배분](#6-day-3-시간-배분)
7. [컴포넌트 상세 명세](#7-컴포넌트-상세-명세)
8. [의존성 매트릭스](#8-의존성-매트릭스)
9. [컴포넌트 카탈로그 페이지 (옵션)](#9-컴포넌트-카탈로그-페이지-옵션)
10. [검증 체크리스트](#10-검증-체크리스트)
11. [위험 요소 + 완화](#11-위험-요소--완화)
12. [Day 4 의존성 확인](#12-day-4-의존성-확인)

---

## 1. Day 3 전체 목표

| # | 목표 | 측정 기준 |
|:--:|---|---|
| 1 | **재사용 가능한 16개 공통 컴포넌트** 구축 | TS strict 통과 + Day 4~11에서 직접 사용 |
| 2 | **Plotly 통합** (코드 스플리팅) | 차트 페이지 진입 시 dynamic import |
| 3 | **react-leaflet 통합** (Folium 대체) | 19 사업장 지도 즉시 가능 |
| 4 | **SSE 클라이언트 헬퍼** | Day 4 C 도우미 즉시 사용 |
| 5 | **컴포넌트 카탈로그 페이지** (옵션) | `/dev/components` 라우트 |

### Day 3가 끝나면 가능한 것:
- 모든 기능 페이지에서 일관된 디자인 시스템 컴포넌트 사용
- Plotly 차트를 하나의 wrapper로 통일 (테마 자동 적용)
- 사업장 지도 (Folium → react-leaflet)
- 폼 검증 (react-hook-form + Zod 통합)
- 모달 / Drawer / Toast 알림
- LLM 마크다운 응답 렌더링
- SSE 스트리밍 토큰 단위 수신

---

## 2. Day 2 마감 시점 진단

### 2-1. 이미 만들어진 컴포넌트 (Day 2에서 추출됨)
| 파일 | 라인 | 상태 |
|---|---:|:--:|
| `components/ui/Button.tsx` | 30 | ✅ 5 variants + sm/md/lg + loading + icon |
| `components/ui/Badge.tsx` | 30 | ✅ 6 status (●/○ 글리프) |
| `components/ui/MetricCard.tsx` | 18 | ✅ 카운트업 통합 |
| `components/ui/ErrorAlert.tsx` | 28 | ✅ critical/warning/info |

### 2-2. 셸 컴포넌트 (이미 동작)
- `components/shell/TopBar.tsx`
- `components/shell/LeftSidebar.tsx`
- `components/shell/RightPanel.tsx`

### 2-3. 미흡한 부분 (Day 3에서 보완)
- ❌ 일관된 Card 추상화 없음 (각 페이지마다 직접 className 사용)
- ❌ Tabs 없음 (Draft 3탭, Compliance 4탭, Admin 6탭, Equipment 3+5탭에서 필요)
- ❌ Modal 없음 (사용자 생성 위저드, 시뮬레이션 결과 등)
- ❌ DataTable 없음 (사원 24명, 에러 685, 로그인 이력)
- ❌ PlotlyChart 없음 (D Gantt, E 7차트, F SPC Nelson)
- ❌ MapView 없음 (A 인원 검색 19개소, D 사업장 지도)
- ❌ FormField 없음 (Login 외 폼 일관성)
- ❌ MarkdownRenderer 없음 (LLM 응답)
- ❌ Toast 없음 (실시간 알람 알림)
- ❌ SSE 헬퍼 없음 (Day 4 차단 요소)

---

## 3. 컴포넌트 목록 (16개)

### 카테고리별 16개 컴포넌트

| # | 컴포넌트 | 파일 | 카테고리 | 라이브러리 | 예상 라인 |
|:--:|---|---|:--:|---|:--:|
| 1 | **Card** | `ui/Card.tsx` | 레이아웃 | — | 35 |
| 2 | **GlassPanel** | `ui/GlassPanel.tsx` | 레이아웃 | — | 40 |
| 3 | **PanelHeader** | `ui/PanelHeader.tsx` | 레이아웃 | — | 30 |
| 4 | **Tabs** | `ui/Tabs.tsx` | 인터랙션 | — | 80 |
| 5 | **Stepper** | `ui/Stepper.tsx` | 인터랙션 | — | 60 |
| 6 | **Modal** | `ui/Modal.tsx` | 인터랙션 | — | 90 |
| 7 | **Drawer** | `ui/Drawer.tsx` | 인터랙션 | — | 80 |
| 8 | **Tooltip** | `ui/Tooltip.tsx` | 인터랙션 | — | 60 |
| 9 | **Toast** | `ui/Toast.tsx` + `useToast` | 알림 | zustand | 100 |
| 10 | **DataTable** | `ui/DataTable.tsx` | 데이터 | @tanstack/react-table | 150 |
| 11 | **FormField** | `form/FormField.tsx` | 폼 | react-hook-form | 70 |
| 12 | **PlotlyChart** | `chart/PlotlyChart.tsx` | 차트 | react-plotly.js (lazy) | 80 |
| 13 | **MapView** | `chart/MapView.tsx` | 지도 | react-leaflet | 90 |
| 14 | **MarkdownRenderer** | `ui/MarkdownRenderer.tsx` | 텍스트 | react-markdown + remark-gfm | 50 |
| 15 | **DottedSeparator** | `ui/DottedSeparator.tsx` | 레이아웃 | — | 15 |
| 16 | **Skeleton** | `ui/Skeleton.tsx` | 로딩 | — | 40 |

### + 헬퍼 / 훅

| # | 헬퍼 | 파일 | 용도 |
|:--:|---|---|---|
| H1 | **`useSSE` 훅** | `hooks/useSSE.ts` | SSE 스트리밍 (Day 4 필수) |
| H2 | **`useToast` 훅 / store** | `store/toast.ts` + `ui/Toast.tsx` | 알림 표시 |
| H3 | **`useFirestoreCollection` 훅** | `hooks/useFirestoreCollection.ts` | Firestore 쿼리 (Day 6+) |
| H4 | **`useRTDBValue` 훅** | `hooks/useRTDBValue.ts` | RTDB 라이브 (Day 6+) |
| H5 | **`useDebounce` 훅** | `hooks/useDebounce.ts` | 검색 입력 |

### + 스타일 보강

| # | 항목 | 파일 |
|:--:|---|---|
| S1 | 컴포넌트 모듈 CSS | `styles/components.css` |
| S2 | Tabs/Modal 애니메이션 | `styles/animations.css` |

---

## 4. 페이지별 사용 매핑

### 컴포넌트 × 페이지 매트릭스

|              | A | B | C | D | E | F | Login | Dashboard |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Card         | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ |
| GlassPanel   | — | — | ✓ chat | ✓ | — | — | ✓ | — |
| PanelHeader  | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ |
| Tabs         | — | ✓ 3 | ✓ 모드 | ✓ 4 | ✓ 6 | ✓ 3+5 | — | — |
| Stepper      | — | — | ✓ SOP | — | ✓ 위저드 | — | — | — |
| Modal        | — | ✓ 미리보기 | — | ✓ 시뮬 | ✓ 생성 | ✓ CSV 업 | — | — |
| Drawer       | — | — | — | — | ✓ 상세 | — | — | — |
| Tooltip      | ✓ | ✓ | — | ✓ | ✓ | ✓ | — | ✓ |
| Toast        | — | ✓ | ✓ | ✓ 알람 | — | ✓ 알람 | — | ✓ |
| DataTable    | ✓ 24명 | ✓ 이력 | — | ✓ 변경 | ✓ 사용자 | ✓ 이력 | — | — |
| FormField    | — | ✓ | ✓ | — | ✓ 위저드 | ✓ | ✓ | — |
| PlotlyChart  | — | — | — | ✓ Gantt | ✓ 7차트 | ✓ SPC | — | — |
| MapView      | ✓ 19 | — | — | ✓ 19 | — | — | — | — |
| MarkdownRenderer | — | ✓ 결과 | ✓ LLM | — | — | ✓ 매뉴얼 | — | — |
| DottedSeparator | — | — | ✓ | — | — | — | ✓ | ✓ |
| Skeleton     | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ |

### 사용 빈도 분석
- **모든 페이지**: Card, PanelHeader, Skeleton
- **6/8 페이지**: Tooltip, FormField
- **5/8 페이지**: DataTable, Tabs
- **4/8 페이지**: Modal, Toast
- **2/8 페이지**: PlotlyChart, MapView (그러나 핵심 가치 ↑)

---

## 5. 우선순위 분류

### 🔴 우선순위 1 — Day 4 의존 (반드시 Day 3 완성)
| # | 컴포넌트 | Day 4 사용처 |
|:--:|---|---|
| H1 | **`useSSE` 훅** | C 챗봇 스트리밍 |
| 14 | **MarkdownRenderer** | C LLM 응답 렌더링 |
| 1 | **Card** | C 메시지 카드 |
| 2 | **GlassPanel** | C 챗 컴포저 (Liquid Glass) |
| 11 | **FormField** | C 입력 필드 |
| 9 | **Toast** | C 피드백 알림 |
| 6 | **Modal** | C 비전 모델 이미지 미리보기 |

### 🟡 우선순위 2 — Day 5~9 의존
| # | 컴포넌트 | 사용처 |
|:--:|---|---|
| 4 | **Tabs** | B/D/E/F 모든 다탭 페이지 |
| 12 | **PlotlyChart** | D Gantt / E 통계 / F SPC |
| 13 | **MapView** | A / D 사업장 지도 |
| 10 | **DataTable** | A / B / E / F 테이블 |

### 🟢 우선순위 3 — Day 10~11 의존
| # | 컴포넌트 | 사용처 |
|:--:|---|---|
| 5 | **Stepper** | E 사용자 생성 위저드 |
| 7 | **Drawer** | E 사용자 상세 |
| 8 | **Tooltip** | 모든 페이지 |
| 16 | **Skeleton** | 로딩 상태 |
| 3 | **PanelHeader** | 모든 섹션 |
| 15 | **DottedSeparator** | C 메모리 영역 |

---

## 6. Day 3 시간 배분

### 6시간 (09:00 ~ 16:00, 점심 1h 포함)

| 시간 | 작업 | 컴포넌트 |
|:--:|---|---|
| 09:00 ~ 09:30 | 레이아웃 4종 | Card / GlassPanel / PanelHeader / DottedSeparator |
| 09:30 ~ 10:30 | 인터랙션 4종 | Tabs / Stepper / Modal / Drawer |
| 10:30 ~ 10:45 | 휴식 | — |
| 10:45 ~ 11:30 | 알림 + 폼 | Toast / Tooltip / FormField |
| 11:30 ~ 12:00 | 데이터 | DataTable (TanStack 통합) |
| 12:00 ~ 13:00 | 점심 | — |
| 13:00 ~ 14:00 | **차트 통합** | PlotlyChart (lazy + 테마 자동) |
| 14:00 ~ 14:45 | **지도 통합** | MapView (react-leaflet + 19 사업장) |
| 14:45 ~ 15:00 | 휴식 | — |
| 15:00 ~ 15:30 | 마크다운 + 로딩 | MarkdownRenderer / Skeleton |
| 15:30 ~ 16:00 | **SSE 헬퍼 + Firebase 훅** | useSSE / useFirestoreCollection / useRTDBValue / useDebounce |

### 검증 단계 (16:00 ~ 16:30)
- TS strict 컴파일 0 오류
- 카탈로그 페이지 렌더링 (`/dev/components`)
- Bundle size 측정 (Plotly 코드 스플리팅 확인)

---

## 7. 컴포넌트 상세 명세

### 7-1. Card
```tsx
interface CardProps {
  children: ReactNode;
  variant?: 'default' | 'highlighted' | 'flat';
  padding?: 'sm' | 'md' | 'lg' | 'none';
  className?: string;
  onClick?: () => void;
}
```
- HUD `2px` border-radius
- 라이트: `#FFFFFF` + `1px solid var(--hud-border)`
- 다크: `#111820` + `1px solid var(--hud-border)`
- highlighted: 좌측 골드 3px 띠

### 7-2. GlassPanel
```tsx
interface GlassPanelProps {
  children: ReactNode;
  intensity?: 'normal' | 'strong';
  className?: string;
}
```
- `backdrop-filter: blur(24px) saturate(140%)`
- TopBar / RightPanel / Chat composer / Modal scrim에 사용
- SKILL.md "Liquid Glass 4영역 한정" 규칙 준수

### 7-3. PanelHeader
```tsx
interface PanelHeaderProps {
  labelEn: string;
  labelKo?: string;
  badge?: ReactNode;
  action?: ReactNode;
}
```
- 영문 대문자 + 한글 부제 패턴
- letter-spacing 0.1em
- 우측 배지 또는 액션 버튼

### 7-4. Tabs
```tsx
interface TabItem {
  id: string;
  labelEn: string;
  labelKo: string;
  icon?: ReactNode;
  badge?: number;
  disabled?: boolean;
}
interface TabsProps {
  items: TabItem[];
  active: string;
  onChange: (id: string) => void;
  variant?: 'main' | 'sub';
}
```
- main: 골드 밑줄 (활성)
- sub: 회색 underline + 골드 텍스트 (활성)
- 키보드: ←→ 화살표로 탭 이동
- ARIA: role="tablist" / role="tab" / aria-selected

### 7-5. Stepper
```tsx
interface Step {
  id: string;
  title: string;
  description?: string;
}
interface StepperProps {
  steps: Step[];
  current: number;
  onStepClick?: (idx: number) => void;
  variant?: 'horizontal' | 'vertical';
}
```
- 각 단계: ●(완료) / ◉(현재) / ○(미진행)
- 진행률 바 (활성/비활성 색상)
- E 사용자 생성 위저드 / C SOP에 사용

### 7-6. Modal
```tsx
interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
  closeOnEsc?: boolean;
  closeOnOverlay?: boolean;
  hideCloseButton?: boolean;
  children: ReactNode;
}
```
- `<dialog>` 네이티브 사용 (포커스 트랩 자동)
- 60% 네이비 scrim + GlassPanel 카드
- ESC / 외부 클릭 닫기 (옵션)

### 7-7. Drawer
```tsx
interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  side?: 'right' | 'left' | 'bottom';
  width?: number;
  children: ReactNode;
}
```
- `transform: translateX/Y` 슬라이드 200ms
- E 사용자 상세 / 알람 상세에 사용

### 7-8. Tooltip
```tsx
interface TooltipProps {
  content: ReactNode;
  position?: 'top' | 'bottom' | 'left' | 'right';
  children: ReactElement;
  delay?: number;
}
```
- 호버 시 200ms 후 표시
- ARIA: role="tooltip" + aria-describedby
- 모바일: 길게 누르기

### 7-9. Toast
```tsx
interface Toast {
  id: string;
  type: 'success' | 'warning' | 'error' | 'info';
  title?: string;
  message: string;
  duration?: number; // ms (default 4000)
  action?: { label: string; onClick: () => void };
}

// 사용
const { addToast } = useToast();
addToast({ type: 'success', message: '저장 완료' });
```
- 우측 하단 stack
- ●/○ 글리프 + 색상
- D 알람 / B 다운로드 / F 위반 감지에 사용

### 7-10. DataTable
```tsx
interface DataTableProps<T> {
  data: T[];
  columns: ColumnDef<T>[];
  pagination?: boolean;
  pageSize?: number;
  sortable?: boolean;
  filterable?: boolean;
  onRowClick?: (row: T) => void;
  loading?: boolean;
}
```
- TanStack Table v8 기반
- HUD 스타일 헤더 (영문 대문자 + 한글 부제)
- A 사원 24, B 문서 이력, E 사용자, E 로그인 이력, F 에러 685
- CSV/XLSX 내보내기 액션 슬롯

### 7-11. FormField
```tsx
interface FormFieldProps {
  label: string;
  name: string;
  type?: 'text' | 'email' | 'password' | 'number' | 'select' | 'textarea';
  required?: boolean;
  error?: string;
  helperText?: string;
  options?: { value: string; label: string }[]; // for select
  register?: UseFormRegister; // react-hook-form
}
```
- react-hook-form 통합
- ARIA: aria-invalid + aria-describedby
- 에러 메시지 빨간 점 ●
- helperText 회색

### 7-12. PlotlyChart ⭐ (가장 중요)
```tsx
interface PlotlyChartProps {
  data: Plotly.Data[];
  layout?: Partial<Plotly.Layout>;
  config?: Partial<Plotly.Config>;
  className?: string;
  onClick?: (event: Plotly.PlotMouseEvent) => void;
}
```
- **Lazy import**: `React.lazy(() => import('react-plotly.js'))`
- 테마 자동 적용 (라이트/다크 자동 전환)
- 한국어 폰트 (Pretendard)
- 호버 색상: 골드 보더
- 사용처:
  - D Gantt / D Network
  - E 7차트 (Bar/Pie/Heatmap)
  - F Nelson SPC + Plotly Network (Markov)
  - F XGBoost 게이지

### 7-13. MapView ⭐
```tsx
interface Marker {
  id: string;
  lat: number;
  lng: number;
  name: string;
  description?: string;
  icon?: ReactNode;
}
interface MapViewProps {
  markers: Marker[];
  center?: [number, number];
  zoom?: number;
  height?: string;
  onMarkerClick?: (marker: Marker) => void;
}
```
- react-leaflet + OpenStreetMap (무료)
- 19 사업장 마커 (Folium 대체)
- 다크 모드: CartoDB Dark Matter 타일
- 라이트 모드: CartoDB Positron
- 클러스터링 (옵션)

### 7-14. MarkdownRenderer
```tsx
interface MarkdownRendererProps {
  content: string;
  variant?: 'chat' | 'document';
}
```
- react-markdown + remark-gfm (테이블 지원)
- 코드 블록: 모노스페이스 + 골드 보더
- 링크: 골드 색상
- 강조: 골드
- 테이블: HUD 스타일
- 마크다운 → CSV 변환 (B 페이지)

### 7-15. DottedSeparator
```tsx
interface DottedSeparatorProps {
  text?: string; // 중앙에 라벨
  margin?: 'sm' | 'md' | 'lg';
}
```
- C 메모리 영역 / 페이지 구역 분리

### 7-16. Skeleton
```tsx
interface SkeletonProps {
  variant?: 'text' | 'card' | 'avatar' | 'metric';
  width?: string | number;
  height?: string | number;
  count?: number;
}
```
- 펄스 애니메이션 (1.4s)
- 라이트: `#E8E3DA`
- 다크: `#1A2030`

---

## 8. 의존성 매트릭스

### 외부 라이브러리 (이미 설치됨)
| 라이브러리 | 버전 | 사용 컴포넌트 |
|---|---|---|
| `@tanstack/react-table` | latest | DataTable |
| `react-plotly.js` + `plotly.js` | latest | PlotlyChart |
| `react-leaflet` + `leaflet` | latest | MapView |
| `react-hook-form` + `zod` | latest | FormField |
| `react-markdown` + `remark-gfm` | latest | MarkdownRenderer |
| `clsx` | latest | 모든 컴포넌트 |
| `lucide-react` | latest | Tabs / Toast 아이콘 |

### 추가 설치 필요 (없음)
- 모든 라이브러리는 Day 1에서 이미 설치 완료 ✓

### 컴포넌트 간 의존성
```
Card ← (모든 페이지)
GlassPanel ← Modal / Drawer / TopBar (이미 사용)
Tabs ← (B / D / E / F)
Modal ← (D 시뮬 / E 위저드 / F CSV 업로드)
   ↓
Stepper (Modal 내부에서 사용)
   ↓
FormField (Stepper 각 단계)
DataTable
   ↓
   ├─ Skeleton (loading)
   └─ Tooltip (액션 버튼)
PlotlyChart ← (D / E / F)
   ↓
   └─ themeStore (라이트/다크 전환 감지)
MapView ← (A / D)
Toast ← useToast → 모든 페이지
MarkdownRenderer ← (B / C / F)
```

---

## 9. 컴포넌트 카탈로그 페이지 (옵션)

### 목적
Day 3 종료 시 모든 컴포넌트를 한 페이지에서 시연·검증.

### 구현 옵션
| 옵션 | 장단 |
|:--:|---|
| **A) `/dev/components` 라우트** (DEV 모드만) | ✅ 빠름 / ❌ 라우트 추가 |
| **B) Storybook 통합** | ✅ 표준 / ❌ 1일 추가 작업 |
| **C) 카탈로그 미작성** (인-페이지 검증) | ✅ 시간 절약 / ❌ 일관성 검증 어려움 |

**권장**: **A** — Day 3 막판 30분에 간단한 카탈로그 라우트 작성. Storybook은 본선 후 도입.

### 카탈로그 라우트 구조 (`routes/dev/components.tsx`)
```tsx
function ComponentCatalog() {
  return (
    <div className="page">
      <h1>컴포넌트 카탈로그</h1>

      <Section title="Buttons">
        <Button variant="primary">Primary</Button>
        <Button variant="secondary">Secondary</Button>
        ...
      </Section>

      <Section title="Cards">
        <Card>...</Card>
        <Card variant="highlighted">...</Card>
      </Section>

      ... (16 컴포넌트 모두)
    </div>
  );
}
```

`App.tsx`:
```tsx
{import.meta.env.DEV && <Route path="/dev/components" element={<ComponentCatalog />} />}
```

---

## 10. 검증 체크리스트

### Day 3 마감 시 12 시나리오

| # | 시나리오 | 기대 결과 |
|:--:|---|---|
| 1 | TS strict 컴파일 | 0 오류 |
| 2 | dev 서버 부팅 | < 3초 |
| 3 | `/dev/components` 진입 | 모든 컴포넌트 렌더링 |
| 4 | Plotly 차트 페이지 진입 | dynamic chunk 로드 (network tab 확인) |
| 5 | 라이트/다크 토글 | Plotly 색상 즉시 전환 |
| 6 | MapView 19개소 마커 | OpenStreetMap 타일 + 마커 표시 |
| 7 | Modal 열기 | scrim + GlassPanel 카드 + ESC 닫기 |
| 8 | Drawer 열기 | 우측 슬라이드 200ms |
| 9 | Toast 발생 | 우측 하단 스택 + 4초 후 자동 제거 |
| 10 | DataTable 정렬·페이지네이션 | TanStack 동작 |
| 11 | FormField + react-hook-form | Zod 검증 + 에러 메시지 |
| 12 | useSSE 헬퍼 (mock SSE) | 토큰 단위 수신 시뮬레이션 |

### Bundle Size 검증
```bash
npm run build
# 다음 chunk 분리 확인:
# - plotly.js (3MB+) → 별도 chunk
# - leaflet (200KB) → 별도 chunk
# - i18next → 별도 chunk
```

---

## 11. 위험 요소 + 완화

| # | 위험 | 영향 | 완화 |
|:--:|---|:--:|---|
| 1 | **Plotly 번들 3MB+** | 🔴 | `React.lazy()` 코드 스플리팅 + Suspense fallback |
| 2 | **react-leaflet SSR 이슈** | 🟡 | Vite는 CSR이므로 무관 |
| 3 | **TanStack Table 학습 곡선** | 🟡 | 단순 use case 먼저 (정렬·페이지) |
| 4 | **Modal `<dialog>` 브라우저 호환** | 🟢 | Chrome 37+, Safari 15.4+ — 본선 OK |
| 5 | **Toast 중복 표시** | 🟢 | id 기반 dedup |
| 6 | **MarkdownRenderer XSS** | 🔴 | `react-markdown` 기본 sanitize + `dangerouslySetInnerHTML` 미사용 |
| 7 | **Plotly 한글 깨짐** | 🟡 | `font: { family: 'Pretendard, ...' }` 명시 |
| 8 | **react-leaflet 타일 차단** (회사 방화벽) | 🟡 | 본선 무대 인터넷 확보됨 |
| 9 | **6시간 내 16개 미완성** | 🔴 | 우선순위 1만 6 → 우선순위 2 → 3 순으로 |

---

## 12. Day 4 의존성 확인

### Day 4 (C 도우미) 시작 전 반드시 완성되어야 할 항목
- [ ] **`useSSE` 훅** (Day 4 차단 요소)
- [ ] **MarkdownRenderer** (LLM 응답 렌더링)
- [ ] **Card** (메시지 카드)
- [ ] **GlassPanel** (챗 컴포저)
- [ ] **FormField** (입력 필드)
- [ ] **Toast** (피드백 알림)
- [ ] **Modal** (비전 이미지 미리보기)

→ **우선순위 1 (7개)** 모두 완성 시 Day 4 즉시 시작 가능

### Day 5+ 의존
- Day 5 (B): Tabs / DataTable / FormField / MarkdownRenderer
- Day 6~7 (F): Tabs / **PlotlyChart** / DataTable / Modal
- Day 8 (B): Tabs / DataTable / Modal / FormField
- Day 9 (D): Tabs / **PlotlyChart** / **MapView** / Modal
- Day 10 (A): DataTable / **MapView**
- Day 11 (E): Tabs / DataTable / **PlotlyChart** / Stepper / Drawer / Modal

---

## 13. Day 3 산출물 요약

### 신규 파일 (예상 23개)

```
frontend/src/
├── components/
│   ├── ui/
│   │   ├── Card.tsx                       ⭐
│   │   ├── GlassPanel.tsx                 ⭐
│   │   ├── PanelHeader.tsx                ⭐
│   │   ├── Tabs.tsx                       ⭐
│   │   ├── Stepper.tsx                    ⭐
│   │   ├── Modal.tsx                      ⭐
│   │   ├── Drawer.tsx                     ⭐
│   │   ├── Tooltip.tsx                    ⭐
│   │   ├── Toast.tsx                      ⭐
│   │   ├── DataTable.tsx                  ⭐
│   │   ├── MarkdownRenderer.tsx           ⭐
│   │   ├── DottedSeparator.tsx            ⭐
│   │   └── Skeleton.tsx                   ⭐
│   ├── form/
│   │   └── FormField.tsx                  ⭐
│   └── chart/
│       ├── PlotlyChart.tsx                ⭐
│       └── MapView.tsx                    ⭐
├── hooks/
│   ├── useSSE.ts                          ⭐ (Day 4 차단)
│   ├── useFirestoreCollection.ts          ⭐
│   ├── useRTDBValue.ts                    ⭐
│   └── useDebounce.ts                     ⭐
├── store/
│   └── toast.ts                           ⭐
├── styles/
│   ├── components.css                     ⭐
│   └── animations.css                     ⭐
└── routes/dev/
    └── components.tsx                     ⭐ (DEV 카탈로그)
```

### 갱신 파일
```
frontend/
├── src/App.tsx                            (DEV 카탈로그 라우트 추가)
└── src/main.tsx                           (animations.css import)
```

---

## 14. Day 3 종료 기준

다음 모두 충족 시 Day 4로 넘어갑니다:

- [ ] **TS strict 컴파일 0 오류**
- [ ] **`/dev/components` 카탈로그** 모든 컴포넌트 렌더링
- [ ] **Plotly 코드 스플리팅** 검증 (별도 chunk 확인)
- [ ] **MapView 19 사업장** OpenStreetMap에서 표시
- [ ] **Toast / Modal / Drawer** 키보드 (ESC) 동작
- [ ] **DataTable** 정렬 / 페이지네이션 동작
- [ ] **useSSE** 훅 (mock 토큰 스트리밍 시뮬레이션) 동작
- [ ] **MarkdownRenderer** XSS 안전 검증
- [ ] **Bundle build 성공** (`npm run build`)
- [ ] **Day 3 산출물 23개 파일** 모두 커밋 가능

---

## 15. 즉시 시작 가능

다음 중 선택:

| 옵션 | 작업 |
|:--:|---|
| **A** | **Day 3 즉시 시작** — 09:00 시간대부터 (레이아웃 4종) |
| **B** | **검토 + 조정** — 16개 컴포넌트 중 일부 추가/제외/연기 |
| **C** | **우선순위 1만 먼저** — 7개 컴포넌트 (Day 4 차단 해제) |
| **D** | **카탈로그 페이지 제외** — Day 3 시간 30분 절약 |

권장: **A 또는 C** — 시간 부족 시 C, 여유 시 A.

---

## 변경 이력

| 버전 | 날짜 | 변경 |
|---|---|---|
| **1.0** | 2026-04-27 | 초안 — Day 3 (16 컴포넌트 + 5 훅) 6h 분배 |

---

**관련 문서**:
- [FINAL_17DAY_PLAN.md](FINAL_17DAY_PLAN.md) — 17일 통합 로드맵
- [DAY2_PLAN.md](DAY2_PLAN.md) — Day 2 (어제)
- [WEB_DESIGN_SPECIFICATION.md](WEB_DESIGN_SPECIFICATION.md) — 디자인 사양
