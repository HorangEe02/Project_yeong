# 기능 C — AI 업무 도우미 / 온보딩 챗봇 (Onboarding · Chat)

> **이 문서는 누구를 위한 것인가요?**
> 개발자가 아닌 분 (운영자·기획자·교육 담당자) 도 끝까지 읽을 수 있도록 작성했습니다.
> 어려운 용어는 처음 등장할 때 _기울임_ 으로 표시하고 옆에 짧은 설명을 붙입니다.

---

## 1. 한 줄 요약

**"신입사원 6개월 동안 사수에게 묻기 어려운 질문을 24시간 답해주는 AI 동료"입니다.**

신입사원이 "8D Report 가 뭐예요?" 같은 기초 질문부터 "산안법 38조 의무는?" 같은 법규 질문까지 자유롭게 던지면, 챗봇이 (1) 사내 SOP 8종에서 매칭, (2) 협업 시나리오 5종에서 키워드 매칭, (3) 인-챗 액션 8종으로 즉시 카드 응답, (4) LLM 으로 풀 답변 — 4 단계로 나눠서 처리합니다. **부서·직급에 맞춰 응답이 달라지고**, 답변 후 👍/👎 피드백을 받아 운영자가 품질 개선에 활용합니다.

---

## 2. 누가, 언제 쓰는가?

| 사용자 | 시나리오 | 기능 C 가 해주는 일 |
|---|---|---|
| **신입사원 (입사 1-6개월)** | "PPAP Level 3 어떻게 진행?" 사수가 바쁨 | SOP-PPAP 단계별 가이드 + 5문제 퀴즈로 학습 검증 |
| **부서 이동자** | 품질팀에서 생산기술팀으로 이동, 4M 변경 관리 처음 | curriculum.py 가 부서별 학습 경로 생성 — proactive_engine 이 아직 안 본 항목 추천 |
| **임시 협업자** | 다른 부서 과제 — 안전보건팀 점검 대비 | "안전 점검" 키워드 → 협업 시나리오 매칭 → 즉시 응답 카드 |
| **멘토** | 신입한테 SOP 알려줘야 하는데 매번 똑같은 설명 | SOP/list 공유 + 챗봇이 1:1 대응 — 멘토는 검증·피드백만 |
| **비대면 근무자** | 사무실 동료에게 직접 못 묻는 상황 | 24시간 챗봇 — Markdown + 출처·신뢰도 표시 |

---

## 3. 전체 작동 흐름 (그림으로)

신입사원이 "8D 클레임 대응 어떻게 하나요?" 라고 묻는 경우:

```
[브라우저]                                            [서버]
사용자 입력
"8D 클레임 대응"
        │
        │ POST /api/onboarding/chat (SSE)
        │ { query, department, history, force_provider }
        ▼
─────────────── 인터넷 / 사내망 ───────────────
                                                FastAPI
                                                    │
                                                    │ 1) 부서 컨텍스트 RBAC 체크
                                                    │   role_level=1 → 자기 부서만
                                                    │   role_level=3 → 본부 내
                                                    │   role_level=4 → 전사
                                                    ▼
                                                Phase 4: 2단계 응답 엔진
                                                (onboarding_bot.py)
                                                    │
                                                    │ ─── 1단계: 룰·매칭 (빠름, 0.1초)
                                                    │
                                                    ├─ glossary_matcher
                                                    │   "8D" 용어사전 hit?
                                                    │
                                                    ├─ sop_guide.find_sop_by_query
                                                    │   "8D" → SOP-8D 매칭!
                                                    │   → SOP 카드 즉시 반환
                                                    │
                                                    ├─ collaboration_guide.match_collaboration
                                                    │   ["8D","클레임"] → 협업 시나리오 매칭!
                                                    │
                                                    └─ work_actions.match_action
                                                        regulation_qa / employee_search /
                                                        spc_status / 등 8종
                                                        → action_handlers 로 디스패치
                                                    │
                                                    │ ─── 2단계: LLM (룰 미스 시, 1-3초)
                                                    │
                                                    ▼
                                                LLMRouter (CHAT_KOREAN 모드)
                                                    │
                                                    │ 운영 기본: Ollama primary
                                                    │ Gemini는 명시 설정 시 fallback/비교 검증용
                                                    │ 시스템 프롬프트: onboarding_system.txt
                                                    │ + 부서별 맞춤 (department_router)
                                                    │ + 멀티턴 메모리 (conversation_memory)
                                                    ▼
                                                SSE 토큰 stream
   ◀────────────────────────────────────────────────┘
4) 화면에 마크다운 실시간 렌더링
   + 메타 (provider, model, latency)
   + 액션 카드 (있으면)
   + 출처·신뢰도
        │
        │ 답변 후 👍/👎 클릭
        ▼
   POST /api/onboarding/feedback
        │
        ▼
                                                feedback_db (SQLite)
                                                    chat_feedback 테이블에 누적
                                                    운영자 dashboard 에서 분석
```

핵심 5단계: **부서 RBAC → 룰 매칭 (4종) → LLM 폴백 → SSE 스트림 → 피드백 누적**.

---

## 4. 기술 스택

### 4-1. 백엔드 (Backend, "서버 쪽 두뇌")

| 카테고리 | 기술 | 역할 |
|---|---|---|
| 언어 | **Python 3.11+** | 서버 코드 |
| 웹 프레임워크 | **FastAPI** | `/api/onboarding/...` endpoint — 현재 수치는 [API 인덱스](API.md) 기준 |
| 스트리밍 | **SSE** _(Server-Sent Events — 답변을 한 글자씩 흘려보내는 방식)_ | LLM 응답 실시간 출력 |
| LLM 라우터 | **LLMRouter** (자체) | `/api/onboarding/chat`은 `LLMMode.CHAT_KOREAN`으로 스트리밍하며 운영 기본 primary는 Ollama |
| 로컬 LLM | **Ollama** (qwen3.5:9b · exaone3.5 · gemma4) | 사내 GPU 또는 host Metal |
| 클라우드 LLM | **Google Gemini** (옵션) | 운영자가 명시적으로 허용한 데모/Canary 또는 fallback 검증 경로 |
| 데이터베이스 | **SQLite** | `data/feedback.db` — 대화 피드백 누적 |
| 룰 매칭 | **자체 모듈** | sop_guide / collaboration_guide / glossary_matcher / work_actions |
| 메모리 | **ConversationMemory** | 긴 대화의 요약 기반 컨텍스트 압축 |
| 인증 | **JWT (필수)** | `get_current_user` — `/api/onboarding/...` 전체 로그인 사용자 전용 |

### 4-2. 프론트엔드 (Frontend, "사용자가 보는 화면")

| 카테고리 | 기술 | 역할 |
|---|---|---|
| 언어 | **TypeScript** | 화면 코드 |
| UI | **React** + **Vite** | SPA |
| 상태 관리 | **Zustand** _(앱 데이터 보관소)_ | `useUIStore`, `useAuthStore`, `useToastStore` |
| SSE 훅 | **`useSSE` 자체 훅** | 토큰 stream + 자동 재연결 |
| 마크다운 | **MarkdownRenderer** | LLM 응답 표·목록·코드 블록 렌더링 |
| 모델 셀렉터 | **ModelSelect 컴포넌트** | 4 family (qwen/gemma/gemini/exaone) |
| 액션 카드 | **ActionCardRouter** | 8종 액션 결과 카드 라우터 |
| 영속화 | **localStorage** | `ajin-chat-force-provider` (마지막 모델 선택) + 대화 세션 |
| 다운로드 | **DownloadActions** | 대화 내보내기 (TXT/MD/PDF) |

### 4-3. 인프라 (운영 환경)

| 항목 | 값 |
|---|---|
| 컨테이너 | Docker (multi-stage) |
| SSE 버퍼링 회피 | 16KB 패딩 + heartbeat 5초 |
| 로깅 | Python logging + audit.db (감사 로깅) |
| 부서 RBAC | `core/auth/rbac.py` 와 정합 |

### 4-4. 보안

- **JWT 필수** — `/api/onboarding/...` 전체 endpoint 는 로그인 필요. 부서/RBAC 컨텍스트는 항상 인증 사용자 기준으로 계산
- **부서 컨텍스트 RBAC** — `MANAGER_ROLE_LEVEL=3` (본부 내 부서 변경), `EXECUTIVE_ROLE_LEVEL=4` (전사 부서 변경)
- **출처 강제** — `/api/onboarding/chat` SSE 는 먼저 `sources` 이벤트를 보내고, 최종 `done.metadata.citation_status` 로 `verified/corrected/model_only/failed` 를 반환. 서버가 `[출처:<citation_id>]` 누락을 보정
- **Analyzer 봉인 기본값** — `/api/onboarding/vision/*`, `/api/onboarding/document/*` 부서별 analyzer 는 `FEATURE_C_ANALYZERS_ENABLED=true` 일 때만 동작하며, 기본값은 `403 analyzer_disabled`
- **감사 로깅** — 모든 chat 요청은 누가·언제·어떤 query·어떤 모델 응답인지 기록
- **입력 살균** — `sanitize_llm_input()` — 프롬프트 인젝션 방지

### 4-5. Release gate

- Feature C release gate는 `make feature-c-release-check`로 실행합니다.
- 자동 gate는 OpenAPI 기준 39개 endpoint, LLM 비용 posture, fallback/circuit/metrics, Feature C flag wiring, quick question/SOP/collaboration content schema를 확인합니다.
- `GEMINI_API_KEY`가 존재하고 `LLM_ROUTER_PRIMARY=ollama`가 아니면 release blocker입니다. 유료 LLM primary 또는 `FEATURE_C_COMPARE_MODE=true`는 명시적인 `--allow-paid-llm` 검증 run에서만 warning으로 낮출 수 있습니다.
- 부서별 콘텐츠 현업 signoff 파일이 없으면 release blocker입니다. JSON/Markdown schema, citation, reviewed_at/effective_date/version/status 누락, 링크 깨짐은 자동 gate fail로 처리합니다.

---

## 5. 백엔드 Endpoint 목록

현재 endpoint 총수는 FastAPI OpenAPI 산출물인 [API 인덱스](API.md)를 기준으로 확인합니다.

| 메서드 | 경로 | 용도 | 응답 |
|---|---|---|---|
| `POST` | `/api/onboarding/chat` | **(주력)** SSE 스트리밍 챗 | 토큰 stream + 메타 |
| `GET` | `/api/onboarding/health` | 의존성 진단 | `{ok, services: [...]}` |
| `GET` | `/api/onboarding/quick-questions` | 부서·직급별 빠른 질문 6개 | `[{query, label}]` |
| `POST` | `/api/onboarding/chat/vision` | 이미지 분석 챗 (도면·차트 OCR) | `OnboardingChatResponse` |
| `POST` | `/api/onboarding/upload` | 파일 업로드 + 텍스트 추출 | `{filename, text, chars}` |
| `GET` | `/api/onboarding/sop/list` | SOP 8종 목록 | `SopListResponse` |
| `GET` | `/api/onboarding/sop/{sop_id}` | SOP 상세 (단계별) | `SopDetailResponse` |
| `GET` | `/api/onboarding/sop/{sop_id}/quiz` | SOP 학습 검증 퀴즈 5문제 | `SopQuizResponse` |
| `POST` | `/api/onboarding/scenarios/match` | 협업 시나리오 5종 키워드 매칭 | `ScenarioMatchResponse` |
| `POST` | `/api/onboarding/actions/match` | 인-챗 액션 8종 매칭 | `ActionMatchResponse` |
| `POST` | `/api/onboarding/download` | 대화 내보내기 (TXT/MD/PDF) | 바이너리 |

> Access: 위 `/api/onboarding/*` 전체는 로그인 필요. `/vision/*`·`/document/*` analyzer는 추가로 `FEATURE_C_ANALYZERS_ENABLED=true`가 필요합니다.

### 5-1. SSE 응답 예시 — `/api/onboarding/chat`

```
data: {"type":"sources","metadata":{"sources":[{"citation_id":"SOP-8D","source_type":"sop"}],"citation_status":"verified"}}

data: {"type":"token","content":"## SOP-8D — 8D Report 작성 가이드 [출처:SOP-8D]"}

event: token
data: \n\n**1단계: 팀 구성**

...

data: {"type":"done","metadata":{"ok":true,"latency_ms":124,"citation_status":"verified"}}
```

룰 매칭 시 **즉시 응답** (provider=rule). LLM 폴백 시 release 기본은 **provider=ollama**이며, Gemini는 운영자가 명시적으로 허용한 fallback/비교 검증에서만 사용합니다.

### 5-2. JSON 응답 예시 — `/api/onboarding/sop/list`

```json
{
  "items": [
    {"sop_id":"SOP-001","title":"프레스 금형 교체 절차","department":"생산기술팀","category":"공정","steps_count":5},
    {"sop_id":"SOP-PPAP","title":"PPAP(생산부품승인절차) 진행","department":"품질보증팀","category":"품질","steps_count":5},
    ...
  ],
  "total": 8
}
```

---

## 6. 데이터베이스 스키마

대화 피드백은 `data/feedback.db` (SQLite) 의 **1 테이블** 에 저장.

### 6-1. chat_feedback 테이블

| 컬럼 | 타입 | 설명 | 예시 |
|---|---|---|---|
| `id` | INTEGER (PK, AUTOINCREMENT) | 피드백 ID | `1024` |
| `session_id` | TEXT | 대화 세션 ID | `sess-7f3a` |
| `query` | TEXT (필수) | 사용자 질문 | `8D 클레임 대응` |
| `response_preview` | TEXT | 답변 첫 200자 미리보기 | `## SOP-8D...` |
| `intent` | TEXT | 분류된 의도 | `sop_guide`, `regulation_qa` |
| `is_positive` | INTEGER (필수) | 👍=1 / 👎=0 | `1` |
| `user_department` | TEXT | 피드백 준 사용자 부서 | `품질보증팀` |
| `user_position` | TEXT | 피드백 준 사용자 직급 | `사원` |
| `comment` | TEXT | 자유 입력 코멘트 | ``너무 길어요`` |
| `created_at` | TEXT | 피드백 시각 | `2026-05-10 09:23:11` |

### 6-2. ER 다이어그램 (간단)

```
┌───────────────────────────────────────┐
│   chat_feedback (1 테이블)            │
│  ───────────────────────────────────  │
│  id (PK)                              │
│  session_id, query, response_preview  │
│  intent, is_positive (1/0)            │
│  user_department, user_position       │
│  comment, created_at                  │
└───────────────────────────────────────┘
```

> **왜 이 정보를 저장하나요?**
> 1. **품질 개선** — 👎 받은 답변을 운영자가 검토해서 룰·프롬프트 보강
> 2. **사용 통계** — 어떤 부서가 어떤 의도로 자주 쓰는지 파악
> 3. **선제적 가이드** — 자주 묻는 질문 → quick_questions 우선 노출
> 4. **운영 KPI** — 만족도 (👍 / 전체) 비율 추적

### 6-3. 인덱스

```sql
CREATE INDEX idx_fb_created ON chat_feedback(created_at);
CREATE INDEX idx_fb_intent  ON chat_feedback(intent);
```
- 첫 번째 — "최근 24시간 피드백" 빠르게 조회
- 두 번째 — "regulation_qa 의도의 만족도" 빠르게 집계

---

## 7. SOP 8종 + 협업 시나리오 5종 + 인-챗 액션 8종

기능 C 의 핵심 컨텐츠. 각각 룰 기반 매칭으로 **LLM 호출 없이** 즉시 응답.

### 7-1. SOP 8종 (`sop_guide.py:SOP_DATABASE`)

| ID | 제목 | 담당 부서 | 카테고리 | 단계 |
|---|---|---|---|---|
| **SOP-001** | 프레스 금형 교체 절차 | 생산기술팀 | 공정 | 5단계 |
| **SOP-002** | 용접 너겟 품질 검사 절차 | 품질보증팀 | 품질 | 5단계 |
| **SOP-003** | EWP 하우징 CNC 가공 절차 | 생산기술팀 | 공정 | 5단계 |
| **SOP-PPAP** | PPAP (생산부품승인절차) 진행 | 품질보증팀 | 품질 | 5단계 |
| **SOP-8D** | 8D Report 작성 (고객 클레임 대응) | 품질보증팀 | 품질 | 5단계 |
| **SOP-ECN** | ECN (설계변경통보) 접수 및 대응 | 부품개발팀 | 설계 | 3단계 |
| **SOP-PRESS-TRIAL** | 프레스 트라이 (시타) 참관 준비 | 생산기술팀 | 공정 | 4단계 |
| **SOP-MOLD-RECEIVE** | 신규 금형 입고 및 검수 | 생산기술팀 | 공정 | 3단계 |

각 SOP 는 다음 필드를 포함:
- `step_number` — 단계 번호
- `title` — 단계 제목
- `description` — 상세 설명
- `checklist` — 체크리스트 항목
- `caution` — 주의사항
- `related_terms` — 관련 용어 (glossary 연결)

### 7-2. 협업 시나리오 5종 (`collaboration_guide.py:COLLABORATION_SCENARIOS`)

다른 부서 과제 시 **즉시 응답 카드** — LLM 호출 없이 키워드 매칭만.

| 시나리오 | trigger 키워드 | 용도 |
|---|---|---|
| **8D 대응** | 8D, 8d, 클레임, 불량 보고, 시정 조치, 클레임 대응 | 고객 불만 8단계 처리 흐름 |
| **ECN 변경** | ECN, 설계변경, 도면 변경, 리비전 변경 | 설계 변경 통보 처리 흐름 |
| **SPC 분석** | SPC, 공정 능력, Cpk, 관리도, 측정 데이터 | 통계적 공정 관리 분석 흐름 |
| **PPAP 승인** | PPAP, 승인 서류, 초도품, 양산 승인 | 양산 부품 승인 절차 |
| **안전 점검** | 안전 점검, 안전 감사, 안보팀, 점검 대비, 산안법 | 산업안전 정기 점검 대응 |

### 7-3. 인-챗 액션 8종 (`work_actions.py:ACTION_PATTERNS`)

자연어 입력에서 의도를 추출 → 백엔드 함수로 디스패치 → 카드 응답.

| 액션 ID | 핸들러 (`action_handlers.py`) | 트리거 예시 | 응답 |
|---|---|---|---|
| `error_code` | `handle_error_lookup()` | "프레스 에러 E102" | 에러 코드 + 원인 + 조치 카드 |
| `employee_search` | `handle_employee_search()` | "안전보건팀 부장" | 직원 카드 (Feature A 연동) |
| `spc_status` | (Feature F 연동) | "EWP 라인 SPC 현황" | 공정 신호등 + Nelson 위반 |
| `compose_email` | `handle_draft_compose()` | "OEM 이메일 작성" | Feature B 초안 생성 트리거 |
| `compose_document` | `handle_draft_compose()` | "8D Report 작성" | Feature B 초안 생성 트리거 |
| `regulation_status` | `handle_compliance_lookup()` | "산안법 현황" | Feature D 시나리오 카드 |
| `regulation_qa` | `handle_regulation_qa()` | "산안법 38조" | Feature D RAG 답변 (Phase 2 LLM 라우팅) |
| `document_search` | `handle_document_search()` | "PPAP 양식 찾아줘" | Feature A 검색 결과 |

---

## 8. 2단계 응답 엔진 (Phase 4 onboarding_bot)

기능 C 의 본질. **빠르게 정확히 → 못 하면 LLM 으로** 흐름.

### 8-1. 1단계 (Rule, ~100ms)

순서대로 시도 → 첫 hit 에서 즉시 응답:
1. `glossary_matcher` — 용어사전 정확 매칭 (예: "PPAP" → 정의)
2. `sop_guide.find_sop_by_query` — SOP 8종 키워드 매칭
3. `collaboration_guide.match_collaboration` — 협업 시나리오 5종
4. `work_actions.match_action` (우선순위 순)
   - regulation_qa > regulation_status > compliance > employee_search > sop_step

### 8-2. 2단계 (LLM, 1-3s)

1단계 모두 miss → LLM 호출:
- 시스템 프롬프트: `features/onboarding/prompts/onboarding_system.txt`
- 부서별 맞춤: `department_router.py` 가 부서 컨텍스트 추가
- 멀티턴: `conversation_manager.py` 가 직전 N개 메시지 + 요약 메모리 첨부
- 모델: 사용자 선택 (qwen/gemma/gemini/exaone) 또는 LLMRouter 자동

### 8-3. 응답 메타

응답 헤더에 다음 표시 (사용자가 신뢰도 판단):
- **src** — 응답 출처 (`SOP_GUIDE`, `COLLAB`, `LLM-QWEN3.5`, `EMPLOYEE_DB` 등)
- **conf** — 신뢰도 (`95%` (룰), `—` (LLM))
- **latency** — 응답 시간 (`124ms · 41 t/s`)
- **provider** / **model** — 풍부한 메타 (v3.3 Phase A)

---

## 9. 부서별 맞춤 라우팅 (`department_router.py`)

같은 질문이라도 **사용자 부서** 에 따라 응답이 달라집니다.

### 9-1. 예시 — "8D 어떻게 해?"

| 사용자 부서 | 응답 강조점 |
|---|---|
| **품질보증팀** | 8D 8단계 정식 절차 + FMEA 연계 |
| **생산기술팀** | 4단계 (Containment Action) 의 공정 격리 + 임시 조치 |
| **부품개발팀** | 5단계 (Root Cause) 의 설계 측면 검토 |
| **영업팀** | 고객 응답 timeline + 6단계 (Permanent Action) |

### 9-2. 구현

`department_router.py` 가 시스템 프롬프트에 부서 정보를 주입:
```
당신은 아진산업 사내 AI 도우미입니다.
사용자 부서: {department}
사용자 직급: {position}

위 부서 관점에서 답변하세요. 다른 부서의 책임은 간단히 언급만 하고,
사용자 부서가 직접 수행해야 할 작업을 중심으로 설명하세요.
```

---

## 10. 프론트엔드 컴포넌트 트리

### 10-1. 페이지 구조

```
/chat 라우트 (frontend/src/routes/chat.tsx)
│
├─ <_shell>
│  ├─ <TopBar>
│  └─ <Sidebar>
│
└─ <Chat> (메인 페이지)
   │
   ├─ 헤더
   │  ├─ <ChatModeToggle>     — 교육 / 업무 (2 모드)
   │  ├─ <DepartmentSelector> — 부서 선택 (RBAC: MANAGER 본부 내 / EXEC 전사)
   │  └─ <ModelSelect>        — Ollama / Gemini / 모델명 (localStorage 영속)
   │
   ├─ 좌측 채팅 영역
   │  ├─ <MessageList>
   │  │  ├─ <UserMessage>     — 사용자 입력
   │  │  └─ <AssistantMessage>
   │  │     ├─ <MarkdownRenderer>  — 본문 렌더링
   │  │     ├─ <ActionCardRouter>  — 8종 액션 카드
   │  │     ├─ <MetaBar>           — src / conf / latency
   │  │     ├─ <FeedbackActions>   — 👍/👎 + 코멘트
   │  │     └─ <DownloadActions>   — TXT/MD/PDF 내보내기
   │  ├─ <QuickQuestions>     — 부서별 6개 추천 질문 (대화 시작 시)
   │  └─ <InputBar>           — 자유 입력 textarea + 첨부 + 전송
   │
   └─ 우측 SidePanel (3종 선택)
      ├─ "sop"     — SOP 8종 목록 + 단계별 상세 + 5문제 퀴즈
      ├─ "collab"  — 협업 시나리오 5종 카드
      └─ "quiz"    — 부서별 학습 진행률 + 미완료 항목 (proactive_engine)
```

### 10-2. 상태 관리

| 데이터 | 위치 | 영속성 |
|---|---|---|
| 대화 메시지 list | `chatSession.ts` | localStorage (브라우저별) |
| 모델 선택 | `loadForceProvider()` | localStorage `ajin-chat-force-provider` |
| 사용자 정보 | `useAuthStore` (Zustand) | localStorage |
| 채팅 모드 / 부서 | useState | 페이지 이탈 시 리셋 |
| SOP 목록 / 상세 | useState + `fetchSopList` | API 호출마다 갱신 |

### 10-3. API 호출 흐름

```typescript
// 페이지 진입
fetchSopList()              → GET  /api/onboarding/sop/list
fetchUserScenarios()         → GET  /api/onboarding/quick-questions

// 대화
buildChatUrl(...)            → POST /api/onboarding/chat (SSE)
useSSE(...)                  → 토큰 stream 처리

// SOP 사이드 패널
fetchSopDetail(sop_id)       → GET  /api/onboarding/sop/{sop_id}
fetchSopQuiz(sop_id)         → GET  /api/onboarding/sop/{sop_id}/quiz

// 피드백
submitFeedback(...)           → POST /api/onboarding/feedback (👍/👎)

// 다운로드
downloadConversation(format) → POST /api/onboarding/download
```

---

## 11. 부속 모듈 가이드 (17 모듈)

### 11-1. 핵심 봇

| 파일 | 역할 |
|---|---|
| `__init__.py` | 통합 진입점 + DI |
| `onboarding_bot.py` | **Phase 4 — 2단계 응답 엔진 (룰 → LLM)** |
| `stream_response.py` | SSE 토큰 stream 헬퍼 |

### 11-2. 대화 관리

| 파일 | 역할 |
|---|---|
| `conversation_manager.py` | **Phase 6 — 멀티턴 대화 + 관련 용어 추천** |
| `conversation_memory.py` | 긴 대화의 요약 기반 컨텍스트 압축 |
| `context_optimizer.py` | LLM 토큰 한도에 맞춰 history 컷 |

### 11-3. 룰 매칭 (1단계)

| 파일 | 역할 |
|---|---|
| `glossary_matcher.py` | **Phase 3 — 용어사전 정확 매칭** |
| `sop_guide.py` | **SOP 8종 + 단계별 가이드 + 키워드 매핑** |
| `collaboration_guide.py` | **협업 시나리오 5종** |
| `work_actions.py` | 인-챗 액션 8종 패턴 + 우선순위 |
| `action_handlers.py` | **v3.3 Phase E-3 — 액션별 디스패처 + 핸들러 7개** |

### 11-4. 부서별 맞춤

| 파일 | 역할 |
|---|---|
| `department_router.py` | **Phase 5 — 부서별 시스템 프롬프트 주입** |
| `curriculum.py` | 부서별 학습 경로 생성 + 진행 추적 |
| `quick_questions.py` | **v3.3 Phase D — 부서·직급 맞춤 추천 질문 6개** |
| `proactive_engine.py` | **선제적 가이드 — 아직 안 본 필수 항목 추천** |

### 11-5. 학습·퀴즈

| 파일 | 역할 |
|---|---|
| `quiz_engine.py` | SOP 별 5문제 퀴즈 자동 생성 + 채점 |

### 11-6. 데이터

| 파일 | 역할 |
|---|---|
| `feedback_db.py` | `chat_feedback` 테이블 CRUD + 통계 |

### 11-7. 프롬프트

| 파일 | 역할 |
|---|---|
| `prompts/onboarding_system.txt` | 시스템 프롬프트 (부서별 동적 주입 전 base) |

---

## 12. 대화 메모리 (`conversation_memory.py`)

긴 대화 (예: 50 메시지) 를 LLM 에 통째로 보내면 토큰 비용 폭증 + context window 초과. 해결: **요약 기반 압축**.

### 12-1. 동작

```
대화 1-10 메시지       → 요약 생성 (LLM 으로 1번)
                          "사용자가 8D 의 단계별 진행을 물었고,
                           AI 가 SOP-8D 를 안내함."
                          ↓ (요약본만 보존)
대화 11-20 메시지       → 새 메시지 + 요약본 + 최근 N개 메시지
                          → 다시 요약 갱신
                          ↓
대화 21+ 메시지         → 압축된 요약 + 최근 6 메시지만 LLM 에 전달
```

### 12-2. 효과

- 토큰 80% 절감 (50 메시지 → 요약 + 6 메시지 ≈ 7 메시지)
- 컨텍스트 손실 최소화 (요약이 핵심 사실 보존)
- 비용 절감 (Phase B Vertex 진입 시 더 큰 효과)

---

## 13. 선제적 가이드 (`proactive_engine.py`)

신입사원이 **아직 안 물어본 중요한 것** 을 먼저 알려주는 모듈.

### 13-1. 동작

1. `curriculum.py` 가 부서별 필수 학습 항목 정의 (예: 품질팀=8D/PPAP/FMEA/MSA/SPC)
2. 사용자의 대화 이력 + SOP 조회 이력 분석
3. 미달성 항목 검출
4. 다음 대화 시작 시 부드럽게 추천:
   > "혹시 8D Report 는 다뤄보셨어요? 신입 첫 달에 자주 만나는 양식입니다 — SOP-8D 보여드릴까요?"

### 13-2. UI 표시

`/chat` 페이지의 우측 SidePanel "quiz" 탭에서 학습 진행률 표시:
```
품질보증팀 신입 학습 경로 (3/8)
✓ PPAP 기본
✓ 용어사전 (FMEA / MSA / Cpk)
✓ 8D 1단계 (팀 구성)
○ 8D 2-8단계
○ SPC 관리도
○ 협력사 응답
○ 사내 8D 회의
○ 8D 종료
```

---

## 14. 운영·확장 노트

### 14-1. ENABLE_FEATURE_C 플래그

`.env`:
```
ENABLE_FEATURE_C=true
```
이면 `/api/onboarding/...` 활성. SOP·협업 시나리오 데이터는 `features/onboarding/sop_guide.py` / `collaboration_guide.py` 에 정적 정의 — backend 재기동으로 갱신.

### 14-2. SOP 추가/수정

`features/onboarding/sop_guide.py:SOP_DATABASE` dict 에 새 항목 추가:
```python
"SOP-NEW-001": SOPDocument(
    sop_id="SOP-NEW-001",
    title="새 절차",
    department="...",
    category="...",
    steps=[
        SOPStep(step_number=1, title="...", description="...",
                checklist=["..."], caution="...", related_terms=["..."]),
    ],
)
```
backend 재기동 후 즉시 반영.

### 14-3. 협업 시나리오 추가

`features/onboarding/collaboration_guide.py:COLLABORATION_SCENARIOS` 리스트에 추가:
```python
CollaborationScenario(
    name="새 시나리오",
    trigger_keywords=["키워드1", "키워드2"],
    description="...",
    steps=[...],
)
```

### 14-4. 액션 추가

`features/onboarding/work_actions.py:ACTION_PATTERNS` + `action_handlers.py` 에 핸들러:
```python
# work_actions.py
"new_action": {"keywords": [...], "priority": ..., "regex": r"..."}

# action_handlers.py
def handle_new_action(query: str, ...) -> dict:
    return {"kind": "new_action", "data": {...}}

# dispatcher 분기 추가
if action.action_type == "new_action":
    return handle_new_action(query, ...)
```

### 14-5. 성능 — 응답 시간 목표

| 작업 | 목표 | 현재 |
|---|---|---|
| 룰 매칭 (SOP/협업/액션) | < 100ms | ~30-80ms |
| `/api/onboarding/sop/list` | < 200ms | ~50ms |
| LLM 폴백 첫 토큰 | < 2s | ~1-3s (Ollama 콜드 5-10s) |
| 멀티턴 메모리 압축 | < 500ms | ~200-400ms |

### 14-6. 현재 반영 및 남은 운영 과제

- [ ] **음성 입력** — Web Speech API → 마이크 챗
- [ ] **다국어** — 한국어 + 영문 (해외법인 신입 대응)
- [x] **vision/document 입력** — `/api/onboarding/chat/vision`, `/api/onboarding/vision/*`, `/api/onboarding/document/*` endpoint 구현. 도면·차트·문서별 prompt 품질 검수는 운영 과제로 유지
- [ ] **Slack 통합** — Slack 슬래시 커맨드 `/ajin ask`
- [x] **학습 진도 게임화** — `GET /api/onboarding/badges/me`, 뱃지 사이드바/모달, 부서 랭킹 계산 구현
- [x] **release gate** — `make feature-c-release-check`로 endpoint/LLM 비용/fallback/flag/content schema 검증

---

## 15. 자주 묻는 질문 (FAQ)

**Q1. 챗봇이 사실과 다른 답을 했어요.**
> 답변 하단 👎 클릭 + 코멘트 남기시면 운영자가 검토합니다 (`chat_feedback` 테이블 누적). 룰 매칭 응답은 SOP / 협업 시나리오 정의 자체를 수정해야 하고, LLM 응답은 시스템 프롬프트 또는 모델 변경으로 개선합니다.

**Q2. 부서를 바꿔서 챗하고 싶어요.**
> RBAC 등급에 따라 다릅니다. role_level=3 (관리자급) 이면 본부 내 부서 변경, role_level=4 (임원급) 이면 전사 부서 변경 가능. 일반 사용자는 자기 부서로 고정.

**Q3. 응답이 너무 길어요.**
> ChatMode 를 "업무" 로 바꾸면 간결하게 응답합니다. "교육" 모드는 신입 친화 — 자세한 설명 + 관련 용어 풀이.

**Q4. SOP 가 부족합니다. 더 추가할 수 있나요?**
> 현재 8종 정의. 운영자가 `sop_guide.py:SOP_DATABASE` 에 항목 추가 후 backend 재기동. 향후 관리자 UI 에서 직접 편집 가능하게 할 예정.

**Q5. 같은 질문에 매번 다른 답변이 나와요.**
> LLM 의 본질입니다 (확률적 생성). 룰 매칭으로 처리되는 SOP·협업·액션 응답은 결정적 (deterministic). 자주 묻는 질문은 룰로 옮기면 일관성 보장.

**Q6. 이미지 첨부해도 되나요?**
> `/chat/vision` endpoint 가 vision 모델 (gemma4:e2b/e4b 등) 로 처리. 도면·차트·그래프 분석 가능. 단 Ollama 0.18.x 에서는 gemma4 미지원 (Phase 2 hotfix 참조).

**Q7. 대화 내용이 외부로 새지 않나요?**
> 사내 Ollama 경로를 사용하면 LLM 처리가 내부 런타임에 머뭅니다. Gemini/Vertex 경로는 운영자가 명시적으로 설정한 경우에만 사용하며, 실제 데이터 보관·학습·리전 조건은 배포 프로젝트의 provider 설정과 계약 기준으로 별도 검토해야 합니다.

**Q8. 액션 카드 안에 검색 결과가 안 나와요.**
> 해당 feature 가 비활성됐을 가능성 — `ENABLE_FEATURE_A=false` 면 `employee_search` 액션 미동작. health endpoint 로 확인.

---

## 16. 용어집

| 용어 | 풀이 |
|---|---|
| **SSE** | Server-Sent Events — 서버가 토큰을 한 글자씩 흘려보내는 방식 (ChatGPT 처럼) |
| **JWT** | JSON Web Token — 로그인 후 받는 신분증 토큰 |
| **RBAC** | Role-Based Access Control — 역할에 따라 권한이 다른 시스템 |
| **role_level** | 사용자 권한 등급 — 1 (사원) / 3 (관리자) / 4 (임원) |
| **SOP** | Standard Operating Procedure — 표준 작업 절차서 |
| **PPAP** | Production Part Approval Process — 양산 부품 승인 절차 |
| **8D Report** | 8 Disciplines — 품질 문제 8단계 해결 보고서 |
| **ECN** | Engineering Change Notice — 설계 변경 통보 |
| **FMEA** | Failure Mode and Effects Analysis — 잠재 고장 영향 분석 |
| **MSA** | Measurement System Analysis — 측정 시스템 분석 |
| **SPC** | Statistical Process Control — 통계적 공정 관리 |
| **Cpk** | 공정 능력 지수 — 공정의 표준편차 대비 규격 한계까지의 거리 |
| **Nelson Rules** | SPC 관리도에서 이상 신호를 감지하는 8가지 규칙 |
| **intent** | 의도 — 사용자 질문의 분류된 카테고리 |
| **action_type** | 인-챗 액션 식별자 (예: `regulation_qa`) |
| **vision 모델** | 이미지를 입력으로 받는 LLM (예: gemma4 family) |
| **glossary** | 용어사전 — 사내 약어·전문 용어 정의 모음 |
| **proactive guide** | 사용자가 묻기 전에 먼저 안내하는 시스템 |
| **멀티턴** | 한 대화에서 주제가 이어지며 여러 번 주고받음 |
| **온도 (temperature)** | LLM 답변의 무작위성 — 0=결정적, 1=다양 |

---

## 17. 변경 이력 (Feature C 한정)

| 버전 | 날짜 | 주요 변경 |
|---|---|---|
| Phase 1-3 | 2025-? | 기본 챗 + glossary_matcher 도입 |
| Phase 4 | 2025-? | 2단계 응답 엔진 (룰 → LLM) |
| Phase 5 | 2025-? | department_router — 부서별 맞춤 |
| Phase 6 | 2025-? | conversation_manager — 멀티턴 + 관련 용어 |
| v3.3 Phase A | 2026-? | LLM 멀티 프로바이더 셀렉터 + localStorage 영속 |
| v3.3 Phase B | 2026-? | 부서 컨텍스트 RBAC (MANAGER/EXEC) |
| v3.3 Phase D | 2026-? | quick_questions 부서·직급 맞춤 |
| v3.3 Phase E-3 | 2026-? | action_handlers 5종 → 7종 + 디스패처 |
| v3.4 | 2026-04 | SOP 8종 (PPAP/8D/ECN/프레스/금형 추가) + 협업 시나리오 5종 + 진행률 바 + 스트리밍 중 네비 차단 |

상세 변경 이력은 [CHANGELOG.md](../CHANGELOG.md) 참조.

---

## 18. 한눈 요약 카드

```
┌─────────────────────────────────────────────────────────────┐
│  기능 C — AI 업무 도우미 / 온보딩 챗봇                     │
├─────────────────────────────────────────────────────────────┤
│  💬 신입사원 6개월 동안 24시간 답해주는 AI 동료            │
│                                                             │
│  💻 Backend     FastAPI + SSE + LLMRouter (Ollama/Gemini)  │
│                  + 2단계 응답 (룰→LLM) + 멀티턴 메모리     │
│  🖥  Frontend    React + Vite + TS + Zustand + useSSE       │
│                  + MarkdownRenderer + ActionCardRouter     │
│  🔐 보안         JWT 필수 + 부서 RBAC (level 1/3/4)        │
│                  + 감사 로깅 + 입력 살균                   │
│  🌐 Endpoint    OpenAPI 기준 — docs/API.md 자동 산정       │
│                  chat/vision·upload·sop/list·quiz 등      │
│  📊 데이터       chat_feedback 1 테이블 (👍/👎 누적)       │
│  📚 SOP          8종 (프레스 금형/용접/CNC/PPAP/8D/ECN/    │
│                       시타/금형 입고)                      │
│  🤝 협업 시나리오 5종 (8D/ECN/SPC/PPAP/안전점검)            │
│  ⚡ 인-챗 액션   8종 (error/employee/spc/email/document/   │
│                       regulation_status·qa/document_search)│
│  🎯 부서 맞춤    27 부서 × 직급별 응답 차별                │
│  📁 코드          features/onboarding/ (17 모듈)            │
│                  routes/chat.tsx                            │
└─────────────────────────────────────────────────────────────┘
```

---

## v4.0 변경 (2026-05-10) — 90% → 100% + 사용자 피드백 5건 적용

### 작업 8건

| ID | 작업 | 산출물 |
|---|---|---|
| **C1** | 부서 selectbox 라벨 단순화 | `chat.tsx:1217` "부서 컨텍스트" → "부서" |
| **C2** | 세션 ID 노출 제거 | `chat.tsx:2050` `세션 #A47-2026` → `대화` (`● LIVE` 인디케이터만 유지) |
| **C3** | SOP 부서 처리 (안내 + 클라이언트 필터) | `displaySopList` useMemo 추가 + `sopFilterMode='matching'\|'all'` 토글 + 매칭 부서 0개 시 안내 |
| **C4** | LeftSidebar streaming BUG 격리 | `LeftSidebar.tsx:163` 라벨 교체("응답 생성 중...") 제거 → 활성 모듈 옆 점멸 점만 유지. 추천 질문 클릭 시 사이드바 안정 |
| **C5** | KB 자료 4개 + JSON kb_doc_path + /chat 자동 prepend | `data/knowledge_base/department_guides/총무인사팀_복리후생.md`, `_시설관리.md`, `_사회환원.md`, `_채용.md` + `quick_questions/총무인사팀.json` 7개 항목 (`hr-csr-activities` 신규) + `features/onboarding/kb_lookup.py` (promptText 매칭 → KB markdown 자동 컨텍스트 주입) |
| **C6-1** | 퀴즈 채점 정리 | 점수 요약 + 다시 풀기 + 해설 이모지(🎯/🔄/💡/⚠) 제거 → `SCORE · n / N` / `해설 — …` / `● 백엔드 미가용` 텍스트 형식 |
| **C6-2** | 부서 변경 시 SOP·협업 deps 정상화 | `chat.tsx:371,391` `useEffect deps` 에 `dept` 추가 → 부서 selectbox 변경 시 자동 리페치 |
| **C6-3** | 검색 결과 없음 응답 개선 | `EmployeeCard.tsx:84-93` 친절한 안내 + 검색 팁 4개 + 인사관리팀 안내 |

### 신규 자산

- KB 자료: `data/knowledge_base/department_guides/총무인사팀_*.md` × 4 (복리후생 / 시설관리 / 사회환원 / 채용)
- 신규 모듈: `features/onboarding/kb_lookup.py` (promptText → kb_doc_path 매칭 + 자동 markdown 로드 + 4000자 제한)
- 신규 추천 질문: `hr-csr-activities` (사회 환원활동 지원) — 7개 슬롯
- 갱신 라벨: `hr-benefit-list` "복리후생 안내" → **"직원 복리후생"**, `hr-facility-request` "시설 신청" → **"시설관리"**

### `/chat` 핸들러 흐름 (v4)

```
요청 수신
  ↓
부서 RBAC 강제 (_resolve_effective_department)
  ↓
액션 감지 (detect_actions) → 카드 페이로드
  ↓
[NEW C5] kb_lookup.load_kb_context(query, dept) → 매칭 KB markdown 로드
  ↓
시스템 프롬프트 합성 (history + file_ctx + action_context + kb_context)
  ↓
LLMRouter SSE 스트리밍 (운영 기본 Ollama primary, Gemini/LM Studio는 명시 설정 시 fallback 또는 비교 검증)
```

### 디자인 시스템 v3.5 정렬

- 이모지 0건 (모든 quiz/badge 텍스트로 교체)
- 라운드 8/12/16/999px 만 사용
- 영문 eyebrow + 한글 본문 페어
- `lg-state-pill` / `lg-eyebrow` / `lg-btn` / `lg-pill` 캐노니컬 클래스

### 검증

- `tsc -b && vite build` ✓ (1.48s, 4,610 모듈)
- Python AST ✓ (kb_lookup.py / onboarding.py)
- JSON 검증 ✓ (총무인사팀.json 7 항목)
- e2e 시나리오 6건 (신입 첫 진입 / 부서 변경 동기화 / 추천 질문 응답 품질 / 사이드바 격리 / 세션 헤더 / 퀴즈 채점)

### 후속 트랙 (v5+)

- 32 부서 전부 KB 자료 작성 (현재 총무인사팀 4개만 MVP)
- 백엔드 `/sop/list?department=` 파라미터 + DB 확장 (현재 클라이언트 필터링만)
- 사내 위키 풀 RAG 임베딩 + 동적 검색 (현재 정적 prepend)
- 음성 입력 + Confluence 연동

---

문서 작성: 2026-05-10 | 본 문서는 기능 변경 시 함께 갱신해주세요.
