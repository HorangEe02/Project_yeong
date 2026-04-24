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
