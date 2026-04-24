# Commit 8 — RTDB Security Rules v2 (Custom Claims 기반)

> **작성일**: 2026-04-24
> **전제**: Commit 7 (Custom Claims) 머지됨. Commit 7.5 (Secret 이관) 머지됨.
> **배포 조건**: Commit 9 마이그레이션 스크립트로 **모든 활성 유저의 Custom Claims가 주입된 후**에만 deploy.

---

## 1. 변경 요약

### 1.1 핵심 전환
| 이전 (Legacy) | 이후 (v2) | 효과 |
|---|---|---|
| `root.child('users').child(auth.uid).child('role').val() === 'admin'` | `auth.token.role === 'admin'` | 요청당 RTDB 1 read 감소. 규칙 평가 속도 ↑, 비용 ↓ |
| role만 체크 | `auth.token.role` + `auth.token.hospitalId` 병행 | **tenant 격리**. 타 병원 admin이 우리 병원 데이터 접근 불가 |
| `admin`만 관리 | `admin` (병원 범위) + `platformAdmin` (전사 범위) | 플랫폼 운영자 ↔ 병원 admin 권한 분리 |

### 1.2 신규 경로
- `hospitals/$hospitalId/staff-codes` — 로그인 유저가 직접 읽어 코드 검증 가능
- `hospitals/$hospitalId/triage-map` — P3 AI triage 진료과 매핑 (로그인 유저만)
- `wait_queue/$hospitalId/...` — P3 실시간 대기 순번. 스태프(동일 병원)만 전체 읽기, 환자는 자기 entry만

### 1.3 유지 경로 (행동 변경 없음)
- `sessions/$sessionId/.write` — anonymous 허용 유지 (QR-only 환자 플로우)
- `qr_tokens/$token` — anonymous 허용 유지
- `shared_plans/$code` — anonymous 허용 유지

### 1.4 visit_plans hospitalId 관대 처리
기존 레코드에 `hospitalId` 필드가 없을 수 있으므로, 다음 로직 적용:
```
(auth.token.role === 'staff' && (!data.child('hospitalId').exists() || data.child('hospitalId').val() === auth.token.hospitalId))
```
→ `hospitalId` 없는 레거시 레코드는 **모든 staff 접근 허용** (backward compat). Commit 9에서 backfill 예정.

---

## 2. 권한 매트릭스 (신규 v2)

| 경로 | patient (본인) | staff (동일 병원) | admin (동일 병원) | platformAdmin |
|---|---|---|---|---|
| `users/$uid` | R/W 본인 | ❌ | R/W 본인 병원 | R/W 전체 |
| `users/$uid/role` 초기값 | self-set `'patient'` or `'staff'` 1회 | — | R/W 임의 | R/W 임의 |
| `users/$uid/status` 초기값 | self-set `'active'` 1회 | — | R/W 임의 | R/W 임의 |
| `staff_codes/$code` (root 경로) | R (검증용) | R | R/W | R/W |
| `hospitals/$hospitalId/staff-codes` | ❌ | R | R/W 본인 병원 | R/W 전체 |
| `sessions/$sid` | R/W 본인 | R/W 동일 병원 hospitalId 값으로 제한 | R/W 동일 병원 | R/W 전체 |
| `audit_logs` | ❌ | ❌ | ❌ (P1 범위 한정) | R |
| `visit_plans/$uid` | R/W 본인 | R/W 동일 병원 | R/W (hospitalId scope — Commit 10+에서 강화) | R/W 전체 |
| `hospitals/$hospitalId` | R | R | R/W 본인 병원 | R/W 전체 |
| `wait_queue/$hospitalId` | R 자기 queue (leaf) | R/W 동일 병원 | R/W 동일 병원 | R/W 전체 |
| `shared_plans/$code` | R/W 본인 생성 | R | R | R |
| `staff_invitations/$token` | R if email 일치 | ❌ | R/W | R/W |

### 정책 결정 (리뷰 반영)
- **audit_logs는 P1에서 platformAdmin 전용** — 병원 admin용 감사 뷰는 Commit 10+에서 `/audit_logs/$hospitalId/` 재구조 또는 scoped Cloud Function으로 추가.
- **staff-codes 이중 노출 차단** — 루트 `/staff_codes/$code`는 로그인 유저가 코드 단건 검증 가능하지만, 중첩 `/hospitals/$hid/staff-codes`는 staff 이상 전용으로 좁힘 (환자가 병원별 코드 리스트를 열람하지 못하게).
- **sessions write 무결성** — `newData.child('hospitalId').val() === auth.token.hospitalId` 강제. 익명 QR 유저가 hospitalId 없이 쓰는 레거시 경로는 임시 허용 (Commit 10+에서 QR 토큰 발급 시 server-side hospitalId 결정).
- **role self-write 화이트리스트** — 'patient' 또는 'staff' 초기값만 허용. 'admin'/'platformAdmin' 직접 승격 경로 차단.

---

## 3. 배포 절차 (Commit 8 단독으로는 배포 X)

### 사전 점검
1. Commit 7 (setClaims.ts · useRefreshToken) 이미 머지 및 **functions 배포 완료**
2. Commit 7.5 (Secrets 이관) 이미 머지 · Secret 등록 완료
3. Commit 9 (migrateAllClaims) 완료 및 실행 완료 → 모든 활성 유저 claim 주입 확인

### 배포
```bash
cd mediway

# 1. 로컬 에뮬레이터로 규칙 검증
firebase emulators:start --only database,auth
# 별도 터미널에서 public/e2e-rules-v2.html 열어 확인

# 2. staging 환경 먼저 배포
firebase deploy --only database --project mediway-staging

# 3. 24h 관측 (Sentry · Firebase console 에러 모니터링)

# 4. production 배포
firebase deploy --only database --project mediway-demo
```

### 롤백
```bash
# 즉시 복구 필요 시:
cp database.rules.legacy.json database.rules.json
firebase deploy --only database
```
복구 트리거:
- 401 에러가 평소의 2배 이상 급증 (claim 누락 유저)
- 특정 hospitalId 데이터 접근 불가 리포트 다수

---

## 4. Commit 9 — 마이그레이션 (구현 완료 · 실행 대기)

**상세 runbook**: [COMMIT_9_MIGRATION.md](./COMMIT_9_MIGRATION.md)

### 4.1 구현된 산출물
- [functions/src/migrations/migrateAllClaims.ts](../functions/src/migrations/migrateAllClaims.ts) — platformAdmin 전용 onCall. 페이지네이션 500, resume 지원, dry-run 옵션
- [functions/src/migrations/verifyMigration.ts](../functions/src/migrations/verifyMigration.ts) — claim 누락·불일치 리포트
- [functions/scripts/bootstrap-platform-admin.ts](../functions/scripts/bootstrap-platform-admin.ts) — 최초 platformAdmin 1명 Admin SDK 수동 주입 (chicken-and-egg 해결)
- 테스트 13건 (권한·dry-run·skip·재개·불일치 감지)

### 4.2 실행 순서 (Quick Reference)
1. `firebase deploy --only functions` — Commit 7/7.5/9 배포
2. `npx ts-node scripts/bootstrap-platform-admin.ts <uid>` — 최초 platformAdmin
3. `migrateAllClaims({ dryRun: true })` — 범위 확인
4. `migrateAllClaims({ migrationId: 'YYYY-MM-DD-prod' })` — 실제 주입
5. `verifyMigration({})` → `ready === true` 확인
6. `firebase deploy --only database` — Commit 8 rules 배포

---

## 5. 변경 파일 (Commit 8)
- [mediway/database.rules.json](../database.rules.json) — 본 규칙
- [mediway/database.rules.legacy.json](../database.rules.legacy.json) — 롤백용 백업
- [mediway/public/e2e-rules-v2.html](../public/e2e-rules-v2.html) — 브라우저 E2E 검증
- [mediway/docs/COMMIT_8_RULES.md](./COMMIT_8_RULES.md) — 본 문서

배포가 아닌 **코드만 머지** 스코프이므로 Commit 8 단독으로는 서비스 영향 0. 롤백 리스크도 0.

---

## 6. 알려진 한계·후속 과제

| 한계 | 대응 |
|---|---|
| `visit_plans`에 `hospitalId` 없음 — 임시로 모든 staff 접근 허용 | Commit 9에서 backfill + 이후 rule 강화 |
| `sessions`의 write 단계에서 hospitalId 무결성 검증 없음 | Commit 10+에서 `newData.child('hospitalId').val() === auth.token.hospitalId` 추가 |
| `wait_queue` schema leaf 규칙이 scaffold 수준 | P3 구현 시 `patientUid`, `department` validation 추가 |
| `platformAdmin` 생성 경로 아직 미정 | Commit 10+에서 별도 부트스트랩 절차 (최초 1명은 수동 Firebase Console) |
| FCM token, device 같은 private per-user 경로 아직 없음 | P4 알림 작업에서 추가 |
