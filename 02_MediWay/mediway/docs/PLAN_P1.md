# Phase 1 구현 계획 — Multi-Tenant 기반

> **상태**: 착수 (2026-04-22)
> **브랜치**: `mediway/plusultra/p1`
> **타깃 병합지**: `mediway/develop`
> **예상 기간**: 2주 (1인 풀타임)

---

## 0. 목표

현재 **단일 데모 병원 하드코딩** 상태를 **다수 병원을 수용할 수 있는 Multi-Tenant 기반**으로 전환.
후속 Phase(대시보드·편의 기능·접근성·고급)의 모든 구현이 **hospitalId 격리 위에서 안전하게 확장**되도록 토대를 만든다.

### 성공의 정의

1. `/hospitals/{id}` 서브트리에 여러 병원이 공존 가능
2. RTDB 보안 규칙이 `auth.token.hospitalId`로 데이터 교차 접근을 차단
3. 환자·의료진이 소속 병원에 따라 해당 병원 홈으로 자연 진입
4. 기존 데모 페이지(`/patient`)가 깨지지 않음 — 점진적 전환
5. 플랫폼 관리자가 병원 CRUD 가능

---

## 1. 스코프

### IN

| 영역 | 내용 |
|---|---|
| 데이터 모델 | `/hospitals/{id}` 서브트리 · `users` 확장 · `visit_plans`·`sessions`에 `hospitalId` 필드 |
| 인증·권한 | Firebase Custom Claims (role + hospitalId) · 토큰 갱신 전략 |
| 라우팅 | `/h/:slug/*` 신설 · `HospitalContext` · 레거시 `/patient` 리다이렉트 |
| UI | 병원 선택 페이지 · 화이트라벨 브랜딩(CSS custom properties) |
| 보안 | RTDB rules hospitalId 기반 재작성 · E2E 검증 페이지 |
| 운영 | 데모 병원 1회성 마이그레이션 스크립트 · 플랫폼 관리자 콘솔 |

### OUT (후속 Phase)

- 대시보드·탭 구조 → P2
- 실시간 대기·결제·알림톡 → P3
- 고령자 모드·OAuth 확장·가족 대리 → P4
- 검사결과·메시지·문진 → P5

### v2 고려사항 (구현에 반영할 사항)

- **고령자 모드 토글 자리 예약**: `UserProfile.preferences.largeUi: boolean` 필드를 P1 스키마에 미리 포함 (P2에서 인프라 시작)
- **가족 대리(F7) 데이터 격리 대비**: `/hospitals/{id}/family_links` 경로를 향후 추가할 수 있도록 rules 구조 설계
- **검사결과 무기한 보관(F3) 대비**: `/hospitals/{id}/health_records` 경로도 rules pattern 공유 가능하도록 헬퍼 작성

---

## 2. 선행 조건 확인 (pre-flight checklist)

- [x] `mediway/plusultra/p1` 브랜치 생성
- [x] `mediway/develop` 최신 반영
- [ ] 로컬 `.env.local` 세팅 (Firebase 연결 확인)
- [ ] Firebase CLI 로그인 + mediway-demo 프로젝트 접근 가능
- [ ] 현재 RTDB 스냅샷 백업 (마이그레이션 전 안전망)
- [ ] 기존 테스트 전체 통과 확인 (`npm test`)

---

## 3. 작업 순서 — 9개 논리 단위 (Commit 단위)

각 단위는 **독립 검증 가능한 커밋**. 모두 `mediway/plusultra/p1`에 누적되며, 전체 완료 시 `mediway/develop`으로 PR.

### Commit 1 — Types 확장 (Foundation)

**파일**
- `src/types/hospital.ts` — `Hospital`, `HospitalProfile`, `HospitalFeatures` 인터페이스 확장
- `src/types/user.ts` — `UserProfile`에 `primaryHospitalId`, `hospitalIds[]`, `hospitalRoles`, `preferences` 추가
- `src/types/auth-claims.ts` (신규) — Custom Claims 타입

**검증**
- `npx tsc --noEmit` 통과
- 기존 import 경로 호환성

**리스크**: 낮음 (타입만 추가, 런타임 영향 없음)

---

### Commit 2 — Hospital 서비스

**파일**
- `src/services/hospitals.ts` — `listHospitals`, `getHospital`, `createHospital`, `updateHospital`, `subscribeHospital`
- `src/services/__tests__/hospitals.test.ts`

**검증**
- 단위 테스트: mock Firebase RTDB로 CRUD 동작 확인

**리스크**: 중간 (RTDB 경로 규약 확정 필요)

---

### Commit 3 — HospitalContext + Provider

**파일**
- `src/contexts/HospitalContext.tsx` — slug → hospital profile 구독, 로딩·에러 상태
- `src/hooks/useHospital.ts` — context 소비 훅
- `src/components/common/HospitalGate.tsx` — slug 미선택 시 redirect, 로딩 UI

**검증**
- 테스트: slug 변경 시 context 재구독
- 레거시 `/patient` 라우트가 `primaryHospitalId` 기반으로 자동 redirect 되도록

**리스크**: 중간 (기존 라우팅과의 공존 로직 주의)

---

### Commit 4 — 라우팅 재구성

**파일**
- `src/App.tsx` — `/h/:slug/*` 라우트 추가
- `src/pages/redirect/LegacyPatientRedirect.tsx` — `/patient` → `/h/{primaryHospitalId}/patient`
- `src/pages/redirect/LegacyStaffRedirect.tsx` — 동일 패턴

**검증**
- 기존 deep link (`/patient/:sessionId`)가 redirect 후에도 세션 복원
- Platform admin `/admin`은 변경 없음

**리스크**: 높음 (deep link 호환성)

---

### Commit 5 — 화이트라벨 브랜딩

**파일**
- `src/styles/theme.css` (신규) — `:root { --color-primary: #004e9f; … }` 기본값
- `tailwind.config.js` — token 값을 `var(--color-primary)` 등 참조로 변경
- `src/contexts/HospitalContext.tsx` — `useEffect`로 `document.documentElement.style.setProperty`

**검증**
- 시각적 확인: 테마 색상 반영
- 기본값 fallback (hospital 로딩 전)

**리스크**: 중간 (Tailwind 토큰 마이그레이션 범위)

---

### Commit 6 — 병원 선택 UI

**파일**
- `src/pages/SelectHospitalPage.tsx` — 드롭다운 + 검색 + URL `?hospital=` 부트스트랩
- `src/components/hospital/HospitalCard.tsx`
- 사전 초대(`/invite/:token`) 플로우와 통합

**검증**
- URL 파라미터로 자동 선택
- 빈 상태 ("가입 가능 병원 없음")
- 가입 플로우에서 `SignupPage` 후 이 페이지로 이동

**리스크**: 낮음 (격리된 UI)

---

### Commit 7 — Custom Claims Cloud Function

**파일**
- `functions/src/setClaims.ts` (신규) — `onCreate` trigger + `setUserRole` callable
- `functions/src/index.ts` — export 추가
- `src/hooks/useRefreshToken.ts` (신규) — `getIdToken(true)` 강제 갱신

**검증**
- Emulator에서 trigger 동작 확인
- claim 갱신 후 토큰 payload에 `hospitalId`·`role` 반영

**리스크**: 높음 (claim 전파 지연 이슈 — 최대 1시간 캐시)

---

### Commit 8 — RTDB 보안 규칙 재작성

**파일**
- `database.rules.json` — hospitalId 기반 전면 재작성
- `public/e2e-hospital-isolation.html` — E2E 테스트 페이지
- `docs/SECURITY_RULES_GUIDE.md` (갱신) — 헬퍼 함수 설명

**검증**
- `firebase deploy --only database`
- E2E 테스트: 다른 병원 데이터 접근 시 401
- 기존 테스트 페이지 (`public/e2e-visit-plan.html`) 여전히 통과

**리스크**: ★★★ **최고** (보안 규칙 오류 시 데이터 유출 가능)

### 보안 규칙 설계 초안

```
{
  "rules": {
    ".read": false,
    ".write": false,

    "hospitals": {
      "$hospitalId": {
        "profile": {
          ".read": "auth != null",
          ".write": "auth.token.role == 'platformAdmin'"
        },
        "floor-plans": {
          ".read": "auth != null && (auth.token.hospitalId == $hospitalId || auth.token.role == 'platformAdmin')",
          ".write": "auth.token.role == 'platformAdmin' || (auth.token.role == 'admin' && auth.token.hospitalId == $hospitalId)"
        },
        "visit_plans": {
          "$uid": {
            ".read": "$uid === auth.uid || auth.token.role in ['staff','admin','platformAdmin']",
            ".write": "..."
          }
        }
      }
    },

    "users": { /* 기존 유지 */ },
    "audit_logs": { /* hospitalId 하위로 이동 검토 */ }
  }
}
```

---

### Commit 9 — 마이그레이션 스크립트

**파일**
- `scripts/migrate-demo-hospital.mjs` (신규 · 1회성)
- `scripts/README.md` — 실행 방법

**동작**
1. 현재 `src/data/hospital/demoHospital`의 정적 데이터 → `/hospitals/demo/*`에 업로드
2. 기존 `/users/*`에 `primaryHospitalId: 'demo'` 채움
3. 기존 `/visit_plans/*`·`/sessions/*`에 `hospitalId: 'demo'` 필드 추가
4. dry-run 모드 + commit 모드

**검증**
- Dry-run 결과 확인 후 commit 실행
- 마이그레이션 후 기존 페이지 정상 동작

**리스크**: ★★ (데이터 수정, 1회성이지만 되돌리기 어려움)

---

### Commit 10 — 플랫폼 관리자 콘솔

**파일**
- `src/pages/admin/HospitalsPage.tsx` — 병원 목록·생성·편집·활성화
- `src/components/admin/HospitalForm.tsx`
- 기존 `/admin`에 "병원 관리" 메뉴 추가

**검증**
- `role === 'platformAdmin'` 아닌 사용자는 접근 불가 (403)
- 생성·편집·비활성 정상 동작

**리스크**: 낮음 (CRUD UI)

---

## 4. 데이터 모델 상세

### 4.1 `/hospitals/{hospitalId}`

```typescript
interface Hospital {
  profile: HospitalProfile;
  'floor-plans': Record<string, FloorPlan>;
  pois: Record<string, POI>;
  'staff-codes': Record<string, StaffCode>;
  departments: Record<string, Department>;
  announcements: Record<string, Announcement>;
}

interface HospitalProfile {
  name: string;              // "MediWay 데모 병원"
  slug: string;              // "demo" — URL 노출
  logoUrl?: string;          // Firebase Storage URL
  themeColor: string;        // "#004e9f"
  contractStatus: 'active' | 'pilot' | 'paused';
  features: HospitalFeatures;
  createdAt: number;
  updatedAt: number;
}

interface HospitalFeatures {
  appointments: boolean;     // P2 외래 탭
  inpatient: boolean;        // P2 입원 탭
  checkup: boolean;          // P2 검진 탭
  payment: boolean;          // P3
  prescription: boolean;     // P3
  parking: boolean;          // P3 (파일럿별)
  aiTriage: boolean;         // v2 신규 F19
  familyDelegation: boolean; // P4 F7
  healthRecords: boolean;    // P5 F3
}

interface Department {
  id: string;
  name: string;
  locationPoiId?: string;    // POI 참조
  floorLevel: number;
}
```

### 4.2 `/users/{uid}` 확장

```typescript
interface UserProfile {
  // 기존
  uid: string;
  email: string;
  displayName?: string;
  status: 'active' | 'suspended' | ...;
  createdAt: number;
  updatedAt: number;

  // ★ Multi-Tenant 확장
  primaryHospitalId?: string;                // 로그인 시 기본 병원
  hospitalIds?: string[];                    // 가입된 병원들
  role: 'patient' | 'staff' | 'admin' | 'platformAdmin';
  hospitalRoles?: Record<string, Role>;      // 병원별 역할 (가족 대리 대비)

  // ★ v2 예약 필드
  preferences?: {
    largeUi?: boolean;                       // P2에서 활성, P1은 자리만
    notificationChannels?: ('push'|'sms'|'email')[];
    language?: 'ko' | 'en' | ...;            // P5 i18n 대비
  };
}
```

### 4.3 `/visit_plans/{uid}` 확장

기존 필드 유지 + `hospitalId: string` 추가. 마이그레이션에서 `'demo'` 채움.

### 4.4 Custom Claims

```jsonc
{
  "role": "patient",
  "hospitalId": "demo",             // primary
  "hospitalIds": ["demo", "smch"]   // multi-hospital 대비
}
```

---

## 5. 마이그레이션 전략

### 5.1 단계

1. **스냅샷 백업** — `firebase database:get / > backup-pre-p1.json`
2. **드라이런** — `node scripts/migrate-demo-hospital.mjs --dry-run`
3. **검수** — 영향 경로·개수 확인
4. **실행** — `node scripts/migrate-demo-hospital.mjs --commit`
5. **사후 검증** — E2E 페이지로 교차 접근 차단 확인

### 5.2 롤백

- 마이그레이션 도중 실패 시 백업에서 `firebase database:update / backup-pre-p1.json`으로 복원
- Commit 8 (rules) 문제 시 이전 rules 파일로 재배포

### 5.3 구 라우트 호환

- `/patient` 라우트는 **최소 1 Phase 유지** (P2까지)
- 로그인 사용자는 `primaryHospitalId` 기반 `/h/:slug/patient`로 redirect
- 익명 QR 세션은 세션 토큰의 hospitalId로 분기

---

## 6. 테스트 전략

### 단위 테스트

- `src/services/hospitals.test.ts` — CRUD
- `src/contexts/HospitalContext.test.tsx` — slug 변경 재구독
- `functions/src/setClaims.test.ts` — claim 설정

### E2E 테스트 페이지

- `public/e2e-hospital-isolation.html` — 다른 병원 데이터 접근 시 401 검증
- 기존 `public/e2e-visit-plan.html` regression 확인

### 수동 QA 체크리스트

- [ ] 신규 환자 가입 → 병원 선택 → 해당 병원 홈
- [ ] 스태프 코드 가입 → hospitalId 자동 설정
- [ ] 기존 `/patient` URL → `/h/demo/patient`로 redirect
- [ ] 로고·테마 색상 브랜딩 반영
- [ ] 플랫폼 관리자 병원 생성·편집·비활성
- [ ] 다른 병원 데이터 직접 접근 시 403/null

---

## 7. 리스크 레지스터 (P1 한정)

| 리스크 | 확률 | 영향 | 완화 |
|---|---|---|---|
| RTDB rules 오류로 데이터 유출 | 중 | 크리티컬 | E2E 테스트 페이지 + dry-run emulator |
| Custom claim 전파 지연 | 높 | 중 | `getIdToken(true)` 강제 갱신 훅 + UI 로딩 상태 |
| 기존 데모 라우트 깨짐 | 중 | 높 | Legacy redirect 컴포넌트 + 1 Phase 병존 |
| 마이그레이션 중복 실행 | 낮 | 중 | idempotent 스크립트 (이미 존재 시 skip) |
| deep link 호환성 | 중 | 중 | redirect 매핑 + 세션 복원 로직 |
| Tailwind 토큰 마이그레이션 누락 | 중 | 낮 | 전체 search-replace + 시각 검사 |

---

## 8. 완료 기준 (PlusUltra#1.md §結 준수)

- [ ] 데모 병원 `/hospitals/demo`에 정상 저장, 기존 환자 페이지 동작
- [ ] 신규 환자 회원가입 → 병원 선택 → 해당 병원 홈 이동
- [ ] 의료진 코드 가입 시 hospitalId 자동 설정
- [ ] RTDB 보안 규칙 E2E 테스트 통과
- [ ] 다른 병원 데이터 교차 접근 시 401
- [ ] 플랫폼 관리자가 전체 병원 목록 관리 가능
- [ ] `npx tsc --noEmit` 통과
- [ ] `npm test` 통과 (기존 + 신규 단위 테스트)
- [ ] `mediway/develop`에 PR 오픈 + 셀프 리뷰 체크리스트

---

## 9. 예상 일정 (Day-level)

| Day | 작업 |
|---|---|
| 1 | Commit 1·2 (Types + hospitals service) |
| 2 | Commit 3 (HospitalContext) |
| 3 | Commit 4 (라우팅 재구성) |
| 4 | Commit 5 (화이트라벨 브랜딩) |
| 5 | Commit 6 (병원 선택 UI) |
| 6 | Commit 7 (Custom Claims Cloud Function) |
| 7-8 | Commit 8 (RTDB 규칙 재작성 + E2E 페이지) — ★ 집중 |
| 9 | Commit 9 (마이그레이션 스크립트 + 드라이런) |
| 10 | Commit 10 (플랫폼 관리자 콘솔) |
| 11 | 통합 테스트 · 수동 QA · 버그 수정 |
| 12 | 마이그레이션 실행 · 배포 전 최종 검증 |
| 13 | `mediway/develop` PR · 리뷰 · 병합 |
| 14 | 예비일 |

---

## 10. 참조

- `GUIDE_v2/PlusUltra#1.md` — 상세 구현 가이드 (v1 + v2 상단 조정 블록)
- `GUIDE_v2/plusultra_v2.md` §Phase 1 — v2 실행 기준
- `mediway/docs/PHASE_E_SPEC.md` — 기존 multi-hospital 스펙 (참고용, v2와 일부 충돌)

---

_작성일: 2026-04-22_
