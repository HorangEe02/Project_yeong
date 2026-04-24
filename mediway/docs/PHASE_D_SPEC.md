# MediWay Phase D — 의료진 UI 기능 설명서

> 작성일: 2026-04-16 | Phase D 구현 완료 시점 기준
> 빌드 결과: JS 627KB / CSS 17.3KB (gzip 후 ~191KB)

---

## 목차

1. [개요](#1-개요)
2. [UI/UX 디자인 분석 및 반영](#2-uiux-디자인-분석-및-반영)
3. [StaffDashboard 상태 머신](#3-staffdashboard-상태-머신)
4. [QR 스캐너](#4-qr-스캐너)
5. [동선 템플릿 선택 UI](#5-동선-템플릿-선택-ui)
6. [커스텀 경로 편집기](#6-커스텀-경로-편집기)
7. [전송 확인 모달](#7-전송-확인-모달)
8. [StaffPage 반응형 레이아웃](#8-staffpage-반응형-레이아웃)
9. [컴포넌트 상세 명세](#9-컴포넌트-상세-명세)
10. [Phase E/F 연계](#10-phase-ef-연계)

---

## 1. 개요

### 1.1 Phase D의 목적

Phase D는 MediWay의 **의료진 측 인터페이스**를 구현합니다. 의료진(간호사)이 환자의 QR 코드를 스캔하고, 진료 동선을 선택/편집한 뒤, 환자에게 전송하는 전체 플로우를 포함합니다.

### 1.2 구현 범위

| 구현 항목 | 파일 | 설명 |
|----------|------|------|
| useQRScanner 훅 | `hooks/useQRScanner.ts` | html5-qrcode 카메라 라이프사이클 관리 |
| QRScanner 컴포넌트 | `components/staff/QRScanner.tsx` | 카메라 QR 스캔 + 수동 입력 폴백 |
| RouteTemplateList | `components/staff/RouteTemplateList.tsx` | 6개 동선 템플릿 카드 UI |
| RouteBuilder | `components/staff/RouteBuilder.tsx` | 커스텀 경로 편집기 (검색/추가/삭제/순서변경) |
| SendConfirm | `components/staff/SendConfirm.tsx` | Vitality Glass 전송 확인 모달 |
| StaffDashboard | `components/staff/StaffDashboard.tsx` | 상태 머신 기반 전체 플로우 통합 |
| StaffPage | `pages/StaffPage.tsx` | 반응형 레이아웃 (웹 2열 / 모바일 1열) + 통계 사이드바 |

### 1.3 핵심 설계 결정

| 결정 | 이유 |
|------|------|
| 상태 머신 패턴 (8개 state) | 복잡한 UI 플로우를 예측 가능하게 관리 |
| 템플릿 선택 / 커스텀 빌더 탭 분리 | 빈번 동선은 원클릭 선택, 특수 동선은 자유 편집 |
| 수동 토큰 입력 폴백 | 카메라 미지원 환경(데스크톱, HTTP) 대응 |
| Vitality Glass 모달 | DESIGN.md 준수 — backdrop-blur 80%, 이전 화면 투과 |

---

## 2. UI/UX 디자인 분석 및 반영

### 2.1 참조한 디자인 파일

| 디자인 | 파일 경로 | 반영 내용 |
|--------|----------|----------|
| 웹 staff_v2_1 | `uiux/web_page_uiux/mediway_staff_v2_1/` | "동선 전송 및 관리 센터" 제목, QR 스캔 영역 + 템플릿 선택 + 커스텀 경로 빌더 레이아웃 |
| 웹 staff_v2_2 | `uiux/web_page_uiux/mediway_staff_v2_2/` | 통계 카드(PENDING/IN PROGRESS/COMPLETED), 실시간 환자 테이블, 시스템 로그 사이드바 |
| 모바일 staff_1 | `uiux/mobile_uiux/mediway_staff_1/` | Clinical Ops 헤더, Patient Queue, Quick Templates 그리드, Ward Status |
| 모바일 staff_2 | `uiux/mobile_uiux/mediway_staff_2/` | "Scan Patient QR" 배너, Route Templates 카드, Current Status 리스트, Pulse Metrics |
| 모바일 QR | `uiux/mobile_uiux/mediway_qr/` | 환자 QR 표시 화면 (환자 측이지만 QR 스캔 연계 참고) |
| DESIGN.md | `uiux/web_page_uiux/mediway_clinical/DESIGN.md` | Editorial Clinical Excellence 디자인 시스템 |

### 2.2 디자인 → 구현 매핑

| 디자인 요소 | 구현 컴포넌트 | 적용 방식 |
|------------|-------------|----------|
| "Scan Patient QR" 배너 (staff_2) | QRScanner | gradient-primary 배경 + ScanLine 아이콘 |
| Route Templates 카드 (staff_2) | RouteTemplateList | 진료과 그룹핑 + 색상 인디케이터 + 단계/시간 메타 |
| 동선 전송 관리 센터 (staff_v2_1) | StaffPage 제목 + 설명 | "Operational Task" 라벨 + 2열 레이아웃 |
| 종합 대시보드 통계 (staff_v2_2) | StaffPage 사이드바 StatCard | PENDING(amber)/IN PROGRESS(blue)/COMPLETED(green) 색상 |
| 시스템 로그 (staff_v2_2) | StaffPage 사이드바 LogItem | 이름 + 경로 + 시간 |
| Vitality Glass Modal (DESIGN.md) | SendConfirm | bg-surface/80 + backdrop-blur-20px |
| No-Line Rule (DESIGN.md) | 전 컴포넌트 | border 없음, 배경색 차이로 영역 구분 |
| gradient-primary (DESIGN.md) | 주요 CTA 버튼 | `bg-gradient-to-r from-primary to-primary-container` |

### 2.3 반응형 전략

| 뷰포트 | 레이아웃 | 특징 |
|--------|---------|------|
| **모바일** (< 1024px) | 1열 스택 | 전체 너비 카드, 사이드바 숨김, 터치 최적화 (44px 최소 터치 타겟) |
| **데스크톱** (≥ 1024px) | 2열 그리드 `[1fr_360px]` | 좌: 대시보드 메인, 우: 통계 + 로그 사이드바 |

---

## 3. StaffDashboard 상태 머신

### 3.1 상태 다이어그램

```
                    ┌──────────────────┐
                    │       idle       │ ← 초기 상태
                    └────────┬─────────┘
                             │ QR 스캔 시작
                             ▼
                    ┌──────────────────┐
                    │     scanning     │
                    └────────┬─────────┘
                             │ 스캔 성공 (token)
                    ┌────────┴─────────┐
                    │     scanned      │ ← 환자 매칭 완료
                    └──┬──────────┬────┘
                       │          │
            탭: 템플릿  │          │  탭: 커스텀
                       ▼          ▼
            ┌─────────────┐  ┌──────────────┐
            │ selecting_  │  │  building_   │
            │  template   │  │   custom     │
            └──────┬──────┘  └──────┬───────┘
                   │ 선택            │ "이 경로로 전송"
                   └────┬───────────┘
                        ▼
               ┌──────────────────┐
               │    confirming    │ ← SendConfirm 모달
               └──┬───────────┬──┘
                  │ 확인       │ 취소
                  ▼            ▼
         ┌────────────┐  (scanned로 복귀)
         │    sent     │
         └─────┬──────┘
               │ 3초 후 자동
               ▼
         ┌────────────┐
         │    idle     │ ← 초기화
         └────────────┘

         ┌────────────┐
         │    error    │ ← QR 스캔 실패 시
         └─────┬──────┘
               │ "다시 시도"
               ▼
         (idle로 복귀)
```

### 3.2 상태별 UI 렌더링

| 상태 | 화면 내용 |
|------|----------|
| `idle` | QRScanner (스캔 대기 화면) |
| `scanning` | QRScanner (카메라 활성, 스캔 중) |
| `scanned` | 매칭 완료 배너 + 탭(템플릿/커스텀) + 기본 탭: RouteTemplateList |
| `selecting_template` | 매칭 배너 + 탭(활성: 템플릿) + RouteTemplateList |
| `building_custom` | 매칭 배너 + 탭(활성: 커스텀) + RouteBuilder + "이 경로로 전송" 버튼 |
| `confirming` | SendConfirm 모달 (전체 화면 오버레이) |
| `sent` | 성공 배너 ("동선이 환자에게 전송되었습니다!") → 3초 후 idle |
| `error` | 에러 배너 + "다시 시도" 버튼 |

### 3.3 상태 관리 변수

| 변수 | 타입 | 용도 |
|------|------|------|
| `state` | `StaffState` | 현재 상태 머신 상태 |
| `patientToken` | `string \| null` | 스캔된 환자 QR 토큰 |
| `selectedTemplate` | `RouteTemplate \| null` | 선택된 동선 템플릿 |
| `customWaypoints` | `string[]` | 커스텀 경로 경유지 배열 (기본: `['entrance_main']`) |
| `errorMessage` | `string \| null` | 에러 메시지 |

---

## 4. QR 스캐너

### 4.1 useQRScanner 훅

**파일:** `src/hooks/useQRScanner.ts`

html5-qrcode 라이브러리의 카메라 접근, 스캔, 해제를 관리하는 커스텀 훅입니다.

| 반환값 | 타입 | 설명 |
|--------|------|------|
| `containerId` | `string` | html5-qrcode 컨테이너 DOM ID |
| `isScanning` | `boolean` | 스캔 활성 여부 |
| `hasCamera` | `boolean` | 카메라 사용 가능 여부 |
| `startScanning` | `() => Promise<void>` | 카메라 시작 |
| `stopScanning` | `() => Promise<void>` | 카메라 중지 |

**카메라 설정:**

| 항목 | 값 |
|------|-----|
| facingMode | `environment` (후면 카메라 우선) |
| fps | 10 |
| qrbox | 250 × 250px |
| 자동 해제 | 컴포넌트 언마운트 시 `stop()` 호출 |

### 4.2 QRScanner 컴포넌트

**파일:** `src/components/staff/QRScanner.tsx`

| Props | 타입 | 설명 |
|-------|------|------|
| `onScanSuccess` | `(token: string) => void` | 스캔 성공 콜백 |
| `onScanError?` | `(error: string) => void` | 에러 콜백 |

**3가지 모드:**

| 모드 | 트리거 | UI |
|------|--------|-----|
| 대기 | 초기 상태 | ScanLine 아이콘 + "QR 스캔 시작" 버튼 |
| 카메라 | "QR 스캔 시작" 클릭 | html5-qrcode 카메라 뷰 + "스캔 중지" 버튼 |
| 수동 입력 | "수동 토큰 입력" 클릭 | 텍스트 입력 + "확인" 버튼 |

**카메라 미지원 대응:**
- `Html5Qrcode.getCameras()`가 빈 배열 반환 시 → `hasCamera=false`
- 카메라 권한 거부 시 → `hasCamera=false` + 에러 콜백
- 두 경우 모두 "수동 토큰 입력" 폴백 사용 가능

---

## 5. 동선 템플릿 선택 UI

### 5.1 RouteTemplateList

**파일:** `src/components/staff/RouteTemplateList.tsx`

| Props | 타입 | 설명 |
|-------|------|------|
| `templates` | `RouteTemplate[]` | 전체 템플릿 배열 |
| `selectedId` | `string \| null` | 선택된 템플릿 ID |
| `onSelect` | `(template: RouteTemplate) => void` | 선택 콜백 |

### 5.2 진료과별 그룹핑

템플릿을 `departmentTag` 기준으로 자동 그룹핑합니다:

```
내과
  ├── 채혈 → 원무과 → 약국 → 귀가 (기본)
  ├── 원무과 → 약국 → 귀가
  └── 영상의학과 → 원무과 → 약국 → 귀가

외과
  └── 채혈 → 영상의학과 → 원무과 → 약국 → 귀가

건강검진
  └── 채혈 → CT → 내시경 → 상담 → 원무과 → 귀가

정형외과
  └── X-ray → 정형외과 → 원무과 → 약국 → 귀가
```

### 5.3 카드 구성

```
┌───────────────────────────────────────────┐
│ █  채혈 → 원무과 → 약국 → 귀가       기본  >│
│ █  📍 4단계  ⏱ 약 15분                      │
└───────────────────────────────────────────┘
 ↑                                          ↑
 색상 인디케이터                          ChevronRight
 (template.color)
```

| 요소 | 설명 |
|------|------|
| 색상 인디케이터 | 1.5px 폭 둥근 막대, `template.color` |
| 경유지 체인 | shortName 연결 ("채혈 → 원무과 → 약국 → 귀가") |
| 메타 정보 | MapPin 아이콘 + 단계 수, Clock 아이콘 + 예상 시간 |
| 기본 뱃지 | `isDefault: true`일 때 primary/10 배경 뱃지 |
| 선택 상태 | `ring-2 ring-primary/30` + `shadow-ambient-lg` |

---

## 6. 커스텀 경로 편집기

### 6.1 RouteBuilder

**파일:** `src/components/staff/RouteBuilder.tsx`

| Props | 타입 | 설명 |
|-------|------|------|
| `waypoints` | `string[]` | 현재 경유지 POI ID 배열 |
| `onChange` | `(waypointPoiIds: string[]) => void` | 변경 콜백 |

### 6.2 기능

| 기능 | 동작 |
|------|------|
| **경유지 추가** | POI 검색 패널 → 카테고리 필터(전체/진료실/검사실/영상의학/약국/원무) + 텍스트 검색 → 클릭하여 추가 |
| **경유지 삭제** | X 버튼 (귀가(entrance_main)는 삭제 불가) |
| **순서 변경** | ↑↓ 버튼으로 위/아래 이동 |
| **자동 귀가** | 새 경유지는 항상 "귀가" 앞에 삽입됨 |
| **중복 방지** | 이미 추가된 POI는 검색 결과에서 제외 |
| **필터링** | 엘리베이터/계단/화장실은 검색 결과에서 제외 (네비게이션 전용) |

### 6.3 검색 패널

| 요소 | 설명 |
|------|------|
| 검색바 | Search 아이콘 + 텍스트 입력 (name, shortName 매칭) |
| 카테고리 필터 | 6개 칩 버튼 (전체/진료실/검사실/영상의학/약국/원무) |
| 결과 목록 | 최대 48px 높이 스크롤, POI 이름 + 층 표시 |

### 6.4 경유지 카드

```
┌─────────────────────────────────────────┐
│ ① 채혈실                          ↑ ↓ ✕ │
│    2층                                   │
└─────────────────────────────────────────┘
```

| 요소 | 설명 |
|------|------|
| 순서 번호 | primary/10 원형 뱃지 |
| POI 이름 | 굵은 텍스트 |
| 층 정보 | 보조 텍스트 |
| 액션 버튼 | ↑ 이동 / ↓ 이동 / ✕ 삭제 (귀가는 액션 없음) |

---

## 7. 전송 확인 모달

### 7.1 SendConfirm

**파일:** `src/components/staff/SendConfirm.tsx`

| Props | 타입 | 설명 |
|-------|------|------|
| `waypointPoiIds` | `string[]` | 전송할 경유지 배열 |
| `templateName?` | `string` | 템플릿 이름 (커스텀이면 undefined) |
| `onConfirm` | `() => void` | 전송 확인 콜백 |
| `onCancel` | `() => void` | 취소 콜백 |

### 7.2 Vitality Glass 디자인

DESIGN.md의 "Vitality Glass Modal" 사양을 구현합니다:

| 속성 | 값 |
|------|-----|
| 오버레이 배경 | `glass-modal` (bg-surface/80 + backdrop-blur-20px) |
| 모달 카드 | `bg-surface-container-lowest` + `rounded-2xl` + `shadow-ambient-lg` |
| 오버레이 클릭 | 모달 닫기 (취소와 동일) |

### 7.3 모달 구성

```
┌─────────────────────────────────────┐
│ 동선 전송 확인                    ✕ │
│ 채혈 → 원무과 → 약국 → 귀가        │
│                                     │
│  ① 채혈실             본관 2층      │
│  │                                  │
│  ② 원무과             본관 1층      │
│  │                                  │
│  ③ 외래약국           본관 1층      │
│  │                                  │
│  ④ 정문 출입구        본관 1층      │
│                                     │
│  ┌─────────────────────────────┐   │
│  │ 📍 4단계    ⏱ 예상 2분 30초  │   │
│  └─────────────────────────────┘   │
│                                     │
│  [  취소  ] [ 🔵 환자에게 전송  ]    │
└─────────────────────────────────────┘
```

| 요소 | 설명 |
|------|------|
| 타임라인 | 번호 원형 + 세로 점선 연결 (마지막은 primary 배경) |
| 요약 카드 | 단계 수 + 예상 시간 (`computeRoute()` 결과 활용) |
| 취소 버튼 | surface-container-high 배경, on-surface-variant 텍스트 |
| 전송 버튼 | gradient-primary + Send 아이콘 |

---

## 8. StaffPage 반응형 레이아웃

### 8.1 전체 구조

**파일:** `src/pages/StaffPage.tsx`

```
┌──────────────────────────────────────────────────────────┐
│ OPERATIONAL TASK                                          │
│ 동선 전송 및 관리 센터                                     │
│ 환자의 진료 경로를 설정하고 보내줄 기기로 즉시 전송합니다.    │
├──────────────────────────────┬───────────────────────────┤
│                              │                           │
│   StaffDashboard             │   사이드바 (lg만)           │
│   (메인 플로우)                │                           │
│                              │   ┌── Clinical Overview ──┐│
│   • QR 스캐너                 │   │ 진료 대기: 24명        ││
│   • 동선 선택                 │   │ 이동/검사중: 18명      ││
│   • 커스텀 경로               │   │ 진료 완료: 86명        ││
│   • 전송 확인                 │   │ 오늘 방문자: 128명     ││
│                              │   └──────────────────────┘│
│                              │                           │
│                              │   ┌── 최근 전송 로그 ─────┐│
│                              │   │ 김민지: 채혈→원무과     ││
│                              │   │ 이현우: X-ray→정형외과  ││
│                              │   │ 박지성: 원무과→약국     ││
│                              │   └──────────────────────┘│
└──────────────────────────────┴───────────────────────────┘
```

### 8.2 반응형 브레이크포인트

| 뷰포트 | 그리드 | 사이드바 | max-width |
|--------|--------|---------|-----------|
| 모바일 (< 1024px) | 1열 | 숨김 (`hidden`) | `max-w-2xl` |
| 데스크톱 (≥ 1024px) | `grid-cols-[1fr_360px]` | 표시 (`lg:block`) | `max-w-5xl` |

### 8.3 사이드바 컴포넌트

**StatCard** — 통계 카드:

| status | 배경 | 텍스트 | 용도 |
|--------|------|--------|------|
| `pending` | `bg-amber-50` | `text-amber-600` | 진료 대기 |
| `active` | `bg-blue-50` | `text-blue-600` | 이동 및 검사 중 |
| `completed` | `bg-green-50` | `text-green-600` | 진료 완료 |
| `total` | `bg-surface-container-low` | `text-on-surface` | 오늘 방문자 |

**LogItem** — 전송 로그 항목:

| 필드 | 표시 |
|------|------|
| 이름 | 굵은 텍스트 |
| 경로 | 보조 텍스트 (경유지 요약) |
| 시간 | 우측 정렬 ("2분 전", "12분 전") |

> 현재 통계 데이터는 하드코딩된 데모 값입니다. Phase F에서 Firebase Realtime DB와 연동하여 실시간 데이터로 대체됩니다.

---

## 9. 컴포넌트 상세 명세

### 9.1 파일별 Props 요약

| 컴포넌트 | Props | 주요 이벤트 |
|---------|-------|-----------|
| `QRScanner` | `onScanSuccess`, `onScanError?` | 스캔 성공/실패 |
| `RouteTemplateList` | `templates`, `selectedId`, `onSelect` | 템플릿 선택 |
| `RouteBuilder` | `waypoints`, `onChange` | 경유지 변경 |
| `SendConfirm` | `waypointPoiIds`, `templateName?`, `onConfirm`, `onCancel` | 전송/취소 |
| `StaffDashboard` | (없음 — 내부 상태 관리) | — |
| `StaffPage` | (없음 — 페이지 컴포넌트) | — |

### 9.2 컴포넌트 의존성

```
StaffPage
└── StaffDashboard
    ├── QRScanner
    │   └── useQRScanner (html5-qrcode)
    ├── RouteTemplateList
    │   └── routeTemplates (정적 데이터)
    │   └── getPOIById (POI shortName 조회)
    ├── RouteBuilder
    │   └── allPOIs (전체 POI 검색/필터)
    │   └── getPOIById (선택된 POI 정보)
    └── SendConfirm
        ├── getPOIById (경유지 정보 표시)
        ├── computeRoute (예상 시간 계산)
        ├── navigationGraph (그래프 데이터)
        └── formatDuration (시간 포맷)
```

### 9.3 Phase C 연계 포인트

SendConfirm 모달에서 `computeRoute(navigationGraph, waypointPoiIds)`를 호출하여:
- 전체 경로의 **예상 소요 시간**을 계산하여 표시
- 경로 계산 실패 시에도 모달은 표시하되, 시간 정보는 숨김

---

## 10. Phase E/F 연계

### 10.1 Phase E (환자 UI) 연계

의료진이 "환자에게 전송" 버튼을 클릭하면:

1. **현재(Phase D):** `setState('sent')` → 3초 후 초기화 (로컬 시뮬레이션)
2. **Phase F 이후:** Firebase Realtime DB에 세션 생성 → 환자 웹에서 `onValue` 리스너로 실시간 수신

전송 데이터 구조:

```typescript
// Phase F에서 /sessions/{sessionId}에 기록할 데이터
{
  sessionId: uuid(),
  patientUid: qrToken에서 조회,
  staffUid: 현재 인증 UID,
  qrToken: patientToken,
  hospitalId: 'demo-hospital',
  status: 'navigating',
  currentWaypointIndex: 0,
  waypoints: activeWaypoints.map((poiId, i) => ({
    poiId,
    status: i === 0 ? 'current' : 'pending',
    arrivedAt: null,
  })),
  createdAt: Date.now(),
}
```

### 10.2 Phase F (Firebase) 연계

| 현재 (Phase D) | Phase F 이후 |
|---------------|-------------|
| QR 토큰 로컬 검증 | `/qr_tokens/{token}` 조회 + status 검증 |
| 세션 로컬 시뮬레이션 | `/sessions/{sessionId}` Realtime DB 쓰기 |
| 전송 성공 로컬 알림 | FCM 푸시 알림 발송 |
| 통계 하드코딩 | Realtime DB 실시간 집계 |

### 10.3 코드 스플리팅 고려

현재 번들 크기 627KB (gzip 187KB)는 html5-qrcode(~300KB)와 firebase(~200KB)가 주원인입니다. Phase G에서:

```typescript
// 의료진 페이지 동적 임포트
const StaffPage = lazy(() => import('@/pages/StaffPage'));
// html5-qrcode는 QRScanner 내부에서만 동적 임포트
```

---

*본 문서는 MediWay Phase D 구현 완료 시점의 기능 명세입니다.*
*Phase E(환자 UI)에서 동선 수신 측을, Phase F(Firebase)에서 실시간 전송 연동을 구현합니다.*
