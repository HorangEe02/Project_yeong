# MediWay Phase F — Firebase 통합 기능 설명서

> 작성일: 2026-04-16 | Phase F 구현 + Firebase 연동 완료 시점 기준
> 빌드 결과: JS 915KB / CSS 20KB (gzip 후 ~279KB) | 테스트: 13/13 통과
> Firebase 연동: ✅ 익명 인증, Realtime DB 읽기/쓰기/삭제 모두 검증 완료

---

## 목차

1. [개요](#1-개요)
2. [Firebase 프로젝트 — 실제 구성 정보](#2-firebase-프로젝트--실제-구성-정보)
3. [익명 인증 (Anonymous Auth)](#3-익명-인증-anonymous-auth)
4. [Realtime Database — QR 토큰 관리](#4-realtime-database--qr-토큰-관리)
5. [Realtime Database — 세션 관리](#5-realtime-database--세션-관리)
6. [실시간 구독 시스템 (useSession)](#6-실시간-구독-시스템-usesession)
7. [FCM 웹 푸시 알림](#7-fcm-웹-푸시-알림)
8. [Graceful Degradation — 로컬 데모 모드](#8-graceful-degradation--로컬-데모-모드)
9. [StaffDashboard Firebase 연동](#9-staffdashboard-firebase-연동)
10. [Realtime DB 스키마 및 보안 규칙](#10-realtime-db-스키마-및-보안-규칙)
11. [Firebase 연동 검증 결과](#11-firebase-연동-검증-결과)
12. [컴포넌트 의존성](#12-컴포넌트-의존성)
13. [Phase G 연계](#13-phase-g-연계)

---

## 1. 개요

### 1.1 Phase F의 목적

Phase F는 MediWay의 **백엔드 인프라**를 구현합니다. Phase D(의료진)와 Phase E(환자)에서 구현한 로컬 시뮬레이션을 **Firebase 실시간 통신**으로 연결하여, 두 브라우저 탭 간 동선 전송/수신이 실시간으로 동작하도록 합니다.

### 1.2 구현 범위

| 구현 항목 | 파일 | 설명 |
|----------|------|------|
| Firebase 초기화 | `config/firebase.ts` | App, Auth, DB, Messaging 인스턴스 |
| 환경변수 | `.env.local` + `.env.local.example` | 실제 Firebase config + 템플릿 |
| 익명 인증 서비스 | `services/auth.ts` | signInAnonymously, UID 조회 |
| 세션 서비스 | `services/session.ts` | QR 토큰 CRUD, 세션 CRUD, 경유지 도착 처리 |
| 실시간 구독 훅 | `hooks/useSession.ts` | QR 토큰→세션 2단계 onValue 구독 |
| 알림 서비스 | `services/notification.ts` | FCM 토큰 획득, 포그라운드 메시지, 로컬 알림 |
| 알림 훅 | `hooks/useNotification.ts` | FCM 권한 요청, 포그라운드 리스너 |
| Service Worker | `public/firebase-messaging-sw.js` | 백그라운드 FCM 메시지 처리 (실제 config 적용) |
| DB 보안 규칙 | `database.rules.json` | 세션 참여자 기반 접근 제어 |
| Firebase 프로젝트 설정 | `firebase.json` + `.firebaserc` | CLI 프로젝트 연결 |
| App.tsx 수정 | `App.tsx` | 앱 시작 시 익명 인증 초기화 |
| StaffDashboard 수정 | `StaffDashboard.tsx` | QR 검증 + 세션 생성 + 알림 연동 |

### 1.3 핵심 설계 결정

| 결정 | 이유 |
|------|------|
| Graceful Degradation | Firebase 미설정 시 로컬 데모 모드로 완전 동작 — 개발/시연 편의성 |
| 클라이언트 직접 DB 접근 | Phase 1 데모 규모에서는 서버 불필요, Firebase SDK가 TLS 보장 |
| 2단계 실시간 구독 | QR 토큰 → 세션으로 자연스러운 전환, 불필요한 전체 세션 구독 방지 |
| 클라이언트 사이드 알림 | Cloud Functions 없이 로컬 Notification API 활용 (데모 단순화) |
| Anonymous Auth | 환자 회원가입 불필요, 세션 기반 보안 규칙으로 접근 제어 |

---

## 2. Firebase 프로젝트 — 실제 구성 정보

### 2.1 프로젝트 정보

| 항목 | 값 |
|------|-----|
| 프로젝트 ID | `mediway-demo` |
| 프로젝트 이름 | MediWay Demo |
| 웹 앱 이름 | MediWay Web |
| App ID | `1:805996216710:web:caee81623cd2fbc5baac07` |
| 계정 | `catlife9029@gmail.com` |
| Firebase Console | https://console.firebase.google.com/project/mediway-demo/overview |

### 2.2 활성화된 서비스

| 서비스 | 상태 | 상세 |
|--------|------|------|
| **Authentication** | ✅ 활성 | 익명(Anonymous) 인증 활성화 |
| **Realtime Database** | ✅ 활성 | 인스턴스: `mediway-demo-default-rtdb` (us-central1) |
| **Cloud Messaging** | ✅ 준비 | Service Worker 배포 완료 (VAPID 키 미발급 — Phase G) |

### 2.3 `config/firebase.ts`

**파일:** `src/config/firebase.ts`

Firebase App을 초기화하고 Auth, Realtime DB, Messaging 인스턴스를 내보냅니다.

| 내보내기 | 타입 | 설명 |
|---------|------|------|
| `auth` | `Auth` | Firebase Authentication 인스턴스 |
| `db` | `Database` | Firebase Realtime Database 인스턴스 |
| `getMessagingInstance()` | `async () → Messaging \| null` | FCM 인스턴스 (브라우저 지원 확인 후 반환) |
| `isFirebaseConfigured()` | `() → boolean` | 환경변수 존재 여부로 Firebase 설정 상태 판별 |

### 2.4 환경변수 (`.env.local`)

| 변수 | 실제 값 | 비고 |
|------|--------|------|
| `VITE_FIREBASE_API_KEY` | `REPLACE_WITH_YOUR_FIREBASE_API_KEY` | |
| `VITE_FIREBASE_AUTH_DOMAIN` | `mediway-demo.firebaseapp.com` | |
| `VITE_FIREBASE_DATABASE_URL` | `https://mediway-demo-default-rtdb.firebaseio.com` | |
| `VITE_FIREBASE_PROJECT_ID` | `mediway-demo` | |
| `VITE_FIREBASE_STORAGE_BUCKET` | `mediway-demo.firebasestorage.app` | |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | `805996216710` | |
| `VITE_FIREBASE_APP_ID` | `1:805996216710:web:caee81623cd2fbc5baac07` | |
| `VITE_FIREBASE_VAPID_KEY` | (미발급) | Phase G에서 FCM 활성화 시 설정 |

> `.env.local`은 Git에 커밋하지 않습니다. `.env.local.example`에 키 이름만 기록된 템플릿이 있습니다.

### 2.5 FCM Messaging 초기화

FCM은 모든 브라우저에서 지원되지 않습니다 (iOS Safari, Firefox Private 등). `isSupported()`로 런타임 확인 후 인스턴스를 생성합니다:

```typescript
export async function getMessagingInstance() {
  const supported = await isSupported();
  if (!supported) return null;
  return getMessaging(app);
}
```

---

## 3. 익명 인증 (Anonymous Auth)

### 3.1 `services/auth.ts`

**파일:** `src/services/auth.ts`

| 함수 | 시그니처 | 설명 |
|------|---------|------|
| `initAnonymousAuth` | `() → Promise<User \| null>` | 익명 인증 실행 (앱 시작 시 1회) |
| `getCurrentUid` | `() → string \| null` | 현재 인증 UID |
| `onAuthChange` | `(callback) → () => void` | 인증 상태 변경 구독 |

### 3.2 인증 플로우

```
앱 시작 (App.tsx useEffect)
    │
    ├── isFirebaseConfigured() === false
    │       → 스킵 (로컬 데모 모드)
    │
    └── isFirebaseConfigured() === true ← 현재 상태
            → signInAnonymously(auth)
            → auth.currentUser.uid 획득
            → 이후 DB 읽기/쓰기에 이 UID 사용
```

### 3.3 인증 검증 결과

| 항목 | 결과 |
|------|------|
| `signInAnonymously()` | ✅ 성공 |
| 발급된 테스트 UID | `tvsTPquiGTZcrfIeFvB336uoTk32` |
| Firebase Console 확인 | Authentication > Users 탭에서 익명 사용자 확인 가능 |

### 3.4 UID 활용

| 역할 | UID 사용 |
|------|---------|
| 의료진 | 세션의 `staffUid` 필드 |
| 환자 | QR 토큰의 `patientUid` 필드, 세션의 `patientUid` 필드 |
| 보안 규칙 | `auth.uid === data.child('staffUid').val()` 등으로 접근 제어 |

---

## 4. Realtime Database — QR 토큰 관리

### 4.1 QR 토큰 함수

**파일:** `src/services/session.ts`

| 함수 | 시그니처 | 호출 측 | 설명 |
|------|---------|--------|------|
| `createQRToken` | `(token, patientUid) → Promise<void>` | 환자 | 토큰 DB 등록 (status: waiting) |
| `getQRToken` | `(token) → Promise<QRToken \| null>` | 의료진 | 토큰 조회 (검증용) |
| `updateQRTokenStatus` | `(token, status, sessionId?) → Promise<void>` | 의료진 | 상태 변경 (waiting→matched) |
| `subscribeQRToken` | `(token, callback) → Unsubscribe` | 환자 | 실시간 구독 (매칭 감지) |

### 4.2 QR 토큰 생명 주기

```
환자 웹 접속
    │
    ├── 1. uuid v4로 토큰 생성
    ├── 2. createQRToken(token, patientUid)
    │       → DB: /qr_tokens/{token} = { patientUid, status: "waiting", createdAt }
    ├── 3. QR 코드 화면에 표시
    └── 4. subscribeQRToken(token, callback)
            → onValue 리스너로 status 변경 감시

의료진 QR 스캔
    │
    ├── 1. getQRToken(token) → 검증 (status === "waiting" 확인)
    ├── 2. 동선 선택 후 createSession(session)
    └── 3. updateQRTokenStatus(token, "matched", sessionId)
            → 환자 측 onValue가 "matched" 감지
            → 환자 자동으로 세션 구독 시작

3분 후 (Phase G에서 구현)
    │
    └── QR 토큰 만료 처리 (status → "expired")
```

### 4.3 DB 구조

```
/qr_tokens/{tokenId}/
    ├── patientUid: string
    ├── status: "waiting" | "matched" | "expired"
    ├── sessionId: string (matched 시 추가)
    └── createdAt: number (timestamp)
```

### 4.4 DB 쓰기/읽기 검증 결과

연동 검증 시 실제 DB 동작 확인:

```
쓰기: /qr_tokens/test_token_123
  → { patientUid: "tvsTPquiGTZ...", status: "waiting", createdAt: 1776332886244 }
  → ✅ 성공

읽기: /qr_tokens/test_token_123
  → { createdAt: 1776332886244, patientUid: "tvsTPquiGTZ...", status: "waiting" }
  → ✅ 성공 (데이터 일치)

삭제: /qr_tokens/test_token_123
  → ✅ 성공 (테스트 데이터 정리)
```

---

## 5. Realtime Database — 세션 관리

### 5.1 세션 함수

**파일:** `src/services/session.ts`

| 함수 | 시그니처 | 호출 측 | 설명 |
|------|---------|--------|------|
| `createSession` | `(session) → Promise<void>` | 의료진 | 세션 생성 (동선 전송) |
| `getSession` | `(sessionId) → Promise<Session \| null>` | 양측 | 세션 조회 |
| `subscribeSession` | `(sessionId, callback) → Unsubscribe` | 환자 | 세션 실시간 구독 |
| `markWaypointArrived` | `(sessionId, index, total) → Promise<void>` | 환자 | 경유지 도착 처리 |
| `updateSessionStatus` | `(sessionId, status) → Promise<void>` | 양측 | 세션 상태 변경 |

### 5.2 세션 생명 주기

```
의료진 "전송" 클릭
    │
    ├── createSession({
    │     sessionId: uuid,
    │     staffUid, patientUid, qrToken,
    │     hospitalId: "demo-hospital",
    │     status: "navigating",
    │     currentWaypointIndex: 0,
    │     waypoints: [
    │       { poiId: "lab_blood", status: "current" },
    │       { poiId: "admin_billing", status: "pending" },
    │       ...
    │     ]
    │   })
    │
    └── → DB: /sessions/{sessionId} 에 기록

환자 동선 수신 (subscribeSession)
    │
    ├── 경로 계산 (computeRoute)
    ├── 지도에 경로 표시
    └── "도착" 버튼 대기

환자 "도착" 클릭
    │
    └── markWaypointArrived(sessionId, currentIndex, totalWaypoints)
            → 원자적 업데이트:
              waypoints[current].status = "completed"
              waypoints[current].arrivedAt = timestamp
              waypoints[next].status = "current"
              currentWaypointIndex++
              (마지막이면: status = "completed", completedAt = timestamp)
```

### 5.3 원자적 경유지 업데이트

`markWaypointArrived`는 `update(ref(db), updates)`를 사용하여 여러 경로를 **하나의 원자적 트랜잭션**으로 업데이트합니다:

```typescript
const updates: Record<string, unknown> = {};
updates[`sessions/${sessionId}/waypoints/${index}/status`] = 'completed';
updates[`sessions/${sessionId}/waypoints/${index}/arrivedAt`] = Date.now();
updates[`sessions/${sessionId}/waypoints/${nextIndex}/status`] = 'current';
updates[`sessions/${sessionId}/currentWaypointIndex`] = nextIndex;
await update(ref(db), updates);
```

이 방식은 네트워크 지연이나 동시 접근 시에도 데이터 일관성을 보장합니다.

### 5.4 DB 구조

```
/sessions/{sessionId}/
    ├── sessionId: string
    ├── patientUid: string
    ├── staffUid: string
    ├── qrToken: string
    ├── hospitalId: string
    ├── status: "navigating" | "completed"
    ├── currentWaypointIndex: number
    ├── waypoints/
    │   ├── 0/ { poiId, status, arrivedAt? }
    │   ├── 1/ { poiId, status, arrivedAt? }
    │   └── ...
    ├── createdAt: number
    └── completedAt: number | null
```

---

## 6. 실시간 구독 시스템 (useSession)

### 6.1 `hooks/useSession.ts`

**파일:** `src/hooks/useSession.ts`

| 반환값 | 타입 | 설명 |
|--------|------|------|
| `qrTokenData` | `QRToken \| null` | QR 토큰 실시간 데이터 |
| `session` | `Session \| null` | 세션 실시간 데이터 |
| `isConnected` | `boolean` | Firebase 연결 여부 |

### 6.2 2단계 구독 패턴

```
Stage 1: QR 토큰 구독
    qrToken 있음 → subscribeQRToken(token, callback)
    │
    └── onValue 리스너가 /qr_tokens/{token} 변경 감지
        └── qrTokenData.status === "matched" 감지

Stage 2: 세션 구독 (자동 전환)
    qrTokenData.sessionId 획득 → subscribeSession(sessionId, callback)
    │
    └── onValue 리스너가 /sessions/{sessionId} 변경 감지
        └── 경유지 도착, 세션 완료 등 실시간 반영
```

### 6.3 구독 정리

각 `useEffect`는 `Unsubscribe` 함수를 반환하여, QR 토큰이 변경되거나 컴포넌트가 언마운트될 때 이전 리스너를 자동 해제합니다.

---

## 7. FCM 웹 푸시 알림

### 7.1 `services/notification.ts`

**파일:** `src/services/notification.ts`

| 함수 | 시그니처 | 설명 |
|------|---------|------|
| `requestNotificationPermission` | `() → Promise<string \| null>` | 알림 권한 요청 + FCM 토큰 반환 |
| `onForegroundMessage` | `(callback) → Promise<Unsubscribe \| null>` | 포그라운드 메시지 리스너 |
| `showLocalNotification` | `(title, body) → void` | 브라우저 네이티브 알림 표시 |
| `NotificationMessages.routeReceived` | `() → void` | "다음 목적지가 등록되었습니다" |
| `NotificationMessages.nextDestination` | `(name) → void` | "다음 목적지 — {name}" |
| `NotificationMessages.allCompleted` | `() → void` | "오늘 진료가 모두 끝났습니다" |

### 7.2 알림 발송 시나리오

| 시나리오 | 트리거 | 메시지 |
|---------|--------|--------|
| 동선 최초 수신 | 의료진이 "전송" 클릭 | "MediWay: 다음 목적지가 등록되었습니다" |
| 다음 목적지 전환 | 환자가 "도착" 클릭 | "MediWay: 다음 목적지 — 본관 1층 원무과" |
| 모든 동선 완료 | 마지막 경유지 도착 | "MediWay: 오늘 진료가 모두 끝났습니다" |

### 7.3 포그라운드 vs 백그라운드

| 상태 | 처리 방식 |
|------|----------|
| **포그라운드** (탭 활성) | `onMessage()` → 브라우저 Notification API |
| **백그라운드** (탭 비활성/최소화) | Service Worker `onBackgroundMessage()` → 시스템 알림 |

### 7.4 `hooks/useNotification.ts`

| 반환값 | 타입 | 설명 |
|--------|------|------|
| `fcmToken` | `string \| null` | FCM 토큰 (세션에 저장용) |
| `permissionStatus` | `NotificationPermission \| 'unsupported'` | 권한 상태 |
| `requestPermission` | `() → Promise<void>` | 권한 요청 함수 |

### 7.5 Service Worker — 실제 Config 적용 완료

**파일:** `public/firebase-messaging-sw.js`

Service Worker에는 Vite 환경변수를 사용할 수 없으므로 실제 Firebase config이 하드코딩되어 있습니다:

```javascript
firebase.initializeApp({
  apiKey: 'REPLACE_WITH_YOUR_FIREBASE_API_KEY',
  authDomain: 'mediway-demo.firebaseapp.com',
  databaseURL: 'https://mediway-demo-default-rtdb.firebaseio.com',
  projectId: 'mediway-demo',
  storageBucket: 'mediway-demo.firebasestorage.app',
  messagingSenderId: '805996216710',
  appId: '1:805996216710:web:caee81623cd2fbc5baac07',
});

messaging.onBackgroundMessage((payload) => {
  const { title, body } = payload.notification || {};
  self.registration.showNotification(title, { body, icon: '/favicon.svg' });
});
```

---

## 8. Graceful Degradation — 로컬 데모 모드

### 8.1 설계 원칙

Firebase가 설정되지 않은 환경(`.env.local` 없음)에서도 앱이 완전히 동작해야 합니다. 모든 Firebase 서비스 함수는 `isFirebaseConfigured()` 가드를 포함합니다:

```typescript
export async function createSession(session: Session): Promise<void> {
  if (!isFirebaseConfigured()) return;  // ← 로컬 모드에서는 즉시 리턴
  // ... Firebase 로직
}
```

### 8.2 모드별 동작 비교

| 기능 | Firebase 모드 (현재 활성) | 로컬 데모 모드 (.env.local 없을 때) |
|------|--------------------------|----------------------------------|
| 익명 인증 | `signInAnonymously()` ✅ | 스킵, console.warn |
| QR 토큰 등록 | `/qr_tokens/{token}` DB 쓰기 ✅ | 즉시 리턴 (no-op) |
| QR 토큰 검증 | DB에서 status 확인 ✅ | 스킵 → 바로 scanned 상태 |
| 세션 생성 | `/sessions/{sessionId}` DB 쓰기 ✅ | 즉시 리턴 (no-op) |
| 실시간 구독 | `onValue` 리스너 ✅ | callback(null), 빈 unsubscribe |
| 동선 수신 | Firebase → 자동 전환 | "동선 수신 시뮬레이션" 버튼 |
| "도착" 처리 | DB 원자적 업데이트 ✅ | 로컬 상태만 변경 |
| 푸시 알림 | FCM → 시스템 알림 | `showLocalNotification` (브라우저 API) |

### 8.3 모드 판별

```typescript
export function isFirebaseConfigured(): boolean {
  return Boolean(import.meta.env.VITE_FIREBASE_API_KEY);
}
```

현재 `.env.local`이 설정되어 있으므로 **Firebase 모드로 동작합니다.** `.env.local`을 삭제하면 자동으로 로컬 데모 모드로 전환됩니다.

---

## 9. StaffDashboard Firebase 연동

### 9.1 수정된 QR 스캔 플로우

```
스캔 성공 (handleScanSuccess)
    │
    ├── isFirebaseConfigured() === true ← 현재 상태
    │       → getQRToken(token) — DB에서 토큰 조회
    │       → status === "waiting" 확인
    │       → 실패 시: "유효하지 않거나 이미 사용된 QR 코드" 에러
    │
    └── isFirebaseConfigured() === false
            → 검증 스킵, 바로 scanned 상태
```

### 9.2 수정된 전송 플로우

```
전송 확인 (handleSendConfirm)
    │
    ├── isFirebaseConfigured() === true ← 현재 상태
    │       → sessionId = uuid v4
    │       → staffUid = getCurrentUid() — Firebase 익명 UID
    │       → patientUid = getQRToken(token).patientUid
    │       → createSession({ sessionId, staffUid, patientUid, waypoints, ... })
    │       → updateQRTokenStatus(token, "matched", sessionId)
    │       → NotificationMessages.routeReceived()
    │
    └── isFirebaseConfigured() === false
            → NotificationMessages.routeReceived() (로컬 알림만)
    │
    └── setState('sent') → 3초 후 초기화
```

### 9.3 에러 처리

Firebase 세션 생성 실패 시:
- `console.error` 로깅
- "동선 전송에 실패했습니다. 다시 시도해주세요." 에러 배너 표시
- `error` 상태 → "다시 시도" 버튼으로 `idle` 복귀

---

## 10. Realtime DB 스키마 및 보안 규칙

### 10.1 전체 스키마

```
mediway-demo-default-rtdb/
├── qr_tokens/
│   └── {tokenId}/
│       ├── patientUid: string
│       ├── status: "waiting" | "matched" | "expired"
│       ├── sessionId: string (matched 시)
│       └── createdAt: number
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
│       │   └── {index}/ { poiId, status, arrivedAt? }
│       ├── createdAt: number
│       └── completedAt: number | null
│
└── hospitals/ (정적, 읽기 전용)
```

### 10.2 보안 규칙 — 배포 완료

**파일:** `database.rules.json` — `firebase deploy --only database`로 배포됨

```json
{
  "rules": {
    "sessions": {
      "$sessionId": {
        ".write": "auth != null",
        ".read": "auth != null && (data.child('staffUid').val() === auth.uid || data.child('patientUid').val() === auth.uid)"
      }
    },
    "qr_tokens": {
      "$token": {
        ".write": "auth != null",
        ".read": "auth != null"
      }
    },
    "hospitals": {
      ".read": true,
      ".write": false
    }
  }
}
```

| 규칙 | 설명 | 배포 상태 |
|------|------|----------|
| 세션 쓰기 | 인증된 사용자만 | ✅ 배포됨 |
| 세션 읽기 | 해당 세션의 staffUid 또는 patientUid만 | ✅ 배포됨 |
| QR 토큰 쓰기 | 인증된 사용자만 | ✅ 배포됨 |
| QR 토큰 읽기 | 인증된 모든 사용자 (스캔을 위해) | ✅ 배포됨 |
| 병원 데이터 | 누구나 읽기, 쓰기 불가 | ✅ 배포됨 |

---

## 11. Firebase 연동 검증 결과

### 11.1 CLI 검증

```bash
firebase projects:list
# ✅ mediway-demo (MediWay Demo)

firebase database:instances:list --project mediway-demo
# ✅ mediway-demo-default-rtdb (1 instance)
```

### 11.2 통합 검증 스크립트 결과

Node.js에서 Firebase SDK를 직접 호출하여 전체 파이프라인을 검증했습니다:

| 단계 | 작업 | 결과 |
|------|------|------|
| 1 | Firebase 초기화 | ✅ 성공 |
| 2 | 익명 인증 (`signInAnonymously`) | ✅ UID: `tvsTPquiGTZcrfIeFvB336uoTk32` |
| 3 | DB 쓰기 (`/qr_tokens/test_token_123`) | ✅ 성공 |
| 4 | DB 읽기 (같은 경로) | ✅ 데이터 일치 확인 |
| 5 | DB 삭제 (테스트 데이터 정리) | ✅ 성공 |

### 11.3 설정 파일 검증

| 파일 | 상태 | 내용 |
|------|------|------|
| `.env.local` | ✅ 생성됨 | 7개 키 실제 값 입력, VAPID_KEY만 미설정 |
| `.env.local.example` | ✅ 존재 | 키 이름 템플릿 (Git 커밋용) |
| `firebase.json` | ✅ 생성됨 | `firebase init database`로 자동 생성 |
| `.firebaserc` | ✅ 생성됨 | `mediway-demo` 프로젝트 연결 |
| `database.rules.json` | ✅ 배포됨 | 세션 참여자 기반 보안 규칙 |
| `firebase-messaging-sw.js` | ✅ 교체됨 | 실제 Firebase config 하드코딩 |

---

## 12. 컴포넌트 의존성

### 12.1 Firebase 서비스 계층

```
config/firebase.ts (초기화)
    ↓
├── services/auth.ts (인증)
├── services/session.ts (DB CRUD)
└── services/notification.ts (FCM)
    ↓
├── hooks/useSession.ts (실시간 구독)
├── hooks/useNotification.ts (알림 관리)
    ↓
├── App.tsx (initAnonymousAuth)
├── StaffDashboard.tsx (세션 생성, QR 검증)
└── PatientDashboard.tsx (세션 구독 — Phase G에서 완전 연동)
```

### 12.2 isFirebaseConfigured 가드 적용 위치

| 파일 | 가드 적용 함수 |
|------|--------------|
| `auth.ts` | `initAnonymousAuth`, `onAuthChange` |
| `session.ts` | `createQRToken`, `getQRToken`, `updateQRTokenStatus`, `subscribeQRToken`, `createSession`, `getSession`, `subscribeSession`, `markWaypointArrived`, `updateSessionStatus` |
| `notification.ts` | `requestNotificationPermission`, `onForegroundMessage` |
| `useSession.ts` | 내부 `useEffect` 조건 |
| `useNotification.ts` | 내부 `useEffect` 조건 |
| `App.tsx` | `useEffect` 조건 |
| `StaffDashboard.tsx` | `handleScanSuccess`, `handleSendConfirm` 내부 |

---

## 13. Phase G 연계

### 13.1 Phase G에서 완성할 항목

| 항목 | 현재 상태 | Phase G |
|------|----------|---------|
| PatientDashboard Firebase 연동 | 로컬 시뮬레이션 유지 | `useSession` 훅으로 실시간 수신 |
| 세션 복원 (새로고침) | 미구현 | `localStorage` + `getSession()` |
| QR 토큰 만료 | 미구현 | 3분 후 status→"expired" |
| 세션 TTL | 미구현 | 24시간 후 자동 만료 |
| FCM VAPID 키 | 미발급 | Console에서 발급 후 .env.local 추가 |
| E2E 테스트 | 단위 테스트만 | 두 브라우저 탭 전체 플로우 |
| 코드 스플리팅 | 단일 번들 915KB | `lazy()` + 동적 import |

### 13.2 Firebase 프로젝트 상태 체크리스트

| 항목 | 상태 |
|------|------|
| ✅ Firebase 프로젝트 생성 (mediway-demo) | 완료 |
| ✅ 웹 앱 등록 (MediWay Web) | 완료 |
| ✅ Authentication > 익명 인증 활성화 | 완료 |
| ✅ Realtime Database > 인스턴스 생성 | 완료 (us-central1) |
| ✅ Realtime Database > 보안 규칙 배포 | 완료 |
| ✅ .env.local 설정 | 완료 (7개 키) |
| ✅ firebase-messaging-sw.js config 교체 | 완료 |
| ✅ 연동 검증 (인증 + DB 읽기/쓰기/삭제) | 통과 |
| ⬜ Cloud Messaging > VAPID key 생성 | Phase G |

---

*본 문서는 MediWay Phase F Firebase 연동 완료 시점의 기능 명세입니다.*
*Firebase 프로젝트 `mediway-demo`가 실제 구성되어 있으며, 익명 인증 + Realtime DB가 동작 중입니다.*
*Phase G(통합 + 배포)에서 PatientDashboard 완전 연동, E2E 테스트, Vercel 배포를 진행합니다.*
