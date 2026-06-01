# 기능 A — 사내 인원 검색 / 조직도 (Search · Organization)

> **이 문서는 누구를 위한 것인가요?**
> 개발자가 아닌 분 (운영자·기획자·도메인 전문가) 도 끝까지 읽을 수 있도록 작성했습니다.
> 어려운 용어는 처음 등장할 때 _기울임_ 으로 표시하고 옆에 짧은 설명을 붙입니다.

---

## 1. 한 줄 요약

**"누구한테·어떤 문서로·어디서부터 시작하지?" 를 한 화면에서 해결합니다.**

자연어로 직원·문서·SOP를 동시에 찾는 **통합 검색**, 사람·문서 두 카테고리의 전용 탭, 어느 페이지에서든 **⌘K** 로 호출되는 글로벌 명령 팔레트를 제공합니다. 본부·팀별 헤드카운트가 노출된 조직도, 자주 찾는 사람 즐겨찾기, 검색 이력, 신입 사원에게만 노출되는 온보딩 사이드 패널까지 한 페이지에서 동작합니다.

**개인정보 정책 (F5, 2026-05-10):** 사내 협업 자산인 **내선번호와 사내 이메일은 본부·부서 관계 없이 공개**되며, **개인 휴대폰만 PARTIAL 등급에서 마스킹**됩니다. 전직원 상세 개인정보는 인사관리팀이 별도 운영합니다.

---

## 2. 누가, 언제 쓰는가?

| 사용자 | 시나리오 | 기능 A 가 해주는 일 |
|---|---|---|
| **품질보증팀 신입사원** | 8D 보고서 수정해야 하는데 부품개발팀 담당자를 모름 | "부품개발팀 과장 누구?" 검색 → 이름·내선·이메일 즉시 |
| **구매팀 대리** | 협력사 미팅에 안전보건팀 동행이 필요 | 본부 = "생산본부" + 팀 = "안전보건팀" 필터 → 직급 순 정렬 카드 |
| **신입사원 온보딩** | 회사 조직 구조 파악 | 조직도 화면 → 본부 4개 → 팀 27개 트리 + 헤드카운트 |
| **HR 관리자** | 전체 인원 현황 확인 | 페이지네이션으로 전체 직원 조회, 마스킹 없이 모든 필드 열람 |

---

## 3. 전체 작동 흐름 (그림으로)

사용자가 검색창에 "안전보건팀 부장" 을 입력했을 때:

```
[브라우저]                                         [서버]
사용자 입력
    │
    │ "안전보건팀 부장"
    ▼
검색창 (React 컴포넌트)
    │
    │ HTTP POST /api/employee/search
    │ {"query": "안전보건팀 부장"}
    ▼
─────────────── 인터넷 / 사내망 ───────────────
                                                FastAPI 서버
                                                    │
                                                    │ 1) 로그인 사용자 확인 (인증 미들웨어)
                                                    ▼
                                                EmployeeSearchEngine
                                                    │
                                                    │ 2) 자연어에서 조건 추출
                                                    │   "안전보건팀" → department
                                                    │   "부장" → position
                                                    ▼
                                                SQLite (employees.db)
                                                    │
                                                    │ 3) SELECT * FROM employees
                                                    │   WHERE department='안전보건팀'
                                                    │     AND position='부장'
                                                    ▼
                                                가시성 필터 (RBAC)
                                                    │
                                                    │ 4) 보는 사람 vs 대상 부서 비교
                                                    │   같은 부서 → FULL (전체)
                                                    │   다른 부서 → PARTIAL (휴대폰 숨김)
                                                    │   퇴사자  → HIDDEN (제외)
                                                    ▼
                                                JSON 응답
    ┌───────────────────────────────────────────────┘
    ▼
검색 결과 카드/표 렌더링
    │
    │ 클릭 시 상세 Drawer 열림
    ▼
[브라우저 화면]
```

핵심은 **"검색 → 조건 추출 → DB 조회 → 가시성 필터 → 화면"** 5단계입니다. 각 단계는 뒤에서 자세히 설명합니다.

---

## 4. 기술 스택

기술 스택을 4 영역으로 나눠 봅니다. 각 항목 옆 괄호 안은 _그게 뭔가요?_ 풀이입니다.

### 4-1. 백엔드 (Backend, "서버 쪽 두뇌")

| 카테고리 | 기술 | 역할 |
|---|---|---|
| 언어 | **Python 3.11+** | 서버 코드 작성 |
| 웹 프레임워크 | **FastAPI** _(요청을 받고 응답을 돌려주는 도구)_ | `/api/employee/...` 같은 endpoint 제공 |
| 데이터베이스 | **SQLite** _(파일 형태의 가벼운 DB — 엑셀처럼 한 파일에 표가 담김)_ | `data/employees.db` 에 직원 목록 저장 |
| 검색 엔진 (옵션) | **SQLite FTS5** _(SQLite 의 전문 검색 기능)_ | 빠른 키워드 검색 |
| 검색 엔진 (옵션, 비활성) | **BM25 + 벡터 + RRF** _(문서 검색용 알고리즘 3종)_ | 사내 문서 하이브리드 검색 — 현재 `ENABLE_FEATURE_A=false` 로 꺼져있음 |
| 인증 | **JWT** _(로그인 후 발급되는 신분증 토큰)_ | "이 요청을 누가 보냈나?" 를 매 요청마다 확인 |
| 가시성 엔진 | **사내 자체 RBAC** _(역할 기반 접근 제어)_ | 보는 사람 ↔ 대상 부서 관계로 마스킹 결정 |

### 4-2. 프론트엔드 (Frontend, "사용자가 보는 화면")

| 카테고리 | 기술 | 역할 |
|---|---|---|
| 언어 | **TypeScript** _(JavaScript 에 타입 안전성 추가)_ | 화면 코드 작성 |
| UI 라이브러리 | **React** _(컴포넌트 단위로 화면을 조립하는 도구)_ | 검색창·카드·표·드로어 구성 |
| 빌드 도구 | **Vite** _(코드를 묶어 브라우저용으로 만들어주는 도구)_ | 개발 서버 + 배포용 정적 파일 생성 |
| 라우팅 | **React Router** | URL `/search` 와 화면 컴포넌트 연결 |
| 상태 관리 | **Zustand** _(앱 전체에서 공유하는 데이터 보관소)_ | 로그인 사용자 정보 (`useAuthStore`) |
| 시각화 | **Plotly** (조직도) / **MapView** (사업장 지도) | 본부·팀 트리, 6개 사업장 위치 |

### 4-3. 인프라 (운영 환경)

| 항목 | 값 |
|---|---|
| 컨테이너 | Docker (multi-stage build) |
| 운영 OS | Linux (Cloud Run) / macOS (개발) |
| 리버스 프록시 | nginx-rp (개발) / Cloud Run backend + 정적 SPA hosting rewrite 경로 |
| 로깅 | Python logging + docker compose logs |

### 4-4. 보안

- **JWT 인증** — `/api/employee/...` 및 `/api/search/...` 모든 endpoint 는 로그인 필수
- **RBAC 가시성** — 본 문서 §7 참조
- **감사 로깅** — 모든 검색 요청은 `log_api_access()` 로 기록 (누가·언제·무엇을 검색했는지)
- **입력 살균** — `sanitize_llm_input()` 으로 LLM 프롬프트 인젝션 방지

---

## 5. 백엔드 Endpoint 목록

기능 A 가 제공하는 서버 API. 모두 로그인 필요.

| 메서드 | 경로 | 용도 | 입력 | 출력 |
|---|---|---|---|---|
| `POST` | `/api/employee/search` | 자연어 직원 검색 | `{"query": "안전보건팀 부장"}` | 매칭된 직원 목록 + 메시지 |
| `GET` | `/api/employee/list?limit=24&offset=0` | 페이지네이션 전체 조회 | URL 쿼리 파라미터 | 직원 카드 (가시성 필터 적용) |
| `GET` | `/api/employee/by-department?dept=안전보건팀` | 특정 부서 전체 인원 | `dept` 또는 `division` | 해당 단위 인원 목록 |
| `GET` | `/api/employee/org-tree` | 조직도 트리 (본부 → 팀) | 없음 | `[{division, headcount, teams: [...]}]` |
| `GET` | `/api/employee/{employee_id}/extras` | **(W7)** 출장이력·직속부하·결재 — 권한 분기 | path | `{permission, trips, direct_reports, approvals}` |
| `POST` | `/api/search/documents` | 사내 문서 하이브리드 검색 (BM25+Vector RRF) | `{"query": ..., "k": 10, "doc_type_filter": ...}` | 문서 결과 + 점수 |
| `POST` | `/api/search/summarize` | 검색 결과를 LLM 으로 요약 (SSE 스트리밍) | `{"query": ...}` | 실시간 스트리밍 텍스트 |

> **W7 권한 정책** (`features/search/adapters/erp_adapter.py`):
> - `role_level >= 5` (SYS_ADMIN/HR_ADMIN) → `FULL` (출장·결재·부하 모두 노출)
> - 같은 부서 동료 → `PARTIAL` (직속부하만)
> - 그 외 → `DENIED` (권한 부족 안내)
>
> `UserContext.role` (문자열) 을 정수 레벨로 매핑하는 룩업이 라우터 핸들러에 위치 — `core/auth/visibility.py` 의 RBAC 정책과 정합 (`backend/routers/employee.py`).

### 응답 예시 — `/api/employee/search`

요청:
```json
POST /api/employee/search
{ "query": "안전보건팀 부장" }
```

응답 (요약):
```json
{
  "mode": "structured",
  "total": 1,
  "results": [
    {
      "name": "홍길동",
      "department": "안전보건팀",
      "division": "생산본부",
      "position": "부장",
      "extension": "1234",            ← 항상 공개 (사내 협업 자산)
      "email": "hong@ajin.co.kr",     ← 항상 공개 (사내 이메일, F5 정책)
      "phone": "(내선번호로 연락)",   ← PARTIAL 시 마스킹 (개인 휴대폰)
      "plant": "경산 본사"
    }
  ],
  "message": "1명을 찾았습니다.",
  "formatted_markdown": "..."
}
```

---

## 6. 데이터베이스 스키마

직원 정보는 **SQLite 파일 1개** (`data/employees.db`) 안의 `employees` 테이블 하나에 저장됩니다.

### 6-1. employees 테이블 — 컬럼 명세

| 컬럼명 | 타입 | 설명 | 예시 |
|---|---|---|---|
| `employee_id` | TEXT (PK) | 사번 — 고유 식별자 | `EMP-A0001` |
| `name` | TEXT (필수) | 한글 이름 | `홍길동` |
| `name_en` | TEXT | 영문 이름 | `Hong Gil-dong` |
| `gender` | TEXT | 성별 (`M` 또는 `F`) | `M` |
| `position` | TEXT (필수) | 직급 | `부장`, `과장`, `사원` |
| `position_level` | INTEGER (필수) | 직급 정렬용 숫자 | `4` (부장=4) |
| `division` | TEXT (필수) | 본부 | `생산본부`, `재경본부` |
| `department` | TEXT (필수) | 팀 | `안전보건팀`, `재무팀` |
| `department_id` | TEXT | 부서 코드 | `DEPT-SAFETY` |
| `role` | TEXT | RBAC 역할 (default `''` = 일반) | `SYS_ADMIN`, `HR_ADMIN` |
| `email` | TEXT | 이메일 | `gildong@ajin.co.kr` |
| `phone` | TEXT | 휴대폰 | `010-1234-5678` |
| `extension` | TEXT | 사내 내선 | `1234` |
| `plant` | TEXT (default `경산 본사`) | 근무지 사업장명 | `경산 본사`, `경주 구어` |
| `plant_id` | TEXT (default `PLANT-KS-HQ`) | 사업장 코드 | `PLANT-GJ` |
| `hire_date` | TEXT | 입사일 (YYYY-MM-DD) | `2020-03-15` |
| `is_active` | INTEGER (default `1`) | 재직 여부 (1=재직, 0=퇴사) | `1` |
| `is_team_leader` | INTEGER (default `0`) | 팀장 여부 | `0` |
| `photo_url` | TEXT | 프로필 사진 URL | (현재 미사용) |
| `overseas_assignment` | TEXT | 해외법인 파견 정보 (v1.6 추가) | `JOON INC (Georgia)` |
| `language_skills` | TEXT | 어학 능력 (v1.6 추가) | `English: Advanced` |

### 6-2. ER 다이어그램 (간단)

```
┌──────────────────────────────────┐
│         employees (1 테이블)     │
│  ────────────────────────────    │
│  employee_id (PK) ─── 사번       │
│  name, name_en, gender           │
│  position, position_level        │
│  division, department, dept_id   │
│  role (RBAC)                     │
│  email, phone, extension         │
│  plant, plant_id                 │
│  hire_date, is_active            │
│  is_team_leader, photo_url       │
│  overseas_assignment             │
│  language_skills                 │
└──────────────────────────────────┘
       │
       │ (참조 — config.py 에 정적 정의)
       ▼
┌──────────────────────────────────┐
│  DEPARTMENTS  (config.py)         │
│  PLANTS       (config.py)         │
│  COMPANY_INFO (config.py)         │
└──────────────────────────────────┘
```

> **왜 부서·사업장은 별도 테이블이 아니라 코드 파일에 있나요?**
> 부서 27개·사업장 6개는 변동이 거의 없습니다. DB 정규화로 분리하기보다 코드 (`config.py`) 에 정적 dict 로 두면 편집·검토가 쉽습니다 (Git 으로 변경 이력 추적).

### 6-3. 주요 인덱스 (검색 성능)

```sql
CREATE INDEX IF NOT EXISTS idx_emp_dept ON employees(department);
CREATE INDEX IF NOT EXISTS idx_emp_div  ON employees(division);
CREATE INDEX IF NOT EXISTS idx_emp_pos  ON employees(position);
CREATE INDEX IF NOT EXISTS idx_emp_name ON employees(name);
```

이 4개 인덱스 덕분에 `WHERE department=?` 쿼리가 1ms 안에 끝납니다 (650명 기준).

### 6-4. FTS5 전문 검색 (옵션)

`employees_fts` 가상 테이블 (`features/search/employee/fts_index.py`) 을 통해 이름·부서·직급의 부분 매칭 검색이 가능합니다. 일반 SQL `LIKE '%xxx%'` 보다 5-10배 빠릅니다.

---

## 7. 가시성 정책 (개인정보 마스킹 규칙)

기능 A 의 핵심 보안 장치. 같은 데이터라도 **누가 보느냐** 에 따라 다르게 보입니다.

### 7-1. 3계층 모델

| 등급 | 의미 | 보이는 필드 |
|---|---|---|
| **FULL** | 전체 정보 열람 | 이름·부서·직급·이메일·휴대폰·내선·입사일·해외파견·어학 |
| **PARTIAL** | 협업 자산 공개 + 휴대폰만 마스킹 (F5, 2026-05-10) | 이름·부서·직급·**내선·이메일**·근무지 — 휴대폰·입사일은 숨김 |
| **HIDDEN** | 결과에서 제외 | 아무것도 안 보임 (검색 결과 카드 자체 미생성) |

> **F5 정책 변경 배경**: 사용자 시연 피드백 — 사내 협업에서 내선번호와 사내 이메일은 매일 사용하는 자산이라 마스킹할 이유가 없음. 개인 휴대폰만 PARTIAL 등급에서 마스킹 유지하고, 전직원 상세 개인정보는 인사관리팀이 별도 운영. 적용 위치: `core/auth/visibility.py:filter_employee_fields()` + 프론트 `frontend/src/lib/visibility.ts:maskEmail/maskPhone()`.

### 7-2. 판단 우선순위

`core/auth/visibility.py:determine_visibility()` 함수가 다음 순서로 판단:

```
1. 대상이 INACTIVE (퇴사자)              → HIDDEN
2. 인증 컨텍스트가 없는 내부 호출          → PARTIAL
3. 보는 사람이 SYS_ADMIN / HR_ADMIN      → FULL
4. 보는 사람이 TEAM_LEAD (팀장 이상)     → FULL (전 부서)
5. 보는 사람과 대상이 같은 부서          → FULL
6. 보는 사람과 대상이 같은 본부          → PARTIAL
7. 그 외 (다른 본부)                      → PARTIAL
```

### 7-3. 예시

> **시나리오:** 구매팀 대리 김철수 가 안전보건팀 부장 홍길동 을 검색

- 김철수의 부서: `구매팀` → 본부 `구매본부`
- 홍길동의 부서: `안전보건팀` → 본부 `생산본부`
- 두 사람이 **다른 본부** → 김철수에게는 홍길동이 **PARTIAL**

화면 출력 (F5 정책):
```
홍길동  │  생산본부 / 안전보건팀  │  부장
내선 #1234  │  경산 본사
이메일 hong@ajin.co.kr   ← 사내 이메일은 PARTIAL 에서도 공개
휴대폰 (내선번호로 연락)  ← PARTIAL 시 마스킹 유지
```

> **시나리오 변경:** 같은 안전보건팀 사원이 홍길동을 검색
- 같은 부서 → **FULL**
- 휴대폰 원본까지 모두 노출

### 7-4. 감사 로깅

모든 검색 요청은 다음 정보가 `audit.db` 에 기록됩니다:
- 누가 (employee_id, role)
- 언제 (timestamp)
- 무엇을 (query, endpoint)
- 결과 (status_code, masked 카운트, excluded 카운트)

이는 ISO 27001 / 개인정보보호법 의 **접근 이력 보존 의무** 를 충족하기 위함입니다.

---

## 8. 프론트엔드 컴포넌트 트리

### 8-1. 페이지 구조

```
/search 라우트 (frontend/src/routes/search.tsx, 690 LOC)
│
├─ <_shell> (공통 레이아웃)
│  ├─ <TopBar> (사이트 헤더 + 검색창)
│  └─ <Sidebar> (네비게이션)
│
└─ <Search> (이 기능의 메인 페이지)
   │
   ├─ 필터 영역
   │  ├─ <Select hq>      — 본부 드롭다운 (전체 / 6 본부)
   │  ├─ <Select team>    — 팀 드롭다운 (hq 선택 후 활성)
   │  ├─ <Select position>— 직급 (전체 / 부장~사원)
   │  ├─ <Select gender>  — 성별
   │  └─ <Select plant>   — 사업장 (6개)
   │
   ├─ 검색창
   │  └─ <Input query>    — 자연어 입력
   │
   ├─ 정렬·표시 옵션
   │  ├─ <SortSelector>   — 직급/이름/부서 (localStorage 영속)
   │  └─ <ColumnToggle>   — "전체 보기" 토글 (관리자급)
   │
   ├─ 결과 영역 (필터링·정렬된 직원 카드 그리드)
   │  └─ <EmployeeCard> × N
   │      └─ 클릭 → <EmployeeDetailDrawer> 열림
   │
   ├─ 시각화 영역 (선택)
   │  ├─ <MapView>        — 6 사업장 위치 마커
   │  └─ <OrgTreemap>     — 본부 → 팀 헤드카운트 (Plotly)
   │
   └─ 다운로드
      └─ <DownloadActions> — CSV / XLSX / PDF 내보내기
```

### 8-2. 상태 관리 (어떤 데이터를 어디에)

| 데이터 | 위치 | 영속성 |
|---|---|---|
| 로그인 사용자 정보 | `useAuthStore` (Zustand) | localStorage |
| 정렬 키 | `sortKey` (useState) | localStorage `ajin-search-sort` |
| 필터 상태 (hq/team/position 등) | useState | 메모리만 (페이지 이탈 시 리셋) |
| 직원 목록 (백엔드) | useState + `fetchEmployeeList()` | API 호출마다 갱신 |
| 조직도 트리 | useState + `fetchOrgTree()` | 페이지 진입 시 1회 |
| 사업장 좌표 | mock seed (`PLANTS_COORDS`) | 정적 |

### 8-3. API 호출 흐름

`frontend/src/api/employee.ts` 가 백엔드 API 4개를 감싸서 React 컴포넌트가 쉽게 호출하도록 합니다.

```typescript
// 페이지 진입 시 — 첫 화면
fetchEmployeeList(limit=24, offset=0)
  → GET /api/employee/list

// 본부 선택 시
fetchByDivision("생산본부")
  → GET /api/employee/by-department?division=생산본부

// 팀 선택 시
fetchByDepartment("안전보건팀")
  → GET /api/employee/by-department?dept=안전보건팀

// 자연어 검색 시
searchEmployee("부장")
  → POST /api/employee/search { "query": "부장" }

// 조직도 그리기
fetchOrgTree()
  → GET /api/employee/org-tree
```

---

## 9. 부속 모듈·파일 가이드

### 9-1. 백엔드 (`features/search/`)

문서·정보 검색용 (현재 `ENABLE_FEATURE_A=false` 로 비활성):

| 파일 | 역할 | 한 줄 설명 |
|---|---|---|
| `indexer.py` | 문서 인덱싱 | 사내 문서 (PDF·DOCX 등) 를 검색 가능한 형태로 변환 |
| `searcher.py` | 하이브리드 검색 | BM25 (키워드) + 벡터 (의미) + RRF (점수 합산) |
| `intent_router.py` | 의도 분류 | "문서 찾아줘" vs "직원 검색" 자동 구분 |
| `metadata_extractor.py` | 메타 추출 | 질의에서 부품명·문서 종류·날짜 등 추출 |
| `ml_intent_classifier.py` | ML 분류기 | 키워드만으로 부족할 때 머신러닝 보완 |
| `summarizer.py` | 결과 요약 | LLM 으로 검색 결과 한 문단 요약 (SSE) |

### 9-2. 백엔드 (`features/search/employee/`)

직원 검색 — 현재 활성:

| 파일 | 역할 | 핵심 함수 |
|---|---|---|
| `database.py` | SQLite 직원 DB | `init_db()`, `query_employees()` |
| `search.py` | 검색 엔진 | `EmployeeSearchEngine.search(query)` — 자연어→SQL |
| `text_to_sql.py` | 자연어→SQL 변환 | "안전보건팀 부장" → `WHERE dept=? AND pos=?` |
| `semantic_search.py` | 의미 검색 | 동의어 (예: "안전팀" → "안전보건팀") 매칭 |
| `fts_index.py` | 전문 검색 인덱스 | SQLite FTS5 가상 테이블 |
| `formatter.py` | 결과 포맷팅 | 마크다운 카드/표 생성 |
| `org_chart.py` | 조직도 시각화 | Plotly Treemap / Sunburst (백엔드 사전 렌더링) |
| `analytics.py` | 검색 통계 | 인기 검색어, 부서별 검색 수 |
| `seed_data.py` | 더미 데이터 | 개발·시연용 가상 직원 생성 |
| `search_history.py` | 검색 이력 | 사용자별 최근 검색어 저장 |

### 9-3. 프론트엔드

| 파일 | 역할 |
|---|---|
| `frontend/src/routes/search.tsx` | 메인 검색 페이지 (690 LOC) |
| `frontend/src/components/employee/EmployeeDetailDrawer.tsx` | 직원 상세 정보 사이드 드로어 |
| `frontend/src/api/employee.ts` | 백엔드 API 호출 클라이언트 |
| `frontend/src/lib/visibility.ts` | 프론트 측 가시성 보조 (백엔드와 일관성) |
| `frontend/src/lib/employeeSort.ts` | 직급/이름/부서 정렬 로직 |
| `frontend/src/api/mock/seed/employees.ts` | 디자인 시스템 mock 데이터 (개발용) |
| `frontend/src/api/mock/seed/plants.ts` | 6 사업장 좌표 (지도 마커) |

### 9-4. 데이터·설정

| 파일 | 역할 |
|---|---|
| `data/employees.db` | SQLite 직원 DB (gitignored, bind-mount) |
| `data/audit.db` | 감사 이력 DB |
| `config.py` | DEPARTMENTS (27 부서), PLANTS (6 사업장), COMPANY_INFO 등 정적 정의 |
| `core/auth/visibility.py` | 가시성 결정 엔진 |
| `core/auth/rbac.py` | RBAC 역할 정의 |

---

## 10. 운영·확장 노트

### 10-1. ENABLE_FEATURE_A 플래그

현재 `.env` 또는 docker compose env 에서:
```
ENABLE_FEATURE_A=false
```
로 설정되어 있어 **하이브리드 문서 검색 (BM25+벡터+RRF) 은 비활성** 입니다. 직원 검색 (`/api/employee/...`) 은 별개로 항상 활성.

활성화하려면:
1. `.env.docker` 에 `ENABLE_FEATURE_A=true`
2. `data/vectorstore/` 에 ChromaDB 벡터 인덱스 빌드 필요
3. backend 재기동

### 10-2. 직원 데이터 갱신

`data/employees.db` 는 다음 방법으로 갱신 가능:
- **Direct SQL:** `sqlite3 data/employees.db "INSERT INTO employees (...) VALUES (...)"`
- **HR 관리자 UI:** `/admin` (현재 v3.5 — 사용자 등록 폼)
- **Bulk import:** `features/search/employee/seed_data.py` 의 패턴 참고하여 CSV/XLSX 가져오기 스크립트 작성

직원 추가 후 재기동 불필요 (매 요청마다 DB 직접 조회).

### 10-3. 성능 — 응답 시간 목표

| 작업 | 목표 | 현재 |
|---|---|---|
| `/api/employee/list?limit=24` | < 100ms | ~30-50ms |
| `/api/employee/by-department` | < 100ms | ~10-30ms |
| `/api/employee/org-tree` | < 200ms | ~50-100ms |
| `/api/employee/search` (자연어) | < 300ms | ~150-250ms |

### 10-4. 향후 확장

- [ ] **사진 업로드** — `photo_url` 컬럼 활성, GCS / Firebase Storage 연동
- [ ] **자유 텍스트 검색 (전 직원 대상 자기소개)** — `bio` 컬럼 추가 + FTS5 인덱스
- [ ] **조직도 인터랙티브 편집** — 드래그앤드롭 부서 이동 (HR 관리자)
- [ ] **검색 결과 LLM 요약** — `/api/search/summarize` 엔드포인트가 이미 있음 — `EmployeeSearchEngine` 와 통합

---

## 11. 자주 묻는 질문 (FAQ)

**Q1. 다른 사람의 휴대폰 번호가 안 보여요. 버그인가요?**
> 아닙니다. 가시성 정책 (§7) 에 따른 의도된 동작입니다. 같은 부서가 아니거나 본인이 관리자 권한이 없으면 휴대폰은 표시되지 않습니다. 필요 시 사내 전화 (내선) 를 이용해주세요.

**Q2. 퇴사자도 검색되나요?**
> 안 됩니다. `is_active=0` 인 직원은 자동으로 HIDDEN 처리되어 결과에서 제외됩니다. HR 관리자는 별도 endpoint 로 조회 가능합니다.

**Q3. 검색이 잘 안 돼요. "안전팀" 으로 검색하면 결과가 없어요.**
> 동의어 매칭이 부분 적용되어 있습니다. 정확한 부서명 ("안전보건팀") 으로 검색하거나 본부 드롭다운으로 필터하세요. 향후 `semantic_search.py` 강화 예정입니다.

**Q4. 본부·팀 목록을 어떻게 추가하나요?**
> 현재는 `config.py` 의 `DEPARTMENTS` 리스트를 직접 편집해야 합니다. 변경 후 backend 재기동 + 직원 DB 의 `department` 컬럼 갱신이 필요합니다. 향후 관리자 UI 에서 직접 편집 가능하게 할 예정.

**Q5. 검색 기록은 누가 봐요?**
> SYS_ADMIN 권한자만 `/api/admin/audit-log` 로 조회 가능합니다. 일반 사용자의 본인 최근 검색 내역은 `search_history.py` 에 저장되어 본인만 볼 수 있습니다.

**Q6. 데이터가 외부로 새는 건 아닌가요?**
> 검색과 권한 필터링은 backend 서버에서 처리됩니다. LLM 요약은 설정된 provider 로 필요한 검색 결과 메타데이터만 전달하는 구조이며, 운영 환경에서는 provider·리전·데이터 사용 정책을 별도 보안 검토 대상으로 둡니다. 직원 개인정보 원문은 요약 프롬프트에 보내지 않도록 설계했습니다.

**Q7. 모바일에서도 쓸 수 있나요?**
> Vite SPA 는 반응형으로 동작하고, 설비 현장 모드는 `/equipment/field` + `manifest.webmanifest` 로 홈 화면 추가가 가능합니다. 전체 앱의 full offline/service worker 적용은 별도 백로그입니다.

---

## 12. 용어집

| 용어 | 풀이 |
|---|---|
| **endpoint** | 서버가 외부에 제공하는 URL — 예: `/api/employee/search` |
| **API** | 프로그램끼리 데이터를 주고받는 약속된 통로 |
| **JWT** | "이 사람이 로그인한 사용자다" 를 증명하는 암호화된 신분증 토큰 |
| **RBAC** | 역할(SYS_ADMIN, HR_ADMIN 등) 에 따라 접근 권한이 다른 시스템 |
| **SQLite** | 가벼운 파일형 데이터베이스 — 엑셀처럼 한 파일에 여러 표(테이블) 저장 |
| **FTS** | Full-Text Search — 글 안에서 키워드를 빠르게 찾는 인덱스 |
| **BM25** | 키워드 기반 검색 점수 매김 알고리즘 — 구글 검색의 기초 |
| **벡터 검색** | 단어 의미를 숫자(벡터)로 바꿔서 비슷한 의미를 찾는 검색 |
| **RRF** | Reciprocal Rank Fusion — 여러 검색 결과를 합치는 방법 |
| **마스킹** | 정보를 가리는 것 — 예: `gildong@ajin.co.kr` → `***@ajin.co.kr` |
| **SSE** | Server-Sent Events — 서버가 응답을 한 번에 안 보내고 조금씩 흘려보내는 방식 (LLM 답변 실시간 표시용) |
| **Zustand** | React 앱에서 데이터를 한 곳에 모아 공유하는 라이브러리 |
| **Drawer** | 오른쪽에서 슬라이드해서 나오는 사이드 패널 |

---

## 13. 변경 이력 (Feature A 한정)

| 버전 | 날짜 | 주요 변경 |
|---|---|---|
| v1.0 | 2025-? | 직원 DB 도입, 자연어 검색 기본 |
| v1.6 | 2025-? | 해외법인 파견·어학 컬럼 추가 |
| v3.0 | 2026-? | RBAC + 가시성 3계층 도입 — 인증 필수 |
| v3.4 | 2026-04 | 본부/부서 selectbox 레이스 컨디션 수정 |
| v3.5 | 2026-04 | 인사 관리 탭 통합 (Tier 4: 7→6탭), CSV/XLSX 다운로드 |
| v3.6 | 2026-? | 페이지네이션 (`/employee/list`), 정렬 (`localStorage`), 상세 Drawer, "전체 보기" 토글 |
| **v4.0** | **2026-05-10** | **W1~W8 + F1~F5 라이브 배포** — 통합 검색, 문서 검색, 액션 4종, 이력·즐겨찾기, ⌘K 팔레트, 신입 온보딩 패널, W7 권한 강화, 검색 분석 대시보드, 디자인 시스템 v3.5 정렬, 마스킹 정책 완화, RightPanel 관리자 전용 |

상세 변경 이력은 [CHANGELOG.md](../CHANGELOG.md) 참조. v4.0 신규 기능의 상세 설명은 §15 참조.

---

## 14. 한눈 요약 카드

```
┌─────────────────────────────────────────────────────────────┐
│  기능 A — 사내 인원 / 문서 검색 + 통합 검색 (v4.0)          │
├─────────────────────────────────────────────────────────────┤
│  📌 누구·무슨 문서·어디서부터 시작할지 한 화면에서 해결    │
│                                                             │
│  💻 Backend     FastAPI + SQLite + ChromaDB + BM25 RRF      │
│  🖥  Frontend    React + Vite + TS + Zustand + Liquid Glass │
│  🔐 보안         JWT + RBAC 3계층 + F5 마스킹 완화 정책     │
│  🌐 Endpoint    OpenAPI 기준 — docs/API.md 자동 산정        │
│                  employee/search/directory 계열 API         │
│  ⌨️  단축키      ⌘K / Ctrl+K — 글로벌 명령 팔레트            │
│  🪟 UI 모드     통합 / 인사 / 문서 3탭 + 신입 온보딩 패널  │
│  💾 클라 캐시   검색 이력·즐겨찾기·최근 본 사람·문서       │
│                  + 피드백 (도움됨/부적합) localStorage      │
│  📊 데이터       650명 직원 · 27 부서 · 6 본부 · 6 사업장 │
│                  + ChromaDB 문서 인덱스 + BM25 코퍼스       │
│  📈 분석         관리자 대시보드 (Top 쿼리 / 0건 / CTR)     │
│  📁 코드          features/search/ (16+ 모듈, adapters/ 신규)│
│                  routes/search.tsx (~720 LOC)               │
│                  components/search/ 7개 신규                │
└─────────────────────────────────────────────────────────────┘
```

---

## 15. v4.0 신규 기능 상세 (W1~W8 + F1~F5)

기존 80% 구현도였던 기능 A를 100%로 끌어올린 v4.0 패치 묶음. 사용자 시연 피드백 5종을 반영해 라이브 배포까지 완료한 상태입니다.

### 15-1. W1 — 문서 본문 검색 UX

기존 인사 검색 전용 페이지에 **문서 탭** 추가. 백엔드 `/api/search/documents` (BM25 + Vector RRF) 를 호출해 8D 보고서 / ECN / 이메일 / 회의록 / PPAP 5개 카테고리에서 본문 검색.

- **신규 컴포넌트**: `components/search/DocumentResultCard.tsx`, `DocumentDetailDrawer.tsx`, `DocumentSearchPanel.tsx`
- **신규 API 클라이언트**: `api/search.ts` (extractTokens, buildSnippet 헬퍼 포함)
- **상세 드로어 액션 3종**: 초안 작성으로 이동 (Feature B 브릿지) / 챗봇으로 질문 (Feature C 브릿지) / 본문 클립보드 복사
- 키워드 하이라이트 + 메타(부품명·작성일·작성자·부서) 표시 + RRF 스코어 배지

### 15-2. W2 — 통합 검색 (사람 + 문서 + SOP)

단일 검색 바로 3개 자료원 동시 fan-out. 의도 추정 배지(인사/문서/SOP/복합) + 결과 섹션별 상세 탭으로 점프.

- **신규 컴포넌트**: `components/search/UnifiedSearchPanel.tsx`
- 클라이언트 측 `Promise.allSettled` 로 `/employee/search`, `/search/documents`, `/sop/list` 병렬 호출 → 부분 실패 허용
- 의도 분류 휴리스틱 (한국어 이름 정규식 + 부서/직급 키워드 + 문서 타입 키워드)

### 15-3. W3 — 검색 결과 액션 4종

`usePersonActions()` 훅으로 통합 — 메일 / 멘션 클립보드 복사 / 초안 작성 / 챗봇 문의.

- **신규 훅**: `hooks/usePersonActions.ts`
- **EmployeeDetailDrawer 갱신**: `<Button>` UI 프리미티브를 `lg-btn` 캐노니컬 클래스로 교체, 즐겨찾기 토글 추가
- 멘션 형식: `@이름 직급 (팀) <email>` — 클립보드 복사

### 15-4. W4 — 검색 이력 / 즐겨찾기 / 최근 본 사람·문서

localStorage 기반 4분할 위젯. 시연 첫 화면이 비어 보이지 않게 + 매일 동선 단축.

- **신규 라이브러리**: `lib/searchHistory.ts` (CRUD + 분석 집계 + subscribeChanges)
- **신규 컴포넌트**: `components/search/HistoryFavoritesPanel.tsx`
- 영속 항목: 최근 검색(12) / 즐겨찾기 사람(24) / 최근 본 사람(8) / 최근 본 문서(8) / 검색 분석 로그(200) / 피드백(200)

### 15-5. W5 — ⌘K 글로벌 명령 팔레트

어느 페이지에서든 `⌘K` (macOS) / `Ctrl+K` 로 호출. 사람·문서 디바운스 검색 + 페이지 점프 + 키보드 네비.

- **신규 훅**: `hooks/useHotkeys.ts`
- **신규 컴포넌트**: `components/search/CommandPalette.tsx`
- **마운트 위치**: `routes/_shell.tsx` 글로벌
- 결과 클릭 시 `pushRecentQuery` 자동 + URL 쿼리 파라미터 (`?tab=people|documents`) 로 탭 전환

### 15-6. W6 — 신입 온보딩 사이드 패널

`role_level <= 2` 신입에게만 노출. 사수 자동 추정 + 첫 주 체크리스트 + 부서 FAQ + 용어 사전 진입.

- **신규 컴포넌트**: `components/search/OnboardingSidePanel.tsx`
- 사수 자동 추정: `fetchByDepartment(user.department)` → 부장/차장/과장/팀장/책임 우선 한 명
- 체크리스트 5종 (SOP 8종 / 조직도 / MSDS / 용어 30개 / 첫 초안)
- 부서 FAQ Top 5 — 정적 데이터(품질보증팀/생산기술팀/default 분기)

### 15-7. W7 — 권한 기반 강화 검색 + ERP 어댑터 스텁

ERP/HRIS 인터페이스 lock-in. 출장 이력 / 직속 부하 / 결재 현황 권한 분기 노출.

- **신규 백엔드 모듈**: `features/search/adapters/erp_adapter.py` (ABC + MockErpAdapter)
- **신규 라우트**: `GET /api/employee/{id}/extras`
- **신규 프론트**: `api/employeeExtras.ts`, `components/employee/EmployeeExtrasSection.tsx`
- 권한: SYS_ADMIN/HR_ADMIN(L5) → FULL · 같은 부서 → PARTIAL · 그 외 → DENIED
- **버그 픽스 (2026-05-10)**: 초기 구현에서 `UserContext.role_level` 필드를 참조했으나 실제 dataclass에는 `role` 문자열만 존재 → 모든 사용자가 default 1로 평가되어 SYS_ADMIN도 RESTRICTED 표시. 라우터 핸들러에서 `role` → `ROLE_LEVELS` dict 매핑으로 정정 (revision `00161-rig` 라이브).

### 15-8. W8 — 검색 분석 대시보드 + 품질 피드백

관리자(L3+) 화면에 검색 분석 탭 추가. Top 10 쿼리 / 0건 쿼리 / 피드백 좋아요율 추적.

- **신규 컴포넌트**: `components/admin/tabs/SearchAnalyticsTab.tsx`
- 데이터 소스: 클라이언트 localStorage (W4 + W8 누적). 추후 `audit.db` 집계로 전환 가능 — 데이터 모델 동일.
- DocumentResultCard 하단에 ThumbsUp/ThumbsDown 피드백 버튼 → `pushFeedback(query, docId, helpful)`

---

## 16. v4.0 사용자 피드백 수정 (F1~F5)

W1~W8 1차 배포 후 사용자 시연에서 드러난 5개 마찰점을 코드 레벨에서 수정해 라이브 적용한 패치.

### 16-1. F1 — Hero 폰트 크기 위계 정렬

전반적으로 글자가 크게 느껴진다는 지적. 디자인 시스템 v3.5 README 권장값(page title 28px)에 정렬.

- 변경: `lg-display` 56→28px, `lg-sub` 19→16px, `lg-h2` 26→22px
- 위치: `frontend/src/styles/lg-theme.css:950-967`
- 단일 파일 수정으로 dashboard / search / draft / chat / compliance / equipment 전 페이지 일괄 반영

### 16-2. F2 — 한국어 어절 단위 줄나눔

"한눈/에" 처럼 어절 중간 끊김 가독성 저하. CSS `word-break: keep-all` 적용.

- 변경: `.lg-page { word-break: keep-all; overflow-wrap: break-word; }`
- 영문 토큰(URL/email)은 컨테이너 경계 분리 허용 (`.lg-email a`, `.mono` 에 `break-all` 보존)
- 위치: `frontend/src/styles/lg-theme.css:947-949`

### 16-3. F3 — 이름 검색 BUG (백엔드 미호출)

본부/팀 미선택 + 이름만 입력 시 0건 표시. 원인은 첫 마운트 24명 풀에서만 클라이언트 필터를 돌리는 구조 — `/api/employee/search` 자연어 라우트가 호출 안 됨.

- 수정: `routes/search.tsx` useEffect 분기에 `query.trim().length >= 1` 조건 추가 → `searchEmployees(q)` 호출 + 250ms 디바운스
- 자연어 검색기는 부서 약어 / 직급 동의어 / 본부 선택 무관 매칭을 백엔드가 처리 (v3.6 강화됨)
- 검증: "최동현" 입력 → 1건 노출 ✓

### 16-4. F4 — 본부 선택해야만 팀 선택 가능 제약 해제

제조업 1차 협력사 환경에서 "이 팀이 어느 본부 소속인지" 모르는 시나리오 빈번. 본부 → 팀 드릴다운 강제를 풀고, 팀 검색 자동완성 추가.

- 수정 1: 팀 selectbox `disabled={hq === ALL}` 제거. 본부 미선택 시 30개 팀을 본부별 `<optgroup>` 으로 펼침
- 수정 2: 신규 lg-field "팀 빠른 검색" — `<datalist id="ajin-team-options">` 자동완성 input
- 수정 3: 팀 선택 시 `teamToHqMap` 으로 본부 자동 동기화 (`handleTeamChange`)

### 16-5. F5 — 인사 마스킹 정책 완화

내선번호·이메일·휴대폰 모두 PARTIAL 마스킹이 협업에 마찰. 사용자 정책: 사내 협업 자산은 공개, 휴대폰만 마스킹.

- 수정 (프론트): `lib/visibility.ts` — `maskEmail` PARTIAL 시 원문 반환, `extMasked` 항상 `#${ext}` 노출
- 수정 (백엔드): `core/auth/visibility.py` — `FIELD_VISIBILITY` 에서 `email` 을 `full_only` → `partial` 로 이동, `filter_employee_fields` 에서 이메일 마스킹 분기 제거
- 수정 (UI): `EmployeeDetailDrawer` 안내 문구 "휴대전화만 일부 마스킹" 으로 정정, 메일 액션 가드를 `e.email` 존재 여부로 단순화

---

## 17. v4.0 운영 변경 (인프라 / 라이브)

### 17-1. RightPanel SYSTEM ANALYTICS 관리자 전용

신입 / 현직자에게 GPU·LATENCY·QPS 등 시스템 메트릭은 불필요. SYS_ADMIN(L5)에게만 노출.

- 수정: `routes/_shell.tsx` — `isAdmin = (user?.role_level ?? 0) >= 5` 조건으로 패널 마운트 자체 비조건부 차단 + main 컬럼이 전체 폭 사용
- 수정: `components/shell/TopBar.tsx` — `HIDE`/`SYS` 토글 버튼도 관리자만 노출

### 17-2. LLM 라우터 정상화

라이브 시연 중 TopBar `LLM OFFLINE` 표시 발견. 3중 원인:

1. **Cloudflare TryCloudflare 서버 장애** (error code 1101) — 우리 통제 밖
2. **트래픽 핀 락업** — 초기 deploy 시 `--to-revisions=00155-sov=100` 핀 → env 업데이트가 새 revision을 만들어도 트래픽 안 옮겨감 → `--to-latest` 로 자동 추적 모드 전환
3. **`LLM_ROUTER_FALLBACK_ENABLED=false`** — Ollama 실패 시 Gemini fallback 비활성. 캐노니컬 기본값 `true` 로 복귀

조치:
- `OLLAMA_BASE_URL` ngrok URL (`phasic-cammy-chorial.ngrok-free.dev`) 로 우회
- `LLM_ROUTER_PRIMARY=gemini`, `LLM_ROUTER_FALLBACK_ENABLED=true` 로 라우팅 정상화
- 결과: 관리자 인증 후 `/api/health/llm-status` → `🟢 Ollama OK (7 모델) · 🟢 Gemini 키 OK · 기능 A~F 매핑 6/6`

### 17-3. 디자인 시스템 v3.5 풀 정렬

모든 신규 컴포넌트가 `lg-*` 캐노니컬 클래스 + 라운드 토큰(2/12/16/18/24/999px) + Liquid Glass 모달 + 영문 eyebrow + 한글 본문 페어 + lucide 아이콘만 사용 (이모지 0건). 자세한 토큰은 `uiux/AJIN AI Assistant Design System_v2/colors_and_type.css`.

---

문서 작성: 2026-05-09 | 최종 갱신: 2026-05-10 (v4.0 라이브 배포 완료) | 본 문서는 향후 feature 변경 시 함께 갱신해주세요.
