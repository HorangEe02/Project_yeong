# 기능 E — 인사·관리자 패널 (Admin · HR · Security)

> **이 문서는 누구를 위한 것인가요?**
> 개발자가 아닌 분 (HR·IT·임원·총무인사팀) 도 끝까지 읽을 수 있도록 작성했습니다.
> 어려운 용어는 처음 등장할 때 _기울임_ 으로 표시하고 옆에 짧은 설명을 붙입니다.

---

## 1. 한 줄 요약

**"사내 사용자·접근권한·로그인 이력·시스템 헬스를 한 화면에서 통제하는 관리자 콘솔"입니다.**

650명 사용자의 계정 캐시/권한 위임/잠금/은퇴를 처리하고, 로그인 시도·실패 패턴을 감지해 보안 알림을 띄우며, IdP 그룹 매핑과 감사·시스템 헬스를 관리합니다. 운영 인증은 **사내 IdP 우선**이며, 로컬 비밀번호 로그인은 2FA가 켜진 break-glass `SYS_ADMIN(L5)`에만 제한됩니다. 관리자 콘솔은 **3 탭 구조 + RBAC** (role_level 4-5) 로 운영합니다.

---

## 2. 누가, 언제 쓰는가?

| 사용자 | 시나리오 | 기능 E 가 해주는 일 |
|---|---|---|
| **HR_ADMIN (총무인사팀)** | 신입사원 계정 위임 | `/admin/users` 폼 → 부서·직급·역할 선택 → 사번 자동 생성. 운영에서는 임시 비밀번호를 응답하지 않고 사내 IdP 초대/초기화 절차 사용 |
| **HR_ADMIN** | 퇴사자 처리 | `/admin/users/{id}/retire` — 소프트 은퇴 (DB 보존). hard delete 는 기본 차단 |
| **IT_ADMIN** | 의심 로그인 감지 | `/admin/security/alerts` — 비정상 IP·시간대·실패 횟수 자동 감지 |
| **임원 (level=4)** | 분기 인사 통계 | `/admin/hr/headcount`, `/hr/tenure`, `/hr/matrix` 한 화면 |
| **SYS_ADMIN (level=5)** | 시스템 백업·헬스 | `/admin/system/backup`, `/admin/system/health` |
| **사용자 본인** | 비밀번호 변경 | `/auth/change-password` |
| **컴플라이언스 담당자** | 감사 이력 추적 | `/admin/system/audit-log` — 누가 언제 어느 endpoint 호출했는지 |

---

## 3. 전체 작동 흐름 (그림으로)

새로운 사용자가 시스템에 진입하는 전체 라이프사이클:

```
[HR_ADMIN — 계정 생성]
  POST /admin/employee-id/preview      ← 사번 자동 생성 (예: EMP-A0123)
  POST /admin/users                    ← IdP 초대/초기화 또는 dev 전용 임시 PW
                  │
                  ▼
[신규 사용자 — 첫 로그인]
  POST /auth/login                     ← 운영 일반 사용자는 IdP, break-glass 만 로컬 2FA
       │
       │ password_hash 검증
       │ failed_attempts 누적
       │ locked_until 자동 설정 (5회 실패 시)
       ▼
  must_change_pw=1 → /auth/change-password 강제
                  │
                  ▼
  HttpOnly cookie 세션 발급 + login_history INSERT
                  │
                  ▼
[사용자 — 일상 사용]
  매 요청마다 auth_middleware 가 검증 +
  api_audit_log INSERT (감사 로깅)
                  │
                  ▼
[IT_ADMIN — 보안 모니터링]
  GET /admin/security/login-stats     ← 일별 로그인 / 실패율
  GET /admin/security/alerts          ← 비정상 패턴 (IP/시간/실패)
                  │
                  ▼
[퇴사 시]
  DELETE /admin/users/{id}/retire     ← is_active=0 (소프트)
  또는
  DELETE /admin/users/{id}            ← 기본 차단, AUTH_ALLOW_HARD_DELETE=true + 사유 + L5 예외
```

핵심: **계정 생성 → 강제 PW 변경 → cookie 기반 세션 + 감사 로깅 → 비정상 감지 → 은퇴**.

---

## 4. 기술 스택

### 4-1. 백엔드 (Backend)

| 카테고리 | 기술 | 역할 |
|---|---|---|
| 언어 | **Python 3.11+** | 서버 |
| 웹 프레임워크 | **FastAPI** | `/api/admin/*`, `/api/auth/*` 라우터 |
| 데이터베이스 | **SQLite** | `auth.db` (사용자) + `audit.db` (감사) |
| 인증 | **HttpOnly cookie + JWT** _(브라우저에는 토큰 값을 노출하지 않는 세션)_ | `core/auth/cookies.py`, `core/auth/jwt_handler.py` |
| 비밀번호 해시 | **bcrypt** | 단방향 암호화 (역추적 불가) |
| RBAC | **role_level (1-5)** | 사원=1 / 매니저=3 / 임원=4 / SYS_ADMIN=5 |
| 외부 IdP | **OIDC / SAML / LDAP** | `/api/auth/idp/*` 로그인·callback·direct-bind |
| 분석 | **Python collections + datetime** | DAU·heatmap·ROI 계산 |

### 4-2. 프론트엔드 (Frontend)

| 카테고리 | 기술 | 역할 |
|---|---|---|
| 언어 | **TypeScript** | 화면 코드 |
| UI | **React** + **Vite** | 3 탭 관리자 콘솔 |
| 상태 관리 | **Zustand** | `useAuthStore` (사용자 정보 + role_level) |
| 차트 | **Plotly.js** / Chart.js | 인사 통계·DAU·heatmap |
| 폼 | **React Hook Form** | 사용자 생성/수정 |

### 4-3. 보안 (이 도메인의 핵심)

- **Cookie 기반 JWT 검증** — 모든 `/admin/*` endpoint 는 `get_current_user` 의존. 브라우저는 `ajin_access`/`ajin_refresh` HttpOnly cookie 를 사용하고, `Authorization: Bearer` 는 `ALLOW_BEARER_AUTH=true` 인 운영 smoke/API 자동화 예외로만 허용
- **CSRF 방어** — `ajin_csrf` non-HttpOnly cookie 값을 unsafe method 에서 `X-CSRF-Token` 헤더로 복사
- **RBAC 게이트** — minLevel 3-5 (탭별로 다름)
- **감사 로깅** — `api_audit_log` 테이블에 모든 요청 기록 (employee_id·endpoint·status·IP·timestamp)
- **로그인 보안** — failed_attempts 5회 → locked_until 자동 설정 (15분)
- **비밀번호 정책** — 최소 8자 + 대소문자·숫자·특수문자 (`frontend/src/lib/passwordPolicy.ts`)
- **must_change_pw** — 첫 로그인·관리자 리셋 후 강제 변경
- **비밀번호 이력** — `password_history` 테이블 (재사용 방지)
- **운영 session store** — production 은 `SESSION_STORE=redis` + `REDIS_URL` 필수. refresh token 은 서버 allowlist 로 rotation/reuse 차단
- **기본 계정 gate** — `admin`, `SYS-0001`, `HR-0001`, `QA-0001`, `PE-0019` 같은 기본·데모 계정이 production 에서 active 이면 release blocker

---

## 5. 백엔드 Endpoint 목록

현재 endpoint 총수는 FastAPI OpenAPI 산출물인 [API 인덱스](API.md)를 기준으로 확인합니다.

### 5-1. 인증 (`/api/auth/*`)

| 메서드 | 경로 | 용도 |
|---|---|---|
| `POST` | `/api/auth/login` | 운영 일반 사용자는 `403 local_login_disabled`; break-glass L5는 2FA 후 HttpOnly cookie 세션 |
| `POST` | `/api/auth/change-password` | 비밀번호 변경 |
| `POST` | `/api/auth/refresh` | refresh cookie rotation + access cookie 재발급 |
| `GET` | `/api/auth/idp/capabilities` | 활성 외부 IdP 목록 |
| `GET` | `/api/auth/idp/{provider}/login` | OIDC/SAML 로그인 redirect |
| `GET` | `/api/auth/idp/{provider}/callback` | OIDC callback → 사내 cookie 세션 |
| `POST` | `/api/auth/idp/saml/acs` | SAML Assertion Consumer Service |
| `POST` | `/api/auth/idp/ldap/login` | LDAP direct-bind 로그인 |
| `GET` | `/api/auth/me` | 내 프로필 + role_level |
| `PUT` | `/api/auth/me` | 내 정보 수정 (이메일·전화) |
| `GET` | `/api/auth/me/login-history` | 내 로그인 이력 |

### 5-2. 사용자 관리 (`/api/admin/users`) — 8개

| 메서드 | 경로 | 용도 | minLevel |
|---|---|---|---|
| `GET` | `/api/admin/users` | 사용자 목록 + 필터 (부서·직급·역할) | 4 |
| `GET` | `/api/admin/users/{id}` | 상세 정보 | 4 |
| `PUT` | `/api/admin/users/{id}` | 정보 수정 | 4 |
| `POST` | `/api/admin/users/{id}/reset-password` | 운영에서는 임시 PW 미응답, IdP 초대/초기화 안내 | 4 |
| `POST` | `/api/admin/users/{id}/lock` | 강제 잠금 | 4 |
| `POST` | `/api/admin/users/{id}/unlock` | 잠금 해제 | 4 |
| `DELETE` | `/api/admin/users/{id}/retire` | **소프트 은퇴** (is_active=0) | 4 |
| `DELETE` | `/api/admin/users/{id}` | **hard delete** 예외 경로. 기본 `403 hard_delete_disabled` | 5 |
| `POST` | `/api/admin/employee-id/preview` | 사번 자동 생성 미리보기 | 4 |
| `POST` | `/api/admin/users` | 신규 계정 생성 | 4 |

### 5-3. 부서 트리 (`/api/admin/departments`) — 1개

| 메서드 | 경로 | 용도 |
|---|---|---|
| `GET` | `/api/admin/departments` | 6 본부 × 27 부서 트리 + 직급·역할 매트릭스 |

### 5-4. 보안 모니터링 (`/api/admin/security/*`) — 3개

| 메서드 | 경로 | 용도 |
|---|---|---|
| `GET` | `/api/admin/security/alerts` | 비정상 로그인 패턴 알림 |
| `GET` | `/api/admin/security/login-stats` | 일별 로그인 / 실패율 |
| `GET` | `/api/admin/security/login-history` | 전체 로그인 이력 (관리자 view) |

### 5-5. 사용 분석 (`/api/admin/analytics/*`) — 4개

| 메서드 | 경로 | 용도 |
|---|---|---|
| `GET` | `/api/admin/analytics/usage` | feature 별 사용량 |
| `GET` | `/api/admin/analytics/heatmap` | 시간 × 요일 사용 히트맵 |
| `GET` | `/api/admin/analytics/dau` | Daily Active Users |
| `GET` | `/api/admin/analytics/roi` | ROI 추정 (LLM 비용 vs 절감 시간) |

### 5-6. 인사 통계 (`/api/admin/hr/*`) — 6개

| 메서드 | 경로 | 용도 |
|---|---|---|
| `GET` | `/api/admin/hr/summary` | 총 인원 + 활성 + 신규 |
| `GET` | `/api/admin/hr/headcount` | 본부·부서별 헤드카운트 |
| `GET` | `/api/admin/hr/gender` | 성별 분포 |
| `GET` | `/api/admin/hr/tenure` | 근속 분포 |
| `GET` | `/api/admin/hr/matrix` | 본부 × 직급 매트릭스 |
| `GET` | `/api/admin/hr/overseas` | 해외법인 파견 현황 (6 법인) |

### 5-7. 시스템 도구 (`/api/admin/system/*`) — 3개 (level=5)

| 메서드 | 경로 | 용도 |
|---|---|---|
| `GET` | `/api/admin/system/audit-log` | 감사 이력 (전체) |
| `POST` | `/api/admin/system/backup` | DB 백업 트리거 |
| `GET` | `/api/admin/system/health` | 시스템 헬스 (DB / Ollama / 디스크) |

### 5-8. 협업 시나리오 (`/api/admin/scenarios/*`) — 9개

| 메서드 | 경로 | 용도 |
|---|---|---|
| `GET` | `/api/admin/scenarios` | 시나리오 목록 |
| `GET` | `/api/admin/scenarios/usage-stats` | 시나리오 사용 통계 |
| `GET` | `/api/admin/scenarios/{id}` | 상세 |
| `POST` | `/api/admin/scenarios` | 새 시나리오 추가 |
| `PUT` | `/api/admin/scenarios/{id}` | 수정 |
| `POST` | `/api/admin/scenarios/{id}/reset` | 기본값 복원 |
| `DELETE` | `/api/admin/scenarios/{id}` | 삭제 |
| `GET` | `/api/admin/scenarios/{id}/history` | 변경 이력 |
| `POST` | `/api/admin/scenarios/{id}/restore/{history_id}` | 이력 복원 |

---

## 6. 데이터베이스 스키마

기능 E 는 **2 SQLite DB** 사용.

### 6-1. auth.db — 사용자·역할·로그인

#### roles 테이블

| 컬럼 | 타입 | 설명 | 예시 |
|---|---|---|---|
| `role_id` | INTEGER PK | 역할 ID | `1` |
| `role_name` | TEXT (UNIQUE) | 역할명 | `EMPLOYEE`, `MANAGER`, `EXECUTIVE`, `HR_ADMIN`, `SYS_ADMIN` |
| `role_level` | INTEGER | 권한 등급 (1-5) | `4` |
| `description` | TEXT | 설명 | |
| `created_at` | TEXT | 생성 시각 | |

#### users 테이블

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `user_id` | INTEGER PK | 내부 ID |
| `employee_id` | TEXT (UNIQUE) | 사번 |
| `username` | TEXT | 표시명 |
| `password_hash` | TEXT | bcrypt 해시 |
| `role_id` | INTEGER FK | 역할 |
| `is_active` | INTEGER | 재직 여부 (1/0) |
| `must_change_pw` | INTEGER | PW 강제 변경 플래그 |
| `failed_attempts` | INTEGER | 연속 실패 횟수 |
| `locked_until` | TEXT | 잠금 해제 시각 |
| `last_login` | TEXT | 마지막 로그인 |
| `created_at` / `updated_at` | TEXT | 생성·갱신 시각 |

#### login_history 테이블

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | INTEGER PK | 이력 ID |
| `user_id` | INTEGER FK | 사용자 |
| `employee_id` | TEXT | 사번 (FK 백업) |
| `action` | TEXT | `login` / `logout` / `password_change` |
| `success` | INTEGER | 성공 여부 (1/0) |
| `ip_address` | TEXT | 접속 IP |
| `user_agent` | TEXT | 브라우저 정보 |
| `timestamp` | TEXT | 시각 |

#### password_history 테이블

비밀번호 재사용 방지용. 최근 N개 해시 저장.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | INTEGER PK | 이력 ID |
| `user_id` | INTEGER FK | 사용자 |
| `password_hash` | TEXT | 이전 해시 |
| `changed_at` | TEXT | 변경 시각 |

### 6-2. audit.db — 감사 로깅

#### api_audit_log 테이블

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | INTEGER PK | 이력 ID |
| `employee_id` | TEXT | 누가 |
| `name` | TEXT | 사용자 이름 |
| `department` | TEXT | 부서 |
| `role` | TEXT | 역할 |
| `endpoint` | TEXT (필수) | 어느 API |
| `method` | TEXT (default `GET`) | HTTP 메서드 |
| `status_code` | INTEGER | 응답 코드 |
| `detail` | TEXT | 추가 정보 (예: query, doc_type) |
| `ip_address` | TEXT | 접속 IP |
| `timestamp` | TEXT | 시각 |

### 6-3. ER 다이어그램

```
┌──────────────┐
│   roles      │ 5 행 (EMPLOYEE/MANAGER/EXEC/HR_ADMIN/SYS_ADMIN)
│  ──────────  │
│  role_id PK  │
│  role_name   │
│  role_level  │
└──────┬───────┘
       │ 1:N
       ▼
┌────────────────────────┐         ┌────────────────────┐
│   users                │         │ login_history      │
│  ─────────────────     │ 1:N     │  ────────────────  │
│  user_id PK            │────────▶│  id PK             │
│  employee_id (UNIQUE)  │         │  user_id FK        │
│  password_hash         │         │  action, success   │
│  role_id FK            │         │  ip_address, ua    │
│  is_active             │         │  timestamp         │
│  failed_attempts       │         └────────────────────┘
│  locked_until          │
└──────┬─────────────────┘
       │ 1:N
       ▼
┌────────────────────┐         ┌────────────────────────┐
│ password_history   │         │ api_audit_log (audit.db)│
│  ────────────────  │         │  ────────────────────  │
│  id PK             │         │  id PK                 │
│  user_id FK        │         │  employee_id           │
│  password_hash     │         │  endpoint, method      │
│  changed_at        │         │  status_code, detail   │
└────────────────────┘         │  ip_address, timestamp │
                                └────────────────────────┘
```

---

## 7. RBAC — 5 역할 + role_level

### 7-1. 5 역할

| Role | level | 권한 | 부서 가시성 |
|---|---|---|---|
| `EMPLOYEE` | 1 | 자기 정보 조회·수정, 일반 feature 사용 | 같은 부서 FULL / 다른 부서 PARTIAL |
| `MANAGER` | 3 | 본부 내 부서 변경, 일부 통계 | 같은 본부 FULL |
| `EXECUTIVE` | 4 | 전사 부서 변경, 인사 통계, 사용자 관리 | 전사 FULL |
| `HR_ADMIN` | 4 | EXEC + 사용자 CRUD | 전사 FULL |
| `SYS_ADMIN` | 5 | 모두 + 시스템 도구 + hard delete 예외 승인 | 전사 FULL |

### 7-2. 3 탭 별 minLevel (`frontend/src/routes/admin.tsx`)

| 탭 | 한글 | minLevel | 보이는 사람 |
|---|---|---|---|
| `account_delegation` | 계정 위임 | 4 | HR·SYS |
| `security_alerts` | 보안 알림 | 4 | HR·SYS |
| `system_health` | 시스템 헬스 | 5 | SYS |

### 7-3. 가시성 정책 (Feature A 와 공유)

`core/auth/visibility.py` — 같은 모듈을 `/employee/search` 와 공유. 자세한 내용은 [FEATURE_A_SEARCH.md §7](FEATURE_A_SEARCH.md) 참조.

---

## 8. 보안 모니터링 — `security_monitor.py`

### 8-1. 비정상 패턴 감지

`/api/admin/security/alerts` 가 다음 패턴을 자동 감지:

| 패턴 | 트리거 | 대응 |
|---|---|---|
| **연속 실패** | 같은 IP 에서 5회 이상 실패 | locked_until 자동 설정 |
| **비정상 시간대** | 자정 ~ 06:00 로그인 | 알림 카드 |
| **IP 변경** | 24시간 내 다른 국가 IP | 의심 알림 |
| **봇 의심 user-agent** | Python-requests, curl 등 | 차단 |
| **계정 폭증** | 1시간 내 같은 사번 10+ 시도 | 임시 잠금 |

### 8-2. 로그인 통계

`/api/admin/security/login-stats` 응답:
```json
{
  "daily": [
    {"date": "2026-05-09", "success": 245, "failure": 12},
    ...
  ],
  "failure_rate_percent": 4.7,
  "top_failed_employees": ["EMP-A0042", "EMP-B0123"],
  "top_failed_ips": ["192.168.1.50"]
}
```

---

## 9. 사용 분석 — `usage_analytics.py`

### 9-1. DAU (Daily Active Users)

`/api/admin/analytics/dau` — 일별 고유 사용자 수. `api_audit_log` 의 `employee_id` DISTINCT 카운트.

### 9-2. Heatmap

`/api/admin/analytics/heatmap` — 시간 (24h) × 요일 (7d) 사용 강도. 168 셀 매트릭스.

```
시간↓ \ 요일→  월   화   수   목   금   토   일
00-01          2    1    3    2    2    0    0
01-02          0    0    1    0    0    0    0
...
09-10         85   92   88   91   80    5    2
10-11        110  115  108  112   98    7    3
...
```

### 9-3. ROI 추정

`/api/admin/analytics/roi` — LLM 비용 vs 시간 절감 환산.

```json
{
  "llm_cost_krw_monthly": 2300,
  "estimated_hours_saved_monthly": 85,
  "estimated_value_krw_monthly": 4250000,
  "roi_ratio": 1847
}
```
- LLM 비용: Vertex billing 또는 Ollama 추정 GPU 시간
- 시간 절감: feature 사용량 × 평균 작업 시간 단축
- 시간 가치: 시급 50,000원 × 절감 시간

---

## 10. 부속 모듈 가이드

### 10-1. 백엔드

| 파일 | 역할 |
|---|---|
| `backend/routers/admin.py` | 사용자·보안·분석·인사·시스템 API |
| `backend/routers/admin_scenarios.py` | 협업 시나리오 CRUD API |
| `backend/routers/auth.py` | 로그인·비밀번호·프로필 API |
| `backend/auth_middleware.py` | JWT 검증 + 감사 로깅 미들웨어 |
| `features/admin/security_monitor.py` | 비정상 패턴 감지 |
| `features/admin/usage_analytics.py` | DAU·heatmap·ROI 계산 |
| `core/auth/database.py` | auth.db CRUD |
| `core/auth/jwt_handler.py` | JWT 발급·검증 |
| `core/auth/permissions.py` | 권한 체크 헬퍼 |
| `core/auth/rbac.py` | role_level 정의 |
| `core/auth/visibility.py` | 가시성 (Feature A 공유) |
| `core/auth/password.py` | bcrypt 해시 + 정책 검증 |

### 10-2. 프론트엔드 컴포넌트 트리

```
/admin 라우트 (frontend/src/routes/admin.tsx, 582 LOC)
│
└─ <Admin>
   │
   ├─ <TabBar>  — 3 탭 (RBAC 게이트 적용 — minLevel 미만 숨김)
   │
   ├─ "계정 위임" 탭 (level≥4)
   │  └─ <AccountDelegationTab>
   │     ├─ <UserFilterBar>       — 부서·직급·역할 캐시 조회
   │     ├─ <IdpManagedRedirect>  — IdP 중심 계정 운영 안내
   │     ├─ <PermissionMatrixUI>  — 권한 매트릭스
   │     └─ <ApprovalQueueTable>  — 권한 변경 승인 대기열
   │
   ├─ "보안 알림" 탭 (level≥4)
   │  └─ <SecurityAlertsTab>
   │     ├─ <SecurityAlertCard>   — security_monitor 결과
   │     ├─ <TwoFactorEnrollModal>
   │     └─ <LoginHistoryTable>
   │
   └─ "시스템 헬스" 탭 (level=5)
      └─ <SystemHealthTab>
         ├─ <SystemHealth>        — DB·Ollama·IdP·감사 sink
         ├─ <BackupTrigger>
         └─ <AuditLogViewer>      — api_audit_log 검색
```

### 10-3. 3 탭 → minLevel 매트릭스

```
              EMP(1)  MGR(3)  EXEC(4)  HR(4)  SYS(5)
계정 위임       ❌     ❌      ❌      ✅     ✅
보안 알림       ❌     ❌      ❌      ✅     ✅
시스템 헬스     ❌     ❌      ❌      ❌     ✅
```

---

## 11. 사번 자동 생성 (`/admin/employee-id/preview`)

### 11-1. 규칙

부서 prefix + 4자리 일련번호. 예:

| 부서 | prefix | 사번 예 |
|---|---|---|
| 안전보건팀 | A | EMP-A0042 |
| 품질보증팀 | Q | EMP-Q0103 |
| 구매팀 | P | EMP-P0078 |
| IT전략팀 | I | EMP-I0015 |
| ... | ... | ... |

prefix 는 `config.py:DEPARTMENTS` 의 `prefix` 필드 또는 자동 생성.

### 11-2. 동작

1. 부서 선택 → POST `/admin/employee-id/preview`
2. 서버가 해당 prefix 의 마지막 일련번호 +1 계산
3. 사용 가능한 다음 ID 반환 (예: `EMP-A0043`)
4. HR 이 확인 후 `POST /admin/users` 로 생성

---

## 12. 운영·확장 노트

### 12-1. 비밀번호 정책 (`frontend/src/lib/passwordPolicy.ts` + `core/auth/password.py`)

- 최소 8자
- 대문자·소문자·숫자·특수문자 4 종 중 3 종 이상
- 최근 5개 비밀번호 재사용 금지 (`password_history` 활용)
- 90일 강제 변경 (옵션)

### 12-2. 잠금 정책

- 5회 연속 실패 → 15분 자동 잠금
- HR_ADMIN 이 수동 잠금/해제 가능 (`/lock`·`/unlock`)
- 잠금 시 사용자에게 이메일 알림 (옵션 — SMTP env 필요)

### 12-3. 백업 (`/admin/system/backup`)

- 모든 SQLite DB 를 ZIP 으로 덤프
- 결과: `data/backup/ajin-backup-YYYYMMDD-HHMMSS.zip`
- 클라우드 동기화 (Cloud Storage 등)는 백업 endpoint 범위에 포함하지 않음 — 운영자가 별도 보관 절차로 처리

### 12-4. 성능 — 응답 시간 목표

| 작업 | 목표 | 현재 |
|---|---|---|
| `/admin/users` (650명) | < 300ms | ~50-100ms |
| `/admin/security/alerts` | < 200ms | ~80ms |
| `/admin/hr/headcount` | < 200ms | ~30-50ms |
| `/admin/system/audit-log` (10k 행) | < 500ms | ~200-300ms |
| `/admin/system/backup` | < 30s | ~5-15s (DB 크기 의존) |

### 12-5. 현재 반영 및 향후 확장

- [x] **2FA** — TOTP enroll/confirm/verify/backup/disable API 와 관리자 UI 도입
- [x] **SSO / 외부 IdP** — OIDC, SAML, LDAP provider 와 IdP 관리 흐름 도입
- [x] **권한 매트릭스 / 승인 워크플로** — `/api/admin/permissions/*` 와 2단계 승인 이력 도입
- [x] **감사 로그 외부 연동** — SIEM 호환 export (Splunk JSON, CEF, LEEF) 도입
- [x] **계정 위임·정합성 운영 화면** — IdP 그룹 매핑, Feature D delegation_rules, user_cache reconcile job 상태 요약 제공
- [x] **브라우저 cookie auth hardening** — `access_token`/`refresh_token` body·query·localStorage 노출 제거, HttpOnly cookie + CSRF header + refresh rotation 도입
- [x] **Release gate** — `make feature-e-release-check` 로 74 endpoint surface, cookie/CSRF wiring, frontend token posture, IdP-first 정책, hard-delete 기본 차단, audit retention, production secret/session/default 계정 blocker 검증
- [ ] **알림 자동화** — 비정상 로그인 → Slack DM
- [ ] **휴가 기반 사용자 권한 임시 위임** — 기간 만료와 승인 정책이 있는 별도 위임 모델 필요

### 12-6. Release hardening 기준 문서

- OWASP JWT Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html
- NIST SP 800-63B — https://pages.nist.gov/800-63-4/sp800-63b.html
- OAuth 2.0 Security BCP (RFC 9700) — https://www.rfc-editor.org/rfc/rfc9700.html
- MDN `Set-Cookie` — https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie
- FastAPI response cookies — https://fastapi.tiangolo.com/advanced/response-cookies/

---

## 13. 자주 묻는 질문 (FAQ)

**Q1. 비밀번호를 잊어버렸어요.**
> 운영에서는 HR_ADMIN 이 `/admin/users/{id}/reset-password` 를 호출해도 임시 PW 를 응답하지 않습니다. 사내 IdP 의 초대/초기화 절차를 사용합니다. 로컬/dev 에서는 명시적으로 허용된 경우에만 임시 PW 를 표시합니다.

**Q2. 다른 사용자의 정보가 안 보여요.**
> 가시성 정책 (FULL/PARTIAL/HIDDEN). 같은 본부가 아니면 휴대폰·이메일 숨김. 자세한 내용은 [FEATURE_A_SEARCH.md §7](FEATURE_A_SEARCH.md).

**Q3. 시스템 도구 탭이 안 보여요.**
> minLevel=5 (SYS_ADMIN) 만 보입니다. 본인 권한이 부족할 가능성. `/auth/me` 로 role_level 확인.

**Q4. 퇴사자 데이터를 완전히 지우고 싶어요.**
> 1단계 — `/admin/users/{id}/retire` (소프트 — 데이터 보존, is_active=0)
> 2단계 — `/admin/users/{id}` DELETE 는 기본 `403 hard_delete_disabled` 입니다.
> 예외적으로 `AUTH_ALLOW_HARD_DELETE=true`, SYS_ADMIN(L5), 확인 사번, 사유가 모두 있을 때만 실행됩니다.
> 감사 이벤트는 기본 hot 1년 + archive 3년 보존 기준을 따릅니다.

**Q5. 5회 실패 잠금을 해제하려면?**
> HR_ADMIN 이 `/admin/users/{id}/unlock` 호출. 또는 15분 후 자동 해제.

**Q6. 감사 로그가 너무 많아요.**
> `api_audit_log` 가 1년 = 수백만 행 가능. 운영자가 주기적으로 오래된 행 archive·삭제 필요. cron 스크립트 추가 권장.

**Q7. ROI 가 너무 낙관적이에요.**
> ROI 추정은 "시간 절감 × 시급" 단순 공식. 실제 가치는 부서·업무에 따라 다름. 운영자가 `usage_analytics.py:_estimate_hours_saved()` 의 가중치 조정 가능.

**Q8. Firebase 로그인 통합은?**
> Firebase ID Token 교환 endpoint 는 폐기되었습니다. 외부 로그인은 `/api/auth/idp/*` 의 OIDC/SAML/LDAP 흐름에서 사내 cookie 세션을 발급합니다.

**Q8-1. 운영에서 사번/비밀번호 로그인이 되나요?**
> 일반 사용자는 되지 않습니다. 운영 기본값은 `AUTH_PRIMARY_PROVIDER=idp` 이며, `/api/auth/login` 은 일반 사용자에게 `403 local_login_disabled` 를 반환합니다. 로컬 로그인은 `bootstrap_admin` 계열 SYS_ADMIN(L5) + TOTP 2FA break-glass 용도로만 남깁니다.

**Q9. 브라우저가 access token 을 어디에 저장하나요?**
> 저장하지 않습니다. access/refresh JWT 는 HttpOnly cookie 로만 전달되고, 프런트는 사용자 프로필 메타데이터만 Zustand 에 보관합니다. unsafe method 는 `ajin_csrf` 값을 `X-CSRF-Token` 헤더로 복사해야 합니다.

---

## 14. 용어집

| 용어 | 풀이 |
|---|---|
| **JWT** | JSON Web Token — 서버가 서명한 신분증 토큰. 브라우저에서는 HttpOnly cookie 안에만 보관 |
| **HttpOnly cookie** | JavaScript 에서 읽을 수 없는 cookie. access/refresh token 보호에 사용 |
| **CSRF** | Cross-Site Request Forgery — cookie 인증 요청 위조를 막기 위해 `X-CSRF-Token` 검증 |
| **bcrypt** | 단방향 해시 알고리즘 — 원본 비밀번호 역추적 불가 |
| **RBAC** | Role-Based Access Control — 역할 기반 접근 제어 |
| **role_level** | 권한 등급 (1=사원 / 3=매니저 / 4=임원 / 5=SYS) |
| **must_change_pw** | 첫 로그인·관리자 리셋 후 PW 강제 변경 플래그 |
| **soft delete** | DB 행을 지우지 않고 is_active=0 으로 비활성화 |
| **hard delete** | 기본 차단된 예외 삭제 경로. `AUTH_ALLOW_HARD_DELETE=true` + SYS_ADMIN(L5) + 사유 필요 |
| **DAU** | Daily Active Users — 일별 고유 사용자 수 |
| **Heatmap** | 시간 × 요일 사용 강도 매트릭스 |
| **ROI** | Return on Investment — 투자 대비 효과 |
| **2FA** | Two-Factor Authentication — 비밀번호 + 추가 인증 |
| **SSO** | Single Sign-On — 한 번 로그인으로 여러 서비스 |
| **SAML / OIDC** | 외부 IdP 연동 표준 (Okta·Azure AD 등) |
| **TOTP** | Time-based One-Time Password (Google Authenticator) |
| **SIEM** | Security Information and Event Management |
| **IdP** | Identity Provider — 외부 인증 서버 |
| **감사 로그** | 누가·언제·어느 endpoint 호출했는지 기록 |

---

## 15. 변경 이력 (Feature E 한정)

| 버전 | 날짜 | 주요 변경 |
|---|---|---|
| Phase 1 | 2025-? | 사용자 CRUD + JWT 기본 |
| v2.3 | 2025-? | failed_attempts·locked_until 마이그레이션 |
| v3.0 | 2026-? | 감사 로깅 (api_audit_log) 도입 |
| v3.4 | 2026-04 | 본부/부서 selectbox 레이스 컨디션 수정 |
| v3.5 | 2026-04 | Tier 4: 7→6탭 (이력 → 보안 통합), CSV/XLSX 다운로드, 날짜 필터 |
| v3.6 | 2026-? | 페이지네이션 + 정렬 + Drawer + "전체 보기" 토글 (인사 검색) |
| v4.9 | 2026-05 | 브라우저 auth 를 HttpOnly cookie + CSRF + refresh rotation 으로 hardening, `feature-e-release-check` gate 추가 |
| v4.10 | 2026-05 | 운영 IdP-first 정책, break-glass 2FA 로컬 로그인, default/test 계정 fail-closed, hard-delete 기본 차단, audit retention/redaction gate 추가 |

---

## 16. 한눈 요약 카드

```
┌──────────────────────────────────────────────────────────────┐
│  기능 E — 인사·관리자 패널 (Admin · HR · Security)          │
├──────────────────────────────────────────────────────────────┤
│  🛡  사내 사용자·접근권한·로그인·시스템을 통제                │
│                                                              │
│  💻 Backend     FastAPI + SQLite × 2 + cookie JWT + bcrypt   │
│                  + OIDC/SAML/LDAP IdP                         │
│  🖥  Frontend    React + Vite + TS + Zustand + Plotly         │
│                  3 탭 (RBAC 게이트 적용)                     │
│  🔐 보안         HttpOnly cookie + CSRF + RBAC + 감사 로깅   │
│                  + 5회 실패 자동 잠금 + bcrypt + refresh 회전│
│                                                              │
│  🌐 Endpoint    OpenAPI 기준 — docs/API.md 자동 산정        │
│  📊 SQLite × 2  auth.db (4 테이블) + audit.db (1 테이블)    │
│                                                              │
│  👥 5 역할       EMPLOYEE(1) / MANAGER(3) / EXECUTIVE(4) /  │
│                  HR_ADMIN(4) / SYS_ADMIN(5)                  │
│                                                              │
│  📂 3 탭 — minLevel                                          │
│   • 계정 위임 (4)   • 보안 알림 (4)                          │
│   • 시스템 헬스 (5) — SYS_ADMIN 만                           │
│                                                              │
│  📁 Module       features/admin/ (2) + core/auth/ (10)       │
│                  routes/admin.tsx (582 LOC)                  │
│                                                              │
│  🔗 공유          Feature A 와 visibility.py 공유 (가시성)    │
│                  Feature D 와 delegation_rules 연동          │
└──────────────────────────────────────────────────────────────┘
```

---

문서 갱신: 2026-05-20 | 본 문서는 feature 변경 시 함께 갱신해주세요.
