# Day 2 상세 작업 계획 — Login/Dashboard 폴리싱 + 더미 데이터 시드

> **Phase**: 1 확장 (Phase 1 마감 작업)
> **목표 일수**: 1 (8시간 가정)
> **선행 조건**: Day 1 부트스트랩 완료 — Vite + TS strict + 라우터 + i18n + 셸 + 인증 가드 모두 동작
> **작성일**: 2026-04-27
> **관련 문서**: [REACT_MIGRATION_PLAN.md](REACT_MIGRATION_PLAN.md), [WEB_DESIGN_SPECIFICATION.md](WEB_DESIGN_SPECIFICATION.md)

---

## 목차

1. [Day 2 전체 목표](#1-day-2-전체-목표)
2. [Day 1 마감 시점 진단](#2-day-1-마감-시점-진단)
3. [작업 카테고리 개요 (A/B/C)](#3-작업-카테고리-개요-abc)
4. [A. Login 정밀 폴리싱 (3시간)](#4-a-login-정밀-폴리싱-3시간)
5. [B. Dashboard 정밀 폴리싱 (2.5시간)](#5-b-dashboard-정밀-폴리싱-25시간)
6. [C. 더미 데이터 시드 + Mock API (2시간)](#6-c-더미-데이터-시드--mock-api-2시간)
7. [공통 보강 작업 (0.5시간)](#7-공통-보강-작업-05시간)
8. [Day 2 시간 배분표](#8-day-2-시간-배분표)
9. [검증 체크리스트](#9-검증-체크리스트)
10. [위험 요소 + 완화](#10-위험-요소--완화)
11. [Day 2 산출물 (Day 3 시작 전 준비물)](#11-day-2-산출물-day-3-시작-전-준비물)

---

## 1. Day 2 전체 목표

| # | 목표 | 측정 기준 |
|:--:|---|---|
| 1 | **Login 페이지를 본선 데모 수준의 완성도로** | 로그인 흐름·실패 케이스·비번 변경·접근성 모두 동작 |
| 2 | **Dashboard 페이지를 데이터 시각화 가능한 골격으로** | 6 모듈 카드가 RBAC + 부서로 필터링되며, 실제 메트릭 노출 |
| 3 | **백엔드 없이도 데모 가능한 Mock API 인프라 구축** | `VITE_USE_MOCK=true` 환경변수로 전환, 24명 사원 + 메트릭 + 시나리오 |
| 4 | **Day 3 (공통 컴포넌트) 작업의 의존성 제거** | Button/Card/Badge 등을 Day 2에서 일부 추출 |

### Day 2가 끝나면 가능한 시연:
1. `http://localhost:5173/login` → 사원번호·비번 입력 → 로그인
2. 비번이 정책 미달 시 6 조건 카드 실시간 점등
3. 로그인 실패 시 친절한 에러 메시지 + 재시도
4. 로그인 성공 → Dashboard로 자동 이동
5. Dashboard에서 6 모듈 카드 RBAC 필터링된 결과 확인
6. 우측 패널의 Data Ingestion이 Mock 데이터로 채워져 있음
7. 한·영 토글 시 모든 텍스트 자연스럽게 전환
8. 라이트/다크/자동 테마 전환 시 로고·차트·글래스 모두 갱신

---

## 2. Day 1 마감 시점 진단

### 2-1. 동작하는 것
- ✅ Vite dev 서버 (`http://localhost:5173`)
- ✅ TS strict 컴파일 통과
- ✅ React Router 6 + 가드 (`<RequireAuth>`, `<RequireRole>`)
- ✅ Zustand store (auth/theme/ui) + persist
- ✅ i18n (한·영 78 키)
- ✅ 셸 컴포넌트 (TopBar/LeftSidebar/RightPanel)
- ✅ 9 라우트 (login + dashboard + 6 모듈 placeholder + shell)
- ✅ Liquid Glass 적용 (TopBar/RightPanel/Login card)
- ✅ axios 클라이언트 + JWT auto-refresh interceptor

### 2-2. 미흡한 부분 (Day 2에서 보완)
| 항목 | 현재 상태 | Day 2 목표 |
|---|---|---|
| **로그인 실패 UX** | 단순 에러 메시지 박스 | 잠금 카운트다운 + 재시도 버튼 + 안내 톤 |
| **비밀번호 변경** | 라우트 없음 | `must_change_pw=true` 시 자동 모달 + 강도 표시 |
| **데모 계정 빠른 로그인** | 없음 | 33명 중 4종 RBAC 빠른 로그인 칩 (개발 모드만) |
| **로그인 후 자동 이동** | 무조건 `/` | Referer 또는 originalRoute 복원 |
| **Dashboard 메트릭** | 하드코딩 (329/201/29/33) | API 호출 또는 Mock store에서 |
| **Dashboard 모듈 카드** | 모두 표시 | RBAC + 부서별 필터링 |
| **Dashboard 환영 메시지** | 없음 | 사용자 부서 + 마지막 로그인 시각 |
| **Dashboard 빠른 액션** | 없음 | "최근 작성한 문서 / 진행 중 알람 / 오늘의 SOP" 3종 |
| **Mock API** | 없음 | MSW 또는 자체 mock client |
| **로고 전환** | 라이트/다크 자동 | 폰트 fallback 검증 (AJIN Sans 미로딩 시) |
| **Login 키보드** | autoComplete만 | autoFocus + Enter 키 + 캡스락 경고 |
| **반응형 검증** | CSS만 | 768/1024 실제 시연 |

### 2-3. Day 2 직전 알려진 이슈
| 이슈 | 영향도 | 해결 시점 |
|---|:--:|:--:|
| AJIN Sans 폰트 파일명에 Korean ID(`__________`) — Vite 처리 OK | 🟢 낮 | Day 2에서 검증만 |
| 우측 패널 토글 시 메인 영역 폭 점프 | 🟡 중 | Day 2 마감 시점 transition 추가 |
| Login 화면에서 사이드바·우측 패널 미노출 (인증 가드 효과) | 🟢 정상 | — |
| Mock 모드 환경변수 미정의 | 🔴 차단 | **Day 2 작업 1순위** |

---

## 3. 작업 카테고리 개요 (A/B/C)

```
Day 2 (8h)
│
├─ A. Login 정밀 폴리싱 (3.0h)
│  ├─ A1. 비밀번호 정책 6조건 실시간 검증 강화 (0.5h)
│  ├─ A2. 잠금/실패/오류 케이스 UX (0.75h)
│  ├─ A3. 비밀번호 변경 모달 (must_change_pw) (0.75h)
│  ├─ A4. 데모 빠른 로그인 칩 (4 RBAC) (0.5h)
│  └─ A5. 키보드/접근성 + originalRoute 복원 (0.5h)
│
├─ B. Dashboard 정밀 폴리싱 (2.5h)
│  ├─ B1. 환영 헤더 (부서/직급/마지막 로그인) (0.5h)
│  ├─ B2. 메트릭 카드를 Mock store 연결 + 애니메이션 (0.5h)
│  ├─ B3. 6 모듈 카드 RBAC + 부서 필터링 + 호버 (0.5h)
│  ├─ B4. 빠른 액션 3종 (최근 문서·알람·오늘의 SOP) (0.5h)
│  └─ B5. 시스템 정보 카드 (LLM 패밀리·ML 모델·데이터 규모) (0.5h)
│
├─ C. 더미 데이터 시드 + Mock API (2.0h)
│  ├─ C1. Mock 모드 환경변수 + 라우팅 (0.25h)
│  ├─ C2. 사원 24명 + 6 본부 + 19 팀 데이터 (0.5h)
│  ├─ C3. 33 테스트 계정 (auth) + RBAC 매트릭스 (0.5h)
│  ├─ C4. 메트릭 + INGESTION + 보안 로그 시드 (0.25h)
│  ├─ C5. 시나리오 / 알람 / 메시지 시드 (0.5h)
│
└─ D. 공통 보강 (0.5h)
   ├─ D1. Button / Badge 컴포넌트 추출 (0.25h)
   └─ D2. 우측 패널 transition + 모바일 폴리싱 (0.25h)
```

---

## 4. A. Login 정밀 폴리싱 (3시간)

### A-1. 비밀번호 정책 6조건 실시간 검증 강화 (0.5h)

**현재 상태**: `passwordRules` 배열 + 정규식, `passwordValue.length > 0` 시점부터 노출

**목표**:
- 6 조건이 **2열 그리드**로 정렬되어 ●/○ 글리프 + 텍스트
- 점등 색상: 만족=`var(--hud-green)`, 미달=`var(--hud-text-muted)`
- 강도 점수 (0~100점) 진행 바 — 골드 색상
- 비밀번호 변경 모드에서만 노출 (로그인 모드는 숨김 옵션)

**파일**:
- [src/routes/login.tsx](../../frontend/src/routes/login.tsx) 수정
- [src/lib/passwordPolicy.ts](../../frontend/src/lib/passwordPolicy.ts) 신규 (정책 함수 분리)

**`passwordPolicy.ts` 시그니처**:
```ts
export interface PolicyRule {
  key: 'min_length' | 'uppercase' | 'lowercase' | 'number' | 'special' | 'no_repeat';
  test: (s: string) => boolean;
}
export function evaluatePolicy(password: string): {
  passed: PolicyRule['key'][];
  score: number; // 0-100
};
```

**검증**: 빈 비번 → 0점 / 8자+소문자 → 33점 / 8자+모든 조건 → 100점

---

### A-2. 잠금/실패/오류 케이스 UX (0.75h)

**현재 상태**: 단순 빨간 박스에 에러 메시지만

**목표**:

| 백엔드 응답 | 프론트 처리 |
|---|---|
| `401 비밀번호 X (3/5)` | `잘못된 사번 또는 비밀번호입니다. 남은 시도: 2회` 친절한 톤 |
| `401 비밀번호 X (5/5)` | `5회 연속 실패. 30분 후 다시 시도하세요.` + 30분 카운트다운 |
| `423 잠김` | `계정이 잠금 상태입니다. HH:MM:SS 후 다시 시도하세요.` + 카운트다운 |
| `403 비활성` | `비활성화된 계정입니다. 관리자에게 문의하세요.` + IT 연락처 안내 |
| `Network` | `서버 연결 실패. 네트워크를 확인해 주세요.` + 재시도 버튼 |
| `200 OK + must_change_pw=true` | 비밀번호 변경 모달 자동 노출 (A-3) |

**파일**:
- [src/routes/login.tsx](../../frontend/src/routes/login.tsx) 에러 분기 추가
- [src/components/ui/ErrorAlert.tsx](../../frontend/src/components/ui/ErrorAlert.tsx) 신규
- [src/hooks/useCountdown.ts](../../frontend/src/hooks/useCountdown.ts) 신규 (잠금 타이머)

**i18n 추가 키** (`ko/common.json`, `en/common.json`):
```json
{
  "login": {
    "error": {
      "invalid_credentials": "잘못된 사번 또는 비밀번호입니다. 남은 시도: {{remaining}}회",
      "locked": "계정이 {{minutes}}분 잠금 상태입니다.",
      "lock_countdown": "잠금 해제까지 {{time}}",
      "inactive": "비활성화된 계정입니다. 관리자에게 문의하세요.",
      "network": "서버 연결 실패. 네트워크를 확인해 주세요.",
      "retry": "다시 시도",
      "max_attempts": "5회 연속 실패. 30분 후 다시 시도하세요."
    }
  }
}
```

---

### A-3. 비밀번호 변경 모달 (must_change_pw) (0.75h)

**현재 상태**: 라우트 없음, 백엔드 응답에 `must_change_pw` 처리 미구현

**목표**:
- 로그인 응답에 `must_change_pw=true` 시 모달 강제 노출 (닫기 X 버튼 없음)
- 현재 비밀번호 + 새 비밀번호 + 새 비밀번호 확인 3 필드
- 새 비밀번호 6 조건 실시간 점등 (A-1 재사용)
- 두 새 비밀번호 일치 검증
- 백엔드 `/api/auth/change-password` 호출
- 성공 시 → Dashboard로 이동 (정상 로그인 흐름)

**파일**:
- [src/components/auth/ChangePasswordModal.tsx](../../frontend/src/components/auth/ChangePasswordModal.tsx) 신규
- [src/api/auth.ts](../../frontend/src/api/auth.ts) 신규 (auth API 분리)

**모달 구조**:
```tsx
<Modal isOpen={mustChangePw} closeOnEsc={false} closeOnOverlay={false}>
  <h2>비밀번호 변경 필요</h2>
  <p>최초 로그인이거나 비밀번호 만료. 정책에 맞는 새 비밀번호 설정</p>
  <Field label="현재 비밀번호" type="password" />
  <Field label="새 비밀번호" type="password" />
  <PolicyChecklist value={newPw} />
  <Field label="새 비밀번호 확인" type="password" error={mismatch} />
  <Button primary disabled={!allValid}>변경 후 로그인</Button>
</Modal>
```

---

### A-4. 데모 빠른 로그인 칩 (4 RBAC) (0.5h)

**조건**: `import.meta.env.DEV === true` 또는 `VITE_USE_MOCK === 'true'` 일 때만 노출

**4 RBAC 칩**:
| 사번 | 이름 | 역할 | RBAC L |
|---|---|---|:--:|
| `SYS-0001` | 박준영 | SYS_ADMIN | 6 |
| `HR-0001` | 이영희 | HR_ADMIN | 5 |
| `QA-0001` | 김민수 | TEAM_LEAD | 4 |
| `PE-0019` | 최유진 | EMPLOYEE | 2 |

**UI**: Login 카드 하단에 4 작은 칩 — 클릭 시 사번/비번 자동 채움 + 자동 로그인 시도.

**파일**:
- [src/routes/login.tsx](../../frontend/src/routes/login.tsx) 데모 칩 영역 추가
- [src/lib/demoAccounts.ts](../../frontend/src/lib/demoAccounts.ts) 신규 (4 계정 정의)

---

### A-5. 키보드/접근성 + originalRoute 복원 (0.5h)

**작업**:
1. `<input autoFocus />` — 사원번호 필드에
2. Enter 키 → form submit 자동
3. 캡스락 경고 (browser-native CapsLock 이벤트)
4. ARIA 라벨: `aria-label`, `aria-invalid`, `aria-describedby="password-policy"`
5. `originalRoute` 복원: 인증 만료로 `/login` 이동 시 → 로그인 후 원래 페이지로

**구현**:
```tsx
// _shell.tsx 또는 RequireAuth
const location = useLocation();
if (!isAuth) {
  return <Navigate to="/login" state={{ from: location }} replace />;
}

// login.tsx 내부
const from = (location.state as { from?: Location })?.from?.pathname ?? '/';
navigate(from);
```

---

## 5. B. Dashboard 정밀 폴리싱 (2.5시간)

### B-1. 환영 헤더 (부서/직급/마지막 로그인) (0.5h)

**현재**: `대시보드 v3.5` 만 표시

**목표**:
```
┌─────────────────────────────────────────────────────┐
│ 안녕하세요, 김민수 차장님                v3.5       │
│ 품질본부 / 품질보증팀 · 본사(대구)                  │
│ 마지막 로그인: 2026-04-26 18:32 (서울)              │
└─────────────────────────────────────────────────────┘
```

**i18n**:
```json
"dashboard": {
  "greeting": "안녕하세요, {{name}}{{position}}님",
  "context": "{{division}} / {{department}} · {{plant}}",
  "last_login": "마지막 로그인: {{at}}"
}
```

**시간 포맷**: `date-fns` `formatDistanceToNow(at, { locale: ko })` → `n분 전 / 1시간 전 / 어제`

---

### B-2. 메트릭 카드를 Mock store 연결 + 애니메이션 (0.5h)

**현재**: 4 메트릭 모두 하드코딩

**목표**:
- `useMetricsStore` (Zustand) — 메트릭 4종을 store로 분리
- Mock 모드: `seed/metrics.ts`에서 초기값 로드
- Real 모드: `GET /api/dashboard/metrics` 호출
- **카운트업 애니메이션**: 0 → 329 (1.2초 ease-out, requestAnimationFrame)

**파일**:
- [src/store/metrics.ts](../../frontend/src/store/metrics.ts) 신규
- [src/hooks/useCountUp.ts](../../frontend/src/hooks/useCountUp.ts) 신규
- [src/components/ui/MetricCard.tsx](../../frontend/src/components/ui/MetricCard.tsx) 신규 (재사용 컴포넌트)

---

### B-3. 6 모듈 카드 RBAC + 부서 필터링 + 호버 (0.5h)

**현재**: 6 모듈 모두 표시 + 단순 호버

**목표**:
| RBAC L | 표시 모듈 |
|:--:|---|
| 1 (EMPLOYEE) | A · B · C |
| 2 | A · B · C · D (관련 부서일 때) |
| 3 (TEAM_LEAD) | + E |
| 4+ | 전체 |

**부서 필터** (D 모듈은 7개 부서, F 모듈은 14개 부서로 제한):
- `isMenuVisible(slug, dept, role)` 로직 → `src/lib/rbac.ts` 헬퍼
- 비가시 모듈은 카드에서 숨김 (또는 `dim` + 자물쇠 아이콘)

**호버 효과**: `transform: scale(1.02)` 300ms + 골드 그림자 (다크 모드만)

---

### B-4. 빠른 액션 3종 (최근 문서·알람·오늘의 SOP) (0.5h)

**Dashboard 하단에 3-카드 행**:

```
┌─ 최근 작성 문서 ─┐ ┌─ 진행 중 알람 ─┐ ┌─ 오늘의 SOP ─┐
│ ● 8D-2026-042   │ │ ⚠ SPC OBC 위반 │ │ ▣ 프레스 트라이│
│   초안 (어제)   │ │   Cpk 1.18      │ │  Step 3 of 7  │
│ ● ECN-2026-018  │ │ ⚠ JST 누유     │ │ [이어하기 ▶] │
│ [전체 보기 →]   │ │ [모니터 →]     │ └─────────────┘
└─────────────────┘ └────────────────┘
```

**Mock 데이터**:
- `seed/recentDrafts.ts` (5건)
- `seed/alarms.ts` (3건)
- `seed/sopProgress.ts` (사용자별 진행률)

---

### B-5. 시스템 정보 카드 (LLM·ML·데이터) (0.5h)

**Dashboard 마지막 행** (full-width 카드):

```
┌─ 시스템 정보 ──────────────────────────────────────────┐
│ LLM 엔진:  Gemini 1.5 Pro · Qwen 3.5 · EXAONE · Gemma 4│
│ 비전 모델: Gemini Vision · Gemma 4                     │
│ ML/DL:    Intent · Error TF-IDF · SPC IF · Mold XGB    │
│            Markov · DocQual · RegRisk (총 7종)          │
│ 데이터:   사원 329 · 에러 201 · 금형 25 · SPC 5공정    │
│            용어집 297 · Few-shot 584                    │
│ RBAC:     6단계 + 28개 세부 권한 + 부서 30개            │
└────────────────────────────────────────────────────────┘
```

**소스**: `seed/systemInfo.ts` (단일 객체)

---

## 6. C. 더미 데이터 시드 + Mock API (2시간)

### C-1. Mock 모드 환경변수 + 라우팅 (0.25h)

**환경변수**:
```bash
# frontend/.env.development
VITE_USE_MOCK=true
VITE_API_URL=http://localhost:8000
```

**API 클라이언트 분기** ([src/api/client.ts](../../frontend/src/api/client.ts)):
```ts
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
export const api = USE_MOCK ? createMockClient() : createRealClient();
```

**Mock 클라이언트 옵션**:

| 옵션 | 장단점 |
|:--:|---|
| **A) MSW (Mock Service Worker)** | ✅ 진짜 fetch 인터셉트, axios 코드 변경 없음 / ❌ 추가 dep, service worker 등록 |
| **B) axios mock-adapter** | ✅ 가벼움 / ❌ 응답 바이너리·SSE 지원 약함 |
| **C) 자체 mock 함수** | ✅ 통제 가능 / ❌ 직접 작성 |

**권장**: **C 자체 mock** — 본선 데모 제한 시간 내에 통제 가능, SSE는 별도 mock 처리.

**파일**:
- [src/api/mock/index.ts](../../frontend/src/api/mock/index.ts) 신규 (axios 래퍼)
- [src/api/mock/handlers.ts](../../frontend/src/api/mock/handlers.ts) 신규 (URL → 응답 매핑)

---

### C-2. 사원 24명 + 6 본부 + 19 팀 데이터 (0.5h)

**소스**: [uiux/AJIN AI Assistant Design System/ui_kits/web_app/Search.jsx](../../uiux/AJIN AI Assistant Design System/ui_kits/web_app/Search.jsx) 의 `peopleAll` 24명 그대로 활용

**파일**: [src/api/mock/seed/employees.ts](../../frontend/src/api/mock/seed/employees.ts) 신규

```ts
export interface MockEmployee {
  id: string;       // 사번 (QA-0001)
  name: string;
  gender: '남' | '여';
  hq: string;       // 본부
  team: string;     // 팀
  position: string;
  ext: string;
  mobile: string;
  email: string;
  plant: string;
}

export const ORG: { hq: string; n: number; teams: { team: string; n: number }[] }[] = [...];
export const EMPLOYEES: MockEmployee[] = [...]; // 24명
```

**확장**: 자동 생성 함수로 24 → 329명 확장 (선택, 시간 여유 시)
```ts
export function generateExtendedEmployees(count = 329): MockEmployee[] { /* ... */ }
```

---

### C-3. 33 테스트 계정 + RBAC 매트릭스 (0.5h)

**파일**: [src/api/mock/seed/accounts.ts](../../frontend/src/api/mock/seed/accounts.ts) 신규

```ts
export interface MockAccount {
  employee_id: string;
  username: string;
  password: string;     // 평문 (mock 전용; 실제는 bcrypt 해시)
  role_name: 'SYS_ADMIN' | 'HR_ADMIN' | 'TEAM_LEAD' | 'MANAGER' | 'EMPLOYEE' | 'INACTIVE';
  role_level: 6 | 5 | 4 | 3 | 2 | 1;
  department: string;
  position: string;
  plant: string;
  must_change_pw: boolean;
  failed_attempts: number;
  locked_until: string | null;
  last_login: string | null;
}

export const ACCOUNTS: MockAccount[] = [
  // 시스템 관리자 2
  { employee_id: 'SYS-0001', username: '박준영', password: 'Demo!2026', role_name: 'SYS_ADMIN', role_level: 6, ... },
  // 인사 3
  { employee_id: 'HR-0001', username: '이영희', password: 'Demo!2026', role_name: 'HR_ADMIN', role_level: 5, ... },
  // 품질 6
  // 생산기술 5
  // 영업 4
  // 환경안전 3
  // 법무 2
  // 기타 8
];

export const RBAC_MATRIX: Record<string, number> = {
  // 메뉴별 최소 RBAC 레벨
  'A. 인원 검색': 1,
  'B. 문서 검색/작성': 1,
  'C. AI 업무 도우미': 1,
  'D. 법규 모니터링': 2,
  'E. 인사 관리': 3,
  'F. 설비/공정 AI': 1,
};

export const PERMISSIONS_28: Record<string, number> = {
  // 28개 세부 권한
  'employee.view_all': 4,
  'employee.view_dept': 1,
  // ...
};
```

---

### C-4. 메트릭 + INGESTION + 보안 로그 시드 (0.25h)

**파일**: [src/api/mock/seed/system.ts](../../frontend/src/api/mock/seed/system.ts) 신규

```ts
export const METRICS = {
  employees: 329,
  errorCodes: 201,
  departments: 29,
  testAccounts: 33,
};

export const INGESTION = [
  { label: 'errors', current: 201, total: 201 },
  { label: 'molds', current: 25, total: 25 },
  { label: 'spc', current: 5, total: 5 },
  { label: 'drawings', current: 15, total: 15 },
  { label: 'inspections', current: 9, total: 9 },
];

export const SYSTEM_HEALTH = {
  gpu: 42,
  latencyMs: 124,
  qps: 8400,
  llmEngines: ['Gemini 1.5 Pro', 'Qwen 3.5', 'EXAONE 3.5', 'Gemma 4'],
  visionModels: ['Gemini Vision', 'Gemma 4'],
  mlModels: ['Intent', 'Error TF-IDF', 'SPC IF', 'Mold XGB', 'Markov', 'DocQual', 'RegRisk'],
};

export const SECURITY_LOG = [
  '[AUTH] JWT_VALIDATED',
  '[RBAC] ACCESS_GRANTED_L4',
  '[SYNC] CHROMADB_UP',
  '[LLM] ENGINE_ONLINE',
  '[BACKEND] CLOUDFLARE_TUNNEL_OK',
];
```

---

### C-5. 시나리오 / 알람 / 메시지 시드 (0.5h)

**3 파일 분리**:

[src/api/mock/seed/alarms.ts](../../frontend/src/api/mock/seed/alarms.ts) — 진행 중 알람 3종:
```ts
export const ALARMS = [
  { id: 'A-001', severity: 'HIGH', title: 'SPC OBC 위반', detail: 'Cpk 1.18 (Nelson Rule 2)', module: 'F', timestamp: '2026-04-27T08:30:00+09:00' },
  { id: 'A-002', severity: 'MEDIUM', title: 'JST 누유', detail: '10번 프레스 라인', module: 'F', timestamp: '2026-04-27T07:15:00+09:00' },
  { id: 'A-003', severity: 'CRITICAL', title: '산안법 시행 D-30', detail: '안전거리 300→400mm', module: 'D', timestamp: '2026-04-27T06:00:00+09:00' },
];
```

[src/api/mock/seed/recentDrafts.ts](../../frontend/src/api/mock/seed/recentDrafts.ts) — 최근 작성 5건:
```ts
export const RECENT_DRAFTS = [
  { id: '8D-2026-042', type: '8D Report', title: '8D-2026-042 초안', status: 'draft', updatedAt: '2026-04-26T22:30:00+09:00' },
  { id: 'ECN-2026-018', type: 'ECN', title: '범퍼빔 두께 변경', status: 'draft', updatedAt: '2026-04-26T18:15:00+09:00' },
  // ... 3 more
];
```

[src/api/mock/seed/scenarios.ts](../../frontend/src/api/mock/seed/scenarios.ts) — 법규 시나리오 3종:
```ts
export const SCENARIOS = [
  { id: 'KOR-OSHA-2026', score: 85, severity: 'CRITICAL', dDay: 30, title: '산안법 안전거리', summary: '300mm → 400mm', impactedSites: ['본사', '천안1', '천안2'] },
  { id: 'US-TARIFF-25', score: 78, severity: 'HIGH', dDay: 90, title: '트럼프 25% 관세', summary: 'JOON INC 공급분 +400억', impactedSites: ['JOON INC (USA)'] },
  { id: 'EU-REACH-SVHC', score: 52, severity: 'MEDIUM', dDay: 180, title: 'REACH 신규 SVHC', summary: '부품 재인증', impactedSites: ['AJIN POLAND'] },
];
```

[src/api/mock/seed/sopProgress.ts](../../frontend/src/api/mock/seed/sopProgress.ts) — SOP 진행 (사용자별):
```ts
export const SOP_PROGRESS: Record<string, { sopId: string; step: number; total: number }> = {
  'PE-0019': { sopId: 'press-tryout', step: 3, total: 7 },
  // ...
};
```

---

### C-6. Mock Handlers (0h, C-1에 통합)

**파일**: [src/api/mock/handlers.ts](../../frontend/src/api/mock/handlers.ts)

```ts
// URL → 응답 매핑
export const handlers = {
  'POST /auth/login': (body: { employee_id: string; password: string }) => {
    const account = ACCOUNTS.find(a => a.employee_id === body.employee_id);
    if (!account || account.password !== body.password) {
      throw { status: 401, detail: '잘못된 사번 또는 비밀번호입니다.' };
    }
    return {
      access_token: 'mock.jwt.' + account.employee_id,
      refresh_token: 'mock.refresh.' + account.employee_id,
      ...account,
    };
  },
  'GET /dashboard/metrics': () => METRICS,
  'GET /dashboard/ingestion': () => INGESTION,
  'GET /dashboard/system-health': () => SYSTEM_HEALTH,
  'GET /dashboard/recent-drafts': () => RECENT_DRAFTS,
  'GET /dashboard/alarms': () => ALARMS,
  'GET /employees': () => EMPLOYEES,
  'POST /employees/search': (body: { query: string }) => searchEmployees(body.query),
  // ...
};
```

---

## 7. 공통 보강 작업 (0.5시간)

### D-1. Button / Badge 컴포넌트 추출 (0.25h)

**현재**: `<button className="btn primary full">` 패턴이 여러 곳

**목표**:
[src/components/ui/Button.tsx](../../frontend/src/components/ui/Button.tsx) 신규
```tsx
type Variant = 'primary' | 'secondary' | 'tertiary' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'lg';

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  fullWidth?: boolean;
  loading?: boolean;
  icon?: React.ReactNode;
}

export const Button: React.FC<Props> = ({ variant = 'secondary', size = 'md', fullWidth, loading, icon, children, ...rest }) => {
  // ...
};
```

[src/components/ui/Badge.tsx](../../frontend/src/components/ui/Badge.tsx) 신규
```tsx
type Status = 'ok' | 'warn' | 'fail' | 'info' | 'off' | 'on';
export const Badge: React.FC<{ status: Status; children: React.ReactNode }> = ({ status, children }) => (
  <span className={`hud-badge-${status}`}>{children}</span>
);
```

> **이유**: Day 3에서 어차피 만들어야 함 → 미리 추출하면 Login·Dashboard에서 즉시 활용

---

### D-2. 우측 패널 transition + 모바일 폴리싱 (0.25h)

**현재**: 우측 패널 토글 시 grid-template-columns 점프

**목표**: `theme.css` 보강
```css
.app-body {
  transition: grid-template-columns 200ms ease-out;
}
.right-panel {
  transition: opacity 200ms ease-out, transform 200ms ease-out;
}
.right-panel.entering { opacity: 0; transform: translateX(20px); }
```

**모바일**:
- 햄버거 버튼 (TopBar 좌측, 768px 미만에서만 노출)
- 사이드바를 오버레이로 변환 (`position: fixed; left: 0; height: 100vh`)
- 사이드바 외부 클릭 시 닫힘

---

## 8. Day 2 시간 배분표

| 시간 | 작업 | 핵심 산출물 |
|:--:|---|---|
| 09:00 ~ 09:15 | C-1. Mock 환경변수 + 라우팅 | `.env.development`, `mock/index.ts` 골격 |
| 09:15 ~ 10:00 | C-2. 사원 24명 + 조직도 시드 | `seed/employees.ts` |
| 10:00 ~ 10:30 | C-3. 33 계정 + RBAC | `seed/accounts.ts`, `seed/permissions.ts` |
| 10:30 ~ 10:45 | 휴식 | — |
| 10:45 ~ 11:00 | C-4. 메트릭/INGESTION/보안 로그 | `seed/system.ts` |
| 11:00 ~ 11:30 | C-5. 시나리오/알람/SOP/문서 | `seed/{alarms,recentDrafts,scenarios,sopProgress}.ts` |
| 11:30 ~ 12:00 | A-1. 비밀번호 정책 분리 + 강도 점수 | `lib/passwordPolicy.ts` |
| 12:00 ~ 13:00 | 점심 | — |
| 13:00 ~ 13:45 | A-2. 잠금/실패/오류 케이스 + i18n | `useCountdown.ts`, login.tsx 보강 |
| 13:45 ~ 14:30 | A-3. 비밀번호 변경 모달 | `ChangePasswordModal.tsx`, `api/auth.ts` |
| 14:30 ~ 15:00 | A-4. 데모 빠른 로그인 칩 | `lib/demoAccounts.ts` |
| 15:00 ~ 15:30 | A-5. 키보드/접근성 + originalRoute | login.tsx + `_shell.tsx` |
| 15:30 ~ 15:45 | 휴식 | — |
| 15:45 ~ 16:15 | B-1. 환영 헤더 | dashboard.tsx 보강 |
| 16:15 ~ 16:45 | B-2. 메트릭 카운트업 + Mock 연결 | `store/metrics.ts`, `useCountUp.ts`, `MetricCard.tsx` |
| 16:45 ~ 17:15 | B-3. 모듈 카드 RBAC 필터 | `lib/rbac.ts` |
| 17:15 ~ 17:45 | B-4. 빠른 액션 3카드 | dashboard.tsx 하단 추가 |
| 17:45 ~ 18:15 | B-5. 시스템 정보 카드 | dashboard.tsx 하단 |
| 18:15 ~ 18:30 | D-1. Button/Badge 추출 | `components/ui/{Button,Badge}.tsx` |
| 18:30 ~ 18:45 | D-2. transition + 모바일 햄버거 | `theme.css` 보강 |
| 18:45 ~ 19:00 | 마감 검증 + Day 2 회고 메모 | 체크리스트 9 항목 모두 ✓ |

**총 작업 시간**: 8시간 (점심·휴식 포함 10시간)

---

## 9. 검증 체크리스트

Day 2 마감 시 다음 9개 시나리오를 직접 시연해 모두 ✓ 처리되어야 합니다.

| # | 시나리오 | 기대 결과 |
|:--:|---|---|
| 1 | `/login` 접속 → 빠른 로그인 칩 4개 노출 (DEV 모드) | ✓ 칩 클릭 시 자동 채움 + 자동 로그인 |
| 2 | `QA-0001` / `Demo!2026` 로그인 | ✓ Dashboard로 이동 |
| 3 | 잘못된 비번 5회 입력 | ✓ "30분 후 다시 시도" + 카운트다운 |
| 4 | `must_change_pw=true` 계정으로 로그인 | ✓ 비밀번호 변경 모달 자동 노출 |
| 5 | 새 비번 6 조건 모두 만족 → 변경 | ✓ Dashboard로 이동 |
| 6 | Dashboard 환영 헤더 노출 | ✓ 이름·부서·마지막 로그인 |
| 7 | RBAC L1 계정으로 로그인 | ✓ E (인사) 모듈 카드 숨김 또는 잠금 |
| 8 | 메트릭 카드 카운트업 애니메이션 | ✓ 0 → 329 부드럽게 (1.2초) |
| 9 | 한·영 토글 시 모든 텍스트 갱신 | ✓ 끊김 없이 즉시 반영 |
| 10 | 라이트/다크/AUTO 테마 토글 | ✓ 로고 즉시 전환 + 글래스 갱신 |
| 11 | 우측 패널 토글 시 부드러운 transition | ✓ 200ms ease-out |
| 12 | 모바일 768px → 햄버거 사이드바 | ✓ 오버레이 + 외부 클릭 닫힘 |

---

## 10. 위험 요소 + 완화

| # | 위험 | 영향 | 완화 |
|:--:|---|:--:|---|
| 1 | Mock 모드와 Real 모드 분기가 axios 인터셉터와 충돌 | 🔴 | 분기를 클라이언트 생성 단계로 끌어올림 (코드 경로 분리) |
| 2 | 비밀번호 변경 모달이 Esc로 닫힘 (보안 우회) | 🟡 | `closeOnEsc={false}` + `closeOnOverlay={false}` 강제 |
| 3 | Mock JWT가 실제 JWT 형식 다름 → 디코드 시 에러 | 🟡 | Mock JWT를 `mock.jwt.{employee_id}` 단순 문자열로, 디코드 시 prefix 체크 |
| 4 | originalRoute 무한 루프 (`/login` → `/login`) | 🟢 | `from` 가 `/login` 일 때 `/` 로 fallback |
| 5 | 33 계정 평문 비번이 git에 커밋됨 | 🟡 | `.gitignore` 에 `seed/accounts.ts` 추가 또는 `.env.development.local` 분리 |
| 6 | 카운트업 애니메이션이 페이지 진입마다 재생 | 🟢 | `useEffect([])` 1회만, persisted store 값은 초기값으로 |
| 7 | i18n 누락 키 → 한·영 토글 시 영문 키 노출 | 🟡 | `i18next.options.fallbackLng = 'ko'` + 누락 키 콘솔 경고 |
| 8 | 모바일 햄버거가 사이드바 컴포넌트 내부에서 토글 → 닫혀 있을 때 노출 안 됨 | 🟡 | TopBar에 햄버거 버튼 + Zustand로 상태 분리 |
| 9 | Mock 데이터가 실제 백엔드 스키마와 불일치 → Day 13 통합 시 폭증 작업 | 🔴 | TypeScript 인터페이스를 백엔드 Pydantic과 매칭 (수동 동기화) |

---

## 11. Day 2 산출물 (Day 3 시작 전 준비물)

### 신규 파일 (예상 23개)

```
frontend/
├── .env.development                              ⭐ Mock 환경변수
├── src/
│   ├── api/
│   │   ├── auth.ts                               ⭐ login/refresh/changePassword
│   │   └── mock/
│   │       ├── index.ts                          ⭐ Mock 클라이언트
│   │       ├── handlers.ts                       ⭐ URL → 핸들러 맵
│   │       └── seed/
│   │           ├── employees.ts                  ⭐ 24명 사원
│   │           ├── accounts.ts                   ⭐ 33 계정
│   │           ├── permissions.ts                ⭐ RBAC 매트릭스
│   │           ├── system.ts                     ⭐ 메트릭/INGESTION/보안
│   │           ├── alarms.ts                     ⭐ 알람 3종
│   │           ├── recentDrafts.ts               ⭐ 최근 문서 5
│   │           ├── scenarios.ts                  ⭐ 법규 3
│   │           └── sopProgress.ts                ⭐ SOP 진행
│   ├── components/
│   │   ├── auth/
│   │   │   └── ChangePasswordModal.tsx           ⭐ 비번 변경 모달
│   │   └── ui/
│   │       ├── Button.tsx                        ⭐ 재사용 버튼
│   │       ├── Badge.tsx                         ⭐ 상태 배지
│   │       ├── ErrorAlert.tsx                    ⭐ 에러 표시
│   │       └── MetricCard.tsx                    ⭐ 메트릭 카드
│   ├── hooks/
│   │   ├── useCountdown.ts                       ⭐ 잠금 타이머
│   │   └── useCountUp.ts                         ⭐ 메트릭 애니메이션
│   ├── lib/
│   │   ├── passwordPolicy.ts                     ⭐ 6 조건 + 강도 점수
│   │   ├── demoAccounts.ts                       ⭐ DEV 빠른 로그인 4종
│   │   └── rbac.ts                               ⭐ isMenuVisible 헬퍼
│   ├── store/
│   │   └── metrics.ts                            ⭐ 메트릭 store
│   └── types/
│       └── api.ts                                ⭐ Pydantic 미러 타입
```

### 갱신 파일

```
frontend/
├── src/
│   ├── App.tsx                                  (originalRoute 복원)
│   ├── api/client.ts                            (Mock 분기)
│   ├── routes/login.tsx                         (정밀 폴리싱 전체)
│   ├── routes/dashboard.tsx                     (5 섹션 추가)
│   ├── components/shell/TopBar.tsx              (햄버거 버튼)
│   ├── components/shell/LeftSidebar.tsx         (모바일 오버레이)
│   ├── i18n/ko/common.json                      (login.error.* 추가)
│   ├── i18n/en/common.json                      (동일)
│   ├── styles/theme.css                         (transition 추가)
│   └── store/ui.ts                              (mobileNavOpen 상태)
```

---

## 12. Day 2 종료 기준

다음 모두 충족 시 Day 3로 넘어갑니다:

- [ ] TypeScript strict 컴파일 0 오류
- [ ] dev 서버 부팅 시간 < 3초
- [ ] 검증 체크리스트 12개 시나리오 모두 ✓
- [ ] `VITE_USE_MOCK=true` 로 백엔드 없이 4 RBAC 빠른 로그인 + Dashboard 진입 가능
- [ ] 한·영 토글 시 모든 텍스트 갱신, 잘못된 키 노출 없음
- [ ] 라이트/다크/AUTO 테마 전환 시 로고·글래스·폰트 즉시 전환
- [ ] 모바일 768px에서 햄버거 사이드바 정상 동작
- [ ] Day 2 산출물 23개 파일 모두 커밋 가능 상태

---

## 13. Day 3 (공통 컴포넌트 라이브러리) 시작 시 의존하는 항목

Day 2에서 만든 다음 항목이 Day 3 작업의 기반이 됩니다:
- ✅ Button / Badge / MetricCard / ErrorAlert (Day 3에서 Card / Tabs / Tooltip / Modal / Stepper 등 추가)
- ✅ Mock API 인프라 (Day 3에서 Plotly 차트가 Mock 시계열 데이터 소비)
- ✅ Seed 데이터 (Day 3 PlotlyChart 컴포넌트가 SPC/관세 mock 데이터 소비)
- ✅ i18n 보강된 키 (Day 3에서 차트 라벨도 다국어)

---

## 변경 이력

| 버전 | 날짜 | 변경 |
|---|---|---|
| **1.0** | 2026-04-27 | 초안 — Day 2 (Login/Dashboard 폴리싱 + Mock API) 13 섹션 8h 분배 |

---

**관련 문서**:
- [REACT_MIGRATION_PLAN.md](REACT_MIGRATION_PLAN.md) — 전체 14일 로드맵
- [WEB_DESIGN_SPECIFICATION.md](WEB_DESIGN_SPECIFICATION.md) — 디자인 시스템 사양
- [FEATURE_SPECIFICATION.md](../features/FEATURE_SPECIFICATION.md) — 6대 기능 상세
