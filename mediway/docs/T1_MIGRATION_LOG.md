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
