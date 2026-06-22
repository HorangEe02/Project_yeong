# Lemon-Aid — develop 핸드오프 정리 (2026-06-22)

> 브랜치 `fix/mobile-theme-and-watch-label` (HEAD `85601a1f`, 약 532 commits / 3006 files) 의 작업을 **기능별·파일별로 정리**한 문서. develop 병합 전 핸드오프용.

## ⚠️ 브랜치 토폴로지 (먼저 확인)

- `origin/develop` = `origin/main` = `2f941020` — **2026-05-11 "docs: add research evidence usage guide"의 47-파일 초기 스캐폴드**.
- 이 브랜치는 develop과 **공통 조상이 없음(unrelated histories)**. 즉 **실제 프로젝트 전체가 이 브랜치에 있고** develop은 사실상 빈 스캐폴드. → develop 반영은 일반 머지가 아니라 무관-이력 reconcile (아래 옵션 참고).

## 검증 상태 (현재 HEAD)

- 백엔드 라이브(docker `lemon-aid-backend-1`) health 200. 단위/통합 테스트 그린(파서·로컬라이저·챗봇 RAG·식단 어댑터 등). ruff/black 클린(잔여 PLR0911·UP009·F401·ollama 통합테스트는 선재/환경의존).
- 미커밋 추적파일 0 (작업트리 클린). 미추적은 생성 아티팩트/로그/데모영상뿐 — develop은 **커밋 기준**이라 영향 없음.

---

# 기능별 정리

## 1. 챗봇 & LLM-WIKI RAG

**한 줄:** A safety-bounded Korean chatbot that, when it has no reviewed evidence card to answer from, falls back to a fail-open LLM-WIKI pgvector RAG path (Gemma synthesis + citations + off-topic deferral), personalized with the user's meds/supplements/conditions and rendered with clean source chips in the mobile chat tab.

**상태:** done — the RAG fallback, citations, off-topic deferral, meds personalization, clean source chips, and the post-gen safety screen are all implemented and unit/integration tested on this branch, and prior memory notes record live verification. One important caveat: the vector/hybrid pgvector RAG is gated behind `enable_wiki_vector_rag` (default False) and requires loaded embeddings plus the lemon_app USAGE-on-extensions grant; without those it silently degrades to lexical-only retrieval (still functional, just non-semantic). So the code is done, but full semantic RAG is ops/flag-dependent rather than on by default.

The branch adds a tiered fallback to the existing reviewed-evidence chatbot: previously, any question with no reviewed `medical_evidence_items` card returned `unknown_no_reviewed_source` and effectively refused. Now, that exact refusal branch calls `answer_with_wiki_rag`, which retrieves from the populated LLM-WIKI pgvector corpus (cosine top-K over `wiki_chunk_embeddings`, with hybrid lexical merge and entity-link boosting), asks the local Gemma model to synthesize a grounded Korean answer with 1-based source citations, and degrades to a brief general answer + disclaimer when nothing relevant is retrieved (off-topic fallback) — so the bot stops refusing benign nutrition/health questions. Later commits hardened this: raised the answer token cap (truncation produced empty content), cut synthesis latency via a "5문장 이내" prompt and a 90s mobile timeout, and personalized answers by passing a privacy-safe summary of the user's chronic conditions, medications, and registered supplements so Gemma can flag interactions/duplication. The mobile side maps wiki citations to compact, humanized source chips (strips section numbers and file paths) that ellipsize instead of overflowing, with a tap-through source detail sheet. The whole RAG path is fail-open by design — any retrieval/LLM/parse error returns a safe minimal Korean message rather than breaking the chat route — and a post-generation safety screen degrades any answer containing high-precision dangerous medication-change directives.

**핵심 파일:**

| 파일 | 역할 |
|---|---|
| `backend/Nutrition-backend/src/services/chatbot_wiki_rag.py` | Core RAG fallback: retrieves wiki citations, builds the Gemma chat payload (system prompt + user context + numbered references), parses the JSON answer + used_sources, runs the post-generation dangerous-directive safety screen, and maps cited citations to public-safe source dicts. Fail-open throughout. |
| `backend/Nutrition-backend/src/services/llm_wiki_retrieval.py` | WIKI retrieval engine. `retrieve_llm_wiki_context` is the lexical Markdown scanner; `retrieve_llm_wiki_context_db` adds the pgvector vector/hybrid path with entity-link boosting, embedding via local Ollama, registry-allowlisted embedding tables, and lexical fallback on any failure. |
| `backend/Nutrition-backend/src/api/v1/ai_agent.py` | `run_chatbot` route. Wires the RAG fallback into the `unknown_no_reviewed_source` branch, records the unknown-knowledge backlog event, builds the personalization summary (`_user_health_summary_for_rag`), filters public source fields (`_public_chatbot_sources` / `PUBLIC_CHATBOT_SOURCE_FIELDS`), and wraps the body in an inner-commit-allowing RLS transaction. |
| `backend/Nutrition-backend/src/services/chatbot_evidence_retriever.py` | Builds the reviewed-evidence retriever (AnswerCards) from governance DB rows (reviewed source + version + non-expired); the primary answer path that the RAG fallback runs only when this yields no card. |
| `backend/Nutrition-backend/src/services/chatbot_unknown_backlog.py` | Privacy-minimized unknown-knowledge backlog: builds an event from intent analysis (no raw user/model text) and stages it for source-review triage when the answer is unknown. |
| `backend/Nutrition-backend/src/services/wiki_embedding_targets.py` | Embedding-model registry (table names, query prompt prefixes) used to allowlist the pgvector table and apply the correct query-side prefix per model. |
| `backend/Nutrition-backend/src/config.py` | Settings/flags: `enable_wiki_vector_rag` (default False), `llm_wiki_retrieval_mode` (default hybrid), `llm_wiki_retrieval_enabled`, `wiki_embedding_model` (default bge-m3, 1024d), `llm_wiki_max_sources`, `ollama_model` gemma4:e4b. |
| `mobile/lib/features/chat/chat_repository.dart` | Encapsulates POST /ai-agent/chat: composes payload, caps message/conversation, handles one-shot sensitive-health-analysis consent retry, and raises the chat timeout to 90s for the slow local-LLM RAG pass. |
| `mobile/lib/features/chat/chat_models.dart` | Response/source models. `ChatbotSource` reads `source_title`, derives `familyLabel` (lemon_wiki -> 레몬 위키) and a clean compact `label` (strips section numbering and file paths via `_cleanTitle`/`_humanizePath`). |
| `mobile/lib/screens/chat_screen.dart` | Chat UI: renders bot messages, answerability caption, reviewed-source chips (`_SourceChips` with width-capped ellipsizing labels + `_showSourceSheet` detail), CTA chips, and the compliance disclaimer line. |
| `mobile/lib/features/chat/widgets/chat_analysis_card.dart` | Inline analysis-snapshot card rendered after an approved in-chat analysis run (today/health analysis). |
| `backend/Nutrition-backend/tests/unit/services/test_chatbot_wiki_rag.py` | Unit tests for the RAG fallback (grounding, off-topic, safety screen, fail-open). |
| `backend/Nutrition-backend/tests/unit/services/test_llm_wiki_retrieval_db.py` | Unit tests for the pgvector vector/hybrid retrieval + entity boosting + lexical fallback. |
| `backend/Nutrition-backend/tests/integration/api/test_ai_agent_api.py` | Integration tests covering the chat route including the wiki-RAG branch. |

**설계 결정:**

- Tiered fallback only: the RAG path runs ONLY for the benign `unknown_no_reviewed_source` answerability. Dangerous-query policies (stop meds, diagnosis, symptoms+red-flags) fire earlier in the agent and never reach this path.
- Fail-open by design: every retrieval/LLM/parse error in both the RAG synthesis and the pgvector retrieval returns a safe minimal Korean message / lexical fallback rather than raising, so the chat route never breaks on the fallback.
- Two-tier safety: an upstream classifier blocks dangerous queries, PLUS a post-generation safety screen (`_DANGEROUS_DIRECTIVE_PHRASES`) that is high-precision only (command/permission-form medication-change directives), deliberately excluding bare words like 진단/치료/처방 and negated-safe forms to avoid degrading legitimate 'consult a professional' answers.
- On-device LLM + local embeddings: synthesis uses local Gemma (gemma4:e4b via Ollama) at temperature 0; query embedding uses the local Ollama embeddings API (default bge-m3, 1024d) — no cloud LLM in the RAG path.
- Feature-gated vector RAG: `enable_wiki_vector_rag` defaults False and `llm_wiki_retrieval_mode` defaults hybrid; vector/hybrid only activate when the flag is on AND pgvector embeddings are loaded, else it silently uses the lexical scanner. The RAG fallback itself (answer_with_wiki_rag) is always wired in code; live activation is via env/compose override (commit 9b4e644d enables it in compose).
- Compliance: every RAG answer carries a fixed SAFETY_DISCLAIMER ('일반 정보, 정확한 판단은 의사/약사와 상담'), never claims to be a reviewed medical source, and personalization is explicitly 'never a diagnosis source — defer to experts'.
- Privacy: personalization summary and the unknown-knowledge backlog store no raw user/model free text; sources are filtered through a `PUBLIC_CHATBOT_SOURCE_FIELDS` whitelist; wiki `source_url` is intentionally omitted (repo-internal relative path would be a dead link).
- SQL safety: pgvector table name is interpolated (dimension-typed columns can't be bound params) but validated against a registry allowlist (`_require_embedding_table`) before reaching the query; uses `extensions.<=>`/`extensions.vector` schema-qualified operators, which require the lemon_app role to have USAGE on the extensions schema (scripted in commit 367b26bf).
- RLS: run_chatbot is wrapped in `rls_request_transaction_allow_inner_commit` (Step 8 Phase C2 hybrid CM) so the unknown-backlog insert and inner analysis commits survive under lemon_app FORCE-RLS.
- Latency-driven prompting: answer token cap is a 1500-token runaway backstop (a tight 600 cap truncated mid-reasoning to empty content); brevity is driven by a '5문장 이내' prompt instruction (~29s -> ~17s), and the mobile client raises its timeout to 90s for this path.


## 2. 영양제 OCR & 파서 (라벨 성분 추출)

**한 줄:** A recall-first supplement-label pipeline that turns CLOVA/Paddle OCR text into structured, span-grounded, Korean-localized ingredient/amount rows by combining a gated on-device gemma LLM parse with deterministic OCR fallbacks.

**상태:** partially-done — The deterministic parser, span grounding, recall recoveries, Korean name+section localization, candidate filtering, multi-image fusion, and Ollama hardening are DONE and live. The active live OCR path is a reduced subset: CLOVA OCR (full image) + best-effort gemma vision/translation assist. Paddle local OCR is implemented but OFF live (arm64 SIGSEGV → CLOVA fallback). YOLO ROI detection and multimodal verification are implemented but experimental/off-by-default (gated False in config). Async multi-image fusion was deferred (solved via the sync route path). All subsystem source files are committed and clean on this branch (no untracked code, no TODO/FIXME markers).

This branch rebuilds supplement-label extraction into a layered, recall-oriented pipeline. Image OCR (CLOVA cloud and/or PaddleOCR local, selected by a provider factory) feeds an on-device gemma (Ollama) structured-output parser; when that LLM fails or returns empty on dense labels, the system degrades gracefully (fail-open) into a large set of deterministic OCR fallbacks — split-line name/amount pairing, Korean 원재료명 declaration mining, %DV false-positive guards, CFU magnitude-counter rows (억/조/billion), multi-column duplicate-form merging, and compound-name fragment fusion — rather than returning an empty result or 5xx. Every model- or pattern-proposed amount is span-grounded against the OCR text so a hallucinated number can never reach the "review before save" UI (names are kept, ungrounded amounts nulled). Two Korean-localization passes were added for the KR-market launch: a deterministic EN→KO nutrient-name dictionary for 한글(영문) display, and a best-effort batched gemma translation of English precaution/intake/functional sections (with word-box fragment coalescing). It also adds single-product multi-image fusion, non-ingredient OCR noise filtering, gated raw-OCR-text retention behind a dedicated consent, and Ollama performance/robustness work (resident model keep_alive, per-event-loop parse semaphore, time-budget retries).

**핵심 파일:**

| 파일 | 역할 |
|---|---|
| `backend/Nutrition-backend/src/services/supplement_parser.py` | Core orchestrator (~121KB): runs the LLM parse, fail-open degradation, and all deterministic OCR recall fallbacks (declaration mining, split-line amount pairing, CFU counters, name fusion, layout/section fallbacks); persists the owner-scoped snapshot. |
| `backend/Nutrition-backend/src/llm/ollama.py` | OllamaSupplementParser + OllamaChatClient: gemma structured-output parse with per-event-loop serialization semaphore, time-budget retries, salvage-on-validation-error, and payload normalization. |
| `backend/Nutrition-backend/src/llm/ollama_vision.py` | OllamaVisionAssistAdapter: gated local gemma vision channel for amount/category enrichment, OCR-empty fallback, and structured verification; all payloads carry keep_alive. |
| `backend/Nutrition-backend/src/services/supplement_span_grounding.py` | Pure 'never guess an amount' guardrail: NFKC/casefold-normalized substring grounding that nulls any amount/unit not present in the OCR text while keeping the ingredient name. |
| `backend/Nutrition-backend/src/services/supplement_label_vlm_extractor.py` | gemma4 layout-structuring head: reconstructs name\|amount\|unit\|%DV rows from OCR text (+optional ROI crop), routed through span-grounding; one additive evidence_union candidate, never sole source. |
| `backend/Nutrition-backend/src/services/nutrient_display_name_localizer.py` | Deterministic EN→KO ingredient-name dictionary (KDRIs 2025 + curated supplement vocab); rewrites display_name to Korean, preserves English in original_name for 한글(영문) render and amount/dedup matching. |
| `backend/Nutrition-backend/src/services/supplement_label_localizer.py` | Best-effort batched gemma translation of English precaution/intake/functional section text to Korean, with OCR word-box precaution fragment coalescing; never blocks analysis on failure. |
| `backend/Nutrition-backend/src/services/supplement_candidate_filter.py` | Conservative drop of non-ingredient OCR pattern-fallback noise (nutrition-facts headers, 기준치/별도 boilerplate, bare units, 1-2 char Latin fragments) while preserving real nutrients. |
| `backend/Nutrition-backend/src/ocr/factory.py` | Builds the OCR adapter bundle (CLOVA/Paddle/Google Vision primary, fallback chain, secondary-merge ensemble, YOLO ROI, vision-assist) from settings gates with per-request provider override. |
| `backend/Nutrition-backend/src/ocr/providers/clova.py` | NAVER Cloud CLOVA OCR adapter — the current live primary provider (per ops .env override; arm64 Paddle is SIGSEGV-prone). |
| `backend/Nutrition-backend/src/ocr/providers/paddle.py` | PaddleOCR local adapter (primary per code default, but disabled live due to arm64 conv-kernel SIGSEGV); supports DB-detection thresholds and secondary-merge recognizer dirs. |
| `backend/Nutrition-backend/src/ocr/multilingual_adapter.py` | Adapter that runs/compares providers and selects the higher-confidence normalized OCRResult while preserving the single-image OCR boundary (no raw image/text storage). |
| `backend/Nutrition-backend/src/parsing/layout_parser.py` | Coordinate-based layout parser turning provider OCR boxes into LabelLayout/LabelSection structures used for ROI-aware section/precaution fallbacks. |
| `backend/Nutrition-backend/src/ocr/text_normalizer.py` | Provider-agnostic OCR text normalization fed into the parser and span grounding. |
| `backend/Nutrition-backend/src/services/supplement_label_vlm_extractor.py` | (see above) — duplicate listing guard removed in narrative; the VLM head is the evidence_union additive extractor. |

**설계 결정:**

- Fail-open by design: if the local gemma LLM parse errors or returns empty on substantial OCR, the pipeline degrades to deterministic OCR fallbacks and emits a review warning instead of returning empty/5xx (supplement_parser.py:425-436).
- Span-grounding guardrail ('never guess an amount'): every model/pattern amount must appear as a normalized substring of the OCR text or its amount/unit is nulled (name retained) — recall preserved, hallucinated numbers blocked from the confirm-before-save UI.
- Two-track Korean localization: nutrient NAMES use a deterministic closed-vocabulary EN→KO dictionary (no LLM, fully testable); free-text label SECTIONS use a best-effort batched gemma translation — explicitly kept separate because LLMs translate nutrient names unreliably.
- On-device vs cloud split: OCR can be cloud (CLOVA / Google Vision, gated by ALLOW_EXTERNAL_OCR) or local (Paddle); all LLM parsing/vision/translation runs on a local resident gemma (Ollama keep_alive=-1) — no label text leaves to a third-party LLM.
- Heavy gating with conservative config defaults: enable_multimodal_llm, enable_vision_classifier (YOLO ROI), enable_multimodal_verification all default False, multimodal_ocr_assist_policy defaults 'disabled'. NOTE config default ocr_primary_provider='paddleocr', but live runtime overrides to CLOVA via ops .env (Paddle arm64 SIGSEGV) — config defaults diverge from live (drift risk).
- Concurrency safety for the single resident model: structured parses serialize through a per-event-loop asyncio.Semaphore (ollama_parse_max_concurrency default 1) to avoid the empty-output failure mode from KV-cache contention; parse retries are bounded by a wall-clock budget that sits under the 120s mobile upload timeout.
- Privacy/compliance: raw OCR text is retained only under BOTH an operator opt-in flag (store_raw_ocr_text, default False) AND a per-user RAW_OCR_TEXT_RETENTION consent; grounding/localizer/VLM modules log no raw OCR text and store nothing; snapshot persists via owner-scoped persist_scope (RLS).
- Conservative recall recovery: compound-name fusion only appends known salt/form continuation words (never a second standalone name); CFU magnitude kept in the unit ('억 CFU') rather than multiplied out; non-ingredient filter drops only exact header/boilerplate/unit tokens and 1-2 char Latin fragments, never real nutrients.
- Single-product multi-image batches are fused into one result (route-level sync fusion path) with a salvage path that translates over-limit pydantic ValidationErrors into a recoverable parser_used=False degrade instead of HTTP 500.


## 3. 영양제 분석 API · 비동기 파이프라인 · 학습

**한 줄:** The supplement label analysis API: a 202+poll async OCR/parse/vision pipeline with single- and multi-image (distinct or one-shot fused) modes, user-confirmed registration, and post-commit learning artifact/embedding jobs, all under route-owned RLS transactions.

**상태:** partially-done — synchronous analyze/analyze-multi (distinct + sync one-shot fusion when its flag is on), registration, poll/finalize, barcode, ocr-text parse, explain, and post-commit learning offload are all implemented, committed clean (no working-tree WIP), and the sync path is live. The 202+poll async pipeline and one-shot fusion are fully built but experimental-off-by-default (dark-launched behind supplement_analyze_async_enabled / supplement_one_shot_fusion_enabled, both default False), enabled only via env override. Local Gemma vision extraction and multimodal verification are likewise gated off by default. Per memory, async multi-image fusion was NOT wired into _submit_async_multi_analysis (fusion only reachable via the sync path).

This subsystem turns supplement-label photos into structured, user-confirmable supplement records. The POST /supplements/analyze and /analyze-multi routes can run either synchronously or (behind supplement_analyze_async_enabled) pre-create analysis run rows in `processing`, return 202 with a poll URL, and hand the heavy OCR+parser+vision pipeline to an in-process asyncio worker that flips each run to `requires_confirmation`/`failed` in the same transaction so partial snapshots are never polled as ready; a worker-deadline staleness check prevents wedged clients after a crash/restart. Multi-image supports two strategies: `distinct_products` (one run per image) and `single_product` one-shot fusion, which OCRs every image, fuses the text, and parses ONCE into a single run (raw OCR text never persisted). Registration (POST /supplements) validates an owned preview, persists the user_supplement + ingredients, marks the preview confirmed, and schedules a post-commit learning-embedding BackgroundTask. All owner reads/writes run inside route-owned RLS transactions (rls_request_transaction / get_rls_context_session) as part of the RLS Step 7/8 migration to the lemon_app posture, and learning side-effects (image object storage, section-annotation enqueue, embedding job) are deferred to fresh privileged learning sessions post-commit so a mid-request commit never drops the FORCE-RLS GUCs.

**핵심 파일:**

| 파일 | 역할 |
|---|---|
| `backend/Nutrition-backend/src/api/v1/supplements.py` | Router for all supplement routes (~18 endpoints): analyze, analyze-multi, analysis-sessions, poll (analyses/{id} and group), finalize, barcode lookup, ocr-text parse, explain, registration (POST ""), list/get/delete, categories, recommendations, comprehensive. Holds sync-vs-async branching, multi-image merge/aggregation helpers, consent gates, and post-commit learning task scheduling. |
| `backend/Nutrition-backend/src/services/supplement_analysis_worker.py` | In-process async worker (run_single/run_multi_supplement_analysis_job): opens a fresh RLS-enforced request-engine session, re-applies owner RLS context, runs the pipeline, flips run status atomically, marks failed on any error (never re-raises), then runs learning artifacts post-commit best-effort. |
| `backend/Nutrition-backend/src/services/supplement_image_analysis.py` | Core orchestration: analyze_supplement_image (single/distinct), analyze_fused_supplement_images + extract_supplement_ocr_only (one-shot fusion), OCR ensemble/multimodal/vision-amount merge stages with optional-stage budgets, pipeline-metadata builders, and the two post-commit learning entrypoints store_supplement_learning_artifacts / store_supplement_learning_embedding_job. Defines SupplementImageAnalysisAdapters, SupplementImageAnalysisResult, and the deferred-input dataclasses. |
| `backend/Nutrition-backend/src/services/supplement_intake.py` | Image validation (MIME/size/decode), idempotency-keyed intake row creation (create_supplement_analysis_intake with initial_status PROCESSING for async), preview serialization (supplement_analysis_run_to_preview), and conflict/validation error types. |
| `backend/Nutrition-backend/src/services/supplement_registration.py` | User-confirmed registration: create_user_supplement_from_confirmation (validate nutrient codes + owned preview + evidence refs, persist supplement/ingredients under persist_scope, mark preview confirmed), list/get/soft-delete owner records, category resolution, and active-supplement snapshot for downstream context. |
| `backend/Nutrition-backend/src/learning/pipeline.py` | Learning pipeline: collect_active_learning_consents, enqueue_learning_embedding_job_for_confirmation (commits + reads FORCE-RLS learning tables), build_confirmed_supplement_learning_metadata. DO-NOT-TOUCH commit semantics drive the post-commit/privileged-session design. |
| `backend/Nutrition-backend/src/learning/factory.py` | build_learning_object_store and the privileged learning session factory (get_learning_sessionmaker) that bypasses FORCE RLS for post-commit learning writes under the lemon_app posture. |
| `backend/Nutrition-backend/src/learning/object_storage.py` | Supabase-Storage-backed learning image object store (maybe_store_learning_image_object) used by the post-commit artifact task; consent- and retention-gated. |
| `backend/Nutrition-backend/src/learning/supplement_section_labels.py` | Derives sanitized supplement-section YOLO annotation candidates from OCR layout for the section-detector training dataset (enqueued post-commit). |
| `backend/Nutrition-backend/src/services/supplement_candidate_filter.py` | Drops OCR non-ingredient noise (nutrition-facts headers, units, %DV reference rows) while preserving real nutrients; added to fix multi-image fusion noise. |
| `backend/Nutrition-backend/src/services/nutrient_display_name_localizer.py` | Deterministic EN→KO ingredient display-name dictionary so recognized nutrient names render in Korean (with English in parentheses). |
| `backend/Nutrition-backend/src/services/supplement_parser.py` | Structured OCR-text→supplement parser (LLM + fallback) producing ingredients/amounts/precautions; binding constraint for amount extraction quality. Also hosts gated raw-OCR-text storage. |
| `backend/Nutrition-backend/src/db/dependencies.py` | Provides rls_request_transaction / rls_request_transaction_allow_inner_commit / get_rls_context_session — the route-owned RLS seam the analyze and registration routes wrap their owner writes in. |
| `backend/Nutrition-backend/src/config.py` | Feature flags and budgets: supplement_analyze_async_enabled, supplement_one_shot_fusion_enabled, supplement_analyze_worker_deadline_sec (300), enable_supplement_label_vision_extraction, enable_multimodal_llm/verification, analyze_optional_stage_budget_sec, enable_image_learning_pipeline, enable_pgvector_storage — all default False/off. |

**설계 결정:**

- 202+poll async pipeline (supplement_analyze_async_enabled) is dark-launched / default False: endpoints stay fully synchronous until the flag flips, so async is the intended target for the mobile-timeout fix but is NOT the live default on this branch.
- One-shot single-product fusion (supplement_one_shot_fusion_enabled, default False) always runs SYNCHRONOUSLY even when async is on, because the per-image async worker has no fusion mode; single_product is routed to the sync fused path and distinct_products to the async per-image worker.
- Async worker correctness: status flip to requires_confirmation/failed happens in the SAME transaction as pipeline writes so a partial parsed_snapshot can never be observed as ready; a worker-deadline staleness check (updated_at + 300s) reports dead workers as failed so polls never wedge.
- RLS Step 7/8 posture: every owner read/write is wrapped in route-owned RLS transactions (rls_request_transaction / get_rls_context_session) for the lemon_app FORCE-RLS cutover; the async worker opens a fresh RLS-enforced request-engine session and re-applies owner RLS context (never the privileged learning factory for the pipeline itself).
- Post-commit learning offload: learning image storage, section-annotation enqueue, and embedding-job enqueue run AFTER the request transaction commits, on fresh privileged learning sessions (get_learning_sessionmaker, bypasses FORCE RLS), because a mid-request commit would drop the transaction-local RLS GUCs and the learning enqueue commits/reads FORCE-RLS tables itself (DO-NOT-TOUCH).
- Learning is best-effort and fail-open: any post-commit learning failure is logged and swallowed so a learning miss never surfaces to the user or affects the now-ready run.
- Privacy/compliance: raw image and raw OCR text are never persisted by default (raw_image_stored/raw_ocr_text_stored=False in every audit); only parsed snapshot + OCR text hash are stored. Raw OCR storage is a separate gated feature (store_raw_ocr_text) requiring a dedicated consent.
- Consent gating: routes require OCR_IMAGE_PROCESSING (and conditionally EXTERNAL_OCR_PROCESSING) plus SENSITIVE_HEALTH_ANALYSIS for registration; learning consents are only collected when learning flags are on.
- On-device vs cloud: local Gemma4 vision extraction (enable_supplement_label_vision_extraction) and multimodal assist/verification are off by default and run under an optional-stage time budget (analyze_optional_stage_budget_sec) to protect the mobile timeout; the local Paddle ensemble OCR is offloaded to a single-worker thread and is intentionally load-bearing (not budget-capped). Live OCR is effectively CLOVA-only with Gemma assist toggled via env override.
- Idempotency: a stable non-null client_request_id is synthesized for async submits (async-/multi- prefixes) so the worker reuses the pre-created run instead of orphaning it; mismatched image bytes for an existing key returns 409.
- Audits for the async/202 path are emitted inside the request-managed transaction so they go out-of-band via the privileged audit engine (flip-safe under lemon_app), since the live Request object is gone after the 202 response.


## 4. 음식/식단 분석 & CLIP 비음식 필터

**한 줄:** A review-only food image analysis pipeline that gates on a YOLO food detector, optionally filters non-food crops with a CLIP zero-shot filter, classifies the dish with a DINOv3 linear probe over 40 Korean-food classes, and joins per-100g nutrition — all behind off-by-default feature flags and never auto-confirming user data.

**상태:** partially-done / experimental-off-by-default. The full pipeline (YOLO gate, CLIP non-food filter, DINOv3 40-class classify, nutrition mapping, preview/confirm API, RLS persistence, migrations, unit tests) is implemented and wired end-to-end, but all three feature flags default False and it is not live. Model weights (best.pt exp16b gate, probe_head.pt) are git-ignored local-only files that must be provisioned in the image/volume; only the 40-class CSV and probe_classes.json are tracked. The CLIP filter is newly added and explicitly not latency-validated for the synchronous mobile request path. Per project memory the gated DINOv3 backbone has had container permission/download issues, so live food classification has not been confirmed working.

This branch turns the meal-image endpoint into a structured vision pipeline that produces *candidates for user confirmation only*. The canonical runtime classifier (Food-backend/src/classifier/food_classifier.py) runs an exp16b YOLO "is there food?" gate, then classifies the whole image (not a crop) with a frozen DINOv3 backbone + trained linear probe across 40 classes, and joins a per-100g nutrition row from a 40-class CSV. A new adapter (vision/food_dino_classifier.py) loads that teammate module by file path, sanitizes its output (clamped bbox, bounded confidence, validated strings), and the meal service (services/meal_image_analysis.py) merges detector + classifier results into a bounded, advisory nutrition snapshot with explicit warning codes (food_classification_review_required, food_classifier_empty/unavailable, manual_entry_required). The most recent work imported a teammate CLIP zero-shot non-food filter (food_filter.py) and wired it as an optional cutoff *between* the YOLO gate and DINOv3 classification (YOLO->CLIP->DINOv3) to reject YOLO false positives like people, empty dishes, sauce cups, and paper cups. A 40-class nutrition table + migration (0045/0046) and DB lookup helpers feed the advisory totals. Everything is gated off by default and image bytes are never persisted (sanitized snapshots only).

**핵심 파일:**

| 파일 | 역할 |
|---|---|
| `backend/Nutrition-backend/src/services/meal_image_analysis.py` | Core orchestration: validates image, runs detector+classifier behind flags, builds sanitized candidate + advisory per-serving nutrition snapshots, defines warning codes, persists preview (no image bytes) |
| `backend/Nutrition-backend/src/vision/food_dino_classifier.py` | Production adapter: lazily file-path-imports the Food-backend FoodClassifier, sanitizes name/confidence/bbox/nutrition, passes through CLIP filter flags; fail-safe on any VisionError |
| `backend/Food-backend/src/classifier/food_classifier.py` | Canonical runtime classifier (exp16b YOLO gate -> optional CLIP non-food cut -> whole-image DINOv3+linear-probe 40-class -> 100g nutrition join); KR_NAME EN->KO map |
| `backend/Food-backend/src/classifier/food_filter.py` | CLIPFoodFilter: zero-shot food/non-food via CLIP-ViT-B/16 with curated KO-food + non-food prompts; lazily loaded, fail-open on any inference error |
| `backend/Nutrition-backend/src/vision/food_yolo.py` | FoodYoloDetector / FoodDetection: optional local YOLO food-candidate detector path (detect_foods, food_model_label) feeding review candidates |
| `backend/Nutrition-backend/src/api/v1/meals.py` | Meals API: POST /analyze-image (202 preview), /{id}/confirm, list/update/delete confirmed meals, explain via local WIKI RAG; all on get_rls_context_session |
| `backend/Nutrition-backend/src/config.py` | Feature flags + paths (lines 937-1032): enable_food_yolo_detector, enable_food_dino_classifier, enable_food_clip_filter all default False; classifier module/model/probe/csv paths, gate confidence 0.10, max_px 896, CLIP threshold 0.5 |
| `backend/Nutrition-backend/src/services/taxonomy_catalog.py` | DB lookups load_food_nutrition_by_class_ens / food_nutrition_per_100g used to build advisory nutrition totals from food_nutrition table |
| `backend/Food-backend/src/classifier/nutrition/food_nutrition_40class.csv` | Tracked 40-class per-100g nutrition table (class_en keyed) joined by the classifier |
| `backend/Food-backend/src/classifier/probe_classes.json` | Tracked 40-class label list for the DINOv3 linear probe (the probe_head.pt weights themselves are git-ignored, local-only) |
| `backend/alembic/versions/0045_upsert_food_nutrition_40class_v2.py` | Upserts 40-class food_nutrition rows (recreated after the original 0045 was lost, stranding the DB on a missing revision) |
| `backend/alembic/versions/0046_merge_40class_dyslipidemia.py` | Merge migration collapsing two heads (40class + dyslipidemia) back to a single alembic head |
| `backend/Nutrition-backend/tests/unit/vision/test_food_dino_classifier.py` | Unit tests for the DINO adapter incl. CLIP-filter flag passthrough (81 lines added in the CLIP wiring commit) |
| `backend/Nutrition-backend/tests/unit/services/test_meal_image_analysis.py` | Unit tests for the meal service: candidate merging, warning codes, advisory nutrition snapshot |
| `backend/Food-backend/README.md` | Documents the Food-backend vs Nutrition-backend vs legacy food_image_analysis boundary and that Food-backend/src/classifier is the canonical runtime asset location |
| `docker-compose.yml` | Backend env wiring (lines 143-159): all food flags default false, classifier/model/probe/csv paths point at /app/Food-backend, CLIP filter env; HF_TOKEN note for gated DINOv3 weights |

**설계 결정:**

- Review-only by design: the pipeline only produces candidates and an advisory nutrition estimate; it never overrides or auto-writes user-confirmed values. Outputs carry warning codes (food_classification_review_required, manual_entry_required) and the /analyze-image endpoint returns 202 requiring explicit user confirmation.
- Everything off by default: enable_food_yolo_detector, enable_food_dino_classifier, and enable_food_clip_filter all default False (config + docker-compose). The feature is shipped dark; enabling requires env overrides plus model assets present.
- Fail-open / fail-safe layering: CLIP filter errors or degenerate crops return 'treat as food' (never block a valid classification); classifier load/inference failures degrade to food_classifier_unavailable + manual_entry_required rather than 500. The CLIP filter is tri-state lazily loaded (None/False/instance) so a load failure disables it without retry.
- Whole-image classification, not crop: DINOv3 classifies the full image (max_px 896 thumbnail) because empirically full-image (0.84) beat crop (0.72) for single-dish photos; YOLO only acts as a food-presence gate, and DINO can't say 'no food' so the gate is mandatory for rejection.
- CLIP inserted as YOLO->CLIP->DINOv3 cutoff specifically to kill YOLO false positives (people, empty dishes, sauce cups, paper cups) using curated Korean-food-friendly prompts; documented latency cost (~600MB model load + per-request CPU inference) flagged as mobile-timeout-sensitive and not yet latency-validated.
- On-device / local models: classifier (DINOv3+exp16b) and CLIP run locally in the backend container; consistent with the app's on-device posture. Gated DINOv3 weights need HF_TOKEN.
- Privacy: image bytes are never persisted; only sanitized JSON snapshots (display_name, class_en, confidence, bbox, bounded nutrition) are stored. The adapter re-validates and clamps all model output (bbox clamp, confidence clip, required-string checks).
- Compliance wording: user-facing strings are Korean and avoid regulated medical language (per food_image_analysis README rules); nutrition framed as advisory estimate.
- Canonical-location split: Food-backend/src/classifier is the canonical runtime asset path; legacy backend/food_image_analysis holds the teammate handoff originals + demos. Both backends reuse 'src' package name, so their test suites must be run separately.


## 5. 프라이버시 · RLS · DB · 마이그레이션

**한 줄:** A staged FORCE-Row-Level-Security migration of the FastAPI backend onto a least-privilege Postgres request role (lemon_app), with transaction-local owner-subject GUCs, an ambient-transaction seam, privileged out-of-band audit/learning engines, and consent/audit privacy machinery.

**상태:** partially-done — Code is complete and flip-ready: all routes are on either get_rls_context_session or a CM-wrapped get_async_session (enforced by a seam-guard test), migrations 0023a/b/c exist with policies and FORCE defined, and privileged audit/learning engines + startup guard are wired. The actual enforcement (running 0023c FORCE + pointing DATABASE_URL at lemon_app with the privileged URLs) is an operator action gated behind ops/.env, not the committed default — so in a fresh checkout the app still connects as the privileged role and RLS is not yet enforcing. Per repo memory the flip was exercised and live-verified in the local Docker stack, but that posture is not encoded in the repo's default configuration.

This subsystem hardens data isolation by moving the request path from the superuser `lemon` role to a least-privilege `lemon_app` role under Postgres FORCE ROW LEVEL SECURITY. Migrations 0023a/b/c create the role + grants, owner-scoped RLS policies keyed on transaction-local GUCs (`app.current_subject` / `app.current_subject_hash`), and the FORCE flip across ~32 user-data/catalog tables (Type A plaintext owner, Type B hashed owner, Type C FK children, Type D read-all catalog). Because the GUCs are transaction-local, the code introduces an "ambient-transaction" seam: a per-request marker (`REQUEST_MANAGED_TX`) plus a `persist_scope` context manager so write/audit services either participate (flush-only) in the request transaction or own it (legacy), letting routes adopt RLS incrementally. To keep out-of-band audit writes and post-commit learning writes working once `lemon_app` (which lacks INSERT on those tables) is live, dedicated privileged audit/learning engines (`AUDIT_DATABASE_URL` / `LEARNING_DATABASE_URL`) were added, a startup guard fails fast if the flip happens without them, and three route-owned RLS context managers handle background-task and mid-request-commit edge cases. The consent layer (versioned `ACTIVE_CONSENT_POLICIES`, including a new RAW_OCR_TEXT_RETENTION opt-in) and HMAC subject/IP/UA hashing round out the privacy posture. Per repo memory the `DATABASE_URL`→`lemon_app` flip has been exercised and live-verified in the local Docker stack, but it is an ops/.env action — the default config still reuses `DATABASE_URL`, so the codebase ships flip-ready but not flip-forced.

**핵심 파일:**

| 파일 | 역할 |
|---|---|
| `backend/Nutrition-backend/src/db/rls_context.py` | Sets transaction-local owner-subject GUCs via set_config(is_local=true); SUBJECT_GUC / SUBJECT_HASH_GUC kept in sync with 0023b policies; empty value = fail-closed (0 rows). |
| `backend/Nutrition-backend/src/db/tx.py` | Ambient-transaction seam: REQUEST_MANAGED_TX marker + persist_scope() that participates (flush-only) under RLS sessions or owns the transaction (commit at outermost) for legacy sessions. |
| `backend/Nutrition-backend/src/db/dependencies.py` | FastAPI seams: get_async_session (no tx), get_rls_context_session (opens request tx + sets GUCs), and two route-owned CMs rls_request_transaction / rls_request_transaction_allow_inner_commit (after_begin listener re-applies GUCs to survive a callee's mid-request commit+refresh). |
| `backend/Nutrition-backend/src/db/session.py` | Engine/sessionmaker factories incl. privileged get_audit_sessionmaker / get_learning_sessionmaker (reuse main engine until *_DATABASE_URL set), configurable pool sizing, and verify_stage2_privileged_database_urls() startup guard. |
| `backend/alembic/versions/0023a_create_lemon_app_request_role.py` | Creates NOSUPERUSER/NOBYPASSRLS lemon_app role; grants CRUD on user-data tables, SELECT on catalog tables; password set out-of-band. Inert on its own. |
| `backend/alembic/versions/0023b_create_rls_owner_policies.py` | Owner-scoped RLS policies for lemon_app across Type A/B/C tables (GUC-matched) + read-all catalog policies; inert under superuser. |
| `backend/alembic/versions/0023c_force_row_level_security.py` | Final flip: ALTER TABLE ... FORCE ROW LEVEL SECURITY across all 0023b-covered tables; marked DO NOT APPLY until app verified on lemon_app; downgrade = NO FORCE. |
| `backend/alembic/versions/0003_create_privacy_consent_audit_tables.py` | Base privacy schema: consent_records / consent_policies / audit_logs tables underpinning consent gating and audit. |
| `backend/alembic/versions/0041_harden_ai_agent_chat_table_security.py` | Hardens chatbot tables (e.g. chatbot_unknown_knowledge_events SERVICE_POLICY USING/CHECK(true)) relevant to the run_chatbot RLS path. |
| `backend/Nutrition-backend/src/services/privacy.py` | Audit + privacy service: record_audit_event (Option A — out-of-band privileged audit write when request-managed, else legacy add+commit), _write_audit_out_of_band, create_delete_all_user_data_request bulk-delete (persist_scope). |
| `backend/Nutrition-backend/src/api/v1/privacy.py` | Privacy router (consents, deletion/bulk-delete, audit-emitting endpoints) wired onto the RLS seam. |
| `backend/Nutrition-backend/src/privacy/consent_policies.py` | Versioned ACTIVE_CONSENT_POLICIES registry with SHA-256 content hashes, incl. new RAW_OCR_TEXT_RETENTION (2026-06-21) opt-in and required/optional gating. |
| `backend/Nutrition-backend/src/security/privacy.py` | HMAC hashing helpers: hash_actor_subject (with optional dedicated audit pepper), request IP/UA hashing, bounded request-id extraction. |
| `backend/Nutrition-backend/src/main.py` | Lifespan calls verify_stage2_privileged_database_urls(settings) at startup and dispose_engine() on shutdown. |
| `backend/Nutrition-backend/src/config.py` | Settings for database_url / audit_database_url / learning_database_url (default None = reuse main) and db_pool_size / db_max_overflow per-engine-per-worker budget; store_raw_ocr_text flag. |
| `backend/Nutrition-backend/tests/unit/db/test_rls_route_seam_guard.py` | Regression guard: fails if any new route uses get_async_session outside the in-body-CM allowlist (run_chatbot + supplement analyze/upload/multi/create), preventing flip-unsafe owner reads. |
| `docs/2026-05-31-force-rls-rollout-design.md` | Authoritative design doc for the staged FORCE RLS rollout referenced throughout the migrations and seam code. |

**설계 결정:**

- Three-stage rollout (0023a role+grants → 0023b policies → 0023c FORCE) where every step before the DATABASE_URL flip is inert because the live `lemon` role is a superuser and bypasses RLS; lets policies be reviewed/staged without behavior change.
- Transaction-local owner GUCs via set_config(is_local=true): scoped to the transaction (released on commit/rollback, no connection-pool leak) and passed as bind params so the subject string can't inject SQL; an unset/empty GUC fails closed (matches 0 rows) rather than leaking.
- Ambient-transaction seam (REQUEST_MANAGED_TX marker + persist_scope) so owner-scoped routes can adopt RLS incrementally: request-managed sessions participate (flush-only, never commit/begin mid-request, which would drop the GUCs); legacy get_async_session routes keep byte-identical own-and-commit behavior.
- Privileged out-of-band engines for audit and post-commit learning writes (AUDIT_DATABASE_URL / LEARNING_DATABASE_URL): lemon_app holds only SELECT on audit_logs and FORCE-RLS learning tables would fail closed, so these run on a separate superuser/BYPASSRLS connection; they reuse DATABASE_URL until set, so pre-flip behavior is unchanged.
- Option A audit decoupling tradeoff: under request-managed sessions the audit commits out-of-band *before* the owner-row commit, so a recorded `success` audit no longer guarantees the owned row is durable (documented inversion of legacy ordering); chosen so audits survive a request rollback.
- Startup guard verify_stage2_privileged_database_urls fails fast if DATABASE_URL connects as lemon_app but the privileged URLs are unset/equal/also-lemon_app — turning a silent fail-open into a hard boot error; no-op while the request role is still privileged.
- Three distinct route-owned RLS CMs for hard cases: rls_request_transaction (post-commit BackgroundTasks must run after writes are durable, so commit happens in the route body before Starlette runs background tasks) and rls_request_transaction_allow_inner_commit (an after_begin event listener re-applies the is_local GUC on every (auto)begin to survive a DO-NOT-TOUCH callee that commits-then-refreshes, e.g. store_app_health_analysis_result in run_chatbot).
- Separate audit pepper (privacy_hash_secret_audit_pepper) so a leak of the general privacy hash secret can't correlate audit owner-subject hashes back to known subjects; falls back to the privacy secret when unset to avoid re-hashing existing rows.
- Versioned consent policies with content-hash + required/optional flag; the flip itself plus pool sizing and *_DATABASE_URL are ops/.env concerns (not committed defaults), so the branch ships flip-ready but the live default still reuses the single DATABASE_URL.


## 6. 모바일 앱 (Flutter)

**한 줄:** The Flutter client's non-chat surface — home dashboard, supplement/meal capture-and-management, onboarding+consent gating, settings/profile, build-time environment wiring, and a persisted brand theme — all built against the FastAPI backend with display-only logic and compliance disclaimers.

**상태:** done — the non-chat mobile surface is feature-complete and device-verified per commit messages (home, supplement/meal management, onboarding, consent, settings, theme, env wiring all live). Two caveats: staging/prod backend URLs are still .invalid placeholders (env wiring is intentionally deferred, dev-only live), and the Supabase Auth path is a wired-but-scaffolded seam with debug builds running on devBypass against AUTH_MODE=disabled.

This branch delivers the bulk of the consumer-facing Flutter app outside the chatbot. It rebuilt the home dashboard, food/supplement analysis-result screens, daily-records timeline, calendar, and a 4-week health-score trend to match Figma, and added two dedicated management screens (meal_management_screen.dart, supplement_management_screen.dart) for reviewing/editing/deleting saved records. The supplement OCR flow was reworked from a single long upload into an async poll (2s interval, 300s budget) with transient-failure retries, plus single-product multi-image fusion, distinct-product tabs, Korean ingredient localization, and OCR non-ingredient noise filtering. First-run onboarding (3-slide), a Korean consent-gate sheet (required vs optional consent buckets mapped to backend consent_type), profile/health-interest wizards, medication-reminder server sync, settings subscreens (profile/health-profile/reminders/policies/withdraw), and a Supabase-Auth token seam (auth_session_binder → token_session) were all added. Cross-cutting infra: a build-flavor↔environment config (app_environment/app_config) with HTTPS/cert-pin/.invalid-host release fail-closed checks, and a user-selectable brand theme persisted to shared_preferences and applied app-wide via runtime-mutable design tokens.

**핵심 파일:**

| 파일 | 역할 |
|---|---|
| `mobile/lib/core/config/app_config.dart` | Build-time config from --dart-define; normalizes base URL and fails closed in release (no token, HTTPS-only, cert pins required, rejects unprovisioned .invalid hosts). |
| `mobile/lib/core/config/app_environment.dart` | dev/staging/prod enum in lock-step with Android flavors and iOS xcconfigs; unknown/blank values default to dev so misconfig never promotes to remote. |
| `mobile/lib/screens/supplement_management_screen.dart` | Saved-supplement management: list/delete, add-from-known-category (free-text categories rejected), entry into OCR camera flow. |
| `mobile/lib/screens/meal_management_screen.dart` | Saved-meal management grouped by meal slot (아침/점심/저녁/간식) with camera-add, edit and delete-confirm sheets. |
| `mobile/lib/features/supplements/supplement_repository.dart` | Supplement/medication backend seam: async-analysis polling (300s budget), one-time consent_required(403) retry, 90s local-LLM explanation timeout, mirrored class/condition whitelists. |
| `mobile/lib/features/supplements/supplement_flow_screen.dart` | 3207-line capture/analysis flow: multi-image gallery, per-image result sync, distinct-vs-single-product handling, ingredient detail. |
| `mobile/lib/screens/dashboard_screen.dart` | Live 74KB home dashboard (header weekly strip, score cards, daily-check persistence, analysis deeplink) — the one wired into app.dart as source_dashboard. |
| `mobile/lib/features/consent/consent_gate_sheet.dart` | Korean consent gate mapping UI rows to backend consent_type buckets; 3 required (health analysis, OCR, food image) + 3 optional (external OCR, retention, learning dataset). |
| `mobile/lib/features/onboarding/onboarding_screen.dart` | First-run 3-slide onboarding with mascot art and a disclaimer slide; marks LocalPrefs.onboardingSeen then routes onward. |
| `mobile/lib/features/auth/token_session.dart` | Bearer-token session controller with Secure/Memory stores; devBypassActive lets debug builds use backend AUTH_MODE=disabled, release requires a token. |
| `mobile/lib/features/auth/auth_session_binder.dart` | Bridges AuthService access-token stream into TokenSessionController so Supabase sessions replace operator token paste without touching downstream ApiClient. |
| `mobile/lib/features/reminders/medication_reminder_sync.dart` | Medication-reminder server sync (local is source of truth; server failure keeps local + prompts retry); strips forbidden 진단/처방/치료 terms from messages. |
| `mobile/lib/shared/theme/brand_theme_controller.dart` | Riverpod notifier that persists the selected brand theme to LocalPrefs and applies it to runtime-mutable AppColor tokens (yellow↔purple etc.) app-wide. |
| `mobile/lib/screens/settings_screen.dart` | Settings root: platform-aware watch label (iOS 애플 워치 / Android 갤럭시 워치), dev-only tools gated behind !kReleaseMode, theme swatches, logout. |
| `mobile/lib/features/records/records_repository.dart` | Daily-records backend seam used by the timeline/food-search/delete-with-undo screens. |
| `mobile/lib/shared/widgets/disclaimer_list.dart` | Shared medical-compliance disclaimer widget reused across recommendation surfaces (dashboard, score, onboarding, analysis). |
| `mobile/lib/core/config/app_config.dart` | (see above) central release-safety gate for the whole app. |

**설계 결정:**

- Display/input only: all algorithms run on the backend; mobile screens go through Repository seams (supplement/records/medical/privacy/profile/reminder) per mobile/CLAUDE.md, never calling Dio directly from widgets.
- Environment fail-closed: release builds reject embedded tokens, non-HTTPS URLs, missing cert pins, and unprovisioned .invalid placeholder hosts; staging/prod URLs are still .invalid TODO placeholders, dev is the safe default.
- Auth is a scaffolded seam: token_session + auth_session_binder wire Supabase Auth tokens through, but debug builds intentionally run with devBypassActive against backend AUTH_MODE=disabled; release requires a real token.
- Async OCR analysis: client polls (2s interval, 4s for distinct-product, 300s total budget) instead of one long upload, with transient-poll-failure retries, to survive the LLM-bound multi-image pipeline past the old 120s upload timeout.
- Consent-driven access: a one-time consent_required(403) → grantConsent('sensitive_health_analysis') → retry-once pattern in the supplement repo (mirrors chat repo); consent gate maps UI to backend consent_type buckets with required vs optional separation.
- Compliance guardrails: medical-disclaimer widget required on recommendation screens; reminder messages strip forbidden 진단/처방/치료 terms to pass backend validation; supplement management rejects unknown free-text categories until the backend catalog is updated through a reviewed path.
- Theme applied via runtime-mutable AppColor tokens + a ValueKey(brandTheme) tree rebuild (GoRouter preserves nav state), persisted to shared_preferences and gracefully in-memory if prefs fail to load.
- Platform-aware UX: watch label and local API host (10.0.2.2 vs 127.0.0.1) branch on defaultTargetPlatform/TargetPlatform.


## 7. 영양 계산 · 알고리즘 · KDRIs

**한 줄:** A net-new, deterministic, source-backed nutrition computation core (KDRIs lookup, BMR/TDEE/activity/BMI algorithms, weight prediction, deficiency + 5-card comprehensive analysis, chronic-condition routing, AUDIT-KR scoring) plus the AI daily-coaching route, all returning safe Korean user-facing copy.

**상태:** done — the subsystem is fully implemented and integrated (called from api/v1/supplements.py, api/v1/nutrition.py, services/analysis_results.py; daily-coaching route live). Caveat: KDRIs runs on the 2020-sample fixture by default; the 2025 official dataset is committed but only active when explicitly enabled (the production gate enforces this). The separate Korean-coaching refactor (coaching.py / nutrient_names.py) and the chronic-condition auto-load helper (_apply_stored_chronic_conditions) noted in project memory are NOT on this branch — they live on feat/coaching-ko-supplement-conditions. The '40-class nutrition DB' belongs to the food YOLO classifier subsystem, not these paths.

This branch introduces the entire nutrition-algo subsystem (21 files, ~7,509 insertions, all net-new vs origin/main). It delivers: (1) a KDRIs reference engine (kdris.py) that loads either the 2020-sample fixture or the 2025 official dataset from CSV, switched by the KDRIS_DATA_VERSION setting and tracked via a source manifest; (2) deterministic metabolism/activity/BMI algorithms (Mifflin/Cunningham/Katch-McArdle BMR, METs/cadence/heart-rate TDEE corrections, KSSO waist-circumference abdominal-obesity flag, activity score v1-v4); (3) weight prediction with a safe model selector choosing between a 7-step static approximation and a Hall-lite dynamic simulator, including fail-closed disabling for unsafe chronic profiles and a predicted-vs-measured mismatch evaluator; (4) deficiency analysis and a 5-card comprehensive analyzer that cross-references intake against KDRIs plus a chronic-disease supplement matrix, emitting deficiency/excess/caution/purpose data with drug, warfarin/herb, pregnancy vitamin-A, and smoker corrections; (5) source-backed chronic-condition nutrient prioritization and clinical-guideline routing (ADA/DASH/KDOQI/EASL) with referral gating, plus AUDIT-KR alcohol self-check scoring that pauses supplement recommendation above the dependence cutoff. The /daily-coaching API route wraps a deterministic agent adapter with consent enforcement, RLS, and audit logging. The design intent throughout is to keep the backend focused on validation/scoring/safe-routing while surfacing reviewed Korean message copy and source citations rather than computing disease-specific clinical targets.

**핵심 파일:**

| 파일 | 역할 |
|---|---|
| `backend/Nutrition-backend/src/nutrition/kdris.py` | KDRIs reference loader: parses 2020-sample and 2025 official CSV schemas, resolves dataset version/path from settings, profile/age/sex/pregnancy matching, dataset-status manifest tracking. |
| `backend/Nutrition-backend/src/nutrition/comprehensive.py` | 5-card comprehensive analyzer (largest module, ~1237 lines): deficiency/excess/caution/purpose computation, chronic-matrix cross-reference, drug/warfarin/pregnancy/smoker cautions, diet score. NOTE: uses its own MVP inline _KDRIS_TABLE static dict, not kdris.py. |
| `backend/Nutrition-backend/src/nutrition/deficiency_analysis.py` | Per-nutrient intake classification vs KDRIs, referral-route gating for special profiles, nutrient-interaction and smoker/vitamin-C messages, forbidden-term safety guard. |
| `backend/Nutrition-backend/src/nutrition/chronic_priority.py` | Source-backed chronic-condition nutrient priority table (pydantic-validated JSON) yielding sort boosts only for already-low nutrients; caution nutrients explicitly never boosted. |
| `backend/Nutrition-backend/src/nutrition/chronic_nutrition_guidance.py` | Condition-to-guideline router (ADA diabetes / DASH hypertension / KDOQI CKD / EASL liver) with focus nutrients, referral_required flags, and safe Korean route messages. |
| `backend/Nutrition-backend/src/nutrition/audit_kr.py` | AUDIT-KR 10-item alcohol self-check scoring with sex-specific cutoffs; pauses supplement auto-recommendation above dependence cutoff and routes to counseling. |
| `backend/Nutrition-backend/src/nutrition/source_manifest.py` | KDRIs source manifest schema/version tracking used to report dataset provenance and review status. |
| `backend/Nutrition-backend/src/nutrition/unit_converter.py` | Nutrient unit conversion helpers (carries a TODO about source-specific magnesium UL modeling). |
| `backend/Nutrition-backend/src/algorithms/metabolism.py` | BMR/TDEE engine: Mifflin/Cunningham/Katch-McArdle BMR, step-based PAL, METs/walking-cadence (Tudor-Locke)/heart-rate (Keytel) exercise-kcal and activity-code TDEE. |
| `backend/Nutrition-backend/src/algorithms/activity.py` | Activity score v1-v4: recommended steps, HRmax/target-HR, resting-HR moving median, percentile bonus, chronic-disease/smoking multiplier, lifestyle safety messages. |
| `backend/Nutrition-backend/src/algorithms/bmi.py` | BMI calc/classification (asia_kr region), body-fat reference flag, KSSO sex-specific waist-circumference abdominal-obesity flag. |
| `backend/Nutrition-backend/src/prediction/selector.py` | Safe weight-prediction model selector choosing Hall-lite vs 7-step per period based on settings/engine enum. |
| `backend/Nutrition-backend/src/prediction/hall.py` | Hall-lite dynamic weight simulator: kcal/kJ conversion, composition RMR, energy-balance partitioning into fat/fat-free mass, day-by-day stepping. |
| `backend/Nutrition-backend/src/prediction/weight.py` | 7-step static weight prediction, alcohol-kcal-from-volume, fail-closed disabled response for unsafe chronic profiles, predicted-vs-measured mismatch evaluator (2-week). |
| `backend/Nutrition-backend/src/prediction/body_composition.py` | Initial fat/fat-free mass estimate (Deurenberg body-fat %) feeding the Hall-lite simulator. |
| `backend/Nutrition-backend/src/api/v1/ai_agent.py` | /ai-agent/daily-coaching route (deterministic agent adapter, sensitive-health consent, RLS session, agent-memory upsert, sensitive audit) and chatbot wiring; the live Korean-coaching surface on this branch. |
| `backend/Nutrition-backend/src/services/supplement_recommendation.py` | Supplement impact preview service: builds preview profile, combines warnings, summary message, confirmation gating, safe-message validation. |
| `backend/Nutrition-backend/data/nutrition_reference/kdris/kdris_2025.csv` | 2025 official KDRIs dataset (the production-target dataset, with kdris_2020.csv as the sample fixture and source manifest/metadata alongside). |

**설계 결정:**

- KDRIs dataset is feature-flag selected: KDRIS_DATA_VERSION (Literal '2020-sample' | '2025', default '2020-sample') + optional explicit path/manifest. A production gate in config.py forbids deploy unless KDRIS_DATA_VERSION=2025 AND ALLOW_SAMPLE_KDRIS=false, so the safe default is the sample fixture and the 2025 official data must be explicitly opted into.
- Deterministic-first / on-device posture: the daily-coaching adapter runs deterministically and only attaches an LLM client (Ollama/SGLang/local) when configured; memory/audit are skipped when output.status == 'preview'. Coaching messages are reviewed Korean copy baked into the algorithm modules, not LLM-generated free text.
- Safety-by-construction: multiple fail-closed paths — weight prediction disables itself for unsafe chronic profiles (should_disable_weight_prediction), AUDIT-KR pauses supplement recommendation above the dependence cutoff, CKD/liver guides set referral_required and pause KDRIs auto-analysis. deficiency_analysis has a contains_forbidden_terms guard and _validate_safe_messages enforces safe user copy.
- Source-backed, evidence-citing design: chronic_priority.py validates every rule's source_ids and message_key against a manifest at load (pydantic model_validator); guideline router carries official source titles/URLs (ADA/NHLBI/KDOQI/EASL). Boosts only re-rank nutrients already classified DEFICIENT/LOW — they never invent a deficiency.
- The /daily-coaching route is RLS-migrated (get_rls_context_session, plus rls_request_transaction_allow_inner_commit imported for the chatbot path) and consent-gated on SENSITIVE_HEALTH_ANALYSIS with out-of-band sensitive audit logging, consistent with the branch's RLS Step 8 work.
- Reference data is committed in-repo (data/nutrition_reference/...) and resolved via resolve_nutrition_reference_root(); CSV loads are lru_cached for runtime performance.


## 8. 인프라 · 배포 · 설정

**한 줄:** The Docker/compose/settings/CI/startup-guard layer that builds and runs the FastAPI backend (with Postgres+pgvector, Redis, on-device Ollama, CLOVA/Paddle OCR) and enforces fail-fast configuration and RLS privilege separation before serving traffic.

**상태:** Live infra is done and verified for the local docker stack: the RLS Stage-2 flip is wired in compose and the startup guards, CLOVA-only OCR defaults, KDRIs 2025, one-shot fusion, and wiki vector RAG are all enabled by default. CI gates are in place. Gated/off-by-default subsystems remain experimental: local PaddleOCR (retraining, arm64 SIGSEGV), YOLO section detector, food DINO/CLIP classifiers, multimodal verification, and the image-learning pipeline are all flagged off in compose. The compose flip topology (lemon_app DSNs) is committed in docker-compose.yml but depends on operator-managed secrets (.env: CLOVA creds, HF_TOKEN, lemon_app role password) that are not in the repo.

This branch turns a loose dev stack into a deployable, gated one. docker-compose.yml became the single source of runtime truth: it pins the RLS Stage-2 connection topology (app connects as non-superuser lemon_app, while AUDIT/LEARNING use a privileged lemon engine), pins OCR/KDRIs/fusion/RAG env defaults for the current CLOVA-only phase, and points the chatbot at the pgvector LLM-WIKI corpus. The Dockerfile gained build-arg-gated heavy deps (PaddleOCR/torch/vision off by default), a gosu-based docker-entrypoint.sh that fixes ownership of root-owned HF/Paddle cache volumes before dropping to an unprivileged user, and a healthcheck. main.py's lifespan now fails fast at startup on two classes of misconfiguration: missing privileged audit/learning engines under the lemon_app flip (verify_stage2_privileged_database_urls) and an inconsistent OCR provider config (build_supplement_ocr_adapter). config.py centralizes feature flags, configurable DB pool sizing, and a large production validator that rejects insecure defaults. CI (.github/workflows/ci.yml) adds lint/test/security/dependency-audit plus newly-added Docker-image-build and Next.js frontend-build gates, with a separate agent-backend-ci.yml for the chatbot package.

**핵심 파일:**

| 파일 | 역할 |
|---|---|
| `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/docker-compose.yml` | Primary runtime spec: db (pgvector/pg16), redis, backend; pins RLS Stage-2 DSNs (lemon_app app role + lemon audit/learning), OCR/KDRIs/fusion/RAG env defaults, and the alembic-upgrade-then-uvicorn startup command (migrations run as privileged lemon). |
| `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/backend/Dockerfile` | Python 3.13-slim image; build-arg gates for local OCR / vision / torch index / Paddle preload; gosu added in a separate layer to preserve the torch cache; starts as root for entrypoint chown then drops to lemon; HEALTHCHECK on /health. |
| `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/backend/docker-entrypoint.sh` | chowns root-owned named cache volumes (HF hub / PaddleX / Ultralytics config) then execs the command as the unprivileged lemon user via gosu, fixing gated-DINOv3 PermissionError on cache writes. |
| `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/backend/Nutrition-backend/src/main.py` | FastAPI entrypoint; lifespan runs the Stage-2 privileged-engine guard and the OCR-adapter build guard (both fail-fast at startup), installs TrustedHost/CORS/SecureHeaders/RateLimit middleware, and exposes /health and /ready. |
| `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/backend/Nutrition-backend/src/config.py` | Pydantic Settings: all feature flags, configurable db_pool_size/db_max_overflow, optional audit/learning DSNs, and the large model_validator enforcing production fail-closed rules (auth, OCR creds, allowed hosts/origins, privacy secret length). |
| `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/backend/Nutrition-backend/src/db/session.py` | Engine factory: _engine_kwargs applies pool sizing to main/audit/learning engines; verify_stage2_privileged_database_urls fails fast when DATABASE_URL is lemon_app but audit/learning URLs are unset, equal to it, or also lemon_app. |
| `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/backend/.env.example` | Documented env template; reflects the deployed CLOVA-only OCR phase (note: diverges from config.py code defaults which stay paddleocr/local-first), Supabase Auth/JWT profile, all phase-gate flags default off/0. |
| `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/.github/workflows/ci.yml` | Main CI gate on PR/push to develop/main: black+ruff lint, backend pytest unit, flutter analyze/test, gitleaks+detect-secrets, advisory pip-audit/flutter outdated, plus newly-added backend Docker image build and Next.js typecheck+build jobs. |
| `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/.github/workflows/agent-backend-ci.yml` | Dedicated AI-agent chatbot CI: agent package tests, chatbot route contract tests, merge/backlog smokes, medical-wiki dry-run evals (skipped if manifest absent), targeted ruff/compileall, and an opt-in live SGLang merge smoke via workflow_dispatch. |
| `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/docker-compose.ocr-models.yml` | Optional overlay mounting exported PaddleOCR recognition model dirs from a stable host path (kept separate because Docker Desktop fails bind mounts under external paths with spaces). |
| `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/docker-compose.google-vision.yml` | Optional overlay for the Google Vision OCR opt-in (ADC credentials path). |
| `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/backend/scripts/preload_paddleocr.py` | Build-time PaddleOCR weight preloader invoked by the Dockerfile only when PRELOAD_PADDLEOCR=true. |
| `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid/scripts/check_ai_agent_integration_preflight.py` | Repo-level preflight that reports (path-only, never reads .env contents) on stray secrets/generated artifacts before AI-agent integration. |

**설계 결정:**

- RLS Stage-2 privilege separation baked into compose: the app connects as non-superuser lemon_app (NOSUPERUSER/NOBYPASSRLS) so owner reads/writes obey RLS via per-request GUCs, while out-of-band audit and post-commit learning writes use a privileged lemon engine (AUDIT/LEARNING_DATABASE_URL). Alembic migrations are run inline as the privileged lemon role because lemon_app lacks alembic_version permission.
- Fail-fast startup guards over silent fail-open: verify_stage2_privileged_database_urls hard-errors if the lemon_app flip is set without distinct privileged audit/learning engines; build_supplement_ocr_adapter is invoked in lifespan so an inconsistent OCR config (e.g. CLOVA selected without credentials) is a startup RuntimeError, not a first-request 500.
- Heavy ML deps are build-arg gated (INSTALL_LOCAL_OCR / INSTALL_VISION / PRELOAD_PADDLEOCR) and default off in CI's docker-build job to keep the gate fast; PaddleOCR/torch/vision layers are only exercised by a local docker compose build.
- Phase-gate compliance flags (multimodal LLM/vision, YOLO section detector, food DINO/CLIP, image-learning pipeline, pgvector storage) all default false/0; the production validator in config.py blocks enabling them with unsafe/missing settings. Vision and food classifiers are off-by-default in compose.
- On-device-first LLM/OCR posture: LLM_PROVIDER=ollama with a single gemma4:e4b model for both text and vision (avoids per-request GPU model swap), ALLOW_EXTERNAL_LLM=false; current OCR phase is CLOVA-only (ENABLE_LOCAL_OCR=false) while PaddleOCR is retrained, with ALLOW_EXTERNAL_OCR=true treated as an explicit consent opt-in since CLOVA sends label images to NAVER Cloud.
- Container security: non-root lemon user, gosu drop-privileges entrypoint, TrustedHost middleware that never silently fail-opens, secure-headers + rate-limit/concurrency cap on OCR/LLM endpoints, port bound to 127.0.0.1 only, HF_TOKEN kept server-only.
- config.py code defaults intentionally stay privacy-conservative (paddleocr/local-first) and diverge from the deployed CLOVA-only phase, which lives entirely in compose/.env overrides — a deliberate but drift-prone split.
- DB pool sizing made configurable (db_pool_size=5 / db_max_overflow=10 defaults, byte-identical to prior hardcoding) and applied per-engine per-worker, with the total-connection budget documented against Postgres max_connections.


## 9. 평가 도구 · 문서 · 작업 정리

**한 줄:** The non-runtime support layer of the OCR/supplement/chatbot effort: ~200 operator/eval/training Python+PowerShell scripts, ~36 OCR baseline & handoff design docs, ~200 dated todo-list session logs, and reference datasets (KDRIS, food/meal vision, OCR eval samples) — plus untracked working-tree artifacts that must NOT be merged to develop.

**상태:** done — for the tracked deliverables: 201 scripts, ~36 OCR/handoff docs, ~205 todo logs, and reference datasets are committed and self-consistent (this is documentation/tooling/data, inert at runtime). The OCR accuracy program itself is partially-done/experimental-off-by-default by design (gates not yet met; YOLO ROI and Paddle retraining off in live, CLOVA+Gemma live subset). Untracked working-tree cruft is NOT ready and must be handled before merge.

This branch imports the entire offline tooling and research-record footprint behind the supplement-OCR pipeline. backend/scripts/ gains 201 standalone scripts: PaddleOCR fine-tune/eval/gate runners, A100 Windows training launchers (.ps1), supplement operator-review batch/triage/PII-screening builders, KDRIS 2025 digitization & validation, chatbot/wiki-RAG eval and embedding ingest, and model-registry lifecycle utilities. docs/ocr_baseline_reports/ (and docs/handoff/) accumulate ~36 dated Korean design/baseline documents tracing the OCR accuracy program from synthetic-baseline blockers through ROI/section-detector gating to the current 0.85/0.90 ingredient-recall+field-match gate redesign (which concludes the binding constraint is parser/fusion/layout extraction and measurement discipline, not the recognizer). outputs/ holds ~205 todo-list session logs and ~153 generated eval/manual artifacts; data/ adds curated reference sets (kdris_2020/2025 CSVs, food_images manifests+splits, meal_vision mock dataset, ocr_eval real/synthetic sample images). Almost all of it is documentation/data/tooling with no runtime import path into the live FastAPI/Flutter app.

**핵심 파일:**

| 파일 | 역할 |
|---|---|
| `backend/scripts/` | 201 added offline scripts: PaddleOCR finetune/eval/gate (run_paddleocr_*, gate_paddleocr_*), A100 Windows training launchers (.ps1), supplement operator-review/PII pipeline, KDRIS digitization/validation, chatbot/wiki eval+ingest, model-registry lifecycle |
| `backend/scripts/run_paddleocr_baseline_eval.py` | Representative OCR eval runner; family of run_/gate_/build_paddleocr_* drives the accuracy-gate flywheel |
| `backend/scripts/digitize_kdris_2025_summary.py` | KDRIS 2025 digitization (paired with prepare_/validate_kdris_* and validate_kdris_dataset.py) feeding data/nutrition_reference/kdris |
| `backend/scripts/eval_medical_wiki_chatbot.py` | Chatbot/wiki-RAG offline evaluation; with ingest_llm_wiki_embeddings.py / compare_wiki_embeddings.py supports the wiki-RAG redesign |
| `docs/ocr_baseline_reports/2026-06-19-paddleocr-085-090-gate-redesign-guideline.md` | Latest authoritative OCR redesign doc: concludes parser/fusion/layout + measurement discipline (Wilson lower-bound, ≥100-product holdout) gate 0.85/0.90, recognizer retrain is last resort |
| `docs/ocr_baseline_reports/README.md` | OCR accuracy-baseline program overview (CER≤5% / field-match≥95% target, measurement infra, langchain/PaddleX env conflict, iteration plan) |
| `docs/ocr_baseline_reports/2026-06-15-pipeline-and-build-implementation-audit.md` | Audit of designed vs live OCR pipeline subset (YOLO/Paddle off, CLOVA+Gemma live) and env-specific build wiring |
| `docs/handoff/` | 3 dated next-session handoff prompts (clova-gt, gemma-wiki-embedding, pipeline-gaps cpu-train) |
| `outputs/todo-list/2026-06-21/` | Latest tracked session logs (chatbot wiki-RAG redesign, supplement quality fixes, demo video, WIP-cluster housekeeping); ~200 dated logs total |
| `data/nutrition_reference/kdris/kdris_2025.csv` | Official 2025 KDRIs reference data (+kdris_2020.csv, metadata/source manifest, review/ digitization audit trail) |
| `data/food_images/manifests/` | Food classifier dataset manifests (classes.json, taxonomy.json, roboflow/aihub class maps) + splits/{train,val,test}.csv + convert_aihub_50_to_yolo.py |
| `data/meal_vision/` | Meal-vision MVP mock dataset (mock_predictions.json, classes.yaml, dataset.yaml placeholder) used by Mock detectors |
| `data/ocr_eval/real_samples/` | 86 real supplement-label images (43 categories x2) + real_manifest.json/synthetic_manifest.json for OCR benchmarking |
| `outputs/generated/supplement-learning/2026-06-18..20/` | UNTRACKED: A100 PaddleOCR run artifacts (.ps1 launchers, inference.json/yml, MODEL_MANIFEST.md); heavy .pdiparams weights are gitignored but the config/script files are NOT |
| `data/최종시연영상/` | UNTRACKED: 410MB demo recording dir (166MB .mov, GIF, mp4); not gitignored |
| `.gitignore` | Defines the privacy/artifact ignore policy for outputs/generated/supplement-learning; has a gap (ignores a100-paddleocr-best-snapshots/ but not the actual a100-paddleocr-best-models/ dir's non-weight files) |

**설계 결정:**

- Privacy-by-gitignore: extensive .gitignore rules under outputs/generated/supplement-learning/** exclude raw OCR text, provider/CLOVA/teacher payloads, private images, model weights (.pdiparams/.pdmodel/.pdparams), and operator-review materials — so PII and provider-derived data never land in git (commit 244bdbe4 explicitly untracked operator-review outputs for PII protection).
- OCR accuracy is gated, not shipped: the program is a measurement-driven flywheel (synthetic+real benchmarks, ROI/section-detector gates, Wilson-lower-bound + McNemar discipline). The current authoritative conclusion is that the 0.85/0.90 gates are bound by parser/fusion/layout extraction, not the recognizer, so A100 recognizer retraining is deliberately the last lever.
- Eval/training tooling is offline-only: backend/scripts/* are standalone CLIs/PowerShell launchers (A100 remote training on Windows) with no import path from the running FastAPI app or Flutter mobile — they are operator/research tools, safe to ship as inert code.
- Docs are Korean dated design+handoff records (append-only history), not living architecture docs; they capture decisions and gate status per session.
- Reference data is versioned in-repo: KDRIS 2025 official data carries a full review/ audit trail (candidate rows, issues, schema decisions, source manifest) for compliance traceability; food/meal datasets ship manifests+splits but real image corpora stay on external drive / gitignored.
- Task path note: the requested backend/Nutrition-backend/scripts is empty; the real script home is backend/scripts (201 files added on this branch).

---

# 통합 정리(cleanup) 목록

**1. 챗봇 & LLM-WIKI RAG**
- Untracked __pycache__ artifact under tests: backend/Nutrition-backend/tests/unit/services/__pycache__/test_chatbot_wiki_rag.cpython-313-pytest-9.0.3.pyc (and peers) should not be committed — confirm .gitignore covers them before merging to develop.
- Live activation depends on non-committed ops state: enable_wiki_vector_rag / wiki_embedding_model / loaded pgvector embeddings / the lemon_app `GRANT USAGE ON SCHEMA extensions` are env/compose/DB ops (per memory). Document these as required setup in the handoff so develop deployments don't silently fall back to lexical-only or fail-open with no citations.
- Two parallel wiki retrieval entry points coexist by design (lexical `retrieve_llm_wiki_context` vs db `retrieve_llm_wiki_context_db`); not dead code, but worth a one-line note in the handoff so the next dev doesn't mistake one for stale.
- Confirm wiki_embedding_model default (bge-m3, config.py) matches what the embeddings were actually ingested with — a mismatch silently fails open to lexical with no error surfaced to the user.
**2. 영양제 OCR & 파서 (라벨 성분 추출)**
- Config vs live drift: config.py defaults (ocr_primary_provider='paddleocr', all vision/multimodal gates False) do not match the live runtime (CLOVA primary + gemma vision/translation enabled via ops .env). Reconcile the committed defaults or document the required .env override set in the handoff so develop deployers don't get the wrong pipeline.
- Paddle vs CLOVA decision: PaddleOCR (paddle.py, secondary-merge plumbing, profile-compare tooling) is fully wired but disabled live due to the arm64 conv-kernel SIGSEGV. Decide before develop whether Paddle stays as supported-but-off (document the x86/CUDA/single-model requirement) or is trimmed to reduce surface area.
- Untracked ops/data artifacts in the worktree (data/최종시연영상/, outputs/generated/supplement-learning/*, outputs/todo-list/*) are unrelated to this subsystem but are sitting untracked in the tree — confirm they are gitignored/excluded so they don't accidentally land in the develop merge.
- The .env-driven live OCR/vision configuration (CLOVA secret, OLLAMA_TIMEOUT_SEC=120 override, gemma vision flags) is ops-only and uncommitted; ensure .env.example documents every flag this subsystem reads (ocr_primary_provider, enable_clova_ocr, allow_external_ocr, enable_multimodal_llm, multimodal_ocr_assist_policy, store_raw_ocr_text, ollama_keep_alive_sec) for the handoff.
**3. 영양제 분석 API · 비동기 파이프라인 · 학습**
- Resolve the async multi-image gap before relying on async in prod: _submit_async_multi_analysis has no fusion mode, so single_product silently falls back to the synchronous fused path even when supplement_analyze_async_enabled is on — document this clearly or implement async fusion so the two flags don't interact surprisingly.
- Two experimental dark-launch flags (supplement_analyze_async_enabled, supplement_one_shot_fusion_enabled) ship default-False; confirm the intended develop default and the env that flips them, and ensure CI exercises both branches (the sync path is what's live).
- supplements.py is very large (~155KB / 4000+ lines with ~50 helper functions); consider extracting the multi-image aggregation/merge helpers (_build_merged_multi_image_preview, _append_* , _aggregate_*) into a dedicated module to shrink the router before merge.
- Confirm env/ops are not carried in: live OCR provider selection and the vision/multimodal flags are driven by .env overrides (gitignored, per memory) — the committed config defaults (vision/Gemma off, async off) differ from the live runtime, a known drift to call out in the handoff doc.
- No TODO/FIXME debt found in the core files (only intentional DO-NOT-TOUCH learning-pipeline notes); learning side-effects are correctly best-effort/fail-open, so no dead-code or stale-test cleanup is required in this subsystem.
**4. 음식/식단 분석 & CLIP 비음식 필터**
- Untracked legacy duplicate: backend/food_image_analysis/food_classifier/ (food_classifier.py, food_filter.py, train_probe.py, probe_head.pt, probe_classes.json, nutrition/) is git-ignored and diverged from the canonical Food-backend/src/classifier copy. Project memory already flagged this dir for deletion/replacement decision — resolve before develop to avoid two diverging classifier copies.
- __pycache__ and .DS_Store litter throughout backend/vision, backend/Food-backend, and backend/food_image_analysis — ensure these are gitignored/untracked (none appear tracked, but verify).
- 0045_upsert_food_nutrition_40class_v2.py is a recreated/replacement migration (original was lost, stranding the DB); confirm the alembic head linearizes cleanly (0046 merge collapses two heads) on a fresh DB before merge, since memory notes prior multiple-heads issues.
- Confirm the food_nutrition_40class.csv is identical between Food-backend/src/classifier/nutrition (canonical, tracked) and the untracked legacy copy, and that only ONE is the source of truth; the legacy copy should be removed with its parent dir.
- docker-compose.yml food env block is committed with safe defaults (all false) — fine to merge, but the HF_TOKEN requirement for gated DINOv3 weights and the local-only best.pt/probe_head.pt provisioning should be documented in the handoff/runbook since they are not in git.
- Decide whether the legacy demo scripts (food_image_analysis/app.py, app_exp16b_40cls_demo.py, app_nutrition_demo.py) belong on develop or should move to a docs/experiments area — they are tracked but not part of the runtime path.
**5. 프라이버시 · RLS · DB · 마이그레이션**
- The entire backend/alembic migration tree (0001–0046) shows as branch-new vs origin/main; before merging to develop, confirm this is the intended canonical migration home and that there is no competing alembic tree (the task-hint path src/.../alembic does not exist; migrations live at backend/alembic, and tests reference a separate tests/unit/alembic).
- Migration head hygiene: there are duplicate-numbered revisions (two 0045_* and two 0046_*); 0046_merge_40class_dyslipidemia.py is a merge node resolving the parallel heads — verify `alembic heads` yields exactly one head on the target DB before merge, as multiple-heads has bitten this branch before (see WIP memory).
- 0023c (FORCE) is deliberately marked DO NOT APPLY until lemon_app is verified live; ensure develop's deploy/runbook documents the apply-order so it isn't auto-applied by a blanket `alembic upgrade head` before the role is in place.
- Confirm docker-compose.yml / .env flip edits (DATABASE_URL=lemon_app, AUDIT/LEARNING_DATABASE_URL, pool sizing, lemon_app password) remain ops-only and are not accidentally committed; they are intentionally untracked per repo memory.
- Stage-2 integration tests under tests/integration/db/*_stage2.py require a live lemon_app role with a password and may be skipped/fail in CI without it — verify they are properly gated (skip vs fail) so they don't block the develop pipeline.
- Stray .DS_Store files committed under src/models and src/security should be removed and gitignored.
**6. 모바일 앱 (Flutter)**
- Dead duplicate screen: mobile/lib/features/dashboard/dashboard_screen.dart (7KB, May 26, HealthHeroCard-based) is not imported anywhere — app.dart uses screens/dashboard_screen.dart (74KB) as source_dashboard. Remove the orphan or fold its widgets in.
- Dead prototype code: mobile/lib/prototypes/agent_chat_camera_entry.dart and agent_chat_camera_prototype.dart are not imported by any lib code — delete before develop.
- Stale env TODOs: app_config.dart lines 94/97 still return .invalid staging/prod placeholders; track the real URL provisioning so release builds can ship (they currently fail closed by design).
- Token-migration TODO in shared/theme/lemon_design_tokens.dart:125 ('Replace AppColor.brand usages with ...') — the legacy AppColor brand-token path coexists with lemon_design_tokens; consolidate to one token source.
- calendar_screen.dart has a TODO for an unimplemented disabled nav path (guide 02 ④(b) 10) — confirm intended-deferred vs leftover.
**7. 영양 계산 · 알고리즘 · KDRIs**
- Resolve the KDRIs duplication: nutrition/comprehensive.py uses its own MVP inline _KDRIS_TABLE static dict (adult 19-64 only, ~13 nutrients) with explicit comments ('추후 KDRIs 2020 풀 룩업으로 교체', 'MVP inline 룩업') instead of the full kdris.py module. The 5-card analyzer therefore does NOT consume the version-switched 2020/2025 KDRIs data — reconcile before relying on KDRIS_DATA_VERSION=2025 for comprehensive analysis.
- Address the TODO in nutrition/unit_converter.py:98 ('Model source-specific supplemental intake before applying magnesium ULs') — magnesium UL handling is currently simplified (note comprehensive.py sets magnesium RDA and UL both to 350).
- Confirm deploy config sets KDRIS_DATA_VERSION=2025 and ALLOW_SAMPLE_KDRIS=false for any production/develop-promotion target; the in-repo default (2020-sample, allow_sample_kdris=True) is dev-only and the official 2025 CSV otherwise sits unused.
- Handoff note (not code): the coaching Korean-localization modules (coaching.py, nutrient_names.py) and chronic-condition auto-load (_apply_stored_chronic_conditions) referenced in project memory are on a different branch; ensure the merge plan accounts for whether they should land with this subsystem.
**8. 인프라 · 배포 · 설정**
- DEPLOYMENT_EXPOSURE is documented in backend/.env.example (local/private/public, 'public staging validated like a release gate') but is never read anywhere in backend/Nutrition-backend/src/ — the validators key off ENVIRONMENT instead. Either wire it or drop the doc to avoid implying a gate that does not exist.
- KDRIs comment drift in backend/.env.example: the block says 'Development keeps the non-production 2020 sample fixture' but the same template sets KDRIS_DATA_VERSION=2025 / ALLOW_SAMPLE_KDRIS=false. Reconcile the comment with the values.
- OCR provider default divergence between docker-compose.yml/.env.example (clova, local OCR off) and config.py code defaults (paddleocr/local-first). Intentional per the phase note, but it is a documented drift risk — confirm develop should ship the CLOVA-only compose defaults and that the code-default split is still desired.
- VISION_CLASSIFIER_MODEL default differs between files (compose: yolov8n.pt; .env.example: yolo26n.pt). Both are stock COCO models that get rejected by the class-contract validator, but the inconsistent placeholder is confusing — pick one.
- agent-backend-ci.yml references sibling-repo manifests (../MEDICAL-WIKI/manifest/*.jsonl) that are absent on standard runners, so those eval steps always log 'Skipping'. Fine as a no-op, but note it so it is not mistaken for active coverage.
- Operator/ops state lives outside the repo by design (.env with CLOVA/HF secrets and the lemon_app flip, lemon_app role password). Confirm a deploy runbook documents these before merging to develop, since docker-compose.yml alone will fail-fast at startup without them.
**9. 평가 도구 · 문서 · 작업 정리**
- Do NOT merge untracked data/최종시연영상/ (410MB: 166MB Simulator .mov + GIF + mp4 demo) — add it to .gitignore (or move out of repo). It is not currently ignored.
- Do NOT commit outputs/generated/supplement-learning/2026-06-{18,19,20}/ — fix the .gitignore gap: it ignores a100-paddleocr-best-snapshots/ but the live dirs are named a100-paddleocr-best-models/, so ~25 non-weight files (A100 .ps1/.sh launchers, inference.json/inference.yml, MODEL_MANIFEST.md, adaptive-structured-summary.json) would slip into develop. The heavy .pdiparams weights are correctly ignored.
- Decide on the 3 untracked branch-commit-push summary logs (outputs/todo-list/2026-06-14|15|16/*-branch-commit-push-summary.md) and untracked outputs/todo-list/2026-06-17..20/ session logs — either commit alongside the tracked todo-list convention or gitignore; currently they are loose untracked files.
- Stray .DS_Store files exist on disk under docs/, outputs/, data/ (and data/최종시연영상/). None are tracked in git, but ensure they are not staged by a blanket git add (global *.DS_Store ignore is recommended).
- Audit scope: ~205 todo-list logs and ~36 dated baseline docs are append-only session history; consider whether develop needs the full set or a curated subset (no correctness impact, but it is a large, mostly-Korean historical footprint).

## 작업트리 미추적 항목 (develop엔 미반영, 별도 결정)

- `outputs/generated/supplement-learning/2026-06-{18,19,20}/` (~39MB ML 학습 아티팩트) — 동종 100파일은 이미 추적됨. 용량 커서 develop 반영 여부는 결정 필요.
- `outputs/todo-list/2026-06-{14..20}/` — 세션 작업로그(동종 205파일 추적 중). docs(todo) 관례라 커밋 가능.
- `data/최종시연영상/` — 데모 영상(대용량 바이너리). gitignore 권장.

---

# develop 반영 옵션 (무관 이력)

1. **PR + unrelated 머지** — 이 브랜치 → develop PR 생성 후 `merge --allow-unrelated-histories`. 47-파일 스캐폴드와 겹치는 경로는 우리 버전 우선으로 충돌 해소. develop 이력 보존.
2. **develop 강제 갱신** — develop을 이 브랜치로 맞춤(force-push). develop이 우리 브랜치와 정확히 동일해짐. 47-파일 스캐폴드 이력은 대체됨(되돌리기 어려움 → 사용자 승인 필요).
3. **정리만, 업로드는 후속** — 이 문서로 정리만 확정하고 업로드 방식은 추후 결정.

> 권장: **옵션 1(PR+allow-unrelated)** — 안전하고 리뷰 가능. 강제 갱신은 명시 승인 시에만.

