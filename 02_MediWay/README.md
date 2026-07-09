# 02_MediWay — 병원 내 환자 동선 가이드

MediWay는 **병원 내 환자·의료진 동선 안내** React + Firebase 애플리케이션입니다.
QR 기반 익명 세션, 방문 계획, 길찾기(Dijkstra), 스태프 코드 초대, 관리자 콘솔을 제공합니다.

> **현재 버전**: v1.0 (단일 데모 병원 구현) — `main` 브랜치 + `v1.0-mediway-demo` 태그로 고정.
> **v2.0 작업**: `mediway/plusultra/*` 브랜치에서 Multi-Tenant SaaS 전환 진행 중 (main 미병합 — main은 v1.0 데모 기준).

---

## 브랜치 전략

| 브랜치 / 태그 | 용도 |
|---|---|
| `main` | 안정 릴리스 라인. 직접 push 금지, PR만 허용 |
| `v1.0-mediway-demo` (태그) | v1.0 단일 병원 데모 버전의 영구 스냅샷 |
| `mediway/develop` | v2.0 PlusUltra 통합 개발 브랜치 |
| `mediway/plusultra/p1` ~ `p5` | Phase별 작업 sub-branch (develop으로 PR) |

v2.0 작업 중에도 v1.0 데모는 `v1.0-mediway-demo` 태그로 언제든지 체크아웃 가능합니다.

---

## 기술 스택

- **Frontend**: React 18 · TypeScript · Vite · Tailwind CSS · React Router
- **Map / UI**: Leaflet · react-zoom-pan-pinch · lucide-react · html5-qrcode
- **State**: Zustand
- **Backend**: Firebase (Realtime Database · Auth · Cloud Functions `asia-northeast3`)
- **Test**: Vitest · Testing Library

---

## 핵심 기능 (v1.0)

- **QR 기반 환자 세션** — 로비 QR 스캔 → 익명 Firebase Auth → 24h TTL
- **길찾기** — 4개 층, 30+ POI, Dijkstra 기반 경로 계산 (`src/services/pathfinding.ts`)
- **방문 계획** — 환자·의료진 공유 (30분 링크 TTL)
- **인증** — 이메일 + Kakao · Naver · Google OAuth (Cloud Functions custom token)
- **관리자 콘솔** — 유저·스태프 코드·초대·세션·감사 로그 관리
- **역할 기반 접근** — `ProtectedRoute` + RTDB Security Rules

---

## 로컬 실행

```bash
cd mediway

# 1. 의존성 설치
npm install

# 2. Firebase 설정 (중요 — API 키는 리포지토리에 포함되지 않습니다)
cp .env.local.example .env.local
# .env.local을 열어 본인의 Firebase 프로젝트 값으로 교체
# Firebase Console > 프로젝트 설정 > 웹 앱 > firebaseConfig

# 3. Service Worker 설정 (FCM을 사용하는 경우)
# public/firebase-messaging-sw.js의 "REPLACE_WITH_YOUR_FIREBASE_API_KEY"를
# 본인의 Firebase 프로젝트 값으로 교체

# 4. 개발 서버 실행
npm run dev  # http://localhost:3000

# 5. 테스트 실행
npm test
```

---

## 외부 자산 (리포지토리 미포함)

용량·저작권 이슈로 다음 자산은 **리포지토리에 포함되지 않습니다**:

| 자산 | 용량 | 용도 |
|---|---|---|
| 3D 스캔 (Polycam `.glb`, Roomplan 프로젝트) | ~118MB | 병원 실내 3D 스캔 원본 |
| Point cloud 데이터 | — | 층도면 자동 생성 파이프라인 입력 |
| 경쟁사 벤치마크 문서 | — | 내부 기획 문서 |
| PlusUltra v2.0 가이드라인 | — | v2.0 설계 문서 (로컬에서만 관리) |

필요 시 저자에게 문의해 주세요.

---

## 보안 정책

- `.env.local` 및 Firebase API 키는 **리포지토리에 커밋하지 않습니다**
- `.env.local.example` 및 `functions/.env.example` 템플릿만 제공
- 코드 내 하드코딩된 API 키는 `REPLACE_WITH_YOUR_FIREBASE_API_KEY` placeholder로 치환됨
- Firebase Security Rules (`mediway/database.rules.json`)가 데이터 격리의 1차 방어선

---

## 프로젝트 구조

```
02_MediWay/
└── mediway/
    ├── src/
    │   ├── pages/          # 라우트 단위 페이지 (25)
    │   ├── components/     # UI 컴포넌트
    │   ├── services/       # 비즈니스 로직 (auth, pathfinding, visitPlan, …)
    │   ├── contexts/       # React Context
    │   ├── hooks/          # 커스텀 훅
    │   ├── types/          # TypeScript 타입
    │   ├── data/           # 병원 정적 데이터 (POI, 층도면, 네비 그래프)
    │   └── stores/         # Zustand 스토어
    ├── functions/          # Firebase Cloud Functions (Kakao · Naver OAuth)
    ├── public/             # 정적 자산 + FCM SW
    ├── docs/               # 단계별 구현 스펙 (PHASE_A ~ PHASE_G)
    ├── database.rules.json # RTDB 보안 규칙
    ├── firebase.json       # Firebase 프로젝트 설정
    └── package.json
```

---

## 라이선스 · 기여

개인 프로젝트. 외부 기여는 사전 문의 요망.
