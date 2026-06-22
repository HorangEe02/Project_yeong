# Lemon-Aid 작업 핸드오프 — RLS Step 8(FORCE RLS Stage-2) 완결 + 영양제 다중이미지 one-shot OCR 융합

## 현재 상태 (2026-06-15)
- 브랜치 `feat/ai-agent-chat-import`, **HEAD=`c5c94298`**, `origin/feat/ai-agent-chat-import`와 동기화됨(ahead/behind 0). **작업 폴더 완전 청결**(`git status --porcelain` 빈 출력 — 미커밋 .py/.dart/.md 없음).
- 양 리모트: `origin`(Lemon-Aid-KDT/Lemon-sin) + `personal`(HorangEe02/Project_yeong). 커밋 트레일러 혼재: RLS/인프라 계열은 `Co-Authored-By: Claude Fable 5`, 이번 세션 OCR 융합/정리 계열은 `Co-Authored-By: Claude Opus 4.8 (1M context)`.
- 작업 디렉터리: `/Volumes/Corsair EX400U Media/yeong_offload/99_me/00_github/03_lemon_healthcare/Lemon-Aid` (외장 SSD).
- 이번 세션 핵심 커밋(최신→과거, 모두 푸시됨):
  - `c5c94298` test(rls): supplement RLS 시밍 보완 — 4 라우트 get_rls dep 단언 + Stage-2 owner-isolation 게이트 (← 사용자가 병렬 커밋한 최신 HEAD)
  - `02d3edb1` test(rls): get_async_session 라우트 RLS 시밍 회귀 가드 추가
  - `31220241` docs(mobile): dart format 명령에서 잘못된 `--line-length=100` 제거
  - `faeaabb3` docs(readme): RLS Stage-2 flip(lemon_app) 브랜치 주의사항 추가 (README.md +56줄)
  - `84c8a429` refactor(api): RLS Step 8 후속 — 누락된 supplement owner CRUD 라우트 4개 RLS 시밍 전환
  - `2f091477` docs(rls): RLS Step 8 설계·핸드오프·read-audit 문서
  - `a957d1a4` feat(infra): RLS Stage-2 flip — 앱을 lemon_app(FORCE RLS)로, audit/learning은 privileged 엔진
  - `f79212af` feat(mobile): 단일제품 다중이미지를 one-shot 융합 라우트로 전송
  - `0bd33005` feat(api): merge_strategy=single_product one-shot fusion branch in /analyze-multi
  - `733828fa` feat(supplement): one-shot OCR fusion service for single-product multi-image batches
  - `244bdbe4` chore(outputs): operator-review 산출물 추적 해제(.gitignore 정합·PII 보호)
  - `9bde8785` docs(supplement): 다중 이미지 병합 설계 가이드 + 워크트리 정리 인벤토리
  - `181de294` chore(gitignore): 대용량 모델 zip + figma export 무시
- 세션시작 `git status` 스냅샷엔 `.mcp.json`·food 파일(meal_image_analysis/food_yolo/ollama/supplement_parser)·operator-review jsonl 다수가 `M`으로 보였으나, **지금은 모두 정리됨**: food WIP는 `feat/food-yolo-ocr`로 분리 커밋, operator-review는 추적해제, `.mcp.json`은 커밋 상태(`79f80a61`)로 복귀(=HEAD와 무차이). → 옛 "food/one-shot 동거 헝크격리" 가이드는 이 브랜치에선 **무효**(아래 워크트리 토폴로지 섹션 참조).

## ✅ 완료(이번 세션 추가): 영양제 다중이미지 one-shot OCR 융합 (end-to-end)
**설계 결정**: "한 묶음(single_product)" 여러 장을 LLM 파서 1회로 합쳐 영양제 **1개 결과**를 내기 위해, LLM 파싱 **이전** 단계에서 OCR 텍스트를 **조기 융합(early fusion)**한다. 기존 distinct_products 경로(이미지별 분석)는 하위호환으로 그대로 둔다. 원문 OCR은 비저장(`raw_ocr_text_stored=False`) 정책 유지. 권위 문서: `docs/ocr_baseline_reports/2026-06-15-multi-image-single-supplement-merge-design-and-guideline.md`.

3계층 구현:
- **서비스** (`733828fa`, `backend/Nutrition-backend/src/services/supplement_image_analysis.py`):
  - `extract_supplement_ocr_only`(:521) — 이미지 1장의 OCR 텍스트만(intake/parse/DB write 없음), 기존 OCR 헬퍼 재사용. `analyze_supplement_image`는 미변경.
  - `_fuse_supplement_ocr_texts`(:620) — 이미지별 역할 마커 + 라인 근접중복 제거 융합, 복합 provider·첫 non-null confidence.
  - `_build_fused_image_metadata` — 정렬된 per-image sha256 해시로 순서 독립 멱등 앵커.
  - `analyze_fused_supplement_images`(:703) — N장 OCR→융합→intake 1건→단일 파싱→파이프라인 메타/학습 아티팩트(융합 1건). `raw_ocr_text_stored=False`(:912).
  - 단위 3 신규 + `test_supplement_image_analysis` 38 passed, ruff 클린.
- **라우트** (`0bd33005`, `backend/Nutrition-backend/src/api/v1/supplements.py` `/supplements/analyze-multi`):
  - `merge_strategy: Literal["single_product","distinct_products"]` Form 파라미터(:1714, 기본 `distinct_products`).
  - `single_product` & `settings.supplement_one_shot_fusion_enabled`면(:1793) `analyze_fused_supplement_images`로 1 run/preview 생성(`merged_preview` 채움)·학습 아티팩트 add_task·`_annotate image_role="mixed"`·provider/success 감사(merge_strategy 기록)·early return. `distinct_products`는 기존 이미지별 경로.
  - 통합 16 passed(기존 14+신규 2), supplement 광역 86 passed, ruff/black 클린.
- **모바일** (`f79212af`):
  - `mobile/lib/features/supplements/supplement_repository.dart` `analyzeSupplementImagesOneShot` — 전 이미지 한 multipart 요청(`image_roles_json`+`merge_strategy`), `postMultipartFiles` 재사용. 인터페이스 기본은 세션 flow 위임이라 비백엔드 impl 무영향.
  - `mobile/lib/app_controller.dart` `_analyzeSupplementImagesAutomatically`에 `singleProduct` 스레딩 → single이면 one-shot 호출, distinct는 기존 세션 flow(create→upload→finalize) 유지.
  - flutter analyze 클린, 영향 테스트 111 passed.

**Config 플래그**: `supplement_one_shot_fusion_enabled: bool = Field(default=True)` (`backend/Nutrition-backend/src/config.py:565`). **현재 default-on**.

**남은 후속(다음 세션 결정 필요)**:
- 학습 아티팩트를 **융합 1건**으로 적재 중 — per-image 학습 신호가 필요한지(one-vs-per-image) 결정. 현재 설계는 의도적으로 1건.
- one-shot 결과의 **실 라벨 필드 검증**(성분/함량/한글병기 정확도) — 실제 다장 라벨 묶음으로 end-to-end 검증 미수행.
- **default-on 유지 vs dark-launch**: 현재 `default=True`. 프로덕션 노출 전 플래그를 dark-launch(기본 False)로 돌릴지 결정.

## 🌿 워크트리/브랜치 토폴로지 변경
- **food WIP는 `feat/food-yolo-ocr` 브랜치로 분리됨**(HEAD `d6339b6b` "wip(food-yolo-ocr): 음식 YOLO 분류기·CLIP 필터·PaddleOCR 파인튜닝·섹션검출기 작업 스냅샷", 74 files, +11522). 여기엔 `meal_image_analysis.py`·`vision/food_yolo.py`·`llm/ollama.py`·`services/supplement_parser.py`·관련 테스트가 들어감. → **현재 `feat/ai-agent-chat-import` 워킹트리는 food-0(food 동거 없음)**. 옛 메모의 "food 동거 헝크격리 레시피"는 **이 브랜치에서 무효**(food 변경이 더는 working tree에 없음). food 작업은 해당 브랜치에서 이어가야 함.
- **operator-review 산출물 126파일 추적해제**(`244bdbe4`, ~28809줄 삭제) — `.gitignore` 정합 + PII 보호. `outputs/generated/supplement-learning/2026-06-05/operator-review/**`(review_pii_screening jsonl 등)이 더는 추적되지 않음. 세션시작 스냅샷의 그 M 표시들은 이 untrack으로 해소.
- **gitignore 노이즈 차단**(`181de294`): `outputs/generated/supplement-learning/**/a100-paddleocr-best-snapshots/` + `**/*.zip`(184MB PaddleOCR 체크포인트), `mobile/uiux/figma/`(~35MB figma export).
- **`.mcp.json` 되돌림**: 세션시작 M이었으나 커밋 상태(`79f80a61` "chore(infra): Supabase MCP 로컬 설정 추가")로 복귀 — `git diff HEAD -- .mcp.json` 무차이. (이번 세션 커밋에 미혼입.)
- 추가 워크트리 존재: `external/Lemon-sin-ai-agent-branch`(detached `d949368f`) — 이번 작업과 무관.

## ✅ 완료: RLS Step 8 (FORCE RLS Stage-2)
앱이 비-superuser lemon_app(NOSUPERUSER/NOBYPASSRLS) 역할로 FORCE RLS 하에 동작하도록 전환 완료.
- 코드: Phase A(read)/B(write)/C(복잡 write) 전 owner 라우트 RLS 시밍 채택.
  - 시밍 3종: `get_rls_context_session`(dep, teardown commit) / `rls_request_transaction`(in-body CM, post-commit BackgroundTask용) / `rls_request_transaction_allow_inner_commit`(C2 신규, after_begin 리스너로 매 begin GUC 재적용 — store commit+refresh 대응). seam 파일=`src/db/dependencies.py`, `src/db/tx.py`(persist_scope), `src/db/rls_context.py`(set_request_rls_context, is_local GUC).
  - 이번 세션 보완: `84c8a429`(누락 supplement owner CRUD 4 라우트 시밍 전환) + `c5c94298`(4 라우트 get_rls dep 단언 + Stage-2 owner-isolation 게이트).
- 라이브 flip(로컬 docker 스택, lemon-aid-db-1): `docker-compose.yml` DATABASE_URL=lemon_app + AUDIT/LEARNING=lemon(privileged) + alembic 단계 인라인 override. lemon_app 비번='lemon_app'. 라이브 검증 통과(lemon_app=요청·lemon=privileged 분리, owner read/감사 out-of-band 정상). flip 커밋=`a957d1a4`.
- 회귀 가드: `tests/unit/db/test_rls_route_seam_guard.py`(`02d3edb1`) — get_async_session 라우트가 CM-allowlist(run_chatbot+analyze_supplement_label+upload_supplement_analysis_session_image+analyze_supplement_label_multi+create_user_supplement) 밖이면 CI FAIL.
- README 안내: `faeaabb3` — 이 브랜치를 받는 사람이 README 상단에서 flip(lemon_app·privileged 분리·기동 가드·`ALTER ROLE lemon_app PASSWORD 'lemon_app'` 1회 설정·롤백 절차) 확인 가능.

## ⚠️ 환경 주의사항 (필수 숙지)
1. 소스가 도커 이미지에 baked(바인드마운트 X) → 코드 변경 라이브 반영하려면 `docker compose build backend` 재빌드 필수(recreate만으론 stale). 컨테이너 코드 경로=`/app/Nutrition-backend/src/...`.
2. 디스크 사고 주의: `docker compose build`가 macOS 시스템 디스크를 채우면 Docker 데몬 hung. 빌드 전 항상 `docker system df` + `df -h /System/Volumes/Data`로 여유 확인. hung 시 Docker Desktop 재시작(외장 VirtioFS 마운트 버그도 동시 해결). 백엔드는 외장드라이브 bind-mount(data/nutrition_reference, runs/food_yolo) → recreate 시 마운트 스턱 가능.
3. 사용자가 작업을 병렬로 커밋함 → 커밋 전 항상 `git log --oneline`·`git ls-files`로 HEAD 재확인(신규 생성 파일이 git status서 M이면 이미 병렬 커밋된 것). 이번 세션도 `c5c94298`가 그렇게 들어옴.
4. DB 토폴로지 이원화: 컨테이너 백엔드=lemon-aid-db-1(docker net db:5432/lemon, 호스트 미공개, docker exec만). 호스트 pytest/alembic=supabase_db(127.0.0.1:56322/postgres). 둘 다 lemon_app 역할 보유.
5. 테스트: `cd backend && .venv/bin/python -m pytest Nutrition-backend/tests/unit Nutrition-backend/tests/integration/api -o addopts="" -q`. (전체 2335 passed.)
6. Stage-2 gated 테스트(실 lemon_app): `TEST_DATABASE_URL`=supabase_db admin + `TEST_RLS_APP_DATABASE_URL`=lemon_app. throwaway 비번 절차: `ALTER ROLE lemon_app LOGIN PASSWORD 'lemon_app_local_rls_verify'` → 실행 → `ALTER ROLE lemon_app PASSWORD NULL` 정리.
7. **모바일 dart format은 기본(80)** — `mobile/CLAUDE.md`의 `--line-length=100`은 정정됨(`31220241`). 실제 리포는 `dart format lib test`(기본 80)로 포맷됨. **절대 `--line-length=100`으로 돌리지 말 것**(전 파일 reflow → 거대한 collateral diff).

## 🔴 알려진 이슈 / 후속 (flip 무관, 사용자 확인 필요)
- 새 백엔드 이미지의 alembic이 DB head `0045_upsert_food_nutrition_40class_v2`(사용자 food WIP 마이그레이션) 스크립트를 못 찾아 startup의 `alembic upgrade head`가 FAILED 로그를 남김. 비치명적(command에 &&/set -e 없어 uvicorn은 정상 exec, DB는 이미 head라 스키마 정상)이나, 이미지의 마이그레이션 스크립트 vs DB head 불일치 → food 작업(이제 `feat/food-yolo-ocr` 브랜치) 쪽에서 0045 파일이 커밋/이미지에 포함됐는지 확인 필요.

## 불가침 (DO-NOT-TOUCH)
`learning/pipeline.py`(enqueue 포함)·`app_health_analysis.py:269-271`(store commit+refresh)·`record_audit_event`/`_write_audit_out_of_band`/`_build_audit_log`·`session.py` 엔진 코어·alembic 마이그레이션. config/.env=사용자 WIP(단 flip용 docker-compose는 `a957d1a4`로 커밋됨). 이 브랜치 워킹트리는 현재 청결하나, 사용자가 병렬로 WIP를 다시 풀어둘 수 있으니 **커밋 전 항상 `git status`·staged diff 검토, 필요시 헝크격리**.

## 남은 큰 줄기 (사용자 우선순위 확인 필요 — 다음 세션 후보)
- **(우선 후보 1) one-shot 융합 follow-up**: 위 "✅ 완료(이번 세션 추가)" 섹션의 3개 후속(학습 아티팩트 one-vs-per-image · 실 라벨 필드 검증 · default-on vs dark-launch) 중 사용자 우선순위 확인.
- (옵션) 프로덕션 DATABASE_URL flip — 로컬과 동일 절차(lemon_app 비번·privileged URL·alembic 역할분리)를 운영 환경에 적용하는 별도 ops 작업.
- 섹션 검출기 학습(운영자 205 bbox + A100) — OCR 구조화 필드 빔의 근본책.
- 모바일 Auth 3단계(라이브 Supabase 키) · Supabase Auth 백엔드 라이브 활성화 · Health Connect/push.
- b32 recognizer staging(로컬 WIP, 미커밋) — food 계열 작업은 이제 `feat/food-yolo-ocr` 브랜치에서.
