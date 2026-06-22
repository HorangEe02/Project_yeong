# PR #4 (feat/ai-agent-backend-integration) 델타 분석 및 병합 실행 플랜 (2026-06-12)

> 대상: [Lemon-sin#4](https://github.com/Lemon-Aid-KDT/Lemon-sin/pull/4) — head `0a91a7b2` (2026-06-12 01:47 갱신, Draft)
> 분석 방법: 4영역 병렬 정밀 diff (코어 패키지 / Nutrition 표면 / 마이그레이션 / 운영도구) — 수치는 전부 git 확인값
> 전제: 그들 브랜치(90커밋)는 우리와 **공통 조상 없음** → `git merge` 불가, **경로 단위 임포트만** 가능 (기존 규칙 유지)

## 0. PR 성격 (팀원 리뷰 가이드 요지)

- 최종 에이전트 완성이 아니라 **"안전 LLM 챗 경로 고정" 중간 PR**
- 계약: `/api/v1/ai-agent/chat` canonical(alias 금지) · answerable만 SGLang polish · 응급/P0/복약판단은 deterministic boundary · 미검수 출처는 `unknown_no_reviewed_source` fail-closed · raw payload 노출 금지 · confirmed/preview 레코드 구분
- 병합 OK 조건: agent-backend CI green + strict smoke 4케이스 기대값 충족
- 검증 명령: `check_ai_agent_runtime_prereqs.py` / `run_agent_llm_merge_smoke.py --llm sglang --require-answerable-llm` (로컬 무LLM은 `--llm none` 4/4)

## 1. 영역별 판정 요약

| 영역 | 델타 | 판정 |
|---|---|---|
| `backend/ai_agent_chat` (코어) | 20파일 +2,972 | **통째 덮어쓰기 안전** — 임포트 후 우리가 수정한 적 없음(커밋 이력 확인) |
| Nutrition 표면 (src 4 + tests) | 소규모 | 신규 6파일 통째 수입 안전 · **`ai_agent.py`만 수동 패치**(유일 실충돌) · 우리 독자 작업 2파일 유지 |
| `backend/alembic` | A 0건 | **아무것도 임포트하지 않음** — 그들 17개 체인은 우리 0001~0006+0030~0040과 본문 동일(전수 diff), env.py/0005 변경은 회귀 |
| 운영도구 (scripts/CI/docs) | 스크립트 9+2, CI 1, 문서 4 | 스크립트 충돌 없음 · CI는 **맨 마지막** · 문서 36 번호 충돌 정리 필요 |

## 2. 핵심 발견 (충돌·위험)

### 유일한 실질 코드 충돌 — `ai_agent.py` 로컬 LLM 가드
그들 버전은 우리(30f56e8d)가 추가한 `validate_local_ollama_settings(settings)` 호출을 제거함. 통째 수입 시 `ALLOW_EXTERNAL_LLM=false` 환경에서도 챗 LLM 트래픽이 비로컬로 나갈 수 있고, 테스트는 `_build_llm_client`를 패치하므로 **28개 테스트 전부 그린이어도 미검출**. → 수동 패치로 그들 신규분(`PUBLIC_CHATBOT_SOURCE_FIELDS` + `_public_chatbot_sources()` 소스 공개 화이트리스트)만 가져오고 가드는 유지.

### 우리 독자 작업 보호 목록 (그들 트리에 없음 — diff의 "삭제"를 따라가면 소실)
- `src/services/llm_wiki_retrieval.py`(803줄) · `src/services/wiki_embedding_targets.py`(120줄) — wiki RAG
- `src/llm/ollama.py` — 그들 재작성본은 673줄 작음(루프백 가드·OCR 파싱 확장 소실 위험). **이번 임포트에서 명시 제외**
- `backend/requirements-dev.txt` — 그들 버전은 PyYAML 삭제(우리 YOLO 파이프라인 의존). 우리 것 유지
- alembic `env.py`(VARCHAR(255) 위든) · `0005`(extensions 스키마 vector) — 적용 완료 이력, 그들 변경은 회귀

### 확인된 비충돌 (안심 사항)
- 우리 챗 영속 수정(승인 루프 `_maybe_handle_chat_analysis_run`)은 **양쪽 바이트 동일** — 그들도 같은 코드 보유
- `ChatbotAgent` 생성자는 kw-only `trace_recorder`(기본 Noop) 추가뿐 — 기존 소비자 호환
- `test_ai_agent_api.py`는 순수 추가(24→28, 우리 테스트 전부 보존) — 교체 가능
- 모바일 챗 파싱(ChatbotSource: source_id/family/url) — 소스 화이트리스트와 완전 호환(코드 확인)
- RLS: 그들 마이그레이션엔 RLS 0건이지만 우리 0041이 이미 해당 테이블 전부 FORCE RLS 보정 완료

### 신규 런타임 전제
- **MEDICAL-WIKI 코퍼스**: 저장소 **형제 디렉터리** `…/03_lemon_healthcare/MEDICAL-WIKI/manifest/`에 reviewed_claims.jsonl(42 claims, as_of 2026-06-10)·chatbot_answer_eval_inputs.jsonl(84) 등 필요 — **현재 로컬 부재**(팀원에게 수급 필요). 없으면 wiki 테스트는 skip, 기본 경로 retriever는 FileNotFoundError. 컨테이너에는 별도 마운트/경로 설정 필요(Dockerfile은 ai_agent_chat만 복사)
- SGLang strict smoke는 살아있는 SGLang 엔드포인트 필요 — dev 1차 검증은 `--llm none`(4/4)으로 갈음
- LangSmith 익스포트는 env 3중 게이트(production 무조건 차단) — dev에서만 옵트인
- CI 가드 경로 버그(잠재): workflow는 `repo/MEDICAL-WIKI`, 스크립트는 `repo부모/MEDICAL-WIKI`를 봄 — 러너에선 항상 skip이라 무해하나 vendoring 시 불일치

### 행동 변화 (회귀 아님, 인지 필요)
- 미검수 보충제 효과 질문: 카드 차용 → `unknown_no_reviewed_source`로 전환
- boundary 문구 안전화 재작성("처방 계획 변경 여부는…") — 정확 문구 단언하는 골든/QA 기대값 영향 가능
- LLM polish 응답 포맷 미세 변경(슬롯 재부착, 확인 포인트 5개 캡)

## 3. 병합 실행 플랜 (순서 엄수)

- **Phase 0 — 준비**: ✅ 완료(2026-06-12) — 팀원 코퍼스를 `/Volumes/Corsair EX400U Media/LLM-WIKI/MEDICAL-WIKI/`로 보존 병합(rsync, `__pycache__` 제외, diff -r 바이트 동일 검증)하고 백엔드 기대 경로에 심링크 배선: `03_lemon_healthcare/MEDICAL-WIKI → LLM-WIKI/MEDICAL-WIKI` (레포 밖 형제 경로라 git 무영향). 카운트 확인값: reviewed_claims 42 · chatbot_answer_eval_inputs 84 · evidence_bundle_adapter_fixtures 94(PR 코멘트의 60은 6/9 시점 값). 잔여: 컨테이너 실행 시 경로 마운트/설정은 Phase 4에서, 원본 `/Volumes/Corsair EX400U Media/MEDICAL-WIKI` 정리는 사용자 확인 후
- **Phase 1 — 코어**: ✅ 완료(2026-06-12) — `ai_agent_chat` 20파일(6A+14M) 임포트. 패키지 테스트 **184 passed, 1 skipped** (PR 본문의 팀원 검증값과 정확히 일치 — 코퍼스 인식 확인). Nutrition-backend 소비자 회귀(ai_agent_api 24 + ask_chatbot_agent + evidence_retriever + agent_memory + medical_source_readiness) **51 passed** — boundary 문구 변경·보충제 unknown 전환이 기존 테스트를 깨지 않음
- **Phase 2 — 표면**: ✅ 완료(2026-06-12)
  1. ✅ 신규 6파일 통째 checkout (unknown backlog 서비스+리포트 스크립트+merge smoke+테스트 3)
  2. ✅ `ai_agent.py` 수동 패치 — 화이트리스트 채택 헝크 3개 적용, **validate_local_ollama_settings 가드 유지**(그들 제거 헝크 2개 기각)
  3. ✅ `test_ai_agent_api.py` 교체 (24→28, 순수 추가 재확인)
  4. ✅ `user_health_context_snapshot.py` 통째 채택(최신순 정렬+10개 캡 — 순수 개선) / **`app_health_analysis.py` 기각** — 그들 `session.begin()` 복귀는 라이브 E2E 500(c2a86240)을 재현하는 회귀라 우리 commit 패턴 유지 (분석 경고가 실제 확인된 사례)
  5. ✅ pyproject pythonpath `"."` 추가
  - 검증: 타깃 43 passed → 머지 스모크 `--llm none` **4/4**(전 케이스 PR 기대값 일치) → 백엔드 풀 게이트 **2191 passed**(허용 2건 외 0)
- **Phase 3 — 운영도구·문서**: ✅ 완료(2026-06-12)
  - 스크립트 7종 + ps1 2종(Windows 전용) + `scripts/sync_guide.py` 임포트 — 전부 컴파일 OK
  - `check_ai_agent_runtime_prereqs.py` macOS 실행 확인 — 의료 소스 6/9 ok, 미충족은 전부 선택 게이트(kdca topic ids·mfds api key·semantic-scholar not_reviewed, live DB/SGLang 게이트 off)
  - wiki eval 2종 dry-run: 챗봇 retrieved_top_k **84**·pass / 번들 **94 passed·0 failed·unsafe 0** (PR 기대값 충족 — 병합 코퍼스+심링크 배선 검증)
  - 문서: 그들 36~38+백로그 리포트 임포트 · 우리 ADR **36→39 리네임**(참조 3곳 갱신) · README 수동 병합 — 그들 참조 가이드 보존 + 문서 목록을 Agent/LLM·모바일 2계열로 분리 + **신규 번호 40+ 규칙** 명시 + 링크 전수 유효 확인
- **Phase 4 — 검증 게이트**: ✅ 완료(2026-06-12)
  - 모바일 게이트: analyze 0건 + **360 테스트 전통과**
  - 컨테이너 재빌드·healthy — `medical_wiki_claims`(parents[5], 컨테이너에서 IndexError 경로)는 **런타임 import 체인에 없음을 확인**(스크립트/eval 전용)하여 마운트 불필요 판정
  - 라이브 스모크(재빌드 컨테이너): ① answerable 경로 — 프리셋 질문에 `answerable`+`kdris-2025`, **응답 sources가 화이트리스트 필드만 노출**(수동 패치 라이브 검증) ② 개인 복용량 표현은 `medical_decision_boundary`로 닫힘(안전 계약 의도 동작) ③ 승인 루프 2단계 — 게이트(requires_user_approval=True) → 승인 → snapshot 영속(nutrition_analysis 2→3행) ④ **dashboard/summary 200** — 챗 스냅샷 누적 상태에서 JSONB 필터 회귀 없음
- **Phase 5 — CI·커밋**: ✅ 완료(2026-06-12) — `agent-backend-ci.yml` 임포트(YAML parse OK, 로컬 전부 그린 확인 후 마지막 순서) → 논리 5커밋(mobile P1 / agent core+surface / ops scripts / docs / ci)으로 분리 커밋 → 양 리모트 푸시 `e931f7c0`. **PR#4 경로 단위 병합 전체 완료**
- **금지 목록**: alembic 전체 / `src/llm/ollama.py` / `requirements-dev.txt` / `llm_wiki_retrieval.py`·`wiki_embedding_targets.py` 덮어쓰기

## 4. 결정 필요 (사용자/팀)

1. 문서 36 번호: 우리 ADR을 39로 리네임(권장) vs 팀원 문서 리넘버(상호참조 수정 부담이 그들 쪽이 큼)
2. MEDICAL-WIKI 코퍼스 수급 — 팀원에게 요청 시점
3. strict SGLang smoke를 어디서 돌릴지(SGLang 엔드포인트 보유 환경) — 1차는 `--llm none`으로 충분한지 팀 합의
4. `smoke_ai_agent_server.py`의 Supabase ref 하드코딩(`ajgvoxttzsjcwtphtsuz`)이 우리 프로젝트와 일치하는지 라이브 실행 전 확인
