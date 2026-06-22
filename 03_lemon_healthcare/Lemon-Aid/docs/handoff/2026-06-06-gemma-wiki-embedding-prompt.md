# [새 세션 프롬프트] LLM-WIKI pgvector RAG — Gemma 계열 임베딩을 bge-m3와 함께 추가

아래 블록을 새 세션(새 섹션)에 그대로 붙여넣어 이어서 진행하세요.

---

## 임무
Lemon-Aid 백엔드의 **LLM-WIKI pgvector 시맨틱 RAG**에, 현재의 `bge-m3`(1024d) 임베딩에 **더해 Gemma 계열 임베딩을 두 번째 모델로 추가**해서, 같은 위키를 두 모델로 임베딩·검색하고 검색 품질을 비교(A/B)할 수 있게 만들어라. (목적: gemma4:e4b가 설명 생성 LLM이라 임베딩도 Gemma 계열로 통일·비교하려는 것.)

## 현재까지 완료된 것 (먼저 숙지 — 이 컨텍스트는 새 세션에 없음)
- **경로/실행**: 백엔드 `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/backend`. 패키지는 `Nutrition-backend/src`, venv는 `backend/.venv`. 실행은 `backend`에서 `PYTHONPATH=Nutrition-backend ./.venv/bin/python ...`. git root = `Lemon-Aid`.
- **메모리/플랜**: 프로젝트 메모리 `lemon-aid-db-topology.md`, 플랜 `~/.claude/plans/hidden-dreaming-locket.md`에 전체 설계·DB 토폴로지가 기록돼 있음. **반드시 먼저 읽을 것.**
- **커밋**: 브랜치 `feat/backend-food-nutrition-wiki-rag` (origin=Lemon-Aid-KDT/Lemon-sin, personal=HorangEe02/Project_yeong에 푸시됨). RAG 구현 커밋 = `a421ec3 feat(rag): ...`.
- **3개 DB**(로컬 Supabase `:56322` postgres/postgres, compose `lemon-aid-db-1` lemon/lemon, 원격 Supabase weips pooler)에 모두 적재·검증 완료: wiki_documents ~583, chunk_embeddings ~12k, entity_wiki_links 96.
- **스키마(migration 0028, head)**: `wiki_documents`, `wiki_chunks`, `wiki_chunk_embeddings(embedding extensions.vector(1024), embedding_model, embedding_dimensions, uq(chunk_id, embedding_model))`, `entity_wiki_links`. pgvector는 `extensions` 스키마에 설치 → **코사인 연산자는 반드시 `OPERATOR(extensions.<=>)`로 스키마 한정**(compose 등 search_path에 extensions 없는 DB 대응). 차원 컬럼은 **vector(1024) 고정**.
- **임베딩**: Ollama `bge-m3`(1024d), `POST {ollama_base_url}/api/embed {"model":"bge-m3","input":"..."}`. 위키 = `/Volumes/Corsair EX400U Media/LLM-WIKI`(Obsidian, ~583 md, 닷폴더 제외).
- **스크립트(`backend/scripts/`)**: `ingest_llm_wiki_embeddings.py`(`--model`/`--dimensions` 파라미터화, heading 청킹, content_hash 멱등, 재시도+문서별 실패격리), `seed_entity_wiki_links.py`, `copy_wiki_rag_missing.py`(additive 백필).
- **검색**: `services/llm_wiki_retrieval.retrieve_llm_wiki_context_db(query, settings, *, entity_keys=())` — 벡터/하이브리드 + entity-link 부스트 + lexical 점수 정규화 + lexical fail-open. 설정(`config.py`): `enable_wiki_vector_rag`(기본 False), `llm_wiki_retrieval_mode`(hybrid), `wiki_embedding_model`(bge-m3), `wiki_embedding_dimensions`(1024).

## ⚠️ 핵심 블로커 (2026-06-06 검증됨, 반드시 먼저 해결)
**`gemma4:e4b`는 Ollama 임베딩을 지원하지 않는다.** `/api/embeddings`와 `/api/embed` 모두 `{"error":"This server does not support embeddings. Start it with --embeddings"}` 반환(생성형 text+vision 모델이라 임베딩 헤드 없음). 같은 서버에서 `bge-m3`는 정상(1024d). → **gemma4:e4b로는 직접 임베딩 불가.** 임베딩 소스를 먼저 확정하라:
- **(A) 권장 — `embeddinggemma`**: Google의 Gemma 기반 **임베딩 전용** 모델(약 768d). `ollama pull embeddinggemma` 후 `/api/embed`로 임베딩. 가장 현실적인 "Gemma 임베딩" 경로.
- (B) `gemma4:e4b`에서 임베딩을 켜는 커스텀 Ollama Modelfile 시도(아키텍처상 불확실).
- (C) transformers/sentence-transformers로 Gemma hidden-state 임베딩 추출(무거움; venv에 sentence-transformers 미설치).
선택한 모델의 **임베딩 차원을 먼저 확인**: `curl -s http://127.0.0.1:11434/api/embed -d '{"model":"<모델>","input":"테스트"}'` → `embeddings[0]` 길이.

## 설계 결정 (해야 할 것)
1. **임베딩 모델·차원** 확정(블로커 참조). 차원이 1024가 아니면 현재 `vector(1024)` 컬럼에 못 들어감.
2. **멀티모델 스키마**. 테이블에 `uq(chunk_id, embedding_model)`은 있으나 `embedding` 컬럼이 **단일 고정 차원**. 다른 차원 모델은 아래 중 택1:
   - (a) 모델별 새 테이블 `wiki_chunk_embeddings_<model>`(`vector(<dim>)`),
   - (b) 일반화된 모델별 임베딩 테이블,
   - (c) 모든 모델을 동일 차원으로 표준화(투영/절단)해 컬럼 재사용.
   새 **alembic migration 0029**(현재 head=0028) 작성, **0028 패턴 그대로**: `PGVectorType`→`extensions.vector(N)`, hnsw cosine 인덱스(`extensions.vector_cosine_ops`), `lemon_app` read RLS 정책, 스키마 한정 연산자.
3. **인제스천**: `ingest_llm_wiki_embeddings.py`를 모델별 타깃 테이블로 라우팅하도록 확장(`--model`는 이미 있음; `/api/embed` 사용으로 통일). 멱등(content_hash) 유지.
4. **검색**: `retrieve_llm_wiki_context_db`를 **모델 선택형**으로 — `wiki_embedding_model` 설정에 따라 임베딩 모델·대상 테이블을 고르고, 쿼리를 그 모델로 임베딩해 매칭 테이블 검색. **fail-open + `OPERATOR(extensions.<=>)` 한정 유지.**
5. **비교 하니스**(핵심 목적): bge-m3 vs Gemma 임베딩의 top-K를 대표 쿼리("오메가3 효능", "마그네슘 권장량과 UL", "한식 나트륨", "비타민D 칼슘 상호작용")로 비교해, 큐레이션/엔티티 페이지를 더 잘 올리는 모델을 리포트.

## 단계
1. 임베딩 모델 확정((A): `ollama pull embeddinggemma`, 차원 확인).
2. migration 0029(모델별 임베딩 테이블 + hnsw + RLS) 작성·적용(로컬 먼저).
3. 인제스천 스크립트 확장 → **로컬 Supabase** `postgresql://postgres@127.0.0.1:56322/postgres`(PGPASSWORD=postgres)에 먼저 적재, 카운트 검증.
4. 검색 모델 선택형 확장 → 스모크 쿼리로 합리적 citation 확인.
5. 비교 하니스 실행·리포트.
6. **롤아웃**: compose(socat `docker run -d --rm --name pgfwd --network lemon-aid_default -p 127.0.0.1:55432:55432 alpine/socat tcp-listen:55432,fork,reuseaddr tcp-connect:db:5432` → `postgresql://lemon@127.0.0.1:55432/lemon`, PGPASSWORD=lemon) + 원격 weips(pooler `aws-1-ap-south-1.pooler.supabase.com:5432`, user `postgres.weipsloxntjzcqjvzjax`, 비번 `.env` `SUPABASE_DB_PASSWORD`). **원격은 per-row pooler INSERT가 느리니 `copy_wiki_rag_missing.py`식 bulk copy(compose→원격)를 우선**하고, **원격 prod TRUNCATE는 사용자 명시 승인 없이는 금지**(auto-mode 클래시파이어가 차단함).
7. `feat/backend-<kebab>` 브랜치(레포 규칙: type/kebab)로 커밋 후 origin + personal 푸시. 사용자의 미커밋 WIP는 건드리지 말 것(명시 경로로만 `git add`).

## 제약
- ruff clean, 전체 타입힌트, Google docstring. citation에 원시 OCR/provider payload/절대경로 금지. macOS 파일명은 **NFD** → `unicodedata.normalize("NFC", ...)` 필수. macOS엔 `timeout` 바이너리 없음(쓰지 말 것). `enable_wiki_vector_rag` 기본 False 유지(무중단). 커밋·푸시는 사용자가 요청할 때만.

---
