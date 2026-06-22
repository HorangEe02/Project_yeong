# 2026-06-21 Chatbot LLM-WIKI RAG Redesign

## 기준

- Repo: `Lemon-Aid` / 작성일: `2026-06-21 KST`
- 주제: 챗봇을 DB + LLM-WIKI RAG 기반 Gemma4 출처인용 답변 + 오프토픽 최소응답으로 재설계
- 사용자 불만: "미리 설정된(캔드) 답변 느낌 · 관련 정보 부족으로 답변 못함 · 무관한 질문은 아예 거부"
- 답변 범위 결정: **단계적 RAG**(사용자 선택) — 위험 질문(약 중단/진단)은 어느 안이든 차단

## 오늘 완료한 작업

- [x] 현 챗봇/검색/벡터스택/LLM-WIKI 조사(워크플로 4 병렬) — 기존 인프라 매핑
- [x] 신규 `src/services/chatbot_wiki_rag.py` — retrieve → Gemma4 JSON 합성 → 공개 출처 (`4efcf8fa`)
- [x] `ai_agent.py` `run_chatbot`의 `unknown_no_reviewed_source` 분기에 배선 (`4efcf8fa`)
- [x] compose: `ENABLE_WIKI_VECTOR_RAG=true` + `LLM_WIKI_RETRIEVAL_MODE=vector` (`9b4e644d`)
- [x] `lemon_app` extensions USAGE grant — 라이브 적용 + idempotent 스크립트 (`367b26bf`)
- [x] 백엔드 재빌드 + recreate + 라이브 검증
- [x] 적대 리뷰(code-reviewer opus) APPROVE + 2 MEDIUM 수정

## 근본 원인

- 챗봇(`run_chatbot`→`ChatbotAgent`)은 검수된 `medical_evidence_items` 20개로만 SQL 키워드매칭 → 없으면 하드 거부 + unknown 이벤트 기록 = 3증상의 정체
- LLM-WIKI는 이미 pgvector에 적재(592문서·12,480청크, bge-m3)돼 있었으나 **챗봇과 미연결** → 재설계 = "배선 + 게이트 완화"(그린필드 아님)

## 재설계 (단계적 RAG)

1. 검수 카드 우선(기존 high-confidence 경로, 불변)
2. 카드 없음 → LLM-WIKI 벡터검색(top-K) → Gemma4가 근거 답변 + 출처 인용 + "일반 정보, 전문가 상담" 안내
3. 관련 자료 없음 → 오프토픽 최소 답변(거부 X)
4. 위험 질문 → 상류 분류기가 다른 answerability로 먼저 차단(안전 유지)

## 핵심 블로커 (해결)

- 🔴 `lemon_app`(요청 RLS 롤)이 `extensions` 스키마 USAGE 권한 없음 → pgvector `<=>` 연산자 `permission denied for schema extensions` → retrieve fail-open → 출처 0개 → **모든 답변이 무성 general_fallback**
- 해결: `GRANT USAGE ON SCHEMA extensions TO lemon_app` (라이브 적용 + `backend/scripts/db_poc/grant_lemon_app_extensions_usage.sql` 커밋)
- vector 모드 필수: 컨테이너에 wiki MD 파일 미마운트(lexical 0건), DB 임베딩만 존재. 쿼리 임베딩 = Ollama `bge-m3`(풀됨), 적재 테이블과 동일 모델

## 적대 리뷰 (APPROVE, 0 BLOCKER/HIGH) — 2 MEDIUM 수정

- 안전(위험질문 상류차단)·fail-open·citations·통합 = PASS
- MEDIUM-1: wiki-RAG 출력에 사후 forbidden-phrase 안전 스크린 추가 — **고정밀 약물변경 지시문만**(맨 진단/치료/처방 제외 — 프롬프트가 "전문가 상담" 권하므로 그 단어들로 스크린하면 정상 답변까지 폴백 = "답변 못함" 재발)
- MEDIUM-2: citations 가시화(`source_id`=source_path; `_public_chatbot_sources`가 빈 source_id 드롭) + 내부경로 `source_url`(죽은 링크) 제거

## 라이브 검증 (실 pgvector + bge-m3 + Gemma4)

- "마그네슘 부족 증상" → `answered_from_wiki` + wiki 출처 3건 ✅
- "비타민 D 효능+음식" → 검색이 질병별 문서 매칭 → Gemma 정직하게 출처 미인용 일반 답변(허위 인용 X) ✅
- "오늘 날씨" → 오프토픽 최소 답변 + 건강 도우미 안내 ✅
- 위험 질문 차단 = 상류 분류기(불변, 통합 테스트 통과)

## 검증 / 테스트

- 신규 단위 9 + ai_agent 통합 = 37 통과, 전체 무신규실패, ruff/black 클린

## 잔여 / 후속

- 검색 품질: overview 질문 recall 튜닝(hybrid/top-k↑/re-rank) — 미요청
- 모바일은 이미 `sources` 렌더 → 앱 변경 불필요(챗 탭에서 즉시 확인 가능)
- grant: DB 볼륨 리셋 후 재적용
