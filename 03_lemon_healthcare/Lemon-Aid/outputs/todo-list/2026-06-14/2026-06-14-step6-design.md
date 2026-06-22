# Ambient-tx Step 6 — 구현 설계 (2026-06-14)

> 권위 계획: `2026-06-14-ambient-transaction-refactor-plan.md`. 이 문서는 Step 6 구현 분할 + privacy(6b) 아키텍트 설계(검증됨)를 담는다. Step 5까지 완료(커밋 aa0619a6).

## Step 6 `session.begin()` 인벤토리 (직접 grep 검증)
- analysis_results.py:131 `_persist_result` (DO-NOT-TOUCH: store_daily_health_score_result:192-193는 별개 add+commit)
- meal_image_analysis.py:319 create_preview, :505 confirm
- supplement_intake.py:364
- regulated/ocr_intake.py:303 confirm, :482 preview
- privacy.py:449 grant_consent, :492 revoke_consent(EXT store), :683 delete_analysis_result, :897 bulk-delete(EXT store ×2)
- privacy.py:549 = `_write_audit_out_of_band`(별도 audit_sessionmaker) **DO-NOT-TOUCH**; app_health_analysis.py:266 = 주석 PR#4 DO-NOT-TOUCH

## 난이도 분할
- **6a 기계적** (감사는 라우트 레벨 record_sensitive_audit_event=ambient-aware, 서비스는 owner 데이터만): regulated · meal_image_analysis · supplement_intake · analysis_results._persist_result. begin→persist_scope + post-block refresh를 scope 안으로 + 라우트 스왑(+meals consent-read closer 제거).
- **6b privacy** (서비스가 audit을 **인라인** `_build_audit_log`+session.add): 아래 설계.

## 6b privacy 설계 (아키텍트 + 직접 재검증)
**문제**: lemon_app은 audit_logs SELECT만(0023a) → 인라인 audit add가 Stage-2(lemon_app)서 permission denied. record_audit_event(privacy.py:554, 분기 609-613)는 이미 ambient-aware(request-managed면 out-of-band).

**패턴(함수별)**: 인라인 `async with session.begin(): … session.add(audit_log)` →
```
# outcome/metadata는 scope 안 지역변수로 캡처
async with persist_scope(session):
    … 데이터 행 write(+외부스토어 삭제는 인라인 유지) …
await record_sensitive_audit_event(session, …, outcome=captured, event_metadata=captured)
```
- OWN 모드: persist_scope가 scope-exit commit → 이후 record_audit_event add+commit(라우트 레벨 패턴과 동일, mid-scope commit 회피).
- participate: persist_scope flush-only → record_audit_event out-of-band(audit_logs 회피) → owner write는 의존성-exit commit.

**2-tier 라우트 채택**:
- **6b 스왑**: grant_consent(POST /me/privacy/consents/{type}) · revoke_consent(DELETE …) · delete_analysis_result_for_user(api/v1/analysis_results.py:354-389 DELETE). 데이터 테이블 0023b 정책 완비.
- **Step 8까지 레거시 유지(라우트만)**: create_delete_all_user_data_request(POST /data-deletion-requests). 서비스 본문은 persist_scope 전환(OWN=byte-identical)하되 라우트 dep는 get_async_session 유지 — bulk cross-table delete + 외부스토어 2개 비가역 + 전용 격리 sim 필요 → 보수적 최종 flip. (bulk delete 대상 owner 테이블은 0023b 정책 커버 확인; audit_logs만 갭=out-of-band 처리.)
- 순수 read 라우트(GET consents, GET data-deletion-requests/{id})는 read-batch로 별도 스왑 가능.

**외부 스토어**(revoke learning / bulk learning+media): 인라인 유지, 기존 per-item `status="failed"` 재시도 마커 의존, SAVEPOINT 무의미(blob un-delete 불가), 백그라운드 이전은 Step 7(pipeline.py DO-NOT-TOUCH).

**불가침**: record_audit_event · _write_audit_out_of_band · _build_audit_log · learning/pipeline.py · alembic · session.py 엔진. **0045 불필요**.

**트레이드오프(PR 명시)**: Option-A 감사 순서 역전 — participate에서 success audit이 owner 행 영속을 보장 안 함(privacy.py:573-578). Stage-2 sim이 "강제 main-tx 롤백서 audit out-of-band 생존"을 증명해야.

## 커밋 분할(권장, 각 TDD+별도리뷰+Stage-2+요청 시 push)
1. regulated (2블록+3라우트) — 자기완결, 진행 중(서비스·라우트·fake 완료, 계약/통합/Stage-2 잔여)
2. meal_image_analysis (2블록+meals 쓰기라우트+closer 제거)
3. supplement_intake (1블록+라우트; supplements.py Step7 오케스트레이터 동거 주의)
4. 6b privacy + analysis_results (서비스 _persist_result + 3 privacy 라우트 스왑 + bulk는 서비스만 + analysis_results 라우트) — 아키텍트 설계대로

## 진행 상태(작업트리 미커밋, 안전)
analysis_results._persist_result + regulated 2블록 persist_scope 전환 완료, regulated 3라우트 스왑, 테스트 fake(.info+commit 카운터) regulated·analysis_results 수정 — 단위 11 그린(OWN 보존).
