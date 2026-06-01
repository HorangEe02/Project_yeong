# 기능 D — 법규 모니터링 / Compliance ★

> **이 문서는 누구를 위한 것인가요?**
> 개발자가 아닌 분 (안전보건팀·품질보증팀·구매팀·임원·법무 담당자) 도 끝까지 읽을 수 있도록 작성했습니다.
> 어려운 용어는 처음 등장할 때 _기울임_ 으로 표시하고 옆에 짧은 설명을 붙입니다.
> **P2 운영 기준**: 기본 활성 범위는 D1 변경감지·알림 MVP입니다. D2~D5 코드는 삭제하지 않고 보존하지만 feature flag가 꺼진 환경에서는 API가 404로 숨겨지고 프론트 화면에도 노출되지 않습니다.

---

## 1. 한 줄 요약

**"규제·법규 변경을 자동 감지하고 미확인 변경·알림 큐를 중심으로 대응 상태를 관리하는 D1 MVP"입니다.**

산업안전보건법·관세·EU CBAM·MSDS·ISO·OEM 품질 표준 등 **9 종류의 외부 규제** 를 수동 또는 스케줄로 크롤링하고, 변경이 감지되면 (1) 변경 DB 저장, (2) 영향 등급 분류, (3) HIGH/CRITICAL outbox 알림 큐잉, (4) 변경 피드 확인·상태 전이, (5) 알람 acknowledge 흐름까지 처리합니다. RAG, What-if, 결재·학습, 공급망 기능은 아래 feature flag가 켜진 경우에만 다시 노출합니다.

현재 release 기준의 공개 API 표면은 OpenAPI 산출물 기준 `compliance` 19개와 `notifications` 6개, 총 25개 endpoint입니다. `/api/feature-flags/d`는 화면과 브라우저 smoke가 같은 D1/D2-D5 상태를 읽기 위한 공통 flag endpoint입니다.

### P2 Feature Flag 기본값

| 플래그 | 기본값 | 기본 노출 |
|---|---:|---|
| `FEATURE_D_D1_ALERTS` | `true` | 변경감지, 크롤러 실행, 변경 피드, KPI, 알림 |
| `FEATURE_D_D2_RAG` | `false` | 검색, 법규 상세, 용어, 문서, 판례·계약 |
| `FEATURE_D_D3_WHATIF` | `false` | 시나리오/관세/What-if/비용 시뮬레이션 |
| `FEATURE_D_D4_WORKFLOW` | `false` | 티켓, Jira, 결재, 위임 룰, 학습, SOP, 보고서 |
| `FEATURE_D_D5_SUPPLY` | `false` | 협력사, 공급망 그래프, 산업 트렌드 |

### Release Gate 기준

Firebase 제거/Supabase 전환 release에서는 `make feature-d-release-check`로 다음 항목을 고정합니다.

- OpenAPI: `compliance=19`, `notifications=6`, `/api/feature-flags/d`와 D1 필수 route가 유지되어야 합니다.
- 공식 출처: 9개 크롤러의 공식 URL/API를 live probe합니다. `LAW_GO_KR_OC`, `CUSTOMS_API_KEY`가 없거나 네트워크/credential 실패가 있으면 strict release blocker입니다. D5 공급망 rollout stage까지 허용하는 run은 `DART_API_KEY`도 blocker입니다.
- 크롤러 SLA: 9개 D1 크롤러는 `official_source`, `cadence`, `max_stale_hours`, `fallback_allowed`, 공식 도메인 allowlist 정책을 가져야 하며 `/api/compliance/crawl/history/stats`의 `sla` 블록에 `fresh/stale/degraded/missing_credential` 상태를 노출합니다.
- HTTP posture: ECHA Candidate List는 browser-compatible profile fallback을 명시적으로 허용하고, UNECE WP.29는 `unece.org` 직접 403 시 UN ODS(`docs.un.org`, `documents.un.org`) 공식 문서 fallback을 허용합니다. 모든 공식 URL이 실패하면 blocker입니다.
- 출처/인용: 크롤러 결과는 `source_type`, `source`, `crawled_at`을 가져야 하며, 항목별 `reference_url` 또는 `url`은 공식 출처 도메인으로 제한합니다.
- curated fallback: credential 미설정 또는 HTTP 실패 시 `source_type=curated`와 errors/reason을 남깁니다. live 결과는 가능한 경우 HTTP status, ETag, Last-Modified를 보고서에 기록합니다.
- D2-D5 rollout: 기본 release는 D1만 열립니다. D2-D5가 켜진 상태는 `--allow-d2-d5`와 stage별 `--rollout-stage d2|d3|d4|d5` 없이 blocker입니다.
- 법적 판단 보호: AI 분류·요약·추천·digest는 참고용 disclaimer를 포함해야 하며, HIGH/CRITICAL 또는 법무 영향 변경은 독립 검토 기록 없이 `announced/done`으로 전환할 수 없습니다.
- 알림: 직접 발송 legacy 경로는 off이고, HIGH/CRITICAL은 outbox dispatcher와 Celery schedule을 통해 처리합니다.

---

## 2. 누가, 언제 쓰는가?

| 사용자 | 시나리오 | 기능 D 가 해주는 일 |
|---|---|---|
| **안전보건팀 부장** | 산안법 38조 개정 발효 임박 | 자동 감지 → CRITICAL 등급 → SMS 직보 + Slack + 영향 시설 (경산 본사 프레스 라인) 매핑 |
| **품질보증팀 과장** | OEM 품질 표준 (HKMC SQ) 변경 | 변경 카드 + 8D Report 작성 트리거 + 영향받는 부품번호 자동 추출 |
| **구매팀 대리** | EU CBAM 적용 → 협력사 영향 | 2차 협력사 그래프 + DART 공시 기반 후보 + 자가진단 메일 자동 발송 |
| **임원** | 분기 컴플라이언스 보고 | `/changes/exec-report` 한 번으로 분기 KPI + Top 변경 + 추세 그래프 |
| **법무 담당자** | 계약 영향 분석 | 변경 감지 시 사내 계약 corpus 검색 → 영향받는 계약 자동 리스트업 |
| **신입사원** | 산안법 학습 | 변경 발생 → 자동 학습 경로 생성 (5문제 퀴즈 + 단답 채점) → SCORM/xAPI export |
| **재무팀** | 관세 25% 시나리오 | What-if 시뮬레이션 → P&L 영향 + Scope 1/2/3 분리 |

---

## 3. 5 영역 구조 (큰 그림)

기능 D 는 5 개의 큰 영역이 **데이터 흐름** 으로 연결됩니다:

```
┌─────────────────────────────────────────────────────────────────┐
│ ① 크롤러 영역 (12 모듈)                                          │
│    9 외부 소스 → compliance.db (regulations + crawl_history)    │
│    ─ 국내법 / EU / US-CN / MSDS / ISO / APQP / OEM / EV / ESG  │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ ② 변경 감지 영역 (5 모듈)                                        │
│    이전 크롤링 vs 현재 비교 → regulation_changes 테이블          │
│    분류: ADD/MODIFY/REMOVE × 영향 등급 (CRITICAL/HIGH/MED/LOW) │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ ③ RAG · What-if 영역 (20 모듈)                                   │
│    • 규제 본문 Chroma 인덱싱 + 자연어 Q&A (Phase 2 LLM 라우팅)  │
│    • What-if 시뮬레이션 5종 (tariff/fx/chemical/labor/carbon)  │
│    • 신입 학습경로 + 퀴즈 + 단답 채점 (Phase 2 LLM)             │
│    • 임원 보고서 자동 생성                                       │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ ④ 알림 · 협업 영역 (11 모듈)                                     │
│    • Slack + SMS 라우팅 (등급별)                                │
│    • Jira 양방향 sync + 협업 티켓                                │
│    • 결재 워크플로 (Hancom 대안)                                │
│    • 권한 위임 룰 + 피드백 루프                                  │
│    • 판례 + 계약 영향 분석                                       │
└─────────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│ ⑤ 공급망 영역 (5 모듈)                                           │
│    • 1차/2차/3차 협력사 그래프                                   │
│    • DART 공시 기반 자동 발굴                                    │
│    • 자가진단 메일 + 대체 협력사 추천                            │
│    • 산업 트렌드 (외부 데이터 fetch)                             │
└─────────────────────────────────────────────────────────────────┘
                             ↓
                    임원 보고서 / 학습경로 export
```

각 영역이 다음 영역에 데이터를 공급하는 **파이프라인** 구조. 한 영역만 작동해도 가치 있고, 전체 연결되면 진가 발휘.

---

## 4. 기술 스택

### 4-1. 백엔드 (Backend, "서버 쪽 두뇌")

| 카테고리 | 기술 | 역할 |
|---|---|---|
| 언어 | **Python 3.11+** | 서버 + 크롤러 + 분석 |
| 웹 프레임워크 | **FastAPI** | endpoint 수는 [API 인덱스](API.md) 기준 |
| 크롤링 | **httpx + BeautifulSoup + lxml** | 9 외부 소스 |
| 벡터 DB | **ChromaDB** | 규제 본문 RAG 인덱싱 |
| 임베딩 | **bge-m3** (Ollama) | 한국어 + 다국어 의미 검색 |
| LLM (RAG) | **Ollama / Vertex Gemini** (Phase B) | 자연어 Q&A — 4 feature LLM 라우팅 |
| 데이터베이스 | **SQLite × 5** | compliance / compliance_changes / scenarios / suppliers / industry_trend |
| 알림 | **Slack Webhook + Naver SENS / Twilio SMS** | 등급별 라우팅 |
| 협업 | **Atlassian Jira REST API** | 양방향 sync |
| 외부 API | **DART OpenAPI** | 협력사 공시 |
| 외부 API | **대법원 종합법률정보 OpenAPI** | 판례 검색 |
| 외부 API | **open.law.go.kr / unipass.customs.go.kr** | 국내법·관세 |
| 시각화 | **Plotly** | 타임라인·네트워크·KPI 차트 |
| 학습 export | **SCORM 1.2 + xAPI (Tin Can)** | 외부 LMS 이식 |
| 인증 | **JWT** | 모든 endpoint 인증 필수 |

### 4-2. 프론트엔드 (Frontend)

| 카테고리 | 기술 | 역할 |
|---|---|---|
| 언어 | **TypeScript** | 화면 코드 |
| UI | **React** + **Vite** | SPA |
| 상태 관리 | **Zustand** | `useAuthStore` |
| 차트 | **Plotly.js** | 타임라인 / 네트워크 / KPI |
| 다운로드 | **DownloadActions** | DOCX/PDF/XLSX 내보내기 |

### 4-3. 인프라

| 항목 | 값 |
|---|---|
| 컨테이너 | Docker (multi-stage) |
| 크롤러 스케줄러 | cron / GitHub Actions / Cloud Scheduler |
| 알림 SLA | CRITICAL 5분 / HIGH 30분 / MED 2시간 / LOW 1일 |

### 4-4. 보안

- **JWT 인증** — 모든 `/api/compliance/...` 인증 필수
- **RBAC** — D1 조회는 로그인 사용자에게 허용하되, crawler 실행·scheduler 실행·ack/status transition은 `role_level>=3`, 법무 영향 최종 전환은 `role_level>=4`와 독립 검토를 요구합니다.
- **외부 API 키** — DART_API_KEY / JIRA_API_TOKEN / SENS / TWILIO 모두 `.env` (gitignored)
- **Phase B LLM 라우팅** — RAG·What-if·Quiz·Grade 4 feature 는 Vertex/Ollama 라우팅을 지원합니다. 운영 리전·데이터 사용 조건은 배포 프로젝트 정책으로 별도 검증합니다.
- **감사 로깅** — `audit.db` — 결재 / 변경 / Jira 모든 액션 기록

---

## 5. 백엔드 Endpoint (영역별 분류)

아래 목록은 기능 영역별 대표 endpoint 설명입니다. 현재 전체 endpoint 총수는 FastAPI OpenAPI 산출물인 [API 인덱스](API.md)를 기준으로 확인합니다.

### 5-1. 시나리오·시설·리스크 기반 (5개)

| 메서드 | 경로 | 용도 |
|---|---|---|
| `GET` | `/api/compliance/scenarios` | 사전 정의 시나리오 목록 |
| `GET` | `/api/compliance/facilities` | 사내 시설·공정 목록 |
| `GET` | `/api/compliance/risk/scores` | 시나리오별 리스크 점수 |
| `GET` | `/api/compliance/timeline` | 시간 축 변경 이벤트 |
| `GET` | `/api/compliance/network/{scenario_id}` | 영향 네트워크 (Plotly) |

### 5-2. 변경 감지 + 분류 (10개)

| 메서드 | 경로 | 용도 |
|---|---|---|
| `GET` | `/api/compliance/changes/recent` | 최근 변경 N건 |
| `GET` | `/api/compliance/changes/feed` | 무한 스크롤 변경 feed |
| `GET` | `/api/compliance/changes/kpi` | KPI 카드 (등급별 카운트) |
| `GET` | `/api/compliance/changes/extended-trend` | 12주 추세 |
| `POST` | `/api/compliance/changes/{id}/acknowledge` | 변경 확인 처리 |
| `POST` | `/api/compliance/changes/{id}/transition` | 상태 전이 (NEW→IN_PROGRESS→DONE) |
| `POST` | `/api/compliance/changes/{id}/correct` | 잘못 분류된 변경 수정 |
| `GET` | `/api/compliance/changes/correction-stats` | 수정 통계 (정확도 트래킹) |
| `GET` | `/api/compliance/changes/{id}/industry-context` | 변경 + 산업 트렌드 컨텍스트 |
| `GET` | `/api/compliance/changes/exec-report` | 임원 보고서 자동 생성 |

### 5-3. What-if 시뮬레이션 (3개)

| 메서드 | 경로 | 용도 |
|---|---|---|
| `POST` | `/api/compliance/whatif/simulate` | What-if 시뮬레이션 (5 시나리오 타입) |
| `GET` | `/api/compliance/whatif/baseline` | baseline 재무 데이터 |
| `POST` | `/api/compliance/whatif/simulate/accounting` | P&L line item 매핑 |
| `POST` | `/api/compliance/tariff/simulate` | 관세 시뮬 (전용) |

### 5-4. 협업 — 티켓 + Jira (5개)

| 메서드 | 경로 | 용도 |
|---|---|---|
| `POST` | `/api/compliance/changes/{id}/tickets` | 변경 → 협업 티켓 생성 |
| `GET` | `/api/compliance/tickets` | 티켓 목록 |
| `POST` | `/api/compliance/tickets/{id}/transition` | 티켓 상태 전이 |
| `GET` | `/api/compliance/jira/health` | Jira 연결 상태 |
| `POST` | `/api/compliance/jira/webhook` | Jira → 사내 sync 웹훅 |

### 5-5. 결재 워크플로 (3개)

| 메서드 | 경로 | 용도 |
|---|---|---|
| `POST` | `/api/compliance/approvals` | 결재 chain 생성 |
| `GET` | `/api/compliance/approvals/my` | 내 미결재 |
| `GET` | `/api/compliance/approvals/{id}` | 결재 상세 |

### 5-6. 권한 위임 룰 (3개)

| 메서드 | 경로 | 용도 |
|---|---|---|
| `GET` | `/api/compliance/delegation-rules` | 룰 목록 |
| `POST` | `/api/compliance/delegation-rules` | 룰 추가/수정/삭제 |
| `POST` | `/api/compliance/delegation-rules/dry-run` | 룰 적용 미리보기 |

### 5-7. 학습 경로 — 7개 (Phase 2 LLM 라우팅 영향)

| 메서드 | 경로 | 용도 |
|---|---|---|
| `POST` | `/api/compliance/learning-path` | 학습경로 생성 |
| `GET` | `/api/compliance/learning-path/my` | 내 진도 |
| `GET` | `/api/compliance/learning-path/mentor-queue` | 멘토 검토 대기 |
| `GET` | `/api/compliance/learning-path/{id}/quiz` | 퀴즈 미리보기 |
| `POST` | `/api/compliance/learning-path/{id}/quiz` | **퀴즈 응시** (Phase 2 `quiz_gen`) |
| `POST` | `/api/compliance/learning-path/{id}/review` | **단답 채점** (Phase 2 `short_answer_grade`) |
| `GET` | `/api/compliance/learning-path/{id}/export.scorm.zip` | SCORM 1.2 export |
| `GET` | `/api/compliance/learning-path/{id}/export.xapi.json` | xAPI export |

### 5-8. 판례 + 계약 영향 (5개)

| 메서드 | 경로 | 용도 |
|---|---|---|
| `POST` | `/api/compliance/case-law/index` | 외부 판례 corpus 인덱싱 |
| `GET` | `/api/compliance/changes/{id}/similar-cases` | 유사 판례 |
| `POST` | `/api/compliance/contracts/upload` | 사내 계약 업로드 |
| `GET` | `/api/compliance/contracts` | 계약 목록 |
| `GET` | `/api/compliance/changes/{id}/affected-contracts` | 영향받는 계약 |

### 5-9. 공급망 (8개)

| 메서드 | 경로 | 용도 |
|---|---|---|
| `GET` | `/api/compliance/suppliers/discovery/candidates` | DART 기반 후보 |
| `POST` | `/api/compliance/admin/suppliers/import` | 협력사 일괄 import |
| `GET` | `/api/compliance/suppliers` | 협력사 목록 |
| `GET` | `/api/compliance/suppliers/{id}` | 협력사 상세 |
| `GET` | `/api/compliance/changes/{id}/affected-suppliers` | 영향받는 협력사 |

### 5-10. 산업 트렌드 + Feedback Loop (2개)

| 메서드 | 경로 | 용도 |
|---|---|---|
| `POST` | `/api/compliance/industry-trend/fetch` | 외부 산업 데이터 fetch |
| `POST` | `/api/compliance/feedback-loop/apply` | 사람 수정 → 모델 재학습 시드 |

> **Phase 2 LLM 라우팅 영향:** 4 feature 중 3개가 이 도메인에 존재 — `rag_answer` (regulation_qa), `whatif_nl_route` (whatif_engine), `quiz_gen` + `short_answer_grade` (learning_path). 모두 Vertex Gemini 또는 사내 Ollama 자동 라우팅.

---

## 6. 데이터베이스 스키마

기능 D 는 **5 개의 SQLite DB** 를 사용합니다.

### 6-1. compliance.db — 외부 규제 마스터

#### crawl_history 테이블

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `crawl_id` | INTEGER PK | 크롤 회차 ID |
| `crawler_name` | TEXT | `iso_standards`, `domestic_laws`, `eu_regulation` 등 |
| `display_name` | TEXT | UI 표시명 |
| `json_filename` | TEXT | 백업 JSON 파일명 |
| `crawled_at` | TEXT | 크롤링 시각 (ISO 8601) |
| `total_count` | INTEGER | 수집된 항목 수 |
| `status` | TEXT | `success` / `partial` / `failed` |
| `errors` | TEXT | 오류 메시지 |
| `created_at` | TEXT | 생성 시각 |

#### regulations 테이블

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `reg_pk` | INTEGER PK | 내부 ID |
| `crawl_id` | INTEGER FK | 어느 크롤 회차에서 가져왔나 |
| `reg_id` | TEXT | 원본 ID (law_id, standard_id 등) |
| `name` | TEXT | 규제 이름 (영문/원어) |
| `name_ko` | TEXT | 한국어 이름 |
| `doc_type` | TEXT | `ISO`/`APQP`/`MSDS`/`DomesticLaw`/`EU`/`OEM`/`ESG`/`EV`/`Trade` 9 종 |
| `category` | TEXT | 세부 카테고리 |
| `authority` | TEXT | 발행 기관 |
| `compliance_status` | TEXT | 충족 / 부분충족 / 미충족 |
| `effective_date` | TEXT | 시행일 |
| `last_amended` | TEXT | 최종 개정일 |
| `content_json` | TEXT | 원본 항목 전체 JSON |
| `created_at` | TEXT | 생성 시각 |

**인덱스 4개:** `idx_reg_doc_type`, `idx_reg_crawl_id`, `idx_reg_status`, `idx_crawl_name`

### 6-2. compliance_changes.db — 변경 이력

#### regulation_changes 테이블

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | INTEGER PK | 변경 ID |
| `detected_at` | TEXT | 감지 시각 |
| `regulation_type` | TEXT | 9 종 |
| `change_type` | TEXT | `ADD` / `MODIFY` / `REMOVE` |
| `item_id` | TEXT | 해당 규제 ID |
| `item_title` | TEXT | 항목 제목 |
| `old_value` | TEXT | 변경 전 |
| `new_value` | TEXT | 변경 후 |
| `severity` | TEXT | `CRITICAL` / `HIGH` / `MEDIUM` / `LOW` / `info` |
| `acknowledged` | INTEGER | 확인 여부 (0/1) |

#### change_corrections 테이블 (사람 수정 → Feedback Loop)

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | INTEGER PK | 수정 ID |
| `change_id` | INTEGER FK | 어느 변경 |
| `field` | TEXT | 어느 필드 수정 |
| `old_value` / `new_value` | TEXT | 수정 전/후 |
| `user_id`, `user_role` | TEXT | 누가 |
| `corrected_at` | TEXT | 수정 시각 |
| `note` | TEXT | 사유 |

#### collab_tickets 테이블 (협업 티켓)

협업 티켓 상태·담당자·전이 이력. (자세한 컬럼은 `change_detector.py:107` 참조)

### 6-3. scenarios.db — What-if 시나리오 시드

`features/compliance/demo_scenario_engine.py` 가 관리. 사전 정의 시나리오 (산안법 85점 / 관세 78점 / REACH 52점 등 데모용) + Before/After JSON 자동 생성.

### 6-4. suppliers.db — 협력사 마스터

`features/compliance/supplier_compliance.py` 가 관리. 1차/2차/3차 협력사 정보 + HS 코드 + 자가진단 응답 + 대체 협력사 매핑.

### 6-5. industry_trend.db — 외부 산업 데이터

`features/compliance/industry_trend.py` 가 관리. 경쟁사·산업 트렌드 외부 fetch 결과 캐시.

### 6-6. ER 다이어그램 (간단)

```
crawl_history ──┐
                │ 1:N
                ▼
              regulations ◀── (규제 마스터)
                │
                │ 변경 비교
                ▼
              regulation_changes ──┐
                │                  │ 1:N
                │ 영향 분석        ▼
                ├─→ collab_tickets
                ├─→ change_corrections (사람 수정)
                ├─→ approval_chains
                └─→ learning_paths (학습)
                
suppliers ────────────┐
                       │ 영향 매핑
                       ▼
                regulation_changes
                       ▲
                       │
industry_trend ────────┘ (컨텍스트)
```

---

## 7. ① 크롤러 영역 (12 모듈)

매일/매주 외부 9 소스를 자동 수집해 `compliance.db` 의 `regulations` 테이블 갱신.

### 7-1. 9 외부 소스

| 소스 | 모듈 | 발행 기관 | 갱신 주기 |
|---|---|---|---|
| **국내 법규** | `domestic_law_crawler.py` | 국가법령정보센터 (open.law.go.kr) | 매일 |
| **EU 규제** | `eu_regulation_crawler.py` | EUR-Lex | 매주 |
| **미국·중국 통상** | `global_trade_crawler.py` | USTR / 中国海关 | 매주 |
| **MSDS** | `msds_crawler.py` | 안전보건공단 / EU REACH | 매주 |
| **ISO 국제규격** | `iso_crawler.py` | ISO.org | 분기 |
| **APQP** | `apqp_crawler.py` | AIAG (자동차 업계 표준) | 분기 |
| **OEM 품질** | `oem_quality_crawler.py` | 현대·기아 SQ 매뉴얼 | 변경 시 |
| **EV 배터리** | `ev_battery_crawler.py` | UN ECE R100 / GB 36276 | 분기 |
| **탄소·ESG** | `carbon_esg_crawler.py` | EU CBAM / KRX ESG | 매주 |

### 7-2. 공통 인프라

| 모듈 | 역할 |
|---|---|
| `base_crawler.py` | 모든 크롤러의 공통 골격 (`BaseCrawler` 클래스 — fetch / parse / save 패턴) |
| `_http.py` | httpx 헬퍼 + 재시도 + rate limit |
| `crawler.py` | 통합 진입점 (Phase 3) — 시나리오 로더 포함 |
| `compliance_db.py` | 크롤링 결과 → SQLite 저장 (v2.3 Phase 3) |

### 7-3. 크롤러 인증키

일반 런타임에서는 `.env` 의 다음 키가 있으면 정식 OpenAPI를 사용하고, 없으면 `source_type="curated"` 로 폴백합니다. 다만 release gate에서는 공식 출처 최신성을 확인해야 하므로 두 값이 없으면 blocker로 기록합니다. 로컬 release gate는 `.env.feature-d.local` 을 우선 읽고, 값 자체는 report/stdout에 출력하지 않습니다.
- `LAW_GO_KR_OC` — open.law.go.kr 사용자 ID
- `CUSTOMS_API_KEY` — unipass.customs.go.kr 인증키

### 7-4. 운영

```bash
# 수동 크롤링 트리거
docker compose exec backend python3 -m features.compliance.crawler --source iso

# 결과 확인
sqlite3 data/compliance.db "SELECT crawler_name, total_count, status FROM crawl_history ORDER BY crawled_at DESC LIMIT 10"
```

---

## 8. ② 변경 감지 영역 (5 모듈)

이전 크롤링 결과 vs 현재 결과 비교 → `regulation_changes` 테이블 생성.

### 8-1. 모듈

| 모듈 | 역할 |
|---|---|
| `text_change_detector.py` | **Phase 4** — 텍스트 diff 기반 변경 감지 |
| `change_detector.py` | 변경 + 영향 등급 + DB 저장 통합 진입점 |
| `change_classifier.py` | **MVP Stage 3+4+5** — ADD/MODIFY/REMOVE 분류 + 요약 + 매핑 + 등급 |
| `regulation_classifier.py` | 규제를 카테고리로 분류 |
| `legal_classifier.py` | **P1 D1** — 법무 5분류 + 벌칙 조항 자동 추출 |

### 8-2. 영향 등급 결정 로직

`change_classifier.py` 가 다음 5 요소를 종합:
1. **벌칙 강도** (`legal_classifier`) — 형사/과태료/행정처분
2. **영향 시설 수** (`plant_regulation_mapper`) — 1개 vs 6 시설 모두
3. **시행일까지 남은 시간** — 30일 미만이면 우선순위↑
4. **유사 변경 빈도** — 처음 보는 패턴이면 주의↑
5. **관련 부서 ai_relevance** (`config.py:DEPARTMENTS`) — `critical`/`high` 면 ↑

→ `CRITICAL` / `HIGH` / `MEDIUM` / `LOW` / `info` 결정.

### 8-3. UI

`/compliance` 페이지의 4 탭 구조 중 **법규 모니터** + **법규 업데이트**:
- 4개 KPI 메트릭 카드 (등급별 카운트)
- 무한 스크롤 변경 feed
- 변경 카드 클릭 → 영향 분석 drawer (시설·계약·협력사 매핑)
- 등급별 색상 (CRITICAL=빨강 / HIGH=주황 / MEDIUM=노랑 / LOW=회색)

---

## 9. ③ RAG · What-if 영역 (20 모듈) — 가장 큰 영역

자연어 Q&A·시뮬레이션·학습·임원 보고서·시각화.

### 9-1. RAG (자연어 Q&A) — 4 모듈

| 모듈 | 역할 |
|---|---|
| `regulation_indexer.py` | **P1 D4** — 규제 본문 ChromaDB 인덱싱 (bge-m3 임베딩) |
| `regulation_qa.py` | **P1 D4** — RAG 답변 생성 + 신입 풀이 모드 + Phase 2 라우팅 진입점 (`_call_llm`) |
| `regulation_context.py` | v2.5 — 기능 D 데이터를 기능 B LLM 프롬프트에 주입 (Cross-feature) |
| `regulation_exporter.py` | v2.6 Phase 3 — 규제를 DOCX/PDF 로 export |

**RAG 흐름:**
```
사용자 질문 "산안법 38조 의무는?"
    ↓
regulation_indexer.search() → top-5 청크 (ChromaDB)
    ↓
regulation_qa._build_prompt() → 시스템 프롬프트 + 청크 + 질문
    ↓
_call_llm(feature="rag_answer")  ← Phase 2 라우팅
    ↓ (Vertex Gemini 또는 Ollama qwen3.5:4b)
답변 + 인용 출처 + 신뢰도
```

### 9-2. What-if 시뮬레이션 — 6 모듈

5 시나리오 타입 지원: `tariff` / `fx` / `chemical` / `labor` / `carbon`.

| 모듈 | 역할 |
|---|---|
| `whatif_engine.py` | **자연어 → 시나리오 추출** (`_llm_extract`, Phase 2 `whatif_nl_route`) + 룰 폴백 |
| `tariff_simulator.py` | 관세 시뮬레이션 (HS 코드 × 협력사) |
| `cost_simulator.py` | **P2 D6** — 원가 영향 시뮬레이션 |
| `accounting_trace.py` | **P4 D17** — 시뮬 결과 → P&L line item 매핑 |
| `financial_baseline.py` | **P4 D17** — 재무 baseline + Scope 1/2/3 분리 |
| `risk_scorer.py` | 시나리오 종합 리스크 점수 |

**What-if 자연어 라우팅 예시:**
- 입력: "관세 25% 적용되면?"
- `_llm_extract()` → `{"scenario_type":"tariff","params":{"rate_pct":25}}`
- `tariff_simulator.run()` → 영향 부품·협력사·매출 변동
- `accounting_trace()` → P&L 영향 (영업이익 -₩X 억)

### 9-3. 시각화 — 4 모듈

| 모듈 | 역할 |
|---|---|
| `timeline_builder.py` | 시간 축 변경 이벤트 (Plotly) |
| `impact_network.py` | 영향 네트워크 그래프 |
| `impact_analyzer.py` | **Phase 5** — 영향도 분석기 |
| `plant_regulation_mapper.py` | v2.5 — 공장 ↔ 규제 자동 매핑 (6 시설 × 9 규제 종류) |

### 9-4. 학습 경로 — 3 모듈 (Phase 2 LLM 영향 ★)

| 모듈 | 역할 |
|---|---|
| `learning_path.py` | **P4 D15** — 신입 학습경로 큐레이션 + 퀴즈 + 단답 채점 (Phase 2 `quiz_gen` / `short_answer_grade`) |
| `lms_export.py` | **P5 §5** — 외부 LMS 호환 (SCORM 1.2 + xAPI) |
| `compliance_checker.py` | **Phase 7** — 규정 준수 자동 체크 |

**Phase 2 영향:**
- `_generate_quiz_llm()` → `_call_llm(feature="quiz_gen")` → Vertex Gemini Flash 또는 Ollama qwen3.5:4b
- `_grade_short_answer_llm()` → `_call_llm(feature="short_answer_grade")` → 동일

### 9-5. 데모 + 임원 보고서 + 시설 — 3 모듈

| 모듈 | 역할 |
|---|---|
| `demo_scenario_engine.py` | 데모 시나리오 3종 (산안법 85점 / 관세 78점 / REACH 52점) + Before/After JSON |
| `exec_report.py` | **P1 D2** — 임원 보고서 자동 생성 (분기 KPI + Top 변경 + 추세) |
| `facility_db.py` | 사내 6 시설 + 공정 데이터 |

---

## 10. ④ 알림 · 협업 영역 (11 모듈)

변경 감지 후 적시 알림 + 부서 간 협업 + 외부 시스템 연동.

### 10-1. 알림 — 4 모듈

| 모듈 | 역할 | 발송 대상 |
|---|---|---|
| `notify.py` | **P1 D3** — 통합 라우터 (Slack + SMS) | 등급별 자동 분기 |
| `notify_slack.py` | **MVP Stage 6** — Slack 라우팅 | 모든 등급 |
| `notify_sms.py` | **P1 D3** — SMS 직보 | CRITICAL 임원만 |
| `alert_generator.py` | **Phase 6** — 알림 메시지 생성 | 다국어 + 부서 맞춤 |

**SLA (Service Level Agreement) — 알림 도달 시간 목표:**

| 등급 | SLA | 채널 |
|---|---|---|
| **CRITICAL** | 5분 | Slack + SMS + 임원 직보 |
| **HIGH** | 30분 | Slack 부서 채널 + 담당자 멘션 |
| **MEDIUM** | 2시간 | Slack 부서 채널 |
| **LOW** | 1일 | 일일 다이제스트 메일 |

### 10-2. 협업 — 4 모듈

| 모듈 | 역할 |
|---|---|
| `collab_ticket.py` | **P3 D9** — 다중 부서 영향 변경의 책임자 자동 매핑 |
| `jira_sync.py` | **P5 §6** — Atlassian Jira REST API 양방향 sync |
| `approval_workflow.py` | **P5 §7** — 자체 결재 워크플로 (Hancom e-Approval 무료 대안) |
| `delegation_rules.py` | **P4 D14** — 권한 위임 룰 엔진 |

**Jira sync 동작:**
- 사내 collab_ticket 생성 → Jira issue 자동 생성 (`POST /api/compliance/changes/{id}/tickets`)
- Jira 측 상태 변경 → webhook (`POST /api/compliance/jira/webhook`) → 사내 ticket 동기화
- 양방향 동기 — 어느 쪽에서 작업해도 일관성 유지

### 10-3. 학습 + 분석 — 3 모듈

| 모듈 | 역할 |
|---|---|
| `feedback_loop.py` | **P2 D5** — 사람 수정 → 모델 재학습 시드 (change_corrections 활용) |
| `case_law_indexer.py` | **P2 D8** — 외부 판례 corpus 인덱싱 (대법원 OpenAPI) |
| `contract_indexer.py` | **P2 D7** — 사내 계약 영향 분석 |

---

## 11. ⑤ 공급망 영역 (5 모듈)

규제 변경 → 협력사 영향 자동 매핑 + 대체 협력사 추천 + DART 공시 기반 후보 발굴.

### 11-1. 모듈

| 모듈 | 역할 |
|---|---|
| `supplier_compliance.py` | **P2 D6** — 1차 통합 (협력사·HS·자가진단·시뮬·대체) |
| `supplier_discovery.py` | **P5 §10** — 2차 협력사 자동 발굴 (DART 공시 데이터) |
| `supplier_graph.py` | **P4 D16** — 2차/3차 협력사 그래프 |
| `supplier_recommender.py` | **P2 D6** — 대체 협력사 추천 |
| `industry_trend.py` | **P3 D11** — 경쟁사·산업 트렌드 외부 fetch |

### 11-2. DART (전자공시시스템) 통합

`supplier_discovery.py` 가 DART OpenAPI 로 다음 정보 수집:
- 협력사의 협력사 (2차) — 사업보고서 "주요 거래처" 항목
- 사업 영역 — KOSPI/KOSDAQ 분류
- 재무 안정성 — 매출·자산 추이
- 인수합병 이력 — 변동 위험

`.env` 의 `DART_API_KEY` 필수 (없으면 그래프 정적 데이터로 폴백).

### 11-3. 자가진단 메일 (P2 D6)

규제 변경 발생 시 → 영향받는 1차 협력사에게 자가진단 메일 자동 발송:
- SMTP (`SMTP_HOST`/`SMTP_USER`/`SMTP_PASSWORD` env)
- 미설정 시 `queued` 상태로 DB 만 적재 (graceful skip)

---

## 12. 프론트엔드 컴포넌트 트리

`/compliance` 외 별도 라우트 3개 (Glossary / Regulation / Search).

### 12-1. 4 라우트 구조

```
/compliance              — 메인 (4 탭)
/compliance/glossary     — 용어사전 (규제 용어 검색)
/compliance/reg/:id      — 규제 상세 + 본문 + 인용
/compliance/search       — 통합 검색 (RAG 진입점)
```

### 12-2. /compliance 메인 (4 탭)

```
<Compliance>
├─ 탭 ① "법규 모니터"
│  ├─ <KpiCards>          — 4 등급별 카운트
│  ├─ <ChangeFeed>        — 무한 스크롤
│  └─ <ChangeCard>        — 클릭 시 영향 분석 drawer
│
├─ 탭 ② "법규 업데이트"
│  ├─ <DemoScenarios>     — TOP-3 시나리오 카드
│  ├─ <ScenarioSimulator> — Before/After + 관세 시뮬
│  └─ <CrawlerStatus>     — 9 소스 마지막 크롤 결과
│
├─ 탭 ③ "사업장"
│  ├─ <PlantList>         — 6 시설
│  └─ <PlantRegulationMap>— 시설 × 규제 매트릭스
│
└─ 탭 ④ "법규 문서"
   ├─ <RegulationList>    — 9 doc_type 별 필터
   └─ <RegulationExport>  — DOCX/PDF 다운로드
```

### 12-3. 별도 라우트

| 라우트 | 주요 컴포넌트 | 백엔드 |
|---|---|---|
| `/compliance/glossary` | 용어 검색·정의 | RAG miss 시 폴백 |
| `/compliance/reg/:id` | 규제 상세 + 본문 + 인용 | `/api/compliance/regulations/...` |
| `/compliance/search` | 자연어 Q&A 진입점 | `/api/onboarding/chat` 의 `regulation_qa` 액션 |

---

## 13. 변경 → 영향 분석 흐름 (가장 핵심)

기능 D 의 본질. 변경 1건 발생 시 **자동으로 5 차원 영향** 매핑:

```
변경: "산안법 38조 개정 — 안전조치 의무 강화"
         │
         ▼
┌────────┴────────┐
│  영향 5 차원     │
└────────┬────────┘
         │
    ┌────┼────────────┬────────────┬────────────┬────────────┐
    │             │            │            │            │
    ▼             ▼            ▼            ▼            ▼
시설·공정      계약          협력사       부서          판례
6 시설        contracts     1·2·3차      27 부서        대법원
중 영향      indexer       graph         ai_relevance  종합법률정보
    │             │            │            │            │
    └─────────────┴────────────┴────────────┴────────────┘
                                   │
                                   ▼
                            collab_ticket 자동 생성
                                   │
                       ┌───────────┴───────────┐
                       ▼                       ▼
                   Jira 동기화              Slack/SMS 알림
                       │                       │
                       └───────────┬───────────┘
                                   ▼
                              결재 chain (P5 §7)
                                   │
                                   ▼
                              학습 경로 자동 (D15)
                                   │
                                   ▼
                              임원 보고서 (D2)
```

각 차원의 매핑 모듈:
- **시설·공정** → `plant_regulation_mapper.py`
- **계약** → `contract_indexer.py`
- **협력사** → `supplier_graph.py`
- **부서** → `delegation_rules.py` + `config.py:DEPARTMENTS.ai_relevance`
- **판례** → `case_law_indexer.py`

---

## 14. 운영·확장 노트

### 14-1. 환경변수 (`.env`, `.env.feature-d.local`)

```bash
# 외부 API
DART_API_KEY=...                   # 전자공시 (협력사 발굴)
LAW_GO_KR_OC=...                   # 국가법령정보센터
CUSTOMS_API_KEY=...                # 관세청 unipass

# 알림
SLACK_WEBHOOK_URL=...
SMS_PROVIDER=sens                  # sens (한국) | twilio (해외)
SENS_ACCESS_KEY=...
SENS_SECRET_KEY=...
SENS_SERVICE_ID=...
SENS_FROM_NUMBER=...

# Jira
JIRA_API_TOKEN=...
JIRA_BASE_URL=https://...

# 자가진단 메일
SMTP_HOST=...
SMTP_USER=...
SMTP_PASSWORD=...

# Phase B (선택)
LLM_PROVIDER=vertex
VERTEX_PROJECT_ID=ajin-compliance
```

### 14-2. 크롤러 스케줄링

운영자 결정 사항. 권장:
- 매일 02:00 — 국내법 + EU + MSDS + 통상
- 매주 일 03:00 — ISO + APQP + OEM + EV + ESG
- 변경 감지는 매 크롤링 직후 자동 실행

cron 예시:
```cron
0 2 * * *  cd /path && docker compose exec backend python3 -m features.compliance.crawler --daily
0 3 * * 0  cd /path && docker compose exec backend python3 -m features.compliance.crawler --weekly
```

### 14-3. 성능 — 응답 시간 목표

| 작업 | 목표 | 비고 |
|---|---|---|
| `/changes/recent` | < 200ms | 인덱스 활용 |
| `/changes/feed` (page 0) | < 300ms | 50건 |
| `/changes/{id}/affected-suppliers` | < 500ms | 그래프 BFS |
| `/whatif/simulate` | < 2s | LLM 추출 + 시뮬 |
| `/learning-path/{id}/quiz` | < 5s | LLM 생성 (Phase 2) |
| `/changes/exec-report` | < 10s | 분기 데이터 집계 + 차트 |

### 14-4. 향후 확장

- [ ] **AI 우선순위 큐** — CRITICAL 누적 시 임원에게 자동 회의 제안
- [ ] **음성 알림** — 산안법 발효 임박 시 임원에게 음성 통화
- [ ] **국제 사례 DB** — 일본·중국 판례 corpus 추가
- [ ] **법무법인 협업** — 외부 자문 자동 의뢰 (변경 등급 CRITICAL)
- [ ] **블록체인 감사** — 결재·변경 이력 변조 방지 (Hyperledger)

---

## 15. 자주 묻는 질문 (FAQ)

**Q1. 9 소스 외에 새 규제 소스를 추가하려면?**
> `features/compliance/` 에 `<source>_crawler.py` 작성 (`base_crawler.py:BaseCrawler` 상속) + `compliance_db.py` 의 `doc_type` 에 새 값 추가. backend 재기동.

**Q2. CRITICAL 알림이 너무 자주 와요.**
> `change_classifier.py` 의 등급 기준을 운영자가 조정 가능. 또는 `delegation_rules` 에서 특정 부서·시설은 `LOW` 로 다운그레이드.

**Q3. 협력사 그래프가 비어있어요.**
> DART_API_KEY 미설정 시 정적 데이터만 표시. 정식 사용 시 `/api/compliance/admin/suppliers/import` 로 1차 협력사 일괄 import 필요.

**Q4. 학습 경로 퀴즈가 어색해요.**
> Phase 2 LLM 라우팅 적용 — quiz_gen 모델이 호스트 Ollama 의 `qwen3.5:4b` 또는 Vertex Gemini. 모델 변경 시 `LLM_MODEL_QUIZ` env 1줄 변경.

**Q5. Jira 동기화가 안 돼요.**
> `/api/compliance/jira/health` 로 연결 상태 확인. JIRA_API_TOKEN 만료·webhook URL 미등록 가능성. Jira Console 에서 webhook 등록 (`/api/compliance/jira/webhook`).

**Q6. What-if 시뮬레이션 결과가 가짜처럼 보여요.**
> 데모용 baseline 사용 시 발생. `financial_baseline.py` 가 실제 P&L 데이터 연결 시 정확. 사내 ERP 연동 필요.

**Q7. 임원 보고서가 너무 길어요.**
> `exec_report.py` 의 템플릿 수정 가능. 또는 `/changes/exec-report?period=quarter&top=5` 로 항목 수 제한.

**Q8. 판례 검색이 정확도가 낮아요.**
> 대법원 종합법률정보 OpenAPI 의 한계와 인덱싱 corpus 품질 영향을 받습니다. `features/compliance/infra/case_law_indexer.py` 의 ChromaDB 인덱싱 경로는 구현되어 있으며, 운영자는 외부 corpus 적재와 유사도 임계값을 조정해 검색 품질을 높여야 합니다.

---

## 16. 용어집

| 용어 | 풀이 |
|---|---|
| **RAG** | Retrieval-Augmented Generation — 검색 + LLM 답변 결합 |
| **ChromaDB** | 벡터 DB — 의미 기반 검색 |
| **bge-m3** | 한국어·다국어 임베딩 모델 |
| **What-if** | 가정 시나리오 시뮬레이션 (관세·환율 등) |
| **MSDS** | Material Safety Data Sheet — 물질안전보건자료 |
| **APQP** | Advanced Product Quality Planning — 사전 제품 품질 계획 |
| **PPAP** | Production Part Approval Process — 양산 부품 승인 |
| **8D Report** | 8 Disciplines — 품질 문제 8단계 해결 |
| **ECN** | Engineering Change Notice — 설계 변경 통보 |
| **CBAM** | Carbon Border Adjustment Mechanism — EU 탄소국경조정제도 |
| **REACH** | EU 화학물질 등록·평가·승인·제한 규정 |
| **HS 코드** | Harmonized System — 국제 무역 품목 분류 |
| **DART** | 전자공시시스템 (Data Analysis, Retrieval and Transfer) |
| **OpenAPI** | 외부 시스템 통신 표준 |
| **SCORM** | Sharable Content Object Reference Model — 학습 콘텐츠 표준 |
| **xAPI** | Experience API (Tin Can) — 학습 경험 추적 표준 |
| **Scope 1/2/3** | 직접 배출 / 간접 에너지 / 가치사슬 배출 (탄소 회계) |
| **P&L** | Profit & Loss — 손익계산서 |
| **SLA** | Service Level Agreement — 서비스 수준 협약 |
| **webhook** | 외부 시스템 변경 시 자동 호출되는 callback URL |
| **인덱싱** | 검색을 빠르게 하기 위해 미리 처리하는 작업 |
| **그래프** | 노드(점) + 엣지(선) 로 관계를 표현하는 자료구조 |

---

## 17. 변경 이력 (Feature D 한정)

| 버전 | 날짜 | 주요 변경 |
|---|---|---|
| MVP Stage 1-6 | 2025-? | 크롤러 + 변경 감지 + Slack 알림 기본 |
| P1 D1-D4 | 2025-? | 법무 분류 / 임원 보고서 / SMS / RAG 인덱싱 |
| P2 D5-D8 | 2025-? | Feedback Loop / 공급망 통합 / 계약 영향 / 판례 |
| P3 D9-D11 | 2026-? | 협업 티켓 / What-if 자연어 / 산업 트렌드 |
| P4 D14-D17 | 2026-? | 권한 위임 / 학습 경로 / 협력사 그래프 / What-if 정밀화 |
| P5 §5-§10 | 2026-? | LMS export / Jira sync / 결재 워크플로 / 협력사 발굴 |
| v2.5 | 2026-? | plant_regulation_mapper / regulation_context (Cross-feature) |
| v2.6 Phase 3 | 2026-? | regulation_exporter (DOCX/PDF) |
| v3.4 | 2026-04 | demo_scenario_engine 데모 + 챗봇 연동 |
| v3.5 | 2026-04 | 4탭 구조 / CSV 내보내기 / 인코딩 안정성 |
| Phase 2 (이번 세션) | 2026-05 | LLM 풀 라우팅 — rag_answer / quiz_gen / short_answer_grade / whatif_nl_route |
| Phase B 검증 | 2026-05 | Vertex/Ollama A/B 검증 및 feature별 LLM 라우팅 |

상세 변경 이력은 [CHANGELOG.md](../CHANGELOG.md) 참조.

---

## 18. 한눈 요약 카드

```
┌──────────────────────────────────────────────────────────────────┐
│  기능 D — 법규 모니터링 / Compliance ★                          │
├──────────────────────────────────────────────────────────────────┤
│  📜 9 외부 규제 → 변경 감지 → 영향 분석 → 알림·협업·학습        │
│                                                                  │
│  💻 Backend     FastAPI + ChromaDB + bge-m3 + LLMRouter         │
│                  + Plotly + httpx + BeautifulSoup               │
│                  + Jira REST + Slack/SMS + DART OpenAPI         │
│  🖥  Frontend    React + Vite + TS + Plotly.js                   │
│  🔐 보안         JWT + RBAC + feature별 LLM 라우팅 정책         │
│  🌐 Endpoint    OpenAPI 기준 — docs/API.md 자동 산정             │
│                                                                  │
│  📊 5 SQLite DB  compliance / compliance_changes / scenarios /  │
│                  suppliers / industry_trend                      │
│                                                                  │
│  📁 56 Module — 5 영역                                           │
│   ① 크롤러 (12)        — 9 외부 소스 자동 수집                   │
│   ② 변경 감지 (5)       — diff + 등급 분류 (CRIT/HIGH/MED/LOW) │
│   ③ RAG·What-if (20)   — 자연어 Q&A + 시뮬 5종 + 학습 + 보고서│
│   ④ 알림·협업 (11)      — Slack/SMS + Jira + 결재 + 판례·계약  │
│   ⑤ 공급망 (5)          — 1·2·3차 그래프 + DART 발굴 + 대체    │
│                                                                  │
│  ⚡ Phase 2 영향 — 4 LLM feature 중 3개가 이 도메인              │
│   • rag_answer          — regulation_qa.answer_question          │
│   • whatif_nl_route     — whatif_engine._llm_extract             │
│   • quiz_gen            — learning_path._generate_quiz_llm       │
│   • short_answer_grade  — learning_path._grade_short_answer_llm │
│                                                                  │
│  🚦 SLA          CRITICAL 5분 / HIGH 30분 / MED 2h / LOW 1일    │
│  📚 학습 export  SCORM 1.2 + xAPI (외부 LMS 호환)               │
└──────────────────────────────────────────────────────────────────┘
```

---

문서 작성: 2026-05-10 | 본 문서는 향후 feature 변경 시 함께 갱신해주세요.
