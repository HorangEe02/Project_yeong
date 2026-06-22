# Ambient-Transaction 리팩터 계획 — RLS Stage-2 라우트 점진 채택 (2026-06-14)

> 근거: 이해+설계 워크플로(rls-ambient-tx-plan, 27 agents). 전수 인벤토리 **237 트랜잭션 사이트 / 166개가 request-tx에서 충돌**. 이 문서가 구현 권위.

## 문제 (확정된 ground truth)
- `AsyncSession.begin()`/`async with session.begin()`는 **이미 열린 트랜잭션(autobegin 포함)이 있으면 InvalidRequestError**.
- `get_async_session`(dependencies.py:19-30)은 tx를 열지도 commit하지도 않음 → 서비스가 `session.add()+commit()`(ambient autobegin tx를 닫음) 또는 `async with session.begin()`로 영속.
- `get_rls_context_session`(66-72)은 `async with session.begin()`로 request tx를 열고 **트랜잭션-로컬 GUC**(app.current_subject*)를 set_config(is_local=true)로 설정 → GUC 수명 = 그 tx. **중간 commit이면 GUC 유실**.
- 충돌: RLS 라우트에서 서비스 commit이 request tx를 닫음(GUC 유실) / 서비스 begin()이 raise. 감사 없는 순수 read 라우트 0개(15라우터 전부 record_sensitive_audit_event 호출).
- session 설정: `autoflush=False, expire_on_commit=False`.

## 채택 설계 — Design #1: Marker 기반 ambient `persist_scope`
get_rls_context_session이 `session.info["request_managed_tx"]=True` 스탬프. 모든 마이그레이션 쓰기/감사가 단일 seam 경유:
- **marker 있음 → PARTICIPATE**: flush만, commit/begin 금지 → GUC가 의존성-exit commit까지 생존.
- **marker 없음 → OWN**: 오늘의 commit/begin 동작 그대로 재현 → 레거시 get_async_session 라우트 byte-for-byte 불변.
- 점진: 쓰기 서비스 1개 + 그 라우트 단위로.

(반려: #2 의존성-소유 통일=flag-day, PR#4 commit 패턴 강제 편집 + 실패경로 감사 회귀. #3 begin_nested=SAVEPOINT는 commit 안 함 → 레거시 쓰기 유실 + in_transaction() 비결정적.)

## Helper (src/db/tx.py)
```
MARKER: get_rls_context_session에서 set_request_rls_context 직후
  session.info["request_managed_tx"] = True

persist_scope(session):  # 모든 마이그레이션 쓰기 서비스 본문
  marker 있음: yield; await session.flush(); return   # 절대 commit/begin 안 함
  marker 없음(OWN): 최외곽 own scope만 commit, 내부는 flush만(재진입 규칙)
    # 깊이 카운터(session.info)로 "내가 연 것"이 아니라 "최외곽 own"을 판별 —
    # autobegin tx도 최외곽 own scope가 commit해야 레거시 add+commit 재현.

record_audit_event(session, ..., on_failure=False):  # 단일 출처
  marker 있음: session.add(audit); on_failure면 _commit_audit_out_of_band(별도 단기 세션), 아니면 flush
  marker 없음: add + commit (레거시 불변)

_commit_audit_out_of_band(...): 새 sessionmaker 세션 + begin으로 감사만 독립 commit
  → 실패 분기(HTTPException raise)에서 request tx 롤백돼도 감사 보존(오늘의 2-phase 동작).

TEST GUARD: 마이그레이션 라우트는 핸들러 종료까지 session.in_transaction()==True 단언.
```
refresh()는 participate-mode에서 post-commit 순간이 없으므로 **scope 안에서 flush 후** 실행(또는 expire_on_commit=False라 생략).

## 사이트 마이그레이션 규칙
- **add+commit** (food_records.create:138-139, user_medications.create:61-62, notifications.create:108-109, supplement_image_analysis 620/740/788/1543, health_sync:107, medical_records.create_patient_status_snapshot:406): 본문을 `async with persist_scope(session):`로 감싸고 commit 삭제; refresh는 flush 후 scope 안으로.
- **dirty-update+commit** (food_records.update:198-199, user_medications 105/119, notifications 145/159, medical_records.confirm:361, supplement_parser:332, supplement_barcode_lookup:355, supplements 454/475): persist_scope로 감싸고 scope-exit flush에 의존.
- **Core delete()+commit** (food_records.delete:218): persist_scope로 감싸고 commit 삭제.
- **async with session.begin() 블록** (privacy 447/490/642/856, analysis_results._persist_result:131, meal_image_analysis.create_preview:311, supplement_intake:364, regulated/ocr_intake x2): `async with persist_scope(session):`로 교체(본문 동일, consent+audit 한 scope 원자성 유지).
- **오케스트레이터 내 다중 commit** (analyze_supplement_image 620/740/788/1543): 동시 전환(첫 commit이 GUC 드롭).
- **record_audit_event 성공경로**: ambient helper로. **실패/except 분기**(consent-denied + Validation/Conflict): `on_failure=True`로 out-of-band.
- **consent-read tx closer** (_commit_consent_read_transaction supplements:1003, medical_records:110, meals:91, health:161-163): 마이그레이션 라우트에선 제거(request tx 안에서 읽으므로 닫을 것 없음, commit하면 GUC 드롭).
- **순수 read/refresh/add-staging/flush-only** (breaksUnderRequestTx:false): 변경 없음.
- **라우트 dep 스왑**: 그 라우트의 전이적 호출그래프의 모든 쓰기+감사가 persist_scope/ambient-audit 경유한 **후에만** get_async_session→get_rls_context_session.

## 마이그레이션 순서
- **Step 0**(무동작 변화): src/db/tx.py persist_scope + get_rls_context_session marker + record_audit_event ambient-aware(on_failure out-of-band). **전체 스위트 그린**(marker 부재라 동일 동작).
- Step 1: 감사 호출처 — error분기 on_failure=True, success분기 ambient flush. 라우트 스왑 없음.
- **Step 2(FIRST BATCH)**: 쓰기 없는 owner-scoped read 라우트부터 get_rls_context_session 스왑.
- Step 3: food_records 서비스 persist_scope 전환 + /food-records POST/PATCH/DELETE.
- Step 4: user_medications + notifications + health_profile.
- Step 5: medical_records (create/confirm/patient-status) + consent-read closer 제거.
- Step 6: async-with-begin 서비스(privacy, meal_image_analysis, supplement_intake, analysis_results._persist_result, regulated/ocr_intake) — 외부 오브젝트스토어 삭제 순서·배치 원자성 보존.
- Step 7(최후·게이트): supplement_image_analysis 4-commit 오케스트레이터 + analyze_supplement_label* — learning/pipeline enqueue는 request tx 밖(post-commit background).
- Step 8: 마이그레이션된 라우트에 대해 DATABASE_URL을 lemon_app로 flip + lemon_app 격리 시뮬레이션 통과 후 확장.

## FIRST BATCH (구체)
- seam: src/db/tx.py + marker + ambient audit (활성화 변경, marker 부재라 라우트 동작 변화 0).
- Route 1(쓰기·감사 0): **GET /supplements/categories**(list_supplement_category_catalog, supplements.py:2966) — 순수 read. NO 다른 편집으로 스왑. 가장 안전한 canary.
- Route 2(read, 감사 없음): GET /meals/cuisines, GET /meals/foods.
- Route 3(read+감사): GET /supplements(list_user_supplements:2915), GET /supplements/{id}(3023) — owner-scoped read, 유일 쓰기=record_sensitive_audit_event. ambient audit 후 스왑. **GUC 경로 + 감사 INSERT를 실 owner-scoped SELECT에서 검증.**
- 첫 WRITE 서비스: food_records(create:138/update:198/delete:218) + /food-records POST/PATCH/DELETE.

## DO NOT TOUCH (PR#4/범위 외)
- app_health_analysis.py:269-271 (store_app_health_analysis_result add+commit+refresh, 264-268 주석=라이브 E2E begin()-raises 케이스 기록). PR#4. 라우트(ai_agent.py:264/346)를 의도적으로 RLS화할 때만, 주석/이력 보존하며 persist_scope로.
- analysis_results.py:192-193 (store_daily_health_score_result add+commit, 위 패턴의 형제). app_health_analysis와 lockstep으로만.
- ai_agent.py LLM 가드 라우트. PR#4.
- learning/pipeline.py(commit/rollback 194/196/290/298/304/360/398/437/657/704), upsert_worker.py, pgvector_store.py, media/retention.py — PR#4 job-enqueue/워커 세션. request 범위 밖. enqueue는 post-commit background로.
- 모든 alembic(0023b 포함, 작업트리 0019/0021/0024) — 앱 계층만.
- session.py 엔진/sessionmaker 설정(autoflush=False, expire_on_commit=False) — helper가 의존.
- record_audit_event 레거시 own-mode 분기(marker 부재 add+commit) — 미마이그레이션 감사 호출처 보존.

## RISK REGISTER (요약)
- 전이 호출그래프의 숨은 commit → GUC 드롭: 라우트 스왑 전 commit/begin grep 게이트 + CI에서 라우트 종료 시 in_transaction() 단언.
- 잔존 begin() raise: persist_scope로 전 begin 교체 + repo-wide grep 체크.
- 실패경로 감사 유실: on_failure=True out-of-band.
- 반쪽 전환 시 레거시 쓰기 유실: 서비스+라우트 원자적 전환, own-branch 항상 commit, read-first-batch는 유실 쓰기 없음.
- refresh 의미 변화: participate에선 flush 후 scope 안 refresh(또는 제거).
- 재진입: 내부 own scope는 flush만, 최외곽만 commit(깊이 규칙).
- superuser 마스킹: lemon_app(또는 SET ROLE) Stage-2 시뮬 테스트로 격리+영속 검증, DATABASE_URL flip 게이트.
- owner_subject(앱) vs GUC subject 불일치 → WITH CHECK 거부: build_owner_subject == set_request_rls_context subject 단언, lemon_app 쓰기 테스트로 커버.
- 배치/루프 원자성, 외부 오브젝트스토어 삭제 비가역성: Step 6/7에서 신중(필요시 per-item begin_nested SAVEPOINT).

## VERIFICATION PLAN
- Step 0/1: 라우트 스왑 0 상태로 **전체 백엔드 스위트 100% 그린**(marker 부재 = 동일).
- 라우트별 grep 게이트: 스왑 전 전이 호출그래프에 commit/begin/_commit_consent_read_transaction 0.
- 레거시-영속 테스트: 미마이그레이션 라우트 POST/PATCH/DELETE가 새 세션 재조회로 영속+감사 확인.
- RLS 라우트 GUC-수명 테스트: 핸들러 전 구간 tx open + dependency-exit 직전 GUC 세팅 단언.
- **Stage-2 격리 시뮬(load-bearing)**: 채택 라우트를 lemon_app(또는 SET ROLE) 접속으로 end-to-end — (a) A가 B 행 못 봄/못 고침, (b) A 쓰기가 commit돼 사후 가시, (c) 감사 행 영속, (d) 강제 실패 분기에서 main 롤백돼도 on_failure 감사 out-of-band 보존.
- 감사-실패 테스트 / 재진입 테스트 / first-batch golden compare / CI in_transaction() 단언.

## ⛔ CRITICAL 발견 (Stage-2 검증, 2026-06-14) — audit_logs는 lemon_app이 못 씀
Stage-2 시뮬 준비 중 확인: **`audit_logs`는 lemon_app에 SELECT 권한만**(0023a CATALOG_TABLES에 포함). RLS enabled·정책 0개. **lemon_app 접속으로 INSERT 시도 → `permission denied for table audit_logs`(경험적 확정).** (다른 테이블은 grant 있음 — 모든 public 테이블에 lemon_app grant 존재, write-갭은 audit_logs 단독. supplement_categories=SELECT ✓.)

**영향**: Stage-2(DATABASE_URL=lemon_app)에서 **모든 감사 쓰기 실패** → ambient-audit participate-flush(Step 0)도, `_commit_audit_out_of_band`(get_sessionmaker=lemon_app)도 깨짐. **감사를 호출하는 모든 owner-scoped 라우트가 Stage-2에서 차단**. 이는 기존 RLS 설계 의도로 보임(앱 역할이 자기 감사 로그를 못 쓰게 = 변조 방지). 즉 **감사는 권한 있는(non-lemon_app) 커넥션으로 써야 함** — Step 0의 "request tx에 participate" 전제가 audit_logs엔 적용 불가.

**해결 필요(결정)**:
- **Option A(권장) — 권한 분리 audit writer**: 감사는 항상 별도 권한 커넥션(superuser `lemon`/`postgres` DSN, DATABASE_URL과 분리)으로 out-of-band 기록. 기존 설계 의도와 정합(audit_logs는 앱-쓰기 불가), grant/RLS 변경 없음, 앱 역할이 감사 변조 불가. **레거시 의미와 일치**(오늘도 record_audit_event는 add+commit으로 라우트 종료 전 즉시 커밋 = 감사는 작업과 무관하게 독립 커밋). Step 0의 participate-flush/on_failure 분기는 "항상 권한 out-of-band"로 단순화 가능. 비용: 별도 AUDIT_DATABASE_URL(권한 DSN) 설정 + 감사당 커넥션(풀 고려).
- **Option B — lemon_app에 audit_logs INSERT grant + INSERT 정책**(신규 0045+): 감사가 request tx에 탑승(성공 시 작업과 원자적). 비용: 앱 역할 권한 확대(자기 감사 쓰기) = 컴플라이언스 posture 약화, append-only/owner INSERT 정책 신중 설계 필요, 원 설계자의 SELECT-only 의도 변경.

**현재 상태**: 라우트 마이그레이션/DATABASE_URL flip 전에 발견 → 무피해. Step 0(behavior-preserving)는 커밋됨. 결정 후 감사 경로 설계 수정(Option A면 audit writer 분리) → 그 다음 Step 2 canary + Stage-2 시뮬. **비-감사 순수 read 라우트(GET /supplements/categories 등)는 감사 없으므로 이 차단과 무관하게 채택 가능**(단 대상 테이블 RLS/grant 개별 확인).

## Stage-2 flip 게이트 (DATABASE_URL→lemon_app 전 필수, Option A 리뷰 도출)
- **[MEDIUM] audit_database_url 강제**: DATABASE_URL=lemon_app로 flip할 때 `audit_database_url`(권한 DSN)을 **반드시 설정**해야 함. 미설정 시 `get_audit_sessionmaker`가 lemon_app으로 폴백 → 감사 INSERT가 **요청마다 런타임 permission denied**(조용한 시작 실패 아님, 매 감사 라우트 실패). flip 전 startup 검증(예: database_url 역할이 lemon_app이면 audit_database_url 필수+상이) 추가하거나 ops 체크리스트 게이트.
- **[LOW] 풀 더블-체크아웃**: Option A에서 request-managed 라우트는 매 감사마다 두 번째 커넥션(권한 audit 엔진)을 잡음(요청 커넥션 보유 중). flip 전 `pool_size+max_overflow`(메인 + 별도 audit 엔진 각각)가 피크 동시성 수용하는지 확인.
- **[LOW] audit 엔진 풀 사이징**: 전용 audit 엔진(`create_async_engine(audit_url, pool_pre_ping=True)`)이 기본 풀 크기. Stage-2 핫패스이므로 명시 사이징 또는 기본값 의도 문서화.
- **[테이블별 RLS/grant 확인]**: 라우트 dep 스왑 전, 그 라우트가 읽는 모든 테이블이 lemon_app으로 읽기 가능한지 확인. **RLS-enabled·정책 0개 = lemon_app 읽기 0행 테이블: `audit_logs, model_eval_results, model_registry, model_training_runs, users`**(라이브 확인). `users`를 읽는 owner 라우트가 있으면 catalog/owner read 정책 추가(신규 0045+) 필요. catalog 참조 테이블(supplement_categories/food_cuisines/food_courses/food_catalog_items은 **0025**, food_nutrition은 **0027**)은 `lemon_app_catalog_read`(USING true)+FORCE RLS 보유 — lemon_app 읽기 가능. 0023b의 CATALOG_TABLES(supplement_products/supplement_product_ingredients/consent_policies/learning_dataset_versions)와는 별도 마이그레이션이므로, 정책 집합이 라우트 read를 다 못 덮을 수 있어 라우트별 검증 필요.

## Step 0 리뷰 후속(적대적 리뷰 LOW 2건 — 활성화 단계에서 처리)
- **LOW(Step 3)**: persist_scope OWN-mode 단위 테스트는 autobegin 상태머신을 모델링하지 않음(=fake). "최외곽 own scope가 autobegun read tx를 commit" 주장은 라이브 SQLAlchemy probe로만 검증됨. 첫 실제 쓰기 서비스 마이그레이션(Step 3) 시 실엔진 통합 테스트 추가: SELECT→persist_scope(OWN)→다른 세션에서 행 가시 + in_transaction() False 단언.
- **LOW(Step 1)**: `_commit_audit_out_of_band`는 request RLS 커넥션이 체크아웃·트랜잭션 중인 상태에서 **두 번째 풀 커넥션**을 잡음 → 풀 고갈 시 데드락/타임아웃 가능. Step 0에선 dormant(on_failure 호출처 0). Step 1에서 on_failure 활성화 시 `pool_size+max_overflow`가 순간 2-커넥션 오버랩을 수용하는지 확인(또는 메인 커넥션 해제 후 감사 기록).
