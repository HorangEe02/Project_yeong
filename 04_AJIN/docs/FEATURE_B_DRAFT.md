# 기능 B — 문서 작성 (Draft · Document Generator)

> **이 문서는 누구를 위한 것인가요?**
> 개발자가 아닌 분 (운영자·기획자·도메인 전문가) 도 끝까지 읽을 수 있도록 작성했습니다.
> 어려운 용어는 처음 등장할 때 _기울임_ 으로 표시하고 옆에 짧은 설명을 붙입니다.

---

## 1. 한 줄 요약

**"빈 문서 화면 앞에서 막막한 시간"을 분 단위에서 초 단위로 줄여주는 AI 문서 비서입니다.**

회의록·8D 보고서·OEM 영문 이메일·휴가 신청서 등 API 기준 문서 유형 중 골라 한 줄 설명만 입력하면, **격식체로 잘 정돈된 초안**이 실시간으로 화면에 흘러나옵니다. 마음에 들면 DOCX·PDF·HWPX 등 7포맷으로 즉시 다운로드. 게다가 **누구에게 참조(CC)로 걸어야 하는지** 자동 추천하고, **문서 품질을 5기준 100점 만점으로 채점** 까지 해줍니다.

---

## 2. 누가, 언제 쓰는가?

| 사용자 | 시나리오 | 기능 B 가 해주는 일 |
|---|---|---|
| **품질보증팀 과장** | 협력사에 8D Report 송부해야 함 | 8D Report 선택 → 문제·팀·증상 입력 → 격식체 초안 + PSW/FMEA 등 첨부 항목 자동 표시 |
| **구매팀 대리** | OEM 영문 이메일 작성 — 영어 자신 없음 | OEM Email 선택 → 한국어로 요청 입력 → 영어 초안 + 격식체 |
| **신입사원** | 휴가 신청서 양식 모름 | 휴가 신청서 선택 → 시작일·사유 입력 → 사내 양식 그대로 |
| **생산기술팀 부장** | 주간 보고 작성 — 매주 반복 | 주간 보고 선택 → 이번 주 핵심 입력 → 양식 + 자동 CC (관리·생산·개발본부) |
| **HR 관리자** | 인사발령 통지 — 양식이 정해져 있음 | 사내 양식 .docx 업로드 → 그 양식 그대로 새 내용 작성 |
| **임원** | 사내 이메일 — 톤이 중요 | "친근" / "격식" / "간결" 5단계 톤 선택 |

---

## 3. 전체 작동 흐름 (그림으로)

사용자가 "PPAP Level 3 제출 안내" 라는 OEM 이메일 초안을 만드는 경우:

```
[브라우저]                                            [서버]
1) 문서 유형 선택      
   "OEM 영문 이메일"        
                                                    
2) 입력
   - 톤: "격식 (외부)"  
   - 메타: 부품번호, 기한
   - 요청: "PPAP L3 제출 안내"  
                                                    
3) [생성하기] 클릭
        │
        │ POST /api/draft/stream-v2
        │ (SSE 연결 — 토큰이 한 글자씩 흘러옴)
        ▼
─────────────────── 인터넷 / 사내망 ───────────────────
                                                    FastAPI
                                                       │
                                                       │ (a) classifier
                                                       │     문서 유형 검증
                                                       ▼
                                                    fewshot_rag
                                                       │
                                                       │ (b) 비슷한 과거 문서 3건
                                                       │     검색 (RAG)
                                                       ▼
                                                    doc_type_config.build_prompt
                                                       │
                                                       │ (c) 문서 유형별 시스템 프롬프트
                                                       │     + 톤 + 메타 + 사례 합성
                                                       ▼
                                                    LLMRouter (DRAFT 모드)
                                                       │
                                                       │ (d) Ollama → Gemini → LM Studio
                                                       │     폴백 체인. SSE 토큰 stream
                                                       │
                                                       │ (5초마다 heartbeat — 끊김 방지)
                                                       ▼
4) ◀─ 토큰 한 글자씩 도착                          토큰 = "안", "녕", "하", ...
   → 화면에 실시간 출력
                                                    
5) 완료 후
   - quality/score: 92점 A 등급        
   - cc/recommend: 필수=영업팀,권장=생산본부
   - diff: 이전 버전과 차이 비교 (선택)
                                                    
6) [DOCX 다운로드] 클릭
        │
        │ POST /api/draft/export
        ▼
                                                    format_shaper.shape_for_format()
                                                       → docx/pdf/hwpx/odt/xlsx/csv/txt
                                                       각 라이브러리로 변환
                                                       (python-docx, reportlab, owpml...)
                                                       │
                                                       ▼
   ◀─ 바이너리 응답                                "draft.docx" (Content-Disposition)
   브라우저 자동 다운로드
```

핵심은 **"문서 유형 → 톤 → 메타 → LLM 스트림 → 품질·CC·Diff → 다운로드"** 흐름입니다.

---

## 4. 기술 스택

기술 스택을 4 영역으로 나눠 봅니다. 각 항목 옆 괄호 안은 _그게 뭔가요?_ 풀이입니다.

### 4-1. 백엔드 (Backend, "서버 쪽 두뇌")

| 카테고리 | 기술 | 역할 |
|---|---|---|
| 언어 | **Python 3.11+** | 서버 코드 |
| 웹 프레임워크 | **FastAPI** _(요청을 받고 응답을 돌려주는 도구)_ | `/api/draft/...` endpoint — 현재 수치는 [API 인덱스](API.md) 기준 |
| 스트리밍 | **SSE** _(Server-Sent Events — 응답을 한 번에 안 보내고 토큰 한 개씩 흘려보내는 방식)_ | LLM 답변이 ChatGPT 처럼 실시간 출력 |
| LLM 라우터 | **LLMRouter** (자체) | Ollama·Gemini·LM Studio 폴백 체인 |
| LLM 모델 (로컬) | **Ollama** + qwen3.5:9b / exaone3.5 | 사내 GPU 또는 host Metal 활용 |
| LLM 모델 (옵션) | **Google Gemini** (`google-genai` SDK) | Cloud Run 환경에서 사용 |
| 템플릿 엔진 | **Jinja2** _(빈칸 채우기 식 양식 처리 도구)_ | API 문서 유형의 시스템 프롬프트 + 양식 |
| RAG | **자체 fewshot_rag** | 비슷한 과거 문서 3건 자동 첨부 |
| 데이터베이스 | **SQLite** | `data/draft_versions.db` — 문서 버전 이력 |
| 파일 변환 | **python-docx, reportlab, openpyxl, pypdf, olefile, OWPML** | 7포맷 export |
| 인증 | **JWT (필수)** | `get_current_user` — 문서 작성 API는 로그인 사용자 전용 |

### 4-2. 프론트엔드 (Frontend, "사용자가 보는 화면")

| 카테고리 | 기술 | 역할 |
|---|---|---|
| 언어 | **TypeScript** | 화면 코드 |
| UI 라이브러리 | **React** + **Vite** | 컴포넌트 + 빌드 |
| 상태 관리 | **Zustand** _(앱 데이터 보관소)_ | `useDraftStore` (초안 상태), `useUIStore` (탭 상태) |
| SSE 연결 | **`useSSE` 자체 훅** | 토큰 stream + 자동 재연결 + heartbeat 처리 |
| 아이콘 | **lucide-react** | Upload, FileText, AlertCircle 등 |
| 영속화 | **Backend draft/version API** | 서버 저장소 이력 + legacy Firestore shim 비활성 |
| 다운로드 | **DownloadActions 공통 컴포넌트** | 7포맷 + 클립보드 |

### 4-3. 인프라 (운영 환경)

| 항목 | 값 |
|---|---|
| 컨테이너 | Docker (multi-stage build) |
| 운영 OS | Linux (Cloud Run) / macOS (개발) |
| 리버스 프록시 | nginx-rp (개발) / Cloud Run backend + 정적 SPA hosting rewrite 경로 |
| SSE 버퍼링 회피 | 16KB 패딩 + 5초 heartbeat (GFE buffering 우회) |
| 로깅 | Python logging + 감사 이력 (`audit.db`) |

### 4-4. 보안

- **FEATURE_B_BLOCK_GEMINI=true (default)** — Gemini 클라우드로 사내 문서 내용이 나가지 않도록 차단. 사내 Ollama 로 자동 다운그레이드.
- **자동 안전망** — Ollama 미가용 환경 (`OLLAMA_BASE_URL=""`) + 차단 ON 조합이면 빈 응답 발생 → 차단 자동 해제. 운영자 실수 방지.
- **감사 로깅** — 모든 generate / export 요청은 `log_api_access()` 로 audit.db 기록 (누가·언제·어떤 문서를 만들었나).
- **업로드 파일 검증** — 5MB 한도, 확장자 화이트리스트 (.docx/.pdf/.hwp/.hwpx/.txt/.md), 메모리에서 추출 후 즉시 폐기 (서버 영속 저장 X).

---

## 5. 백엔드 Endpoint 목록

기능 B가 제공하는 서버 API 목록입니다. 현재 endpoint 총수는 FastAPI OpenAPI 산출물인 [API 인덱스](API.md)를 기준으로 확인합니다.

| 메서드 | 경로 | 용도 | 핵심 응답 |
|---|---|---|---|
| `POST` | `/api/draft/generate` | 간단 SSE 초안 생성 (v1) | 토큰 stream |
| `POST` | `/api/draft/stream` | SSE 초안 — 메타 구조화 | 토큰 stream |
| `POST` | `/api/draft/stream-v2` | **(주력)** SSE — Few-shot RAG + LLMRouter + heartbeat | event 6종 (`stage`/`token`/`done`) |
| `POST` | `/api/draft/generate-pipeline` | 비-스트리밍 (분류→생성→렌더 통합) | 완성된 텍스트 |
| `POST` | `/api/draft/export` | 7포맷 다운로드 | 바이너리 (docx/pdf/...) |
| `GET` | `/api/draft/doc-types` | 문서 유형 메타 | `[{id, category, name_ko, name_en, required_fields}]` |
| `GET` | `/api/draft/templates` | 사용 가능한 .j2 템플릿 목록 | `[{id, name, language, category}]` |
| `POST` | `/api/draft/cc/recommend` | CC 자동 추천 3-tier (필수/권장/선택) | `[{tier, departments}]` |
| `POST` | `/api/draft/quality/score` | 품질 평가 5기준 + A~F 등급 | `{total_score, grade, scores, improvements}` |
| `POST` | `/api/draft/diff` | 버전 diff (add/del/mod/ctx) | `{lines, stats, diff_html}` |
| `GET` | `/api/draft/diagnose` | 5 의존성 진단 (Ollama/Gemini/Pipeline/Templates/Prompts, `SYS_ADMIN(L5)` 전용) | `{ok, detail, meta}` × 5 |
| `POST` | `/api/draft/upload-reference` | 사용자 양식 (.docx/.pdf/.hwpx 등) 텍스트 추출 | `{text, detected_format, warning}` |

### 5-1. SSE 응답 예시 — `/api/draft/stream-v2`

```
event: stage
data: {"name":"classify","status":"ok","meta":{"doc_type":"oem_email"}}

event: stage
data: {"name":"rag","status":"ok","meta":{"hits":3}}

event: stage
data: {"name":"llm","status":"running","meta":{"provider":"ollama","model":"qwen3.5:9b"}}

event: token
data: 안

event: token
data: 녕

event: token
data: 하

...

event: stage
data: {"name":"llm","status":"ok"}

event: done
data: {"ok":true}
```

토큰이 1글자씩 흘러나오므로 사용자는 **답변이 생성되는 과정** 을 실시간으로 봅니다 (ChatGPT 와 같은 UX).

### 5-2. 일반 응답 예시 — `/api/draft/quality/score`

요청:
```json
POST /api/draft/quality/score
{ "text": "...", "doc_type": "8d_report" }
```

응답:
```json
{
  "total_score": 87.3,
  "grade": "B+",
  "scores": {
    "structure": 95.0,
    "length": 88.0,
    "terminology": 80.0,
    "completeness": 92.0,
    "tone": 82.0
  },
  "improvements": [
    "제 4단계 '근본 원인 분석' 의 5-Why 다이어그램이 누락됐습니다.",
    "마무리 문구가 누락되어 격식이 떨어집니다."
  ]
}
```

---

## 6. 데이터베이스 스키마

문서 버전 이력은 `data/draft_versions.db` (SQLite) 의 **2 테이블** 에 저장됩니다.

### 6-1. documents 테이블 — 문서 메타

| 컬럼 | 타입 | 설명 | 예시 |
|---|---|---|---|
| `id` | INTEGER (PK, AUTOINCREMENT) | 문서 ID | `42` |
| `doc_type` | TEXT (필수) | 문서 유형 | `8d_report`, `oem_email` |
| `title` | TEXT | 제목 | `PPAP Level 3 제출 안내` |
| `author` | TEXT | 작성자 employee_id | `EMP-A0042` |
| `department` | TEXT | 작성 부서 | `품질보증팀` |
| `created_at` | TEXT | 최초 생성 시각 | `2026-05-09 14:23:11` |
| `updated_at` | TEXT | 최근 갱신 시각 | `2026-05-10 09:01:55` |

### 6-2. versions 테이블 — 문서 버전 이력

| 컬럼 | 타입 | 설명 | 예시 |
|---|---|---|---|
| `id` | INTEGER (PK, AUTOINCREMENT) | 버전 ID | `156` |
| `document_id` | INTEGER (FK → documents.id) | 문서 ID | `42` |
| `version_num` | INTEGER (default `1`) | 몇 번째 버전 | `3` |
| `template_vars_json` | TEXT (default `{}`) | 사용된 메타 변수 (JSON) | `{"recipient":"현대차","level":"3"}` |
| `rendered_text` | TEXT | 최종 텍스트 | `## PPAP ...` |
| `change_summary` | TEXT | 변경 요약 (예: "톤 격식 → 친근") | `친근체로 톤 변경` |
| `created_at` | TEXT | 버전 생성 시각 | `2026-05-09 14:23:11` |
| `created_by` | TEXT | 작성자 | `EMP-A0042` |

### 6-3. ER 다이어그램 (간단)

```
┌──────────────────────────────────┐
│   documents (1 행 = 문서 1개)    │
│  ────────────────────────────    │
│  id (PK)                         │
│  doc_type, title, author         │
│  department, created_at, updated │
└──────────────┬───────────────────┘
               │
               │ 1 : N
               ▼
┌──────────────────────────────────┐
│   versions (1 행 = 버전 1개)      │
│  ────────────────────────────    │
│  id (PK)                         │
│  document_id (FK)                │
│  version_num, template_vars_json │
│  rendered_text, change_summary   │
│  created_at, created_by          │
└──────────────────────────────────┘
```

> **왜 versions 가 별도 테이블인가요?**
> 한 문서를 여러 번 수정하면서 매번 새 버전을 남기기 위함입니다. **언제** 어떤 변수로 어떤 텍스트가 만들어졌는지 추적 가능 — 감사 / 재작성 / 버전 비교 (`/api/draft/diff`) 모두 이 테이블 활용.

### 6-4. 인덱스

```sql
CREATE INDEX idx_versions_doc ON versions(document_id, version_num);
CREATE INDEX idx_documents_author ON documents(author, created_at DESC);
```
- 첫 번째 — "문서 X 의 버전 5 어디 있나?" 조회 빠름
- 두 번째 — "내가 최근 만든 문서 10건" 조회 빠름

---

## 7. 문서 유형 + 5 톤 + 5 품질 기준

### 7-1. 문서 유형

문서 유형은 `features/draft/doc_type_config.py` 에 정의합니다. 현재 config 기준 내부 10종 + 외부 13종을 API 로 변환하며, config 로드 실패 시 backend fallback 16종을 반환합니다.

#### 외부 문서 6종 (협력사·고객사 발송)

| 유형 | 영문 | 필수 필드 | 용도 |
|---|---|---|---|
| **8D Report** | 8D Report | title, issue, team | 품질 문제 8단계 보고서 (자동차 업계 표준) |
| **ECN** | Engineering Change Notice | title, change_reason | 설계 변경 통지서 |
| **PPAP** | Production Part Approval Process | part_number, level | 양산 부품 승인 절차 (Level 1-5) |
| **FMEA** | Failure Mode & Effects Analysis | process, risk | 잠재 고장 모드 + 영향 분석 |
| **MSA** | Measurement System Analysis | instrument, study_type | 측정 시스템 분석 |
| **OEM Email** | OEM Email (English) | recipient, subject | 현대·기아·HMGMA 영문 이메일 |

#### 내부 문서 7종 (사내 사용)

| 유형 | 영문 | 필수 필드 | 용도 |
|---|---|---|---|
| **사내 이메일** | Internal Email | recipient, subject | 부서 간 협조·공유 |
| **회의록** | Meeting Minutes | date, attendees | 회의 결정사항 정리 |
| **주간 보고** | Weekly Report | week, summary | 주간 업무 보고 |
| **휴가 신청서** | Leave Request | start_date, reason | 인사 양식 |
| **견적서** | Quote | customer, items | 영업·구매 |
| **출장 보고서** | Travel Report | destination, purpose | 출장 후 보고 |
| **SPC Report** | SPC Report | process, period | 통계적 공정 관리 보고 |

> **Fallback 동작**: `business_trip_request`, `resignation_letter`, `personnel_notice` 등 내부 문서 유형은 backend fallback 과 frontend fallback 양쪽에 남아 있습니다. 운영 화면의 정식 기준은 `/api/draft/doc-types` 응답입니다.

### 7-2. 5단계 톤 (어조)

| ID | 한글 | 영문 | 용도 |
|---|---|---|---|
| `formal_internal` | 격식 (사내) | Formal (Internal) | 임원 보고·중요 사내 발송 |
| `formal_external` | 격식 (외부) | Formal (External) | OEM·관공서 |
| `standard` | 표준 | Standard | 일반적 사내 |
| `friendly` | 친근 | Friendly | 같은 팀·잘 아는 사이 |
| `concise` | 간결 | Concise | 단순 알림·체크리스트 |

### 7-3. 5 품질 기준 (`/api/draft/quality/score`)

각 0~100점, 평균이 총점 → A~F 등급.

| 기준 | 무엇을 보나 | 예시 |
|---|---|---|
| **structure** (구조) | 제목·수신/발신·본문·끝맺음 4 영역이 다 있나 | 마무리 문구 누락 → 감점 |
| **length** (길이) | 문서 유형에 맞는 적정 분량 | 8D 인데 5줄만 → 감점 |
| **terminology** (전문성) | 도메인 용어가 적절한가 | "PPAP Level 3" 같은 정확한 용어 |
| **completeness** (완성도) | 필수 항목 누락 여부 | FMEA 인데 RPN 계산 누락 |
| **tone** (톤 일관성) | 선택한 톤과 실제 문체 일치 | 격식 선택했는데 반말 → 감점 |

**등급 매핑:**

| 점수 | 등급 |
|---|---|
| 90+ | A |
| 80-89 | B+ |
| 70-79 | B |
| 50-69 | C |
| 30-49 | D |
| <30 | F |

---

## 8. CC 자동 추천 3-tier

`features/draft/cc_recommender.py` 가 문서 유형 + 발신 부서 → CC 대상자 자동 추천. **3 등급:**

| Tier | 의미 | 예시 (8D Report 발신=품질보증팀) |
|---|---|---|
| **REQUIRED** (필수) | 빠지면 절차 위반 | 영업팀 (고객사 응대) |
| **RECOMMENDED** (권장) | 보통 함께 보냄 | 생산본부장, 부품개발팀 |
| **OPTIONAL** (선택) | 사정에 따라 | 임원, IT전략팀 |

매핑은 `cc_recommender.py` 의 룰 테이블에 정의. 운영자가 룰을 수정하면 즉시 반영.

---

## 9. 프론트엔드 컴포넌트 트리

### 9-1. 페이지 구조

```
/draft 라우트 (frontend/src/routes/draft.tsx, ~1500 LOC 추정)
│
├─ <_shell>
│  ├─ <TopBar>
│  └─ <Sidebar>
│
└─ <Draft> (메인 페이지)
   │
   ├─ 헤더 + 진단 배너
   │  └─ <DiagnoseBanner>     — /api/draft/diagnose 5 체크 결과
   │      (모든 OK 면 숨김, 하나라도 실패 시 노란/빨간 배너)
   │
   ├─ 3 탭
   │  ├─ "작성" 탭
   │  │  ├─ <DocTypeSelector>  — 13 유형 그리드 (외부 6 + 내부 7)
   │  │  ├─ <ToneSelector>     — 5단계 톤 chip
   │  │  ├─ <ContextToggle>    — internal / external
   │  │  ├─ <MetaInputs>       — 문서 유형별 필수 필드 (recipient, subject 등)
   │  │  ├─ <UserRequest>      — 자유 입력 textarea
   │  │  ├─ <ReferenceUpload>  — 양식 .docx/.pdf 업로드
   │  │  ├─ <ModelSelector>    — Ollama / Gemini / 모델명 (관리자급)
   │  │  └─ <GenerateButton>   — SSE 시작
   │  │
   │  ├─ "결과" 탭
   │  │  ├─ <StreamingOutput>  — SSE 토큰 실시간 출력
   │  │  ├─ <QualityCard>      — 5 기준 + 총점 + 등급
   │  │  ├─ <CCCard>           — 3-tier 자동 추천
   │  │  └─ <DownloadActions>  — 7포맷 + 클립보드
   │  │
   │  └─ "이력" 탭
   │     └─ <HistoryList>      — 서버 저장소에 남은 과거 초안
   │
   └─ <DiffDrawer> (선택, 우측)
      └─ /api/draft/diff 결과 (lg-diff-line.add/del/mod/ctx 마크업)
```

### 9-2. 상태 관리

| 데이터 | 위치 | 영속성 |
|---|---|---|
| 현재 선택된 doc_type / tone / context | `useDraftStore` (Zustand) | localStorage |
| 메타 입력 (recipient, subject 등) | useState | 메모리 (탭 이탈 시 리셋) |
| 스트리밍 중 토큰 누적 | useState (useSSE 훅 내부) | 메모리 |
| 작성 이력 | backend draft/version API | 서버 저장소 |
| 모델 옵션 (Ollama/Gemini 가용 모델) | `fetchLlmOptions()` | API 호출마다 갱신 |
| diagnose 결과 | useState | 페이지 진입 시 1회 |

### 9-3. API 호출 흐름

`frontend/src/api/draft.ts`가 draft endpoint를 감싸서 React가 쉽게 호출합니다. 전체 endpoint 수는 [API 인덱스](API.md)가 단일 기준입니다.

```typescript
// 페이지 진입
fetchDocTypes()        → GET  /api/draft/doc-types
fetchDiagnose()        → GET  /api/draft/diagnose
fetchLlmOptions()      → GET  /api/models  (공통)

// 양식 업로드 (선택)
uploadReference(file)  → POST /api/draft/upload-reference

// 생성
buildStreamV2Request() + useSSE → POST /api/draft/stream-v2 (SSE)

// 결과 분석 (선택)
recommendCC(...)       → POST /api/draft/cc/recommend
scoreQuality(...)      → POST /api/draft/quality/score
computeDiff(...)       → POST /api/draft/diff

// 다운로드
exportDraft(format)    → POST /api/draft/export → blob
```

---

## 10. 부속 모듈·파일 가이드 (21 모듈)

### 10-1. 핵심 파이프라인

| 파일 | 역할 | 비유로 설명 |
|---|---|---|
| `__init__.py` (DraftPipeline) | 통합 진입점 | "주방장" — 전체 요리(문서) 흐름 지휘 |
| `classifier.py` | 문서 유형 분류 | "메뉴판 보고 어떤 메뉴인지 결정" |
| `generator.py` | LLM 호출 + 초안 생성 | "주방의 화구" — 실제 요리 |
| `template_renderer.py` | Jinja2 양식 적용 | "그릇에 담기" — 양식대로 정렬 |

### 10-2. 양식·프롬프트 관리

| 파일 | 역할 |
|---|---|
| `doc_type_config.py` | 문서 유형 + 시스템 프롬프트 + 필수 필드 + build_prompt() 함수 |
| `tone_config.py` | 5단계 톤별 어조 가이드 |
| `template_catalog.py` | .j2 템플릿 인덱싱 + 검색 |
| `template_exporter.py` | 템플릿을 호출자에 노출 |
| `prompts/` 디렉토리 (7 .txt) | 시스템 프롬프트 raw 텍스트 |

**prompts/ 안의 7개 파일:**
- `email_to_internal.txt` — 사내 이메일
- `email_to_oem.txt` — OEM 이메일
- `email_to_overseas.txt` — 해외법인 이메일
- `email_to_supplier.txt` — 협력사 이메일
- `report_8d.txt` — 8D 보고서
- `report_ecn.txt` — ECN
- `report_meeting.txt` — 회의록

### 10-3. 품질·CC·Diff (분석 도구)

| 파일 | 역할 |
|---|---|
| `doc_quality_scorer.py` | 5 기준 평가 (`evaluate_document()`) |
| `cc_recommender.py` | 3-tier CC 추천 (`recommend_cc()`) |
| `doc_diff.py` | 두 버전 비교 (`compute_diff()`, `compute_similarity_ratio()`) |

### 10-4. RAG (참고 사례 검색)

| 파일 | 역할 |
|---|---|
| `fewshot_rag.py` | 비슷한 과거 문서 N건 검색 |
| `search_engine.py` | 사내 문서 색인 + 검색 |

### 10-5. 7포맷 출력

| 파일 | 포맷 | 라이브러리 |
|---|---|---|
| `format_shaper.py` | 단일 진입점 (`shape_for_format()`) | 모든 포맷 dispatcher |
| `docx_exporter.py` | .docx | python-docx |
| `pdf_exporter.py` | .pdf | reportlab / fpdf |
| `hwpx_exporter.py` | .hwpx (정식 OWPML) | 자체 구현 (한컴 표준) |
| `tabular_exporter.py` | .csv / .xlsx | openpyxl + 마크다운 표 자동 파싱 |

> **HWP/HWPX 가 왜 두 개?** HWP (5.0) 는 Microsoft OLE compound 포맷 (.doc 와 비슷한 옛날 형식) — `_extract_hwp` 가 PrvText 만 추출. HWPX 는 OWPML zip 포맷 (Office Open XML 과 비슷한 신형식) — 정식 출력 가능.

### 10-6. 세션·버전 관리

| 파일 | 역할 |
|---|---|
| `draft_session.py` | 대화형 수정 세션 (생성 → 수정 → 재수정 흐름) |
| `version_db.py` | `documents` + `versions` 테이블 CRUD |

---

## 11. 5 의존성 진단 (`/api/draft/diagnose`)

화면 상단의 "Module B 진단 배너" 가 표시하는 5 체크. `SYS_ADMIN(L5)` 사용자에게만 노출되며, 모든 OK 면 배너 숨김, 하나라도 실패 시 구체 원인 표면화 (Plan v1.0 §1.1).

| 체크 | 무엇 | 실패 시 메시지 |
|---|---|---|
| **1. Ollama** | `OLLAMA_BASE_URL/api/tags` HTTP 200 | `Ollama 서버 연결 불가 — \`ollama serve\` 확인` |
| **2. Gemini** | `.env` 의 `GEMINI_API_KEY` 존재 | `GEMINI_API_KEY 미설정 (.env)` |
| **3. Pipeline** | `app.state.draft_pipeline` 객체 | `DraftPipeline 미부팅 (ENABLE_FEATURE_B=false)` |
| **4. Templates** | `data/knowledge_base/templates/*.j2` | `템플릿 DB 누락` |
| **5. Prompts** | `features/draft/prompts/*.txt` | `프롬프트 누락` |

> **summary_ok** = Ollama + Pipeline + Templates + Prompts 모두 OK (Gemini 는 선택적 — Feature B 보안 정책상 차단됨)

---

## 12. 보안 정책 — Gemini 차단 메커니즘

기능 B 의 가장 까다로운 정책. **사내 문서 내용을 외부 클라우드로 보내지 않기 위함.**

### 12-1. 환경변수

| 변수 | 기본값 | 의미 |
|---|---|---|
| `FEATURE_B_BLOCK_GEMINI` | `true` | Gemini provider 요청 시 ollama 로 강제 다운그레이드 |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 가 가동 중이어야 차단 의미 있음 |

### 12-2. 자동 안전망

`block_gemini=true` + `OLLAMA_BASE_URL=""` (Ollama 없음) 조합이면 모든 provider 가 차단되어 빈 응답 발생. 이를 자동 감지해서 **block_gemini 를 자동 해제** (시연 환경 보호).

### 12-3. SSE 이벤트 알림

차단 적용 시 `stage:security` event 로 사용자에게 표시:
```
event: stage
data: {"name":"security","status":"warn",
       "meta":{"policy":"feature-b-blocks-gemini",
               "message":"Feature B 보안 정책에 따라 Gemini 요청을 로컬 모델로 다운그레이드했습니다."}}
```

### 12-4. 폴백 체인

`/stream-v2` 가 1차 시도에서 토큰 0개 + Gemini 미차단 시 자유 폴백 체인 재시도:
```
ollama → ollama_alt → gemini → lm_studio
```
heartbeat 5초마다 SSE comment (`: hb`) 발사 → 프록시 idle timeout 회피.

---

## 13. 운영·확장 노트

### 13-1. ENABLE_FEATURE_B 플래그

`.env` 또는 docker compose env:
```
ENABLE_FEATURE_B=true
```
이면 backend 부팅 시 `DraftPipeline` 자동 초기화. `false` 면 `/api/draft/diagnose` 의 pipeline 체크가 fail.

### 13-2. 양식 업로드 한도

```python
UPLOAD_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
UPLOAD_MAX_TEXT_CHARS = 30000       # LLM 토큰 보호
```
파일 자체는 메모리에서 추출 후 즉시 폐기 — 서버에 영속 저장 안 됨.

### 13-3. 성능 — 응답 시간 목표

| 작업 | 목표 | 현재 |
|---|---|---|
| `/api/draft/doc-types` | < 100ms | ~30ms |
| `/api/draft/cc/recommend` | < 200ms | ~80ms |
| `/api/draft/quality/score` | < 500ms | ~200-400ms |
| `/api/draft/stream-v2` 첫 토큰 | < 2s | ~1-3s (Ollama 콜드 시 5-10s) |
| `/api/draft/export` (docx) | < 1s | ~200-500ms |

### 13-4. 향후 확장

- [ ] **양식 자동 학습** — 사용자가 자주 쓰는 양식을 fewshot_rag 인덱스에 자동 추가
- [ ] **다국어 (영중일)** — 현재 한국어 우선 + OEM 영문. 일본어·중국어 미고려
- [ ] **음성 입력** — Web Speech API → 마이크로 요청 입력
- [ ] **협업 편집** — 두 사용자가 동시에 같은 문서 수정 (Supabase Realtime / WebSocket / CRDT 설계 필요)
- [ ] **Slack 통합** — Slack 슬래시 커맨드 `/ajin draft` 로 초안 생성

---

## 14. 자주 묻는 질문 (FAQ)

**Q1. 기본 문서 유형 외에 새 양식을 추가하려면?**
> `features/draft/doc_type_config.py` 의 `INTERNAL_DOC_TYPES` 또는 `EXTERNAL_DOC_TYPES` dict 에 새 항목 추가 + `prompts/` 에 시스템 프롬프트 .txt 파일 작성. backend 재기동 필요.

**Q2. 사내 임원에게 보내는 메일인데 Gemini 에 정보가 새지 않을까요?**
> 안 새도록 설계되었습니다 (§12 참조). `FEATURE_B_BLOCK_GEMINI=true` 가 기본이라 Gemini 요청은 자동으로 사내 Ollama 로 다운그레이드됩니다. SSE 이벤트로 사용자에게 알림.

**Q3. 양식 업로드한 .docx 의 표가 깨져요.**
> 현재 `_extract_docx()` 가 각 표 행을 탭 (`\t`) 구분 텍스트로 변환합니다. 복잡한 병합 셀·테두리는 보존 안 됨. 향후 `pandas.read_html()` 등으로 표 구조 보존 검토.

**Q4. PDF 가 스캔 이미지면 텍스트 추출이 안 돼요.**
> `_extract_pdf()` 는 텍스트 레이어만 읽습니다. 스캔 PDF 는 OCR (광학 문자 인식) 필요. 응답에 `warning: "스캔 이미지 가능성"` 표시.

**Q5. HWP (한컴) 파일은 왜 일부만 추출되나요?**
> HWP 5.0 의 본문은 보안 압축돼있어 별도 디코더 없이 전체 추출 어렵습니다. 미리보기(PrvText) 만 추출하므로 양식 구조 파악에는 충분하나 본문 길이가 짧을 수 있습니다. **HWPX (한컴 신 포맷) 권장.**

**Q6. CC 추천이 부정확해요.**
> `cc_recommender.py` 의 룰 테이블이 사내 협업 흐름과 다를 수 있습니다. 운영자가 해당 dict 를 직접 편집해서 부서·문서 유형별 매핑 조정 가능.

**Q7. 품질 점수가 매번 다르게 나와요.**
> `evaluate_document()` 자체는 결정적 (deterministic) 이지만, LLM 이 생성한 텍스트 자체가 매 호출마다 다르므로 점수도 변동합니다. 같은 텍스트로 두 번 채점하면 같은 점수.

**Q8. 빈 응답이 나와요 (스트리밍 안 옴).**
> 가장 흔한 원인 3가지:
> 1. Ollama 미가용 + Gemini 차단 ON → 자동 안전망 작동해도 토큰 0
> 2. `num_predict` 너무 작음 + qwen3 thinking 모드 → 답변 본문 비어있음 (think kwarg 도입으로 Phase B 에서 해결)
> 3. SSE 가 프록시에서 buffering → 16KB 패딩 + heartbeat 로 회피

---

## 15. 용어집

| 용어 | 풀이 |
|---|---|
| **SSE** | Server-Sent Events — 서버가 응답을 한 번에 안 보내고 조금씩 흘려보내는 방식 (ChatGPT 처럼 한 글자씩) |
| **RAG** | Retrieval-Augmented Generation — 관련 자료를 찾아서 LLM 에 함께 넣어주는 기법 |
| **Few-shot** | LLM 에 "이런 식 예시 3개" 를 함께 보여주는 학습법 |
| **Jinja2** | 빈칸이 있는 양식 (`{{ name }}`) 을 실제 값으로 채우는 도구 |
| **HWPX/HWP** | 한컴오피스 한글의 문서 포맷 (HWP=구형 OLE, HWPX=신형 OWPML) |
| **OWPML** | Open Word-processor Markup Language — 한컴이 만든 XML 기반 한글 포맷 |
| **OLE** | Object Linking and Embedding — 마이크로소프트가 만든 옛날 복합 문서 포맷 |
| **CC** | Carbon Copy — 이메일에서 참조 수신자 |
| **PPAP** | Production Part Approval Process — 양산 부품 승인 절차 (자동차 업계 표준) |
| **8D Report** | 8 Disciplines — 품질 문제 8단계 해결 보고서 (자동차 업계 표준) |
| **ECN** | Engineering Change Notice — 설계 변경 통지서 |
| **FMEA** | Failure Mode and Effects Analysis — 잠재 고장 영향 분석 |
| **MSA** | Measurement System Analysis — 측정 시스템 분석 |
| **SPC** | Statistical Process Control — 통계적 공정 관리 |
| **heartbeat** | "나 살아있어요" 신호 — 5초마다 한 번씩 보내서 연결 끊김 방지 |
| **Legacy Firestore shim** | Supabase/Postgres 전환 후 frontend bundle 에서 Firebase 쓰기를 막기 위해 남겨둔 호환 레이어 |

---

## 16. 변경 이력 (Feature B 한정)

| 버전 | 날짜 | 주요 변경 |
|---|---|---|
| Phase 1 | 2025-? | 기본 초안 생성 (`/generate`) |
| Phase 2-6 | 2025-? | 분류기·RAG·렌더러·세션 단계 도입 |
| v1.6 | 2025-? | 톤 설정 (`tone_config.py`), 템플릿 6 추가 |
| v3.0 | 2026-? | 감사 로깅 추가 — 누가 어떤 문서 만들었는지 추적 |
| v3.4 | 2026-04 | "친근체" 톤 추가, 스트리밍 중 네비게이션 차단 |
| v3.5 | 2026-04 | CSV/XLSX 내보내기 (7열), `tabular_exporter.py` 신규 |
| v3.6 | 2026-? | HWPX 정식 OWPML 출력, 양식 업로드 (`/upload-reference`), `/stream-v2` Few-shot RAG 통합 |
| Plan v1.0 | 2026-? | `format_shaper` 단일 진입점 (포맷별 reshape), Module B 5 진단 배너 |
| Day 8 Phase 1 | 2026-? | 5 신규 endpoint (doc-types / cc-recommend / quality-score / diff / stream-v2) |

상세 변경 이력은 [CHANGELOG.md](../CHANGELOG.md) 참조.

---

## 17. 한눈 요약 카드

```
┌────────────────────────────────────────────────────────────────┐
│  기능 B — 문서 작성 (Draft · Document Generator)              │
├────────────────────────────────────────────────────────────────┤
│  📝 빈 문서 앞 막막한 시간을 분 → 초로                       │
│                                                                │
│  💻 Backend     FastAPI + Jinja2 + LLMRouter (Ollama/Gemini)  │
│                  + python-docx/reportlab/pypdf/openpyxl/OWPML │
│  🖥  Frontend    React + Vite + TS + Zustand + useSSE          │
│                  + backend draft/version API                    │
│  🔐 보안         FEATURE_B_BLOCK_GEMINI=true (사내 데이터 보호)│
│                  + 자동 안전망 + 감사 로깅 + 5MB 업로드 한도 │
│  🌐 Endpoint    OpenAPI 기준 — docs/API.md 자동 산정          │
│                  generate/stream/export/doc-types 등          │
│  📊 데이터       documents + versions 2 테이블 (SQLite)       │
│  📋 문서 유형    doc_type_config 기준 23종, fallback 16종      │
│  🎵 톤           5단계 (격식 사내·외부/표준/친근/간결)        │
│  ⭐ 품질 5기준   structure/length/terminology/completeness/   │
│                  tone → A~F 등급                              │
│  📤 7포맷 출력   docx/pdf/hwpx/odt/xlsx/csv/txt + 클립보드   │
│  📁 코드          features/draft/ (21 모듈)                    │
│                  routes/draft.tsx                              │
└────────────────────────────────────────────────────────────────┘
```

---

## v4.0 변경 (2026-05-10) — 85% → 100% + LLM 모델 도움말

### 신규/강화 작업 7건

| ID | 작업 | 산출물 |
|---|---|---|
| **B1** | 템플릿 13종 실자산 + 카드 UX | 13개 신규 `.j2` 템플릿 (메타 헤더) + `TemplateCard.tsx` + `TemplatePreviewPopover.tsx` + `DocTypeMeta` 스키마 확장 (usage_hint / dept_recommend / var_metadata / example_output) |
| **B2** | 변수 입력 폼 (필수★ + 그룹 + placeholder) | `VariableField.tsx` + `VariableForm.tsx` (그룹별 섹션 + 진행률 바) — `var_metadata` 자동 생성 |
| **B3** | 대화형 부분 수정 (명시적 마커 파싱) | `features/draft/partial_editor.py` (Markdown / D1./[Section: …]/8D Step 패턴) + `POST /draft/scan-sections` + `POST /draft/partial-edit` + `DraftBodyView.tsx` 모달 |
| **B4** | 버전 관리 (사용자별 영속 + 단일 검토자) | `version_db.py` 스키마 확장 (status / reviewer_id / reviewed_at / review_note) + 4개 라우트 + `VersionTimeline.tsx` |
| **B5** | CC 추천 강화 (빈도 학습) | `cc_recommender.learn_frequent_cc` (draft_versions.db 의 template_vars.cc 빈출) + 4-tier (필수/권장/**자주 함께**/선택) + `CCTier` 확장 |
| **B6** | 메일 발송 인터페이스 + 첨부 추천 | `features/draft/mail_sender.py` (ABC + MockMailAdapter) + `attachment_recommender.py` (16 doc_type) + `POST /draft/mail/send` + `MailSendModal.tsx` |
| **H1** | LLM 모델 도움말 (사용자 의견 직접) | `MODEL_PROFILES` 9종에 `summary_ko / use_when_ko / avoid_when_ko / tags_ko` 추가 + `GET /api/models/catalog` + `GET /api/models/recommend` + `ModelComparisonCard.tsx` + `ModelHelpPopover.tsx` (ⓘ) + `/profile/llm` 비교 페이지 |

### 신규 백엔드 라우트 (10개)

```
GET  /api/models/catalog                               # H1 — 9 모델 메타 카탈로그
GET  /api/models/recommend?feature&department&...      # H1 — 휴리스틱 추천
POST /api/draft/scan-sections                          # B3 — 섹션 마커 파싱
POST /api/draft/partial-edit                           # B3 — 단일 섹션 LLM 재작성
POST /api/draft/versions                               # B4 — 버전 저장
GET  /api/draft/versions?scope=mine|review|all         # B4 — 사용자별 버전 목록
GET  /api/draft/versions/{id}                          # B4 — 단일 버전 본문
POST /api/draft/versions/{id}/review                   # B4 — submit/approve/reject
GET  /api/draft/mail/attachment-recommendations?doc_type
POST /api/draft/mail/send                              # B6 — Mock 발송
```

### 신규 프론트 자산

- 컴포넌트: `TemplateCard`, `TemplatePreviewPopover`, `VariableField`, `VariableForm`, `DraftBodyView`, `VersionTimeline`, `MailSendModal`, `ModelComparisonCard`, `ModelHelpPopover`
- 페이지: `routes/profile-llm.tsx` (9 모델 비교 + 휴리스틱 추천 + 부서·기능·요구 입력)
- API 클라이언트: `api/models.ts` (24h localStorage 캐시) + `api/draft.ts` 확장

### 디자인 시스템 v3.5 정렬

모든 신규 컴포넌트는 캐노니컬 v3.5 토큰만 사용:
- `lg-card` / `lg-card-tight` / `lg-pill` / `lg-tag` / `lg-state-pill` / `lg-btn` / `lg-eyebrow` / `lg-h2`
- 라운드: 16/12/2/999px tier (6/4/3/8 금지)
- 모달: glass treatment (`--glass-bg-strong` + `--glass-blur` + `--glass-saturate`)
- 영문 uppercase eyebrow + 한글 본문 페어
- 이모지 0건, lucide stroke-width 2

### 데이터 자산

| 자산 | 위치 | 비고 |
|---|---|---|
| 16종 Jinja2 템플릿 | `data/knowledge_base/templates/*.j2` | 메타 헤더 포함 |
| 9종 모델 메타 | `config.py` `MODEL_PROFILES` | 한국어 메타 (summary/use_when/avoid_when/tags) 보강 |
| 버전 DB | `data/draft_versions.db` | documents + versions(status/reviewer_id 컬럼 추가) |
| 첨부 추천 매핑 | `features/draft/attachment_recommender.py` | 16 doc_type (필수★ vs 선택) |

### 검증

- `tsc -b && vite build` ✓ (1.46s, 4,610 모듈)
- Python AST ✓ (mail_sender.py / attachment_recommender.py / partial_editor.py / version_db.py / cc_recommender.py)
- e2e 시나리오 5건 (신입 첫 문서 / 현직자 반복 / 모델 도움말 / 버전 관리 / 메일 발송)

---

문서 작성: 2026-05-10 | 본 문서는 향후 feature 변경 시 함께 갱신해주세요.
