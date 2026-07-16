# 설계 문서 검토 결과 (스키마-API 불일치 · 설계 결함 · 누락 항목)

작성일: 2026-07-16
대상: `meeting-recorder-implementation-plan.md` 및 `docs/**` 전체 (구현 코드 없음, 순수 설계 단계)

## 검토 방법

5개 관점(스키마↔API 정합성 / 문서 간 일관성 / 설계 결함 / 보안 / 완결성)으로 병렬 검토한 뒤,
각 지적을 원문과 대조해 적대적으로 검증했다. 원 지적 46건 중 **확정 36 · 유력 7 · 기각 3**.
중복을 병합해 아래 고유 이슈로 정리한다. 심각도: **P0**=착수 전 결정 필요/요구사항 위반, **P1**=구현 중 결정 필요, **P2**=경미/문서 정합.

---

## P0 — 착수 전 반드시 결정해야 하는 것

### 1. 1차 MVP에 "사용자 식별 주체"가 없다 (user_id를 채울 방법이 없음)
- **근거**: `db-schema.md`(meetings.user_id / recording_files.user_id = NOT NULL FK → profiles), Storage 경로 `/users/{user_id}/...`, `api-spec.md`(POST /jobs 필드에 user_id 없음), `05-security`(owner만 접근), master plan(Supabase Auth는 2차)
- **문제**: 인증이 단일 정적 `LOCAL_API_TOKEN` 하나뿐인데 스키마·경로·권한 모델은 모두 user 단위 격리를 전제한다. POST /jobs가 meetings/recording_files를 INSERT할 때 넣을 user_id의 출처가 어느 문서에도 없어 **FK 위반으로 구현이 막힌다.** `db-schema.md:253`의 "API layer에서 auth.uid() 조건 강제"도 강제할 주체가 없어 성립 불가.
- **권장**: 1차 MVP가 단일 로컬 사용자 전제임을 명시하고 고정 profile 1행 시딩 + `LOCAL_API_TOKEN→user_id` 매핑 규칙을 `db-schema.md`/`local-worker` 문서에 못박는다. (병합: schema-api, cross-doc-userid, design-flaws-9, auth-no-user-identity-1, missing-user-identity-source)

### 2. 녹음 동의를 저장할 API 경로가 없다 (P0 완료조건 충족 불가)
- **근거**: `db-schema.md`(meetings.recording_consent_confirmed default false, ..._at), `05-security` 완료조건 "동의 확인이 저장된다", work-breakdown 에픽6 P0, `api-spec.md`(POST /jobs 필드에 consent 없음, PATCH /meetings는 title만)
- **문제**: 회의를 만드는 유일한 호출 POST /jobs에 동의 필드가 없고 다른 어떤 엔드포인트도 이 값을 true로 쓰지 않는다. → 모든 회의가 영구히 `false`로 남아 법적/프라이버시 필수 통제가 **사실상 비작동**.
- **권장**: POST /jobs multipart에 `recording_consent_confirmed`(+확인 시각)를 필수로 추가하고, 미확인 시 `consent_required`로 업로드를 거부하도록 공통 오류에 정의. (병합: schema-api-3, cross-doc-consent, consent-no-write-path-1, missing-consent-on-job-create)

### 3. 인증 오디오 스트림을 브라우저 `<audio>`가 재생할 수 없다 (핵심 기능 파손)
- **근거**: `api-spec.md`(모든 엔드포인트 Bearer 인증, GET /recording-files/{id}/stream + Range), `02-transcription`(‹audio› + currentTime seek 기반 "발화 클릭 재생"), `05-security:47`(signed URL 또는 인증 streaming — 방식 미확정)
- **문제**: HTML `<audio src=...>`는 커스텀 `Authorization: Bearer` 헤더를 붙일 수 없다. GET /meetings가 주는 `stream_url`은 토큰 없는 평문 경로라 그대로 넣으면 401. fetch→Blob 우회는 Range seek(발화 클릭 재생의 핵심)를 깨뜨린다. → **인증과 seek를 동시에 만족하는 재생 설계가 비어 있음.**
- **권장**: `stream_url`을 단기 서명 토큰 포함 URL(`?token=...`) 또는 쿠키 세션 인증으로 발급하도록 정하고, 생성 규칙·만료·검증 방식을 `api-spec.md`에 명시. (design-flaws-1)

### 4. `hotwords`가 어디에도 저장되지 않아 재시도 시 유실
- **근거**: `api-spec.md`(POST /jobs가 hotwords 수신, POST /retry 본문은 `from_stage`만), `db-schema.md`(meetings/jobs/recording_files 어디에도 hotwords 컬럼 없음), `02-transcription`(transcribe에 hotwords 소비)
- **문제**: hotwords는 업로드 시점에만 들어오는데 비동기 transcribing 단계에서 소비된다. 저장 컬럼이 없어 `POST /retry(from_stage=transcribing)` 재시도가 **최초 ASR 힌트를 복원하지 못해 더 낮은 품질**로 재전사된다.
- **권장**: `jobs.hotwords text[]`(또는 meetings)에 영속화하고 retry가 이를 읽어 재호출하도록 파이프라인에 명시. (병합: schema-api-1, design-flaws-2)

### 5. `meetings.status`와 `jobs.status`가 동일 enum을 이중 보유 — 동기화 주체 미정
- **근거**: `db-schema.md`(두 테이블 동일 6값 CHECK, 둘 다 default 'uploaded'), `local-worker`(파이프라인이 jobs.status만 갱신), `api-spec.md`(GET /meetings는 meetings.status 반환, 필터는 "job 또는 meeting 상태")
- **문제**: 파이프라인 기술에 meetings.status를 갱신하는 단계가 없어, 처리 완료 후에도 **회의 목록/상세 status가 'uploaded'에 고정**될 수 있다. 어느 컬럼이 진실원인지, 어떻게 동기화하는지 미정.
- **권장**: jobs.status를 단일 진실원으로 삼아 meetings.status를 파생/뷰로 만들거나, 각 전이에서 같은 트랜잭션으로 write-through. GET /meetings가 반환/필터하는 컬럼을 명시. (병합: schema-api-2, design-flaws-3)

### 6. 회의 삭제(soft-delete) 엔드포인트가 없다
- **근거**: `db-schema.md`(meetings.deleted_at), `05-security`(5단계 soft-delete 흐름 정의), work-breakdown 에픽6 P1, `api-spec.md`(DELETE 엔드포인트 부재)
- **문제**: soft-delete 정책은 완전히 정의됐지만 이를 트리거할 API가 없어 `deleted_at`이 write-orphan. P1 요구를 충족할 계약이 없음.
- **권장**: `DELETE /v1/meetings/{meeting_id}` 추가(202 + deleted_at 설정, 파일 삭제 queue 등록, 목록 제외 규칙, audit_logs 기록). (병합: schema-api-4, missing-delete-meeting)

---

## P1 — 구현 중 결정 필요

### 7. 가변 운영 상태가 불변 요약 버전에 묶여 편집 때마다 소실 + 이를 쓸 엔드포인트 없음
- **근거**: `db-schema.md`(action_items.status open/done/dismissed, calendar_candidates.status pending/approved/dismissed + created_calendar_url — 모두 summary_version_id의 자식), `03-summary`(PATCH /summary가 배열 통째 교체로 새 버전 생성), `api-spec.md`(개별 항목 상태 갱신 엔드포인트 없음)
- **문제**: 사용자가 할 일을 done, 일정 후보를 approved로 바꾼 뒤 요약을 한 번 더 수정하면 새 버전에서 항목이 default로 재생성되어 **완료/승인 상태가 조용히 유실**. 게다가 이 상태를 쓸 API 자체가 없고, 일정 승인은 "외부 캘린더 링크 열기"뿐이라 생성 여부를 앱이 확인할 수도 없다(created_calendar_url 채울 근거 없음).
- **권장**: 가변 상태를 meeting_id 기준 안정 엔티티로 분리하거나 버전 이월 규칙을 정의. `PATCH /meetings/{id}/action-items/{id}`, `.../calendar-candidates/{id}` 전용 엔드포인트 추가하고 GET /summary 응답에 후보 id/status 노출. (병합: schema-api-8, design-flaws-4, design-flaws-5, missing-action-item-status-update, missing-calendar-approval-endpoint)

### 8. "최신 승인 요약 버전"을 가리키는 마커가 없어 엔드포인트마다 다른 버전을 반환
- **근거**: `db-schema.md`(summary_versions에 approved/current 플래그 없음), `api-spec.md`(GET /summary는 "최신 버전"=max version), `04-export`/`03-summary`("최신 **승인** 버전"으로 export·공유)
- **문제**: 재생성 후 AI draft가 더 높은 version을 가지면 `max(version)`은 미승인 draft인데 "최신 승인"은 이전 user 버전이어야 한다. 선택 규칙 미정으로 **GET /summary와 export/share가 서로 다른 요약을 노출**.
- **권장**: `summary_versions.is_current` 불리언 또는 `meetings.current_summary_version_id` 포인터를 도입하고 세 경로가 동일 셀렉터를 쓰도록 명시. (schema-api-6)

### 9. 요약 생성 실패를 저장할 수 없음 (NOT NULL + 필드명 불일치)
- **근거**: `03-summary`(실패 시 원문을 `summary_raw_output`에 저장), `db-schema.md`(컬럼명은 `raw_model_output`, 그리고 title/summary/raw_json 모두 NOT NULL)
- **문제**: (1) 필드명 불일치(`summary_raw_output` ↔ `raw_model_output`). (2) JSON 파싱 실패 시 구조화 요약이 없는데 NOT NULL 컬럼들 때문에 실패 행을 insert할 수 없다. 또 status enum의 일반 'failed'로는 "전사는 정상, 요약만 실패"를 표현 못함.
- **권장**: 필드명 통일, title/summary/raw_json nullable화(또는 summary_versions에 failed 플래그), "요약만 실패" 상태 표현 방식 결정. (schema-api-5)

### 10. 화자 표시명이 두 곳에 저장 — 승자 미정
- **근거**: `db-schema.md`(transcript_segments.speaker_name + speaker_aliases 둘 다 존재), `02-transcription`("별도 alias 적용"), `api-spec.md`(GET /segments는 per-segment speaker_name 반환, PATCH /speakers는 같은 label 전체 반영)
- **문제**: 같은 사실(라벨→표시명)이 세그먼트마다 denormalize + alias 테이블에 canonical로 이중 저장. 읽기 우선순위와 PATCH 쓰기 대상(alias만? 전 세그먼트도?)이 미정 → **drift 위험**.
- **권장**: 한쪽을 정본으로 선언(alias canonical + GET는 join, 또는 alias 제거) 후 PATCH 쓰기 동작 명시. (schema-api-7)

### 11. Slack `channel_label`은 Incoming Webhook으로 실현 불가 (프라이버시 통제 무력화)
- **근거**: `api-spec.md`(POST /share/slack가 channel_label 수신), `04-export`(단일 SLACK_WEBHOOK_URL), `local-worker`(env SLACK_WEBHOOK_URL 하나)
- **문제**: Incoming Webhook은 URL마다 고정 채널로만 전송 — payload로 임의 채널 변경 불가. UI가 "#product"라 표시해도 실제로는 webhook에 묶인 채널(예 공개 채널)로 회의 요약이 갈 수 있어 "공유 전 채널 확인" 통제가 무의미해짐.
- **권장**: MVP에서 channel_label을 표시 전용으로 규정하고 실제 대상=고정 webhook 채널임을 명시하거나, 채널별 webhook 매핑 도입. 미리보기에 **실제 전송 채널명**을 노출. (slack-channel-label-unfulfillable-1)

### 12. 중복 업로드 방지 완료조건에 대응하는 설계가 비어 있음
- **근거**: `01-recording`(같은 파일 재업로드 시 중복 job 방지 요구), `db-schema.md`(checksum_sha256 = nullable·non-unique), `api-spec.md`(POST /jobs에 idempotency/dedup 없음)
- **문제**: 서버 처리 단계에 체크섬 계산·대조가 없고 unique 제약도 없어 항상 새 job/meeting이 생성됨. 완료조건 미충족.
- **권장**: 업로드 시 checksum 계산·저장, `(user_id, checksum)` 부분 unique 또는 조회 dedup, 혹은 `force_new` 플래그/409+기존 job_id 반환을 스펙에 명시. (병합: design-flaws-7, missing-duplicate-upload-contract)

### 13. "프로세스가 죽어도 재시도" 주장에 실제 복구 메커니즘 부재
- **근거**: `local-worker`(단일 프로세스 background task, "죽어도 재시도"), `db-schema.md`(jobs에 attempts만, lease/heartbeat/started_at 없음)
- **문제**: transcribing 중간에 죽으면 재부팅 시 그 job을 다시 집을 트리거가 없다(진행중 상태로 방치). 최대 attempts, stuck-job 탐지, lease 규칙 미정.
- **권장**: `jobs.locked_until`/`heartbeat_at`(또는 started_at) + 최대 attempts 추가, 부팅 시 만료 lease 회수·재개 루프와 초과 시 failed 전이 규칙 명시. (design-flaws-8)

### 14. Export 다운로드 엔드포인트가 스펙에 없음
- **근거**: `api-spec.md`(POST exports가 `download_url=/v1/exports/{id}/download` 반환하나 GET 정의 없음), `04-export`
- **문제**: 오디오 스트림은 GET으로 명시됐지만 export 다운로드 엔드포인트와 회의별 export 목록 조회(GET)가 없어 **생성 후 다운로드/재다운로드 경로가 비어 있음**.
- **권장**: `GET /v1/exports/{export_id}/download`(인증·권한·signed URL/스트리밍) 및 필요 시 `GET /v1/meetings/{id}/exports` 추가. (missing-export-download-endpoint)

### 15. Slack Webhook "사용자 설정" 저장을 뒷받침할 엔드포인트·테이블 부재
- **근거**: `04-export`("환경변수 또는 사용자 설정"에 저장, 미설정 시 "설정 화면 안내"), `db-schema.md`(설정/webhook 테이블 없음), `api-spec.md`(설정 엔드포인트 없음)
- **권장**: MVP는 환경변수 전용으로 확정하고 "설정 화면" 문구 제거, 또는 설정 저장 테이블 + GET/PUT 엔드포인트(+미설정 조회) 정의. (missing-slack-webhook-settings)

### 16. `audit_logs` 기록 주체가 지정되지 않음 (P1인데 미바인딩)
- **근거**: `db-schema.md`(audit_logs 존재), `05-security`(8종 이벤트 기록 요구), work-breakdown P1, `local-worker`(repositories/API 책임표에 audit_logs 없음, 인덱스도 없음)
- **권장**: 저장 책임 계층(전용 AuditService 또는 각 service side-effect) 지정 + 8종 event_type 문자열/metadata 스키마 + `(meeting_id, created_at)` 인덱스 정의. (orphan-audit-logs-writer)

### 17. 사용자 개시 요약 재생성(source='regenerated') 트리거 엔드포인트 부재
- **근거**: `db-schema.md`(summary_versions.source enum에 'regenerated'), `03-summary`(전사 보정 후 재생성 시나리오), `api-spec.md`(PATCH /summary=user, POST /retry=실패 재시도 — 사용자 개시 재생성 없음)
- **권장**: `POST /meetings/{id}/summary/regenerate`(→ source='regenerated' draft) 정의하거나 POST /retry from_stage='summarizing'가 겸하며 source를 어떻게 세팅하는지 명시. (missing-summary-regenerate-endpoint)

### 18. Supabase `service_role` 키 사용이 RLS를 전면 우회
- **근거**: `db-schema.md:253`(RLS = auth.uid() 정책), `local-worker`(env `SUPABASE_SERVICE_ROLE_KEY`, supabase_storage provider)
- **문제**: 모든 앱 접근이 Worker를 경유하는데 Worker가 service_role로 연결하면 RLS가 실질적으로 아무것도 게이팅하지 못한다. 유일 방어선인 "API layer 강제"는 이슈 #1(식별 주체 부재)로 성립 불가.
- **권장**: Worker가 사용자별 JWT로 RLS를 실제 적용할지, 아니면 service_role + API layer owner 강제를 유일 방어선으로 삼을지 아키텍처 결정을 문서화(이슈 #1과 함께). (service-role-bypasses-rls-1)

### 19. `source_device`가 POST /jobs로 수신되나 저장 컬럼 없음
- **근거**: `api-spec.md`/`01-recording`(source_device 수신, 값 열거), `db-schema.md`(저장 컬럼 없음 — duration_ms/language와 달리 유실)
- **권장**: `recording_files.source_device text`(mime_type/sample_rate 옆) 추가 또는 계약에서 제거. (schema-api-9)

### 20. 파생 리스트 필드 `has_summary`/`shared_count`의 정의 부재
- **근거**: `api-spec.md`(GET /meetings가 두 필드 반환), `db-schema.md`(저장 컬럼 아님)
- **문제**: `shared_count`가 COUNT(share_logs) 전체인지 status='sent'만인지 모호(실패/대기 행 포함 시 과다 계산). "공유 여부" 표시가 부정확해질 수 있음.
- **권장**: `has_summary = EXISTS(summary_versions...)`, `shared_count = COUNT(share_logs WHERE status='sent')`처럼 파생 규칙을 스펙에 명시. (schema-api-10)

---

## P2 — 경미 / 문서 정합성

- **duration_ms 이중 저장**: 클라이언트 측정(meetings.duration_ms, 신뢰불가) vs 서버 측정(recording_files.duration_ms). GET /meetings가 어느 값을 반환하는지 미정 → 서버값을 정본으로 선언. (schema-api-12)
- **GET /meetings/{id}/segments 페이지네이션 부재**: 목록엔 cursor 있으나 segments엔 없음. 긴 회의는 수천 segment. 지속 계약 단계에서 keyset cursor를 정하는 편이 안전. (design-flaws-10)
- **요약 version 채번 동시성**: PATCH /summary와 AI 재생성이 동시에 max(version)+1을 읽어 unique 충돌 가능. row-lock/시퀀스/재시도 규정 필요. (design-flaws-6)
- **share_logs 평문 payload**: request_payload에 요약 전문(민감정보 가능)이 평문 중복 저장. `04-export:95`는 "응답 본문 일부"만이라 했으나 스키마는 전체를 담음 → 보존/마스킹 정책과 정합화. (share-logs-plaintext-payload-1)
- **요약 Provider 명 불일치**: master plan `LocalGemmaProvider` vs 나머지 `LocalLLMProvider`(파일 local_llm.py) → 모델 중립 `LocalLLMProvider`로 통일. (cross-doc-summary-provider-name)
- **Provider 시그니처 불일치**: `transcribe`가 master plan/feature는 2인자, local-worker는 3인자(language 추가); `summarize`가 transcript vs segments → local-worker 시그니처를 정본으로 통일. (cross-doc-provider-signatures)
- **master plan 테이블명 stale**: 저장 구조 스케치의 `users`/`summaries`가 db-schema `profiles`/`summary_versions`와 어긋나고 jobs 누락 → 수정 또는 "정식 스키마는 db-schema.md 기준" 주석. (cross-doc-master-plan-table-names)
- **id 포맷 표기**: API 예시는 `job_01`/`seg_001` 문자열, 스키마는 uuid. "예시는 예시, id는 opaque uuid"임을 1줄 명시하고 PATCH .../segments/{segment_id}가 uuid인지 segment_index인지 명확화. (schema-api-11)
- **embeddings orphan**: `transcript_segment_embeddings`는 MVP 파이프라인에 채우는 단계가 없으나 이는 의도된 2차 범위. "2차 벡터 검색용, MVP에서 미채움" 1줄 추가 권장. master plan이 언급한 summary/action-item embedding은 db-schema엔 없음(2차 정리 필요). (embeddings-forward-looking-note)

---

## 적대적 검증에서 기각(REJECTED)된 항목 — 참고

- **`/v1` 접두사 불일치**: api-spec 섹션 헤더(`POST /jobs`)가 /v1 없이 표기되나 Base URL이 `/v1`이라 상대경로 해석이 자연스러움 → 실질 결함 아님. (다만 응답 URL은 절대 `/v1/...`라 표기 통일 1줄이면 더 명확)
- **stream/export IDOR (객체 단위 인가)**: `05-security`가 "owner만 접근"을 이미 명시하므로 "인가 없음" 주장은 부분 반박됨. 실제 공백은 이슈 #1(식별 주체 부재)에 흡수됨 — 단, 엔드포인트 명세에 owner 바인딩을 재확인하는 문장은 추가 권장.
- **export 실패 재시도 엔드포인트 없음**: POST /exports 재호출이 새 export 레코드를 만들어 재시도를 커버 → 전용 엔드포인트 불필요.

---

## 권장 처리 순서

1. **먼저 결정할 아키텍처 2가지** — (a) MVP 인증/사용자 모델(단일 로컬 사용자 vs 다중 토큰; 이슈 #1·#18), (b) 상태 진실원(meetings vs jobs; 이슈 #5). 이 둘이 나머지 스키마·엔드포인트 결정을 좌우한다.
2. **P0 계약 구멍 메우기** — 동의(#2)·hotwords(#4)·삭제(#6)·오디오 스트림 인증(#3)을 api-spec/db-schema에 반영.
3. **요약/항목 라이프사이클 재설계**(#7·#8·#9) — 편집·재생성·승인 상태 보존 규칙을 확정.
4. 나머지 P1(#10–#20)을 엔드포인트 추가/정의로 해소.
5. P2는 문서 표기 통일 위주로 일괄 정리.
