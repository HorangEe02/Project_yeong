# Step 8 RLS 정책-0 테이블 read 감사 (2026-06-15)

> 권위: `2026-06-14-step7-8-design.md` §7. 본 문서는 flip 전 사전 점검 결과.
> 방법: 라이브 DB(`lemon-aid-db-1`, alembic head `0045`) pg_policies 질의 + 코드 직접 추적 + 3-모달리티 적대 sweep 워크플로(by-model-class / by-table+rawsql / by-route-chain).

## 0. 결론 (TL;DR)
- **READ 측: 안전 (마이그레이션 불필요).** 5개 정책-0 테이블 중 **요청 세션으로 읽히는 것은 없음.** flip해도 read 0행 회귀 없음.
- **🔴 WRITE 측: flip-blocker 발견 (read 범위 밖이지만 직접 인접).** 레거시(`get_async_session`) 라우트의 감사 기록이 flip 후 `audit_logs` INSERT를 **요청 세션(lemon_app)** 으로 시도 → fail-closed. flip 전 해소 필요.

## 1. 정책-0 테이블 집합 (라이브 DB 검증)
`pg_class.relrowsecurity=true` 이고 lemon_app/public 적용 정책이 **0개**인 테이블 (pg_policies 질의로 확정):
| 테이블 | RLS | forced | 정책 | 모델 |
|---|---|---|---|---|
| `users` | ✓ | f | 0 | `User`(models/db/user.py) |
| `audit_logs` | ✓ | f | 0 | `AuditLog`(models/db/privacy.py) |
| `model_registry` | ✓ | f | 0 | `ModelRegistryEntry`(models/db/retraining.py) |
| `model_training_runs` | ✓ | f | 0 | `ModelTrainingRun`(retraining.py) |
| `model_eval_results` | ✓ | f | 0 | `ModelEvalResult`(retraining.py) |

`forced=f`라도 **lemon_app은 소유자가 아니므로(소유자=lemon) RLS 적용 대상** → 정책 0개 = deny-all(read 0행, write fail-closed). (FORCE는 소유자에게만 영향.)

## 2. READ 안전 근거 (정책-0 테이블별)
- **`users`**: DB `User` ORM 모델이 앱 요청 코드에서 **import·쿼리되는 곳이 전무**(models/db 밖 사용 0; 패키지 re-export(`models/db/__init__.py:57`)는 어디서도 select 안 함). 인증 `require_current_user`(auth.py:371)는 **JWT 전용**(DB 세션 없음) — 요청 사용자는 users read가 아님. `build_owner_subject`/`hash_actor_subject`도 토큰 principal 기반.
- **`audit_logs`**: **write-only**. `select/scalar/get(AuditLog)` 전무. 쓰기는 §3 참고.
- **`model_*`**: `ModelRegistryEntry/ModelTrainingRun/ModelEvalResult`는 오프라인 `src/learning/retraining.py`에서 **함수 파라미터 타입힌트로만** 등장(쿼리 없음). 그 모듈은 앱 코드에서 무관 심볼(`validate_sanitized_label_snapshot`) 하나만 import → 라우트 서비스체인에 없음. `revoke_retraining_records_for_owner`(privacy.py:752)는 owner 테이블(LearningDatasetItem/AnnotationTask/MedicalRecordCollection)만 건드림.
- **음성 대조군(모두 clean)**: ORM `relationship()` 정의 **0개**(→ lazy/eager/joined/selectin 암묵 SELECT 불가), automap/reflection 없음, 문자열 동적 모델 해석 없음, 5개 테이블명 raw `text()` SQL 없음(요청경로 text()는 image_embedding_records/wiki_* 대상).

3-모달리티 적대 sweep: `confirmedRequestPathReads = []` (refute 실패 = 결론 견고).

## 3. 🔴 WRITE-측 flip-blocker (감사 INSERT)
`record_audit_event`(privacy.py:608-611):
```
if request_manages_transaction(session):       # RLS 라우트 → out-of-band(privileged audit 엔진)
    return await _write_audit_out_of_band(audit_log)
session.add(audit_log); await session.commit() # 레거시 → 요청 세션에 직접 commit
```
docstring이 명시: "Legacy sessions(get_async_session): the request session is privileged(DATABASE_URL)". **이 가정이 flip 후 깨짐** — DATABASE_URL=lemon_app(SELECT만, 정책0) → 레거시 라우트 감사 INSERT fail-closed.

### 영향 라우터 (get_async_session + 감사 기록)
- **완전 레거시(async>0, rls=0, audits>0)**: `activity.py`, `ai_agent.py`, `dashboard.py`, `nutrition.py`, `predictions.py`
- **혼합(레거시 라우트 일부가 감사)**: `privacy.py`(bulk-delete/reads=Step8 유지분), `meals.py`(list/explain), `supplements.py`(intake/카탈로그 등 미마이그레이션 라우트) — 라우트별 확인 필요
- **안전(완전 마이그레이션, audits out-of-band)**: analysis_results, food_records, health, medical_records, notifications, regulated_inputs, user_medications

### 권장 해소책 (flip 전, 택1 또는 혼합)
1. 남은 감사 기록 라우트를 RLS 시밍(`get_rls_context_session` 또는 `rls_request_transaction`)으로 마이그레이션 → 감사가 자동 out-of-band(가장 일관, 기존 패턴). = 설계 §7의 "전 쓰기 라우트 마이그레이션" 완료.
2. 또는 `record_audit_event`를 **무조건 out-of-band**로 변경(레거시 분기 제거). 단 ordering/atomicity 변화(Option A 트레이드오프)가 레거시 라우트에 확산 → 테스트 파급 큼. 신중.

## 4. flip 게이트 갱신 (design §7 대비)
- ✅ audit_database_url 강제 = startup 가드(`33db1281`) 완료.
- ✅ learning post-commit privileged 엔진(`33db1281`) 완료.
- ✅ 풀 사이징(`fa00f0eb`) 완료.
- ✅ **정책-0 read 점검 = 본 감사: read 안전, 마이그레이션 불필요.**
- 🔴 **남음(write)**: 레거시 감사 기록 라우트 마이그레이션(§3) — flip 직접 선행조건.
- ⬜ 실제 DATABASE_URL flip = ops 액션(config/.env=WIP).
