# Lemon-Aid 다음 세션 핸드오프 — ambient-tx Step 5 완료 + Step 6 설계/6a WIP (2026-06-14 #4)

> 직전 핸드오프(`2026-06-14-next-session-handoff-3.md`)의 후속. 환경·규칙 전체는 거기에, ambient-tx 권위는 `2026-06-14-ambient-transaction-refactor-plan.md`, **Step 6 구체 설계는 `2026-06-14-step6-design.md`(반드시 읽고 시작)**에 있다.

## 0. 한 줄 요약
직전 이후 이번 세션 커밋(양 리모트 0/0): **Step 4a `bc85e6c3`·4b `a585bf7e`(user_medications/notifications/health) + OCR 모바일 단일호출 `f09161c3` + OCR `.env` 테스트격리 `1d4b3af8` + Step 5 `aa0619a6`(medical_records)**. **HEAD=`aa0619a6`.** 그 뒤 **Step 6 착수**: 설계 완료(step6-design.md) + **6a regulated/analysis_results 마이그레이션 WIP(미커밋, 검증됨)**. 남은 = Step 6 나머지(meal_image·supplement_intake·privacy 6b) → 7 → 8.

## 1. 환경/브랜치 (직전과 동일)
- 리포(외장SSD), 브랜치 `feat/ai-agent-chat-import`, 양 리모트 origin+personal **0/0**. HEAD `aa0619a6`.
- 백엔드 `backend/.venv/bin/python`(3.13). 테스트 `cd backend && PYTHONPATH=Nutrition-backend .venv/bin/python -m pytest Nutrition-backend/tests/unit Nutrition-backend/tests/integration -q --no-cov`. **공유 서비스/seam 변경 시 integration도 함께.**
- **컨테이너 검증 주의(메모리 정정)**: 실행 백엔드는 `/opt/venv/bin/python`. `docker exec ... sh -l`은 PATH를 `/usr/local`로 리셋(paddle 없음). heredoc 스모크는 `docker exec -i` 필수. **paddleocr는 이미 설치+동작(no-op).**
- Stage-2 gated: lemon_app throwaway 비번 `lemon_app_local_rls_verify` 설정→실행→`ALTER ROLE lemon_app PASSWORD NULL` 정리. TEST_DATABASE_URL/TEST_RLS_APP_DATABASE_URL 도출법은 handoff-3 §6.1.
- OCR 단위 2건은 로컬 `.env`(OCR_SECONDARY_MERGE_POLICY=always) 누수로 실패 가능 → 전체 스위트 시 `OCR_SECONDARY_MERGE_POLICY=disabled` prepend(또는 test_supplement_image_analysis.py의 autouse `_isolate_dotenv` 픽스처가 그 파일은 이미 격리). 무관 실패 상수: alembic 0045×2(사용자 food WIP) + .mcp.json.

## 2. 규칙 (불변, handoff-3 §2 전체 준수)
사용자 요청 시에만 커밋/푸시·양 리모트·파일/헝크 명시 스테이징(사용자 food WIP 미혼입)·TDD+별도 리뷰·persist_scope 타는 fake에 `.info`+commit 카운터·수치추정 금지·PR#4 불가침·의료 금칙어·**위임 에이전트 출력숨김/환각 → 항상 실코드/테스트 직접 검증**(이번 세션 워크플로·아키텍트·리뷰어 모두 출력 숨김 → 전사본 추출+직접 재검증으로 대응).

## 3. Step 6 상태 (권위: step6-design.md)
**설계 확정**: 6a 기계적(regulated·meal_image·supplement_intake·analysis_results._persist_result — begin→persist_scope, 감사는 라우트레벨 ambient) / 6b privacy(인라인 감사→scope 이후 record_audit_event out-of-band, 외부스토어 인라인유지, bulk-delete 서비스만·라우트는 Step8). **0045 불필요. begin() 인벤토리 9개 + DO-NOT-TOUCH(privacy:549 audit, app_health_analysis:266, analysis_results:192-195 store_daily_health_score_result) 직접 grep 검증됨.**

### 3.1 미커밋 6a WIP (검증됨, 안전 — 다음 세션이 마무리+커밋)
**내 파일(6 + 설계문서) — 사용자 WIP와 구분**:
- `src/services/analysis_results.py` — `_persist_result`(131) begin→persist_scope+refresh 안으로. ⚠️ `store_daily_health_score_result`(192-195 commit)는 **DO-NOT-TOUCH**(미접촉 확인).
- `src/regulated/ocr_intake.py` — `confirm_regulated_document`(303)·`_create_regulated_ocr_preview`(482) begin→persist_scope.
- `src/api/v1/regulated_inputs.py` — 3라우트 get_async_session→get_rls_context_session.
- `tests/unit/regulated/test_ocr_intake.py`·`tests/unit/services/test_analysis_results.py`·`tests/integration/api/test_regulated_inputs_api.py` — fake에 `.info`+flush+commit 카운터.
- **검증됨**: 단위+통합 15 그린, ruff 클린, grep 게이트 클린.
- **잔여(커밋 전)**: ① persist_scope 계약 테스트(participate=commits 0/own=1) regulated·analysis_results ② Stage-2 gated(regulated_documents/prescription_items/lab_result_items/medical child + analysis_results) ③ 별도 리뷰 ④ analysis_results 라우트 스왑은 6b로(POST 3+GET 2 가능, DELETE는 privacy:683 의존). **regulated만 자기완결 → 첫 커밋 후보.**

### 3.2 남은 구현 (단위별 TDD+Stage-2+별도리뷰)
1. **regulated 마무리** → 커밋.
2. **meal_image_analysis** (319 create_preview, 505 confirm) + meals 쓰기라우트(analyze-image/confirm) + **meals consent-read closer 제거**. ⚠️⚠️ **`src/services/meal_image_analysis.py`·`tests/unit/services/test_meal_image_analysis.py`는 사용자 food YOLO WIP로 이미 수정됨 → persist_scope 헝크만 `git apply --cached`로 격리(사용자 WIP 미혼입). meals 라우트(api/v1/meals.py)는 깨끗.**
3. **supplement_intake** (364) + 라우트. ⚠️ supplements.py는 Step7 4-commit 오케스트레이터와 동거 → intake 라우트 dep만 스왑, 다른 라우트/closer 주의.
4. **6b privacy** (step6-design.md §6b 그대로): privacy.py 4블록(449/492/683/897) begin→persist_scope + 인라인 `_build_audit_log`+session.add 제거→scope 이후 `record_audit_event(outcome=캡처)`. 라우트: grant_consent(POST consents)·revoke_consent(DELETE consents)·delete_analysis_result(analysis_results DELETE) 스왑 / **create_delete_all_user_data_request는 서비스 본문만 persist_scope, 라우트는 get_async_session 유지(Step8)**. record_audit_event/_write_audit_out_of_band/_build_audit_log 불가침. 외부스토어 인라인유지(status='failed' 재시도 마커). Stage-2 sim이 "강제 롤백서 audit out-of-band 생존" 증명.

## 4. 자동 메모리
`ai-agent-chatbot-import-state.md`에 Step 5 완료 + Step 6 design/6a WIP + paddleocr 정정 + OCR rate-limit 근본원인 기록됨. local-db-topology·ios-udid 참고.

## 다음 세션 시작 프롬프트 (복붙용)
> Lemon-Aid 이어서. 권위: `outputs/todo-list/2026-06-14/2026-06-14-next-session-handoff-4.md` + `2026-06-14-step6-design.md`(Step 6 설계) + `2026-06-14-ambient-transaction-refactor-plan.md`. 브랜치 feat/ai-agent-chat-import(HEAD aa0619a6), 양 리모트 0/0, 커밋·푸시는 요청 시·양 리모트·헝크 명시(사용자 food WIP 미혼입). 규칙(TDD+별도리뷰·persist_scope fake에 .info·PR#4 불가침·의료 금칙어·위임 출력숨김→직접 검증·컨테이너는 /opt/venv+docker exec -i) 준수. **우선순위: Step 6 — ① 미커밋 6a regulated WIP 마무리(계약 테스트+Stage-2+리뷰→커밋) → ② meal_image(사용자 WIP 헝크격리)+meals closer → ③ supplement_intake → ④ 6b privacy(설계대로 인라인감사→out-of-band, bulk-delete 라우트는 Step8 유지).** 막히면 보고.
