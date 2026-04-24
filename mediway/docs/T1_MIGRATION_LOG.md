# T1-1 audit_logs Migration Log

> RTDB `audit_logs` flat → `audit_logs_v2/{hospitalId}/{pushId}` nested 이관 기록.
>
> 관련 스크립트: `mediway/scripts/migrate-audit-logs-to-v2.py`
> 관련 기획: `mediway/docs/LOCAL_SYNC_GAPS.md` § 1.3 — cross-tenant read leakage 해소.

---

## 2026-04-24 — T1-1a: 초기 마이그레이션 (legacy 병행 보존)

### 실행 결과
| 항목 | 값 |
|------|-----|
| 백업 경로 | `/audit_logs_backup_1777032201117` |
| 백업 엔트리 수 | 13 |
| `/audit_logs` (legacy) | **13 유지** (dual-write 기간용, 삭제 X) |
| `/audit_logs_v2/demo` | 12 |
| `/audit_logs_v2/platform` | 1 |
| pushId 보존 | ✅ |

### Bucket 분류 규칙
스크립트 `bucket_for(entry)` 함수:
1. `meta.hospitalId` 존재 → 그 값
2. `meta.claims.hospitalId` 존재 → 그 값 (seed/migration/bootstrap 계열)
3. action 이 `chatbot.*` 또는 `wait_queue.*` 이고 target 이 string → target 을 hospitalId 로
4. 그 외 → `platform` bucket (platformAdmin 시스템 액션)

### Action 분포 (총 13건)
| action | 건수 | bucket |
|--------|------|--------|
| user.claims.seed.create | 8 | demo |
| user.claims.migration.v1 | 2 | demo |
| chatbot.reply | 2 | demo |
| user.claims.bootstrap.platformAdmin | 1 | platform |

### 롤백 절차
```bash
# 백업으로부터 /audit_logs 복원 (audit_logs_v2 는 별도 정리)
python3 mediway/scripts/migrate-audit-logs-to-v2.py --rollback 1777032201117
```
필요 시 `/audit_logs_v2` 를 수동 삭제:
```bash
TOKEN=$(gcloud auth print-access-token)
curl -X DELETE "https://mediway-demo-default-rtdb.firebaseio.com/audit_logs_v2.json?access_token=${TOKEN}"
```

---

## 다음 단계 (T1-1b / T1-1c 예정)

- **T1-1b** — Cloud Functions (`onQueueCall`, `hospitalChatbot`, 기타) 에서
  audit 기록 경로를 dual-write 로 변경 (`audit_logs` + `audit_logs_v2/{hid}` 양쪽).
  안정성 확인 후 cutover (v2 전용).
- **T1-1c** — `database.rules.json` 에 `audit_logs_v2` rule 추가 +
  기존 `audit_logs` rule 은 write 금지 + platformAdmin read only 로 tighten.
  AdminAuditPage 조회 경로를 v2 로 전환.

---

## 2026-04-24 — T1-2a: visit_plans nested 경로 backfill

관련 스크립트: `mediway/scripts/migrate-visit-plans-to-nested.py`
기획 근거: `mediway/docs/LOCAL_SYNC_GAPS.md` § 2 — visit_plans 이중 구조 정리.

### 실행 결과
| 항목 | 값 |
|------|-----|
| 백업 경로 | `/visit_plans_backup_1777034578225` |
| 백업 엔트리 수 | 2 |
| `/visit_plans` (legacy) | 2 유지 (T1-2c cutover 전까지 보존) |
| `/hospitals/demo/visit_plans/*` | 2 (모두 demo 로 정확 추론) |
| hospitalId 필드 | nested entry 에 주입 완료 |

### Bucket 분류 근거
- entry 1: `users/{uid}/hospitalId = 'demo'`
- entry 2: `users/{uid}/primaryHospitalId = 'demo'` (박준영 platformAdmin)
- unknown bucket 발생 건수: 0

### 롤백 절차
```bash
# 백업에서 /visit_plans 복원 (nested 는 별도 정리)
python3 mediway/scripts/migrate-visit-plans-to-nested.py --rollback 1777034578225
```
nested 를 수동 삭제할 경우:
```bash
TOKEN=$(gcloud auth print-access-token)
curl -X DELETE "https://mediway-demo-default-rtdb.firebaseio.com/hospitals/demo/visit_plans.json?access_token=${TOKEN}"
```

### 다음 단계 (T1-2c)
- `src/services/visitPlan.ts` 에서 legacy write/subscribe/read fallback 제거.
- `database.rules.json` 의 root `/visit_plans` 관대처리 제거
  (.read: platformAdmin only, $uid/.write: false).
- `e2e-hospital-isolation.html` 시나리오 #8 (legacy visit_plans 쓰기 허용) 기대값을
  '차단' 으로 업데이트.
- `firebase deploy --only database`.

---

## 2026-04-24 — T1-1c / T1-2c 룰 부분 롤백 (LIVE 번들 호환성)

T1-1c + T1-2c 에서 legacy `/audit_logs` · `/visit_plans/{uid}` 의 `.write` 를
`false` 로 막았으나, 현 LIVE hosting 의 prod v2 번들 frontend 는 여전히
legacy path 에 write 한다 (appendAudit · setVisitPlan · setAutoSendOptIn).

**증상** (rule 변경 직후 LIVE):
- admin 대시보드 "최근 감사 로그" 공란 — 룰로 read denied (Part A 로 이미 복구)
- 관리자 액션 (role 변경, 코드 발급 등) 시 프런트 `appendAudit` → 401 denied → silent
  data loss (audit 기록 누락)
- 환자가 visit_plan 생성/수정 시도 → 401 denied → UI 실패

**조치 — 2026-04-24 17:?? KST**:
- `audit_logs/$id/.write` 를 원복 (legacy 시대 규칙):
  `auth != null && !data.exists() && newData.child('actorUid').val() === auth.uid`
- `visit_plans/$uid/.read|.write` 도 기존 관대처리 형태로 복구 (staff/admin/self 허용).
  단 `wait_queue_by_patient` · `wait_queue_counters` 등 T0-1 에서 추가된 nested 는 그대로 유지.
- `.write: false` 는 **prod parity + LIVE 재배포 시점** 까지 연기.

**이번 변경이 의미하는 것**:
- audit/visit_plan 의 cross-tenant 격리 효과가 prod parity 전까지 **legacy 쪽은 약화**
  (nested `/hospitals/{hid}/...` 는 여전히 strict 유지)
- Demo 단일 병원 운영 중에는 실질 영향 미미
- Server 측 신규 write 는 이미 v2 전용 (T1-1c 유지). Frontend 만 legacy write 허용

---

## 📅 예약 작업 — Legacy `/audit_logs` + `/visit_plans` 완전 purge

관련 스크립트: `mediway/scripts/purge-legacy-paths.py` (작성만, 실행은 아래 조건 만족 후)

### 실행 전제 (모두 충족해야 함)
1. **LIVE hosting 번들이 prod parity 에 도달 + 전체 재배포 완료**
   - Phase B-3 item 10 (`/h/:slug/*` nested routing + HospitalShell) 이식
   - Phase B-2 step 5~8 (StaffQueuePage, AppointmentsTab, ChatbotWidget, MoreTab) local 소스 포함한 번들 배포
2. **새 프런트엔드가 v2 경로만 사용**
   - `appendAudit` → `/audit_logs_v2/{hid}` 만 write
   - `setVisitPlan` / `subscribeVisitPlan` → `/hospitals/{hid}/visit_plans/{uid}` 만 read/write
3. **Legacy traffic 제로 확인** — Firebase console · Usage 탭 기준 24h 이상 write/read 0건
4. **백업 존재 확인** — `/audit_logs_backup_*` · `/visit_plans_backup_*` 가 RTDB 에 남아 있어야
   rollback 경로 확보

### 실행 절차 (조건 충족 후)
```bash
# 현 상태 확인
python3 mediway/scripts/purge-legacy-paths.py --dry-run

# 실제 삭제 (실행자가 전제 조건 모두 확인했음을 --confirm 으로 확약)
python3 mediway/scripts/purge-legacy-paths.py --apply --confirm
```
스크립트가 수행:
- `/audit_logs` DELETE
- `/visit_plans` DELETE
- `/audit_logs_backup_*` · `/visit_plans_backup_*` 는 **그대로 보존** (rollback 용)
- 실행 후 verify (빈 경로 확인)

### Purge 이후 마무리 (동일 PR 에서 함께)
- `database.rules.json` 에서 `audit_logs` · `visit_plans` 루트 block 완전 삭제
  (또는 `".read": "false", ".write": "false"` 로 재명시 — rule 명시성이 감사 관점에서 유리)
- `firebase deploy --only database`
- `e2e-hospital-isolation.html` 에서 관련 시나리오 제거 또는 기대값 재검토

### Rollback 시나리오 (purge 이후 문제 발견)
```bash
TOKEN=$(gcloud auth print-access-token)
# audit_logs 복구
curl -X PUT "https://mediway-demo-default-rtdb.firebaseio.com/audit_logs.json?access_token=${TOKEN}" \
  --data "@<(curl -sS \"https://mediway-demo-default-rtdb.firebaseio.com/audit_logs_backup_1777032201117.json?access_token=${TOKEN}\")"
# visit_plans 복구
curl -X PUT "https://mediway-demo-default-rtdb.firebaseio.com/visit_plans.json?access_token=${TOKEN}" \
  --data "@<(curl -sS \"https://mediway-demo-default-rtdb.firebaseio.com/visit_plans_backup_1777034578225.json?access_token=${TOKEN}\")"
# 룰도 이전 버전으로 일시 되돌려 frontend 정상화 시까지 유지
```

### 최종 상태 (purge 완료 후)
- `/audit_logs` · `/visit_plans` 노드 없음
- `/audit_logs_v2/{hid}` · `/hospitals/{hid}/visit_plans/{uid}` 만 authoritative
- backup 은 다음 sprint 에서 필요성 재검토 후 수동 삭제 (storage 이슈 없으면 장기 보존도 OK)
