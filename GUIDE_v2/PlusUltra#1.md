# PlusUltra #1 — Multi-Tenant 기반 구축 상세 구현 가이드

> **Phase 1 기능 설명서 + 구현 가이드라인**
> 범위: 데이터 모델·인증·권한·라우팅·브랜딩·마이그레이션
> 예상 기간: 1~2주 (1인 풀타임 기준)
> 선행 요건: 없음 (P0 = 현재 단일 병원 데모 동작)

---

## 목차

- [起 — 왜 지금 Multi-Tenant인가](#起--왜-지금-multi-tenant인가)
- [承 — 설계 원칙과 기술 선택](#承--설계-원칙과-기술-선택)
- [轉 — 세부 구현 설계](#轉--세부-구현-설계)
  - [1. 데이터 모델 (RTDB)](#1-데이터-모델-rtdb)
  - [2. 인증·권한 (Custom Claims)](#2-인증권한-custom-claims)
  - [3. 라우팅 및 HospitalContext](#3-라우팅-및-hospitalcontext)
  - [4. 병원 선택 UI](#4-병원-선택-ui)
  - [5. 화이트라벨 브랜딩](#5-화이트라벨-브랜딩)
  - [6. 보안 규칙 재작성](#6-보안-규칙-재작성)
  - [7. 기존 데모 데이터 마이그레이션](#7-기존-데모-데이터-마이그레이션)
  - [8. 플랫폼 관리자 콘솔](#8-플랫폼-관리자-콘솔)
- [結 — 완료 기준·검증 전략·Next](#結--완료-기준검증-전략next)
- [부록](#부록)

---

## 📌 v2 업데이트 (2026-04-22)

> **이 파일은 PlusUltra v1 상세 가이드입니다.** v2 기준 문서 `GUIDE_v2/plusultra_v2.md` §Phase 1이 최종 실행 기준이며, 충돌 시 **v2가 우선**합니다.

### Phase 1 v2 조정사항

- ✅ **v1 원안 그대로 실행** — 5개 Phase 중 유일하게 구현 범위 변경 없음
- 🔸 **영업 포지셔닝 재정립**: "똑닥/MyChart 대체"가 아닌 **"똑닥 보완 — 원내 특화 화이트라벨 SaaS"**. 300베드 미만 중소·2차 병원 타깃 유지
- 🔸 **성공 기준에 MOAT 3축 의식**: Phase 1 완료 시 후속 MOAT(가족 대리 · 실손 청구 · 검사결과 무기한)의 **데이터 격리 기반**이 되도록 스키마·권한 설계 검토
- 🔸 **고령자 모드 토글 인프라를 P2에서 시작**하므로 Phase 1 HospitalContext 설계 시 user preference(`largeUi` 등) 필드 자리 예약 권장

### 적용 원칙

- 구현 세부·코드·스키마·라우팅·UIUX 가이드: **이 파일 v1 원안 준수**
- 우선순위·포지셔닝·후속 Phase 연결점: **v2 기준**
- 의심 시 `GUIDE_v2/plusultra_v2.md` §"Phase 1" 및 §"시장 포지셔닝 (v2 재정립)" 확인

---

## 起 — 왜 지금 Multi-Tenant인가

### 비즈니스 맥락
MediWay는 현재 **단일 데모 병원**(`demoHospital` 하드코딩)만 지원한다. 시장 조사 결과(`plusultra.md` 0장):
- 한국 상급종합병원은 이미 자체 앱 보유 (삼성서울·서울대·분당서울대 등)
- **공백 영역**은 300베드 미만 중소·2차 병원. 이들은 자체 개발 리소스 없음 → **SaaS 구독형이 적합**
- 화이트라벨 솔루션(Gozio·Connexient)은 미국 엔터프라이즈 가격대, 국내 중소 병원에 비쌈

**MediWay의 경쟁 우위 = "빠른 온보딩 + 낮은 비용 + 한국어 1급 UX"**를 실현하려면 "하나 설치 → 다수 병원 운영" 아키텍처가 **전제 조건**이다. 코드 복제로는 확장 불가능하다.

### 제품적 맥락
현재 코드베이스는 이미 **hospitalId 필드**를 도처에 두고 있다 (staff-codes·invitations·user). 그러나:
- 실제 데이터 격리는 이뤄지지 않음 (`visit_plans/$uid` 단일 트리)
- 병원 엔티티 자체가 코드에만 있음 (`src/data/hospital/index.ts`)
- 로고·테마·부서 목록 등 **병원 고유 속성이 DB에 없음**

Phase 1 목적은 **"hospitalId가 진짜 격리 키로 작동"**하도록 기반을 마련하는 것이다.

### 이번 Phase의 4대 가치
1. **확장성** — 100번째 병원을 추가해도 코드 변경이 없다
2. **격리** — 한 병원의 데이터/장애가 다른 병원에 전파되지 않는다
3. **브랜드 경험** — 환자는 "내 병원 앱"이라 느낀다 (MyChart의 가장 큰 단점을 극복)
4. **운영 가능성** — 플랫폼 관리자가 CLI 없이 병원을 온·오프할 수 있다

---

## 承 — 설계 원칙과 기술 선택

### 원칙 5계명
1. **Single codebase, per-tenant config** — 포크 금지. config는 DB·환경변수에.
2. **격리는 보안 규칙이 최종 방어선** — 앱 코드 버그가 있어도 RTDB 규칙이 막아야 함
3. **점진적 전환** — 배포 직후에도 기존 데모 라우트(`/patient`)가 살아있어야 함 (feature flag + 기간 한정 호환 레이어)
4. **O(1) 조회 최적화** — `hospitalId`는 모든 주요 엔티티에 비정규화하여 조인 없이 접근
5. **낙관적 UX, 비관적 규칙** — 클라이언트는 빠르게, 서버 규칙은 엄격하게

### 기술 스택 선택 근거

| 영역 | 선택 | 대안 검토 | 이유 |
|---|---|---|---|
| Multi-tenancy 전략 | **Single Auth + hospitalId 기반** | Firebase Auth Multi-tenancy (GCIP), 별도 Firebase 프로젝트 per 병원 | GCIP는 Identity Platform 유료($0.0025/MAU), 사용자 1명이 여러 병원 이용하는 시나리오(고령 부모)에서 각각 별도 계정 필요 → UX 악화 |
| 격리 메커니즘 | **RTDB Security Rules + Custom Claims** | Firestore 구조 변경 | 기존이 RTDB라 재사용. Rules에서 `auth.token.hospitalId === $hospitalId` 자연스러운 평가 |
| Custom Claims 설정 | **Cloud Functions `beforeCreate`/`onCall` trigger** | 클라이언트에서 직접 ID token payload 조작 | 클라에서 claim 쓰기 불가(Admin SDK만 가능). Functions 필수 |
| 라우팅 | **React Router `/h/:slug/*`** | 서브도메인 `smch.mediway.app` | 서브도메인은 SSL 와일드카드·DNS 관리 부담. Firebase Hosting 단일 도메인이 빠름. 나중에 B2B2C(일부 병원 커스텀 도메인) 확장 가능 |
| 브랜딩 주입 | **CSS Custom Properties (var)** | Tailwind theme runtime swap | Tailwind는 빌드 타임. CSS var는 런타임 즉시 반영 가능. Tailwind 토큰만 `var(--color-primary)` 참조하도록 변환 |
| Hospital 데이터 | **RTDB `/hospitals/{id}`** | Firestore 분리 | 이미 RTDB 쓰는데 이중 스택 금지. 트래픽 가벼움 |
| 로고·자산 | **Firebase Storage** | 외부 CDN | Storage가 Firebase Auth·규칙과 통합, 단일 콘솔 |

### 필요 선행 지식

| 분야 | 깊이 | 핵심 문서 |
|---|---|---|
| Firebase Realtime Database Rules | 실무 | https://firebase.google.com/docs/database/security |
| Firebase Auth Custom Claims | 실무 | https://firebase.google.com/docs/auth/admin/custom-claims |
| Cloud Functions for Firebase | 개념+실무 | https://firebase.google.com/docs/functions |
| React Router v6 — nested routes + loaders | 실무 | https://reactrouter.com |
| CSS Custom Properties | 기본 | MDN `--*` 변수 |
| Zustand or Context (상태관리) | 기본 | 프로젝트 이미 zustand 사용 |
| TypeScript discriminated unions | 기본 | user role/status 타이핑용 |

### 위험 조기 식별
- **Claim 전파 지연**: Firebase ID token은 최대 1시간 캐시됨. 역할·hospitalId 변경 후 즉시 반영되지 않는 문제 → `getIdToken(true)` 강제 갱신 훅 필요
- **마이그레이션 중 이중 상태**: 기존 `/visit_plans/$uid`와 신규 `/hospitals/{id}/visit_plans/$uid` 공존 기간 설계
- **라우팅 전환 시 deep link 깨짐**: 외부에 공유된 `/patient/:sessionId` URL → redirect 매핑
- **RTDB 규칙 한 파일의 복잡도 폭발**: 병원별 분기를 매번 쓰면 규칙 길이·가독성 악화 → shared `$hospital` 헬퍼 패턴

---

## 轉 — 세부 구현 설계

### 1. 데이터 모델 (RTDB)

#### 1.1 최종 스키마

```jsonc
{
  "hospitals": {
    "$hospitalId": {
      "profile": {
        "name": "string",           // "MediWay 데모 병원"
        "slug": "string",           // "demo" (URL-safe)
        "logoUrl": "string",        // https Storage URL
        "themeColor": "#004e9f",    // primary
        "themeColorAccent": "#0066cc",  // optional
        "contractStatus": "active|pilot|paused",
        "features": {
          "appointments": true,
          "inpatient": false,
          "checkup": true,
          "payment": false
        },
        "locale": "ko",
        "timezone": "Asia/Seoul",
        "createdAt": 1776000000000,
        "updatedAt": 1776000000000
      },
      "floor-plans": {
        "$level": { /* 기존 floor1Data 등을 JSON으로 저장 */ }
      },
      "pois": {
        "$poiId": { /* 기존 POI 구조 */ }
      },
      "departments": {
        "$deptId": { "name": "내과", "floorLevel": 2, "location": "2F-201" }
      },
      "staff_codes": {
        "$code": { /* 기존, hospitalId 포함 */ }
      },
      "announcements": {
        "$annId": { "title": "", "body": "", "publishedAt": 0, "expiresAt": 0 }
      }
    }
  },
  "users": {
    "$uid": {
      "primaryHospitalId": "demo",
      "hospitalIds": ["demo", "asan"],
      "hospitalRoles": { "demo": "admin", "asan": "patient" },
      "role": "admin",              // 최고 우선 역할 (legacy 호환)
      "email": "...",
      "displayName": "...",
      "status": "active",
      "createdAt": 0,
      "updatedAt": 0
    }
  },
  "visit_plans": {
    "$uid": {
      "hospitalId": "demo",         // 필수 추가
      "uid": "...",
      "waypoints": [],
      "source": "admin",
      "updatedBy": "...",
      "updatedAt": 0,
      "expiresAt": 0
    }
  },
  "sessions": {
    "$sessionId": {
      "hospitalId": "demo",         // 필수 추가
      // 기존 필드
    }
  },
  "audit_logs": {
    "$hospitalId": {
      "$id": { /* 기존 엔트리 + hospitalId scope */ }
    },
    "_platform": {                  // 플랫폼 레벨 감사
      "$id": { /* 계약 변경, 병원 온/오프 */ }
    }
  }
}
```

#### 1.2 설계 결정 근거

- **`hospitals/{id}/*` 수직 트리 vs flat + hospitalId 필터** — 자주 같이 불러오는 데이터(floor-plans, pois, departments)는 **수직 트리**로 단일 `onValue` 가능. 드물게 접근하는 데이터(audit_logs)는 hospitalId 키로 flat.
- **`users` 트리는 전역 단일** — 한 사용자가 여러 병원을 오갈 수 있어야 하므로 사용자 레코드는 병원 밖에. `hospitalRoles` map으로 병원별 역할 관리.
- **`visit_plans/{uid}` 구조 유지** + hospitalId 필드 추가 — 기존 E2E·코드·rules 최소 변경. 단, 한 사용자가 동시에 여러 병원에 방문 계획을 가지면 `visit_plans/{uid}/{hospitalId}` 형태가 필요하지만 **현재 요구사항 범위 밖**이므로 1:1 유지.
- **`role` 필드 legacy 유지** — `plusultra.md` 구조 전환 중 기존 코드 계속 동작하도록. P1 완료 후 P2 초반에 `hospitalRoles`로 완전 이관하고 `role` 제거.

#### 1.3 TypeScript 타입 정의

```ts
// src/types/hospital.ts — 확장
export type HospitalContractStatus = 'active' | 'pilot' | 'paused';

export interface HospitalProfile {
  name: string;
  slug: string;
  logoUrl: string;
  themeColor: string;
  themeColorAccent?: string;
  contractStatus: HospitalContractStatus;
  features: {
    appointments: boolean;
    inpatient: boolean;
    checkup: boolean;
    payment: boolean;
  };
  locale: 'ko' | 'en' | 'zh' | 'ja';
  timezone: string;
  createdAt: number;
  updatedAt: number;
}

// src/types/auth.ts — 확장
export type UserRole = 'patient' | 'staff' | 'admin' | 'platformAdmin';

export interface UserProfile {
  uid: string;
  primaryHospitalId?: string;
  hospitalIds: string[];
  hospitalRoles: Record<string, UserRole>;
  role: UserRole;                 // legacy — 가장 높은 권한
  email?: string;
  displayName?: string;
  status: 'active' | 'suspended' | 'deleted';
  createdAt: number;
  updatedAt: number;
}
```

---

### 2. 인증·권한 (Custom Claims)

#### 2.1 왜 Custom Claims인가

`hospitalId`와 `role`을 **ID token에 담아서** Firebase Auth가 RTDB 보안 규칙에 자동 전파하게 한다. 이유:

- **규칙 평가 비용 최소화** — 매 요청마다 `root.child('users/$uid/role').val()` 추가 DB 읽기 하지 않음
- **캐시 가능** — 1시간 JWT 캐시 → 트래픽 부담 경감
- **일관성** — role 변경은 Cloud Functions 한 곳에서만 일어남

**단점**: JWT는 최대 1시간 stale. 이를 해결하기 위해 클라이언트에서 role 변경 감지 시 `user.getIdToken(true)`로 강제 갱신 훅 추가.

#### 2.2 Cloud Functions 구조

```
functions/src/
  setClaims.ts          — 트리거: onUserWrite (/users/{uid}) → claim 동기화
  registerHospital.ts   — HTTP: platform admin이 병원 신규 생성
  updateClaimsOnRoleChange.ts — onCall: 관리자가 역할 변경 시 claim 즉시 갱신
```

#### 2.3 `setClaims` 구현 개요

```ts
// functions/src/setClaims.ts
import { onValueWritten } from 'firebase-functions/v2/database';
import { getAuth } from 'firebase-admin/auth';

export const syncUserClaims = onValueWritten(
  { ref: '/users/{uid}', region: 'asia-northeast3' },
  async (event) => {
    const uid = event.params.uid;
    const after = event.data.after.val();
    if (!after) {
      // 계정 삭제 — claim 초기화
      await getAuth().setCustomUserClaims(uid, null);
      return;
    }
    await getAuth().setCustomUserClaims(uid, {
      role: after.role ?? 'patient',
      hospitalId: after.primaryHospitalId ?? null,
      hospitalIds: after.hospitalIds ?? [],
      hospitalRoles: after.hospitalRoles ?? {},
    });
    // 클라이언트에서 감지할 수 있도록 bumped timestamp를 user 레코드에 기록 (optional)
    await event.data.after.ref.child('claimsUpdatedAt').set(Date.now());
  },
);
```

#### 2.4 클라이언트 훅

```ts
// src/hooks/useRefreshClaims.ts
import { useEffect } from 'react';
import { onValue, ref } from 'firebase/database';
import { auth, db } from '@/config/firebase';

export function useRefreshClaims(uid?: string) {
  useEffect(() => {
    if (!uid) return;
    const unsub = onValue(ref(db, `users/${uid}/claimsUpdatedAt`), async () => {
      if (auth.currentUser) await auth.currentUser.getIdToken(true);
    });
    return () => unsub();
  }, [uid]);
}
```

- **이유**: 서버에서 claim이 갱신되면 DB의 `claimsUpdatedAt`이 업데이트되고, 클라이언트는 이를 구독해 토큰을 즉시 refresh → 규칙 평가가 새 role·hospitalId로 즉시 동작.

#### 2.5 역할 체계

| 역할 | 범위 | 대표 권한 |
|---|---|---|
| `platformAdmin` | 전체 플랫폼 | 병원 생성·계약·모든 데이터 읽기 |
| `admin` (hospital admin) | 특정 병원 | 해당 병원 사용자·코드·공지 |
| `staff` (의료진) | 특정 병원 | 세션·계획 관리 |
| `patient` | 본인 + 소속 병원 공개 | 자기 데이터, 병원 공개 정보 |

이 체계는 `plusultra.md`의 "Hospital Admin vs Platform Admin 분리" 의사결정 포인트에 대한 **구체 답안**이다. 2단계 분리를 **처음부터 도입**한다 — 후에 소급 분리는 비용이 크다.

---

### 3. 라우팅 및 HospitalContext

#### 3.1 최종 라우팅 맵

```
/                                           — 마케팅 랜딩 (비로그인) / 로그인 후 리다이렉트
/login
/signup
/select-hospital                            — 신규 가입 후 병원 선택
/admin                                      — platform admin 콘솔
/h/:slug                                    — 병원 랜딩 (리다이렉트)
/h/:slug/patient                            — 환자 진입점
/h/:slug/patient/home
/h/:slug/patient/guide                      — 기존 안내 (지도 + QR)
/h/:slug/patient/:sessionId                 — 기존 QR 세션 링크 호환 (redirect)
/h/:slug/staff/dashboard
/h/:slug/admin                              — hospital admin
```

#### 3.2 HospitalContext 설계

```ts
// src/contexts/HospitalContext.tsx
interface HospitalContextValue {
  hospital: HospitalProfile | null;
  loading: boolean;
  error: Error | null;
  slug: string;
  userRoleHere: UserRole | null;
  canAccess: boolean;
}

export function HospitalProvider({ children }: { children: ReactNode }) {
  const { slug } = useParams<{ slug: string }>();
  const user = useAuthStore((s) => s.user);
  const [state, setState] = useState<HospitalContextValue>({...});

  useEffect(() => {
    if (!slug) return;
    // 1) slug → hospitalId 조회 (`/hospitals/_bySlug/{slug}` 역인덱스)
    // 2) `/hospitals/{id}/profile` 구독
    // 3) user.hospitalIds 포함 여부 판정
  }, [slug, user?.uid]);

  return <HospitalContext.Provider value={state}>{children}</HospitalContext.Provider>;
}
```

**역인덱스 `/hospitals/_bySlug/{slug}` → hospitalId**
- 이유: URL의 slug로 내부 hospitalId를 찾아야 함. 전체 hospitals 트리를 순회하면 O(N) 비용
- 스키마: `/hospitals/_bySlug/demo = "demo-hospital-uuid"` 등
- 쓰기: 병원 생성 Cloud Function에서 slug unique 보장 + 역인덱스 동시 쓰기

#### 3.3 라우트 가드

```tsx
// src/routes/RequireHospitalAccess.tsx
export function RequireHospitalAccess({ children }: { children: ReactNode }) {
  const { hospital, loading, canAccess } = useHospital();
  if (loading) return <LoadingScreen />;
  if (!hospital) return <Navigate to="/select-hospital" />;
  if (!canAccess) return <NoAccessScreen hospital={hospital} />;
  return <>{children}</>;
}
```

- 이유: 사용자가 URL을 조작해 다른 병원 경로로 진입해도 접근 제한 명확히 표시
- 세그먼트별 가드: `Patient`, `Staff`, `HospitalAdmin` 별 래퍼로 역할 체크

#### 3.4 Legacy 호환 리다이렉트

기존 외부 링크 `/patient/:sessionId` 형태의 QR이 이미 인쇄·발급되어 있을 수 있음. 삭제 대신:

```tsx
// /patient/:sessionId → /h/{slugFromSession}/patient/{sessionId}
<Route path="/patient/:sessionId" element={<LegacyPatientRedirect />} />
```

- 세션의 `hospitalId` 읽어서 해당 slug로 리다이렉트
- Phase 1~4 기간 유지, Phase 5에서 제거

---

### 4. 병원 선택 UI

#### 4.1 트리거 시점
1. 신규 이메일 회원가입 완료 직후
2. 사용자가 "병원 추가" 버튼 클릭 (다병원 이용)
3. 로그인했지만 `hospitalIds`가 비어있을 때 (예외 복구)

#### 4.2 화면 구성

```
┌─────────────────────────────┐
│ MediWay                     │
│                             │
│ 어느 병원에서 진료받으세요?    │
│                             │
│ 🔍 병원 검색                 │
│ [_________________________] │
│                             │
│ 📍 가까운 병원 (위치 기반)   │
│ ┌─────────────────────────┐│
│ │ 🏥 로고  삼성서울병원     ││
│ │         강남구 일원로 81  ││
│ │         1.2km · 활성      ││
│ └─────────────────────────┘│
│ ┌─────────────────────────┐│
│ │ 🏥 로고  MediWay 데모    ││
│ │         · pilot          ││
│ └─────────────────────────┘│
│                             │
│ 🔑 코드로 입력              │
│ [DEMO01________] [확인]     │
└─────────────────────────────┘
```

#### 4.3 기술 포인트

- **데이터 소스**: `/hospitals/_public` 역인덱스 (contractStatus: "active"만) — 모든 사용자가 읽기 허용
- **검색**: 클라이언트 `includes` 필터. 100개 이하 규모에서는 충분. 이후 Algolia 검토
- **위치 기반**: `navigator.geolocation.getCurrentPosition` + 각 병원의 `profile.geo = {lat, lng}` 필드 추가 → Haversine으로 정렬
- **접근성**: 탭 순서·Enter 제출·44px 터치 타겟
- **QR 부트스트랩**: URL `?hospital=demo` → 진입 시 해당 카드 자동 선택 + 하이라이트
- **빈 상태**: "가입 가능한 병원이 없습니다. 병원에서 받은 코드를 입력해 주세요"

#### 4.4 선택 확정 시 동작

```ts
async function selectHospital(hospitalId: string, role: UserRole = 'patient') {
  const uid = auth.currentUser!.uid;
  await update(ref(db, `users/${uid}`), {
    primaryHospitalId: hospitalId,
    hospitalIds: [...existingIds, hospitalId],
    hospitalRoles: { ...existingRoles, [hospitalId]: role },
    updatedAt: Date.now(),
  });
  // setClaims Function이 자동 감지 → claim 갱신
  // claimsUpdatedAt 구독 훅이 강제 token refresh
  navigate(`/h/${hospitalSlug}/patient/home`);
}
```

---

### 5. 화이트라벨 브랜딩

#### 5.1 CSS Custom Property 전략

현재 `tailwind.config.js`는 고정 `primary: '#004e9f'` 등을 쓴다. 이를 런타임 주입 가능하게 리팩터:

```js
// tailwind.config.js
theme: {
  extend: {
    colors: {
      primary: {
        DEFAULT: 'rgb(var(--color-primary) / <alpha-value>)',
        container: 'rgb(var(--color-primary-container) / <alpha-value>)',
      },
      // ...
    },
  },
},
```

- **핵심**: Tailwind 클래스 `bg-primary`, `text-primary`는 이제 `var(--color-primary)`를 참조
- CSS var 값은 런타임에 `document.documentElement.style.setProperty('--color-primary', '0 78 159')` 식으로 주입
- alpha 지원을 위해 `rgb(space-separated) / <alpha-value>` 포맷 사용 (Tailwind v3+ 표준)

#### 5.2 주입 로직

```tsx
// src/contexts/HospitalContext.tsx 내부
useEffect(() => {
  if (!hospital) return;
  const root = document.documentElement;
  root.style.setProperty('--color-primary', hexToRgbSpace(hospital.themeColor));
  if (hospital.themeColorAccent) {
    root.style.setProperty('--color-primary-container', hexToRgbSpace(hospital.themeColorAccent));
  }
  return () => {
    root.style.removeProperty('--color-primary');
    root.style.removeProperty('--color-primary-container');
  };
}, [hospital]);
```

- **이유**: React 트리 re-render 없이 즉시 전역 적용
- **접근성**: 브랜드 컬러가 너무 밝거나 어두울 경우 대비 검사. 제공 시 자동 보정 함수 (`ensureContrast`) 추가 가능 — 선택적

#### 5.3 로고·파비콘·메타

```tsx
<HelmetProvider>
  <Helmet>
    <title>{hospital.name} · MediWay</title>
    <link rel="icon" href={hospital.logoUrl} />
    <meta name="theme-color" content={hospital.themeColor} />
  </Helmet>
</HelmetProvider>
```

- `react-helmet-async` 사용 (의존성 추가)
- 이유: 브라우저 탭·iOS PWA 홈화면에 "내 병원" 로고·이름 표기

#### 5.4 다크 모드 호환
초기에는 light만 지원. 다크 모드는 P4 이후 병원이 요구하면 `themeColorDark` 추가.

---

### 6. 보안 규칙 재작성

#### 6.1 원칙
- 모든 병원 데이터 쓰기는 **`auth.token.hospitalIds` 포함 + `hospitalRoles[$hospitalId]` 매칭**으로 검증
- platform admin은 언제나 허용
- legacy root 경로(`visit_plans/$uid`)는 **shim 유지** (호환 기간)

#### 6.2 예시 규칙 (핵심 부분)

```jsonc
{
  "rules": {
    "hospitals": {
      "_bySlug": {
        ".read": true,        // slug 조회는 공개
        ".write": "auth.token.role === 'platformAdmin'"
      },
      "_public": {
        ".read": true,        // 가입 시 병원 목록 노출용
        ".write": "auth.token.role === 'platformAdmin'"
      },
      "$hospitalId": {
        "profile": {
          ".read": "auth != null && (auth.token.hospitalIds.contains($hospitalId) || auth.token.role === 'platformAdmin')",
          ".write": "auth.token.role === 'platformAdmin' || (auth.token.hospitalRoles[$hospitalId] === 'admin')"
        },
        "staff_codes": {
          "$code": {
            ".read": "auth != null",
            ".write": "auth.token.role === 'platformAdmin' || auth.token.hospitalRoles[$hospitalId] === 'admin' || (!data.child('usedBy').exists() && newData.child('usedBy').val() === auth.uid)"
          }
        },
        "pois":        { ".read": true, ".write": "auth.token.hospitalRoles[$hospitalId] === 'admin'" },
        "floor-plans": { ".read": true, ".write": "auth.token.hospitalRoles[$hospitalId] === 'admin'" },
        "announcements": { ".read": "auth != null", ".write": "auth.token.hospitalRoles[$hospitalId] in ['admin','staff']" }
      }
    },
    "users": {
      "$uid": {
        ".read":  "auth.uid === $uid || auth.token.role === 'platformAdmin'",
        ".write": "auth.uid === $uid || auth.token.role === 'platformAdmin'",
        "hospitalRoles": {
          ".write": "auth.token.role === 'platformAdmin' || auth.token.hospitalRoles[$hospitalId_newData] === 'admin'"
        }
      }
    },
    "visit_plans": {
      "$uid": {
        ".read": "auth.uid === $uid || auth.token.hospitalRoles[data.child('hospitalId').val()] in ['staff','admin'] || auth.token.role === 'platformAdmin'",
        ".write": "auth.uid === $uid || auth.token.hospitalRoles[newData.child('hospitalId').val()] in ['staff','admin'] || auth.token.role === 'platformAdmin'",
        "hospitalId":  { ".validate": "newData.isString() && root.child('hospitals').child(newData.val()).exists()" },
        "updatedBy":   { ".validate": "newData.val() === auth.uid" },
        "expiresAt":   { ".validate": "newData.isNumber() && newData.val() <= now + 172800000" },
        "waypoints":   { ".validate": "newData.hasChildren()" }
      }
    },
    "sessions": {
      "$sessionId": {
        ".read":  "auth.token.hospitalRoles[data.child('hospitalId').val()] in ['staff','admin'] || data.child('staffUid').val() === auth.uid || data.child('patientUid').val() === auth.uid || auth.token.role === 'platformAdmin'",
        ".write": "auth != null"   // 세부 validate로 제한
      }
    }
  }
}
```

- `auth.token.hospitalIds.contains()` — RTDB rule 내 배열 검사는 `.val().contains()` 형태로 문자열 조회. 실제로는 rule 언어가 `.hasChild()` 기반이므로 **hospitalIds를 배열이 아니라 map 형태**로 저장하는 편이 규칙 작성에 편리:

```jsonc
// 대체: hospitalIds 대신 hospitals 맵
{ "hospitals": { "demo": true, "asan": true } }
```

그리고 rule: `auth.token.hospitals[$hospitalId] === true`

⇒ **최종 결정**: Custom claim에 `hospitals: { demo: true }` 형태로 저장. 문서 전반의 `hospitalIds` 배열 표현은 유지하되 직렬화 시 map으로 변환.

#### 6.3 E2E 테스트 (보안 규칙)

`public/e2e-visit-plan.html` 패턴 재활용해 `public/e2e-hospital-isolation.html` 추가:
- 시나리오:
  1. 병원 A의 admin이 병원 A의 pois 쓰기 → 200
  2. 병원 A의 admin이 병원 B의 pois 쓰기 → 401
  3. 환자가 자기 hospitalId의 visit_plan 읽기 → 200
  4. 환자가 소속되지 않은 병원의 staff_codes 읽기 → 401
  5. platformAdmin이 모든 병원 profile 수정 → 200

---

### 7. 기존 데모 데이터 마이그레이션

#### 7.1 무엇을 옮기는가
- `src/data/hospital/index.ts` → `/hospitals/demo/profile`
- `src/data/hospital/floor-plans/floor{1..4}.ts` → `/hospitals/demo/floor-plans/{1..4}`
- `src/data/hospital/pois.ts` (`allPOIs`) → `/hospitals/demo/pois/{poiId}`
- 기존 staff-codes 전역 → `/hospitals/demo/staff_codes`
- 기존 visit_plans/$uid에 `hospitalId: "demo"` 필드 채움
- 기존 users 전원 → `primaryHospitalId: "demo"`, `hospitalIds: ["demo"]`, `hospitalRoles[demo] = role`

#### 7.2 스크립트 구성

```
data/
  migrate-to-multitenant.mjs
```

- Node ESM, firebase-admin SDK, serviceAccount impersonation (진단 때처럼)
- **Idempotent** — 여러 번 실행해도 문제 없게 `if (exists) skip` 패턴
- **Dry run 옵션** — `--dry` 플래그로 변경 사항만 출력
- 실행 순서: 병원 생성 → 정적 데이터 업로드 → 사용자 패치 → 기존 엔티티 hospitalId 백필 → 검증

#### 7.3 정적 데이터 → DB 이관 vs 번들 유지?

**두 전략 비교**

| 전략 | 장점 | 단점 |
|---|---|---|
| A. DB로 이관 | 병원별 편집 가능, LiDAR 스캔 결과물 반영 루트 확보 | 초기 로드 시 네트워크 요청 1회 필요 |
| B. 번들 유지 + DB는 메타만 | 초기 로드 빠름 | 병원마다 코드 변경·재배포 필요 → 확장성 죽음 |

**결정: A (DB로 이관)**. Phase 1의 목적 자체가 "코드 변경 없이 병원 추가". 캐싱은 React Query/SWR 전략으로 해결.

---

### 8. 플랫폼 관리자 콘솔

#### 8.1 필요 기능 (P1 minimum)
- 병원 목록
- 병원 생성 (name, slug, logo 업로드, theme color, features 체크박스)
- 계약 상태 토글 (active ↔ pilot ↔ paused)
- 초기 hospital admin 계정 지정 (이메일 입력 → invitation 발송)

#### 8.2 기존 `/admin` 경로 재구성
현재 `/admin`은 단일 병원 관리자 콘솔. 이를:
- `/admin` = **Platform Admin 전용** — 전체 병원 관리
- `/h/:slug/admin` = **Hospital Admin 전용** — 해당 병원 범위

기존 관리자 사용자(catlife9029@gmail.com)는 마이그레이션 시 `role: "platformAdmin"`으로 업그레이드. Hospital admin은 각 병원별로 별도 사용자 생성.

#### 8.3 UI 화면
- Dashboard: 활성 병원 수, 신규 가입자 7일 추이, audit 요약
- Hospitals 목록: 테이블 (slug·name·contract·사용자 수·생성일)
- Create Hospital form (단계별 마법사): profile → branding → initial admin → 완료

---

## 結 — 완료 기준·검증 전략·Next

### 완료 기준 (세부화)

#### 기능 기준
- [ ] `/hospitals/demo`가 DB에 존재, `profile/name = "MediWay 데모 병원"`
- [ ] 신규 환자 회원가입 → `/select-hospital` → 병원 선택 → `/h/demo/patient/home` 이동
- [ ] 드롭다운에서 위치 기반·검색·코드 입력 모두 동작
- [ ] 로고/테마 컬러가 런타임 주입되어 `bg-primary` 클래스가 해당 병원 컬러로 렌더
- [ ] 기존 QR 링크 `/patient/:sessionId` 접근 시 `/h/{slug}/patient/{sessionId}`로 자동 리다이렉트
- [ ] Platform admin이 `/admin`에서 새 병원 "asan" 생성 → 로그아웃 후 재로그인 없이도 `/h/asan`으로 접근 가능
- [ ] Hospital admin(demo)은 `/h/demo/admin`만 접근 가능, `/h/asan/admin` 접근 시 차단

#### 격리 기준 (E2E)
- [ ] `public/e2e-hospital-isolation.html` 5개 시나리오 모두 통과
- [ ] `public/e2e-visit-plan.html` 기존 시나리오 + hospitalId 검증 추가 통과

#### 품질 기준
- [ ] `npx tsc --noEmit` 통과
- [ ] `npx eslint` 경고 0
- [ ] Lighthouse mobile: Performance ≥ 80, Accessibility ≥ 95
- [ ] 기존 데모 플로우(`/patient?mode=browse`, `/patient?mode=guide`) 깨짐 없음

### 검증 전략

1. **자동**:
   - 규칙 E2E HTML 페이지 (2개)
   - Firebase Emulator Suite로 로컬 테스트 (`firebase emulators:start --only auth,database,functions`)
   - Vitest unit test — `services/hospitals.ts`, `contexts/HospitalContext.tsx` 로직

2. **수동**:
   - 시나리오 A: 새 브라우저 프로필 → 회원가입 → 드롭다운 → demo 선택 → 홈 이동
   - 시나리오 B: demo admin 계정으로 `/h/asan/admin` 접근 → 차단 화면
   - 시나리오 C: platformAdmin으로 병원 "asan" 생성 → 새 브라우저에서 asan으로 가입 → 격리 확인
   - 시나리오 D: 로고·테마 컬러 변경 → 사용자 화면 즉시 반영

3. **모니터링**:
   - Firebase Console Rules 시뮬레이터로 주요 경로 수동 테스트
   - Sentry 설치 → 에러 메시지 추적 (P2 시작 전)

### 롤백 계획

- 데이터: 마이그레이션 스크립트 역방향 버전(`migrate-rollback.mjs`) 준비
- 코드: main 브랜치 보호, Phase 1 작업은 `phase/p1-multitenant` 브랜치에서. 단일 병원 모드 동작 feature flag (`VITE_ENABLE_MULTITENANT=true`) — false일 때 legacy 경로만 노출
- 규칙: 이전 `database.rules.json` 태그로 보존 (`git tag pre-p1-rules`). 문제 시 `firebase deploy --only database`로 즉시 복원

### Next (Phase 2 진입 조건)
1. 완료 기준 100% 통과
2. 파일럿 병원 1곳 계약 또는 사내 QA 승인
3. Phase 2 시작 시 이 문서를 `PlusUltra#2.md`로 이어받아 **탭 셸 + 홈 위젯**으로 전개

---

## 부록

### 부록 A. 의사결정 레지스터

| ID | 결정 | 대안 | 근거 |
|---|---|---|---|
| D1 | Single Firebase project + claim 기반 isolation | Firebase Auth Multi-tenancy (GCIP), 프로젝트 분리 | 비용·UX·복잡도 우위 |
| D2 | slug는 path (`/h/:slug`) | 서브도메인 | SSL/DNS 부담, 빠른 출시 우선 |
| D3 | Tailwind CSS var 기반 theming | 런타임 tailwind-swap | 빌드 단순, 런타임 즉시 반영 |
| D4 | hospital admin vs platform admin 2단 분리 (처음부터) | 단일 admin 유지 | 후속 분리 비용 높음 |
| D5 | 정적 hospital 데이터를 DB로 이관 | 번들 유지 | 확장성 = Phase 1 목적 |
| D6 | legacy `/patient/:sessionId` 호환 유지 | 즉시 폐기 | 외부 인쇄 QR 보호 |
| D7 | `hospitalIds`를 claim에서 map으로 | 배열 | RTDB rule 문법 친화적 |

### 부록 B. 파일 생성·수정 체크리스트

**신규**
- `src/contexts/HospitalContext.tsx`
- `src/hooks/useRefreshClaims.ts`
- `src/pages/SelectHospitalPage.tsx`
- `src/pages/platform/PlatformAdminLayout.tsx`
- `src/pages/platform/PlatformHospitalsPage.tsx`
- `src/pages/platform/CreateHospitalPage.tsx`
- `src/routes/RequireHospitalAccess.tsx`
- `src/routes/RequireRole.tsx`
- `src/services/hospitals.ts`
- `src/components/hospital/HospitalHeader.tsx` (로고·이름)
- `functions/src/setClaims.ts`
- `functions/src/createHospital.ts`
- `public/e2e-hospital-isolation.html`
- `data/migrate-to-multitenant.mjs`
- `data/migrate-rollback.mjs`

**수정**
- `src/App.tsx` — 라우팅 개편
- `src/types/hospital.ts`, `src/types/auth.ts` — 타입 확장
- `src/data/hospital/*` — DB 이관 후 제거 또는 read-only reference
- `database.rules.json` — 전면 재작성
- `tailwind.config.js` — 컬러를 `rgb(var(--color-primary))`로 변환
- `index.html` — viewport, preload 힌트
- 기존 `src/pages/PatientPage.tsx` 및 관련 — 새 라우트 구조로 이동

### 부록 C. 예상 작업 견적 (1인 풀타임 기준)

| 작업 | 소요 |
|---|---|
| 데이터 모델·타입 정의·rules 초안 | 1.0일 |
| setClaims Function + claim 갱신 훅 | 1.0일 |
| HospitalContext + 라우팅 재구성 | 1.5일 |
| 병원 선택 UI + 검색/위치 | 1.0일 |
| 화이트라벨 theming (tailwind·css var) | 1.0일 |
| 보안 규칙 최종 + E2E 테스트 페이지 | 1.5일 |
| 마이그레이션 스크립트 | 0.5일 |
| 플랫폼 admin 최소 콘솔 | 1.5일 |
| 기존 데모 회귀 테스트·버그 픽스 | 1.0일 |
| **합계** | **10일 (≈ 2주)** |

### 부록 D. 학습 리소스 (빠른 참조)

- Firebase Auth Custom Claims: https://firebase.google.com/docs/auth/admin/custom-claims
- Firebase RTDB 규칙 가이드: https://firebase.google.com/docs/database/security
- RTDB rule 언어 핵심 연산자 (data/newData/root/auth/now): https://firebase.google.com/docs/reference/security/database
- Firebase Functions v2 트리거: https://firebase.google.com/docs/functions/beta/database-events
- React Router v6 nested routes: https://reactrouter.com/en/main/start/concepts
- Tailwind CSS with CSS variables: https://tailwindcss.com/docs/customizing-colors#using-css-variables
- White-label SaaS 설계 백서: https://developex.com/blog/building-scalable-white-label-saas/

---

## UIUX 가이드라인 (Phase 1)

본 절은 `uiux/` 폴더의 디자인 자산을 Phase 1 신규 화면에 **정확히 어떻게 녹일지** 정의한다. 이 섹션 없이는 동일 기능이 개발자마다 다른 모양으로 구현될 위험이 있다.

### U1. 참조 자산 매핑

`uiux/` 폴더는 **모바일 전용(`mobile_uiux/`)**과 **웹 전용(`web_page_uiux/`)** 목업을 분리해 제공한다. 각 폴더는 `code.html`(완성된 Tailwind HTML)과 `screen.png`(렌더 이미지)를 짝지어 두고 있다.

| 경로 | 대응 Phase 1 화면 | 용도 |
|---|---|---|
| `mobile_uiux/mediway_clinical/DESIGN.md` | 전체 | **디자인 시스템 성서**. "No-Line Rule", Surface Hierarchy, Glassmorphism 정의 |
| `web_page_uiux/mediway_clinical/DESIGN.md` | 전체 | 웹 버전 동일 |
| `web_page_uiux/mediway_phase_1.md` | 전체 기술 명세 | 초기 기술 스택(React18·TS·Vite·Zustand·Firebase·Leaflet)과 데이터 모델 |
| `mobile_uiux/mediway_select/` | **병원 선택 (모바일)** | 회원가입 후 드롭다운 화면의 모바일 레퍼런스 |
| `web_page_uiux/mediway_select/` | **병원 선택 (웹)** | 동일 기능의 데스크탑 레퍼런스 |
| `mobile_uiux/mediway_user_main/` | 홈 탭 (P2에서 본격 사용) | Phase 1에서는 병원 선택 완료 후 리다이렉트 대상의 **외형 힌트**로만 |
| `web_page_uiux/mediway_user_main/` | 홈 탭 (웹) | 동일 |
| `mobile_uiux/mediway_admin/`, `web_page_uiux/mediway_admin/` | Hospital Admin, Platform Admin | 기존 `/admin` 스타일의 확장 |
| `mobile_uiux/mediway_qr/` | 환자 QR (P2 안내 탭으로 흡수) | 참고만 |

**규칙**: Phase 1 신규 화면은 반드시 `uiux/{mobile_uiux | web_page_uiux}/mediway_*`에서 대응하는 페이지의 레이아웃·컬러·간격·컴포넌트 순서를 유지. 구현 시 `code.html`의 Tailwind 클래스를 출발점으로 삼되, 프로젝트의 `tailwind.config.js` 토큰과 P1에서 도입할 **CSS var(`var(--color-primary)`) 기반**으로 치환한다.

### U2. 디자인 시스템 — 핵심 원칙 요약

`mediway_clinical/DESIGN.md`를 Phase 1 기준으로 강제 적용.

1. **No-Line Rule** — 1px solid border 금지. 경계는 **surface 단계 차이**로만 표현 (`surface` ↔ `surface-container-low` ↔ `surface-container-lowest`).
2. **Surface Hierarchy** — 최상위 카드는 `surface-container-lowest` (흰색). 검색창·비활성 컨테이너는 `surface-container-high`.
3. **Glass & Gradient** — 플로팅 바·모달은 `surface-container-lowest/80` + `backdrop-filter: blur(20px)`. Primary CTA는 `linear-gradient(to right, primary, primary-container)`.
4. **Rounding** — 카드·입력·주요 CTA 는 `rounded-xl`(1.5rem). 날카로운 90° 각 금지.
5. **Ambient Shadow** — 그림자는 primary 색조가 약간 섞인 `shadow-[0_4px_24px_rgba(0,78,159,0.04)]` 형태. 순수 회색 그림자 금지.
6. **Touch Target ≥ 44×44px** — 버튼·링크 최소 히트 영역.
7. **Do Not** 블랙(`#000`) 텍스트. `on-surface`(`#1a1c1d`) 사용.

**Phase 1에서의 적용 영향**: 신규로 만드는 **병원 선택 카드**, **로고 헤더**, **플랫폼 admin 테이블**, **빈 상태 일러스트레이션**은 모두 위 원칙 내에서 작성된다. 이미 구현한 관리자 모바일 드롭다운과 DataTable도 동일 원칙이 이미 적용되어 있어 일관성 유지.

### U3. 모바일 vs 웹 — 근본적 차이

`code.html` 파일들을 교차 분석하면, 모바일과 웹의 **레이아웃 패턴이 정해져 있다**. 혼용하면 디자인 일관성이 깨진다.

| 축 | 모바일 (`< md` = <768px) | 웹 (`md+` ≥768px) |
|---|---|---|
| **최상단 바** | `fixed top-0` **TopAppBar** (h-16) · `backdrop-blur` 글래스 · 중앙 MediWay 로고 · 좌측 back, 우측 프로필 | `sticky top-0` **Header** · 좌측 브랜드(그라디언트 텍스트) · 중앙 탭 5개(Home/Outpatient/Inpatient/Check-up/Guidance) · 우측 알림·프로필 |
| **컨테이너 폭** | 전체 폭 (`px-4~6`) | `max-w-7xl mx-auto px-8` |
| **본문 레이아웃** | 단일 컬럼 세로 스택 (`flex flex-col gap-6`) | 2컬럼 그리드 (`lg:grid-cols-12`, 좌 7 + 우 5) 또는 bento grid |
| **주요 네비게이션** | **하단 BottomNavBar** (4~5 탭, `fixed bottom-0` · `rounded-t-[2rem]` · 안전 영역 padding) | 상단 Header 내 수평 탭 (BottomNav 없음) |
| **Proxy Payment CTA** | 리스트 최상단 큰 그라디언트 배너 | `col-span-2` 그리드 셀로 배치 |
| **Today's Schedule** | 단일 카드 스택, 좌측 1px primary 스트라이프(`absolute top-0 left-0 w-1 h-full bg-primary`) | 큰 카드 + 오른쪽 "View Details" 버튼 + 하단 안내 행 |
| **Quick Actions** | `grid grid-cols-2` 4개 정사각 카드 (아이콘 중앙) | `grid grid-cols-2` 4개 (아이콘 좌측 상단, 제목·서브 좌측) |
| **타이포 스케일** | Display/Headline는 한 단계 작게 (`text-3xl` 등) | 큼 (`text-4xl md:text-5xl`) |
| **여백** | 타이트 (`py-8`, `gap-4`) | 넓음 (`py-12`, `gap-8`) |
| **마진 바텀** | `pb-24` (BottomNav 높이 확보) | `mb-0` 또는 자연스러운 footer |

**Tailwind 반응형 규칙**:
- 모바일 전용 요소: `md:hidden`
- 웹 전용 요소: `hidden md:block` 또는 `md:flex`
- 공용 요소는 브레이크포인트 prefix로 속성 차등화 (`text-3xl md:text-5xl`, `py-8 md:py-12`)

**Phase 1 구현자 원칙**: 하나의 컴포넌트에서 모바일·웹을 **동시에** 기술하되, 구조가 근본적으로 다른 화면(예: 모바일은 BottomNav / 웹은 TopTabs)은 **별도 서브컴포넌트**로 분리해 `md:hidden` / `hidden md:block` 조건부 노출. 조건부 조합을 3단계 이상 섞지 말 것.

### U4. Phase 1 화면별 UIUX 적용 가이드

#### U4.1 병원 선택 페이지 (`/select-hospital`)

**공통 구조**: 헤더 + 검색 + 위치 기반 섹션 + 병원 카드 리스트 + 코드 입력 섹션 + 빈 상태

##### 모바일 (`mediway_select` 모바일 목업 기반)

```
┌──────────────────────────────────────┐
│ ← TopAppBar (MediWay)              ⚙ │  h-16, fixed, backdrop-blur
├──────────────────────────────────────┤
│                                      │
│   DASHBOARD  (label, uppercase)      │  pt-8, px-6
│   어느 병원에서                      │  text-3xl, font-semibold
│   진료받으세요?                      │
│                                      │
│  🔍 [병원 검색..............]        │  surface-container-high
│                                      │
│  📍 가까운 병원                      │  label
│  ┌────────────────────────────────┐ │
│  │ 🏥 logo  삼성서울병원         >│ │  surface-container-lowest
│  │         강남구 · 1.2km · 활성  │ │  rounded-xl, ambient shadow
│  └────────────────────────────────┘ │
│  ┌────────────────────────────────┐ │
│  │ 🏥 logo  MediWay 데모     >│   │
│  │         · pilot                 │ │
│  └────────────────────────────────┘ │
│                                      │
│  🔑 코드로 입력                      │
│  [DEMO01________] [확인 gradient]   │  Primary CTA: gradient
│                                      │
├──────────────────────────────────────┤
│     BottomNav (Home active)          │  hidden이지만 자리 확보: pb-24
└──────────────────────────────────────┘
```

- **CTA "확인"**: `bg-gradient-to-r from-primary to-primary-container text-on-primary rounded-xl`
- **카드 hover** 대신 `active:scale-[0.98]` (모바일 탭 피드백)
- **빈 상태**: 일러스트 + `emptyLabel` 큰 문구 + 보조 문구 (서포트 링크)
- BottomNav는 **없음** 대신 하단 여백(`pb-safe`)만 유지. 로그인 전이므로 BottomNav는 숨김

##### 웹 (`mediway_select` 웹 목업 기반)

```
┌──────────────────────────────────────────────────────────────┐
│ MediWay Healthcare      Home Outpatient Inpatient ...  🔔 👤 │  sticky header
├──────────────────────────────────────────────────────────────┤
│                         max-w-7xl mx-auto                     │
│  Good morning, Alex.                                          │
│  어느 병원에서 진료받으세요?                                   │
│                                                               │
│  ┌─────────── left (col-span-7) ────────┐ ┌── right (5) ──┐  │
│  │ 🔍 [검색창.....................]     │ │ 🔑 코드 입력  │  │
│  │                                      │ │ [_____] [확인]│  │
│  │ 가까운 병원                          │ │               │  │
│  │ ┌──────────────────────────────────┐│ │ 🎈 도움말     │  │
│  │ │ 🏥 logo  삼성서울병원            ││ │               │  │
│  │ │         1.2km · 활성       >     ││ │               │  │
│  │ └──────────────────────────────────┘│ │               │  │
│  │ ┌──────────────────────────────────┐│ │               │  │
│  │ │ 🏥 logo  MediWay Demo     >     ││ │               │  │
│  │ └──────────────────────────────────┘│ │               │  │
│  └──────────────────────────────────────┘ └───────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

- 2컬럼 그리드. 좌측은 병원 리스트, 우측은 코드 입력 + 도움말
- hover `bg-surface-container-low`
- 카드 클릭 시 전환: `transition-colors` + 선택 상태일 때 `ring-2 ring-primary`

#### U4.2 로그인/회원가입 페이지

기존 `mediway_1`(로그인) / `mediway_2`(회원가입) 목업 유지. Phase 1 변경점만 주입:
- **소셜 로그인 버튼** 자리 미리 확보 (실 구현은 P4) — 비활성 상태로 표시
- 회원가입 성공 후 **`/select-hospital`로 자동 이동** 로직만 추가. UI 변경 없음
- 코드 입력으로 가입 시(의료진/사전 초대 환자)는 병원 선택 스킵

#### U4.3 병원 헤더 (`HospitalHeader`)

모든 `/h/:slug/*` 경로 상단에 공통 노출.

##### 모바일
```
┌──────────────────────────────────────┐
│ [logo]  {hospital.name}     🔔  👤  │  h-16, backdrop-blur, fixed
└──────────────────────────────────────┘
```
- 로고: `w-8 h-8 rounded-full object-contain`
- 병원명: `text-lg font-semibold tracking-tight`
- 우측 알림·프로필은 32×32 버튼

##### 웹
```
┌────────────────────────────────────────────────────────────────┐
│ [logo] {hospital.name}    Home Outpatient Inpatient ... 🔔 👤 │
└────────────────────────────────────────────────────────────────┘
```
- 좌측 로고 + 이름
- Phase 1에서는 탭 영역은 **placeholder 비활성** (Phase 2에서 채움)

테마 컬러는 `style={{ '--color-primary': hospital.themeColor }}`로 헤더 루트에 주입.

#### U4.4 Platform Admin 콘솔 (`/admin`)

기존 `mediway_admin` 목업을 Phase 1 확장 대상에 재적용.

##### 모바일
- 드롭다운 내비게이션 (이미 Phase 0에서 D옵션으로 구현됨)
- 병원 목록: DataTable의 자동 모바일 카드 fallback 사용 (이미 구현됨)
- Create Hospital FAB(Floating Action Button) — `fixed bottom-24 right-4` (BottomNav 위)

##### 웹
- 좌측 세로 사이드바 유지 (관리자용은 정보 밀도 높음)
- 우측 메인: 테이블·폼
- Create Hospital은 우측 상단 `+ 병원 생성` 버튼 → 모달 마법사

#### U4.5 NoAccessScreen / Error States

- 로그인된 사용자가 미소속 병원으로 진입 시
- 카드 하나: 아이콘 + "이 병원에 접근 권한이 없습니다" + 두 CTA ("다른 병원 선택", "코드 입력")
- 모바일/웹 동일 레이아웃, 모바일은 `px-6 py-12`, 웹은 `max-w-md mx-auto py-24`

### U5. 반응형 브레이크포인트 체계

Phase 1에서 확정하고 Phase 2~5에서 그대로 계승.

| Token | 범위 | 타깃 디바이스 | 패턴 |
|---|---|---|---|
| `sm` (640px+) | 작은 태블릿, 큰 폰 | 가로 모드 폰 | 여백 증가만, 구조 유지 |
| `md` (768px+) | **모바일↔웹 경계** | 태블릿 세로 | **레이아웃 전환 트리거** — BottomNav off, TopTabs on |
| `lg` (1024px+) | 데스크탑 | 태블릿 가로, 노트북 | 2컬럼 그리드 도입, 사이드바 노출 |
| `xl` (1280px+) | 큰 데스크탑 | 데스크탑 모니터 | 3컬럼, 추가 정보 컬럼 |
| `2xl` (1536px+) | 초대형 | 와이드 모니터 | 전용 폭 `max-w-7xl` 유지 |

**핵심 경계 = `md`**. 이 이하는 "모바일 모드", 이상은 "웹 모드". BottomNav는 `md:hidden`, 상단 데스크탑 네비는 `hidden md:flex`.

### U6. 컬러·테마 — Phase 1 전용 추가 규정

- **브랜드 컬러 주입은 `rgb(var(--color-primary) / <alpha>)` 포맷** — Tailwind JIT의 `/<alpha-value>` 표기법과 호환
- Phase 1에서 도입: 모든 `bg-primary`, `text-primary`, `border-primary`, `ring-primary`는 CSS var 참조
- **절대 금지**: 컴포넌트에서 hardcoded `#004e9f` 문자열 사용. 반드시 Tailwind 토큰 경유
- **색상 fallback**: 병원 profile에 themeColor가 없으면 MediWay 기본(`#004e9f`) 사용
- **대비 검사**: 병원이 밝은 색 입력 시 on-primary(흰색) 가독성 낮음 → `ensureContrast(color)` 유틸이 필요하면 Phase 1 후반에 추가. 단기 해결은 관리자 콘솔에서 권장 팔레트만 노출

### U7. 타이포그래피 — 모바일 vs 웹 스케일

Inter 폰트를 기본. 크기는 Tailwind default + 설정된 tracking.

| 용도 | 모바일 | 웹 | 설명 |
|---|---|---|---|
| 페이지 Title | `text-2xl` (24px) `font-bold` | `text-4xl md:text-5xl` (36~48px) `font-extrabold tracking-tight` | Phase 1 핵심 페이지 |
| Section Heading | `text-lg font-semibold` | `text-2xl font-bold tracking-tight` | |
| Card Title | `text-base font-semibold` | `text-xl font-bold` | |
| Body | `text-sm` (14px) | `text-base` (16px) | |
| Label | `text-xs uppercase tracking-wider` | 동일 | 메타 정보에만 |
| CTA | `text-sm font-semibold` | `text-base font-semibold` | |

한국어 특성: tracking 너무 조여서는 안 됨(`tracking-tighter` 지양). `tracking-tight` 선까지.

### U8. 접근성 체크리스트 (Phase 1 대상 화면)

모든 신규 화면 완료 전 필수 검증:

- [ ] 컬러 대비 4.5:1 이상 (primary on white, primary on surface)
- [ ] 탭 순서: 헤더 → 검색 → 카드 리스트(키보드 ↑↓로 이동) → 코드 입력
- [ ] 모든 아이콘 버튼 `aria-label` 또는 `title`
- [ ] `role="menu"`, `role="menuitem"` — 드롭다운
- [ ] `aria-expanded`, `aria-haspopup` — 확장형 트리거
- [ ] 로고 `alt="{hospital.name} 로고"`
- [ ] 44×44px 터치 타겟 (mobile) / 32×32px (web)
- [ ] prefers-reduced-motion 감지 시 `transition-*` 해제
- [ ] Focus visible outline: `focus:ring-2 ring-primary ring-offset-2`

### U9. 구현 체크리스트 — UIUX 관점

Phase 1 종료 기준에 **UIUX 항목 추가**:

- [ ] **병원 선택 페이지**가 `mediway_select` 모바일·웹 목업과 80% 이상 일치 (레이아웃·컬러·간격)
- [ ] **HospitalHeader**가 `/h/:slug/*` 모든 라우트에 렌더, 모바일·웹 차이 적용
- [ ] **CSS var 기반 테마**로 `bg-primary`가 병원별 실제 컬러로 변경됨 (Chrome DevTools에서 HTML의 `--color-primary` 변경 시 즉시 반영 확인)
- [ ] **BottomNav(모바일)** vs **TopTabs(웹)** 분기 정상 동작 (viewport 리사이즈 테스트)
- [ ] **No-Line Rule** 준수: 신규 컴포넌트에서 `border-*` 클래스 사용 여부 grep → surface 토큰 기반 경계만 사용하는지 감사
- [ ] **Touch targets**: 모바일 주요 버튼이 44px 이상 (DevTools 측정)
- [ ] **Lighthouse Accessibility** 모바일·데스크탑 모두 95+
- [ ] **다크 모드 대비 없음** 확인 (Phase 1 범위 아님)
- [ ] **uiux/**에 새 화면 추가 시 mock html을 함께 업데이트하는 프로세스 안내 (PR 템플릿)

### U10. 피해야 할 흔한 함정

1. **모바일에서 desktop 레이아웃 그대로 축소** — `max-w-7xl mx-auto`를 모바일에서도 그대로 두면 여백이 망가짐. 반드시 모바일은 full-width
2. **웹에서 BottomNav 노출** — 웹 사용자에게 불필요. `md:hidden` 확실히
3. **CSS var 주입 누락** — 브랜드 컬러 변경 시 `HospitalContext` 언마운트될 때 cleanup 안 하면 다음 병원 진입 시 이전 컬러 잔존
4. **Tailwind JIT 안 되는 동적 클래스** — `bg-${color}` 같은 런타임 조합 금지. safelist에 등록하거나 CSS var 사용
5. **모바일 TopAppBar 공간 못 확보** — `fixed top-0 h-16`이면 본문에 `pt-16` 반드시
6. **하단 BottomNav 공간 못 확보** — `fixed bottom-0`이면 본문에 `pb-24` (iOS safe area 감안 `pb-[max(6rem,env(safe-area-inset-bottom))]`)
7. **"No-Line Rule"을 무시한 기본 `border` 사용** — DataTable 헤더·입력 필드 구현 시 주의. surface tint로 대체
8. **Editorial tone 무시한 flat 디자인** — 그라디언트·layering 없는 밋밋한 회색 카드는 브랜드 아이덴티티 훼손

### U11. 기간별 작업 분배 (UIUX 포함 갱신)

부록 C의 작업 견적을 UIUX 반영 버전으로 업데이트:

| 작업 | 이전 | UIUX 포함 신규 |
|---|---|---|
| 데이터 모델·타입·rules 초안 | 1.0일 | 1.0일 |
| setClaims Function + 훅 | 1.0일 | 1.0일 |
| HospitalContext + 라우팅 + **테마 주입** | 1.5일 | **2.0일** (+0.5, CSS var 리팩터) |
| **병원 선택 UI (모바일·웹 양쪽 구현)** | 1.0일 | **1.5일** (+0.5) |
| 화이트라벨 theming (tailwind·css var) | 1.0일 | 1.0일 |
| 보안 규칙 + E2E 테스트 페이지 | 1.5일 | 1.5일 |
| 마이그레이션 스크립트 | 0.5일 | 0.5일 |
| 플랫폼 admin 최소 콘솔 (모바일·웹) | 1.5일 | **2.0일** (+0.5) |
| **HospitalHeader + NoAccessScreen + 에러 화면** | — | **1.0일** (신규) |
| 기존 데모 회귀 테스트·버그 픽스 | 1.0일 | 1.0일 |
| **합계** | 10일 | **12.5일 (≈ 2.5주)** |

---

_작성일: 2026-04-22_
_대상 Phase: #1 — Multi-Tenant 기반_
_이어지는 문서: `PlusUltra#2.md` (Dashboard + Tabs)_
_UIUX 참조: `uiux/mobile_uiux/*`, `uiux/web_page_uiux/*`, `uiux/*/mediway_clinical/DESIGN.md`_
