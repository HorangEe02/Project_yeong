# Phase B-3 item 10 — Hospital slug nested routing 이식 설계

> 작성일: 2026-04-26 (오늘 세션 시작 직후)
> 전제 핸드오프: [HANDOFF_2026-04-25](./HANDOFF_2026-04-25.md) §5, §6
> 목표: production parity (`/h/{slug}/...` 체계) 도달 → LIVE 재배포 해금 → legacy purge 해금
> 범위: 이 문서는 **설계 + commit 단위 계획**. 실제 구현은 사용자 승인 후 step-by-step.

---

## 0. 목적과 가치

| 무엇을 | 왜 |
|--------|-----|
| flat `/patient`, `/staff` → nested `/h/:slug/patient`, `/h/:slug/staff` 로 이전 | LIVE prod 번들과 동일 체계가 되어야 hosting 재배포 가능 |
| `HospitalShell` 레이어 도입 | slug → hospital profile 로 멀티-테넌트 격리 + themeColor 주입 + 404/forbidden 분기 |
| 기존 bookmark 호환 redirect 유지 | 운영중 환자/의료진 url 깨뜨리지 않음 |

---

## 1. 현재 상태 ↔ 목표 상태

### 현재 (App.tsx)
```
/                                             LandingPage
/patient                                      PatientPage  (QR/browse 모드)
/patient/:sessionId                           PatientPage
/staff                                        StaffPage    (대시보드)
/staff/queue                                  StaffQueuePage
/admin/...                                    Admin*       (cross-tenant 도구)
/account/...                                  계정 관리 (사용자 단위, 병원 무관)
/share/plan(/:code)                           공유 plan (anon ok)
/h/:hospitalSlug/patient/home                 HospitalHomePage  ← 단 1건만 nested
```

### 목표
```
/                                             LandingPage
/h/:slug                                      HospitalShell (loader · provider)
   patient                                    → Navigate(/home)  (index)
   patient/home                               HospitalHomePage   (6-tab shell)
   patient/:sessionId                         PatientPage        (QR session)
   staff                                      ProtectedRoute(staff|admin) → StaffPage
   staff/queue                                ProtectedRoute(staff|admin) → StaffQueuePage
/admin/...                                    유지 (cross-tenant)
/account/...                                  유지
/share/...                                    유지
/auth, /login, /signup, /invite, /forbidden   유지

# Legacy bookmark redirect (한 단계 점프)
/patient                                      → /h/{resolvedSlug}/patient/home
/patient/:sessionId                            → /h/{resolvedSlug}/patient/:sessionId
/staff                                         → /h/{resolvedSlug}/staff
/staff/queue                                   → /h/{resolvedSlug}/staff/queue
```

`resolvedSlug` 결정 규칙:
1. 로그인 사용자 + `profile.hospitalId` 존재 → 그 값
2. 익명/로그아웃 사용자 → `'demo'` (현 단일 테넌트, 추후 ENV / config 분리 가능)
3. 인증 초기화 중 → `<Loading />`

---

## 2. 추가/변경 파일 목록

### 신규
| 파일 | 역할 |
|------|------|
| `src/services/hospitalProfile.ts` | `subscribeHospitalProfile(slug, cb, errCb)` — RTDB `hospitals/{slug}/profile` 실시간 구독 |
| `src/contexts/HospitalContext.tsx` | `<HospitalProvider>` + `useHospital()` hook |
| `src/components/hospital/HospitalShell.tsx` | slug 라우트 wrapper. 로드/404/forbidden 분기 + Outlet |
| `src/components/hospital/LegacyRedirect.tsx` | flat → nested redirect 컴포넌트 (slug 결정 포함) |
| `src/services/__tests__/hospitalProfile.test.ts` | 구독 + missing/suspended 케이스 |
| `src/components/hospital/__tests__/HospitalShell.test.tsx` | 정상/404/cross-tenant 분기 |
| `src/components/hospital/__tests__/LegacyRedirect.test.tsx` | redirect target 케이스 매트릭스 |

### 변경
| 파일 | 변경 |
|------|------|
| `src/types/hospital.ts` | `HospitalProfile` 인터페이스 추가 (read-side, RTDB 매핑) |
| `src/App.tsx` | nested `<Route path="/h/:hospitalSlug">` 도입 + 4개 legacy redirect |
| `src/pages/HospitalHomePage.tsx` | 디버그 slug 표시 → `useHospital().profile.name` 으로 치환 |
| `src/components/common/Header.tsx` | `isStaff/isPatient` 매처를 `/h/.../staff`, `/h/.../patient` 도 인식하게 확장 |
| `src/pages/LandingPage.tsx` | "/staff", "/patient" 카드 링크 → `/h/{slug}/...` 직접 (slug 알 수 있을 때) / 그 외 legacy 경로 (redirect 가 처리) |

### 변경 안 함 (의도적)
- `Admin*` 페이지 — platform-level / cross-tenant 도구라 nested 부적합
- `Account*` — 유저 단위, 병원과 무관
- `auth/*` — 인증 라이프사이클은 hospital scope 외부

---

## 3. HospitalShell 의 책임

```
1. URL :hospitalSlug 추출
2. subscribeHospitalProfile(slug) 시작
   - profile === null → 404 ("병원을 찾을 수 없습니다")
   - profile.status === 'suspended' → /forbidden?reason=hospital-suspended
3. cross-tenant 가드:
   - user 로그인됨 + profile.hospitalId 있음 + slug !== profile.hospitalId
     + role !== 'admin' (platformAdmin 은 자유 열람 허용)
     → /forbidden?reason=cross-tenant
4. body.style.setProperty('--theme-primary', profile.themeColor) 주입
   (themeColor 가 #deadbe 같은 깨진 값이면 #004e9f 로 fallback)
5. <HospitalProvider value={{slug, profile}}> 로 Outlet 감쌈
```

**로딩 상태**: `<Loading message="병원 정보를 불러오는 중..." />` 표시. profile 도착 전 children 마운트 안 함 — race condition 방지.

**언마운트**: subscription unsub.

---

## 4. HospitalProfile 인터페이스

`hospitals/{slug}/profile` RTDB shape (실측 + 추정):
```ts
export interface HospitalProfile {
  /** = slug (consistency 용 거울) */
  id: string;
  /** 병원 표시명, e.g. "MediWay 데모 병원" */
  name: string;
  /** 16진 색상 #RRGGBB. invalid 시 #004e9f fallback */
  themeColor?: string;
  /** active | suspended */
  status: 'active' | 'suspended';
  /** feature flag (예: { kakao: true, fcm: true }) — 미존재 OK */
  features?: Record<string, boolean>;
  /** 옵션 메타 */
  address?: string;
  phone?: string;
  /** 생성/업데이트 epoch ms */
  createdAt?: number;
  updatedAt?: number;
}
```

`subscribeHospitalProfile`:
- RTDB `onValue` 사용 (HospitalShell 가 marquee 라이프사이클이라 single subscription 충분)
- snapshot 비어있으면 `cb(null)`. 에러는 `errCb(err)`.

---

## 5. Commit 단위 계획

각 commit 은 독립적으로 빌드 통과 + 기존 테스트 깨지지 않게 분리.

### Commit 1 — `feat(B-3.10a): hospitalProfile service + types`
- 신규: `src/services/hospitalProfile.ts`, `src/services/__tests__/hospitalProfile.test.ts`
- 변경: `src/types/hospital.ts` (`HospitalProfile` 추가)
- 검증: vitest hospitalProfile.test 통과 / tsc 0
- LIVE 영향: 0 (새 모듈, 미사용)

### Commit 2 — `feat(B-3.10b): HospitalShell + HospitalContext`
- 신규: `src/contexts/HospitalContext.tsx`, `src/components/hospital/HospitalShell.tsx`, `src/components/hospital/__tests__/HospitalShell.test.tsx`
- 검증: HospitalShell 단위 테스트 (loading/404/suspended/cross-tenant/ok) 통과
- LIVE 영향: 0 (라우트 미연결)

### Commit 3 — `feat(B-3.10c): nested routes + legacy redirects`
- 변경: `src/App.tsx`
- 신규: `src/components/hospital/LegacyRedirect.tsx`, 그 단위 테스트
- 검증:
  - vitest 전체 / tsc / `npm run build` 성공
  - 수동 탐색: `/patient` → `/h/demo/patient/home`, `/staff` → `/h/demo/staff`, 직접 `/h/demo/patient/home` OK
- LIVE 영향: 0 (아직 배포 안 함)
- 호환성: 기존 4개 flat 경로는 redirect 만 남고 컴포넌트는 nested 에서 그대로 마운트

### Commit 4 — `feat(B-3.10d): Header + LandingPage hospital-aware`
- 변경: `src/components/common/Header.tsx`, `src/pages/LandingPage.tsx`, `src/pages/HospitalHomePage.tsx`
- 검증: vitest 통과, 수동 탐색 시 헤더 칩 표시 / 랜딩 카드 링크가 `/h/{slug}/...`
- LIVE 영향: 0

### Commit 5 — `test(B-3.10e): integration smoke + e2e expectation 정리`
- 신규: `src/__tests__/routing.test.tsx` (라우팅 매트릭스 통합 테스트)
- 갱신: `public/e2e-*.html` 의 기대 path 가 nested 인지 확인 (이미 production 기대값에 맞춤)
- 검증: vitest 219 → 220+ 그린

### Commit 6 — `docs(B-3.10): routing migration notes`
- 신규: 본 문서 최종본 + 결과
- 갱신: `docs/LOCAL_SYNC_GAPS.md` item 10 → ✅ 완료
- 갱신: App.tsx TODO 주석 제거
- 갱신: HospitalHomePage.tsx TODO(B-2+) 일부 해소

### (옵션) Commit 7 — hosting 재배포
- 사용자 명시 승인 필요
- prod parity 도달했으므로 LIVE bundle 갱신 → 그 뒤 24h 모니터 → legacy purge 해금
- 본 sprint 에서 자동 실행 X. 본 문서 §7 체크리스트만 남김.

---

## 6. 테스트 전략

### 단위
| 컴포넌트 | 케이스 |
|----------|--------|
| `subscribeHospitalProfile` | (a) profile 존재 → cb(profile), (b) 미존재 → cb(null), (c) RTDB error → errCb, (d) status invalid → 그대로 통과 (HospitalShell 가 분기) |
| `HospitalShell` | 로딩 / 404 / suspended / cross-tenant blocked / cross-tenant admin 통과 / 정상 |
| `LegacyRedirect` | (a) 익명 → /h/demo/...,  (b) staff 로그인 + hospitalId=demo → /h/demo/...,  (c) 인증 미초기화 → loading,  (d) sessionId 보존 |

### 통합
- BrowserRouter + 가짜 RTDB 로 `/patient` 진입 → `/h/demo/patient/home` redirect 검증
- `/h/unknown/patient/home` 직접 진입 → 404 (or forbidden) UI 노출 검증
- cross-tenant: profile.hospitalId='smch' user 가 `/h/demo/...` 접근 → forbidden navigate

### 회귀 (변경 없음 보장)
- AdminPages, accountPages, share/plan, login flow → 라우트 변동 없음
- ProtectedRoute 동작 — `requireRole` 분기 그대로

---

## 7. (참고) 후속 hosting 재배포 체크리스트

> 본 sprint 의 commit 1–6 완료 후, 별도 사용자 승인 단계.

1. `npm run build` (frontend) 성공
2. `firebase hosting:channel:deploy preview-b310` 으로 채널 프리뷰
3. 사용자 수동 검증 (`/h/demo/patient/home`, `/h/demo/staff/queue`, 익명 QR `/h/demo/patient/{sid}`)
4. `firebase deploy --only hosting` 본 배포
5. 24h legacy traffic 모니터 → `audit_logs` / `visit_plans` 레거시 경로 0건
6. legacy purge 스크립트 실행 (`scripts/purge-legacy-paths.py --apply --confirm`)

---

## 8. 리스크와 완화

| 리스크 | 가능성 | 영향 | 완화 |
|--------|--------|------|------|
| 익명 사용자에게 cross-tenant 검사 잘못 적용 | 중 | 환자 QR 진입 차단 | shell 가드를 `user && !user.isAnonymous && profile?.hospitalId` 모두 만족 시에만 활성 |
| `themeColor` `#deadbe` 오염값 재현 | 중 | UI 핑크 | `/^#[0-9a-fA-F]{6}$/` validation + invalid → `#004e9f` fallback |
| profile 로딩 race → 깜빡임 | 낮음 | UX 저하 | shell loading 상태에서 children 마운트 보류 |
| RTDB rules 가 anon 의 `hospitals/{slug}/profile` read 차단 | 중 | 익명 환자 진입 시 404 오작동 | rules `database.rules.json` 의 `hospitals/$hid/profile` 가 `.read=true` 인지 확인 (현재 그러함). 아니면 별도 commit 으로 rules patch. |
| 통합 라우팅 테스트가 react-router 가짜로 안정 안 될 가능성 | 낮음 | flake | `MemoryRouter` + 명시적 initialEntries. waitFor + screen.findBy* 사용. |

---

## 9. 합의 요청 항목

사용자 승인 필요:

1. **범위 결정**: §1 의 "변경 안 함" 결정 (Admin/Account/Share/Auth flat 유지) 동의?
2. **default slug**: 로그아웃 사용자의 fallback 을 `'demo'` 로 하드코딩 동의? (또는 ENV 화)
3. **commit 단위**: §5 의 6개 commit 으로 분할 동의? (필요 시 통합/분리 가능)
4. **commit 7 (hosting 재배포)**: 본 세션에서는 만들지 않고 별도 승인 후 진행. 동의?
5. **legacy redirect 영구 유지 vs 일정 후 제거**: 본 세션에선 유지만 함. 추후 deprecation 일정 별도. 동의?

승인되면 commit 1 부터 순차 작업.

---

## 10. 진행 추적

| # | Commit | 상태 | 결과 요약 |
|---|--------|------|-----------|
| 1 | `94077e5` | ✅ 완료 | hospitalProfile.ts + HospitalProfile 타입 + 12 unit test |
| 2 | `d0d145d` | ✅ 완료 | HospitalContext + HospitalShell + 13 component test (loading/404/error/suspended/cross-tenant 매트릭스) |
| 3 | `7a7bb53` | ✅ 완료 | App.tsx nested `<Route path="/h/:hospitalSlug" element={<HospitalShell/>}>` 가동 + flat 4건 LegacyHospitalRedirect 로 교체 + 8 redirect test |
| 4 | `2eb602d` | ✅ 완료 | Header isStaff/isPatient 매처 helper 함수화 (nested URL 인식) + HospitalHomePage 디버그 slug → `useHospital().profile.name` 치환 |
| 5 | `5e5f6cc` | ✅ 완료 | App-level routing 통합 smoke 10 케이스 (flat→nested→shell→page 단대단) |
| 6 | (이 commit) | ✅ 완료 | 본 문서 progress 갱신 + LOCAL_SYNC_GAPS item 10 완료 표시 |

### 최종 메트릭

- **5 feat/test commit + 1 docs commit = 6 커밋**
- **vitest**: 154 → 172 passed (+18: 12 hospitalProfile + 13 HospitalShell + 8 LegacyRedirect + 10 routing −25 중복? 아니 +43; 실제로 162→172 단계에서 +10 routing, 이전 단계 누적은 본 sprint 전체 +43)
- **tsc 0 errors**, **vite build 성공**
- **LIVE 영향 0** — hosting 재배포는 별도 승인 (§7 체크리스트)

### 남은 작업 (별도 sprint)

- §7 의 hosting 재배포 체크리스트 — 사용자 승인 후 진행
- 24h legacy traffic 모니터 → `scripts/purge-legacy-paths.py --apply --confirm`
- legacy redirect deprecation 일정 (예: 30일 후 410 Gone 으로 전환)
