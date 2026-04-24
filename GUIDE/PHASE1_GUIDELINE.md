# MediWay Phase 1 — 웹 데모 구현 가이드라인

> Claude Code를 활용한 단계별 구현 지침서
> 예상 기간: 4~6주 | 난이도: ★★☆☆☆

---

## 목차

1. [Phase 1 목표 및 범위](#1-phase-1-목표-및-범위)
2. [기술 스택 및 의존성](#2-기술-스택-및-의존성)
3. [프로젝트 구조](#3-프로젝트-구조)
4. [Week 1-2: 프로젝트 셋업 및 핵심 백엔드](#4-week-1-2-프로젝트-셋업-및-핵심-백엔드)
5. [Week 3-4: 의료진 웹 UI](#5-week-3-4-의료진-웹-ui)
6. [Week 4-5: 환자 웹 UI](#6-week-4-5-환자-웹-ui)
7. [Week 5-6: 푸시 알림, 테스트, 배포](#7-week-5-6-푸시-알림-테스트-배포)
8. [데이터 모델 상세](#8-데이터-모델-상세)
9. [병원 지도 데이터 명세](#9-병원-지도-데이터-명세)
10. [경로 탐색 알고리즘](#10-경로-탐색-알고리즘)
11. [보안 및 개인정보보호](#11-보안-및-개인정보보호)
12. [테스트 전략](#12-테스트-전략)
13. [배포 및 환경 설정](#13-배포-및-환경-설정)
14. [Phase 2 연계 고려사항](#14-phase-2-연계-고려사항)

---

## 1. Phase 1 목표 및 범위

### 1.1 핵심 목표

Phase 1은 MediWay의 **핵심 가치를 검증하는 웹 기반 데모**입니다. 실제 병원 환경이 아닌 **가상 병원 데이터**를 사용하여, "의료진이 환자에게 동선을 전송하고, 환자가 2D 지도에서 경로를 확인하는" 전체 플로우를 웹에서 시연할 수 있어야 합니다.

### 1.2 구현 범위 (In-Scope)

- 의료진 웹: QR 스캔 → 동선 템플릿 선택 → 환자에게 전송
- 환자 웹: 동선 수신 → 2D 평면도 지도에서 경로 확인 → 단계별 진행
- QR 기반 세션 매칭 (비회원 사용 가능)
- Firebase Realtime DB를 통한 실시간 동선 전송
- 가상 병원 평면도 SVG (본관 1~4층)
- 정적 경로 안내 (사전 정의된 경로 하이라이트)
- 환자 수동 "도착" 확인 버튼
- 웹 푸시 알림 (FCM)
- 반응형 웹 (모바일 브라우저 최적화)

### 1.3 구현 범위 밖 (Out-of-Scope)

- 실시간 위치 추적 (BLE/Wi-Fi/GPS)
- AR 네비게이션
- 턴바이턴 음성 안내
- 주차 위치 기록 및 정산
- 실제 병원 데이터 연동
- 네이티브 앱 (iOS/Android)
- 다국어 지원
- 환자 회원가입 / 로그인 (익명 인증만 사용)

### 1.4 데모 시나리오

Phase 1 데모에서 시연할 핵심 시나리오는 다음과 같습니다.

```
[데모 시나리오 — 약 3분 시연]

1. 환자 웹을 열면 QR코드가 자동 생성됨 (세션 대기 상태)
2. 의료진 웹에서 해당 QR코드를 스캔
3. 의료진이 "채혈실 → 원무과 → 약국 → 귀가" 템플릿 선택
4. "전송" 버튼 클릭
5. 환자 웹에 실시간으로 동선 수신, 첫 번째 목적지(채혈실) 경로가 지도에 표시
6. 환자가 "도착" 버튼 클릭 → 다음 목적지(원무과)로 자동 전환
7. 반복하여 모든 동선 완료 → "오늘 진료가 모두 끝났습니다" 표시
```

---

## 2. 기술 스택 및 의존성

### 2.1 핵심 기술 스택

```
영역              기술                      버전(권장)
─────────────────────────────────────────────────────
프레임워크         React                     18.x
언어              TypeScript                5.x
빌드 도구          Vite                      5.x
상태 관리          Zustand                   4.x
라우팅             React Router              6.x
실시간 통신        Firebase Realtime DB       9.x (modular SDK)
인증              Firebase Auth              9.x
푸시 알림          Firebase Cloud Messaging   9.x
실내 지도          Leaflet.js                1.9.x
QR 코드 생성       qrcode.react              3.x
QR 코드 스캔       html5-qrcode              2.x
UI 컴포넌트        Tailwind CSS              3.x
아이콘             Lucide React              0.x
HTTP 클라이언트    내장 fetch API              -
배포              Vercel                     -
```

### 2.2 npm 의존성 목록

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "firebase": "^10.7.0",
    "leaflet": "^1.9.4",
    "react-leaflet": "^4.2.1",
    "qrcode.react": "^3.1.0",
    "html5-qrcode": "^2.3.8",
    "zustand": "^4.4.0",
    "lucide-react": "^0.294.0",
    "uuid": "^9.0.0"
  },
  "devDependencies": {
    "typescript": "^5.3.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@types/leaflet": "^1.9.0",
    "@types/uuid": "^9.0.0",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "vite": "^5.0.0",
    "@vitejs/plugin-react": "^4.2.0",
    "vitest": "^1.0.0",
    "@testing-library/react": "^14.1.0",
    "eslint": "^8.55.0",
    "prettier": "^3.1.0"
  }
}
```

### 2.3 Firebase 프로젝트 설정

```
필요한 Firebase 서비스:
  1. Authentication — Anonymous 인증 활성화
  2. Realtime Database — 세션 및 동선 데이터 실시간 동기화
  3. Cloud Messaging (FCM) — 웹 푸시 알림
  4. Hosting — (선택) Firebase Hosting 또는 Vercel 사용

Firebase 프로젝트 생성 순서:
  1. Firebase Console에서 프로젝트 생성 (mediway-demo)
  2. 웹 앱 등록 → firebaseConfig 복사
  3. Authentication > 로그인 방법 > 익명 인증 활성화
  4. Realtime Database > 생성 (asia-southeast1 또는 가까운 리전)
  5. Cloud Messaging > 웹 푸시 인증서 생성 (VAPID key)
```

---

## 3. 프로젝트 구조

### 3.1 디렉토리 구조

```
mediway/
├── public/
│   ├── firebase-messaging-sw.js    # FCM Service Worker
│   ├── hospital-maps/              # 병원 평면도 SVG 파일
│   │   ├── demo-hospital-1F.svg
│   │   ├── demo-hospital-2F.svg
│   │   ├── demo-hospital-3F.svg
│   │   └── demo-hospital-4F.svg
│   └── index.html
├── src/
│   ├── main.tsx                    # 앱 엔트리
│   ├── App.tsx                     # 라우터 설정
│   ├── config/
│   │   └── firebase.ts             # Firebase 초기화 설정
│   ├── types/
│   │   ├── hospital.ts             # Hospital, Building, Floor, POI 타입
│   │   ├── session.ts              # Session, Route 타입
│   │   └── navigation.ts           # NavigationGraph, Edge 타입
│   ├── data/
│   │   ├── demo-hospital.ts        # 가상 병원 데이터 (POI, 층 정보)
│   │   ├── route-templates.ts      # 사전 정의 동선 템플릿
│   │   └── navigation-graph.ts     # POI 간 연결 그래프
│   ├── stores/
│   │   ├── sessionStore.ts         # 세션 상태 (Zustand)
│   │   └── navigationStore.ts      # 네비게이션 상태 (Zustand)
│   ├── services/
│   │   ├── auth.ts                 # Firebase Anonymous Auth
│   │   ├── session.ts              # 세션 생성/조회/삭제 (Realtime DB)
│   │   ├── notification.ts         # FCM 푸시 알림
│   │   └── pathfinding.ts          # 최단 경로 계산 (Dijkstra)
│   ├── hooks/
│   │   ├── useSession.ts           # 세션 실시간 구독
│   │   ├── useQRScanner.ts         # QR 스캐너 훅
│   │   └── useNotification.ts      # 푸시 알림 권한 및 수신
│   ├── components/
│   │   ├── common/
│   │   │   ├── Header.tsx
│   │   │   ├── Loading.tsx
│   │   │   ├── StepIndicator.tsx   # 동선 진행률 표시 (● ─ ○ ─ ○)
│   │   │   └── Toast.tsx
│   │   ├── staff/
│   │   │   ├── QRScanner.tsx       # QR 코드 스캐너 (카메라)
│   │   │   ├── RouteTemplateList.tsx # 동선 템플릿 목록
│   │   │   ├── RouteBuilder.tsx    # 커스텀 동선 편집기
│   │   │   ├── SendConfirm.tsx     # 전송 확인 모달
│   │   │   └── StaffDashboard.tsx  # 의료진 메인 화면
│   │   ├── patient/
│   │   │   ├── QRDisplay.tsx       # 환자 QR 코드 표시
│   │   │   ├── HospitalMap.tsx     # Leaflet + SVG 지도
│   │   │   ├── FloorSelector.tsx   # 층 선택 탭
│   │   │   ├── RouteOverlay.tsx    # 경로 하이라이트 오버레이
│   │   │   ├── DestinationCard.tsx # 다음 목적지 카드
│   │   │   ├── RouteProgress.tsx   # 동선 진행률 바
│   │   │   ├── ArrivalButton.tsx   # "도착" 확인 버튼
│   │   │   ├── CompletionScreen.tsx # 모든 동선 완료 화면
│   │   │   └── PatientDashboard.tsx # 환자 메인 화면
│   │   └── map/
│   │       ├── IndoorMap.tsx       # Leaflet 지도 래퍼
│   │       ├── SVGFloorPlan.tsx    # SVG 평면도 오버레이
│   │       ├── POIMarker.tsx       # 관심 지점 마커
│   │       └── PathLine.tsx        # 경로 선 렌더링
│   ├── pages/
│   │   ├── StaffPage.tsx           # /staff — 의료진 페이지
│   │   ├── PatientPage.tsx         # /patient — 환자 페이지
│   │   └── LandingPage.tsx         # / — 랜딩 (역할 선택)
│   └── utils/
│       ├── qr.ts                   # QR 토큰 생성 유틸
│       └── distance.ts             # 거리 계산, 소요시간 추정
├── .env.local                      # Firebase 환경변수
├── tailwind.config.js
├── tsconfig.json
├── vite.config.ts
└── package.json
```

### 3.2 라우팅 설계

```
/                    → LandingPage (역할 선택: 의료진 / 환자)
/staff               → StaffPage (의료진 대시보드)
/patient             → PatientPage (QR 표시 → 동선 수신 대기)
/patient/:sessionId  → PatientPage (특정 세션의 동선 안내)
```

---

## 4. Week 1-2: 프로젝트 셋업 및 핵심 백엔드

### 4.1 Task 목록

```
W1-D1~D2: 프로젝트 초기화
  □ Vite + React + TypeScript 프로젝트 생성
  □ Tailwind CSS 설정
  □ ESLint + Prettier 설정
  □ 디렉토리 구조 생성
  □ React Router 설정 (3개 라우트)
  □ 기본 레이아웃 컴포넌트 (Header, Loading)

W1-D3~D4: Firebase 설정
  □ Firebase 프로젝트 생성 및 웹 앱 등록
  □ firebase.ts 초기화 파일 작성
  □ .env.local에 Firebase config 저장
  □ Anonymous Auth 연동 및 테스트
  □ Realtime DB 보안 규칙 작성
  □ FCM VAPID key 생성 및 Service Worker 설정

W1-D5 ~ W2-D2: 데이터 모델 및 시드 데이터
  □ TypeScript 타입 정의 (hospital.ts, session.ts, navigation.ts)
  □ 가상 병원 데이터 작성 (demo-hospital.ts)
  □ 동선 템플릿 데이터 작성 (route-templates.ts)
  □ 네비게이션 그래프 데이터 작성 (navigation-graph.ts)
  □ 가상 병원 SVG 평면도 4개 층 제작

W2-D3~D5: QR 세션 매칭 핵심 로직
  □ QR 토큰 생성 로직 (uuid v4 기반)
  □ 세션 생성 서비스 (Realtime DB에 세션 쓰기)
  □ 세션 실시간 구독 훅 (onValue 리스너)
  □ 세션 상태 머신 (waiting → navigating → completed)
  □ 세션 TTL 관리 (24시간 후 자동 만료)
  □ 의료진-환자 세션 연결 테스트
```

### 4.2 Firebase 초기화 코드 구조

```typescript
// src/config/firebase.ts

import { initializeApp } from 'firebase/app';
import { getAuth, signInAnonymously } from 'firebase/auth';
import { getDatabase } from 'firebase/database';
import { getMessaging } from 'firebase/messaging';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  databaseURL: import.meta.env.VITE_FIREBASE_DATABASE_URL,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getDatabase(app);
export const messaging = getMessaging(app);

// 익명 인증 자동 실행
export const initAuth = () => signInAnonymously(auth);
```

### 4.3 Realtime DB 보안 규칙

```json
{
  "rules": {
    "sessions": {
      "$sessionId": {
        // 세션 생성: 인증된 사용자만 가능
        ".write": "auth != null",
        // 세션 읽기: 세션의 참여자만 가능
        ".read": "auth != null && (
          data.child('staffUid').val() === auth.uid ||
          data.child('patientUid').val() === auth.uid
        )"
      }
    },
    "qr_tokens": {
      "$token": {
        // QR 토큰 생성: 인증된 사용자
        ".write": "auth != null",
        // QR 토큰 읽기: 누구나 (스캔을 위해)
        ".read": "auth != null"
      }
    },
    // 병원 데이터는 읽기 전용
    "hospitals": {
      ".read": true,
      ".write": false
    }
  }
}
```

### 4.4 QR 세션 매칭 플로우 상세

```
[환자 웹 접속]
    │
    ├── 1. 익명 인증 (signInAnonymously)
    │       → auth.uid 획득 (예: "patient_abc123")
    │
    ├── 2. QR 토큰 생성
    │       → token = uuid.v4() (예: "a1b2c3d4-...")
    │       → DB: /qr_tokens/{token} = { patientUid, createdAt, status: "waiting" }
    │
    ├── 3. QR 코드 화면에 표시
    │       → QR 내용: "https://mediway.app/session?token={token}"
    │       → 또는 단순히 token 문자열
    │
    └── 4. 세션 생성 대기 (onValue 리스너)
            → /qr_tokens/{token}/status 가 "matched"로 변경되면
            → /sessions/{sessionId} 구독 시작

[의료진 웹 QR 스캔]
    │
    ├── 1. 익명 인증 (signInAnonymously)
    │       → auth.uid 획득 (예: "staff_xyz789")
    │
    ├── 2. QR 코드 스캔
    │       → html5-qrcode로 카메라 실행
    │       → token 값 획득
    │
    ├── 3. QR 토큰 검증
    │       → DB: /qr_tokens/{token} 읽기
    │       → status === "waiting" 확인
    │       → patientUid 획득
    │
    ├── 4. 동선 선택 UI 표시
    │       → 템플릿 목록 표시 또는 커스텀 경로 편집
    │
    └── 5. 세션 생성 및 전송
            → sessionId = uuid.v4()
            → DB: /sessions/{sessionId} = {
                 staffUid, patientUid, 
                 route: { waypoints: [...], currentIndex: 0 },
                 status: "navigating",
                 createdAt
               }
            → DB: /qr_tokens/{token}/status = "matched"
            → DB: /qr_tokens/{token}/sessionId = sessionId
            → FCM 푸시 발송 (선택)
```

---

## 5. Week 3-4: 의료진 웹 UI

### 5.1 Task 목록

```
W3-D1~D2: QR 스캐너 컴포넌트
  □ html5-qrcode 라이브러리 통합
  □ 카메라 권한 요청 처리 (HTTPS 필수)
  □ QR 스캔 성공 시 토큰 추출 및 검증
  □ 스캔 실패/권한 거부 시 에러 처리
  □ 수동 토큰 입력 폴백 UI (카메라 없는 경우)

W3-D3~D4: 동선 템플릿 UI
  □ RouteTemplateList 컴포넌트 — 사전 정의 템플릿 카드 목록
  □ 템플릿 선택 시 경유지 목록 미리보기
  □ 템플릿 색상/아이콘 구분 (진료과별)
  □ 선택 상태 하이라이트

W3-D5 ~ W4-D1: 커스텀 경로 편집기
  □ RouteBuilder 컴포넌트 — POI 검색 및 추가
  □ POI 카테고리 필터 (진료실/검사실/원무과/약국)
  □ 드래그앤드롭 순서 변경 (또는 ↑↓ 버튼)
  □ 경유지 삭제 기능
  □ "귀가" 자동 마지막 단계 추가

W4-D2~D3: 전송 플로우
  □ SendConfirm 모달 — 최종 확인
  □ 환자 이름/세션 정보 표시
  □ "전송" 버튼 클릭 → Realtime DB 쓰기
  □ 전송 성공/실패 토스트 알림
  □ 전송 완료 후 초기 화면 복귀

W4-D4~D5: 의료진 UI 마무리
  □ StaffDashboard 레이아웃 통합
  □ 반응형 디자인 (태블릿/모바일)
  □ 로딩 상태, 에러 상태 처리
  □ 접근성 기본 사항 (aria-label, 키보드 탐색)
```

### 5.2 의료진 UI 컴포넌트 명세

#### StaffDashboard.tsx — 메인 화면

```
상태 머신:
  idle         → QR 스캔 버튼 표시
  scanning     → 카메라 활성, QR 스캔 중
  scanned      → 환자 매칭 완료, 동선 선택 UI 표시
  selecting    → 템플릿 선택 또는 커스텀 경로 편집 중
  confirming   → 전송 확인 모달 표시
  sent         → 전송 완료 상태 (3초 후 idle 복귀)
  error        → 에러 표시 (재시도 버튼)

Props: 없음 (전역 상태 사용)

주요 액션:
  - onScanSuccess(token: string) → 토큰 검증 → scanned 전환
  - onSelectTemplate(template: RouteTemplate) → confirming 전환
  - onCustomRoute(waypoints: POI[]) → confirming 전환
  - onSendConfirm() → 세션 생성 → sent 전환
  - onSendCancel() → selecting 복귀
```

#### QRScanner.tsx — QR 스캐너

```
기능:
  - 브라우저 카메라 접근 (getUserMedia)
  - html5-qrcode 라이브러리로 QR 디코딩
  - 스캔 성공 시 콜백 호출
  - 카메라 미지원 시 수동 입력 폴백

Props:
  - onScanSuccess: (token: string) => void
  - onScanError?: (error: string) => void

주의사항:
  - HTTPS 환경에서만 카메라 접근 가능
  - 컴포넌트 언마운트 시 카메라 스트림 반드시 해제
  - iOS Safari에서 카메라 권한 처리 별도 확인 필요
```

#### RouteTemplateList.tsx — 동선 템플릿 목록

```
기능:
  - 진료과별 빈번 동선 템플릿 카드 렌더링
  - 선택 시 경유지 상세 표시
  - 색상 코드로 카테고리 구분

Props:
  - templates: RouteTemplate[]
  - selectedId: string | null
  - onSelect: (template: RouteTemplate) => void

템플릿 카드 UI:
  ┌─────────────────────────────────┐
  │ 🔵 채혈실 → 원무과 → 약국 → 귀가  │
  │    4단계 | 예상 15분              │
  └─────────────────────────────────┘
```

---

## 6. Week 4-5: 환자 웹 UI

### 6.1 Task 목록

```
W4-D4 ~ W5-D1: QR 코드 및 세션 대기 화면
  □ QRDisplay 컴포넌트 — qrcode.react로 QR 생성
  □ QR 토큰 자동 생성 (페이지 로드 시)
  □ "QR 코드를 간호사에게 보여주세요" 안내 문구
  □ 세션 매칭 대기 애니메이션
  □ 매칭 완료 시 자동으로 네비게이션 화면 전환

W5-D1~D3: 2D 실내 지도
  □ IndoorMap — Leaflet CRS.Simple 설정 (비지리적 좌표계)
  □ SVGFloorPlan — SVG 평면도를 Leaflet ImageOverlay로 렌더링
  □ FloorSelector — 층 선택 탭 (1F/2F/3F/4F)
  □ POIMarker — 주요 장소 마커 (아이콘 + 라벨)
  □ PathLine — 출발지-목적지 경로 폴리라인 렌더링
  □ 경로 색상: 진행 완료(회색), 현재 구간(파란색 애니메이션)

W5-D3~D4: 동선 안내 UI
  □ DestinationCard — 다음 목적지 정보 카드
  □ RouteProgress — 전체 동선 진행률 (● ─ ○ ─ ○ ─ ○)
  □ ArrivalButton — "도착했습니다" 확인 버튼
  □ 도착 확인 시 다음 경유지로 자동 전환
  □ 층 이동 안내 ("엘리베이터를 타고 3층으로 이동하세요")
  □ CompletionScreen — 모든 동선 완료 화면

W5-D5: 환자 UI 마무리
  □ PatientDashboard 레이아웃 통합
  □ 반응형 디자인 (모바일 우선)
  □ 빈 상태 처리 (동선 없음, 세션 만료)
  □ 새로고침 시 세션 복원 (localStorage에 sessionId 임시 저장)
```

### 6.2 Leaflet 실내 지도 구현 가이드

#### 핵심: CRS.Simple 사용

병원 평면도는 GPS 좌표가 아닌 **픽셀 좌표**를 사용하므로, Leaflet의 `CRS.Simple`을 설정해야 합니다.

```typescript
// 기본 설정 구조
const MAP_CONFIG = {
  // SVG 평면도의 크기 (픽셀)
  width: 1200,
  height: 800,
  // Leaflet bounds (좌하단, 우상단)
  bounds: [[0, 0], [800, 1200]] as L.LatLngBoundsExpression,
  // 초기 줌 레벨
  defaultZoom: 0,
  minZoom: -2,
  maxZoom: 3,
};

// IndoorMap 컴포넌트에서:
// - CRS: L.CRS.Simple
// - ImageOverlay로 SVG 렌더링
// - bounds를 SVG 크기에 맞춤
// - POI 좌표는 SVG 좌표계 기준 (x, y) → Leaflet [y, x]로 변환
```

#### SVG 평면도 제작 지침

```
가상 병원 "MediWay 데모 병원" 설정:

건물: 본관 (4층)

1층: 로비, 원무과, 외래약국, 편의점, 주차장 연결
2층: 내과, 외과, 소아과, 채혈실
3층: 영상의학과(CT/MRI), 정형외과, 재활의학과
4층: 건강검진센터, 회의실, 행정실

각 층 SVG 포함 요소:
  - 벽/통로 (기본 건물 구조)
  - 방 라벨 (진료실 번호, 부서명)
  - 엘리베이터 위치 (2개소)
  - 계단 위치 (2개소)
  - 화장실 위치
  - POI 좌표 앵커 포인트 (각 POI에 id 속성 부여)

SVG 제작 방법 (우선순위 순):
  1. Figma에서 설계 후 SVG 내보내기
  2. 직접 SVG 코드로 작성 (격자 기반 단순화)
  3. draw.io/diagrams.net 활용

SVG 컨벤션:
  - viewBox="0 0 1200 800"
  - POI 위치에 <circle> 또는 <rect>에 data-poi-id 속성 부여
  - 통로는 <path>로 표현, 클래스명 corridor
  - 방은 <rect>로 표현, 클래스명 room
```

### 6.3 환자 UI 컴포넌트 명세

#### PatientDashboard.tsx — 메인 화면

```
상태 머신:
  qr_display     → QR 코드 표시, 세션 대기
  connecting     → 의료진이 QR 스캔, 매칭 중
  navigating     → 동선 안내 중 (지도 + 목적지 카드)
  floor_change   → 층 이동 안내 화면
  arriving       → "도착" 확인 대기
  completed      → 모든 동선 완료

Props: 없음 (전역 상태 사용)
```

#### HospitalMap.tsx — 지도 영역

```
기능:
  - Leaflet MapContainer (CRS.Simple)
  - 현재 층의 SVG 평면도 표시
  - 출발지 마커 (파란 점)
  - 목적지 마커 (빨간 점)
  - 경로 폴리라인 (파란 점선 애니메이션)
  - 경유지 마커 (작은 회색 점)
  - POI 라벨 (주요 장소명)

Props:
  - currentFloor: number
  - startPOI: POI
  - endPOI: POI
  - path: Coordinate[]     // 경로 좌표 배열
  - allPOIs: POI[]          // 현재 층의 모든 POI

특이사항:
  - SVG 좌표 → Leaflet 좌표 변환 필요 ([x, y] → [y, x])
  - 층 변경 시 SVG ImageOverlay 교체
  - 핀치 줌, 드래그 지원
  - 경로가 여러 층에 걸칠 경우 현재 층 구간만 표시
```

#### RouteProgress.tsx — 진행률 표시

```
UI 렌더링:
  ● ── ○ ── ○ ── ○
  내과   채혈실  원무과  약국

  ● = 완료된 경유지 (초록)
  ◉ = 현재 진행 중 (파란, 펄스 애니메이션)
  ○ = 아직 방문하지 않은 경유지 (회색)

Props:
  - waypoints: { poi: POI; status: 'completed' | 'current' | 'pending' }[]
  - onWaypointClick?: (index: number) => void  // 탭 시 해당 경로 미리보기
```

---

## 7. Week 5-6: 푸시 알림, 테스트, 배포

### 7.1 Task 목록

```
W5-D5 ~ W6-D1: 웹 푸시 알림 (FCM)
  □ Service Worker 등록 (firebase-messaging-sw.js)
  □ 알림 권한 요청 UI
  □ FCM 토큰 획득 및 세션에 저장
  □ 동선 전송 시 푸시 발송 (Functions 또는 클라이언트)
  □ 다음 목적지 전환 시 푸시 발송
  □ 모든 동선 완료 시 푸시 발송
  □ 포그라운드/백그라운드 알림 처리

W6-D1~D3: 통합 테스트 및 디버깅
  □ 전체 시나리오 E2E 테스트 (수동)
  □ 크로스 브라우저 테스트 (Chrome, Safari, Firefox)
  □ 모바일 브라우저 테스트 (iOS Safari, Android Chrome)
  □ 에지 케이스 처리
      - 세션 만료 시 재연결
      - 네트워크 끊김 후 복구
      - 동시 다중 세션 방지
      - QR 코드 중복 스캔 방지
  □ 단위 테스트 (pathfinding, session 서비스)

W6-D3~D5: 배포 및 마무리
  □ Vercel 프로젝트 연결 및 환경변수 설정
  □ 커스텀 도메인 설정 (선택)
  □ HTTPS 확인 (카메라, FCM 필수)
  □ README 업데이트 (설치/실행 가이드)
  □ 데모 시연 시나리오 준비
  □ 스크린샷/GIF 촬영
```

### 7.2 FCM 웹 푸시 구현 가이드

```
알림 발송 시나리오:
  1. 동선 최초 수신: "MediWay: 다음 목적지가 등록되었습니다"
  2. 다음 목적지 전환: "MediWay: 다음 목적지 — 본관 3층 원무과"
  3. 모든 동선 완료: "MediWay: 오늘 진료가 모두 끝났습니다. 귀가하셔도 됩니다."

구현 방식 (Phase 1에서는 클라이언트 직접 발송 방식 사용):
  - 의료진 웹에서 동선 전송 시 Realtime DB에 기록
  - 환자 웹의 onValue 리스너가 변경 감지
  - 환자 웹이 포그라운드면 인앱 토스트 표시
  - 백그라운드면 Service Worker가 시스템 알림 표시

참고: 프로덕션에서는 Firebase Cloud Functions에서 
     서버 사이드로 FCM 발송하는 것이 보안상 권장됨.
     Phase 1에서는 클라이언트 방식으로 단순화.
```

### 7.3 Service Worker 구조

```javascript
// public/firebase-messaging-sw.js

importScripts('https://www.gstatic.com/firebasejs/10.7.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.7.0/firebase-messaging-compat.js');

firebase.initializeApp({
  // firebaseConfig (빌드 시 주입 또는 하드코딩)
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
  const { title, body } = payload.notification;
  self.registration.showNotification(title, {
    body,
    icon: '/icons/mediway-icon-192.png',
    badge: '/icons/mediway-badge-72.png',
  });
});
```

---

## 8. 데이터 모델 상세

### 8.1 TypeScript 타입 정의

```typescript
// src/types/hospital.ts

/** 관심 지점 카테고리 */
export type POICategory =
  | 'clinic'      // 진료실
  | 'lab'         // 검사실 (채혈, 소변검사 등)
  | 'imaging'     // 영상의학 (CT, MRI, X-ray)
  | 'pharmacy'    // 약국
  | 'admin'       // 원무과, 접수
  | 'elevator'    // 엘리베이터
  | 'stairs'      // 계단
  | 'restroom'    // 화장실
  | 'parking'     // 주차장
  | 'entrance'    // 출입구
  | 'convenience' // 편의시설 (편의점, 카페)
  | 'lobby';      // 로비

/** 좌표 (SVG 좌표계 기준) */
export interface Coordinate {
  x: number;
  y: number;
}

/** 관심 지점 (Point of Interest) */
export interface POI {
  id: string;
  name: string;           // "내과 3진료실"
  shortName: string;      // "내과"
  category: POICategory;
  buildingId: string;
  floorLevel: number;
  coordinates: Coordinate;
  description?: string;   // "본관 2층, 엘리베이터 옆"
  icon?: string;          // Lucide 아이콘명
}

/** 층 정보 */
export interface Floor {
  level: number;
  name: string;           // "1층", "B1층"
  mapSVGPath: string;     // "/hospital-maps/demo-hospital-1F.svg"
  pois: POI[];
}

/** 건물 */
export interface Building {
  id: string;
  name: string;           // "본관"
  floors: Floor[];
}

/** 병원 */
export interface Hospital {
  id: string;
  name: string;           // "MediWay 데모 병원"
  buildings: Building[];
}


// src/types/session.ts

/** 경유지 상태 */
export type WaypointStatus = 'pending' | 'current' | 'completed';

/** 경유지 */
export interface Waypoint {
  poiId: string;
  status: WaypointStatus;
  arrivedAt?: number;     // timestamp
}

/** 세션 상태 */
export type SessionStatus = 'waiting' | 'navigating' | 'completed';

/** 세션 */
export interface Session {
  sessionId: string;
  patientUid: string;
  staffUid?: string;
  qrToken: string;
  waypoints: Waypoint[];
  currentWaypointIndex: number;
  status: SessionStatus;
  createdAt: number;
  completedAt?: number;
  hospitalId: string;
}


// src/types/navigation.ts

/** 그래프 엣지 (POI 간 연결) */
export interface NavEdge {
  from: string;           // POI id
  to: string;             // POI id
  distance: number;       // 미터 단위
  estimatedTime: number;  // 초 단위
  pathCoordinates: Coordinate[];  // 경로 좌표 배열 (지도 위 렌더링용)
  floorChange?: {
    fromFloor: number;
    toFloor: number;
    via: 'elevator' | 'stairs' | 'escalator';
  };
}

/** 네비게이션 그래프 */
export interface NavigationGraph {
  hospitalId: string;
  edges: NavEdge[];
}

/** 경로 탐색 결과 */
export interface PathResult {
  from: POI;
  to: POI;
  totalDistance: number;
  totalTime: number;
  segments: PathSegment[];
}

/** 경로 세그먼트 (한 층 내의 구간) */
export interface PathSegment {
  floorLevel: number;
  coordinates: Coordinate[];
  distance: number;
  instruction?: string;   // "엘리베이터를 타고 3층으로 이동하세요"
}
```

### 8.2 동선 템플릿 데이터 구조

```typescript
// src/types/hospital.ts (추가)

/** 동선 템플릿 */
export interface RouteTemplate {
  id: string;
  name: string;                // "채혈 → 원무과 → 약국 → 귀가"
  departmentTag: string;       // "내과", "외과" 등 소속 진료과
  color: string;               // "#3B82F6" 구분 색상
  waypointPoiIds: string[];    // 순서대로 방문할 POI id 목록
  estimatedTotalTime: number;  // 전체 예상 소요 시간 (분)
  isDefault: boolean;          // 기본 템플릿 여부
}
```

### 8.3 Realtime DB 스키마

```
Firebase Realtime Database 구조:

mediway-demo/
├── qr_tokens/
│   └── {tokenId}/
│       ├── patientUid: string
│       ├── status: "waiting" | "matched" | "expired"
│       ├── sessionId: string (matched 시 추가)
│       ├── createdAt: number (timestamp)
│       └── fcmToken: string (환자의 FCM 토큰)
│
├── sessions/
│   └── {sessionId}/
│       ├── sessionId: string
│       ├── patientUid: string
│       ├── staffUid: string
│       ├── qrToken: string
│       ├── hospitalId: string
│       ├── status: "navigating" | "completed"
│       ├── currentWaypointIndex: number
│       ├── waypoints/
│       │   ├── 0/
│       │   │   ├── poiId: string
│       │   │   ├── status: "completed" | "current" | "pending"
│       │   │   └── arrivedAt: number | null
│       │   ├── 1/ ...
│       │   └── 2/ ...
│       ├── createdAt: number
│       └── completedAt: number | null
│
└── hospitals/  (정적 데이터, 선택적으로 DB에 저장)
    └── {hospitalId}/
        └── ... (또는 클라이언트 번들에 포함)
```

---

## 9. 병원 지도 데이터 명세

### 9.1 가상 병원 설계

```
병원명: MediWay 데모 병원
건물: 본관 1동
층수: 지상 4층 (B1 주차장은 Phase 1에서 생략)

■ 1층 — 로비 / 접수 / 약국
  ┌──────────────────────────────────────┐
  │  [출입구]                             │
  │                                      │
  │  ┌──────┐  ┌──────┐  ┌───────────┐  │
  │  │ 접수  │  │ 원무과│  │  외래약국  │  │
  │  └──────┘  └──────┘  └───────────┘  │
  │                                      │
  │     [로비/대기공간]                    │
  │                                      │
  │  ┌────┐                   ┌────┐    │
  │  │ EV │                   │계단│    │
  │  └────┘                   └────┘    │
  │         ┌──────────┐                │
  │         │  편의점   │                │
  │         └──────────┘                │
  └──────────────────────────────────────┘

  POI 목록:
    - entrance_main (정문 출입구)
    - admin_reception (접수)
    - admin_billing (원무과)
    - pharmacy_main (외래약국)
    - lobby_1f (1층 로비)
    - elevator_1 (엘리베이터 A)
    - stairs_1 (계단 A)
    - convenience_store (편의점)

■ 2층 — 내과 / 외과 / 채혈실
  ┌──────────────────────────────────────┐
  │                                      │
  │  ┌──────┐  ┌──────┐  ┌──────────┐  │
  │  │내과1  │  │내과2  │  │  채혈실   │  │
  │  └──────┘  └──────┘  └──────────┘  │
  │                                      │
  │        [2층 복도]                     │
  │                                      │
  │  ┌──────┐  ┌──────┐                 │
  │  │외과1  │  │외과2  │   ┌────┐      │
  │  └──────┘  └──────┘   │ EV │      │
  │                        └────┘      │
  │  ┌──────┐              ┌────┐      │
  │  │소아과 │              │계단│      │
  │  └──────┘              └────┘      │
  └──────────────────────────────────────┘

  POI 목록:
    - clinic_internal_1 (내과 1진료실)
    - clinic_internal_2 (내과 2진료실)
    - lab_blood (채혈실)
    - clinic_surgery_1 (외과 1진료실)
    - clinic_surgery_2 (외과 2진료실)
    - clinic_pediatrics (소아과)
    - elevator_2 (엘리베이터 A - 2층)
    - stairs_2 (계단 A - 2층)

■ 3층 — 영상의학과 / 정형외과
  ┌──────────────────────────────────────┐
  │                                      │
  │  ┌──────────┐  ┌──────────────────┐ │
  │  │ CT 촬영실 │  │  MRI 촬영실      │ │
  │  └──────────┘  └──────────────────┘ │
  │                                      │
  │        [3층 복도]                     │
  │                                      │
  │  ┌──────────┐  ┌──────────────────┐ │
  │  │ X-ray    │  │  영상의학과 접수  │ │
  │  └──────────┘  └──────────────────┘ │
  │                                      │
  │  ┌────────┐  ┌────────┐            │
  │  │정형외과 │  │재활의학 │  ┌────┐   │
  │  └────────┘  └────────┘  │ EV │   │
  │                           └────┘   │
  │                           ┌────┐   │
  │                           │계단│   │
  │                           └────┘   │
  └──────────────────────────────────────┘

  POI 목록:
    - imaging_ct (CT 촬영실)
    - imaging_mri (MRI 촬영실)
    - imaging_xray (X-ray 촬영실)
    - imaging_reception (영상의학과 접수)
    - clinic_orthopedics (정형외과)
    - clinic_rehab (재활의학과)
    - elevator_3 (엘리베이터 A - 3층)
    - stairs_3 (계단 A - 3층)

■ 4층 — 건강검진센터
  ┌──────────────────────────────────────┐
  │                                      │
  │  ┌────────────────────────────────┐ │
  │  │      건강검진센터 접수/대기      │ │
  │  └────────────────────────────────┘ │
  │                                      │
  │  ┌──────┐  ┌──────┐  ┌──────────┐  │
  │  │검진1  │  │검진2  │  │  내시경   │  │
  │  └──────┘  └──────┘  └──────────┘  │
  │                                      │
  │  ┌──────────┐          ┌────┐      │
  │  │ 상담실   │          │ EV │      │
  │  └──────────┘          └────┘      │
  │                        ┌────┐      │
  │                        │계단│      │
  │                        └────┘      │
  └──────────────────────────────────────┘

  POI 목록:
    - checkup_reception (검진센터 접수)
    - checkup_room_1 (검진실 1)
    - checkup_room_2 (검진실 2)
    - checkup_endoscopy (내시경실)
    - checkup_consult (상담실)
    - elevator_4 (엘리베이터 A - 4층)
    - stairs_4 (계단 A - 4층)
```

### 9.2 네비게이션 그래프 설계

```
그래프 구조:
  - 노드: 각 POI + 복도 교차점 (waypoint)
  - 엣지: 노드 간 이동 가능 경로 (거리, 시간, 좌표 배열)

층 간 이동:
  - elevator_1 ↔ elevator_2 ↔ elevator_3 ↔ elevator_4
    (거리: 0m, 시간: 30초)
  - stairs_1 ↔ stairs_2 ↔ stairs_3 ↔ stairs_4
    (거리: 0m, 시간: 45초/층)

같은 층 이동 예시 (2층):
  - clinic_internal_1 → corridor_2a: 5m, 15초
  - corridor_2a → lab_blood: 20m, 30초
  - corridor_2a → elevator_2: 30m, 45초

경로 좌표:
  각 엣지에 pathCoordinates 배열로 경로 꺾임 지점 좌표를 저장
  이 좌표를 Leaflet Polyline으로 렌더링

추정 이동 시간 계산:
  보행 속도: 약 1.2m/s (4.3km/h) — 병원 내 걸음 속도
  거리(m) / 1.2 = 소요 시간(초)
  엘리베이터 대기 시간: 30초 (평균)
  층 간 계단 이동: 45초/층
```

### 9.3 기본 동선 템플릿

```
진료과별 빈번 동선 목록:

1. [내과] 채혈 → 원무과 → 약국 → 귀가
   경유지: lab_blood → admin_billing → pharmacy_main → entrance_main
   예상 시간: 15분

2. [내과] 원무과 → 약국 → 귀가
   경유지: admin_billing → pharmacy_main → entrance_main
   예상 시간: 8분

3. [내과] 영상의학과 → 원무과 → 약국 → 귀가
   경유지: imaging_reception → admin_billing → pharmacy_main → entrance_main
   예상 시간: 20분

4. [외과] 채혈 → 영상의학과 → 원무과 → 약국 → 귀가
   경유지: lab_blood → imaging_reception → admin_billing → pharmacy_main → entrance_main
   예상 시간: 25분

5. [건강검진] 채혈 → CT → 내시경 → 상담실 → 원무과 → 귀가
   경유지: lab_blood → imaging_ct → checkup_endoscopy → checkup_consult → admin_billing → entrance_main
   예상 시간: 35분

6. [정형외과] X-ray → 정형외과 → 원무과 → 약국 → 귀가
   경유지: imaging_xray → clinic_orthopedics → admin_billing → pharmacy_main → entrance_main
   예상 시간: 22분
```

---

## 10. 경로 탐색 알고리즘

### 10.1 Dijkstra 최단 경로

```
알고리즘: Dijkstra (가중치 그래프 최단 경로)
가중치: 이동 시간 (초 단위)

입력:
  - graph: NavigationGraph (모든 엣지)
  - startPoiId: string
  - endPoiId: string

출력:
  - PathResult (총 거리, 총 시간, 세그먼트 배열)

구현 위치: src/services/pathfinding.ts

의사 코드:
  1. 인접 리스트 구축 (edges → adjacency map)
  2. 우선순위 큐로 Dijkstra 실행
  3. 최단 경로 역추적
  4. 경로를 층별 세그먼트로 분할
  5. 층 이동 시 instruction 생성 ("엘리베이터를 타고 3층으로 이동하세요")
  6. 각 세그먼트의 좌표 배열 합산

Phase 1에서의 단순화:
  - 동선 템플릿은 이미 경유지 순서가 정해져 있으므로,
    각 인접 경유지 쌍(A→B, B→C, C→D)에 대해 최단 경로를 구하면 됨
  - 전체 경로 = 구간별 최단 경로의 이어붙이기
```

### 10.2 층 이동 처리

```
층 이동이 포함된 경로 처리:

예시: 2층 내과 → 3층 영상의학과

경로 세그먼트:
  Segment 1: 2층
    clinic_internal_1 → corridor_2a → elevator_2
    instruction: "엘리베이터로 이동하세요"

  Segment 2: 층 이동
    elevator_2 → elevator_3
    instruction: "엘리베이터를 타고 3층으로 이동하세요"

  Segment 3: 3층
    elevator_3 → corridor_3a → imaging_reception
    instruction: "영상의학과 접수로 이동하세요"

지도 표시:
  - 현재 보고 있는 층의 세그먼트만 지도에 표시
  - 층 이동 세그먼트는 텍스트 안내로 대체
  - FloorSelector에서 다른 층 탭 시 해당 층의 세그먼트 표시
```

---

## 11. 보안 및 개인정보보호

### 11.1 원칙

```
1. 의료 정보 비접촉
   - 앱에서 진단명, 검사결과, 처방 내용 등을 절대 다루지 않음
   - 동선 데이터에 의료 정보 포함 금지
   - 예) "내과" (O) vs "위암 의심 내과 진료" (X)

2. 데이터 최소 수집
   - 수집 데이터: 익명 UID, QR 토큰, 동선 정보, FCM 토큰
   - 미수집 데이터: 이름, 전화번호, 진료기록, 위치 이력

3. 실시간 처리 후 삭제
   - 세션 TTL: 24시간 후 자동 만료
   - QR 토큰: 매칭 완료 또는 1시간 후 만료
   - Realtime DB 보안 규칙으로 접근 제한

4. 전송 구간 보안
   - Firebase SDK가 TLS/HTTPS 보장
   - Realtime DB 보안 규칙으로 세션 참여자만 읽기/쓰기
```

### 11.2 세션 데이터 접근 제어

```
읽기 권한:
  - 세션의 patientUid와 일치하는 사용자 → 읽기 가능
  - 세션의 staffUid와 일치하는 사용자 → 읽기 가능
  - 그 외 → 접근 거부

쓰기 권한:
  - 세션 생성: staffUid 사용자만 가능
  - 도착 확인 (currentWaypointIndex 업데이트): patientUid만 가능
  - 세션 삭제: staffUid 또는 시스템 TTL

QR 토큰:
  - 생성: 환자 (patientUid)
  - 읽기: 인증된 모든 사용자 (스캔을 위해)
  - 상태 변경: 매칭 시 staffUid 사용자
```

---

## 12. 테스트 전략

### 12.1 단위 테스트

```
테스트 대상 및 도구: Vitest + @testing-library/react

1. pathfinding.ts
   - 같은 층 내 최단 경로 계산
   - 층 이동 포함 경로 계산
   - 경유지 없는 경우 (출발지 = 목적지)
   - 연결되지 않은 POI 예외 처리

2. session.ts
   - 세션 생성 데이터 검증
   - 세션 상태 전환 (waiting → navigating → completed)
   - 도착 확인 시 다음 경유지 인덱스 증가
   - 마지막 경유지 도착 시 세션 완료 처리

3. qr.ts
   - QR 토큰 생성 유일성
   - 토큰 형식 검증

4. distance.ts
   - 두 좌표 간 거리 계산
   - 이동 시간 추정
```

### 12.2 통합/E2E 테스트 시나리오

```
시나리오 1: 정상 플로우
  1. 환자 웹 열기 → QR 생성 확인
  2. 의료진 웹 열기 → QR 스캔
  3. 템플릿 선택 → 전송
  4. 환자 웹에 동선 실시간 수신 확인
  5. 지도에 경로 표시 확인
  6. "도착" 클릭 → 다음 목적지 전환
  7. 모든 경유지 완료 → 완료 화면

시나리오 2: 에지 케이스
  - 세션 없이 환자 페이지 직접 접근
  - QR 만료 후 스캔 시도
  - 네트워크 끊김 중 동선 전송
  - 동일 QR 중복 스캔
  - 브라우저 새로고침 후 세션 복원

시나리오 3: 반응형
  - 모바일 세로 모드에서 지도 + 카드 UI
  - 태블릿에서 의료진 UI
  - 데스크톱에서 양쪽 화면 나란히 시연
```

---

## 13. 배포 및 환경 설정

### 13.1 환경 변수

```
# .env.local (Git에 커밋하지 않음)

VITE_FIREBASE_API_KEY=your-api-key
VITE_FIREBASE_AUTH_DOMAIN=mediway-demo.firebaseapp.com
VITE_FIREBASE_DATABASE_URL=https://mediway-demo-default-rtdb.asia-southeast1.firebasedatabase.app
VITE_FIREBASE_PROJECT_ID=mediway-demo
VITE_FIREBASE_STORAGE_BUCKET=mediway-demo.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123456789:web:abc123
VITE_FIREBASE_VAPID_KEY=your-vapid-key
```

### 13.2 Vercel 배포

```
배포 순서:
  1. GitHub 레포 생성 및 코드 푸시
  2. Vercel에서 GitHub 레포 연결
  3. Framework Preset: Vite
  4. 환경 변수 설정 (위 .env.local 내용)
  5. 빌드 명령: npm run build
  6. 출력 디렉토리: dist
  7. 배포 → HTTPS 자동 적용

도메인:
  - 기본: mediway-demo.vercel.app
  - 커스텀: mediway.app (선택)
```

### 13.3 성능 고려사항

```
번들 최적화:
  - Firebase SDK: 모듈러 import로 트리 쉐이킹
  - Leaflet: CSS + JS 분리 로딩
  - SVG 평면도: 이미지 대신 inline SVG 또는 lazy load

초기 로딩:
  - 랜딩 페이지는 경량 (Firebase SDK는 역할 선택 후 로드)
  - 지도 SVG는 해당 층 접근 시 lazy load
  - QR 스캐너 라이브러리는 의료진 페이지에서만 로드
```

---

## 14. Phase 2 연계 고려사항

### 14.1 Phase 2에서 재사용할 요소

```
재사용 대상:
  ✅ Firebase 백엔드 (Auth, Realtime DB, FCM)
  ✅ 세션 데이터 모델 및 상태 머신
  ✅ 네비게이션 그래프 데이터 포맷
  ✅ 동선 템플릿 데이터 구조
  ✅ 경로 탐색 알고리즘 (pathfinding.ts → Swift 이식)
  ✅ 가상 병원 데이터 (POI, 좌표)

확장 필요:
  ⚠️ 좌표계 — SVG 좌표 → 실제 미터 좌표 변환 레이어 추가
  ⚠️ 네비게이션 그래프 — BLE 비콘 위치 노드 추가
  ⚠️ 세션 모델 — 실시간 위치 추적 필드 추가
```

### 14.2 API 설계 시 모바일 고려

```
Phase 1에서 Firebase Realtime DB를 직접 사용하는 구조는
Phase 2 iOS 앱에서도 동일하게 Firebase iOS SDK로 접근 가능.

만약 Phase 2에서 REST API 서버를 도입할 경우:
  - Phase 1의 Realtime DB 구조를 API 엔드포인트로 래핑
  - 세션 CRUD, 동선 전송, 도착 확인 등

권장: Phase 1에서는 Firebase 직접 접근으로 단순화하되,
     서비스 레이어(services/)를 깔끔하게 분리하여
     Phase 2에서 API로 교체하기 쉽게 설계.
```

---

## 부록: Claude Code 사용 팁

### 프롬프트 예시 — 프로젝트 초기화

```
"Vite + React + TypeScript 프로젝트를 생성해줘.
Tailwind CSS, React Router, Zustand를 설정하고,
위 가이드라인의 디렉토리 구조대로 폴더와 기본 파일을 만들어줘."
```

### 프롬프트 예시 — 데이터 모델 구현

```
"가이드라인 8장의 TypeScript 타입 정의를 구현해줘.
그리고 9장의 가상 병원 데이터(demo-hospital.ts)를
실제 데이터로 작성해줘. POI 좌표는 SVG viewBox 0 0 1200 800 기준으로."
```

### 프롬프트 예시 — 컴포넌트 구현

```
"가이드라인 6.2의 IndoorMap 컴포넌트를 구현해줘.
Leaflet CRS.Simple을 사용하고, SVG 평면도를 ImageOverlay로 표시하고,
PathLine으로 경로를 그리는 기능을 포함해야 해."
```

### 프롬프트 예시 — 전체 플로우 연결

```
"의료진이 QR 스캔 → 템플릿 선택 → 전송하면,
환자 웹에서 실시간으로 동선을 수신하여 지도에 표시하는
전체 플로우를 연결해줘. Firebase Realtime DB를 사용해."
```

---

> **이 가이드라인은 Phase 1 웹 데모의 전체 구현 청사진입니다.**
> Claude Code에서 작업할 때 각 주차별 Task 목록을 체크리스트로 활용하고,
> 데이터 모델과 컴포넌트 명세를 참조하여 일관된 구현을 유지하세요.
