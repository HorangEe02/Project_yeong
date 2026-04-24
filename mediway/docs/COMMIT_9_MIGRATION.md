# Commit 9 — Custom Claims Migration Runbook

> **작성일**: 2026-04-24
> **전제**: Commit 7 (Custom Claims 인프라) + Commit 7.5 (Secret 이관) + Commit 8 (RTDB Rules v2) 모두 머지됨
> **목적**: RTDB `users` 프로필에 기반해 Firebase Auth Custom Claims를 전체 활성 유저에게 1회 주입. Commit 8 rules 배포 전 필수 선행.

---

## 1. 구현 요약

### 1.1 신규 파일
| 파일 | 역할 |
|---|---|
| [functions/src/migrations/migrateAllClaims.ts](../functions/src/migrations/migrateAllClaims.ts) | `platformAdmin` 전용 onCall. 전체 유저 페이지네이션(500) → `buildClaimsFromProfile` → `setCustomUserClaims` + audit log. 진행상황 `/migrations/v1/{id}/progress` 재개 가능 |
| [functions/src/migrations/verifyMigration.ts](../functions/src/migrations/verifyMigration.ts) | `platformAdmin` 전용 onCall. 전체 활성 유저 훑어 `customClaims.role` 보유 / 미보유 / RTDB 불일치 집계 |
| [functions/scripts/bootstrap-platform-admin.ts](../functions/scripts/bootstrap-platform-admin.ts) | chicken-and-egg 해결용 수동 스크립트. Admin SDK로 최초 platformAdmin 1명 직접 주입 |
| [functions/src/__tests__/migrations.test.ts](../functions/src/__tests__/migrations.test.ts) | migrateAllClaims + verifyMigration 권한·동작·dry-run 테스트 13건 |

### 1.2 수정 파일
| 파일 | 변경 |
|---|---|
| [functions/src/index.ts](../functions/src/index.ts) | `migrateAllClaims`, `verifyMigration` export 추가 |

### 1.3 RTDB 스키마 (Admin SDK 전용 — rules 대상 아님)
```
/migrations/v1/{migrationId}/progress   — 재개용 상태 (lastKey, processed, migrated, skipped, failed, errors, finishedAt)
/migrations/v1/{migrationId}/summary    — 완료 요약 (errors는 최대 100건 절삭)
```

---

## 2. 실행 순서 (프로덕션)

### Phase A — 선행 조건 확인
```bash
# Commit 7/7.5/8 머지 + Functions 배포 완료
firebase deploy --only functions --project mediway-demo

# Secret 등록 확인
firebase functions:secrets:access KAKAO_CLIENT_ID --project mediway-demo
firebase functions:secrets:access NAVER_CLIENT_ID --project mediway-demo
```

### Phase B — 최초 platformAdmin 1명 생성
> **chicken-and-egg**: `migrateAllClaims` / `setUserClaims` 모두 platformAdmin을 요구하지만 아직 존재하지 않음. 이 단계에서만 Admin SDK로 직접 주입한다.

```bash
# 1. 대상 유저는 반드시 사전에 로그인하여 /users/{uid} 프로필이 존재해야 함
# 2. 로컬에서 Application Default Credentials 준비 (서비스 계정 키 또는 gcloud login)
gcloud auth application-default login
gcloud config set project mediway-demo

# 3. 부트스트랩 실행
cd mediway/functions
npx ts-node scripts/bootstrap-platform-admin.ts <target-uid>
# 또는 hospitalId를 특정:
npx ts-node scripts/bootstrap-platform-admin.ts <target-uid> --hospitalId=smch
```

대상 유저는 다음 로그인 또는 `refreshMyClaims` 호출 시 `role: 'platformAdmin'` 클레임을 획득.

### Phase C — Dry run (선택, 권장)
```js
// 브라우저 콘솔 (platformAdmin 계정으로 로그인 + 토큰 갱신 후)
const fn = firebase.functions().httpsCallable('migrateAllClaims');
const res = await fn({ dryRun: true });
console.log(res.data.progress);
// processed, migrated, skipped, failed 숫자 확인
// setCustomUserClaims·audit push는 발생 안 함
```

### Phase D — 실제 마이그레이션
```js
const fn = firebase.functions().httpsCallable('migrateAllClaims');
const res = await fn({ migrationId: '2026-04-25-prod' });
console.log(res.data);
// 중단되면 동일 migrationId로 재호출 → lastKey 지점부터 재개
```

### Phase E — 검증
```js
const verify = firebase.functions().httpsCallable('verifyMigration');
const res = await verify({});
console.log(res.data);
// { totalActive, withRoleClaim, missingRoleClaim, sampleMissingUids, mismatchUids, ready }
// ready === true 인지 확인. false면 sampleMissingUids로 개별 조치 후 재실행.
```

### Phase F — Commit 8 rules 배포
```bash
# 선행: verifyMigration.ready === true
firebase deploy --only database --project mediway-staging
# 24h 관측 (Sentry · Firebase console 에러 급증 여부)
firebase deploy --only database --project mediway-demo
```

---

## 3. 롤백

### 3.1 Claims 롤백 (필요 시)
마이그레이션 자체로 인한 역회전은 드묾 (setCustomUserClaims는 덮어쓰기만, 삭제 없음). 필요 시:

```bash
# 전체 claim 제거 스크립트 (긴급용, 준비 필요)
# Firebase Admin SDK로 setCustomUserClaims(uid, {}) 를 전체 유저에게 실행
```

### 3.2 Rules 롤백 (Commit 8)
```bash
cp database.rules.legacy.json database.rules.json
firebase deploy --only database --project mediway-demo
```
복구 트리거:
- 401 에러 급증 (claim 누락 유저)
- 특정 hospitalId 접근 불가 리포트 다수
- cross-tenant 데이터 누출 의심

### 3.3 Bootstrap 되돌리기
```bash
npx ts-node scripts/bootstrap-platform-admin.ts <uid> --revert
# platformAdmin → admin 으로 되돌림
```

---

## 4. 알려진 한계 · 주의사항

| 항목 | 내용 |
|---|---|
| **활성 유저 정의** | `status === 'active'` 또는 `status` 필드 미존재. `suspended`/`deleted`는 skip |
| **마이그레이션 중 가입 유저** | 이미 `ensureUserRecord`가 `injectClaimsForUid`로 자동 주입하므로 별도 조치 불필요 |
| **Auth 계정 없는 orphan 프로필** | `getUser` 실패 → missing으로 카운트. 수동 정리 필요 |
| **claim vs RTDB.role 불일치** | `mismatchUids`로 리포트되나 자동 동기화 X. 정책적으로 RTDB 또는 claim 중 무엇이 truth인지 결정 후 개별 조치 |
| **토큰 1시간 캐시** | 마이그레이션 직후 기존 로그인 유저는 최대 1시간 구 claim 보유. 강제 재로그인 불가 — Commit 8 배포 시점에 일부 401 허용 |
| **hospitalIds 배열** | 현 스키마에 없음 — 모두 `[]`로 주입. 다중 병원 지원 시 별도 마이그레이션 |
| **visit_plans.hospitalId backfill** | 본 Commit 범위 외. 별도 follow-up (MEDIUM-3) |

---

## 5. 체크리스트

### 배포 전
- [ ] Commit 7, 7.5, 8 코드 머지 확인
- [ ] Functions 배포 (`firebase deploy --only functions`)
- [ ] Secrets 등록 (KAKAO_* × 3, NAVER_* × 2)
- [ ] 최초 platformAdmin 부트스트랩 완료
- [ ] `migrateAllClaims({dryRun: true})` 실행해 예상 범위 확인

### 마이그레이션 실행
- [ ] `migrateAllClaims({migrationId: 'YYYY-MM-DD-prod'})` 실행
- [ ] `/migrations/v1/{id}/summary`에서 failed 수 확인 (0 목표)
- [ ] `verifyMigration({})` 실행 → `ready === true` 확인

### RTDB Rules 배포
- [ ] staging 먼저 배포 (`--project mediway-staging`)
- [ ] 24h 에러율 관측
- [ ] production 배포 (`--project mediway-demo`)
- [ ] `database.rules.legacy.json` 은 보존 (롤백용)

### 사후
- [ ] `verifyMigration` 1주일 후 1회 더 실행 (신규 가입자 자동 주입 확인)
- [ ] `visit_plans.hospitalId` backfill 스프린트 기획 (Commit 10+ 후보)
- [ ] M4 (visit_plans admin hospitalId scope) 강화 스프린트 기획
- [ ] M6 (staff_codes 필드 validate) 강화 스프린트 기획

---

## 6. 배포 담당자용 Quick Reference

```bash
# 0) 준비
cd mediway
firebase deploy --only functions --project mediway-demo

# 1) Bootstrap (최초 1회)
cd functions
npx ts-node scripts/bootstrap-platform-admin.ts <ADMIN_UID> --hospitalId=smch

# 2) Dry run (권장)
# 브라우저 콘솔 (platformAdmin 로그인):
firebase.functions().httpsCallable('migrateAllClaims')({ dryRun: true }).then(r => console.log(r.data))

# 3) 실제 마이그레이션
firebase.functions().httpsCallable('migrateAllClaims')({ migrationId: '2026-04-25-prod' }).then(r => console.log(r.data))

# 4) 검증
firebase.functions().httpsCallable('verifyMigration')({}).then(r => console.log(r.data))
#   → ready: true 확인 후 다음 단계

# 5) Rules 배포
cd ..
firebase deploy --only database --project mediway-staging
# 24h 관측 후
firebase deploy --only database --project mediway-demo
```
