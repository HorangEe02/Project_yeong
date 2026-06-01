# Backend Deploy Runbook (canary + smoke gate)

> v3.6.1 — 2026-05-07 인시던트 회고 후 도입한 표준 배포 절차.
> 이전 사고 이력:
>   - **00102~00105**: startup hook 실패로 `Firestore → SQLite 동기화` 누락 (사용자 username 미반영, 부서 빈칸 등 이차 회귀)
>   - **00104**: `requirements.txt` ↔ `requirements-cloudrun.txt` 의 분기로 `python-multipart` 미설치 → gunicorn worker boot 실패
>   - **HR Stats 500**: `features/search/__init__.py` top-level import 가 admin/HR 라우트에 BM25 강제 의존 → `ModuleNotFoundError`

각 사고가 traffic 100% 직후에야 노출되었기에, **promote 전 자동 가드**를 표준화한다.

---

## 가드 구성요소 (single source of truth)

| 자산 | 역할 |
|---|---|
| [`Dockerfile`](../Dockerfile) | 단일 multi-stage 이미지 (`slim` / `full` target). 이전 두 Dockerfile 분리 + 임시 파일 swap 패턴 폐기 |
| [`scripts/smoke-test.sh`](../scripts/smoke-test.sh) | 재사용 가능 검증 — HTTP probe (5xx 금지) + startup 로그 grep (필수/금지 키워드) |
| [`scripts/deploy-backend.sh`](../scripts/deploy-backend.sh) | canary 흐름 자동화 — no-traffic 배포 → smoke → 10% canary → 모니터링 → 100% promote (실패 시 자동 rollback) |
| [`cloudbuild.yaml`](../cloudbuild.yaml) | Cloud Build 파이프라인 — build → no-traffic deploy → smoke. **트래픽 promote 는 의도적으로 수행 안 함** (인간 승인 게이트) |
| [`scripts/deploy-fullmode.sh`](../scripts/deploy-fullmode.sh) | DEPRECATED — `deploy-backend.sh --mode full` 로 위임 |

---

## 표준 배포 절차

### A. 로컬 CLI (가장 일반적)

```bash
cd ajin-ai-assistant-react
bash scripts/deploy-backend.sh                    # 슬림, canary 10% → 100%
bash scripts/deploy-backend.sh --mode full        # 풀 모드
```

자동 흐름:

1. Pre-flight (gcloud auth, Dockerfile 존재, smoke-test.sh 존재)
2. `gcloud run deploy --source . --no-traffic --tag deploy-YYYYMMDD-HHMMSS`
3. **Smoke test** on tag URL (HTTP probe + startup 로그 grep)
4. Canary 10% 적용 → 180초 모니터링 (5xx rate)
5. 5xx 0건이면 100% promote, 아니면 자동 rollback
6. Production URL 에서 final smoke test

각 단계 로그는 `/tmp/ajin-deploy-logs/deploy-YYYYMMDD-HHMMSS.log` 에 tee.

### B. Cloud Build (CI 트리거)

```bash
gcloud builds submit --config=cloudbuild.yaml                              # slim
gcloud builds submit --config=cloudbuild.yaml --substitutions=_MODE=full   # full
```

파이프라인이 **build → no-traffic deploy → smoke** 까지만 실행. **트래픽 promote 는 수동.** 빌드 통과 후:

```bash
# 같은 tag 를 canary 로 promote
bash scripts/deploy-backend.sh --tag <TAG_FROM_BUILD>

# 또는 즉시 100% (긴급 hotfix 등)
gcloud run services update-traffic ajin-backend \
  --region=asia-northeast3 --to-revisions=<리비전명>=100
```

### C. 수동 (가드 우회 시)

원칙적으로 사용 금지. 부득이하게 필요 시:
```bash
gcloud run deploy ajin-backend --source=. --region=asia-northeast3 --no-traffic --tag adhoc-fix
bash scripts/smoke-test.sh https://adhoc-fix---ajin-backend-ncsnraqdaa-du.a.run.app
# smoke pass 확인 후 trafficsplit 직접 변경
```

---

## Smoke test 검사 항목

[`scripts/smoke-test.sh`](../scripts/smoke-test.sh) 가 다음을 모두 통과해야 0 (성공) 으로 종료:

| 단계 | 항목 | 기대 |
|---|---|---|
| HTTP probe | `POST /api/auth/login`, `GET /api/admin/hr/summary` | 5xx 아님 (401/200/404 등 OK) |
| 필수 startup 로그 | `Application startup complete` | 출력됨 |
| 필수 startup 로그 | `✓ 인증 DB 초기화 완료` | 출력됨 |
| 필수 startup 로그 | `Firestore → SQLite 동기화 완료` (AUTH_BACKEND=firestore 시) | 출력됨 |
| 금지 키워드 | `ModuleNotFoundError` | 0건 |
| 금지 키워드 | `Worker failed to boot` | 0건 |
| 금지 키워드 | `HaltServer` | 0건 |
| 금지 키워드 | `Application startup failed` | 0건 |

**각 인시던트 매핑:**
- 00104 회귀: `Worker failed to boot` 키워드로 차단
- 00105 회귀: `Firestore → SQLite 동기화 완료` 누락으로 차단
- BM25 회귀: `ModuleNotFoundError` 키워드로 차단

---

## Rollback

### 즉시 환원 (5xx 폭주 등)
```bash
bash scripts/deploy-backend.sh --rollback
# 또는 명시:
bash scripts/deploy-backend.sh --rollback --lkg ajin-backend-00101-ldw
```

### 수동
```bash
gcloud run services update-traffic ajin-backend \
  --region=asia-northeast3 \
  --to-revisions=<이전-안정-리비전>=100
```

Cloud Run 은 직전 revision 들을 자동 보존 → 1-click rollback 가능.

---

## 디버깅 가이드 (smoke 실패 시)

### "Required startup log missing: Firestore → SQLite 동기화 완료"
- AUTH_BACKEND env 변수가 누락됐거나 `firestore` 가 아님
- 또는 Firestore 클라이언트 초기화 실패 ([`core/auth/database.py:_sync_from_firestore_if_enabled`](../core/auth/database.py))
- 점검: `gcloud run services describe ajin-backend --format='value(spec.template.spec.containers[0].env)'` 에 `AUTH_BACKEND=firestore` 확인

### "Forbidden keyword detected: ModuleNotFoundError"
- 의존성 누락 — 새 import 가 추가됐는데 `requirements-cloudrun.txt`(slim) 또는 `requirements-cloudrun-full.txt`(full) 에 반영 안 됨
- 점검: 실패한 모듈명 grep 으로 import 위치 추적
- 수정: 해당 requirements 파일에 추가

### "HTTP probe failed: try=N/N HTTP 503"
- Cold start 타임아웃 또는 worker boot 실패
- 점검: Cloud Run 로그에서 `gunicorn` startup 로그 확인 — `RuntimeError`, `HaltServer` 등
- 자주 보이는 패턴: import 시 외부 리소스 fetch (vectorstore 다운로드, 모델 weight 등) 가 startup probe timeout 초과

### "tag URL 추론 실패" (Cloud Build)
- `--tag` 가 적용되지 않은 deploy. 보통 deploy step 의 `--no-traffic --tag=...` 인자 누락
- 점검: 빌드 로그에서 `gcloud run deploy` step 의 args 확인

---

## 변경 이력

- 2026-05-07: 초판. Dockerfile 단일화, smoke-test.sh / deploy-backend.sh / cloudbuild.yaml 도입
