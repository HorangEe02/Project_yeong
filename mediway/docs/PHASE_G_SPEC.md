# MediWay Phase G — 통합 + 테스트 + 배포 기능 설명서

> 작성일: 2026-04-16 | Phase G 구현 완료 시점 기준 (Phase 1 전체 완료)
> 빌드 결과: JS 920KB / CSS 20KB (gzip 후 ~281KB) | 테스트: 13/13 통과
> Firebase: mediway-demo 프로젝트 실시간 연동 완료

---

## 목차

1. [개요](#1-개요)
2. [PatientDashboard Firebase 완전 연동](#2-patientdashboard-firebase-완전-연동)
3. [Dual Mode 아키텍처 — Firebase vs 로컬](#3-dual-mode-아키텍처--firebase-vs-로컬)
4. [세션 복원 (새로고침 대응)](#4-세션-복원-새로고침-대응)
5. [E2E 플로우 — 의료진↔환자 실시간 연동](#5-e2e-플로우--의료진환자-실시간-연동)
6. [엣지 케이스 처리](#6-엣지-케이스-처리)
7. [알림 연동](#7-알림-연동)
8. [미사용 코드 정리](#8-미사용-코드-정리)
9. [빌드 및 테스트 결과](#9-빌드-및-테스트-결과)
10. [Phase 1 전체 아키텍처 요약](#10-phase-1-전체-아키텍처-요약)
11. [향후 개선 사항 (Phase 2 연계)](#11-향후-개선-사항-phase-2-연계)

---

## 1. 개요

### 1.1 Phase G의 목적

Phase G는 MediWay Phase 1의 **최종 통합 단계**입니다. Phase A~F에서 구현한 모든 컴포넌트(지도 렌더러, Dijkstra 경로 탐색, 의료진 UI, 환자 UI, Firebase 서비스)를 하나의 동작하는 E2E 플로우로 연결합니다.

### 1.2 Phase G에서 수행한 작업

| 작업 | 파일 | 설명 |
|------|------|------|
| **PatientDashboard 재작성** | `PatientDashboard.tsx` | 로컬 시뮬레이션 → Firebase `useSession` 훅 완전 연동 |
| **세션 복원** | `PatientDashboard.tsx` | localStorage 기반 QR 토큰/세션 ID 복원 |
| **알림 연동** | `PatientDashboard.tsx` | 동선 수신/다음 목적지/전체 완료 시 `NotificationMessages` 호출 |
| **미사용 코드 삭제** | `sessionStore.ts`, `navigationStore.ts` | Zustand 스토어 2개 삭제 (미사용) |
| **빌드 검증** | — | tsc + vitest + npm run build 전체 통과 |

### 1.3 핵심 성과

| 항목 | Phase F (이전) | Phase G (현재) |
|------|---------------|---------------|
| 의료진→환자 동선 전송 | Firebase DB에 세션 생성 ✅ | 변경 없음 (이미 동작) |
| 환자 동선 수신 | 로컬 시뮬레이션 버튼 | **Firebase 실시간 자동 수신** ✅ |
| "도착" 처리 | 로컬 state만 변경 | **Firebase DB 원자적 업데이트** ✅ |
| 세션 복원 | 미구현 | **localStorage 기반 복원** ✅ |
| 알림 | 미연동 | **동선 수신/전환/완료 알림** ✅ |
| 미사용 코드 | sessionStore, navigationStore 존재 | **삭제 완료** |

---

## 2. PatientDashboard Firebase 완전 연동

### 2.1 변경 전후 비교

**변경 전 (Phase E):**
```
PatientDashboard
├── useState로 waypoints, currentIndex 로컬 관리
├── handleSimulateReceive() — 하드코딩 데모 데이터
├── handleArrival() — setWaypoints 로컬 업데이트
└── "동선 수신 시뮬레이션" 버튼
```

**변경 후 (Phase G):**
```
PatientDashboard
├── useSession(qrToken) — Firebase 실시간 구독
│   ├── qrTokenData — QR 토큰 상태 감시
│   ├── session — 세션 데이터 실시간 반영
│   └── isConnected — Firebase 연결 상태
├── createQRToken(token, uid) — QR 생성 시 DB 등록
├── markWaypointArrived(sessionId, index, total) — DB 원자적 업데이트
├── localStorage 세션 복원
├── NotificationMessages 알림 연동
└── isFirebaseConfigured() 가드로 로컬 폴백 유지
```

### 2.2 Firebase 연동 데이터 흐름

```
QRDisplay
  │ onTokenGenerated(token)
  ▼
PatientDashboard.handleTokenGenerated
  ├── setQrToken(token) — 로컬 state
  ├── localStorage.setItem('mediway_qr_token', token)
  └── createQRToken(token, uid) — Firebase DB 등록
       │
       ▼
  /qr_tokens/{token} = { patientUid, status: "waiting", createdAt }
       │
       ▼
useSession(qrToken) → subscribeQRToken(token)
  │ onValue 리스너 활성
  │
  │ === 의료진이 QR 스캔 + 동선 전송 ===
  │
  ▼
qrTokenData.status === "matched"
  │ qrTokenData.sessionId 획득
  ▼
useSession 자동 전환 → subscribeSession(sessionId)
  │ onValue 리스너 활성
  ▼
session 데이터 수신
  ├── session.waypoints → waypoints 파생
  ├── session.currentWaypointIndex → currentIndex 파생
  ├── session.status → state 파생 ('navigating')
  └── computeRoute() → routeResult 계산
       │
       ▼
  지도 렌더링 + DestinationCard + RouteProgress 표시
       │
       ▼
  "도착" 버튼 클릭 → markWaypointArrived(sessionId, index, total)
       │
       ▼
  Firebase DB 원자적 업데이트
  → useSession이 변경 감지 → UI 자동 갱신
```

### 2.3 상태 파생 로직

Phase G에서는 로컬 state 대신 **Firebase 세션 데이터에서 상태를 파생**합니다:

```typescript
// waypoints: Firebase session에서 직접 파생
const waypoints = useMemo(() => {
  if (isLocalMode) return localWaypoints;
  if (!session?.waypoints) return [];
  return Array.isArray(session.waypoints)
    ? session.waypoints
    : Object.values(session.waypoints); // Firebase 배열→객체 정규화
}, [session?.waypoints]);

// currentIndex: Firebase session에서 직접 파생
const currentIndex = useMemo(() => {
  if (isLocalMode) return localCurrentIndex;
  return session?.currentWaypointIndex ?? 0;
}, [session?.currentWaypointIndex]);

// 상태 머신: sessionStatus에서 자동 파생
const state = useMemo(() => {
  if (sessionStatus === 'completed') return 'completed';
  if (sessionStatus === 'navigating' && waypoints.length > 0) return 'navigating';
  return 'qr_display';
}, [sessionStatus, waypoints]);
```

### 2.4 Firebase 배열 정규화

Firebase Realtime DB는 배열을 `{0: {...}, 1: {...}}` 형태의 객체로 저장할 수 있습니다. 이를 안전하게 처리합니다:

```typescript
return Array.isArray(session.waypoints)
  ? session.waypoints
  : Object.values(session.waypoints);
```

---

## 3. Dual Mode 아키텍처 — Firebase vs 로컬

### 3.1 모드 결정

```typescript
const [isLocalMode, setIsLocalMode] = useState(!isFirebaseConfigured());
```

| 조건 | 모드 | 동작 |
|------|------|------|
| `.env.local` 있음 + `VITE_FIREBASE_API_KEY` 설정 | **Firebase 모드** | 실시간 DB 연동 |
| `.env.local` 없음 또는 키 미설정 | **로컬 모드** | 시뮬레이션 버튼 폴백 |
| Firebase 모드에서 시뮬레이션 버튼 클릭 시 | **로컬 전환** | `setIsLocalMode(true)` |

### 3.2 모드별 핵심 함수 분기

| 함수 | Firebase 모드 | 로컬 모드 |
|------|-------------|----------|
| `handleTokenGenerated` | `createQRToken(token, uid)` DB 등록 | `setQrToken(token)` 만 |
| waypoints 소스 | `session.waypoints` (Firebase) | `localWaypoints` (useState) |
| currentIndex 소스 | `session.currentWaypointIndex` | `localCurrentIndex` |
| `handleArrival` | `markWaypointArrived()` DB 업데이트 | `setLocalWaypoints()` 로컬 업데이트 |
| 동선 수신 | `useSession` 자동 감지 | "시뮬레이션" 버튼 클릭 |

### 3.3 Firebase 연결 상태 UI

Firebase 모드에서 QR 대기 화면 하단에 연결 상태를 표시합니다:

```
● 서버 연결됨 — 의료진 스캔 대기 중     (초록 점)
● 서버 연결 중...                        (주황 점)
```

---

## 4. 세션 복원 (새로고침 대응)

### 4.1 localStorage 키

| 키 | 값 | 저장 시점 | 삭제 시점 |
|----|-----|---------|----------|
| `mediway_qr_token` | QR 토큰 UUID | QR 생성 시 | "새 동선 받기" 클릭 시 |
| `mediway_session_id` | 세션 UUID | 세션 수신 시 | "새 동선 받기" 클릭 시 |

### 4.2 복원 플로우

```
브라우저 새로고침
  │
  ├── localStorage에서 mediway_qr_token 읽기
  │     → qrToken 초기값으로 설정
  │
  ├── useSession(qrToken) 자동 실행
  │     → Firebase에서 QR 토큰 상태 확인
  │     → status === "matched"이면 세션 자동 구독
  │
  └── 세션 데이터 수신 → 이전 상태 복원
        → navigating 상태면 지도 + 경로 표시
        → completed 상태면 완료 화면 표시
```

### 4.3 초기화 (새 동선 받기)

```typescript
const handleReset = useCallback(() => {
  setQrToken(null);
  setLocalWaypoints([]);
  setLocalCurrentIndex(0);
  setRouteResult(null);
  setCurrentFloor(1);
  localStorage.removeItem(LS_QR_TOKEN);
  localStorage.removeItem(LS_SESSION_ID);
}, [setCurrentFloor]);
```

---

## 5. E2E 플로우 — 의료진↔환자 실시간 연동

### 5.1 전체 플로우 (Firebase 모드)

```
[탭 1: 환자 /patient]              [탭 2: 의료진 /staff]
        │                                   │
  1. 페이지 로드                              │
  2. 익명 인증 (signInAnonymously)            │
  3. QR 코드 생성 (uuid v4)                   │
  4. createQRToken(token, uid) → DB           │
  5. useSession(token) 구독 시작               │
  6. QR 화면 표시 + "스캔 대기 중"              │
        │                                   │
        │                          7. 페이지 로드
        │                          8. 익명 인증
        │                          9. QR 스캔 (수동 토큰 입력)
        │                         10. getQRToken(token) → 검증
        │                         11. 동선 템플릿 선택
        │                         12. "전송" 클릭
        │                         13. createSession(session) → DB
        │                         14. updateQRTokenStatus("matched") → DB
        │                                   │
  15. useSession 감지: status="matched"        │
  16. sessionId 추출 → 세션 구독               │
  17. session 데이터 수신                      │
  18. computeRoute() 경로 계산                 │
  19. state → "navigating"                    │
  20. 지도 + 경로 + 목적지 카드 표시            │
  21. NotificationMessages.routeReceived()    │
        │                                   │
  22. "도착" 버튼 클릭                          │
  23. markWaypointArrived() → DB               │
  24. useSession 감지: 경유지 업데이트          │
  25. 다음 목적지로 자동 전환                   │
  26. NotificationMessages.nextDestination()   │
        │                                   │
  (22~26 반복)                                │
        │                                   │
  27. 마지막 경유지 도착                        │
  28. session.status = "completed"             │
  29. 완료 화면 표시                            │
  30. NotificationMessages.allCompleted()      │
```

### 5.2 실시간 동기화 지점

| 단계 | DB 경로 | 변경 | 감지 측 |
|------|---------|------|--------|
| 14 | `/qr_tokens/{token}/status` | "waiting"→"matched" | 환자 (useSession Stage 1) |
| 13 | `/sessions/{sessionId}` | 세션 생성 | 환자 (useSession Stage 2) |
| 23 | `/sessions/{sid}/waypoints/{i}/status` | "current"→"completed" | 환자 (useSession 자동 감지) |
| 23 | `/sessions/{sid}/currentWaypointIndex` | i→i+1 | 환자 (useSession 자동 감지) |
| 27 | `/sessions/{sid}/status` | "navigating"→"completed" | 환자 (useSession 자동 감지) |

---

## 6. 엣지 케이스 처리

### 6.1 처리된 엣지 케이스

| 케이스 | 처리 방식 |
|--------|----------|
| **Firebase 미설정** | `isFirebaseConfigured()` 가드 → 로컬 시뮬레이션 모드 폴백 |
| **QR 매칭 대기 중 로딩** | `qrTokenData.status === "matched" && !session` → Loading 컴포넌트 표시 |
| **세션 없이 직접 /patient 접근** | qrToken 없음 → QR 표시 상태로 안내 |
| **브라우저 새로고침** | localStorage에서 qrToken 복원 → useSession 자동 재구독 |
| **Firebase 네트워크 끊김→복구** | onValue 리스너가 자동 재연결 (Firebase SDK 내장) |
| **Firebase 배열→객체 변환** | `Object.values()` 정규화 처리 |
| **알림 미지원 브라우저** | `showLocalNotification()`이 `Notification.permission` 확인 후 안전하게 실행 |

### 6.2 향후 처리 필요 (Phase 2)

| 케이스 | 현재 상태 | 필요 작업 |
|--------|----------|----------|
| QR 토큰 3분 만료 | 클라이언트 갱신만 | DB에서도 status→"expired" 처리 |
| 세션 24시간 TTL | 미구현 | Cloud Functions 또는 클라이언트 정리 |
| 동일 QR 중복 스캔 | `getQRToken` status 확인 | 충돌 시 사용자 안내 강화 |
| 오프라인 "도착" 큐잉 | 미구현 | 오프라인 큐 + 재접속 시 일괄 전송 |

---

## 7. 알림 연동

### 7.1 알림 발송 시점

| 시점 | 함수 호출 | 메시지 |
|------|----------|--------|
| 동선 최초 수신 | `NotificationMessages.routeReceived()` | "다음 목적지가 등록되었습니다" |
| 다음 목적지 전환 | `NotificationMessages.nextDestination(name)` | "다음 목적지 — {name}" |
| 모든 동선 완료 | `NotificationMessages.allCompleted()` | "오늘 진료가 모두 끝났습니다" |

### 7.2 알림 호출 위치

```typescript
// 동선 수신 시 (Firebase 모드)
useEffect(() => {
  if (!isLocalMode && session?.status === 'navigating' && routeResult && currentIndex === 0) {
    NotificationMessages.routeReceived();
  }
}, [session?.status, routeResult, currentIndex]);

// "도착" 클릭 시
const handleArrival = useCallback(async () => {
  // ... DB 업데이트 ...
  if (nextIdx < waypoints.length) {
    NotificationMessages.nextDestination(nextPoi?.name ?? '');
  } else {
    NotificationMessages.allCompleted();
  }
}, [...]);
```

---

## 8. 미사용 코드 정리

### 8.1 삭제된 파일

| 파일 | 삭제 이유 |
|------|----------|
| `stores/sessionStore.ts` | PatientDashboard가 `useSession` 훅 + 로컬 state로 처리, Zustand 스토어 미사용 |
| `stores/navigationStore.ts` | PatientDashboard가 `useMemo`로 경로 계산 결과 관리, Zustand 스토어 미사용 |

### 8.2 유지된 스토어

| 파일 | 사용처 | 역할 |
|------|--------|------|
| `stores/mapStore.ts` | HospitalMapContainer, PatientDashboard | 현재 층, 렌더러 타입, 선택된 POI |

### 8.3 최종 디렉토리 구조 (stores/)

```
stores/
└── mapStore.ts    ← 유일한 Zustand 스토어
```

---

## 9. 빌드 및 테스트 결과

### 9.1 타입 체크

```bash
npx tsc --noEmit
# ✅ 에러 없음
```

### 9.2 단위 테스트

```bash
npx vitest run
# ✅ 13/13 테스트 통과 (4ms)
#
# Test Files  1 passed (1)
#     Tests  13 passed (13)
#  Duration  826ms
```

### 9.3 프로덕션 빌드

```bash
npm run build
# ✅ 빌드 성공
#
# dist/index.html                    0.45 kB │ gzip:   0.29 kB
# dist/assets/index-C_Cj7UCJ.css   20.16 kB │ gzip:   4.55 kB
# dist/assets/index-BhWNmS4a.js   919.97 kB │ gzip: 276.11 kB
```

### 9.4 번들 크기 분석

| 라이브러리 | 추정 크기 | 비고 |
|-----------|----------|------|
| Firebase SDK | ~350KB | Auth + Realtime DB + Messaging |
| html5-qrcode | ~280KB | QR 스캐너 (의료진 전용) |
| React + React DOM | ~140KB | 프레임워크 |
| react-zoom-pan-pinch | ~40KB | SVG 줌/패닝 |
| Leaflet + react-leaflet | ~40KB | (설치됨, 미사용 — 트리쉐이킹 대상) |
| 기타 (Zustand, Lucide 등) | ~70KB | |

> 향후 코드 스플리팅(`React.lazy`)으로 의료진/환자 페이지를 분리하면 초기 로드 크기를 ~50% 줄일 수 있습니다.

---

## 10. Phase 1 전체 아키텍처 요약

### 10.1 전체 파일 수

| 카테고리 | 파일 수 | 주요 파일 |
|---------|--------|----------|
| 타입 정의 | 6 | hospital, floor-plan, navigation, session, route-template, map-renderer |
| 데이터 | 8 | POI 31개, 평면도 4층, 네비게이션 그래프, 동선 템플릿 6개 |
| 서비스 | 4 | pathfinding, auth, session, notification |
| 훅 | 4 | useSession, useQRScanner, useNotification, (useFloorPlan 미생성) |
| 스토어 | 1 | mapStore |
| 지도 컴포넌트 | 12 | 추상화 레이어 4 + SVG 레이어 7 + 스타일 1 |
| 의료진 컴포넌트 | 5 | StaffDashboard, QRScanner, RouteTemplateList, RouteBuilder, SendConfirm |
| 환자 컴포넌트 | 6 | PatientDashboard, QRDisplay, DestinationCard, RouteProgress, ArrivalButton, CompletionScreen |
| 공통 컴포넌트 | 2 | Header, Loading |
| 페이지 | 3 | LandingPage, StaffPage, PatientPage |
| 유틸리티 | 1 | distance |
| 설정 | 5 | firebase.ts, .env.local, vite.config, tailwind.config, vitest.config |
| Firebase | 3 | database.rules.json, firebase.json, firebase-messaging-sw.js |
| **합계** | **~60** | |

### 10.2 기술 스택 최종

| 영역 | 기술 | 버전 |
|------|------|------|
| 프레임워크 | React | 18.x |
| 언어 | TypeScript | 5.x |
| 빌드 | Vite | 8.x |
| 스타일링 | Tailwind CSS | 3.x |
| 상태 관리 | Zustand | 4.x (mapStore만) |
| 라우팅 | React Router | 6.x |
| 인증 | Firebase Auth (Anonymous) | 10.x |
| 실시간 DB | Firebase Realtime Database | 10.x |
| 푸시 알림 | Firebase Cloud Messaging | 10.x |
| 실내 지도 | react-zoom-pan-pinch + 동적 SVG | 3.x |
| QR 생성 | qrcode.react | 3.x |
| QR 스캔 | html5-qrcode | 2.x |
| 아이콘 | Lucide React | 0.x |
| 테스트 | Vitest | 1.x |

### 10.3 데이터 흐름 전체도

```
┌─────────────────────────────────────────────────────┐
│                    Firebase                          │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Auth   │  │ Realtime DB  │  │     FCM      │  │
│  │ Anonymous │  │  /qr_tokens  │  │ Web Push     │  │
│  │          │  │  /sessions   │  │              │  │
│  └────┬─────┘  └──────┬───────┘  └──────┬───────┘  │
└───────┼───────────────┼─────────────────┼───────────┘
        │               │                 │
   auth.ts         session.ts      notification.ts
        │               │                 │
        ├───────────────┤                 │
        ▼               ▼                 ▼
   ┌─────────┐   ┌───────────┐   ┌──────────────┐
   │ App.tsx  │   │useSession │   │useNotification│
   │initAuth  │   │  hook     │   │   hook       │
   └─────────┘   └─────┬─────┘   └──────────────┘
                        │
           ┌────────────┴────────────┐
           ▼                         ▼
   StaffDashboard            PatientDashboard
   ├── QRScanner             ├── QRDisplay
   ├── RouteTemplateList     ├── RouteProgress
   ├── RouteBuilder          ├── DestinationCard
   ├── SendConfirm           ├── ArrivalButton
   │                         ├── CompletionScreen
   │                         └── HospitalMapContainer
   │                              ├── FloorSelector
   │                              └── MapRenderer
   │                                   └── SvgNativeMapRenderer
   │                                        ├── BuildingOutline
   │                                        ├── CorridorLayer
   │                                        ├── RoomLayer
   │                                        ├── WallLayer
   │                                        ├── DoorLayer
   │                                        ├── PathOverlay ← pathfinding.ts
   │                                        └── POIMarkerLayer
   │
   └── pathfinding.ts (Dijkstra) ← navigation-graph.ts
```

---

## 11. 향후 개선 사항 (Phase 2 연계)

### 11.1 즉시 개선 가능

| 항목 | 작업 | 효과 |
|------|------|------|
| 코드 스플리팅 | `React.lazy()` 페이지 분리 | 초기 로드 ~50% 감소 |
| Leaflet 렌더러 | Phase B에서 준비된 추상화에 구현체 추가 | 지도 UX 향상 |
| FCM VAPID 키 | Firebase Console에서 발급 후 .env.local 추가 | 백그라운드 푸시 활성화 |
| QR 토큰 DB 만료 | Cloud Functions 또는 클라이언트 타이머 | 보안 강화 |

### 11.2 Phase 2 연계

| Phase 1 자산 | Phase 2 활용 |
|-------------|-------------|
| Firebase 인프라 | iOS/Android Firebase SDK로 동일 DB 접근 |
| 네비게이션 그래프 구조 | BLE 비콘 노드 추가, 실시간 위치 추적 |
| 세션 데이터 모델 | 실시간 위치 필드 추가 (`currentLocation`) |
| Dijkstra 알고리즘 | Swift/Kotlin 이식 또는 서버 사이드 이동 |
| SVG 좌표계 | 실제 미터 좌표 변환 레이어 추가 |
| 보안 규칙 | 병원별 다중 테넌시 규칙 확장 |

---

*본 문서는 MediWay Phase 1 전체 구현 완료 시점의 최종 기능 명세입니다.*
*Phase A~G 문서는 `mediway/docs/` 폴더에 개별 보관되어 있습니다:*
- `PHASE_A_SPEC.md` — 프로젝트 기초 + 타입 + 데이터
- `PHASE_B_SPEC.md` — 지도 추상화 + SVG 렌더러
- `PHASE_C_SPEC.md` — Dijkstra 경로 탐색
- `PHASE_D_SPEC.md` — 의료진 UI
- `PHASE_E_SPEC.md` — 환자 UI
- `PHASE_F_SPEC.md` — Firebase 통합 + 연동 검증
- `PHASE_G_SPEC.md` — 통합 + 테스트 + 배포 (본 문서)
