# AJIN AI Assistant API — OpenAPI 인덱스

> FastAPI 앱에서 생성한 OpenAPI 3.1.0 spec의 사람-친화 인덱스.
> 원본 머신-리더블 spec: [`openapi.json`](openapi.json) (469 KB).

- **API 버전:** 1.1.0
- **OpenAPI 버전:** 3.1.0
- **총 path:** **215**
- **총 endpoint:** **229**

---

## 재생성 방법

기본 재생성 경로는 호스트 `.venv`에서 FastAPI 앱을 import한 뒤 `app.openapi()` 결과를 저장하는 방식입니다. 서버를 띄우거나 lifespan 서비스를 시작하지 않습니다.

```bash
make openapi-docs
make openapi-docs-check
```

---

## Swagger UI / ReDoc 접근 방법

FastAPI가 두 가지 인터랙티브 문서 UI를 자동 생성합니다. 단, 본 프로젝트는 nginx-rp가 `/api/*`만 backend로 프록시하므로 외부에서는 직접 접근할 수 없습니다.

### 1. 컨테이너 안에서 직접

```bash
# Swagger UI (인터랙티브 — endpoint 호출도 가능)
docker compose exec backend curl -s http://localhost:8080/docs | head -20

# OpenAPI JSON spec
docker compose exec backend curl -s http://localhost:8080/openapi.json > /tmp/spec.json

# 컨테이너 외부 (호스트 macOS)로 복사
docker compose cp backend:/tmp/spec.json ./docs/openapi.json
```

### 2. backend 컨테이너 직접 노출 (개발자용)

docker-compose.yml의 backend service에 `ports: ["8081:8080"]` 추가 후:
- http://localhost:8081/docs (Swagger UI)
- http://localhost:8081/redoc (ReDoc)
- http://localhost:8081/openapi.json (raw spec)

### 3. 외부 도구로 spec import

`docs/openapi.json`을 다음 도구에 업로드:
- **Postman** — Import → File → openapi.json (모든 endpoint 자동 컬렉션)
- **Insomnia** — Import → openapi.json
- **Swagger Editor** (https://editor.swagger.io/) — 온라인 뷰어
- **VS Code OpenAPI 확장** — 인라인 미리보기

---

## Feature 별 endpoint 분포

| Feature | 도메인 | Tag | endpoint 수 | 상세 문서 |
|---|---|---|---:|---|
| **A** | 검색·조직도 | `search`, `employee`, `directory` | **15** | [docs/FEATURE_A_SEARCH.md](FEATURE_A_SEARCH.md) |
| **B** | 문서 작성 | `draft` | **27** | [docs/FEATURE_B_DRAFT.md](FEATURE_B_DRAFT.md) |
| **C** | AI 업무 도우미 | `onboarding`, `scenarios`, `feature-flags` | **39** | [docs/FEATURE_C_ONBOARDING.md](FEATURE_C_ONBOARDING.md) |
| **D** | 법규 모니터링 | `compliance`, `notifications` | **25** | [docs/FEATURE_D_COMPLIANCE.md](FEATURE_D_COMPLIANCE.md) |
| **E** | 인사·관리 | `admin`, `admin-scenarios`, `auth`, `idp` | **74** | [docs/FEATURE_E_ADMIN.md](FEATURE_E_ADMIN.md) |
| **F** | 설비·SPC | `equipment` | **19** | [docs/FEATURE_F_EQUIPMENT.md](FEATURE_F_EQUIPMENT.md) |
| **공통** | 인프라·헬스·모델 | `dashboard`, `models`, `export`, `health`, `me`, `slack`, `untagged`, `feedback`, `live-alarms`, `storage` | **30** | — |
| 합계 | | | **229** | |

---

## 태그 별 endpoint 전체 (229개)

### `search` (A — 9개)

> Access: 로그인 필요.

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/search/capabilities` | Get Search Capabilities |
| `POST` | `/api/search/documents` | Search Documents |
| `GET` | `/api/search/drawings` | List Drawings |
| `GET` | `/api/search/drawings/captions` | List Drawing Captions |
| `POST` | `/api/search/drawings/captions` | Add Drawing Caption |
| `GET` | `/api/search/drawings/{drawing_id}` | Get Drawing Detail |
| `POST` | `/api/search/intent` | Classify Palette Intent |
| `POST` | `/api/search/summarize` | Summarize Results |
| `POST` | `/api/search/vision-query` | Vision Query Search |

### `employee` (A — 5개)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/employee/by-department` | List By Department |
| `GET` | `/api/employee/list` | List Employees Paginated |
| `GET` | `/api/employee/org-tree` | Get Org Tree |
| `POST` | `/api/employee/search` | Search Employee |
| `GET` | `/api/employee/{employee_id}/extras` | Get Employee Extras |

### `directory` (A — 1개)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/directory/tree` | Directory Tree |

### `draft` (B — 27개)

> Access: 로그인 필요. 단, `/api/draft/diagnose`는 `SYS_ADMIN(L5)` 전용.

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/draft/cc/recommend` | Recommend Cc |
| `GET` | `/api/draft/diagnose` | Diagnose Draft |
| `POST` | `/api/draft/diff` | Doc Diff |
| `GET` | `/api/draft/doc-types` | Get Doc Types |
| `POST` | `/api/draft/export` | Export Draft |
| `POST` | `/api/draft/generate` | Generate Draft Stream |
| `POST` | `/api/draft/generate-pipeline` | Generate Draft Pipeline |
| `GET` | `/api/draft/mail/attachment-recommendations` | Attachment Recommendations |
| `POST` | `/api/draft/mail/send` | Send Mail |
| `POST` | `/api/draft/partial-edit` | Partial Edit |
| `GET` | `/api/draft/prefs/me` | Get My Draft Prefs |
| `PUT` | `/api/draft/prefs/me` | Update My Draft Prefs |
| `POST` | `/api/draft/quality/score` | Quality Score |
| `POST` | `/api/draft/recommend` | Recommend Doc Types |
| `POST` | `/api/draft/recommend/aggregate-run` | Trigger Aggregate Run |
| `GET` | `/api/draft/recommend/by-dept` | Recommend By Dept |
| `GET` | `/api/draft/recommend/personal` | Recommend Personal |
| `POST` | `/api/draft/scan-sections` | Scan Sections |
| `POST` | `/api/draft/stream` | Draft Stream |
| `POST` | `/api/draft/stream-v2` | Draft Stream V2 |
| `GET` | `/api/draft/templates` | List Templates |
| `GET` | `/api/draft/templates/{template_id}/prefill` | Get Template Prefill |
| `POST` | `/api/draft/upload-reference` | Upload Reference |
| `GET` | `/api/draft/versions` | List Draft Versions |
| `POST` | `/api/draft/versions` | Save Draft Version |
| `GET` | `/api/draft/versions/{version_id}` | Get Draft Version |
| `POST` | `/api/draft/versions/{version_id}/review` | Review Draft Version |

### `onboarding` (C — 31개)

> Access: 로그인 필요. `/api/onboarding/health`, `/quick-questions`, SOP, upload, vision/document analyzer도 동일하게 보호. `/api/feature-flags/c`만 프론트 부팅용 공개 read-only이며 민감 운영값은 포함하지 않는다. 부서별 vision/document analyzer는 `FEATURE_C_ANALYZERS_ENABLED=true`일 때만 동작하고 기본값은 `403 analyzer_disabled`.

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/onboarding/actions/match` | Match Action |
| `GET` | `/api/onboarding/badges/me` | Get My Badges |
| `POST` | `/api/onboarding/chat` | Onboarding Chat |
| `POST` | `/api/onboarding/chat/vision` | Onboarding Vision |
| `POST` | `/api/onboarding/document/contract` | Document Contract |
| `POST` | `/api/onboarding/document/esg` | Document Esg |
| `POST` | `/api/onboarding/document/financial-statement` | Document Financial Statement |
| `POST` | `/api/onboarding/document/resume` | Document Resume |
| `POST` | `/api/onboarding/download` | Download Response |
| `GET` | `/api/onboarding/health` | Onboarding Health |
| `GET` | `/api/onboarding/leaderboard/{dept}` | Get Leaderboard |
| `GET` | `/api/onboarding/quick-questions` | Get Quick Questions Endpoint |
| `POST` | `/api/onboarding/quiz/result` | Post Quiz Result |
| `POST` | `/api/onboarding/scenarios/match` | Match Scenario |
| `GET` | `/api/onboarding/sop/list` | List Sops |
| `POST` | `/api/onboarding/sop/progress` | Post Sop Progress |
| `GET` | `/api/onboarding/sop/{sop_id}` | Get Sop Detail |
| `GET` | `/api/onboarding/sop/{sop_id}/quiz` | Get Sop Quiz |
| `POST` | `/api/onboarding/upload` | Upload File |
| `POST` | `/api/onboarding/vision/5s` | Vision 5S |
| `POST` | `/api/onboarding/vision/business-card` | Vision Business Card |
| `POST` | `/api/onboarding/vision/cad-verify` | Vision Cad Verify |
| `POST` | `/api/onboarding/vision/certificate` | Vision Certificate |
| `POST` | `/api/onboarding/vision/defect` | Vision Defect |
| `POST` | `/api/onboarding/vision/error-log` | Vision Error Log |
| `POST` | `/api/onboarding/vision/incident` | Vision Incident |
| `POST` | `/api/onboarding/vision/inventory-receive` | Vision Inventory Receive |
| `POST` | `/api/onboarding/vision/msds-label` | Vision Msds Label |
| `POST` | `/api/onboarding/vision/po` | Vision Po |
| `POST` | `/api/onboarding/vision/receipt` | Vision Receipt |
| `POST` | `/api/onboarding/vision/rfq` | Vision Rfq |

### `scenarios` (C — 5개)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/scenarios` | List User Scenarios |
| `GET` | `/api/scenarios/favorites` | List My Favorites |
| `POST` | `/api/scenarios/{scenario_id}/favorite` | Add To Favorites |
| `PUT` | `/api/scenarios/{scenario_id}/favorite` | Update Favorite Note Endpoint |
| `DELETE` | `/api/scenarios/{scenario_id}/favorite` | Remove From Favorites |

### `feature-flags` (C — 3개)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/feature-flags/c` | Get Feature C Flags |
| `GET` | `/api/feature-flags/d` | Get Feature D Flags |
| `GET` | `/api/feature-flags/firebase-cost` | Get Firebase Cost Flags |

### `compliance` (D — 19개)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/compliance/alarms/recent` | Recent Compliance Alarms |
| `GET` | `/api/compliance/alarms/stream` | Stream Compliance Alarms |
| `POST` | `/api/compliance/alarms/{alarm_id}/ack` | Acknowledge Compliance Alarm |
| `GET` | `/api/compliance/changes/feed` | Get Change Feed |
| `GET` | `/api/compliance/changes/kpi` | Get Change Kpi Endpoint |
| `GET` | `/api/compliance/changes/recent` | Get Recent Changes Endpoint |
| `POST` | `/api/compliance/changes/{change_id}/acknowledge` | Acknowledge Change Endpoint |
| `POST` | `/api/compliance/changes/{change_id}/transition` | Transition Change Status |
| `GET` | `/api/compliance/crawl/history` | List Crawl Runs |
| `GET` | `/api/compliance/crawl/history/stats` | Crawl History Stats |
| `GET` | `/api/compliance/crawl/results` | List Crawl Results |
| `GET` | `/api/compliance/crawl/results/{name}` | Get Crawl Result Detail |
| `GET` | `/api/compliance/crawl/results/{name}/download` | Download Crawl Result |
| `POST` | `/api/compliance/crawl/run-all` | Run All Crawlers |
| `POST` | `/api/compliance/crawl/run/{name}` | Run Single Crawler |
| `POST` | `/api/compliance/digest/run-now` | Run Digest Now |
| `GET` | `/api/compliance/facilities` | List Facilities |
| `GET` | `/api/compliance/scheduler/jobs` | List Scheduler Jobs |
| `POST` | `/api/compliance/scheduler/trigger/{job_id}` | Trigger Scheduler Job |

### `notifications` (D — 6개)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/notifications/channels` | List Active Channels |
| `POST` | `/api/notifications/dispatch` | Trigger Dispatch |
| `GET` | `/api/notifications/log` | List Log |
| `GET` | `/api/notifications/me` | Get My Prefs |
| `PUT` | `/api/notifications/me` | Update My Prefs |
| `POST` | `/api/notifications/test` | Send Test Notification |

### `admin` (E — 48개)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/admin/analytics/dau` | Analytics Dau |
| `GET` | `/api/admin/analytics/heatmap` | Analytics Heatmap |
| `GET` | `/api/admin/analytics/roi` | Analytics Roi |
| `GET` | `/api/admin/analytics/usage` | Analytics Usage |
| `GET` | `/api/admin/audit/anomaly/feed` | Audit Anomaly Feed |
| `GET` | `/api/admin/audit/bq/department-dau` | Audit Bq Department Dau |
| `GET` | `/api/admin/audit/bq/hour-distribution` | Audit Bq Hour Distribution |
| `GET` | `/api/admin/audit/bq/summary` | Audit Bq Summary |
| `GET` | `/api/admin/audit/dashboard` | Audit Dashboard |
| `GET` | `/api/admin/audit/export/siem` | Export Siem Format |
| `GET` | `/api/admin/audit/timeline` | Audit Timeline |
| `GET` | `/api/admin/departments` | List Departments |
| `POST` | `/api/admin/employee-id/preview` | Preview Employee Id |
| `GET` | `/api/admin/hr/gender` | Hr Gender |
| `GET` | `/api/admin/hr/headcount` | Hr Headcount |
| `GET` | `/api/admin/hr/matrix` | Hr Matrix |
| `GET` | `/api/admin/hr/overseas` | Hr Overseas |
| `GET` | `/api/admin/hr/summary` | Hr Summary |
| `GET` | `/api/admin/hr/tenure` | Hr Tenure |
| `POST` | `/api/admin/permissions/approve/executive/{request_id}` | Approve Permission Executive |
| `POST` | `/api/admin/permissions/approve/security/{request_id}` | Approve Permission Security |
| `GET` | `/api/admin/permissions/history` | Get Permission History |
| `GET` | `/api/admin/permissions/list` | List Permissions Endpoint |
| `POST` | `/api/admin/permissions/preview` | Preview Permission Change |
| `GET` | `/api/admin/permissions/queue` | Get Permission Queue |
| `POST` | `/api/admin/permissions/reject/{request_id}` | Reject Permission Change |
| `POST` | `/api/admin/permissions/request` | Request Permission Change |
| `GET` | `/api/admin/permissions/{key}` | Get Permission Endpoint |
| `GET` | `/api/admin/security/alerts` | Security Alerts |
| `GET` | `/api/admin/security/login-history` | Login History |
| `GET` | `/api/admin/security/login-history-archived` | Login History Archived |
| `GET` | `/api/admin/security/login-stats` | Login Stats |
| `GET` | `/api/admin/stats/feature-heatmap` | Stats Feature Heatmap |
| `GET` | `/api/admin/system/audit-log` | Audit Log |
| `POST` | `/api/admin/system/backup` | System Backup |
| `GET` | `/api/admin/system/health` | System Health |
| `GET` | `/api/admin/system/health-extended` | System Health Extended |
| `GET` | `/api/admin/users` | List Users |
| `POST` | `/api/admin/users` | Create Employee |
| `POST` | `/api/admin/users/bulk` | Bulk Create Users |
| `POST` | `/api/admin/users/bulk-role` | Bulk Role Change |
| `GET` | `/api/admin/users/{employee_id}` | Get User Detail |
| `PUT` | `/api/admin/users/{employee_id}` | Update User |
| `DELETE` | `/api/admin/users/{employee_id}` | Delete User |
| `POST` | `/api/admin/users/{employee_id}/lock` | Lock User |
| `POST` | `/api/admin/users/{employee_id}/reset-password` | Reset Password |
| `DELETE` | `/api/admin/users/{employee_id}/retire` | Retire User |
| `POST` | `/api/admin/users/{employee_id}/unlock` | Unlock User |

### `admin-scenarios` (E — 9개)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/admin/scenarios` | List Scenarios |
| `POST` | `/api/admin/scenarios` | Create Scenario |
| `GET` | `/api/admin/scenarios/usage-stats` | Scenarios Usage Stats |
| `GET` | `/api/admin/scenarios/{scenario_id}` | Get Scenario |
| `PUT` | `/api/admin/scenarios/{scenario_id}` | Update Scenario |
| `DELETE` | `/api/admin/scenarios/{scenario_id}` | Delete Scenario Endpoint |
| `GET` | `/api/admin/scenarios/{scenario_id}/history` | Get Scenario History |
| `POST` | `/api/admin/scenarios/{scenario_id}/reset` | Reset Scenario |
| `POST` | `/api/admin/scenarios/{scenario_id}/restore/{history_id}` | Restore Version Endpoint |

### `auth` (E — 12개)

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/auth/2fa/backup-regen` | Two Factor Backup Regen |
| `POST` | `/api/auth/2fa/confirm` | Two Factor Confirm |
| `POST` | `/api/auth/2fa/disable` | Two Factor Disable |
| `POST` | `/api/auth/2fa/enroll` | Two Factor Enroll |
| `GET` | `/api/auth/2fa/status` | Two Factor Status |
| `POST` | `/api/auth/2fa/verify` | Two Factor Verify |
| `POST` | `/api/auth/change-password` | Change Password |
| `POST` | `/api/auth/login` | Login |
| `GET` | `/api/auth/me` | Get Me |
| `PUT` | `/api/auth/me` | Update Me |
| `GET` | `/api/auth/me/login-history` | Get My Login History |
| `POST` | `/api/auth/refresh` | Refresh Token |

### `idp` (E — 5개)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/auth/idp/capabilities` | Capabilities |
| `POST` | `/api/auth/idp/ldap/login` | Ldap Login |
| `POST` | `/api/auth/idp/saml/acs` | Saml Acs |
| `GET` | `/api/auth/idp/{provider}/callback` | Callback |
| `GET` | `/api/auth/idp/{provider}/login` | Login Redirect |

### `equipment` (F — 19개)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/equipment/dashboard/overview` | Overview |
| `POST` | `/api/equipment/drawing/{drawing_id}/ocr` | Drawing Ocr |
| `GET` | `/api/equipment/error/categories` | Error Categories |
| `POST` | `/api/equipment/error/search` | Error Search |
| `GET` | `/api/equipment/headline` | Daily Headline |
| `GET` | `/api/equipment/health` | Equipment Health |
| `GET` | `/api/equipment/inspection/checklist/{equipment_type}` | Inspection Checklist |
| `GET` | `/api/equipment/inspection/ingest-log/recent` | Recent Ingest Log |
| `POST` | `/api/equipment/inspection/submit` | Submit Inspection |
| `POST` | `/api/equipment/inspection/upload-csv` | Upload Inspection Csv |
| `POST` | `/api/equipment/manual/search` | Manual Search |
| `GET` | `/api/equipment/markov/{error_code}` | Markov Chain |
| `GET` | `/api/equipment/ml-engines/status` | Ml Engines Status |
| `GET` | `/api/equipment/molds` | Molds List |
| `GET` | `/api/equipment/mtbf` | Mtbf Data |
| `GET` | `/api/equipment/plc/status` | Plc Status |
| `POST` | `/api/equipment/spc/upload-csv` | Spc Upload Csv |
| `GET` | `/api/equipment/spc/violations/recent` | Spc Violations Recent |
| `GET` | `/api/equipment/spc/{process_id}` | Spc Chart |

### `dashboard` (공통 — 6개)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/dashboard/alarms` | Get Alarms |
| `GET` | `/api/dashboard/ingestion` | Get Ingestion |
| `GET` | `/api/dashboard/metrics` | Get Metrics |
| `GET` | `/api/dashboard/module-counts` | Get Module Counts |
| `GET` | `/api/dashboard/system-health` | Get System Health |
| `GET` | `/api/dashboard/system-info` | Get System Info |

### `models` (공통 — 8개)

> Access: 로그인 필요. 단, `POST /api/models/invalidate-cache`는 `SYS_ADMIN(L5)` 전용.

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/models/auto-select` | Auto Select |
| `GET` | `/api/models/available` | List Available Models |
| `GET` | `/api/models/catalog` | Model Catalog |
| `GET` | `/api/models/installed` | List Installed Models |
| `POST` | `/api/models/invalidate-cache` | Invalidate Cache |
| `GET` | `/api/models/llm-options` | List Llm Options |
| `GET` | `/api/models/recommend` | Recommend Model |
| `GET` | `/api/models/vision` | List Vision Models |

### `export` (공통 — 3개)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/export/health` | Export Health |
| `POST` | `/api/export/hwp` | Export Hwp |
| `POST` | `/api/export/hwpx` | Export Hwpx |

### `health` (공통 — 2개)

> Access: `GET /api/health`는 공개. `GET /api/health/llm-status`는 `SYS_ADMIN(L5)` 전용.

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/health` | Health Check |
| `GET` | `/api/health/llm-status` | Llm Status |

### `me` (공통 — 2개)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/me/mobile-tab-prefs` | Get Mobile Tab Prefs |
| `PUT` | `/api/me/mobile-tab-prefs` | Put Mobile Tab Prefs |

### `slack` (공통 — 2개)

| Method | Path | Summary |
|---|---|---|
| `POST` | `/slack/command` | Slack Command |
| `GET` | `/slack/health` | Slack Health |

### `untagged` (공통 — 1개)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/` | Root |

### `feedback` (공통 — 1개)

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/feedback` | Create Feedback |

### `live-alarms` (공통 — 2개)

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/live-alarms/recent` | Get Recent Live Alarms |
| `POST` | `/api/live-alarms/{alarm_id}/ack` | Ack Live Alarm |

### `storage` (공통 — 3개)

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/storage/complete-upload` | Complete Storage Upload |
| `GET` | `/api/storage/signed-download/{attachment_id}` | Create Storage Signed Download |
| `POST` | `/api/storage/signed-upload` | Create Storage Signed Upload |
