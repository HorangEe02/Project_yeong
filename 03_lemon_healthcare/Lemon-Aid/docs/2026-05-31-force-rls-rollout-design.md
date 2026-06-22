# FORCE ROW LEVEL SECURITY 이행 설계 (로드맵)

> 상태: **설계 단계** — 라이브 DB 미적용. throwaway DB 프로토타입으로 증명한 뒤
> 마이그레이션/배선 파일을 작성하고, 라이브 적용은 **별도 승인** 후 단계적으로 진행한다.
>
> 배경: §13.x 보안 라운드에서 핵심 테이블에 `ENABLE ROW LEVEL SECURITY` + 클라이언트
> 역할 `REVOKE` + `ALTER DEFAULT PRIVILEGES`(fail-closed)를 적용했다. 그러나 현재는
> 정책(`POLICY`)이 없고 `FORCE`도 꺼져 있어, 보호는 "grant 회수"에만 의존한다.
> 진짜 행수준 격리(`FORCE` + per-row 정책)는 요청경로 접속 모델을 바꿔야 하는
> 대공사라 별도 로드맵으로 분리했다.

---

## 1. 현황 사실 (라이브 DB 실측, 2026-05-31)

- **접속 역할 = `lemon`, 그리고 `rolsuper = true`.** 모든 public 테이블의 owner도 `lemon`.
  - ⚠️ **superuser는 RLS도, FORCE RLS도 우회한다.** 따라서 현재 역할로는 `FORCE`를
    켜도 아무 효과가 없다(정책 평가 자체를 건너뜀). FORCE RLS가 의미를 가지려면
    **비-superuser·비-owner 요청 역할이 필수 선행조건**이다.
- 앱은 단일 엔진(`src/db/session.py`)으로 접속하며 **per-request 역할 전환·세션 GUC·
  `SET ROLE`·`SET LOCAL`이 전혀 없다**(grep 확인). 쓰기는 서비스 계층의
  `async with session.begin()` 트랜잭션으로 수행.
- 쿼리는 애플리케이션 레벨에서 `owner_subject == build_owner_subject(user)`로 직접
  필터링한다(예: `supplement_registration.py`). 즉 **현재 격리는 100% 앱 코드 의존**.
- RLS 활성 테이블 = **36개**. owner 식별 방식으로 4분류:

| 유형 | 수 | 식별 컬럼 | 대표 테이블 |
|---|---|---|---|
| A. 평문 owner | 10 | `owner_subject` (varchar) | user_supplements, supplement_analysis_runs, meal_records, health_daily_summaries, analysis_results, consent_records, body_profile_snapshots, food_image_analysis_runs, health_metric_samples, health_sync_batches |
| B. 해시 owner | 10 | `owner_subject_hash` (char64) | regulated_documents, media_objects, medical_record_collections, learning_image_objects, image_embedding_jobs/records, learning_dataset_items, annotation_tasks, deletion_requests, patient_status_snapshots |
| C. FK 자식 | 1+ | 부모 FK | user_supplement_ingredients(→user_supplements), supplement_image_evidence, meal_food_items, media_processing_runs, patient_conditions/medications, prescription_items, lab_result_items |
| D. 카탈로그/공용 | 다수 | owner 없음 | supplement_products(+ingredients), consent_policies, users, model_registry/training_runs/eval_results, learning_dataset_versions |

---

## 2. 목표 / 비목표

**목표**: superuser가 아닌 요청 역할로 접속할 때, 행수준 정책이 "본인 소유 행"만
read/write 하도록 강제(`FORCE`)한다. Supabase Data API/실수 grant/세션 탈취 시에도
DB가 최종 방어선이 된다(앱 코드 버그와 독립).

**비목표**: 카탈로그(D)의 공개 읽기를 막지 않는다. 오프라인 임포터/마이그레이션/관리
작업은 계속 owner(또는 superuser) 역할로 수행한다.

---

## 3. 설계

### 3.1 요청 전용 역할 `lemon_app` (선행 필수)
```sql
CREATE ROLE lemon_app LOGIN PASSWORD '<env>' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
GRANT USAGE ON SCHEMA public TO lemon_app;
-- 테이블별 최소 grant: 유형 A/B/C는 SELECT/INSERT/UPDATE/DELETE, 유형 D는 SELECT(일부)만.
```
- 앱(`DATABASE_URL`)은 **`lemon_app`로 접속**. 마이그레이션/임포터/백업은 계속 `lemon`.
- `NOBYPASSRLS` 명시: 이 역할은 절대 RLS를 우회하지 못한다.

### 3.2 세션 GUC로 현재 주체 주입
요청 트랜잭션 시작 시 백엔드가 주입:
```sql
SET LOCAL app.current_subject = '<issuer::subject>';       -- 유형 A
SET LOCAL app.current_subject_hash = '<hash_actor_subject>'; -- 유형 B
```
- `SET LOCAL`이라 트랜잭션 종료 시 자동 해제(커넥션 풀 누수 없음).
- 배선 위치: `src/db/session.py` 세션 팩토리 또는 `get_async_session` 의존성에서
  `AuthenticatedUser`를 받아 트랜잭션 첫 문장으로 실행. **미인증/배치 경로 호환**을 위해
  값이 없으면 빈 문자열 → 정책상 0행(fail-closed).

### 3.3 정책 (유형별)
```sql
-- 유형 A (평문 owner)
ALTER TABLE public.user_supplements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_supplements FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_rw ON public.user_supplements
  FOR ALL TO lemon_app
  USING (owner_subject = current_setting('app.current_subject', true))
  WITH CHECK (owner_subject = current_setting('app.current_subject', true));

-- 유형 B (해시 owner): owner_subject_hash = current_setting('app.current_subject_hash', true)

-- 유형 C (FK 자식): 부모 정책 위임
CREATE POLICY owner_rw ON public.user_supplement_ingredients
  FOR ALL TO lemon_app
  USING (EXISTS (SELECT 1 FROM public.user_supplements p
                 WHERE p.id = user_supplement_id
                   AND p.owner_subject = current_setting('app.current_subject', true)));

-- 유형 D (카탈로그): 읽기 공개, 쓰기는 lemon_app 비허용
CREATE POLICY catalog_read ON public.supplement_products
  FOR SELECT TO lemon_app USING (true);
```
- `current_setting(..., true)`의 2번째 인자 `true` = GUC 미설정 시 NULL 반환(에러 X).
  NULL = 어떤 owner와도 불일치 → **fail-closed로 0행**.
- `FOR ALL` USING+WITH CHECK 둘 다: 타인 행 read/insert/update/delete 전부 차단.

### 3.4 단계적 롤아웃 (각 단계 롤백 가능)
1. **0023a**: `lemon_app` 역할 + grant 생성(아직 FORCE 안 함, 앱은 여전히 lemon 접속) — 무해.
2. **세션 배선 PR**: GUC 주입 코드 추가 + 단위/통합 테스트(아직 lemon 접속이라 정책 미평가).
3. **0023b**: 유형별 정책 CREATE(아직 FORCE 안 함) — superuser라 여전히 우회, 무해.
4. **스테이징 전환**: `DATABASE_URL`을 `lemon_app`로 → 통합 테스트로 read/write 정상 확인.
5. **0023c**: `FORCE ROW LEVEL SECURITY` — 이제부터 실제 강제. 스테이징 검증 후 프로덕션.
- 각 단계는 직전으로 롤백 가능(`NO FORCE`, 정책 DROP, 역할 revoke 순).

### 3.5 위험과 완화
| 위험 | 완화 |
|---|---|
| 백엔드 자기잠금(deny-all) | 4단계에서 `lemon_app`로 먼저 통합테스트; FORCE는 마지막 단계 |
| GUC 미주입 경로(배치/크론) | 그 경로는 owner `lemon` 유지(FORCE는 비owner에만 강제); 또는 명시적 GUC |
| 커넥션 풀 GUC 누수 | `SET LOCAL`(트랜잭션 한정) 사용 |
| 카탈로그 읽기 차단 | 유형 D는 `catalog_read USING(true)` |
| 마이그레이션/임포터 깨짐 | 그들은 계속 owner `lemon`로 실행(superuser 우회) |
| 성능(서브쿼리 정책) | 유형 C 부모 FK 인덱스 확인; EXPLAIN 검증 |

---

## 4. 검증 계획
- **throwaway DB(`rls_poc`)** 에서 4유형 샘플로 증명(라이브 미접촉):
  1. GUC 설정 시 본인 행만 SELECT, 2. 타인 행 0행, 3. 카탈로그 read 허용,
  4. owner(lemon) 마이그레이션/시드 정상.
- backend 통합테스트에 `lemon_app` 접속 + GUC 경로 추가.
- 적용 후: `SET ROLE lemon_app; SET app.current_subject='other'; SELECT count(*)` = 0 확인.

## 5. 잔여 결정(승인 필요)
- `lemon_app` 비밀번호 관리(.env/secret) 및 compose/배포 반영.
- 배치/크론 경로의 접속 역할(owner 유지 vs 전용 GUC).
- 프로덕션 적용 윈도우(롤백 리허설 포함).
